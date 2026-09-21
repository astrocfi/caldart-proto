"""Payment reporting: filters, the period summary and the CSV export.

Everything here works off one annotation, ``paid_at`` — the moment the money
arrived, which is ``completed_at`` for a settled payment and ``created_at`` for
one that never got that far.  Using it for both the date filter and the
grouping keeps the list, the summary and the export answering the same
question.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TypedDict

from django.db.models import Count, Q, QuerySet, Sum
from django.db.models.functions import Coalesce, TruncMonth, TruncYear
from django.utils import timezone

from apps.payments.models import Payment, PaymentStatus

#: Columns of ``GET /admin/payments/export.csv``.
CSV_HEADER = (
    "paid_on",
    "name",
    "email",
    "plan",
    "plan_amount",
    "contribution",
    "total",
    "provider",
    "wallet",
    "status",
    "provider_ref",
)

GROUPS = {"month": TruncMonth, "year": TruncYear}
PERIOD_FORMAT = {"month": "%Y-%m", "year": "%Y"}

#: The period :func:`summarize` groups by unless the caller asks for the other.
DEFAULT_GROUP = "month"

#: Fields ``?ordering=`` accepts, as DRF's OrderingFilter would spell them.
ORDERING_FIELDS = (
    "paid_at",
    "created_at",
    "completed_at",
    "amount_cents",
    "contribution_cents",
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
    by_provider: dict[str, int]


def base_queryset() -> QuerySet[Payment]:
    """Every payment, annotated with ``paid_at`` and joined for display."""
    return Payment.objects.select_related("user", "plan").annotate(
        paid_at=Coalesce("completed_at", "created_at")
    )


@dataclass(frozen=True)
class PaymentFilters:
    """The narrowing the list, summary and CSV endpoints share.

    Each field is already validated: the API layer reads the query string, and an
    empty string or ``None`` means "do not narrow on this".
    """

    date_from: dt.date | None = None
    date_to: dt.date | None = None
    provider: str = ""
    status: str = ""
    search: str = ""


def apply_filters(queryset: QuerySet[Payment], filters: PaymentFilters) -> QuerySet[Payment]:
    """Narrow ``queryset`` (which must carry ``paid_at``) by ``filters``."""
    # django-stubs resolves field names against the model, so it cannot see the
    # ``paid_at`` annotation :func:`base_queryset` adds.
    if filters.date_from:
        queryset = queryset.filter(paid_at__date__gte=filters.date_from)  # type: ignore[misc]
    if filters.date_to:
        queryset = queryset.filter(paid_at__date__lte=filters.date_to)  # type: ignore[misc]
    if filters.provider:
        queryset = queryset.filter(provider=filters.provider)
    if filters.status:
        queryset = queryset.filter(status=filters.status)
    if filters.search:
        term = filters.search
        queryset = queryset.filter(
            Q(user__email__icontains=term)
            | Q(user__first_name__icontains=term)
            | Q(user__last_name__icontains=term)
            | Q(provider_ref__icontains=term)
        )
    return queryset


def summarize(queryset: QuerySet[Payment], group: str = DEFAULT_GROUP) -> list[PeriodSummary]:
    """Money received per period, oldest first.

    ``group`` is a key of :data:`GROUPS`, which the API layer has already checked.
    Only succeeded payments count: a pending or failed attempt never became
    revenue.  ``by_provider`` breaks the period total down by provider and
    omits providers with nothing in that period.
    """
    rows = (
        queryset.filter(status=PaymentStatus.SUCCEEDED)
        .annotate(period=GROUPS[group]("paid_at"))
        .values("period", "provider")
        .annotate(
            count=Count("id"),
            total_cents=Sum("amount_cents"),
            plan_cents=Sum("plan_amount_cents"),
            contribution_cents=Sum("contribution_cents"),
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
                "by_provider": {},
            },
        )
        bucket["count"] += row["count"]
        bucket["total_cents"] += row["total_cents"] or 0
        bucket["plan_cents"] += row["plan_cents"] or 0
        bucket["contribution_cents"] += row["contribution_cents"] or 0
        provider = row["provider"]
        bucket["by_provider"][provider] = bucket["by_provider"].get(provider, 0) + (
            row["total_cents"] or 0
        )

    return [periods[key] for key in sorted(periods)]


def _dollars(cents: int | None) -> str:
    return f"{(cents or 0) / 100:.2f}"


def csv_rows(queryset: QuerySet[Payment]) -> Iterator[list[str]]:
    """Lazily yield the export rows, matching :data:`CSV_HEADER`.

    Dates are the local date the money arrived, money is dollars with two places
    and no sign, and a payment with no plan exports an empty plan cell.  A member
    with neither first nor last name is exported under their email address.
    """
    for payment in queryset.iterator(chunk_size=200):
        paid_at = payment.completed_at or payment.created_at
        name = f"{payment.user.first_name} {payment.user.last_name}".strip()
        yield [
            timezone.localtime(paid_at).date().isoformat() if paid_at else "",
            name or payment.user.email,
            payment.user.email,
            payment.plan.name if payment.plan is not None else "",
            _dollars(payment.plan_amount_cents),
            _dollars(payment.contribution_cents),
            _dollars(payment.amount_cents),
            payment.provider,
            payment.wallet,
            payment.status,
            payment.provider_ref,
        ]
