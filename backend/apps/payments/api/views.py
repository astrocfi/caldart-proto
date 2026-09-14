"""Payments API and payment reports.

Two rules run through every view here:

* the server never trusts a client-supplied amount — totals are recomputed
  from the plan price plus the contribution in
  :func:`apps.payments.services.create_checkout`; and
* a membership is only activated after the *provider* has confirmed the money,
  which is why the confirm endpoints re-fetch the intent or capture the order
  rather than believing the browser.
"""

from __future__ import annotations

from django.conf import settings
from django.http import Http404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status as http_status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAccountAdmin, user_has_any_role
from apps.accounts.roles import ACCOUNT_ADMIN
from apps.members.models import MembershipPlan
from apps.members.services import membership_status
from apps.payments import reports
from apps.payments.api.serializers import (
    CheckoutSerializer,
    MockCompleteSerializer,
    PaymentPeriodSummarySerializer,
    PaymentResultSerializer,
    PaymentsConfigSerializer,
    PaymentSerializer,
    PayPalCaptureSerializer,
    StripeConfirmSerializer,
)
from apps.payments.models import CONTRIBUTION_TIERS, Payment, PaymentProvider
from apps.payments.providers import available_providers, get_provider
from apps.payments.providers.base import PaymentError
from apps.payments.services import create_checkout
from caldart.reports import csv_response


def payment_result(payment: Payment) -> dict:
    """The ``{status, membership}`` body every confirm endpoint answers with."""
    return {"status": payment.status, "membership": membership_status(payment.user)}


def load_payment(payment_id: int, user, *, provider: str | None = None) -> Payment:
    """The caller's own pending payment, or 404.

    Confirmation endpoints are deliberately owner-only: an account admin has no
    business completing somebody else's checkout.
    """
    payment = Payment.objects.filter(pk=payment_id, user=user).first()
    if payment is None:
        raise Http404("No such payment.")
    if provider is not None and payment.provider != provider:
        raise ValidationError({"payment_id": f"That payment is not a {provider} payment."})
    return payment


class IsPaymentOwnerOrAccountAdmin(BasePermission):
    """Object permission for ``GET /payments/{id}``."""

    def has_object_permission(self, request, view, obj) -> bool:
        if obj.user_id == request.user.id:
            return True
        return user_has_any_role(request.user, (ACCOUNT_ADMIN,))


