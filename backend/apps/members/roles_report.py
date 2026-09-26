"""The CalDART roles report: who holds each role other than member.

One section per staff role, least privileged first, each drawn even when nobody holds
that role, and one row for every role an active account holds, so an account holding
two staff roles is listed in both sections.  The house style lives in
``caldart.reports``; this module decides which rows the report holds, how its filters
narrow them, and what each cell prints.  It lives beside the membership report because
its rows read the membership state, which the accounts app sits below.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING

import django_filters
from django.db.models import Q

from apps.accounts.models import AccountKind, User
from apps.accounts.roles import ACCOUNT_ADMIN, STAFF_ROLE_LABELS, STAFF_ROLE_SLUGS, USER_ADMIN
from apps.members.models import MemberProfile
from apps.members.services import MembershipStatusDict, membership_payload, with_membership
from caldart.reports import (
    Params,
    ReportColumn,
    ReportQuery,
    ReportSpec,
    apply_filterset,
    given_params,
)

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from apps.members.services import MemberRow

#: The filters the PDF subtitle and the email name, in order, when given a value.
EXPORT_FILTER_PARAMS: tuple[str, ...] = ("search", "role", "kind")

#: The line the PDF draws under a role nobody holds.
EMPTY_SECTION = "Nobody holds this role."

#: The kinds ``?kind=`` accepts: a donor never holds a role, so it is not one.
ROLE_HOLDER_KINDS: list[tuple[str, str]] = [
    (AccountKind.MEMBER.value, AccountKind.MEMBER.label),
    (AccountKind.FRIEND.value, AccountKind.FRIEND.label),
]


class RolesReportFilterSet(django_filters.FilterSet):
    """``?search=&role=&kind=`` on the roles report.

    ``search`` splits on whitespace and keeps the accounts every word of which matches
    part of the first name, the last name, or the address, case-insensitively, which
    is how the users list searches.  ``role`` is one staff role's slug and keeps its
    holders; the member role, or any other slug, is refused.  ``kind`` is ``member``
    or ``friend``, matched against the effective kind the queryset is annotated with,
    and anything else is refused.  A parameter the set does not name is ignored, as
    the users list ignores it.
    """

    search = django_filters.CharFilter(method="filter_search", label="Name or email")
    role = django_filters.ChoiceFilter(
        choices=[(slug, slug) for slug in STAFF_ROLE_SLUGS],
        field_name="groups__name",
        label="Staff role slug",
    )
    kind = django_filters.ChoiceFilter(
        choices=ROLE_HOLDER_KINDS, field_name="effective_kind", label="Member or friend"
    )

    class Meta:
        model = User
        fields: list[str] = []

    def filter_search(
        self, queryset: QuerySet[MemberRow], name: str, value: str | None
    ) -> QuerySet[MemberRow]:
        """Rows every word of ``value`` matches in the first name, last name, or email.

        A blank or missing value narrows nothing.
        """
        for word in (value or "").split():
            queryset = queryset.filter(
                Q(first_name__icontains=word)
                | Q(last_name__icontains=word)
                | Q(email__icontains=word)
            )
        return queryset


@dataclass(frozen=True)
class RoleRow:
    """One role held by one account, with everything the columns read.

    ``role`` is the role's slug and ``role_label`` its name, which is also the title
    of the section the row is drawn in.  ``profile`` is ``None`` for an account with
    no profile, and every column that reads it is then blank.
    """

    role: str
    role_label: str
    user: MemberRow
    profile: MemberProfile | None
    membership: MembershipStatusDict


def _profile_text(row: RoleRow, field: str) -> str:
    """The text in the profile's ``field``, or a blank cell without a profile."""
    text: str = getattr(row.profile, field) if row.profile is not None else ""
    return text


def _dart(row: RoleRow) -> str:
    """The name of the account's DART, or a blank cell without one."""
    if row.profile is None or row.profile.dart is None:
        return ""
    return row.profile.dart.name


