"""The aircraft register as CSV and PDF.

One column registry serves both downloads and the chooser on the register
screen, so the two formats can never disagree about what a row holds.  The
house style -- landscape letter PDF, a repeated header and page numbers -- lives
in ``caldart.reports``; this module only decides what goes in the table and which
aircraft it lists.

Money is the one cell the two formats render differently: a PDF is read, so it
carries ``$1,000,000``, while a CSV is added up, so it carries ``1000000.00``.
The insured amounts are :class:`~caldart.reports.Money` cells, which the engine
renders for each format.
"""

from __future__ import annotations

from apps.accounts.roles import ACCOUNT_ADMIN
from apps.aircraft.filters import AircraftFilter, order_register
from apps.aircraft.models import Aircraft
from apps.aircraft.services import pilot_names
from caldart.reports import (
    Money,
    Params,
    ReportColumn,
    ReportQuery,
    ReportSpec,
    apply_filterset,
    given_params,
)

#: The register filters the PDF subtitle names, in order, when they carry a value.
EXPORT_FILTER_PARAMS: tuple[str, ...] = (
    "search",
    "make",
    "owner_type",
    "insurance",
    "expiring_within",
    "is_active",
    "ordering",
)


def _money(aircraft: Aircraft, field: str) -> Money | None:
    """The insured amount in ``field``, round figures without their cents in a PDF.

    An amount that is not on file at all is a blank cell in either format.
    """
    cents: int | None = getattr(aircraft, field)
    return None if cents is None else Money(cents, drop_zero_cents=True)


#: Every column the register exports can carry, in export order.  ``key`` is
#: what ``?columns=`` names and what ``GET /reports/aircraft/columns`` answers
#: with, ``label`` is the header both exports print, ``default`` says whether
#: the column appears when the caller chooses none, and ``width`` is the share
#: of the page the PDF gives it.  The three that are off by default -- the
#: owner's kind, the per-person liability limit and the pilots who fly the plane
#: -- are there for an insurance review or a roster rather than for the everyday
#: register, which is sized so no default cell has to wrap; the pilot list is as
#: long as the number of members who fly the aircraft, so it is asked for rather
#: than assumed.
AIRCRAFT_REPORT_COLUMNS: tuple[ReportColumn[Aircraft], ...] = (
    ReportColumn("n_number", "N-number", True, lambda row: row.n_number, width=2.0),
    ReportColumn("make", "Make", True, lambda row: row.make, width=2.2),
    ReportColumn("model", "Model", True, lambda row: row.model, width=4.2),
    ReportColumn("owner_name", "Owner", True, lambda row: row.owner_name, width=6.8),
    ReportColumn(
        "owner_type",
        "Owner type",
        False,
        lambda row: row.get_owner_type_display(),
        width=2.0,
    ),
    ReportColumn(
        "insurance_carrier",
        "Carrier",
        True,
        lambda row: row.insurance_carrier,
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
        lambda row: row.insurance_expiration.isoformat() if row.insurance_expiration else "",
        width=2.1,
    ),
    ReportColumn(
        "insurance_current",
        "Current",
        True,
        lambda row: "yes" if row.insurance_is_current else "no",
        width=1.4,
    ),
    ReportColumn(
        "pilots",
        "Pilots",
        False,
        lambda row: "; ".join(pilot_names(row)),
        width=6.0,
    ),
)

REPORT_TITLE = "CalDART aircraft register"


def aircraft_report_query(params: Params) -> ReportQuery[Aircraft]:
    """The aircraft the register shows for ``params``, in the register's order.

    ``params`` are the register's own query parameters: the filters of
    ``AircraftFilter`` and ``ordering``, which ``order_register`` reads the way the
    list does.  A filter the set refuses raises DRF's
    ``ValidationError`` keyed by that filter.  The pilots are fetched with the rows, a
    chunk at a time, and the applied filters are those of :data:`EXPORT_FILTER_PARAMS`
    given a value.
    """
    narrowed = apply_filterset(AircraftFilter, params, Aircraft.objects.all())
    ordered = order_register(narrowed, params.get("ordering", "")).prefetch_related("pilots__user")
    return ReportQuery(
        rows=ordered.iterator(chunk_size=200),
        filters=given_params(params, EXPORT_FILTER_PARAMS),
    )


#: The aircraft register, for account administrators.
AIRCRAFT_REPORT: ReportSpec[Aircraft] = ReportSpec(
    slug="aircraft",
    title=REPORT_TITLE,
    filename_stem="caldart-aircraft",
    columns=AIRCRAFT_REPORT_COLUMNS,
    roles=(ACCOUNT_ADMIN,),
    query=aircraft_report_query,
)
