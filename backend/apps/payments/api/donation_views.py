"""The public donation page's endpoints: open to anyone, proved by a signed token.

Nobody signs in to give on the public site, so every view here allows an anonymous
caller.  The session authentication class still enforces CSRF on every unsafe
method, so only a page served by this site can start or finish a gift, and starting
one is throttled by client address under the ``donate`` rate.  Starting a gift
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

from apps.accounts.throttling import DonateThrottle
from apps.darts.models import Dart
from apps.members.models import CALIFORNIA_COUNTIES, US_STATE_CHOICES
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
from apps.payments.api.views import confirmed, payment_result
from apps.payments.donations import (
    HAS_ACCOUNT_CODE,
    HAS_ACCOUNT_MESSAGE,
    DonationTokenError,
    DonorFields,
    HasAccountError,
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

        The donor behind the address is found or made and given the details sent
        (:func:`apps.payments.donations.donor_for`), then a pending contribution of
        ``contribution_cents`` is started with the provider.  ``client`` is what the
        provider's browser SDK needs, as the portal checkout answers it; ``token``
        proves the caller for the calls that finish the payment.

        400 ``{"email": [...], "code": "has_account"}`` when the address belongs to a
        member or a friend, active or not; 400 by field for a detail the profile's rules
        refuse, for a gift of nothing, and for a provider that is not configured; 400
        with ``detail`` when the provider refuses to start.  Any refusal writes nothing.
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
        try:
            with transaction.atomic():
                payment = start_donation(fields, data["contribution_cents"], provider)
                try:
                    client = get_provider(provider).start(payment)
                except PaymentError as exc:
                    raise ValidationError({"detail": str(exc)}) from exc
        except HasAccountError as exc:
            raise ValidationError(
                {"email": [HAS_ACCOUNT_MESSAGE], "code": HAS_ACCOUNT_CODE}
            ) from exc

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

    @extend_schema(
        request=DonationStripeConfirmSerializer, responses={200: PaymentResultSerializer}
    )
    def post(self, request: Request) -> Response:
        """200 with ``{status, membership}`` once Stripe has been asked about the intent.

        404 without the payment's token; 400 keyed by ``payment_id`` for a payment
        started with another provider; 400 with ``detail`` when Stripe disagrees or
        cannot be reached.
        """
        serializer = DonationStripeConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = proven_payment(serializer.validated_data, provider=PaymentProvider.STRIPE)
        return confirmed(
            payment,
            PaymentProvider.STRIPE,
            payment_intent_id=serializer.validated_data["payment_intent_id"],
        )


class DonationPayPalCaptureView(APIView):
    """``POST /donations/paypal/capture`` -- capture the order, then settle the gift."""

    permission_classes = [AllowAny]

    @extend_schema(
        request=DonationPayPalCaptureSerializer, responses={200: PaymentResultSerializer}
    )
    def post(self, request: Request) -> Response:
        """200 with ``{status, membership}`` once the PayPal order has been captured.

        404 without the payment's token; 400 keyed by ``payment_id`` for a payment
        started with another provider; 400 with ``detail`` when PayPal reports anything
        but a completed capture for the right amount, or cannot be reached.
        """
        serializer = DonationPayPalCaptureSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = proven_payment(serializer.validated_data, provider=PaymentProvider.PAYPAL)
        return confirmed(
            payment, PaymentProvider.PAYPAL, order_id=serializer.validated_data["order_id"]
        )


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
        return confirmed(
            payment, PaymentProvider.MOCK, outcome=serializer.validated_data["outcome"]
        )


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
        return Response(PaymentResultSerializer(payment_result(payment)).data)
