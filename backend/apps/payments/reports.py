"""Payment reporting: filters, the period summary, the column registry, exports.

Everything here works off one annotation, ``paid_date`` -- the day the money
counts as received, which is ``received_on`` for a payment recorded by hand and
the local date of ``completed_at`` (or of ``created_at``, for one that never
settled) for every other.  It is :attr:`apps.payments.models.Payment.paid_on`
expressed in SQL, so the date filters, the period summary, the reconciliation
rows, the contributions list and the exported ``Date`` column all answer the
same question: a check received in January is January's money whatever day the
treasurer keyed it in.

A second annotation, ``paid_at``, keeps the moment a payment settled, so
``?ordering=paid_at`` can sort by it and rows within one ledger day have a
stable order.

The exports share one column registry, :data:`PAYMENT_REPORT_COLUMNS`, so the
CSV, the PDF and the chooser the screen draws can never drift apart.  Adding a
column means adding one entry to that tuple.

The query-string serializers the finance list, the summary and the reports read
live here too, so the payments report and the contributions report validate their
params exactly as the screens they belong to do.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any, TypedDict

from django.db.models import Count, DateField, Q, QuerySet, Sum
from django.db.models.functions import Coalesce, TruncDate, TruncMonth, TruncYear
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from apps.accounts.roles import ACCOUNT_ADMIN, TREASURER
from apps.members.models import Membership
from apps.payments.models import (
    Payment,
    PaymentKind,
    PaymentProvider,
    PaymentStatus,
    PaymentWallet,
    Refund,
    RefundStatus,
)
from caldart.reports import (
    Money,
    Params,
    ReportColumn,
    ReportQuery,
    ReportSpec,
    given_params,
    money_label,
    resolve_period,
)

GROUPS = {"month": TruncMonth, "year": TruncYear}
PERIOD_FORMAT = {"month": "%Y-%m", "year": "%Y"}

#: The period :func:`summarize` groups by unless the caller asks for the other.
DEFAULT_GROUP = "month"

#: How the list and the exports sort when ``?ordering=`` names nothing: newest
#: ledger day first, and within a day the payment that settled last.
DEFAULT_ORDERING = ("-paid_date", "-paid_at")

#: The title on every page of the payments PDF export.
REPORT_TITLE = "CalDART payments"

#: The title on every page of the contributions PDF export.
CONTRIBUTION_TITLE = "CalDART contributions"

#: The roles that read the money reports.
FINANCE_ROLES: tuple[str, ...] = (TREASURER, ACCOUNT_ADMIN)

#: The statuses that count as money CalDART received.  A refunded payment is
#: still money that arrived and was then given back, which is why the refunded
#: column exists rather than the row disappearing.
RECEIVED_STATUSES = (
    PaymentStatus.SUCCEEDED,
    PaymentStatus.PARTIALLY_REFUNDED,
    PaymentStatus.REFUNDED,
)

#: Fields ``?ordering=`` accepts, as DRF's OrderingFilter would spell them.
ORDERING_FIELDS = (
    "paid_at",
    "created_at",
    "completed_at",
    "amount_cents",
    "contribution_cents",
    "fee_cents",
    "net_cents",
    "reconciled_on",
    "status",
    "provider",
    "plan__name",
    "user__last_name",
    "user__email",
)


class PeriodSummary(TypedDict):
    """One row of :func:`summarize`: a period's money, and its split by provider."""

    period: str
    count: int
    total_cents: int
    plan_cents: int
    contribution_cents: int
    fee_cents: int
    net_cents: int
    refunded_cents: int
    by_provider: dict[str, int]


class ContributionRow(TypedDict):
    """One row of :func:`contribution_rows`: a member's giving for one year."""

    user_id: int
    name: str
    email: str
    count: int
    contribution_cents: int
    refunded_cents: int
    net_contribution_cents: int