#: Every column the roles report can carry, in export order.  The seven defaults are
#: sized so that no seeded cell or heading wraps
#: (``test_no_default_roles_cell_wraps_in_the_pdf``).  ``kind`` is the effective
#: kind's label, Member or Friend, and ``membership`` the membership state's label,
#: exactly as the membership report's Kind and Status columns read them.
ROLES_REPORT_COLUMNS: tuple[ReportColumn[RoleRow], ...] = (
    ReportColumn("role", "Role", True, lambda row: row.role_label, width=2.6),
    ReportColumn("name", "Name", True, lambda row: row.user.display_name, width=2.6),
    ReportColumn("email", "Email", True, lambda row: row.user.email, width=4.4),
    ReportColumn("phone", "Phone", True, lambda row: _profile_text(row, "phone"), width=1.9),
    ReportColumn("dart", "DART", True, _dart, width=3.4),
    ReportColumn(
        "kind", "Kind", True, lambda row: AccountKind(row.user.effective_kind).label, width=1.2
    ),
    ReportColumn(
        "membership", "Membership", True, lambda row: row.membership["status"].label, width=1.8
    ),
    ReportColumn("city", "City", False, lambda row: _profile_text(row, "city"), width=1.6),
    ReportColumn("county", "County", False, lambda row: _profile_text(row, "county"), width=1.8),
    ReportColumn(
        "home_airport",
        "Home airport",
        False,
        lambda row: _profile_text(row, "home_airport_identifier"),
        width=1.6,
    ),
)


def role_holders(params: Params) -> QuerySet[MemberRow]:
    """The active accounts holding a staff role, narrowed by ``params``, in name order.

    ``params`` are read by :class:`RolesReportFilterSet`, and a value it refuses raises
    DRF's ``ValidationError`` keyed by that filter.  The order is last name, first
    name, then address, and each account arrives with its role groups, its profile and
    its DART fetched and its membership annotated.
    """
    staff = User.objects.filter(groups__name__in=STAFF_ROLE_SLUGS).values("pk")
    accounts = with_membership(
        User.objects.filter(is_active=True, pk__in=staff)
        .select_related("profile", "profile__dart")
        .prefetch_related("groups")
    )
    narrowed = apply_filterset(RolesReportFilterSet, params, accounts)
    return narrowed.order_by("last_name", "first_name", "email")


def role_rows(roles: tuple[str, ...], accounts: list[MemberRow]) -> Iterator[RoleRow]:
    """One row per role in ``roles`` held by each of ``accounts``, role by role.

    The rows run through ``roles`` in its order and, within one role, through
    ``accounts`` in theirs.
    """
    for role in roles:
        for user in accounts:
            if role in user.roles:
                profile: MemberProfile | None = getattr(user, "profile", None)
                yield RoleRow(
                    role=role,
                    role_label=STAFF_ROLE_LABELS[role],
                    user=user,
                    profile=profile,
                    membership=membership_payload(user),
                )


def roles_report_query(params: Params) -> ReportQuery[RoleRow]:
    """The roles report's rows and sections for ``params``.

    Every staff role is a section, in privilege order, unless ``role`` names one, and
    then that one alone is.  The applied filters are those of
    :data:`EXPORT_FILTER_PARAMS` given a value.
    """
    accounts = list(role_holders(params))
    role = params.get("role", "")
    roles = (role,) if role != "" else STAFF_ROLE_SLUGS
    return ReportQuery(
        rows=role_rows(roles, accounts),
        filters=given_params(params, EXPORT_FILTER_PARAMS),
        sections=[STAFF_ROLE_LABELS[slug] for slug in roles],
    )


#: The roles report: who holds each staff role, for user and account administrators.
ROLES_REPORT: ReportSpec[RoleRow] = ReportSpec(
    slug="roles",
    title="CalDART roles report",
    filename_stem="caldart-roles",
    columns=ROLES_REPORT_COLUMNS,
    roles=(USER_ADMIN, ACCOUNT_ADMIN),
    query=roles_report_query,
    landscape=True,
    choosable=True,
    section=lambda row: row.role_label,
    empty_section=EMPTY_SECTION,
)
