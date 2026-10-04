"""The CalDART verification report: which items a verifier has checked, and which not.

Four sections, in this order: *Pilot certificates*, *Medicals*, and *Photo IDs*, one row
per checkable person with a profile who holds that item, and *Aircraft insurance*, one
row per aircraft in service with a policy on file.  An item nobody holds (a non-pilot's
certificate, a medical of *None*, a photo ID of *Not provided*, insurance with no
expiration) has nothing to verify and is never listed.  Each row names the item's holder,
what is on file, and when the record was last written; the Section column and the three
verification columns (whether, by whom, and on which day) are there to choose, and off
by default, since the section heads its rows and the default list is of items nobody
has verified.  The
house style lives in ``caldart.reports``; this module decides which rows the report
holds, how its two filters narrow them, and what each cell prints.  It lives in the
aircraft app, which sits above the members app and already decides who the leader's
member check can find, because it lists both people and aircraft.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import date, datetime

from django.db.models import Q, QuerySet
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.accounts.models import User
from apps.accounts.roles import VERIFY_ROLES
from apps.aircraft.models import Aircraft
from apps.aircraft.services import checkable_people
from apps.darts.models import Dart
from apps.members.models import MedicalType, MemberProfile, PhotoIdType, PilotCertificateType
from apps.members.verification import is_held
from caldart.dates import format_display_date
from caldart.reports import Params, ReportColumn, ReportQuery, ReportSpec

#: The section each person's item is listed under, keyed by the item's slug.
PERSON_SECTIONS: dict[str, str] = {
    "certificate": "Pilot certificates",
    "medical": "Medicals",
    "photo_id": "Photo IDs",
}

#: The section every aircraft's insurance is listed under.
INSURANCE_SECTION = "Aircraft insurance"

#: Every section, in the order the report draws them.
SECTIONS: tuple[str, ...] = (*PERSON_SECTIONS.values(), INSURANCE_SECTION)

#: The line the PDF draws under a section with no rows.
EMPTY_SECTION = "Nothing to show."

#: ``?status=`` for the items not yet verified, the default.
UNVERIFIED = "unverified"

#: ``?status=`` for the verified items.
VERIFIED = "verified"

#: ``?status=`` for every item.
ALL = "all"

#: The values ``?status=`` accepts.
STATUSES: tuple[str, ...] = (UNVERIFIED, VERIFIED, ALL)

#: Each status in the words the PDF subtitle prints after ``Showing:``.
STATUS_WORDS: dict[str, str] = {
    UNVERIFIED: "Not yet verified",
    VERIFIED: "Verified",
    ALL: "Everything",
}

#: What joins the parts of a Details cell.
DETAIL_SEPARATOR = " \u00b7 "


@dataclass(frozen=True)
class VerificationRow:
    """One item of one person or one aircraft, with everything the columns read.

    ``section`` is the title of the section the row is drawn in.  ``name`` is the
    person's display name or the aircraft's N-number; ``dart`` the person's DART or the
    aircraft's owner; ``details`` what is on file for the item.  ``updated_at`` is when
    the record was last written (``None`` for a profile nobody has written), and
    ``verified_at`` and ``verified_by`` are the item's stamp, both ``None`` while it is
    unverified; ``verified_by`` is also ``None`` when the verifier's account is gone.
    """

    section: str
    name: str
    dart: str
    details: str
    updated_at: datetime | None
    verified_at: datetime | None
    verified_by: User | None

    @property
    def is_verified(self) -> bool:
        """True when the item carries a verification stamp."""
        return self.verified_at is not None


def _local_day(moment: datetime | None) -> str:
    """The local day of ``moment`` as ``MM/DD/YYYY``, or a blank cell for ``None``."""
    if moment is None:
        return ""
    return format_display_date(timezone.localdate(moment))


def _details(*parts: str) -> str:
    """The non-blank ``parts`` joined with :data:`DETAIL_SEPARATOR`."""
    return DETAIL_SEPARATOR.join(part for part in parts if part != "")


def _expires(day: date | None) -> str:
    """``expires MM/DD/YYYY``, or blank when no expiration is on file."""
    return "" if day is None else f"expires {format_display_date(day)}"


def certificate_details(profile: MemberProfile) -> str:
    """The certificate's type and number joined by a middle dot, or the type alone."""
    label = PilotCertificateType(profile.pilot_certificate_type).label
    return _details(label, profile.certificate_number)