def base_queryset() -> QuerySet[Payment]:
    """Every payment, annotated with ``paid_date`` and ``paid_at`` and joined.

    The refunds, the renewal attempt behind an automatic charge and the term each
    payment bought are fetched with it, so a report over the whole table runs a
    fixed number of queries however many rows it holds.  ``received_on`` is set
    only on a payment recorded by hand, which is what makes it the first choice
    for ``paid_date``.
    """
    return (
        Payment.objects.select_related("user", "plan", "membership")
        .prefetch_related("refunds", "renewal_attempts")
        .annotate(
            paid_at=Coalesce("completed_at", "created_at"),
            paid_date=Coalesce(
                "received_on",
                TruncDate("completed_at"),
                TruncDate("created_at"),
                output_field=DateField(),
            ),
        )
    )


@dataclass(frozen=True)
class PaymentFilters:
    """The narrowing the list, summary, and export endpoints share.

    Each field is already validated: the API layer reads the query string, and an
    empty string or ``None`` means "do not narrow on this".  ``reconciled`` is
    ``"yes"`` for payments a treasurer has matched to a statement, ``"no"`` for
    the ones still waiting, and empty for both.
    """

    date_from: dt.date | None = None
    date_to: dt.date | None = None
    provider: str = ""
    status: str = ""
    search: str = ""
    plan: str = ""
    kind: str = ""
    wallet: str = ""
    reconciled: str = ""
    member: int | None = None
    min_cents: int | None = None
    max_cents: int | None = None


def _kind_filter(kind: str) -> Q:
    """The condition that picks out payments of ``kind``.

    ``kind`` is a :class:`~apps.payments.models.PaymentKind` value, and the
    condition mirrors :attr:`apps.payments.models.Payment.kind`: a contribution
    names no plan, a membership names one and gives nothing beyond it, and both
    does the two at once.
    """
    if kind == PaymentKind.CONTRIBUTION:
        return Q(plan__isnull=True)
    if kind == PaymentKind.MEMBERSHIP:
        return Q(plan__isnull=False, contribution_cents=0)
    return Q(plan__isnull=False, contribution_cents__gt=0)


def apply_filters(queryset: QuerySet[Payment], filters: PaymentFilters) -> QuerySet[Payment]:
    """Narrow ``queryset`` (which must carry ``paid_date``) by ``filters``."""
    # django-stubs resolves field names against the model, so it cannot see the
    # ``paid_date`` annotation :func:`base_queryset` adds.
    if filters.date_from:
        queryset = queryset.filter(paid_date__gte=filters.date_from)  # type: ignore[misc]
    if filters.date_to:
        queryset = queryset.filter(paid_date__lte=filters.date_to)  # type: ignore[misc]
    if filters.provider:
        queryset = queryset.filter(provider=filters.provider)
    if filters.status:
        queryset = queryset.filter(status=filters.status)
    if filters.plan:
        queryset = queryset.filter(plan__slug=filters.plan)
    if filters.kind:
        queryset = queryset.filter(_kind_filter(filters.kind))
    if filters.wallet:
        queryset = queryset.filter(wallet=filters.wallet)
    if filters.reconciled == "yes":
        queryset = queryset.filter(reconciled_on__isnull=False)
    elif filters.reconciled == "no":
        queryset = queryset.filter(reconciled_on__isnull=True)
    if filters.member is not None:
        queryset = queryset.filter(user_id=filters.member)
    if filters.min_cents is not None:
        queryset = queryset.filter(amount_cents__gte=filters.min_cents)
    if filters.max_cents is not None:
        queryset = queryset.filter(amount_cents__lte=filters.max_cents)
    if filters.search:
        term = filters.search
        queryset = queryset.filter(
            Q(user__email__icontains=term)
            | Q(user__first_name__icontains=term)
            | Q(user__last_name__icontains=term)
            | Q(provider_ref__icontains=term)
            | Q(note__icontains=term)
        )
    return queryset


