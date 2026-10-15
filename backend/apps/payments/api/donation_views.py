"""The public donation page's endpoints: open to anyone, proved by a signed token.

Nobody signs in to give on the public site, so every view here allows an anonymous
caller.  The session authentication class still enforces CSRF on every unsafe
method, so only a page served by this site can start or finish a gift.  Starting one
is throttled by client address under the ``donate`` rate, and confirming one with
Stripe or capturing it with PayPal under the ``donate_confirm`` rate.  Starting a gift
answers a token (:func:`apps.payments.donations.donation_token`); every call that
finishes or reads that payment must bring it back, and a missing, forged, expired or
mismatched token reads exactly as an unknown payment does: 404.

What the provider is asked, and when a payment counts as paid, is the portal
checkout's own: the same providers, ``create_checkout`` and ``mark_succeeded``.
"""

from __future__ import annotations

from typing import Any, cast

from django.conf import settings
from django.db import transaction
from django.http import Http404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status as http_status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.throttling import DonateConfirmThrottle, DonateThrottle
from apps.darts.models import Dart
from apps.members.models import CALIFORNIA_COUNTIES, US_STATE_CHOICES
from apps.members.services import donor_membership
from apps.payments.api.donation_serializers import (
    DonationCheckoutResponseSerializer,
    DonationCheckoutSerializer,
    DonationMockCompleteSerializer,
    DonationPayPalCaptureSerializer,
    DonationsConfigSerializer,
    DonationStatusQuerySerializer,
    DonationStripeConfirmSerializer,
)
from apps.payments.api.serializers import PaymentResultSerializer
from apps.payments.api.views import confirm_payment
from apps.payments.donations import (
    DonationTokenError,
    DonorFields,
    donation_token,
    payment_for_token,
    start_donation,
)
from apps.payments.models import (
    CONTRIBUTION_TIERS,
    MAX_CONTRIBUTION_CENTS,
    Payment,
    PaymentProvider,
)
from apps.payments.providers import available_providers, get_provider
from apps.payments.providers.base import PaymentError

#: The body fields that are the giver's details rather than the payment's.
PAYMENT_FIELDS = ("contribution_cents", "provider")


def gift_result(payment: Payment) -> Response:
    """200 with ``{status, membership}`` for a gift, ``membership`` always a donor's.

    The giver may not be the account's owner, so the answer says nothing about the
    account the gift went to: ``membership`` reads ``donor`` whoever holds the address.
    """
    result = {"status": payment.status, "membership": donor_membership()}
    return Response(PaymentResultSerializer(result).data)


def proven_payment(data: dict[str, Any], *, provider: str | None = None) -> Payment:
    """The payment ``data["payment_id"]`` names, once ``data["token"]`` proves the caller.

    Raises ``Http404`` when the token does not prove it, and DRF's ``ValidationError``
    keyed by ``payment_id`` when ``provider`` is given and the payment was started with
    another one.
    """
    try:
        payment = payment_for_token(data["payment_id"], data["token"])
    except DonationTokenError as exc:
        raise Http404(str(exc)) from exc
    if provider is not None and payment.provider != provider:
        raise ValidationError({"payment_id": f"That payment is not a {provider} payment."})
    return payment


class DonationsConfigView(APIView):
    """``GET /donations/config`` -- what the public donation form offers."""

    permission_classes = [AllowAny]

    @extend_schema(responses={200: DonationsConfigSerializer})
    def get(self, request: Request) -> Response:
        """200 with the providers, their keys, the amounts, and the profile's choices.

        The amounts are the tiers, the largest gift, and the smallest
        (``DONATION_MINIMUM_CENTS``).

        ``counties`` are California's counties by name, ``darts`` the active DARTs as
        ``{id, name}`` in name order, and ``states`` every state as ``{value, label}``.
        Open to anyone and not throttled.
        """
        data = {
            "providers": available_providers(),
            "stripe_publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
            "paypal_client_id": settings.PAYPAL_CLIENT_ID,
            "contribution_tiers": CONTRIBUTION_TIERS,
            "max_contribution_cents": MAX_CONTRIBUTION_CENTS,
            "donation_minimum_cents": settings.DONATION_MINIMUM_CENTS,
            "counties": list(CALIFORNIA_COUNTIES),
            "darts": Dart.objects.filter(is_active=True).order_by("name"),
            "states": [{"value": code, "label": name} for code, name in US_STATE_CHOICES],
        }
        return Response(DonationsConfigSerializer(data).data)


