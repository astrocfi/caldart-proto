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

from django.db.models import Count, Q, QuerySet, Sum
from django.db.models.functions import Coalesce, TruncMonth, TruncYear
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.exceptions import ValidationError

from apps.payments.models import Payment, PaymentProvider, PaymentStatus

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


def base_queryset() -> QuerySet[Payment]:
    """Every payment, annotated with ``paid_at`` and joined for display."""
    return Payment.objects.select_related("user", "plan").annotate(
        paid_at=Coalesce("completed_at", "created_at")
    )


@dataclass(frozen=True)
class PaymentFilters:
    """The query parameters shared by the list, summary and CSV endpoints."""

    date_from: dt.date | None = None
    date_to: dt.date | None = None
    provider: str = ""
    status: str = ""
    search: str = ""

    @classmethod
    def from_query(cls, params) -> PaymentFilters:
        provider = (params.get("provider") or "").strip()
        if provider and provider not in PaymentProvider.values:
            raise ValidationError({"provider": f"Unknown provider '{provider}'."})

        status = (params.get("status") or "").strip()
        if status and status not in PaymentStatus.values:
            raise ValidationError({"status": f"Unknown status '{status}'."})

        return cls(
            date_from=_date(params.get("from"), "from"),
            date_to=_date(params.get("to"), "to"),
            provider=provider,
            status=status,
            search=(params.get("search") or "").strip(),
        )


def _date(value: str | None, field: str) -> dt.date | None:
    if not value:
        return None
    parsed = parse_date(value)
    if parsed is None:
        raise ValidationError({field: "Expected a date as YYYY-MM-DD."})
    return parsed


def apply_filters(queryset: QuerySet[Payment], filters: PaymentFilters) -> QuerySet[Payment]:
    """Narrow ``queryset`` (which must carry ``paid_at``) by ``filters``."""
    if filters.date_from:
        queryset = queryset.filter(paid_at__date__gte=filters.date_from)
    if filters.date_to:
        queryset = queryset.filter(paid_at__date__lte=filters.date_to)
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


def summarize(queryset: QuerySet[Payment], group: str = "month") -> list[dict]:
    """Money received per period, oldest first.

    Only succeeded payments count: a pending or failed attempt never became
    revenue.  ``by_provider`` breaks the period total down by provider and
    omits providers with nothing in that period.
    """
    if group not in GROUPS:
        raise ValidationError({"group": "Expected 'month' or 'year'."})

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

    periods: dict[str, dict] = {}
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


def csv_rows(queryset: QuerySet[Payment]) -> Iterator[list]:
    """Lazily yield the export rows, matching :data:`CSV_HEADER`."""
    for payment in queryset.iterator(chunk_size=200):
        paid_at = payment.completed_at or payment.created_at
        name = f"{payment.user.first_name} {payment.user.last_name}".strip()
        yield [
            timezone.localtime(paid_at).date().isoformat() if paid_at else "",
            name or payment.user.email,
            payment.user.email,
            payment.plan.name if payment.plan_id else "",
            _dollars(payment.plan_amount_cents),
            _dollars(payment.contribution_cents),
            _dollars(payment.amount_cents),
            payment.provider,
            payment.wallet,
            payment.status,
            payment.provider_ref,
        ]
