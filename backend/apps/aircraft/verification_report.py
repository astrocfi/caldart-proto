"""The CalDART verification report: which items a verifier has checked, and which not.

Two sections, in this order: *People*, one row per checkable person with a profile who
holds at least one of a photo ID, a pilot certificate, and a medical, and *Aircraft
insurance*, one row per aircraft in service with a policy on file.  An item nobody holds
(a non-pilot's certificate, a medical of *None*, a photo ID of *Not provided*, insurance
with no expiration) has nothing to verify, and a person who holds none of the three, like
an aircraft with no policy, is never listed.  A person's row has a check column for each
item, Photo ID, Certificate, and Medical in that order, each reading *Verified*, *Not
verified*, or *Not provided* for an item the person does not hold.  Then what is on file,
the medical's expiry (the policy's for an aircraft) in a column of its own, and when the
record last changed.  The PDF draws each section under its own header: People under
Name, DART, the three checks, Details, Expires, and Updated, and Aircraft insurance
under N-number, Owner, Carrier, Expires, and Updated, with no check columns.  The CSV is
one table under one header, the union of the two, so an aircraft's row leaves the three
check cells blank and its N-number, owner, and carrier sit under *Name*, *DART or owner*,
and *Details*.  The Section column is a default in the CSV, which has no headings, and
left to the headings in the PDF; the three verification stamp columns (whether, by whom,
and on which day) are there to choose, and off by default, since the default list is of
rows with something nobody has verified.  The house style lives in ``caldart.reports``;
this module decides which rows the report holds, how its two filters narrow them, and
what each cell prints.  It lives in the aircraft app, which sits above the members app
and already decides who the leader's member check can find, because it lists both people
and aircraft.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime

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
from caldart.reports import Params, ReportColumn, ReportQuery, ReportSpec, SectionColumns

#: The section every person is listed under.
PEOPLE_SECTION = "People"

#: The section every aircraft's insurance is listed under.
INSURANCE_SECTION = "Aircraft insurance"

#: Every section, in the order the report draws them.
SECTIONS: tuple[str, ...] = (PEOPLE_SECTION, INSURANCE_SECTION)

#: The line the PDF draws under a section with no rows.
EMPTY_SECTION = "Nothing to show."

#: ``?status=`` for the rows with an item not yet verified, the default.
UNVERIFIED = "unverified"

#: ``?status=`` for the rows whose every item is verified.
VERIFIED = "verified"

#: ``?status=`` for every row.
ALL = "all"

#: The values ``?status=`` accepts.
STATUSES: tuple[str, ...] = (UNVERIFIED, VERIFIED, ALL)

#: Each status in the words the PDF subtitle prints after ``Showing:``.
STATUS_WORDS: dict[str, str] = {
    UNVERIFIED: "Not yet verified",
    VERIFIED: "Verified",
    ALL: "Everything",
}

#: What a check column reads for a verified item.
CHECK_VERIFIED = "Verified"

#: What a check column reads for an item that requires validation.
CHECK_UNVERIFIED = "Not verified"

#: What a person's check column reads for an item the person does not hold.
CHECK_NOT_PROVIDED = "Not provided"

#: What joins the parts of a Details cell.
DETAIL_SEPARATOR = " \u00b7 "

#: The slug of an aircraft's one item, its insurance.
INSURANCE = "insurance"

#: A floor for ordering stamps, which every real stamp follows.
_EPOCH = datetime.min.replace(tzinfo=UTC)


@dataclass(frozen=True)
class ItemCheck:
    """One held item of a row and its verification stamp.

    ``slug`` is ``photo_id``, ``certificate``, ``medical``, or ``insurance``.
    ``verified_at`` and ``verified_by`` are the item's stamp, both ``None`` while it is
    unverified; ``verified_by`` is also ``None`` when the verifier's account is gone.
    """

    slug: str
    verified_at: datetime | None
    verified_by: User | None

    @property
    def is_verified(self) -> bool:
        """True when the item carries a verification stamp."""
        return self.verified_at is not None


@dataclass(frozen=True)
class VerificationRow:
    """One person or one aircraft, with everything the columns read.

    ``section`` is the title of the section the row is drawn in.  ``name`` is the
    person's display name or the aircraft's N-number; ``dart`` the person's DART or the
    aircraft's owner; ``details`` what is on file; ``expires`` the medical's or the
    policy's expiration.  ``updated_at`` is when the record was last changed: the
    profile's last edit, or its creation when nobody has edited it since, and the
    aircraft record's last write.  ``items`` are the row's held items, never empty.
    """

    section: str
    name: str
    dart: str
    details: str
    expires: date | None
    updated_at: datetime | None
    items: tuple[ItemCheck, ...]

    @property
    def is_verified(self) -> bool:
        """True when every held item carries a verification stamp."""
        return all(item.is_verified for item in self.items)

    def check(self, slug: str) -> str:
        """``slug``'s check: *Verified* or *Not verified* when it is held.

        An item the row does not hold reads *Not provided* on a person's row and is blank
        on an aircraft's, whose only item is its insurance.
        """
        for item in self.items:
            if item.slug == slug:
                return CHECK_VERIFIED if item.is_verified else CHECK_UNVERIFIED
        return CHECK_NOT_PROVIDED if self.section == PEOPLE_SECTION else ""

    @property
    def latest(self) -> ItemCheck | None:
        """The row's most recently verified item, or ``None`` when none is verified."""
        verified = [item for item in self.items if item.is_verified]
        return max(verified, key=lambda item: item.verified_at or _EPOCH, default=None)


