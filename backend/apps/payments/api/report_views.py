"""The finance API: the payment list, the period summary, the tables and the ledger.

Every view here is guarded by ``IsFinance`` -- a treasurer or an account
administrator, with a system administrator passing as it does everywhere.  The
list and the tables read the same query functions the payments, reconciliation
and contributions reports read, so the figures on the screen and in a download
can never disagree.

Two things a treasurer does rather than reads also live here: recording a
payment taken by hand, and marking a payment reconciled against a statement.
Both write an audit record naming the payment and the administrator.
"""

from __future__ import annotations

from typing import Any

from django.db.models import CharField, F, Q, QuerySet, Value
from django.db.models.functions import Concat
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status as http_status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import IsFinance
from apps.members.services import membership_status
from apps.payments import reconciliation, reports
from apps.payments.api.serializers import (
    ContributionRowSerializer,
    FinanceMemberSerializer,
    FinancePaymentDetailSerializer,
    FinancePaymentSerializer,
    ManualPaymentSerializer,
    MemberLedgerSerializer,
    MemberSearchQuerySerializer,
    PaymentPatchSerializer,
    PaymentPeriodSummarySerializer,
    ReconciliationRowSerializer,
)
from apps.payments.manual import record_manual_payment
from apps.payments.models import Payment, PaymentProvider, RenewalMandate
from apps.payments.providers.base import PaymentError
from apps.payments.services import backfill_fees, fees_are_known
from caldart import audit

#: What the fee refresh answers with when the provider still cannot price a payment.
FEES_UNAVAILABLE = "The provider has no fee to report for this payment yet."

#: How many members the finance area's search answers with at most.
MEMBER_SEARCH_LIMIT = 10


def acting_finance_user(request: Request) -> User:
    """The administrator behind a request ``IsFinance`` has let through.

    Every caller runs after that permission, so the user is a real account rather
    than an anonymous one, which is what the narrowing records.
    """
    user = request.user
    assert isinstance(user, User)  # noqa: S101 - mypy strict narrowing, not test code
    return user


class AdminPaymentListView(ListAPIView[Payment]):
    """``GET /admin/payments`` -- filtered, searchable, ordered, paginated."""

    permission_classes = [IsAuthenticated, IsFinance]
    serializer_class = FinancePaymentSerializer
    # Filtering, search, and ordering are handled here rather than by the
    # project-wide backends: they all key off the ``paid_at`` annotation.
    filter_backends = []

    def get_queryset(self) -> QuerySet[Payment]:
        """The payments the query string asks for, newest money first by default.

        Raises DRF's ``ValidationError`` -- a 400 -- for a parameter the report
        will not act on.  Only a treasurer or an account administrator reaches
        this; the page size is the project-wide default.
        """
        return reports.filtered_payments(self.request.query_params)


class AdminPaymentSummaryView(APIView):
    """``GET /admin/payments/summary?group=month|year`` -- money per period."""

    permission_classes = [IsAuthenticated, IsFinance]

    @extend_schema(responses={200: PaymentPeriodSummarySerializer(many=True)})
    def get(self, request: Request) -> Response:
        """200 with one row per period, oldest first, for the finance roles only.

        The same filters as the list narrow it, and only money that arrived
        counts.  400 for a parameter the report will not act on, ``group``
        included.
        """
        query = reports.validated_query(request.query_params)
        queryset = reports.apply_filters(reports.base_queryset(), query.to_filters())
        rows = reports.summarize(queryset, query.validated_data["group"])
        # The stubs take the instance type from the single-object parameter, so
        # they do not widen it to a list when ``many`` is set.
        serializer = PaymentPeriodSummarySerializer(rows, many=True)  # type: ignore[arg-type]
        return Response(serializer.data)


class ReconciliationBaseView(APIView):
    """The reconciliation table's permission and its validated query."""

    permission_classes = [IsAuthenticated, IsFinance]

    def query(self, request: Request) -> reconciliation.ReconciliationQuerySerializer:
        """The validated range, provider and grouping, or a field-keyed 400."""
        serializer = reconciliation.ReconciliationQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        return serializer

    def rows(self, request: Request) -> list[reconciliation.ReconciliationRow]:
        """The reconciliation rows the query string asks for."""
        data = self.query(request).validated_data
        return reconciliation.reconciliation_rows(
            date_from=data["from"],
            date_to=data["to"],
            provider=data["provider"],
            group=data["group"],
        )


class AdminReconciliationView(ReconciliationBaseView):
    """``GET /admin/payments/reconciliation`` -- the books against a statement."""

    @extend_schema(responses={200: ReconciliationRowSerializer(many=True)})
    def get(self, request: Request) -> Response:
        """200 with one row per period, or per provider when ``group=provider``.

        Succeeded, partially refunded and refunded payments count; refunds are
        dated by the day they were taken.  400 for a parameter the report will
        not act on.
        """
        serializer = ReconciliationRowSerializer(self.rows(request), many=True)  # type: ignore[arg-type]
        return Response(serializer.data)