class DonationCheckoutView(APIView):
    """``POST /donations/checkout`` -- make or find the donor and start the gift."""

    permission_classes = [AllowAny]
    throttle_classes = [DonateThrottle]

    @extend_schema(
        request=DonationCheckoutSerializer, responses={201: DonationCheckoutResponseSerializer}
    )
    def post(self, request: Request) -> Response:
        """201 with ``{payment_id, provider, client, token}`` for anyone.

        The donor behind the address is found or made, and a pending contribution
        of ``contribution_cents`` is started with the provider
        (:func:`apps.payments.donations.start_donation`).  The details sent are kept
        on the pending payment and written to the donor's account only once the gift
        settles.  ``client`` is what the provider's browser SDK needs, as the portal
        checkout answers it; ``token`` proves the caller for the calls that finish the
        payment.

        The answer is the same whoever holds the address: one that belongs to a member's
        or a friend's account gives to that account, and the details sent are never
        written onto it.  400 by field for a detail the profile's rules refuse, for a
        gift of nothing or of less than ``DONATION_MINIMUM_CENTS``, and for a provider
        that is not configured; 400 with ``detail``
        when the provider refuses to start.  Any refusal writes nothing.
        """
        serializer = DonationCheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        provider = data["provider"]
        if provider not in available_providers():
            raise ValidationError({"provider": f"'{provider}' is not configured."})

        # The serializer's keys, less the payment's two, are exactly DonorFields' own.
        fields = cast(
            DonorFields, {key: value for key, value in data.items() if key not in PAYMENT_FIELDS}
        )
        with transaction.atomic():
            payment = start_donation(fields, data["contribution_cents"], provider)
            try:
                client = get_provider(provider).start(payment)
            except PaymentError as exc:
                raise ValidationError({"detail": str(exc)}) from exc

        return Response(
            {
                "payment_id": payment.pk,
                "provider": provider,
                "client": client,
                "token": donation_token(payment),
            },
            status=http_status.HTTP_201_CREATED,
        )


class DonationStripeConfirmView(APIView):
    """``POST /donations/stripe/confirm`` -- verify with Stripe, then settle the gift."""

    permission_classes = [AllowAny]
    throttle_classes = [DonateConfirmThrottle]

    @extend_schema(
        request=DonationStripeConfirmSerializer, responses={200: PaymentResultSerializer}
    )
    def post(self, request: Request) -> Response:
        """200 with ``{status, membership}`` once Stripe has been asked about the intent.

        404 without the payment's token; 400 keyed by ``payment_id`` for a payment
        started with another provider; 400 with ``detail`` when Stripe disagrees or
        cannot be reached; 429 past the ``donate_confirm`` rate.  A gift that is no
        longer pending is answered as it stands, without asking Stripe.
        """
        serializer = DonationStripeConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = proven_payment(serializer.validated_data, provider=PaymentProvider.STRIPE)
        confirm_payment(
            payment,
            PaymentProvider.STRIPE,
            payment_intent_id=serializer.validated_data["payment_intent_id"],
        )
        return gift_result(payment)


class DonationPayPalCaptureView(APIView):
    """``POST /donations/paypal/capture`` -- capture the order, then settle the gift."""

    permission_classes = [AllowAny]
    throttle_classes = [DonateConfirmThrottle]

    @extend_schema(
        request=DonationPayPalCaptureSerializer, responses={200: PaymentResultSerializer}
    )
    def post(self, request: Request) -> Response:
        """200 with ``{status, membership}`` once the PayPal order has been captured.

        404 without the payment's token; 400 keyed by ``payment_id`` for a payment
        started with another provider; 400 with ``detail`` when PayPal reports anything
        but a completed capture for the right amount, or cannot be reached; 429 past the
        ``donate_confirm`` rate.  A gift that is no longer pending is answered as it
        stands, without asking PayPal.
        """
        serializer = DonationPayPalCaptureSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = proven_payment(serializer.validated_data, provider=PaymentProvider.PAYPAL)
        confirm_payment(
            payment, PaymentProvider.PAYPAL, order_id=serializer.validated_data["order_id"]
        )
        return gift_result(payment)


class DonationMockCompleteView(APIView):
    """``POST /donations/mock/complete`` -- dev and e2e only.

    The route answers 404 when ``PAYMENTS_MOCK_ENABLED`` is off, exactly as the
    portal's does.
    """

    permission_classes = [AllowAny]

    @extend_schema(request=DonationMockCompleteSerializer, responses={200: PaymentResultSerializer})
    def post(self, request: Request) -> Response:
        """200 with ``{status, membership}`` after succeeding or failing a mock gift.

        404 when the mock provider is disabled and without the payment's token; 400
        keyed by ``payment_id`` for a payment started with another provider.
        """
        if not settings.PAYMENTS_MOCK_ENABLED:
            raise Http404("The mock payment provider is disabled.")
        serializer = DonationMockCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = proven_payment(serializer.validated_data, provider=PaymentProvider.MOCK)
        confirm_payment(payment, PaymentProvider.MOCK, outcome=serializer.validated_data["outcome"])
        return gift_result(payment)


class DonationStatusView(APIView):
    """``GET /donations/{id}?token=`` -- a gift's status, for a redirect's return."""

    permission_classes = [AllowAny]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "token", str, description="The token ``POST /donations/checkout`` answered."
            )
        ],
        responses={200: PaymentResultSerializer},
    )
    def get(self, request: Request, pk: int) -> Response:
        """200 with ``{status, membership}``, or 404 without the payment's token."""
        query = DonationStatusQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        payment = proven_payment({"payment_id": pk, "token": query.validated_data["token"]})
        return gift_result(payment)
