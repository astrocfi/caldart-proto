"""Filtering and ordering for the members admin API.

The ``status`` and ``expiring_within`` filters and ``ordering=expires_on`` all
need the *computed* membership status, which ``members.services`` states as
correlated subqueries so the database can filter, order, and paginate on it.
:func:`member_admin_queryset` hangs those annotations on the user table with
``members.services.with_membership`` and adds the two this list needs on top of
them, in :func:`derived_annotations`.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any

import django_filters
from django.db.models import Case, CharField, DateField, F, Model, Q, QuerySet, Value, When
from django.db.models.functions import Concat
from django.utils import timezone
from rest_framework import filters as drf_filters
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.roles import ROLE_SLUGS
from apps.members.models import MedicalType, MembershipState, PilotCertificateType
from apps.members.services import with_membership

if TYPE_CHECKING:
    from apps.members.services import MemberRow

#: Longest "expiring within" window this filter will answer.  Matches
#: ``apps.aircraft.services.MAX_EXPIRING_WINDOW_DAYS``; clamping to it keeps
#: ``today + timedelta(days=n)`` from raising ``OverflowError`` -- a 500 -- on
#: an absurd query string.
MAX_EXPIRING_WINDOW_DAYS = 3650


def derived_annotations() -> dict[str, Concat | Case]:
    """What this list needs on top of the membership annotations.

    ``full_name`` serves ``?search=``; ``effective_expiry`` is built on
    ``covers_today``, ``coverage_end``, and ``past_end`` and serves
    ``?ordering=expires_on``.  Splat the result into ``QuerySet.annotate`` on a
    queryset that already carries the membership annotations.
    """
    return {
        "full_name": Concat(F("first_name"), Value(" "), F("last_name"), output_field=CharField()),
        # The date the list sorts on: the end of current coverage, else the
        # date the last term ran out.  NULL for lifetime and never-a-member,
        # which ``MemberOrderingFilter`` keeps at the end of the page.
        "effective_expiry": Case(
            When(covers_today=True, then=F("coverage_end")),
            default=F("past_end"),
            output_field=DateField(),
        ),
    }


def member_admin_queryset(today: date | None = None) -> QuerySet[MemberRow]:
    """Every account, annotated with its membership status.

    Everyone in the table is listed: ``member`` is granted at registration, so
    "members" and "accounts" are the same population, and ``?role=`` narrows it.
    The status is worked out for ``today``, defaulting to the current local
    date, and each row arrives with its profile, DART, and aircraft fetched.
    """
    return with_membership(
        User.objects.select_related("profile", "profile__dart").prefetch_related(
            "profile__aircraft"
        ),
        today=today,
    ).annotate(**derived_annotations())


class MemberAdminFilterSet(django_filters.FilterSet):
    """``GET /admin/members`` query parameters."""

    search = django_filters.CharFilter(
        method="filter_search", label="Name, email, phone, or certificate number"
    )
    status = django_filters.ChoiceFilter(
        choices=MembershipState.choices, method="filter_status", label="Membership status"
    )
    certificate = django_filters.ChoiceFilter(
        field_name="profile__pilot_certificate_type",
        choices=PilotCertificateType.choices,
        label="Pilot certificate",
    )
    medical = django_filters.ChoiceFilter(
        field_name="profile__medical_type", choices=MedicalType.choices, label="Medical"
    )
    dart = django_filters.CharFilter(method="filter_dart", label="DART (id or name)")
    role = django_filters.ChoiceFilter(
        choices=[(slug, slug) for slug in ROLE_SLUGS], method="filter_role", label="Role"
    )
    expiring_within = django_filters.NumberFilter(
        method="filter_expiring_within", label="Expiring within N days"
    )
    is_active = django_filters.BooleanFilter(field_name="is_active", label="Account active")

    class Meta:
        model = User
        fields: list[str] = []

    # -- methods -----------------------------------------------------------
    def filter_search(
        self, queryset: QuerySet[MemberRow], name: str, value: str | None
    ) -> QuerySet[MemberRow]:
        """Rows whose name, email, either phone or certificate number contains ``value``.

        The whole queryset comes back for a blank or missing value, and the
        match is case-insensitive on every one of those fields.
        """
        value = (value or "").strip()
        if not value:
            return queryset
        return queryset.filter(
            Q(full_name__icontains=value)
            | Q(email__icontains=value)
            | Q(profile__phone__icontains=value)
            | Q(profile__phone_alt__icontains=value)
            | Q(profile__certificate_number__icontains=value)
        )

    def filter_status(
        self, queryset: QuerySet[MemberRow], name: str, value: str | None
    ) -> QuerySet[MemberRow]:
        """Rows whose computed membership status is ``value``.

        ``current`` is a term covering today, ``expired`` a paid term that has
        started and run out, ``new`` an account whose only term is unpaid, and
        ``none`` an account with no term at all.  Anything else leaves the
        queryset alone.
        """
        if value == MembershipState.CURRENT:
            return queryset.filter(covers_today=True)
        if value == MembershipState.EXPIRED:
            return queryset.filter(covers_today=False, has_started_term=True)
        if value == MembershipState.NEW:
            return queryset.filter(covers_today=False, has_started_term=False, has_unpaid_term=True)
        if value == MembershipState.NONE:
            return queryset.filter(
                covers_today=False, has_started_term=False, has_unpaid_term=False
            )
        return queryset

    def filter_dart(
        self, queryset: QuerySet[MemberRow], name: str, value: str | None
    ) -> QuerySet[MemberRow]:
        """Rows whose profile names that DART, by id or by part of its name.

        An all-digit value is read as the DART's id and anything else as a
        case-insensitive fragment of its name.  A blank or missing value leaves
        the queryset alone.
        """
        value = (value or "").strip()
        if not value:
            return queryset
        if value.isdigit():
            return queryset.filter(profile__dart_id=int(value))
        return queryset.filter(profile__dart__name__icontains=value)

    def filter_role(
        self, queryset: QuerySet[MemberRow], name: str, value: str | None
    ) -> QuerySet[MemberRow]:
        """Rows holding that role group, by slug; a blank value narrows nothing.

        The test is the role group the account is actually in, so a superuser
        who was never added to one is not listed by ``?role=system_admin``.
        """
        if not value:
            return queryset
        return queryset.filter(groups__name=value)

    def filter_expiring_within(
        self, queryset: QuerySet[MemberRow], name: str, value: float | None
    ) -> QuerySet[MemberRow]:
        """Current members whose computed expiry falls in the next N days.

        ``value`` is clamped to ``0..MAX_EXPIRING_WINDOW_DAYS`` before use, so a
        negative or absurdly large window never raises ``OverflowError``.  A
        missing value leaves the queryset alone, and a lifetime member is never
        listed: there is no date to compare.
        """
        if value is None:
            return queryset
        window = min(max(int(value), 0), MAX_EXPIRING_WINDOW_DAYS)
        cutoff = timezone.localdate() + timedelta(days=window)
        return queryset.filter(
            covers_today=True, coverage_end__isnull=False, coverage_end__lte=cutoff
        )


class MemberOrderingFilter(drf_filters.OrderingFilter):
    """``?ordering=`` over ``name``, ``email``, ``expires_on`` and ``joined``.

    Each alias expands to real columns, so ``name`` sorts by surname then
    forename, and the two computed dates keep empty values at the end whichever
    direction is asked for (a lifetime member has no expiry to compare).
    """

    ordering_description = "Which field to order by: name, email, expires_on, or joined."

    aliases: dict[str, tuple[str, ...]] = {
        "name": ("last_name", "first_name", "email"),
        "email": ("email",),
        "expires_on": ("effective_expiry",),
        "joined": ("joined_on",),
    }

    def get_valid_fields(
        self,
        queryset: QuerySet[MemberRow],
        view: APIView,
        context: Mapping[str, Any] | None = None,
    ) -> list[tuple[str, str]]:
        """The four aliases, as DRF's ``(value, label)`` pairs.

        Only these are accepted, so ``?ordering=`` can never reach a column the
        list does not sort on.
        """
        return [(alias, alias) for alias in self.aliases]

    def filter_queryset[M: Model, R](
        self, request: Request, queryset: QuerySet[M, R], view: APIView
    ) -> QuerySet[M, R]:
        """``queryset`` ordered by the requested alias, defaulting to ``name``.

        Each alias expands to its real columns, a leading ``-`` reverses them,
        and empty values sort last whichever direction is asked for.
        """
        ordering = self.get_ordering(request, queryset, view) or ["name"]
        terms = []
        for term in ordering:
            descending = term.startswith("-")
            for field in self.aliases.get(term.lstrip("-"), ()):
                expression = F(field)
                terms.append(
                    expression.desc(nulls_last=True)
                    if descending
                    else expression.asc(nulls_last=True)
                )
        return queryset.order_by(*terms) if terms else queryset


#: Query parameters echoed into the PDF subtitle.
EXPORT_FILTER_PARAMS: tuple[str, ...] = (
    "search",
    "status",
    "certificate",
    "medical",
    "dart",
    "role",
    "expiring_within",
    "is_active",
    "ordering",
)


def applied_filters(request: Request) -> dict[str, str]:
    """The filters the caller actually supplied, for the report subtitle.

    Only the parameters in ``EXPORT_FILTER_PARAMS`` are looked at, and only
    those the query string gives a non-empty value.
    """
    return {
        key: request.query_params[key]
        for key in EXPORT_FILTER_PARAMS
        if request.query_params.get(key)
    }