def _refunds_by_period(queryset: QuerySet[Payment], group: str) -> dict[str, int]:
    """Succeeded refund totals per period, keyed by the *payment's* period.

    The summary answers "what did this month bring in, and how much of it went
    back", so a refund is counted against the month the payment arrived in,
    whenever the refund itself was taken.  The reconciliation report, which is
    matched against a bank statement, dates refunds by ``refunded_at`` instead.
    """
    rows = (
        Refund.objects.filter(status=RefundStatus.SUCCEEDED, payment__in=queryset)
        .annotate(
            paid_date=Coalesce(
                "payment__received_on",
                TruncDate("payment__completed_at"),
                TruncDate("payment__created_at"),
                output_field=DateField(),
            ),
        )
        .annotate(period=GROUPS[group]("paid_date"))
        .values("period")
        .annotate(refunded_cents=Sum("amount_cents"))
    )
    totals: dict[str, int] = {}
    for row in rows:
        if row["period"] is None:
            continue
        label = row["period"].strftime(PERIOD_FORMAT[group])
        totals[label] = totals.get(label, 0) + (row["refunded_cents"] or 0)
    return totals


def summarize(queryset: QuerySet[Payment], group: str = DEFAULT_GROUP) -> list[PeriodSummary]:
    """Money received per period, oldest first.

    ``group`` is a key of :data:`GROUPS`, which the API layer has already checked.
    Only money that arrived counts: a pending or failed attempt never became
    revenue, while a payment since refunded did and is reported with what went
    back.  ``fee_cents`` and ``net_cents`` are what the provider reported,
    ``refunded_cents`` the succeeded refunds against those payments, and
    ``by_provider`` breaks the period's gross down by provider, omitting
    providers with nothing in that period.
    """
    received = queryset.filter(status__in=RECEIVED_STATUSES)
    rows = (
        received.annotate(period=GROUPS[group]("paid_date"))
        .values("period", "provider")
        .annotate(
            count=Count("id"),
            total_cents=Sum("amount_cents"),
            plan_cents=Sum("plan_amount_cents"),
            contribution_cents=Sum("contribution_cents"),
            fee_cents=Sum("fee_cents"),
            net_cents=Sum("net_cents"),
        )
        .order_by("period", "provider")
    )

    periods: dict[str, PeriodSummary] = {}
    for row in rows:
        if row["period"] is None:
            continue
        label = row["period"].strftime(PERIOD_FORMAT[group])
        bucket = periods.setdefault(
            label,
            {
                "period": label,
                "count": 0,
                "total_cents": 0,
                "plan_cents": 0,
                "contribution_cents": 0,
                "fee_cents": 0,
                "net_cents": 0,
                "refunded_cents": 0,
                "by_provider": {},
            },
        )
        bucket["count"] += row["count"]
        bucket["total_cents"] += row["total_cents"] or 0
        bucket["plan_cents"] += row["plan_cents"] or 0
        bucket["contribution_cents"] += row["contribution_cents"] or 0
        bucket["fee_cents"] += row["fee_cents"] or 0
        bucket["net_cents"] += row["net_cents"] or 0
        provider = row["provider"]
        bucket["by_provider"][provider] = bucket["by_provider"].get(provider, 0) + (
            row["total_cents"] or 0
        )

    refunded = _refunds_by_period(received, group)
    for label, bucket in periods.items():
        bucket["refunded_cents"] = refunded.get(label, 0)

    return [periods[key] for key in sorted(periods)]


def contribution_rows(year: int) -> list[ContributionRow]:
    """One row per member who gave something in ``year``, largest giver first.

    A member appears when they made at least one payment carrying a contribution
    whose ledger date falls in ``year``, the same dating the filters and the
    period summary use, so a check counts in the year it was received.  ``count``
    is how many such payments they made, ``refunded_cents`` what was given back
    against them -- whenever the refund itself was taken -- and
    ``net_contribution_cents`` the difference, which is the figure the year-end
    acknowledgment quotes.  Ties on the net amount break on the member's name, so
    the order is stable.
    """
    payments = (
        base_queryset()
        .filter(  # type: ignore[misc]
            paid_date__year=year, status__in=RECEIVED_STATUSES, contribution_cents__gt=0
        )
        .order_by()
    )
    rows: dict[int, ContributionRow] = {}
    for payment in payments:
        row = rows.setdefault(
            payment.user_id,
            {
                "user_id": payment.user_id,
                "name": display_name(payment),
                "email": payment.user.email,
                "count": 0,
                "contribution_cents": 0,
                "refunded_cents": 0,
                "net_contribution_cents": 0,
            },
        )
        row["count"] += 1
        row["contribution_cents"] += payment.contribution_cents
        row["refunded_cents"] += min(payment.refunded_cents, payment.contribution_cents)

    for row in rows.values():
        row["net_contribution_cents"] = row["contribution_cents"] - row["refunded_cents"]
    return sorted(rows.values(), key=lambda row: (-row["net_contribution_cents"], row["name"]))


