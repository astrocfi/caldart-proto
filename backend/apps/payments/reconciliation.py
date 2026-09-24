"""Reconciling CalDART's records against a bank or provider statement.

A treasurer picks a date range and asks what the books say arrived in it, in
periods or by provider, and how much of it they have already matched to a
statement line.  The rows here answer that question and nothing else: the
payment list answers "which payments", and this answers "how much, and how much
is still unmatched".

Two dating rules make the rows add up against a statement.  A payment is dated
by ``paid_at`` -- when the money arrived.  A refund is dated by ``refunded_at``
-- when the money went back -- which is not always the same period, so a refund
of a January payment taken in February belongs to February here.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Mapping
from typing import Any, TypedDict

from django.db.models import Count, Q, QuerySet, Sum

from apps.payments.models import Payment, PaymentProvider, Refund, RefundStatus
from apps.payments.reports import (
    GROUPS,
    PERIOD_FORMAT,
    RECEIVED_STATUSES,
    base_queryset,
)

#: How the rows may be grouped.  ``month`` and ``year`` are the periods
#: :data:`apps.payments.reports.GROUPS` defines; ``provider`` puts every period
#: together and splits by who took the money instead.
BY_PROVIDER = "provider"
RECONCILIATION_GROUPS = (*GROUPS, BY_PROVIDER)

#: The default grouping, which is the one a bank statement is organized by.
DEFAULT_GROUP = "month"

#: The title on every page of the reconciliation PDF.
REPORT_TITLE = "CalDART reconciliation"

#: The header both reconciliation exports print, in column order.
RECONCILIATION_HEADER = (
    "Period",
    "Payments",
    "Gross",
    "Fees",
    "Net",
    "Refunded",
    "Net after refunds",
    "Reconciled",
    "Unreconciled",
)


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
        queryset = queryset.filter(paid_at__date__gte=date_from)  # type: ignore[misc]
    if date_to:
        queryset = queryset.filter(paid_at__date__lte=date_to)  # type: ignore[misc]
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
        payments.annotate(period=GROUPS[group]("paid_at")).values("period").annotate(**_AGGREGATES)
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


def reconciliation_filename(
    extension: str,
    *,
    date_from: dt.date | None,
    date_to: dt.date | None,
) -> str:
    """The download name, which carries the range so two exports never collide.

    An open end of the range is spelled ``all``, so a reconciliation of
    everything downloads as ``caldart-reconciliation-all-all.csv``.
    """
    start = date_from.isoformat() if date_from else "all"
    end = date_to.isoformat() if date_to else "all"
    return f"caldart-reconciliation-{start}-{end}.{extension}"