def _local_day(moment: datetime | None) -> str:
    """The local day of ``moment`` as ``MM/DD/YYYY``, or a blank cell for ``None``."""
    if moment is None:
        return ""
    return format_display_date(timezone.localdate(moment))


def _day(day: date | None) -> str:
    """``day`` as ``MM/DD/YYYY``, or a blank cell for ``None``."""
    return "" if day is None else format_display_date(day)


def _details(*parts: str) -> str:
    """The non-blank ``parts`` joined with :data:`DETAIL_SEPARATOR`."""
    return DETAIL_SEPARATOR.join(part for part in parts if part != "")


def photo_id_details(profile: MemberProfile) -> str:
    """The kind of photo ID, the one thing recorded about it: ``Passport``."""
    return PhotoIdType(profile.photo_id_type).label


def certificate_details(profile: MemberProfile) -> str:
    """The certificate's type and number joined by a middle dot, or the type alone."""
    label = PilotCertificateType(profile.pilot_certificate_type).label
    return _details(label, profile.certificate_number)


def medical_details(profile: MemberProfile) -> str:
    """The medical's class or kind, such as ``Third class``; its expiry has a column."""
    return MedicalType(profile.medical_type).label


#: Each person's item, in check-column order: its slug and how the details read it.
PERSON_ITEMS: tuple[tuple[str, Callable[[MemberProfile], str]], ...] = (
    ("photo_id", photo_id_details),
    ("certificate", certificate_details),
    ("medical", medical_details),
)


def _verified_by_name(row: VerificationRow) -> str:
    """The latest verifier's display name, or a blank cell when there is none."""
    latest = row.latest
    return "" if latest is None or latest.verified_by is None else latest.verified_by.display_name


def _verified_on(row: VerificationRow) -> str:
    """The local day of the row's latest verification, or a blank cell."""
    latest = row.latest
    return "" if latest is None else _local_day(latest.verified_at)


def _check_column(slug: str, label: str) -> ReportColumn[VerificationRow]:
    """The default check column for the item ``slug``, headed ``label``."""
    return ReportColumn(slug, label, True, lambda row: row.check(slug), width=1.25)


#: Every column the report can carry, in export order.  The three verification columns
#: are off by default, and the PDF leaves Section to its headings.
VERIFICATION_REPORT_COLUMNS: tuple[ReportColumn[VerificationRow], ...] = (
    ReportColumn("section", "Section", True, lambda row: row.section, width=2.0),
    ReportColumn("name", "Name", True, lambda row: row.name, width=2.0),
    ReportColumn("dart", "DART or owner", True, lambda row: row.dart, width=4.3),
    _check_column("photo_id", "Photo ID"),
    _check_column("certificate", "Certificate"),
    _check_column("medical", "Medical"),
    ReportColumn("details", "Details", True, lambda row: row.details, width=5.2),
    ReportColumn("expires", "Expires", True, lambda row: _day(row.expires), width=1.4),
    ReportColumn("updated", "Updated", True, lambda row: _local_day(row.updated_at), width=1.4),
    ReportColumn(
        "verified", "Verified", False, lambda row: "Yes" if row.is_verified else "No", width=1.2
    ),
    ReportColumn("verified_by", "Verified by", False, _verified_by_name, width=2.4),
    ReportColumn("verified_on", "Verified on", False, _verified_on, width=1.5),
)