def display_name(payment: Payment) -> str:
    """The payer's full name, or their email address when they have no name."""
    full = f"{payment.user.first_name} {payment.user.last_name}".strip()
    return full or payment.user.email


def term_of(payment: Payment) -> Membership | None:
    """The membership term ``payment`` bought, or ``None`` when it bought none.

    A payment carries at most one term, through ``Membership.payment``.  A pure
    contribution, a failed attempt and a term that has since been detached all
    report ``None``.
    """
    # A reverse one-to-one raises rather than answering None when there is no
    # related row, which is Django's way of saying "not set".
    try:
        return payment.membership
    except Membership.DoesNotExist:
        return None


def _iso(value: dt.date | None) -> str:
    """The date as ``YYYY-MM-DD``, or a blank cell when there is none."""
    return value.isoformat() if value else ""


def _term_start(payment: Payment) -> str:
    term = term_of(payment)
    return _iso(term.starts_on) if term is not None else ""


def _term_end(payment: Payment) -> str:
    term = term_of(payment)
    return _iso(term.ends_on) if term is not None else ""


def _money(cents: int) -> str:
    """Integer cents as a plain two-decimal number, which a spreadsheet adds up."""
    return money_label(cents, currency=False)


#: Every column the payment exports can carry, in export order.  ``key`` is what
#: ``?columns=`` names and what ``GET /reports/payments/columns`` answers with,
#: ``label`` is the header both exports print, and ``default`` says whether the
#: column appears when the caller chooses none.  The five that are off by default
#: -- the receipt number, the date a check was received, the treasurer's note and
#: the term's two dates -- are there for a reconciliation or an audit rather than
#: for the everyday list.
PAYMENT_REPORT_COLUMNS: tuple[ReportColumn[Payment], ...] = (
    ReportColumn("paid_on", "Date", True, lambda p: _iso(p.paid_on)),
    ReportColumn("receipt_number", "Receipt", False, lambda p: p.receipt_number),
    ReportColumn("name", "Name", True, display_name),
    ReportColumn("email", "Email", True, lambda p: p.user.email),
    ReportColumn("plan", "Plan", True, lambda p: p.plan.name if p.plan is not None else ""),
    ReportColumn("kind", "Kind", True, lambda p: p.kind),
    ReportColumn("plan_amount", "Dues", True, lambda p: _money(p.plan_amount_cents)),
    ReportColumn("contribution", "Contribution", True, lambda p: _money(p.contribution_cents)),
    ReportColumn("total", "Total", True, lambda p: _money(p.amount_cents)),
    ReportColumn("fee", "Fee", True, lambda p: _money(p.fee_cents)),
    ReportColumn("net", "Net", True, lambda p: _money(p.net_cents)),
    ReportColumn("refunded", "Refunded", True, lambda p: _money(p.refunded_cents)),
    ReportColumn("provider", "Provider", True, lambda p: p.provider),
    ReportColumn("wallet", "Method", True, lambda p: p.wallet),
    ReportColumn("status", "Status", True, lambda p: p.status),
    ReportColumn("provider_ref", "Reference", True, lambda p: p.provider_ref),
    ReportColumn("received_on", "Received", False, lambda p: _iso(p.received_on)),
    ReportColumn("reconciled_on", "Reconciled", True, lambda p: _iso(p.reconciled_on)),
    ReportColumn("note", "Note", False, lambda p: p.note),
    ReportColumn("membership_starts", "Term starts", False, _term_start),
    ReportColumn("membership_ends", "Term ends", False, _term_end),
)