def medical_details(profile: MemberProfile) -> str:
    """The medical and ``expires 03/01/2027``, joined by a middle dot.

    A medical with no expiration on file, such as ``None``, reads its type alone.
    """
    label = MedicalType(profile.medical_type).label
    return _details(label, _expires(profile.medical_expiration))


def photo_id_details(profile: MemberProfile) -> str:
    """The kind of photo ID, the one thing recorded about it: ``Passport``."""
    return PhotoIdType(profile.photo_id_type).label


def insurance_details(aircraft: Aircraft) -> str:
    """The carrier and ``expires 03/01/2027``, joined by a middle dot, or blank."""
    return _details(aircraft.insurance_carrier, _expires(aircraft.insurance_expiration))


#: Each person's item: its slug and how its Details cell reads the profile.
PERSON_DETAILS: tuple[tuple[str, Callable[[MemberProfile], str]], ...] = (
    ("certificate", certificate_details),
    ("medical", medical_details),
    ("photo_id", photo_id_details),
)


def _verified_by_name(row: VerificationRow) -> str:
    """The verifier's display name, or a blank cell when there is none."""
    return "" if row.verified_by is None else row.verified_by.display_name


#: Every column the report can carry, in export order.  Section and the three
#: verification columns are off by default.
VERIFICATION_REPORT_COLUMNS: tuple[ReportColumn[VerificationRow], ...] = (
    ReportColumn("section", "Section", False, lambda row: row.section, width=2.3),
    ReportColumn("name", "Name", True, lambda row: row.name, width=2.6),
    ReportColumn("dart", "DART", True, lambda row: row.dart, width=3.0),
    ReportColumn("details", "Details", True, lambda row: row.details, width=4.2),
    ReportColumn("updated", "Updated", True, lambda row: _local_day(row.updated_at), width=1.4),
    ReportColumn(
        "verified", "Verified", False, lambda row: "Yes" if row.is_verified else "No", width=1.2
    ),
    ReportColumn("verified_by", "Verified by", False, _verified_by_name, width=2.4),
    ReportColumn(
        "verified_on", "Verified on", False, lambda row: _local_day(row.verified_at), width=1.5
    ),
)


def _status(params: Params) -> str:
    """The ``status`` param, :data:`UNVERIFIED` when blank or missing.

    Anything but a value of :data:`STATUSES` raises DRF's ``ValidationError`` keyed by
    ``status``, worded as the other reports word a refused choice.
    """
    status = params.get("status", "") or UNVERIFIED
    if status not in STATUSES:
        raise ValidationError(
            {"status": [f"Select a valid choice. {status} is not one of the available choices."]}
        )
    return status


def _dart_filter(value: str, field: str) -> Q:
    """``Q`` for the DART named by ``value`` through the relation ``field``.

    An all-digit value is the DART's id and anything else a case-insensitive fragment
    of its name, as the membership report reads ``?dart=``.
    """
    if value.isdigit():
        return Q(**{f"{field}_id": int(value)})
    return Q(**{f"{field}__name__icontains": value})


def checkable_profiles(dart: str) -> QuerySet[MemberProfile]:
    """The profiles of every checkable person, narrowed to ``dart`` when it is given.

    Checkable people are active members and friends (see
    ``apps.aircraft.services.checkable_people``); an account without a profile has
    nothing to verify.  The order is last name, first name, then address, and each
    profile arrives with its account, its DART, and its three verifiers fetched.
    """
    profiles = MemberProfile.objects.filter(user__in=checkable_people()).select_related(
        "user", "dart", "certificate_verified_by", "medical_verified_by", "photo_id_verified_by"
    )
    if dart != "":
        profiles = profiles.filter(_dart_filter(dart, "dart"))
    return profiles.order_by("user__last_name", "user__first_name", "user__email")


