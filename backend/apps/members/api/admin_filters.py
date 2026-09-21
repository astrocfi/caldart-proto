"""Filtering and ordering for the members admin API.

The ``status`` and ``expiring_within`` filters and ``ordering=expires_on`` all
need the *computed* membership status, which ``members.services`` states as
correlated subqueries so the database can filter, order and paginate on it.
:func:`member_admin_queryset` hangs those annotations on the user table with
``members.services.with_membership`` and adds the two this list needs on top of
them, in :func:`derived_annotations`.
"""

from __future__ import annotations

from datetime import date, timedelta

import django_filters
from django.contrib.auth import get_user_model
from django.db.models import Case, CharField, DateField, F, Q, QuerySet, Value, When
from django.db.models.functions import Concat
from django.utils import timezone
from rest_framework import filters as drf_filters

from apps.accounts.roles import ROLE_SLUGS
from apps.members.models import MedicalType, MembershipState, PilotCertificateType
from apps.members.services import with_membership

User = get_user_model()

#: Longest "expiring within" window this filter will answer.  Matches
#: ``apps.aircraft.services.MAX_EXPIRING_WINDOW_DAYS``; clamping to it keeps
#: ``today + timedelta(days=n)`` from raising ``OverflowError`` -- a 500 -- on
#: an absurd query string.
MAX_EXPIRING_WINDOW_DAYS = 3650


def derived_annotations() -> dict:
    """What this list needs on top of the membership annotations.

    ``full_name`` serves ``?search=``; ``effective_expiry`` is built on
    ``covers_today``, ``coverage_end`` and ``past_end`` and serves
    ``?ordering=expires_on``.
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


def member_admin_queryset(today: date | None = None) -> QuerySet:
    """Every account, annotated with its membership status.

    Everyone in the table is listed: ``member`` is granted at registration, so
    "members" and "accounts" are the same population, and ``?role=`` narrows it.
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
        method="filter_search", label="Name, email, phone or certificate number"
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
    def filter_search(self, queryset, name, value):
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

    def filter_status(self, queryset, name, value):
        if value == MembershipState.CURRENT:
            return queryset.filter(covers_today=True)
        if value == MembershipState.EXPIRED:
            return queryset.filter(covers_today=False, has_started_term=True)
        if value == MembershipState.NONE:
            return queryset.filter(covers_today=False, has_started_term=False)
        return queryset

    def filter_dart(self, queryset, name, value):
        value = (value or "").strip()
        if not value:
            return queryset
        if value.isdigit():
            return queryset.filter(profile__dart_id=int(value))
        return queryset.filter(profile__dart__name__icontains=value)

    def filter_role(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(groups__name=value)

    def filter_expiring_within(self, queryset, name, value):
        """Current members whose computed expiry falls in the next N days.

        ``value`` is clamped to ``0..MAX_EXPIRING_WINDOW_DAYS`` before use, so a
        negative or absurdly large window never raises ``OverflowError``.
        """
        if value is None:
            return queryset
        window = min(max(int(value), 0), MAX_EXPIRING_WINDOW_DAYS)
        cutoff = timezone.localdate() + timedelta(days=window)
        return queryset.filter(
            covers_today=True, coverage_end__isnull=False, coverage_end__lte=cutoff
        )


class MemberOrderingFilter(drf_filters.OrderingFilter):
    """``?ordering=`` over four sorts: ``name``, ``email``, ``expires_on`` and ``joined``.

    Each alias expands to real columns, so ``name`` sorts by surname then
    forename, and the two computed dates keep empty values at the end whichever
    direction is asked for (a lifetime member has no expiry to compare).
    """

    ordering_description = "Which field to order by: name, email, expires_on or joined."

    aliases: dict[str, tuple[str, ...]] = {
        "name": ("last_name", "first_name", "email"),
        "email": ("email",),
        "expires_on": ("effective_expiry",),
        "joined": ("joined_on",),
    }

    def get_valid_fields(self, queryset, view, context=None):
        return [(alias, alias) for alias in self.aliases]

    def filter_queryset(self, request, queryset, view):
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


def applied_filters(request) -> dict[str, str]:
    """The filters the caller actually supplied, for the report subtitle."""
    return {
        key: request.query_params[key]
        for key in EXPORT_FILTER_PARAMS
        if request.query_params.get(key)
    }
