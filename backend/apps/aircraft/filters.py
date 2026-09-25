"""django-filter definitions for the aircraft register.

The list endpoint and both exports share this filter set, so a CSV or PDF a
member downloads always contains exactly the rows they were looking at.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

import django_filters
from django.db.models import F, Q, QuerySet
from rest_framework.filters import OrderingFilter

from apps.aircraft.models import Aircraft, OwnerType, normalize_n_number
from apps.aircraft.services import expiring_within, insurance_queryset

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.views import APIView

INSURANCE_CHOICES = (
    ("current", "Current"),
    ("expired", "Expired"),
    ("missing", "Not on file"),
)


class AircraftFilter(django_filters.FilterSet):
    """``?search=&make=&owner_type=&insurance=&expiring_within=``."""

    search = django_filters.CharFilter(method="filter_search", label="Search")
    make = django_filters.CharFilter(field_name="make", lookup_expr="icontains")
    owner_type = django_filters.ChoiceFilter(choices=OwnerType.choices)
    insurance = django_filters.ChoiceFilter(
        choices=INSURANCE_CHOICES, method="filter_insurance", label="Insurance"
    )
    expiring_within = django_filters.NumberFilter(
        method="filter_expiring_within", label="Expiring within (days)"
    )
    is_active = django_filters.BooleanFilter(field_name="is_active", label="In service")

    class Meta:
        model = Aircraft
        fields = ["search", "make", "owner_type", "insurance", "expiring_within", "is_active"]

    def filter_search(
        self, queryset: QuerySet[Aircraft], name: str, value: str
    ) -> QuerySet[Aircraft]:
        """N-number, make, model, or owner name.

        The N-number half searches the normalized form too, so ``n-172sp``
        , ``172sp``, and ``N172SP`` are all the same query.
        """
        term = (value or "").strip()
        if not term:
            return queryset
        matches = (
            Q(n_number__icontains=term)
            | Q(make__icontains=term)
            | Q(model__icontains=term)
            | Q(owner_name__icontains=term)
        )
        normalized = normalize_n_number(term)
        if normalized:
            matches |= Q(n_number__icontains=normalized)
        return queryset.filter(matches)

    def filter_insurance(
        self, queryset: QuerySet[Aircraft], name: str, value: str
    ) -> QuerySet[Aircraft]:
        """Narrow ``queryset`` to ``current``, ``expired``, or ``missing`` cover."""
        return insurance_queryset(queryset, value)

    def filter_expiring_within(
        self, queryset: QuerySet[Aircraft], name: str, value: Decimal | None
    ) -> QuerySet[Aircraft]:
        """Narrow ``queryset`` to cover that expires within ``value`` days from today.

        Returns ``queryset`` unfiltered when ``value`` is ``None``.  ``NumberFilter``
        cleans the query string through a form ``DecimalField``, so ``value`` arrives
        as a ``Decimal`` number of days, truncated here to whole days and clamped to
        ``0..MAX_EXPIRING_WINDOW_DAYS`` (3650) before use.  Aircraft whose cover has
        already lapsed are excluded.
        """
        if value is None:
            return queryset
        return expiring_within(queryset, int(value))


class NullsLastOrderingFilter(OrderingFilter):
    """``?ordering=`` that keeps empty values at the bottom either way.

    Postgres sorts NULLs first on a descending order, which would put every
    aircraft with no insurance on file at the top of "latest expiry" -- the
    opposite of what an administrator chasing lapsed cover wants to see.

    Every ordering also ends in the primary key.  Sorting the register by a
    column many rows share -- ``make``, or an expiry date a whole club renews
    on one day -- otherwise leaves the tie order undefined, and page two of a
    ``LIMIT``/``OFFSET`` query can then repeat or skip rows.
    """

    def filter_queryset(
        self, request: Request, queryset: QuerySet[Any], view: APIView
    ) -> QuerySet[Any]:
        """Apply ``ordering``, with NULLs last and the primary key as a tiebreaker."""
        ordering = self.get_ordering(request, queryset, view)
        if not ordering:
            return queryset
        terms = [
            F(term[1:]).desc(nulls_last=True)
            if term.startswith("-")
            else F(term).asc(nulls_last=True)
            for term in ordering
        ]
        if not any(term.lstrip("-") in {"pk", "id"} for term in ordering):
            terms.append(F("pk").asc())
        return queryset.order_by(*terms)