#: What a report date parameter answers with when it is not a date on the calendar.
DATE_FORMAT_MESSAGE = "Expected a date as YYYY-MM-DD."
GROUP_MESSAGE = "Expected 'month' or 'year'."

#: What ``?reconciled=`` answers with when it is neither of the two words.
RECONCILED_MESSAGE = "Expected 'yes' or 'no'."


#: The earliest year the contributions report will look at: CalDART's founding
#: is long after it, so anything earlier is a typo rather than a query.
FIRST_REPORTABLE_YEAR = 1900


class ReportDateField(serializers.DateField):
    """One end of a report's date range, where an empty parameter is no bound at all.

    The report screen sends every parameter on every request, so ``?from=`` has to
    mean the same as leaving ``from`` out.  Anything else that is not a date the
    calendar has -- ``2026-02-30`` as much as ``last tuesday`` -- is a 400 naming
    this parameter.
    """

    def __init__(self, **kwargs: Any) -> None:
        """Build the field, defaulting to optional, unbounded, and our own message."""
        kwargs.setdefault("required", False)
        kwargs.setdefault("default", None)
        kwargs.setdefault("error_messages", {"invalid": DATE_FORMAT_MESSAGE})
        super().__init__(**kwargs)

    # DRF's DateField promises a date, and answering an empty parameter with
    # ``None`` is the whole point of this field.
    def to_internal_value(self, value: dt.date | str) -> dt.date | None:  # type: ignore[override]
        """``None`` for an empty parameter, otherwise the date the string names.

        Raises DRF's ``ValidationError`` with :data:`DATE_FORMAT_MESSAGE` for
        anything else.
        """
        if value == "":
            return None
        return super().to_internal_value(value)


class PaymentReportQuerySerializer(serializers.Serializer[dict[str, Any]]):
    """The query string the finance list, summary and exports share.

    Every parameter is optional and an empty one narrows nothing.  ``from`` and
    ``to`` bound the date the money arrived; ``provider``, ``status``, ``wallet``
    and ``kind`` must each name one of the payment choices; ``plan`` is a plan
    slug; ``member`` is a member's id; ``reconciled`` is ``yes`` or ``no``;
    ``min_cents`` and ``max_cents`` bound the total; ``search`` matches a name, an
    email address, a provider reference or a treasurer's note; ``group`` is the
    summary's period, ``month`` or ``year``.  Every endpoint therefore refuses the
    same input the same way, with the complaint keyed by the parameter it came from.
    """

    provider = serializers.CharField(required=False, allow_blank=True, default="")
    status = serializers.CharField(required=False, allow_blank=True, default="")
    search = serializers.CharField(required=False, allow_blank=True, default="")
    group = serializers.CharField(required=False, allow_blank=True, default=DEFAULT_GROUP)
    plan = serializers.CharField(required=False, allow_blank=True, default="")
    kind = serializers.CharField(required=False, allow_blank=True, default="")
    wallet = serializers.CharField(required=False, allow_blank=True, default="")
    reconciled = serializers.CharField(required=False, allow_blank=True, default="")
    member = serializers.IntegerField(required=False, allow_null=True, default=None)
    min_cents = serializers.IntegerField(required=False, allow_null=True, min_value=0, default=None)
    max_cents = serializers.IntegerField(required=False, allow_null=True, min_value=0, default=None)

    def get_fields(self) -> dict[str, serializers.Field[Any, Any, Any, Any]]:
        """The declared fields plus the date bounds, whose names are Python keywords."""
        fields = super().get_fields()
        fields["from"] = ReportDateField()
        fields["to"] = ReportDateField()
        return fields

    def validate_provider(self, value: str) -> str:
        """Return ``value``, or raise ``Unknown provider '<value>'.`` for an unknown one.

        An empty string is accepted and narrows nothing.
        """
        if value and value not in PaymentProvider.values:
            raise serializers.ValidationError(f"Unknown provider '{value}'.")
        return value

    def validate_status(self, value: str) -> str:
        """Return ``value``, or raise ``Unknown status '<value>'.`` for an unknown one.

        An empty string is accepted and narrows nothing.
        """
        if value and value not in PaymentStatus.values:
            raise serializers.ValidationError(f"Unknown status '{value}'.")
        return value

    def validate_wallet(self, value: str) -> str:
        """Return ``value``, or raise ``Unknown wallet '<value>'.`` for an unknown one.

        An empty string is accepted and narrows nothing.
        """
        if value and value not in PaymentWallet.values:
            raise serializers.ValidationError(f"Unknown wallet '{value}'.")
        return value

    def validate_kind(self, value: str) -> str:
        """Return ``value``, or raise ``Unknown kind '<value>'.`` for an unknown one.

        An empty string is accepted and narrows nothing.
        """
        if value and value not in PaymentKind.values:
            raise serializers.ValidationError(f"Unknown kind '{value}'.")
        return value

    def validate_reconciled(self, value: str) -> str:
        """Return ``value``, or raise :data:`RECONCILED_MESSAGE` for anything else.

        An empty string is accepted and narrows nothing.
        """
        if value and value not in {"yes", "no"}:
            raise serializers.ValidationError(RECONCILED_MESSAGE)
        return value

    def validate_group(self, value: str) -> str:
        """Return the period to group by, defaulting an empty parameter to ``month``.

        Raises DRF's ``ValidationError`` with :data:`GROUP_MESSAGE` for anything
        but ``month`` or ``year``.
        """
        group = value or DEFAULT_GROUP
        if group not in GROUPS:
            raise serializers.ValidationError(GROUP_MESSAGE)
        return group

    def to_filters(self) -> PaymentFilters:
        """The validated parameters as the narrowing the report functions take.

        Call it after ``is_valid``.  The summary reads its period from
        ``validated_data["group"]``, which no filter uses.
        """
        data = self.validated_data
        return PaymentFilters(
            date_from=data["from"],
            date_to=data["to"],
            provider=data["provider"],
            status=data["status"],
            search=data["search"],
            plan=data["plan"],
            kind=data["kind"],
            wallet=data["wallet"],
            reconciled=data["reconciled"],
            member=data["member"],
            min_cents=data["min_cents"],
            max_cents=data["max_cents"],
        )


