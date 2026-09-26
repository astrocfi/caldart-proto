"""The membership report.

One row per member, one column list shared by the CSV and the PDF so the two
exports can never drift apart.  The house style -- landscape letter PDF with
zebra rows, a repeated header and page numbers -- lives in ``caldart.reports``;
this module only decides *what* goes in the table and which members it lists.

Adding a column means adding one entry to :data:`MEMBER_REPORT_COLUMNS`; the
CSV header, the PDF header and both row builders follow from it, and so does
the list ``GET /reports/members/columns`` answers with.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date
from typing import TYPE_CHECKING, TypedDict

from django.utils import timezone

from apps.accounts.models import AccountKind
from apps.accounts.roles import ACCOUNT_ADMIN, DART_LEADER
from apps.members.filters import (
    MemberAdminFilterSet,
    MemberOrderingFilter,
    applied_filters,
    member_admin_queryset,
)
from apps.members.models import MemberProfile, PilotCertificateType
from apps.members.services import MembershipStatusDict, membership_payload
from caldart.reports import Params, ReportColumn, ReportQuery, ReportSpec, apply_filterset

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from apps.members.services import MemberRow


class RowContext(TypedDict):
    """One member, gathered once so every column reads it without a query."""

    user: MemberRow
    profile: MemberProfile | None
    dart: str
    membership: MembershipStatusDict
    aircraft: list[str]
    joined_on: date | None


#: Every column the membership report can carry, in export order.  ``key`` is
#: what ``?columns=`` names and what ``GET /reports/members/columns`` answers
#: with, ``label`` is the header both exports print, ``default`` says whether
#: the column appears when the caller chooses none, and ``width`` is the share
#: of the page the PDF gives it.  The ones that are off by default -- the plan,
#: the certificate number, the instrument rating, the town, the state, the county,
#: the two joining dates and the profile's last update -- are there for a roster
#: or an audit rather than for the everyday report, which is sized so no default
#: cell has to wrap.
#:
#: A lifetime membership has no expiry date, so ``expires_on`` is blank for one;
#: the ``plan`` column ("Life") and ``status`` ("Current") say what it is.  The
#: ``status`` cell is the :class:`~apps.members.models.MembershipState` label,
#: never the slug, and the ``certificate`` cell abbreviates the airline
#: transport pilot certificate to "ATP" through :data:`REPORT_CERTIFICATE_LABELS`,
#: which keeps that column narrow.  The status is Current, Expired, or
#: Friend: a donor is never in the report.  ``kind`` is the effective kind's
#: label, Member or Friend, so a member whose change to friend has come, or
#: who chose to be a member and has not yet paid, reads Friend.  The eleven
#: default widths are balanced so that no seeded cell or heading wraps
#: (``test_no_default_member_cell_wraps_in_the_pdf``).
#: ``joined_on``
#: is the start of the earliest term on file, and ``member_since`` the day the
#: member says they joined -- the same date until the terms before a gap, or
#: before an import, are missing.
MEMBER_REPORT_COLUMNS: tuple[ReportColumn[RowContext], ...] = (
    ReportColumn("name", "Name", True, lambda ctx: ctx["user"].display_name, width=2.55),
    ReportColumn("email", "Email", True, lambda ctx: ctx["user"].email, width=4.4),
    ReportColumn(
        "phone",
        "Phone",
        True,
        lambda ctx: ctx["profile"].phone if ctx["profile"] else "",
        width=1.9,
    ),
    ReportColumn("dart", "DART", True, lambda ctx: ctx["dart"], width=3.4),
    ReportColumn(
        "status", "Status", True, lambda ctx: ctx["membership"]["status"].label, width=2.1
    ),
    ReportColumn(
        "kind", "Kind", True, lambda ctx: AccountKind(ctx["user"].effective_kind).label, width=1.2
    ),
    ReportColumn("plan", "Plan", False, lambda ctx: ctx["membership"]["plan"] or "", width=2.0),
    ReportColumn(
        "expires_on", "Expires", True, lambda ctx: _iso(ctx["membership"]["expires_on"]), width=1.6
    ),
    ReportColumn(
        "certificate",
        "Certificate",
        True,
        lambda ctx: _certificate_display(ctx["profile"]),
        width=1.75,
    ),
    ReportColumn(
        "certificate_number",
        "Certificate number",
        False,
        lambda ctx: _value(ctx["profile"], "certificate_number"),
        width=1.6,
    ),
    ReportColumn("ifr", "IFR", False, lambda ctx: _display(ctx["profile"], "ifr_rated"), width=0.8),
    ReportColumn(
        "medical_type",
        "Medical",
        True,
        lambda ctx: _display(ctx["profile"], "medical_type"),
        width=1.8,
    ),
    ReportColumn(
        "medical_expiration",
        "Medical expires",
        True,
        lambda ctx: _iso(_date(ctx["profile"], "medical_expiration")),
        width=2.25,
    ),
    ReportColumn("aircraft", "Aircraft", True, lambda ctx: " ".join(ctx["aircraft"]), width=2.35),
    ReportColumn("city", "City", False, lambda ctx: _value(ctx["profile"], "city"), width=1.6),
    ReportColumn("state", "State", False, lambda ctx: _value(ctx["profile"], "state"), width=0.8),
    ReportColumn(
        "county", "County", False, lambda ctx: _value(ctx["profile"], "county"), width=1.8
    ),
    ReportColumn("joined_on", "Joined", False, lambda ctx: _iso(ctx["joined_on"]), width=1.6),
    ReportColumn(
        "member_since",
        "Member since",
        False,
        lambda ctx: _iso(_date(ctx["profile"], "member_since")),
        width=1.8,
    ),
    ReportColumn(
        "profile_updated",
        "Profile updated",
        False,
        lambda ctx: _profile_updated(ctx["profile"]),
        width=1.8,
    ),
)

REPORT_TITLE = "CalDART membership report"


def _iso(value: date | None) -> str:
    """The date as ``YYYY-MM-DD``, or a blank cell when there is none."""
    return value.isoformat() if value else ""


def _value(profile: MemberProfile | None, field: str) -> str:
    """The text in ``field``, or a blank cell when the member has no profile."""
    text: str = getattr(profile, field, "") if profile is not None else ""
    return text


def _date(profile: MemberProfile | None, field: str) -> date | None:
    """The date in ``field``, or ``None`` when it is unset or there is no profile."""
    value: date | None = getattr(profile, field, None) if profile is not None else None
    return value


def _profile_updated(profile: MemberProfile | None) -> str:
    """``profile.profile_updated_at`` as a local calendar date, or a blank cell.

    Blank when the member has no profile, or the profile has never been edited.
    """
    if profile is None or profile.profile_updated_at is None:
        return ""
    return timezone.localdate(profile.profile_updated_at).isoformat()


#: Choice values that mean "nothing on file"; they read better as a blank cell
#: than as the word "None" in a spreadsheet.
_EMPTY_CHOICES = frozenset({"none", "na"})


def _display(profile: MemberProfile | None, field: str) -> str:
    """The human label behind a ``choices`` field, e.g. ``private`` -> Private.

    A member without a profile, and one whose answer means "nothing on file",
    both read as a blank cell.
    """
    if profile is None or getattr(profile, field, "") in _EMPTY_CHOICES:
        return ""
    label: str = getattr(profile, f"get_{field}_display")()
    return label


#: A report-only override of a certificate's on-screen label, keyed by the
#: choice's value.  The certificate column is narrow, so the report abbreviates
#: what would otherwise wrap; the profile screens keep spelling the certificate
#: out.
REPORT_CERTIFICATE_LABELS: dict[str, str] = {
    PilotCertificateType.ATP: "ATP",
}


def _certificate_display(profile: MemberProfile | None) -> str:
    """The certificate column's cell: the report's abbreviation, or the choice's label.

    A member without a profile, and one who holds no certificate, both read as
    a blank cell, exactly as :func:`_display` would show them.
    """
    if profile is None or profile.pilot_certificate_type in _EMPTY_CHOICES:
        return ""
    if profile.pilot_certificate_type in REPORT_CERTIFICATE_LABELS:
        return REPORT_CERTIFICATE_LABELS[profile.pilot_certificate_type]
    return _display(profile, "pilot_certificate_type")


def _row_context(user: MemberRow) -> RowContext:
    """Everything the columns read for one member, fetched once.

    An account with no profile row still yields a context: the profile is
    ``None``, and every column that reads it is blank.
    """
    profile: MemberProfile | None = getattr(user, "profile", None)
    return {
        "user": user,
        "profile": profile,
        "dart": profile.dart.name if profile is not None and profile.dart is not None else "",
        "membership": membership_payload(user),
        "aircraft": (
            [aircraft.n_number for aircraft in profile.aircraft.all()]
            if profile is not None
            else []
        ),
        "joined_on": getattr(user, "joined_on", None),
    }


def member_rows(users: Iterator[MemberRow]) -> Iterator[RowContext]:
    """One :class:`RowContext` per user, lazily, in the order ``users`` arrives in."""
    for user in users:
        yield _row_context(user)


def member_report_queryset(params: Params) -> QuerySet[MemberRow]:
    """The accounts the member report lists for ``params``, unordered.

    ``params`` narrow the list's own queryset through ``MemberAdminFilterSet``, and a
    deactivated account is left out whatever ``include_inactive`` says; donors are
    never there, since the list leaves them out.  A filter the set refuses raises
    DRF's ``ValidationError`` keyed by that filter.  A DART roster counts its members
    through this same queryset, so the count its email states matches its rows.
    """
    return apply_filterset(MemberAdminFilterSet, params, member_admin_queryset()).filter(
        is_active=True
    )


def member_report_query(params: Params) -> ReportQuery[RowContext]:
    """The members the member list shows for ``params``, in the list's order.

    ``params`` are the list's own query parameters: the filters of
    ``MemberAdminFilterSet`` and ``ordering``, which ``MemberOrderingFilter`` reads the
    same way the list does.  The report never lists a deactivated account, whatever
    ``include_inactive`` says, and never a donor.  A filter the set refuses raises
    DRF's ``ValidationError`` keyed by that filter.  The rows are read from the
    database a chunk at a time, and the applied filters are the ones
    :func:`apps.members.filters.applied_filters` names.
    """
    ordered = MemberOrderingFilter.order_queryset(
        member_report_queryset(params), params.get("ordering", "")
    )
    return ReportQuery(
        rows=member_rows(ordered.iterator(chunk_size=200)),
        filters=applied_filters(params),
    )


#: The membership report: every member the member list shows, for DART leaders and
#: account administrators.
MEMBER_REPORT: ReportSpec[RowContext] = ReportSpec(
    slug="members",
    title=REPORT_TITLE,
    filename_stem="caldart-members",
    columns=MEMBER_REPORT_COLUMNS,
    roles=(DART_LEADER, ACCOUNT_ADMIN),
    query=member_report_query,
)
