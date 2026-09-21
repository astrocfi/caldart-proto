"""The membership report.

One row per member, one column list shared by the CSV and the PDF so the two
exports can never drift apart.  The house style — streaming CSV, landscape
letter PDF with zebra rows, a repeated header and page numbers — lives in
``caldart.reports``; this module only decides *what* goes in the table.

Adding a column means adding one entry to :data:`MEMBER_REPORT_COLUMNS`; the
CSV header, the PDF header and both row builders follow from it.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from datetime import date
from typing import TYPE_CHECKING, TypedDict

from django.utils import timezone

from apps.members.models import MemberProfile
from apps.members.services import MembershipStatusDict, membership_payload

if TYPE_CHECKING:
    from apps.members.services import MemberRow


class RowContext(TypedDict):
    """One member, gathered once so every column reads it without a query."""

    user: MemberRow
    profile: MemberProfile | None
    dart: str
    membership: MembershipStatusDict
    aircraft: list[str]
    joined_on: date | None


#: Header text and the value function for every column, in export order.
#: A lifetime membership has no expiry date, so ``expires_on`` is blank for one;
#: the ``plan`` column ("Life") and ``status`` ("current") say what it is.
MEMBER_REPORT_COLUMNS: tuple[tuple[str, Callable[[RowContext], str]], ...] = (
    ("name", lambda ctx: ctx["user"].display_name),
    ("email", lambda ctx: ctx["user"].email),
    ("phone", lambda ctx: ctx["profile"].phone if ctx["profile"] else ""),
    ("dart", lambda ctx: ctx["dart"]),
    ("status", lambda ctx: ctx["membership"]["status"]),
    ("plan", lambda ctx: ctx["membership"]["plan"] or ""),
    ("expires_on", lambda ctx: _iso(ctx["membership"]["expires_on"])),
    ("certificate", lambda ctx: _display(ctx["profile"], "pilot_certificate_type")),
    ("certificate_number", lambda ctx: _value(ctx["profile"], "certificate_number")),
    ("ifr", lambda ctx: _display(ctx["profile"], "ifr_rated")),
    ("medical_type", lambda ctx: _display(ctx["profile"], "medical_type")),
    ("medical_expiration", lambda ctx: _iso(_date(ctx["profile"], "medical_expiration"))),
    ("aircraft", lambda ctx: " ".join(ctx["aircraft"])),
    ("city", lambda ctx: _value(ctx["profile"], "city")),
    ("state", lambda ctx: _value(ctx["profile"], "state")),
    ("joined_on", lambda ctx: _iso(ctx["joined_on"])),
)

#: Column headers, for both exports.
MEMBER_REPORT_HEADER: tuple[str, ...] = tuple(name for name, _ in MEMBER_REPORT_COLUMNS)

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


def member_report_rows(users: Iterable[MemberRow]) -> Iterator[list[str]]:
    """Yield one report row per user, lazily, in the queryset's order.

    Each row holds the columns of :data:`MEMBER_REPORT_COLUMNS`, in that order,
    every cell already text.  ``users`` must come from
    ``admin_filters.member_admin_queryset`` so the membership annotations are
    present.
    """
    for user in users:
        context = _row_context(user)
        yield [value(context) for _, value in MEMBER_REPORT_COLUMNS]


def member_report_filename(extension: str, on_date: date | None = None) -> str:
    """The download name for the report, e.g. ``caldart-members-2026-09-04.csv``.

    ``on_date`` defaults to the current local date, and ``extension`` is added
    as given.
    """
    on_date = on_date or timezone.localdate()
    return f"caldart-members-{on_date.isoformat()}.{extension}"


__all__ = [
    "MEMBER_REPORT_COLUMNS",
    "MEMBER_REPORT_HEADER",
    "REPORT_TITLE",
    "member_report_filename",
    "member_report_rows",
]
