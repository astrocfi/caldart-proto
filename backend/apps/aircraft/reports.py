"""The aircraft register as CSV and PDF.

One column registry serves both downloads and the chooser on the register
screen, so the two formats can never disagree about what a row holds.  The
house style -- streaming CSV, landscape letter PDF, a repeated header and page
numbers -- lives in ``caldart.reports``; this module only decides what goes in
the table.

Money is the one cell the two formats render differently: a PDF is read, so it
carries ``$1,000,000``, while a CSV is added up, so it carries ``1000000.00``.
:class:`AircraftRow` pairs each aircraft with the form its export wants.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass

from django.db.models import QuerySet

from apps.aircraft.models import Aircraft
from apps.aircraft.services import pilot_names
from caldart.reports import ReportColumn


@dataclass(frozen=True)
class AircraftRow:
    """One aircraft, with the money format the export that asked for it wants.

    ``currency`` true renders an insured amount as dollars for a reader,
    ``$1,000,000``; false renders it as the plain number a spreadsheet sums,
    ``1000000.00``.
    """

    aircraft: Aircraft
    currency: bool


def _dollars(cents: int | None, *, currency: bool) -> str:
    """Cents as dollars: ``$1,000,000`` for people, ``1000000.00`` for sheets.

    An amount that is not on file at all is a blank cell in either form, and a
    reader's form keeps the cents only when there are cents to keep.
    """
    if cents is None:
        return ""
    if currency:
        return f"${cents / 100:,.0f}" if cents % 100 == 0 else f"${cents / 100:,.2f}"
    return f"{cents / 100:.2f}"


def _money(row: AircraftRow, field: str) -> str:
    """The insured amount in ``field``, in this export's money format."""
    cents: int | None = getattr(row.aircraft, field)
    return _dollars(cents, currency=row.currency)


#: Every column the register exports can carry, in export order.  ``key`` is
#: what ``?columns=`` names and what ``GET /admin/aircraft/columns`` answers
#: with, ``label`` is the header both exports print, ``default`` says whether
#: the column appears when the caller chooses none, and ``width`` is the share
#: of the page the PDF gives it.  The three that are off by default -- the
#: owner's kind, the per-person liability limit and the pilots who fly the plane
#: -- are there for an insurance review or a roster rather than for the everyday
#: register, which is sized so no default cell has to wrap; the pilot list is as
#: long as the number of members who fly the aircraft, so it is asked for rather
#: than assumed.
AIRCRAFT_REPORT_COLUMNS: tuple[ReportColumn[AircraftRow], ...] = (
    ReportColumn("n_number", "N-number", True, lambda row: row.aircraft.n_number, width=2.0),
    ReportColumn("make", "Make", True, lambda row: row.aircraft.make, width=2.2),
    ReportColumn("model", "Model", True, lambda row: row.aircraft.model, width=4.2),
    ReportColumn("owner_name", "Owner", True, lambda row: row.aircraft.owner_name, width=6.8),
    ReportColumn(
        "owner_type",
        "Owner type",
        False,
        lambda row: row.aircraft.get_owner_type_display(),
        width=2.0,
    ),
    ReportColumn(
        "insurance_carrier",
        "Carrier",
        True,
        lambda row: row.aircraft.insurance_carrier,
        width=4.8,
    ),
    ReportColumn(
        "liability_per_occurrence",
        "Liability / occurrence",
        True,
        lambda row: _money(row, "insurance_liability_per_occurrence_cents"),
        width=3.3,
    ),
    ReportColumn(
        "liability_per_person",
        "Liability / person",
        False,
        lambda row: _money(row, "insurance_liability_per_person_cents"),
        width=3.0,
    ),
    ReportColumn("hull", "Hull", True, lambda row: _money(row, "insurance_hull_cents"), width=2.0),
    ReportColumn(
        "insurance_expiration",
        "Expires",
        True,
        lambda row: (
            row.aircraft.insurance_expiration.isoformat()
            if row.aircraft.insurance_expiration
            else ""
        ),
        width=2.1,
    ),
    ReportColumn(
        "insurance_current",
        "Current",
        True,
        lambda row: "yes" if row.aircraft.insurance_is_current else "no",
        width=1.4,
    ),
    ReportColumn(
        "pilots",
        "Pilots",
        False,
        lambda row: "; ".join(pilot_names(row.aircraft)),
        width=6.0,
    ),
)

REPORT_TITLE = "CalDART aircraft register"


def export_queryset(queryset: QuerySet[Aircraft] | None = None) -> QuerySet[Aircraft]:
    """The queryset the exports read, with the pilot join prefetched."""
    base = Aircraft.objects.all() if queryset is None else queryset
    return base.prefetch_related("pilots__user")


def aircraft_rows(
    queryset: Iterable[Aircraft],
    columns: Sequence[ReportColumn[AircraftRow]],
    *,
    currency: bool = False,
) -> Iterator[list[str]]:
    """Stream the report rows, so a CSV never materializes the whole register.

    Each row holds ``columns`` in the order given, every cell already text, with
    insured amounts rendered for a reader when ``currency`` is set and as plain
    numbers otherwise.
    """
    for aircraft in queryset:
        row = AircraftRow(aircraft=aircraft, currency=currency)
        yield [str(column.value(row)) for column in columns]