class ContributionBaseView(APIView):
    """The contributions list's permission and its validated year."""

    permission_classes = [IsAuthenticated, IsFinance]

    def year(self, request: Request) -> int:
        """The calendar year ``?year=`` asks for, defaulting to this one."""
        serializer = reports.ContributionQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        return serializer.chosen_year()

    def rows(self, year: int) -> list[reports.ContributionRow]:
        """One row per member who gave something in ``year``."""
        return reports.contribution_rows(year)


class AdminContributionsView(ContributionBaseView):
    """``GET /admin/payments/contributions?year=`` -- the acknowledgment list."""

    @extend_schema(responses={200: ContributionRowSerializer(many=True)})
    def get(self, request: Request) -> Response:
        """200 with one row per contributing member, largest net giver first.

        400 when ``year`` is not a year the report will look at.
        """
        rows = self.rows(self.year(request))
        serializer = ContributionRowSerializer(rows, many=True)  # type: ignore[arg-type]
        return Response(serializer.data)


class AdminPaymentDetailView(APIView):
    """``GET | PATCH /admin/payments/{id}`` -- the full finance row."""

    permission_classes = [IsAuthenticated, IsFinance]

    def payment(self, pk: int) -> Payment:
        """The payment with that id, or 404."""
        return get_object_or_404(reports.base_queryset(), pk=pk)

    @extend_schema(responses={200: FinancePaymentDetailSerializer})
    def get(self, request: Request, pk: int) -> Response:
        """200 with the payment, its refunds and the term it bought.

        404 for an unknown id, 403 without a finance role.
        """
        return Response(FinancePaymentDetailSerializer(self.payment(pk)).data)

    @extend_schema(request=PaymentPatchSerializer, responses={200: FinancePaymentDetailSerializer})
    def patch(self, request: Request, pk: int) -> Response:
        """200 with the payment as it now stands, after reconciling or noting it.

        ``reconciled_on`` is the day it was matched to a statement, or ``null`` to
        un-match it, and setting it records who did so; ``note`` is the
        treasurer's own line.  Each field that really changes writes its own audit
        record.  400 for a body naming neither field, 404 for an unknown id.
        """
        payment = self.payment(pk)
        serializer = PaymentPatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        actor = acting_finance_user(request)
        data = serializer.validated_data

        changed: list[str] = []
        if "reconciled_on" in data and data["reconciled_on"] != payment.reconciled_on:
            payment.reconciled_on = data["reconciled_on"]
            payment.reconciled_by = actor if data["reconciled_on"] is not None else None
            changed += ["reconciled_on", "reconciled_by"]
            audit.record(
                audit.PAYMENT_RECONCILE,
                actor=actor,
                target=payment.user,
                payment=payment.pk,
                reconciled=data["reconciled_on"] is not None,
            )
        if "note" in data and data["note"] != payment.note:
            payment.note = data["note"]
            changed.append("note")
            audit.record(audit.PAYMENT_NOTE, actor=actor, target=payment.user, payment=payment.pk)
        if len(changed) > 0:
            payment.save(update_fields=[*changed, "updated_at"])

        payment.refresh_from_db()
        return Response(FinancePaymentDetailSerializer(payment).data)


class AdminPaymentRecordView(APIView):
    """``POST /admin/payments/record`` -- money taken by check, cash or transfer."""

    permission_classes = [IsAuthenticated, IsFinance]

    @extend_schema(request=ManualPaymentSerializer, responses={201: FinancePaymentDetailSerializer})
    def post(self, request: Request) -> Response:
        """201 with the payment, which is already succeeded and has bought its term.

        The member is emailed the same receipt a card payment earns.  400 keyed
        by the field at fault for an unusable body -- an unknown method, a date
        in the future, a reference another recorded payment carries, an inactive
        plan, or a plan and contribution that come to nothing -- and 404 for an
        unknown member.
        """
        serializer = ManualPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        member = get_object_or_404(User, pk=data["user_id"])
        actor = acting_finance_user(request)

        payment = record_manual_payment(
            user=member,
            plan_slug=data["plan"] or None,
            contribution_cents=data["contribution_cents"],
            method=data["method"],
            reference=data["reference"],
            received_on=data["received_on"],
            note=data["note"],
            actor=actor,
        )
        audit.record(
            audit.PAYMENT_RECORD,
            actor=actor,
            target=member,
            payment=payment.pk,
            method=payment.wallet,
            amount_cents=payment.amount_cents,
        )
        return Response(
            FinancePaymentDetailSerializer(payment).data, status=http_status.HTTP_201_CREATED
        )


