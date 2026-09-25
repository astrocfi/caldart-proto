"""The payments API: checkout, each provider's confirmation, and the webhooks.

Two rules run through every view here:

* the server never trusts a client-supplied amount -- totals are recomputed
  from the plan price plus the contribution in
  :func:`apps.payments.services.create_checkout`; and
* a membership is only activated after the *provider* has confirmed the money,
  which is why the confirm endpoints re-fetch the intent or capture the order
  rather than believing the browser.

The finance area's own endpoints -- the list, the reports, the ledger and the
reconciliation -- live in ``report_views.py``.
"""

from __future__ import annotations

from typing import Any, cast

from django.conf import settings
from django.http import Http404, HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status as http_status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import user_has_any_role
from apps.accounts.roles import ACCOUNT_ADMIN, TREASURER
from apps.members.models import MembershipPlan
from apps.members.services import membership_status
from apps.payments.api.serializers import (
    CheckoutResponseSerializer,
    CheckoutSerializer,
    MockCompleteSerializer,
    PaymentResultSerializer,
    PaymentsConfigSerializer,
    PayPalCaptureSerializer,
    StripeConfirmSerializer,
)
from apps.payments.models import (
    CONTRIBUTION_TIERS,
    MAX_CONTRIBUTION_CENTS,
    Payment,
    PaymentProvider,
)
from apps.payments.providers import available_providers, get_provider
from apps.payments.providers.base import PaymentError
from apps.payments.renewals import begin_mandate, discard_pending_mandate
from apps.payments.services import create_checkout
from caldart.exceptions import DomainValidationError

#: What the webhook endpoints answer with.  The provider chooses the body, and
#: neither portal screen reads it, so the schema describes only the status.
WEBHOOK_RESPONSE_DESCRIPTION = (
    "Acknowledged.  The body is whatever the provider's own handler returns."
)


def payment_result(payment: Payment) -> dict[str, Any]:
    """The ``{status, membership}`` body every confirm endpoint answers with.

    ``membership`` is the payer's membership as it stands after the payment, so a
    caller never has to fetch it separately.
    """
    return {"status": payment.status, "membership": membership_status(payment.user)}


def signed_in_user(request: Request) -> User:
    """The member behind a request an ``IsAuthenticated`` permission has let through.

    Every caller runs after that permission, so the user is never anonymous.  DRF
    types ``Request.user`` as either a user or ``AnonymousUser`` whatever the
    permissions say, which is what the cast records.
    """
    return cast(User, request.user)


def load_payment(payment_id: int, user: User, *, provider: str | None = None) -> Payment:
    """The caller's own payment, or 404.

    Confirmation endpoints are deliberately owner-only: an account admin has no
    business completing somebody else's checkout, so another member's payment
    raises ``Http404`` exactly as an unknown id does.  When ``provider`` is given
    and the payment was not started with it, raises DRF's ``ValidationError``
    keyed by ``payment_id``.
    """
    payment = Payment.objects.filter(pk=payment_id, user=user).first()
    if payment is None:
        raise Http404("No such payment.")
    if provider is not None and payment.provider != provider:
        raise ValidationError({"payment_id": f"That payment is not a {provider} payment."})
    return payment


class IsPaymentOwnerOrFinance(BasePermission):
    """Object permission for ``GET /payments/{id}``."""

    def has_object_permission(self, request: Request, view: APIView, obj: Payment) -> bool:
        """Whether ``request.user`` owns ``obj``, or holds a finance role.

        The finance roles are ``treasurer`` and ``account_admin``; a system
        administrator passes through the usual rule.
        """
        if obj.user_id == request.user.id:
            return True
        return user_has_any_role(request.user, (TREASURER, ACCOUNT_ADMIN))


