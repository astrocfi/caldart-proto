"""django-filter definitions and the ordering for the aircraft register.

The list endpoint and the aircraft report share this filter set and this ordering,
so a CSV or PDF an administrator downloads always contains exactly the rows they
were looking at, in the same order.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import django_filters
from django.db.models import F, Model, Q, QuerySet
from rest_framework.filters import OrderingFilter

from apps.aircraft.models import Aircraft, OwnerType, normalize_n_number
from apps.aircraft.services import expiring_within, insurance_queryset
from caldart.reports import ordering_terms

if TYPE_CHECKING:
    from rest_framework.request import Request
    from rest_framework.views import APIView

#: The fields ``?ordering=`` accepts.  The first three are the core sorts;
#: ``model`` and ``owner_name`` are here so every column of the admin table is
#: genuinely sortable.
ORDERING_FIELDS = ["n_number", "make", "insurance_expiration", "model", "owner_name"]

#: The order the register takes when ``?ordering=`` names nothing it accepts.
DEFAULT_ORDERING = ["n_number"]

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
        """Apply ``ordering`` through :func:`nulls_last_order`; no ordering, no change."""
        ordering = self.get_ordering(request, queryset, view)
        if not ordering:
            return queryset
        return nulls_last_order(queryset, ordering)


def nulls_last_order[M: Model](queryset: QuerySet[M], ordering: Sequence[str]) -> QuerySet[M]:
    """``queryset`` ordered by ``ordering``, NULLs last either way, the key breaking ties.

    Each term is a field name with an optional leading ``-`` for descending.  Unless a
    term already names the primary key, ``pk`` ascending is appended, so rows the
    ordering cannot separate keep a stable order from one page to the next.
    """
    terms = [
        F(term[1:]).desc(nulls_last=True) if term.startswith("-") else F(term).asc(nulls_last=True)
        for term in ordering
    ]
    if not any(term.lstrip("-") in {"pk", "id"} for term in ordering):
        terms.append(F("pk").asc())
    return queryset.order_by(*terms)


def order_register(queryset: QuerySet[Aircraft], ordering: str) -> QuerySet[Aircraft]:
    """The register ordered by a comma-separated ``ordering``, as the list orders it.

    Terms naming a field outside :data:`ORDERING_FIELDS` are dropped, and when none is
    left the order is :data:`DEFAULT_ORDERING`; :func:`nulls_last_order` does the rest.
    """
    terms = [term for term in ordering_terms(ordering) if term.removeprefix("-") in ORDERING_FIELDS]
    return nulls_last_order(queryset, terms or DEFAULT_ORDERING)
