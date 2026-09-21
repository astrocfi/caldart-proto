"""The aircraft register as CSV and PDF.

The columns: n_number, make, model, owner, owner_type, insurance carrier,
liability limits, hull, expiration, current?, pilots.  Both formats render from
the same rows so the two downloads can never disagree.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any

from django.db.models import QuerySet

from apps.aircraft.models import Aircraft
from apps.aircraft.services import pilot_names

HEADER: tuple[str, ...] = (
    "n_number",
    "make",
    "model",
    "owner",
    "owner_type",
    "insurance_carrier",
    "liability_per_occurrence",
    "liability_per_person",
    "hull",
    "insurance_expiration",
    "insurance_current",
    "pilots",
)

#: Human column titles for the PDF, which is read rather than parsed.
PDF_HEADER: tuple[str, ...] = (
    "N-number",
    "Make",
    "Model",
    "Owner",
    "Owner type",
    "Carrier",
    "Liability / occurrence",
    "Liability / person",
    "Hull",
    "Expires",
    "Current",
    "Pilots",
)


def _dollars(cents: int | None, *, currency: bool) -> str:
    """Cents as dollars: ``$1,000,000`` for people, ``1000000.00`` for sheets."""
    if cents is None:
        return ""
    if currency:
        return f"${cents / 100:,.0f}" if cents % 100 == 0 else f"${cents / 100:,.2f}"
    return f"{cents / 100:.2f}"


def export_queryset(queryset: QuerySet[Aircraft] | None = None) -> QuerySet[Aircraft]:
    """The queryset the exports read, with the pilot join prefetched."""
    base = Aircraft.objects.all() if queryset is None else queryset
    return base.prefetch_related("pilots__user")


def aircraft_row(aircraft: Aircraft, *, currency: bool = False) -> list[Any]:
    """Return one report row for ``aircraft``, in the order of ``HEADER``."""
    return [
        aircraft.n_number,
        aircraft.make,
        aircraft.model,
        aircraft.owner_name,
        aircraft.get_owner_type_display(),
        aircraft.insurance_carrier,
        _dollars(aircraft.insurance_liability_per_occurrence_cents, currency=currency),
        _dollars(aircraft.insurance_liability_per_person_cents, currency=currency),
        _dollars(aircraft.insurance_hull_cents, currency=currency),
        aircraft.insurance_expiration.isoformat() if aircraft.insurance_expiration else "",
        "yes" if aircraft.insurance_is_current else "no",
        "; ".join(pilot_names(aircraft)),
    ]


def aircraft_rows(queryset: Iterable[Aircraft], *, currency: bool = False) -> Iterator[list[Any]]:
    """Stream the report rows, so a CSV never materializes the whole register."""
    for aircraft in queryset:
        yield aircraft_row(aircraft, currency=currency)