class AdminMemberLedgerView(APIView):
    """``GET /admin/payments/ledger/{user_id}`` -- one member's money history."""

    permission_classes = [IsAuthenticated, IsFinance]

    @extend_schema(responses={200: MemberLedgerSerializer})
    def get(self, request: Request, user_id: int) -> Response:
        """200 with the member, their totals, every payment, the mandate and the years.

        The payments are newest money first, the totals cover their whole history,
        ``mandate`` is ``null`` when the member has no standing renewal authority,
        and ``statement_years`` names the years they can download a contribution
        statement for.  404 for an unknown member.
        """
        member = get_object_or_404(User, pk=user_id)
        payments = list(
            reports.base_queryset().filter(user=member).order_by("-paid_at", "-id")  # type: ignore[misc]
        )
        body: dict[str, Any] = {
            "user": {
                "id": member.pk,
                "name": member.display_name,
                "email": member.email,
                "membership": membership_status(member),
            },
            "totals": ledger_totals(payments),
            "payments": payments,
            "mandate": mandate_of(member),
            "statement_years": statement_years(payments),
        }
        return Response(MemberLedgerSerializer(body).data)


def ledger_totals(payments: list[Payment]) -> dict[str, int]:
    """What a member has paid, given and been charged in fees, over every payment.

    Only money that arrived counts, so a pending or failed attempt adds nothing.
    """
    received = [p for p in payments if p.status in reports.RECEIVED_STATUSES]
    return {
        "paid_cents": sum(p.amount_cents for p in received),
        "contribution_cents": sum(p.contribution_cents for p in received),
        "fee_cents": sum(p.fee_cents for p in received),
        "refunded_cents": sum(p.refunded_cents for p in received),
    }


def statement_years(payments: list[Payment]) -> list[int]:
    """The years the member can download a contribution statement for, newest first.

    A year qualifies when at least one payment carrying a contribution arrived in
    it, dated the same way the ledger dates every payment.
    """
    years = {
        payment.paid_on.year
        for payment in payments
        if payment.paid_on is not None
        and payment.contribution_cents > 0
        and payment.status in reports.RECEIVED_STATUSES
    }
    return sorted(years, reverse=True)


def mandate_of(member: User) -> RenewalMandate | None:
    """The member's renewal mandate, or ``None`` when they have no standing authority."""
    return RenewalMandate.objects.filter(user=member).select_related("plan").first()


class AdminPaymentFeesView(APIView):
    """``POST /admin/payments/{id}/fees`` -- ask the provider what a payment cost."""

    permission_classes = [IsAuthenticated, IsFinance]

    @extend_schema(request=None, responses={200: FinancePaymentDetailSerializer})
    def post(self, request: Request, pk: int) -> Response:
        """200 with the payment as it now stands, its fee and net filled in.

        A provider settles asynchronously, so a payment can arrive before anybody
        knows what it cost; this asks again and records the answer.  400 carrying
        ``detail`` when the provider still has nothing to report -- a payment
        recorded by hand, one that never succeeded, a charge the provider has not
        settled -- or when it cannot be reached.  404 for an unknown id, 403
        without a finance role.
        """
        payment = get_object_or_404(Payment, pk=pk)
        if payment.provider == PaymentProvider.MANUAL:
            raise ValidationError({"detail": FEES_UNAVAILABLE})
        try:
            payment = backfill_fees(payment)
        except PaymentError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        if not fees_are_known(payment):
            raise ValidationError({"detail": FEES_UNAVAILABLE})
        return Response(FinancePaymentDetailSerializer(self.row(pk)).data)

    def row(self, pk: int) -> Payment:
        """The payment read back through the finance queryset, ready to serialize."""
        return get_object_or_404(reports.base_queryset(), pk=pk)


class AdminFinanceMemberSearchView(APIView):
    """``GET /admin/payments/members?search=`` -- who a payment can be recorded for."""

    permission_classes = [IsAuthenticated, IsFinance]

    @extend_schema(responses={200: FinanceMemberSerializer(many=True)})
    def get(self, request: Request) -> Response:
        """200 with the members whose name or address carries the term, by name.

        At most :data:`MEMBER_SEARCH_LIMIT` rows come back, so a short term does
        not answer with the whole register, and a blank ``search`` answers none at
        all.  403 without a finance role.
        """
        query = MemberSearchQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        term = query.validated_data["search"].strip()
        rows = [
            {
                "user_id": member.pk,
                "name": member.display_name,
                "email": member.email,
                "membership": membership_status(member),
            }
            for member in search_members(term)
        ]
        serializer = FinanceMemberSerializer(rows, many=True)  # type: ignore[arg-type]
        return Response(serializer.data)


def search_members(term: str) -> list[User]:
    """The members whose name or address carries ``term``, by name, capped.

    The term is matched against the full name as well as each half of it, so a
    treasurer holding a check made out to "Marta Reyes" can type what is written
    on it.  An empty term matches nobody: the search is a form control, and a
    form nobody has typed in asks for no members rather than for all of them.
    """
    if term == "":
        return []
    matches = User.objects.annotate(
        full_name=Concat(F("first_name"), Value(" "), F("last_name"), output_field=CharField())
    ).filter(
        Q(full_name__icontains=term)
        | Q(first_name__icontains=term)
        | Q(last_name__icontains=term)
        | Q(email__icontains=term)
    )
    return list(matches.order_by("last_name", "first_name", "pk")[:MEMBER_SEARCH_LIMIT])
