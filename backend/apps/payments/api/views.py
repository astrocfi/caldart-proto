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

from typing import Any, cast

from django.conf import settings
from django.db.models import QuerySet
from django.http import Http404, HttpResponse, StreamingHttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status as http_status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import IsAccountAdmin, user_has_any_role
from apps.accounts.roles import ACCOUNT_ADMIN
from apps.members.models import MembershipPlan
from apps.members.services import membership_status
from apps.payments import reports
from apps.payments.api.serializers import (
    CheckoutSerializer,
    MockCompleteSerializer,
    PaymentPeriodSummarySerializer,
    PaymentReportQuerySerializer,
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


class IsPaymentOwnerOrAccountAdmin(BasePermission):
    """Object permission for ``GET /payments/{id}``."""

    def has_object_permission(self, request: Request, view: APIView, obj: Payment) -> bool:
        """Whether ``request.user`` owns ``obj``, or holds the ``account_admin`` role."""
        if obj.user_id == request.user.id:
            return True
        return user_has_any_role(request.user, (ACCOUNT_ADMIN,))


# --------------------------------------------------------------------------
# Checkout
# --------------------------------------------------------------------------
class PaymentsConfigView(APIView):
    """``GET /payments/config`` — what the checkout UI can offer."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        """200 with what the checkout screen may offer.

        Names the configured providers, their publishable keys, the active plans
        and the contribution tiers.  Any signed-in member may ask.
        """
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

    def post(self, request: Request) -> Response:
        """201 with ``{payment_id, provider, client}`` for a signed-in member.

        ``client`` is whatever the chosen provider's browser SDK needs.  400 when
        the provider is not configured, when the plan or the contribution is one
        the server will not charge for, or when the provider refuses to start the
        payment -- in which case the pending payment is deleted again.
        """
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        provider_slug = serializer.validated_data["provider"]

        if provider_slug not in available_providers():
            raise ValidationError({"provider": f"'{provider_slug}' is not configured."})

        payment = create_checkout(
            signed_in_user(request),
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
    """``POST /payments/paypal/capture`` — capture the order, then activate."""

    permission_classes = [IsAuthenticated]

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
    """``POST /payments/mock/complete`` — dev and e2e only.

    The route answers 404 when ``PAYMENTS_MOCK_ENABLED`` is off, so production
    does not advertise a way to grant itself a membership.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        """200 with ``{status, membership}`` after completing a mock payment.

        ``outcome`` chooses between succeeding and failing it.  404 when the mock
        provider is disabled, and when the payment is not the caller's own mock
        payment.
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
    """``GET /payments/{id}`` — the owner, or an account admin."""

    permission_classes = [IsAuthenticated, IsPaymentOwnerOrAccountAdmin]
    # The view answers with the result body rather than the payment row, so this
    # is here only for DRF's own introspection, not for the response.
    serializer_class = PaymentResultSerializer  # type: ignore[assignment]
    queryset = Payment.objects.select_related("user", "plan")

    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """200 with ``{status, membership}`` for the payer or an account admin.

        Any other signed-in member gets 403, and an unknown id 404.
        """
        payment = self.get_object()
        return Response(PaymentResultSerializer(payment_result(payment)).data)


# --------------------------------------------------------------------------
# Webhooks (no session, no CSRF: the signature is the authentication)
# --------------------------------------------------------------------------
@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(APIView):
    """``POST /payments/stripe/webhook`` — safety net for redirect methods."""

    authentication_classes = []
    permission_classes = []

    def post(self, request: Request) -> HttpResponse:
        """Hand the signed event to the Stripe provider, which answers it.

        Unauthenticated by design: the ``Stripe-Signature`` header is what proves
        where the request came from, so an unsigned body is a 400.
        """
        return get_provider(PaymentProvider.STRIPE).handle_webhook(request)


@method_decorator(csrf_exempt, name="dispatch")
class PayPalWebhookView(APIView):
    """``POST /payments/paypal/webhook`` — recorder; capture is authoritative."""

    authentication_classes = []
    permission_classes = []

    def post(self, request: Request) -> HttpResponse:
        """Hand the notification to the PayPal provider, which records it.

        Unauthenticated by design: PayPal's own verification call is what proves
        where the request came from, and an unverified notification is filed
        against the payment without changing it.
        """
        return get_provider(PaymentProvider.PAYPAL).handle_webhook(request)


# --------------------------------------------------------------------------
# Reports — account_admin
# --------------------------------------------------------------------------
def report_query(request: Request) -> PaymentReportQuerySerializer:
    """The validated report parameters of ``request``.

    Raises DRF's ``ValidationError`` -- a 400 keyed by the parameter at fault --
    for anything the three report endpoints will not act on.
    """
    serializer = PaymentReportQuerySerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    return serializer


class AdminPaymentListView(ListAPIView[Payment]):
    """``GET /admin/payments`` — filtered, searchable, ordered, paginated."""

    permission_classes = [IsAuthenticated, IsAccountAdmin]
    serializer_class = PaymentSerializer
    # Filtering, search and ordering are handled here rather than by the
    # project-wide backends: they all key off the ``paid_at`` annotation.
    filter_backends = []

    def get_queryset(self) -> QuerySet[Payment]:
        """The payments the query string asks for, in the order it asks for.

        Raises DRF's ``ValidationError`` -- a 400 -- for a parameter the report
        will not act on.  Only ``account_admin`` reaches this; the page size is
        the project-wide default.
        """
        filters = report_query(self.request).to_filters()
        queryset = reports.apply_filters(reports.base_queryset(), filters)
        return queryset.order_by(*self.requested_ordering())

    def requested_ordering(self) -> list[str]:
        """The ``order_by`` arguments ``?ordering=`` asks for.

        Newest money first when the parameter is absent, and a leading ``-``
        reverses.  The id breaks ties, so paging is stable.  Raises
        DRF's ``ValidationError`` keyed by ``ordering``, saying
        ``Cannot order by '<field>'.``, for a field outside
        :data:`apps.payments.reports.ORDERING_FIELDS`.
        """
        requested = (self.request.query_params.get("ordering") or "").strip()
        field = requested.lstrip("-")
        if field and field not in reports.ORDERING_FIELDS:
            raise ValidationError({"ordering": f"Cannot order by '{field}'."})
        return [requested or "-paid_at", "-id"]


class AdminPaymentSummaryView(APIView):
    """``GET /admin/payments/summary?group=month|year`` — money per period."""

    permission_classes = [IsAuthenticated, IsAccountAdmin]

    def get(self, request: Request) -> Response:
        """200 with one row per period, oldest first, for ``account_admin`` only.

        The same filters as the list narrow it, and only succeeded payments count.
        400 for a parameter the report will not act on, ``group`` included.
        """
        query = report_query(request)
        queryset = reports.apply_filters(reports.base_queryset(), query.to_filters())
        rows = reports.summarize(queryset, query.validated_data["group"])
        # The stubs take the instance type from the single-object parameter, so
        # they do not widen it to a list when ``many`` is set.
        serializer = PaymentPeriodSummarySerializer(rows, many=True)  # type: ignore[arg-type]
        return Response(serializer.data)


class AdminPaymentExportView(APIView):
    """``GET /admin/payments/export.csv`` — the filtered list as a download."""

    permission_classes = [IsAuthenticated, IsAccountAdmin]

    def get(self, request: Request) -> StreamingHttpResponse:
        """200 with ``caldart-payments.csv`` as an attachment, for ``account_admin`` only.

        The same filters as the list narrow it, and the rows are newest money
        first.  400 for a parameter the report will not act on.
        """
        filters = report_query(request).to_filters()
        # django-stubs cannot see the ``paid_at`` annotation the queryset carries.
        queryset = reports.apply_filters(reports.base_queryset(), filters).order_by(
            "-paid_at"  # type: ignore[misc]
        )
        return csv_response(
            "caldart-payments.csv",
            reports.CSV_HEADER,
            reports.csv_rows(queryset),
        )
