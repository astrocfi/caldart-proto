"""Reconciling CalDART's records against a bank or provider statement.

A treasurer picks a date range and asks what the books say arrived in it, in
periods or by provider, and how much of it they have already matched to a
statement line.  The rows here answer that question and nothing else: the
payment list answers "which payments", and this answers "how much, and how much
is still unmatched".

Two dating rules make the rows add up against a statement.  A payment is dated
by ``paid_date`` -- the day the money arrived, which for a check is the day it
was received rather than the day it was keyed in.  A refund is dated by
``refunded_at`` -- when the money went back -- which is not always the same
period, so a refund of a January payment taken in February belongs to February
here.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from typing import Any, TypedDict

from django.db.models import Count, Q, QuerySet, Sum
from rest_framework import serializers

from apps.payments.models import Payment, PaymentProvider, Refund, RefundStatus
from apps.payments.reports import (
    FINANCE_ROLES,
    GROUPS,
    PERIOD_FORMAT,
    RECEIVED_STATUSES,
    ReportDateField,
    base_queryset,
)
from caldart.reports import Money, Params, ReportColumn, ReportQuery, ReportSpec, given_params

#: How the rows may be grouped.  ``month`` and ``year`` are the periods
#: :data:`apps.payments.reports.GROUPS` defines; ``provider`` puts every period
#: together and splits by who took the money instead.
BY_PROVIDER = "provider"
RECONCILIATION_GROUPS = (*GROUPS, BY_PROVIDER)

#: The default grouping, which is the one a bank statement is organized by.
DEFAULT_GROUP = "month"

#: The title on every page of the reconciliation PDF.
REPORT_TITLE = "CalDART reconciliation"

#: What the reconciliation's ``?group=`` answers with for an unknown grouping.
RECONCILIATION_GROUP_MESSAGE = "Expected 'month', 'year' or 'provider'."


class ReconciliationRow(TypedDict):
    """One period (or one provider): what arrived, what went back, what is matched."""

    period: str
    count: int
    gross_cents: int
    fee_cents: int
    net_cents: int
    refunded_cents: int
    net_after_refunds_cents: int
    reconciled_count: int
    unreconciled_count: int


def _empty_row(period: str) -> ReconciliationRow:
    """A row for ``period`` with every figure at zero."""
    return {
        "period": period,
        "count": 0,
        "gross_cents": 0,
        "fee_cents": 0,
        "net_cents": 0,
        "refunded_cents": 0,
        "net_after_refunds_cents": 0,
        "reconciled_count": 0,
        "unreconciled_count": 0,
    }


def received_payments(
    *,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    provider: str = "",
) -> QuerySet[Payment]:
    """The payments a reconciliation counts: money that arrived in the range.

    Succeeded, partially refunded and refunded payments all count -- each one is
    a line on the statement -- while a pending or failed attempt never reached
    the bank.  An empty ``provider`` counts every provider.
    """
    queryset = base_queryset().filter(status__in=RECEIVED_STATUSES)
    if date_from:
        queryset = queryset.filter(paid_date__gte=date_from)  # type: ignore[misc]
    if date_to:
        queryset = queryset.filter(paid_date__lte=date_to)  # type: ignore[misc]
    if provider:
        queryset = queryset.filter(provider=provider)
    return queryset


#: The aggregates every reconciliation row is built from, whichever way the rows
#: are keyed.  ``reconciled_count`` counts the payments a treasurer has matched.
_AGGREGATES = {
    "count": Count("id"),
    "gross_cents": Sum("amount_cents"),
    "fee_cents": Sum("fee_cents"),
    "net_cents": Sum("net_cents"),
    "reconciled_count": Count("id", filter=Q(reconciled_on__isnull=False)),
}


def _bucket(period: str, row: Mapping[str, Any]) -> ReconciliationRow:
    """One aggregate row as a reconciliation row, refunds still to come."""
    bucket = _empty_row(period)
    bucket["count"] = row["count"]
    bucket["gross_cents"] = row["gross_cents"] or 0
    bucket["fee_cents"] = row["fee_cents"] or 0
    bucket["net_cents"] = row["net_cents"] or 0
    bucket["reconciled_count"] = row["reconciled_count"]
    bucket["unreconciled_count"] = row["count"] - row["reconciled_count"]
    return bucket


def _payment_buckets(payments: QuerySet[Payment], group: str) -> dict[str, ReconciliationRow]:
    """The payment half of every row, keyed by period or by provider."""
    if group == BY_PROVIDER:
        by_provider = payments.values("provider").annotate(**_AGGREGATES)
        return {row["provider"]: _bucket(row["provider"], row) for row in by_provider}

    by_period = (
        payments.annotate(period=GROUPS[group]("paid_date"))
        .values("period")
        .annotate(**_AGGREGATES)
    )
    return {
        row["period"].strftime(PERIOD_FORMAT[group]): _bucket(
            row["period"].strftime(PERIOD_FORMAT[group]), row
        )
        for row in by_period
        if row["period"] is not None
    }


def _refund_buckets(
    group: str,
    *,
    date_from: dt.date | None,
    date_to: dt.date | None,
    provider: str,
) -> dict[str, int]:
    """Succeeded refund totals in the range, keyed the way ``group`` keys rows."""
    refunds = Refund.objects.filter(status=RefundStatus.SUCCEEDED, refunded_at__isnull=False)
    if date_from:
        refunds = refunds.filter(refunded_at__date__gte=date_from)
    if date_to:
        refunds = refunds.filter(refunded_at__date__lte=date_to)
    if provider:
        refunds = refunds.filter(payment__provider=provider)

    if group == BY_PROVIDER:
        by_provider = refunds.values("payment__provider").annotate(
            refunded_cents=Sum("amount_cents")
        )
        return {row["payment__provider"]: row["refunded_cents"] or 0 for row in by_provider}

    rows = (
        refunds.annotate(period=GROUPS[group]("refunded_at"))
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


def reconciliation_rows(
    *,
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    provider: str = "",
    group: str = DEFAULT_GROUP,
) -> list[ReconciliationRow]:
    """The reconciliation table, oldest period first.

    ``group`` is one of :data:`RECONCILIATION_GROUPS`, which the API layer has
    already checked: ``month`` and ``year`` answer one row per period, ordered by
    the period, and ``provider`` one row per provider that took money, ordered by
    the provider's name.

    A period in which money only went back -- a refund taken in a month with no
    payments at all -- still gets a row, with a zero count and the refund in it,
    because the statement has that line too.  ``net_after_refunds_cents`` is
    ``net_cents`` less ``refunded_cents`` and can therefore be negative.
    """
    payments = received_payments(date_from=date_from, date_to=date_to, provider=provider)
    buckets = _payment_buckets(payments, group)
    for period, refunded in _refund_buckets(
        group, date_from=date_from, date_to=date_to, provider=provider
    ).items():
        bucket = buckets.setdefault(period, _empty_row(period))
        bucket["refunded_cents"] = refunded
    for bucket in buckets.values():
        bucket["net_after_refunds_cents"] = bucket["net_cents"] - bucket["refunded_cents"]

    if group == BY_PROVIDER:
        order = {provider_slug: index for index, provider_slug in enumerate(PaymentProvider.values)}
        return sorted(buckets.values(), key=lambda row: order.get(row["period"], len(order)))
    return [buckets[key] for key in sorted(buckets)]


class ReconciliationQuerySerializer(serializers.Serializer[dict[str, Any]]):
    """The query string the reconciliation table and its exports share.

    ``from`` and ``to`` bound the range, ``provider`` narrows to one provider, and
    ``group`` is ``month``, ``year`` or ``provider``.  Every parameter is optional
    and an empty one narrows nothing.
    """

    provider = serializers.CharField(required=False, allow_blank=True, default="")
    group = serializers.CharField(required=False, allow_blank=True, default=DEFAULT_GROUP)

    def get_fields(self) -> dict[str, serializers.Field[Any, Any, Any, Any]]:
        """The declared fields plus the date bounds, whose names are Python keywords."""
        fields = super().get_fields()
        fields["from"] = ReportDateField()
        fields["to"] = ReportDateField()
        return fields

    def validate_provider(self, value: str) -> str:
        """Return ``value``, or refuse a provider that is not one of the choices.

        The message is ``Unknown provider '<value>'.``; an empty string is
        accepted and narrows nothing.
        """
        if value and value not in PaymentProvider.values:
            raise serializers.ValidationError(f"Unknown provider '{value}'.")
        return value

    def validate_group(self, value: str) -> str:
        """Return the grouping, defaulting an empty parameter to ``month``.

        Raises DRF's ``ValidationError`` with :data:`RECONCILIATION_GROUP_MESSAGE`
        for anything but ``month``, ``year`` or ``provider``.
        """
        group = value or DEFAULT_GROUP
        if group not in RECONCILIATION_GROUPS:
            raise serializers.ValidationError(RECONCILIATION_GROUP_MESSAGE)
        return group


#: The reconciliation table's columns, fixed, in order.  The period label is wider
#: than a figure, and every figure is about as wide as the next.
RECONCILIATION_COLUMNS: tuple[ReportColumn[ReconciliationRow], ...] = (
    ReportColumn("period", "Period", True, lambda row: row["period"], width=2.0),
    ReportColumn("payments", "Payments", True, lambda row: row["count"], width=1.0),
    ReportColumn("gross", "Gross", True, lambda row: Money(row["gross_cents"]), width=1.4),
    ReportColumn("fees", "Fees", True, lambda row: Money(row["fee_cents"]), width=1.2),
    ReportColumn("net", "Net", True, lambda row: Money(row["net_cents"]), width=1.4),
    ReportColumn("refunded", "Refunded", True, lambda row: Money(row["refunded_cents"]), width=1.4),
    ReportColumn(
        "net_after_refunds",
        "Net after refunds",
        True,
        lambda row: Money(row["net_after_refunds_cents"]),
        width=1.6,
    ),
    ReportColumn("reconciled", "Reconciled", True, lambda row: row["reconciled_count"], width=1.2),
    ReportColumn(
        "unreconciled", "Unreconciled", True, lambda row: row["unreconciled_count"], width=1.3
    ),
)

#: The query parameters the reconciliation report names in its PDF subtitle, in order.
EXPORT_FILTER_PARAMS: tuple[str, ...] = ("from", "to", "provider", "group")


def reconciliation_report_query(params: Params) -> ReportQuery[ReconciliationRow]:
    """The rows the reconciliation table answers for ``params``.

    The range, provider and grouping are refused as the table refuses them; the
    applied filters are those of :data:`EXPORT_FILTER_PARAMS` given a value.
    """
    query = ReconciliationQuerySerializer(data=given_params(params))
    query.is_valid(raise_exception=True)
    data = query.validated_data
    rows = reconciliation_rows(
        date_from=data["from"], date_to=data["to"], provider=data["provider"], group=data["group"]
    )
    return ReportQuery(
        rows=rows,
        filters=given_params(params, EXPORT_FILTER_PARAMS),
    )


#: The reconciliation table, for the finance roles: fixed columns, upright.
RECONCILIATION_REPORT: ReportSpec[ReconciliationRow] = ReportSpec(
    slug="reconciliation",
    title=REPORT_TITLE,
    filename_stem="caldart-reconciliation",
    columns=RECONCILIATION_COLUMNS,
    roles=FINANCE_ROLES,
    query=reconciliation_report_query,
    landscape=False,
    choosable=False,
)