class ContributionQuerySerializer(serializers.Serializer[dict[str, Any]]):
    """``?year=`` for the contributions list and its exports.

    The parameter is optional; leaving it out reports the current calendar year.
    A year outside :data:`FIRST_REPORTABLE_YEAR` to nine thousand is a 400.
    """

    year = serializers.IntegerField(
        required=False, min_value=FIRST_REPORTABLE_YEAR, max_value=9_000, default=None
    )

    def chosen_year(self) -> int:
        """The year to report on, which is this year when the caller named none."""
        year = self.validated_data["year"]
        return year if year is not None else timezone.localdate().year


def requested_ordering(ordering: str) -> list[str]:
    """The ``order_by`` arguments an ``?ordering=`` value asks for.

    Newest money first when the value is blank -- by the ledger date, then by the
    moment the payment settled -- and a single leading ``-`` reverses.  The id breaks
    ties, so paging is stable.  Raises DRF's ``ValidationError`` keyed by ``ordering``,
    saying ``Cannot order by '<field>'.``, for a field outside :data:`ORDERING_FIELDS`.
    """
    requested = ordering.strip()
    # One leading "-" is the reversal Django understands; anything else -- a
    # doubled prefix, a bare "-" -- is a field name the queryset cannot resolve,
    # so it is refused here rather than raising ``FieldError`` from ``order_by``.
    field = requested[1:] if requested.startswith("-") else requested
    if requested and field not in ORDERING_FIELDS:
        raise ValidationError({"ordering": f"Cannot order by '{field}'."})
    if not requested:
        return [*DEFAULT_ORDERING, "-id"]
    return [requested, "-id"]


def validated_query(params: Params) -> PaymentReportQuerySerializer:
    """``params`` checked by :class:`PaymentReportQuerySerializer`.

    A blank param is left out first, so it narrows nothing whether ``params`` is a
    query string or a stored mapping.  Raises DRF's ``ValidationError`` -- a 400 keyed
    by the parameter at fault -- for anything the finance endpoints will not act on.
    """
    query = PaymentReportQuerySerializer(data=given_params(params))
    query.is_valid(raise_exception=True)
    return query