#: The verification stamp columns, which either section draws when they are chosen.
_STAMP_KEYS: tuple[str, ...] = ("verified", "verified_by", "verified_on")

#: The columns each section draws in the PDF, and the words it heads them with.  An
#: aircraft has no check columns, and its Name, DART, and Details are its N-number, owner,
#: and carrier.
VERIFICATION_SECTION_COLUMNS: tuple[SectionColumns, ...] = (
    SectionColumns(
        title=PEOPLE_SECTION,
        keys=(
            "section",
            "name",
            "dart",
            "photo_id",
            "certificate",
            "medical",
            "details",
            "expires",
            "updated",
            *_STAMP_KEYS,
        ),
        labels={"dart": "DART"},
    ),
    SectionColumns(
        title=INSURANCE_SECTION,
        keys=("section", "name", "dart", "details", "expires", "updated", *_STAMP_KEYS),
        labels={"name": "N-number", "dart": "Owner", "details": "Carrier"},
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


def _profile_changed_at(profile: MemberProfile) -> datetime:
    """When ``profile``'s items were last changed: its last edit, else its creation.

    A profile nobody has edited since it was made carries no ``profile_updated_at``,
    and what is on file has been there since the profile was created.
    """
    return profile.profile_updated_at or profile.created_at


def _person_row(profile: MemberProfile) -> VerificationRow | None:
    """``profile``'s row, or ``None`` when the person holds none of the three items.

    The checks, and the details, name only the items held, in check-column order, and
    the expiry is the medical's, blank without a medical.
    """
    held = [(slug, details) for slug, details in PERSON_ITEMS if is_held(profile, slug)]
    if len(held) == 0:
        return None
    return VerificationRow(
        section=PEOPLE_SECTION,
        name=profile.user.display_name,
        dart="" if profile.dart is None else profile.dart.name,
        details=_details(*(details(profile) for _slug, details in held)),
        expires=profile.medical_expiration if is_held(profile, "medical") else None,
        updated_at=_profile_changed_at(profile),
        items=tuple(
            ItemCheck(
                slug=slug,
                verified_at=getattr(profile, f"{slug}_verified_at"),
                verified_by=getattr(profile, f"{slug}_verified_by"),
            )
            for slug, _details in held
        ),
    )


def person_rows(profiles: list[MemberProfile]) -> Iterator[VerificationRow]:
    """One row per person of ``profiles`` who holds an item, in the order given."""
    for profile in profiles:
        row = _person_row(profile)
        if row is not None:
            yield row


def insurance_rows(aircraft: QuerySet[Aircraft]) -> Iterator[VerificationRow]:
    """One row per aircraft's insurance: the owner, the carrier, and the expiry."""
    for plane in aircraft:
        yield VerificationRow(
            section=INSURANCE_SECTION,
            name=plane.n_number,
            dart=plane.owner_name,
            details=plane.insurance_carrier,
            expires=plane.insurance_expiration,
            updated_at=plane.updated_at,
            items=(
                ItemCheck(
                    slug=INSURANCE,
                    verified_at=plane.insurance_verified_at,
                    verified_by=plane.insurance_verified_by,
                ),
            ),
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

    ``status`` is ``unverified`` (the default), ``verified``, or ``all``: ``unverified``
    keeps the rows with any held item not yet verified, ``verified`` the rows whose every
    held item is verified, and ``all`` every row; any other value raises DRF's
    ``ValidationError`` keyed by ``status``.  ``dart`` is a DART's id or part of its
    name, and keeps that DART's people and the aircraft its pilots fly.  The rows come
    section by section in
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
    section_column="section",
    section_columns=VERIFICATION_SECTION_COLUMNS,
)
