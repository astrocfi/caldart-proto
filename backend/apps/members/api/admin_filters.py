"""Filtering, ordering and membership annotations for the members admin API.

The ``status`` and ``expiring_within`` filters and ``ordering=expires_on`` all
need the *computed* membership status, which
``members.services.membership_status`` works out in Python.  Recomputing that
per row would be a query per member and could not be filtered or ordered in the
database at all, so :func:`membership_annotations` expresses exactly the same
rules as correlated subqueries.

The translation, term by term:

``covers_today``
    An active term has started and has not run out — ``_current_term``.
``coverage_end``
    ``_coverage`` walks forward from the covering term through terms that start
    no later than the day after the previous one ends.  The end of that walk is
    the earliest *boundary*: an active term ending on or after today that no
    other active term continues.  Anything ending earlier inside the chain has
    a follower by definition, and anything in a later chain ends after the gap,
    so "earliest boundary" and "end of the walk" are the same date.  NULL means
    the chain reaches a lifetime term (or that nothing covers today).
``past_end`` / ``past_plan``
    The most recent non-cancelled term that has started, which
    ``membership_status`` reports for an expired member.

``tests/test_members_admin_status.py`` checks the two implementations agree
over a deliberately awkward set of histories, including early renewals, gaps
and cancelled terms.
"""

from __future__ import annotations

from datetime import date, timedelta

import django_filters
from django.contrib.auth import get_user_model
from django.db.models import (
    Case,
    CharField,
    DateField,
    Exists,
    F,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    Value,
    When,
)
from django.db.models.functions import Concat
from django.utils import timezone
from rest_framework import filters as drf_filters

from apps.accounts.roles import ROLE_SLUGS
from apps.members.models import (
    MedicalType,
    Membership,
    MembershipStatusChoices,
    PilotCertificateType,
)

User = get_user_model()

#: The three values ``?status=`` accepts.
STATUS_CHOICES: tuple[tuple[str, str], ...] = (
    ("current", "Current"),
    ("expired", "Expired"),
    ("none", "Never a member"),
)


def membership_annotations(today: date | None = None) -> dict:
    """Annotations mirroring ``members.services.membership_status`` in SQL."""
    today = today or timezone.localdate()
    active = Membership.objects.filter(status=MembershipStatusChoices.ACTIVE)

    # A later term that continues the one being examined: it starts no later
    # than the day after this one ends, and reaches further into the future.
    follower = active.filter(
        user=OuterRef("user"),
        starts_on__lte=OuterRef("ends_on") + timedelta(days=1),
    ).filter(Q(ends_on__isnull=True) | Q(ends_on__gt=OuterRef("ends_on")))

    boundaries = (
        active.filter(user=OuterRef("pk"), ends_on__isnull=False, ends_on__gte=today)
        .filter(~Exists(follower))
        .order_by("ends_on")
    )

    lifetime = active.filter(user=OuterRef("pk"), ends_on__isnull=True).order_by("starts_on")

    started = Membership.objects.exclude(status=MembershipStatusChoices.CANCELLED).filter(
        user=OuterRef("pk"), starts_on__lte=today
    )
    past = started.order_by(F("ends_on").desc(nulls_first=True), "-starts_on")

    return {
        "covers_today": Exists(
            active.filter(user=OuterRef("pk"), starts_on__lte=today).filter(
                Q(ends_on__isnull=True) | Q(ends_on__gte=today)
            )
        ),
        "has_started_term": Exists(started),
        "coverage_end": Subquery(boundaries.values("ends_on")[:1], output_field=DateField()),
        "coverage_plan": Subquery(boundaries.values("plan__name")[:1], output_field=CharField()),
        "lifetime_plan": Subquery(lifetime.values("plan__name")[:1], output_field=CharField()),
        "past_end": Subquery(past.values("ends_on")[:1], output_field=DateField()),
        "past_plan": Subquery(past.values("plan__name")[:1], output_field=CharField()),
        "joined_on": Subquery(
            Membership.objects.filter(user=OuterRef("pk"))
            .order_by("starts_on")
            .values("starts_on")[:1],
            output_field=DateField(),
        ),
        "full_name": Concat(F("first_name"), Value(" "), F("last_name"), output_field=CharField()),
    }


def derived_annotations() -> dict:
    """Annotations built on :func:`membership_annotations`, for ``?ordering=``."""
    return {
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
    return (
        User.objects.select_related("profile", "profile__dart")
        .prefetch_related("profile__aircraft")
        .annotate(**membership_annotations(today))
        .annotate(**derived_annotations())
    )


def membership_payload(user) -> dict:
    """Read the annotated status back in ``membership_status`` shape."""
    if user.covers_today:
        lifetime = user.coverage_end is None
        return {
            "status": "current",
            "expires_on": user.coverage_end,
            "plan": user.lifetime_plan if lifetime else user.coverage_plan,
            "is_lifetime": lifetime,
        }
    if user.has_started_term:
        return {
            "status": "expired",
            "expires_on": user.past_end,
            "plan": user.past_plan,
            "is_lifetime": False,
        }
    return {"status": "none", "expires_on": None, "plan": None, "is_lifetime": False}


class MemberAdminFilterSet(django_filters.FilterSet):
    """``GET /admin/members`` query parameters."""

    search = django_filters.CharFilter(
        method="filter_search", label="Name, email, phone or certificate number"
    )
    status = django_filters.ChoiceFilter(
        choices=STATUS_CHOICES, method="filter_status", label="Membership status"
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
        if value == "current":
            return queryset.filter(covers_today=True)
        if value == "expired":
            return queryset.filter(covers_today=False, has_started_term=True)
        if value == "none":
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
        """Current members whose computed expiry falls in the next N days."""
        if value is None:
            return queryset
        days = int(value)
        cutoff = timezone.localdate() + timedelta(days=days)
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