# --------------------------------------------------------------------------
# Checkout
# --------------------------------------------------------------------------
class PaymentsConfigView(APIView):
    """``GET /payments/config`` -- what the checkout UI can offer."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: PaymentsConfigSerializer})
    def get(self, request: Request) -> Response:
        """200 with what the checkout screen may offer.

        Names the configured providers, their publishable keys, the active plans,
        the contribution tiers and the largest contribution checkout accepts.  Any
        signed-in member may ask.
        """
        plans = MembershipPlan.objects.filter(is_active=True)
        data = {
            "providers": available_providers(),
            "stripe_publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
            "paypal_client_id": settings.PAYPAL_CLIENT_ID,
            "plans": plans,
            "contribution_tiers": CONTRIBUTION_TIERS,
            "max_contribution_cents": MAX_CONTRIBUTION_CENTS,
        }
        return Response(PaymentsConfigSerializer(data).data)


class CheckoutView(APIView):
    """``POST /payments/checkout`` -- create the pending payment and start it."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=CheckoutSerializer, responses={201: CheckoutResponseSerializer})
    def post(self, request: Request) -> Response:
        """201 with ``{payment_id, provider, client}`` for a signed-in member.

        ``client`` is whatever the chosen provider's browser SDK needs.  400 when
        the provider is not configured, when the plan or the contribution is one
        the server will not charge for, or when the provider refuses to start the
        payment -- in which case the pending payment is deleted again.

        A life member has nothing to renew, so a ``plan`` from one is a 400 naming
        ``plan``: their checkout is a contribution, with or without a standing
        authority behind it.

        ``auto_renew`` asks for the method to be saved and the membership renewed
        from it each year: a ``pending`` mandate is created before the provider is
        started, so the provider knows to save the method, and it becomes active
        when the payment succeeds.  A life member's mandate carries no plan and
        charges the contribution once a year.  400 naming ``auto_renew`` for a plan
        that never expires, for a checkout by a member who is not a life member
        that buys no plan, for a life member who contributes nothing, and for a
        provider that cannot charge a saved method -- and the pending payment is
        deleted again, exactly as it is when the provider refuses to start.

        ``next_charge_on`` is the day that authority first charges on, and a day
        before today is a 400 naming ``next_charge_on``.  Left out, the first
        charge falls on the day the term this payment buys runs out.

        A checkout that does *not* ask for automatic renewal throws away any
        pending mandate the member is still carrying from a checkout they
        abandoned, so no method is ever saved against a member who said no.
        """
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        provider_slug = serializer.validated_data["provider"]

        if provider_slug not in available_providers():
            raise ValidationError({"provider": f"'{provider_slug}' is not configured."})

        user = signed_in_user(request)
        payment = create_checkout(
            user,
            serializer.validated_data.get("plan") or None,
            serializer.validated_data["contribution_cents"],
            provider_slug,
        )
        if serializer.validated_data["auto_renew"]:
            # Before the provider is started: Stripe needs a customer on the
            # intent and PayPal a vault instruction on the order, and neither can
            # be added after the fact.
            try:
                begin_mandate(
                    user,
                    plan=payment.plan,
                    contribution_cents=payment.contribution_cents,
                    provider=provider_slug,
                    next_charge_on=serializer.validated_data["next_charge_on"],
                )
            except DomainValidationError:
                payment.delete()
                raise
        else:
            discard_pending_mandate(user)
        try:
            client = get_provider(provider_slug).start(payment)
        except PaymentError as exc:
            payment.delete()
            raise ValidationError({"detail": str(exc)}) from exc

        return Response(
            {"payment_id": payment.pk, "provider": provider_slug, "client": client},
            status=http_status.HTTP_201_CREATED,
        )


class StripeConfirmView(APIView):
    """``POST /payments/stripe/confirm`` -- verify with Stripe, then activate."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=StripeConfirmSerializer, responses={200: PaymentResultSerializer})
    def post(self, request: Request) -> Response:
        """200 with ``{status, membership}`` once Stripe has been asked about the intent.

        The caller must own the payment, which must be a Stripe payment: anything
        else is a 404, or a 400 keyed by ``payment_id``.  400 as well when Stripe
        disagrees with our row or cannot be reached; the membership is activated
        only when Stripe reports the intent as succeeded.
        """
        serializer = StripeConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = load_payment(
            serializer.validated_data["payment_id"],
            signed_in_user(request),
            provider=PaymentProvider.STRIPE,
        )
        try:
            get_provider(PaymentProvider.STRIPE).confirm(
                payment,
                payment_intent_id=serializer.validated_data["payment_intent_id"],
            )
        except PaymentError as exc:
            raise ValidationError({"detail": str(exc)}) from exc

        payment.refresh_from_db()
        return Response(PaymentResultSerializer(payment_result(payment)).data)


class PayPalCaptureView(APIView):
    """``POST /payments/paypal/capture`` -- capture the order, then activate."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=PayPalCaptureSerializer, responses={200: PaymentResultSerializer})
    def post(self, request: Request) -> Response:
        """200 with ``{status, membership}`` once the PayPal order has been captured.

        The caller must own the payment, which must be a PayPal payment: anything
        else is a 404, or a 400 keyed by ``payment_id``.  400 as well when PayPal
        reports anything but a completed capture for the right amount, or cannot
        be reached.
        """
        serializer = PayPalCaptureSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = load_payment(
            serializer.validated_data["payment_id"],
            signed_in_user(request),
            provider=PaymentProvider.PAYPAL,
        )
        try:
            get_provider(PaymentProvider.PAYPAL).confirm(
                payment, order_id=serializer.validated_data["order_id"]
            )
        except PaymentError as exc:
            raise ValidationError({"detail": str(exc)}) from exc

        payment.refresh_from_db()
        return Response(PaymentResultSerializer(payment_result(payment)).data)