def filtered_payments(params: Params) -> QuerySet[Payment]:
    """The payments ``params`` ask for, in the order they ask for.

    The finance list and the payments report both read this, so the two can never
    disagree about which payments a filter picks or how they are ordered.
    """
    queryset = apply_filters(base_queryset(), validated_query(params).to_filters())
    return queryset.order_by(*requested_ordering(params.get("ordering", "")))


#: The query parameters the payments report names in its PDF subtitle, in order.
EXPORT_FILTER_PARAMS: tuple[str, ...] = (
    "from",
    "to",
    "provider",
    "status",
    "search",
    "plan",
    "kind",
    "wallet",
    "reconciled",
    "member",
    "min_cents",
    "max_cents",
    "ordering",
)


def payment_report_query(params: Params) -> ReportQuery[Payment]:
    """The payments the finance list shows for ``params``, in its order, every status.

    The rows are read a chunk at a time; the applied filters are those of
    :data:`EXPORT_FILTER_PARAMS` given a value.
    """
    return ReportQuery(
        rows=filtered_payments(params).iterator(chunk_size=200),
        filters=given_params(params, EXPORT_FILTER_PARAMS),
    )


def payment_period(params: Params, today: dt.date) -> Params:
    """``params`` with ``period`` replaced by the ``from`` and ``to`` it spans."""
    return resolve_period(
        params, today, lambda start, end: {"from": start.isoformat(), "to": end.isoformat()}
    )


#: The payment list, for the finance roles: every filter the list takes, and
#: ``period`` for the month or year a download or a subscription means.
PAYMENT_REPORT: ReportSpec[Payment] = ReportSpec(
    slug="payments",
    title=REPORT_TITLE,
    filename_stem="caldart-payments",
    columns=PAYMENT_REPORT_COLUMNS,
    roles=FINANCE_ROLES,
    query=payment_report_query,
    resolve=payment_period,
)


#: The contributions table's columns, fixed, in order: who gave, how many payments,
#: what they gave, what went back, and the difference.
CONTRIBUTION_COLUMNS: tuple[ReportColumn[ContributionRow], ...] = (
    ReportColumn("name", "Name", True, lambda row: row["name"], width=2.4),
    ReportColumn("email", "Email", True, lambda row: row["email"], width=3.0),
    ReportColumn("payments", "Payments", True, lambda row: row["count"], width=1.0),
    ReportColumn(
        "contributed", "Contributed", True, lambda row: Money(row["contribution_cents"]), width=1.6
    ),
    ReportColumn("refunded", "Refunded", True, lambda row: Money(row["refunded_cents"]), width=1.4),
    ReportColumn("net", "Net", True, lambda row: Money(row["net_contribution_cents"]), width=1.8),
)


def contribution_report_query(params: Params) -> ReportQuery[ContributionRow]:
    """One row per member who gave in the ``year`` ``params`` names, or this year.

    The year is refused as the contributions list refuses it, and is always named in
    the applied filters, since the report's title does not carry it.
    """
    query = ContributionQuerySerializer(data=given_params(params))
    query.is_valid(raise_exception=True)
    year = query.chosen_year()
    return ReportQuery(rows=contribution_rows(year), filters={"year": str(year)})


def contribution_year(params: Params, today: dt.date) -> Params:
    """``params`` with ``period`` replaced by the ``year`` it falls in."""
    return resolve_period(params, today, lambda start, end: {"year": str(start.year)})


#: The year-end contributions list, for the finance roles: fixed columns, upright.
CONTRIBUTION_REPORT: ReportSpec[ContributionRow] = ReportSpec(
    slug="contributions",
    title=CONTRIBUTION_TITLE,
    filename_stem="caldart-contributions",
    columns=CONTRIBUTION_COLUMNS,
    roles=FINANCE_ROLES,
    query=contribution_report_query,
    landscape=False,
    choosable=False,
    resolve=contribution_year,
)