def insured_aircraft(dart: str) -> QuerySet[Aircraft]:
    """Every aircraft in service with a policy on file, narrowed to ``dart``, by N-number.

    A policy on file is an insurance expiration; without one there is nothing to verify.
    An aircraft belongs to a DART through its pilots: ``dart`` keeps the aircraft that
    some pilot on that DART flies, each once however many of them fly it.
    """
    aircraft = Aircraft.objects.filter(
        is_active=True, insurance_expiration__isnull=False
    ).select_related("insurance_verified_by")
    if dart != "":
        flown = Aircraft.objects.filter(_dart_filter(dart, "pilots__dart")).values("pk")
        aircraft = aircraft.filter(pk__in=flown)
    return aircraft.order_by("n_number")


def person_rows(profiles: list[MemberProfile]) -> Iterator[VerificationRow]:
    """One row per item each of ``profiles`` holds, item by item in section order."""
    for slug, details in PERSON_DETAILS:
        for profile in profiles:
            if not is_held(profile, slug):
                continue
            yield VerificationRow(
                section=PERSON_SECTIONS[slug],
                name=profile.user.display_name,
                dart="" if profile.dart is None else profile.dart.name,
                details=details(profile),
                updated_at=profile.profile_updated_at,
                verified_at=getattr(profile, f"{slug}_verified_at"),
                verified_by=getattr(profile, f"{slug}_verified_by"),
            )


def insurance_rows(aircraft: QuerySet[Aircraft]) -> Iterator[VerificationRow]:
    """One row per aircraft's insurance, the owner's name in the DART column."""
    for plane in aircraft:
        yield VerificationRow(
            section=INSURANCE_SECTION,
            name=plane.n_number,
            dart=plane.owner_name,
            details=insurance_details(plane),
            updated_at=plane.updated_at,
            verified_at=plane.insurance_verified_at,
            verified_by=plane.insurance_verified_by,
        )


def _wanted(row: VerificationRow, status: str) -> bool:
    """Whether ``row`` is listed for ``status``."""
    if status == ALL:
        return True
    return row.is_verified is (status == VERIFIED)


def _dart_words(value: str) -> str:
    """How the PDF subtitle names the ``dart`` filter: a DART's name for its id.

    A fragment of a name, or an id no DART has, is printed as it was given.
    """
    if value.isdigit():
        found = Dart.objects.filter(pk=int(value)).values_list("name", flat=True).first()
        if found is not None:
            return found
    return value


def verification_report_query(params: Params) -> ReportQuery[VerificationRow]:
    """The report's rows and sections for ``params``.

    ``status`` is ``unverified`` (the default), ``verified``, or ``all``, and keeps the
    items in that state; any other value raises DRF's ``ValidationError`` keyed by
    ``status``.  ``dart`` is a DART's id or part of its name, and keeps that DART's
    people and the aircraft its pilots fly.  The rows come section by section in
    :data:`SECTIONS` order, every section is listed even when no row falls in it, and
    the applied filters, as the PDF subtitle prints them, are ``Showing`` with the
    status in words (always, since it has a default; see :data:`STATUS_WORDS`) and then
    ``DART`` with the DART's name, or the fragment given, when ``dart`` is.
    """
    status = _status(params)
    dart = params.get("dart", "").strip()
    rows = [
        *person_rows(list(checkable_profiles(dart))),
        *insurance_rows(insured_aircraft(dart)),
    ]
    filters = {"Showing": STATUS_WORDS[status]}
    if dart != "":
        filters["DART"] = _dart_words(dart)
    return ReportQuery(
        rows=[row for row in rows if _wanted(row, status)],
        filters=filters,
        sections=list(SECTIONS),
    )


#: The verification report: every item a verifier has, or has yet, to check.
VERIFICATION_REPORT: ReportSpec[VerificationRow] = ReportSpec(
    slug="verification",
    title="CalDART verification report",
    filename_stem="caldart-verification",
    columns=VERIFICATION_REPORT_COLUMNS,
    roles=VERIFY_ROLES,
    query=verification_report_query,
    landscape=True,
    choosable=True,
    section=lambda row: row.section,
    empty_section=EMPTY_SECTION,
)