class MockCompleteView(APIView):
    """``POST /payments/mock/complete`` -- dev and e2e only.

    The route answers 404 when ``PAYMENTS_MOCK_ENABLED`` is off, so production
    does not advertise a way to grant itself a membership.
    """

    permission_classes = [IsAuthenticated]

    @extend_schema(request=MockCompleteSerializer, responses={200: PaymentResultSerializer})
    def post(self, request: Request) -> Response:
        """200 with ``{status, membership}`` after completing a mock payment.

        ``outcome`` chooses between succeeding and failing it.  404 when the mock
        provider is disabled, and when the payment is not the caller's own; a
        payment the caller owns that was started with another provider is a 400
        keyed by ``payment_id``.
        """
        if not settings.PAYMENTS_MOCK_ENABLED:
            raise Http404("The mock payment provider is disabled.")

        serializer = MockCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = load_payment(
            serializer.validated_data["payment_id"],
            signed_in_user(request),
            provider=PaymentProvider.MOCK,
        )
        get_provider(PaymentProvider.MOCK).confirm(
            payment, outcome=serializer.validated_data["outcome"]
        )
        payment.refresh_from_db()
        return Response(PaymentResultSerializer(payment_result(payment)).data)


class PaymentDetailView(RetrieveAPIView[Payment]):
    """``GET /payments/{id}`` -- the owner, or a finance role."""

    permission_classes = [IsAuthenticated, IsPaymentOwnerOrFinance]
    # The view answers with the result body rather than the payment row, so this
    # is here only for DRF's own introspection, not for the response.
    serializer_class = PaymentResultSerializer  # type: ignore[assignment]
    queryset = Payment.objects.select_related("user", "plan")

    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """200 with ``{status, membership}`` for the payer or a finance role.

        Any other signed-in member gets 403, and an unknown id 404.
        """
        payment = self.get_object()
        return Response(PaymentResultSerializer(payment_result(payment)).data)


# --------------------------------------------------------------------------
# Webhooks (no session, no CSRF: the signature is the authentication)
# --------------------------------------------------------------------------
@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(APIView):
    """``POST /payments/stripe/webhook`` -- safety net for redirect methods."""

    authentication_classes = []
    permission_classes = []

    @extend_schema(
        request=None,
        responses={200: OpenApiResponse(description=WEBHOOK_RESPONSE_DESCRIPTION)},
    )
    def post(self, request: Request) -> HttpResponse:
        """Hand the signed event to the Stripe provider, which answers it.

        Unauthenticated by design: the ``Stripe-Signature`` header is what proves
        where the request came from, so an unsigned body is a 400.
        """
        return get_provider(PaymentProvider.STRIPE).handle_webhook(request)


@method_decorator(csrf_exempt, name="dispatch")
class PayPalWebhookView(APIView):
    """``POST /payments/paypal/webhook`` -- recorder; capture is authoritative."""

    authentication_classes = []
    permission_classes = []

    @extend_schema(
        request=None,
        responses={200: OpenApiResponse(description=WEBHOOK_RESPONSE_DESCRIPTION)},
    )
    def post(self, request: Request) -> HttpResponse:
        """Hand the notification to the PayPal provider, which records it.

        Unauthenticated by design: PayPal's own verification call is what proves
        where the request came from, and an unverified notification is filed
        against the payment without changing it.
        """
        return get_provider(PaymentProvider.PAYPAL).handle_webhook(request)