# --------------------------------------------------------------------------
# Checkout
# --------------------------------------------------------------------------
class PaymentsConfigView(APIView):
    """``GET /payments/config`` — what the checkout UI can offer."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        plans = MembershipPlan.objects.filter(is_active=True)
        data = {
            "providers": available_providers(),
            "stripe_publishable_key": settings.STRIPE_PUBLISHABLE_KEY,
            "paypal_client_id": settings.PAYPAL_CLIENT_ID,
            "plans": plans,
            "contribution_tiers": CONTRIBUTION_TIERS,
        }
        return Response(PaymentsConfigSerializer(data).data)


class CheckoutView(APIView):
    """``POST /payments/checkout`` — create the pending payment and start it."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        provider_slug = serializer.validated_data["provider"]

        if provider_slug not in available_providers():
            raise ValidationError({"provider": f"'{provider_slug}' is not configured."})

        payment = create_checkout(
            request.user,
            serializer.validated_data.get("plan") or None,
            serializer.validated_data["contribution_cents"],
            provider_slug,
        )
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
    """``POST /payments/stripe/confirm`` — verify with Stripe, then activate."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = StripeConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = load_payment(
            serializer.validated_data["payment_id"], request.user, provider=PaymentProvider.STRIPE
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
    """``POST /payments/paypal/capture`` — capture the order, then activate."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PayPalCaptureSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = load_payment(
            serializer.validated_data["payment_id"], request.user, provider=PaymentProvider.PAYPAL
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
    """``POST /payments/mock/complete`` — dev and e2e only.

    The route answers 404 when ``PAYMENTS_MOCK_ENABLED`` is off, so production
    does not advertise a way to grant itself a membership.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not settings.PAYMENTS_MOCK_ENABLED:
            raise Http404("The mock payment provider is disabled.")

        serializer = MockCompleteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = load_payment(
            serializer.validated_data["payment_id"], request.user, provider=PaymentProvider.MOCK
        )
        get_provider(PaymentProvider.MOCK).confirm(
            payment, outcome=serializer.validated_data["outcome"]
        )
        payment.refresh_from_db()
        return Response(PaymentResultSerializer(payment_result(payment)).data)


class PaymentDetailView(RetrieveAPIView):
    """``GET /payments/{id}`` — the owner, or an account admin."""

    permission_classes = [IsAuthenticated, IsPaymentOwnerOrAccountAdmin]
    serializer_class = PaymentResultSerializer
    queryset = Payment.objects.select_related("user", "plan")

    def retrieve(self, request, *args, **kwargs):
        payment = self.get_object()
        return Response(PaymentResultSerializer(payment_result(payment)).data)


# --------------------------------------------------------------------------
# Webhooks (no session, no CSRF: the signature is the authentication)
# --------------------------------------------------------------------------
@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(APIView):
    """``POST /payments/stripe/webhook`` — safety net for redirect methods."""

    authentication_classes: list = []
    permission_classes: list = []

    def post(self, request):
        return get_provider(PaymentProvider.STRIPE).handle_webhook(request)


@method_decorator(csrf_exempt, name="dispatch")
class PayPalWebhookView(APIView):
    """``POST /payments/paypal/webhook`` — recorder; capture is authoritative."""

    authentication_classes: list = []
    permission_classes: list = []

    def post(self, request):
        return get_provider(PaymentProvider.PAYPAL).handle_webhook(request)


# --------------------------------------------------------------------------
# Reports — account_admin
# --------------------------------------------------------------------------
class AdminPaymentListView(ListAPIView):
    """``GET /admin/payments`` — filtered, searchable, ordered, paginated."""

    permission_classes = [IsAuthenticated, IsAccountAdmin]
    serializer_class = PaymentSerializer
    # Filtering, search and ordering are handled here rather than by the
    # project-wide backends: they all key off the ``paid_at`` annotation.
    filter_backends: list = []

    def get_queryset(self):
        filters = reports.PaymentFilters.from_query(self.request.query_params)
        queryset = reports.apply_filters(reports.base_queryset(), filters)
        return queryset.order_by(*self.requested_ordering())

    def requested_ordering(self) -> list[str]:
        requested = (self.request.query_params.get("ordering") or "").strip()
        field = requested.lstrip("-")
        if field and field not in reports.ORDERING_FIELDS:
            raise ValidationError({"ordering": f"Cannot order by '{field}'."})
        return [requested or "-paid_at", "-id"]


class AdminPaymentSummaryView(APIView):
    """``GET /admin/payments/summary?group=month|year`` — money per period."""

    permission_classes = [IsAuthenticated, IsAccountAdmin]

    def get(self, request):
        group = (request.query_params.get("group") or "month").strip()
        filters = reports.PaymentFilters.from_query(request.query_params)
        queryset = reports.apply_filters(reports.base_queryset(), filters)
        rows = reports.summarise(queryset, group)
        return Response(PaymentPeriodSummarySerializer(rows, many=True).data)


class AdminPaymentExportView(APIView):
    """``GET /admin/payments/export.csv`` — the filtered list as a download."""

    permission_classes = [IsAuthenticated, IsAccountAdmin]

    def get(self, request):
        filters = reports.PaymentFilters.from_query(request.query_params)
        queryset = reports.apply_filters(reports.base_queryset(), filters).order_by("-paid_at")
        return csv_response(
            "caldart-payments.csv",
            reports.CSV_HEADER,
            reports.csv_rows(queryset),
        )
