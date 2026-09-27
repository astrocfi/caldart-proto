"""The CalDART verification report: what a verifier still has to check, item by item.

The report has four sections, pilot certificates, medicals, photo IDs, and aircraft
insurance, each present even when it has no rows.  A person is listed in each of the
first three once, an aircraft in the fourth once, and ``?status=`` chooses whether the
unverified items (the default), the verified ones, or all of them are listed.  Every
verifying role reads it, and a subscription can send it to any of them.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.accounts.models import AccountKind, User
from apps.accounts.roles import (
    ACCOUNT_ADMIN,
    DART_LEADER,
    SYSTEM_ADMIN,
    USER_ADMIN,
    VERIFIER,
    VERIFY_ROLES,
)
from apps.aircraft.models import Aircraft
from apps.darts.models import Dart
from apps.members.models import MedicalType, MemberProfile, PhotoIdType, PilotCertificateType
from apps.members.verification_report import (
    VERIFICATION_REPORT,
    VERIFICATION_REPORT_COLUMNS,
    VerificationRow,
)
from apps.reports.registry import REPORTS
from caldart.reports import Params, select_columns
from tests.conftest import PdfText, read_csv, role_matrix
from tests.factories import AircraftFactory, DartFactory, MemberProfileFactory, UserFactory

pytestmark = pytest.mark.django_db

REPORTS_URL = "/api/v1/reports"
CSV_URL = "/api/v1/reports/verification/export.csv"
PDF_URL = "/api/v1/reports/verification/export.pdf"
SUBSCRIPTIONS_URL = "/api/v1/reports/subscriptions"

#: The four sections, in the order the report draws them.
SECTION_TITLES = ["Pilot certificates", "Medicals", "Photo IDs", "Aircraft insurance"]

#: The day the report is built on in the table tests.
TODAY = date(2026, 9, 26)

#: When the verification tests stamp an item: noon on 2026/09/20 in California.
STAMP = datetime(2026, 9, 20, 19, 0, tzinfo=UTC)


def rows_for(params: Params | None = None) -> list[VerificationRow]:
    """The rows the report's query answers for ``params``, in order."""
    return list(VERIFICATION_REPORT.query(params or {}).rows)


def pairs(rows: list[VerificationRow]) -> list[tuple[str, str]]:
    """Each row as its ``(section, name)``."""
    return [(row.section, row.name) for row in rows]


def section_titles(params: Params | None = None) -> list[str]:
    """The titles of the report's sections for ``params``, in order."""
    table = VERIFICATION_REPORT.table(params or {}, fmt="csv", today=TODAY)
    return [section.title for section in table.sections]


def cells(section: str, name: str, params: Params | None = None) -> list[str]:
    """Every default cell after Section and Name of the row ``(section, name)``."""
    table = VERIFICATION_REPORT.table(params or {}, fmt="csv", today=TODAY)
    return next(row[2:] for row in table.rows if row[0] == section and row[1] == name)


def person(
    first: str = "Pat", last: str = "Doe", *, dart: Dart | None = None, **fields: object
) -> MemberProfile:
    """A member's profile with the given names, DART, and profile fields."""
    user = UserFactory(
        email=f"{first}.{last}@example.test".lower(), first_name=first, last_name=last
    )
    profile: MemberProfile = MemberProfileFactory(
        user=user, dart=dart or DartFactory(name="Palo Alto"), **fields
    )
    return profile


def verify_all(profile: MemberProfile, by: User) -> None:
    """Stamp the profile's three items verified by ``by`` at :data:`STAMP`."""
    for slug in ("certificate", "medical", "photo_id"):
        setattr(profile, f"{slug}_verified_at", STAMP)
        setattr(profile, f"{slug}_verified_by", by)
    profile.save()


# --------------------------------------------------------------------------
# The spec and the registry
# --------------------------------------------------------------------------
def test_the_report_is_titled_and_named_for_its_file() -> None:
    """The title heads the PDF; the stem begins the file name."""
    assert (VERIFICATION_REPORT.title, VERIFICATION_REPORT.filename_stem) == (
        "CalDART verification report",
        "caldart-verification",
    )


def test_the_report_is_read_by_every_verifying_role() -> None:
    """Verifiers, DART leaders, and user and account administrators read it."""
    assert VERIFICATION_REPORT.roles == VERIFY_ROLES


def test_the_report_is_landscape_with_choosable_columns_and_no_period() -> None:
    """``(choosable, landscape, periods)``: a wide table whose columns can be chosen."""
    spec = VERIFICATION_REPORT
    assert (spec.choosable, spec.landscape, spec.periods) == (True, True, False)


def test_an_empty_section_says_there_is_nothing_to_show() -> None:
    """The PDF draws ``Nothing to show.`` under a section with no rows."""
    assert VERIFICATION_REPORT.empty_section == "Nothing to show."


def test_every_column_is_registered_in_export_order() -> None:
    """The eight columns, Section first."""
    assert [(column.key, column.label) for column in VERIFICATION_REPORT_COLUMNS] == [
        ("section", "Section"),
        ("name", "Name"),
        ("dart", "DART"),
        ("details", "Details"),
        ("updated", "Updated"),
        ("verified", "Verified"),
        ("verified_by", "Verified by"),
        ("verified_on", "Verified on"),
    ]


def test_every_column_is_on_by_default() -> None:
    """Choosing no columns prints all eight."""
    chosen = select_columns(VERIFICATION_REPORT_COLUMNS, None)
    assert len(chosen) == len(VERIFICATION_REPORT_COLUMNS)


def test_the_registry_files_the_report_under_its_slug() -> None:
    """``REPORTS["verification"]`` is the verification report."""
    assert REPORTS["verification"] is VERIFICATION_REPORT


def test_the_registry_lists_the_report_right_after_the_roles_report() -> None:
    """The portal lists the verification report third, after the roles report."""
    slugs = list(REPORTS)
    assert slugs[slugs.index("roles") + 1] == "verification"


# --------------------------------------------------------------------------
# Rows and sections
# --------------------------------------------------------------------------
def test_every_section_is_drawn_even_with_nothing_in_it() -> None:
    """The four sections, in order, with no rows at all."""
    assert section_titles() == SECTION_TITLES


def test_an_unverified_person_is_listed_once_in_each_person_section() -> None:
    """A member with nothing verified is under certificates, medicals, and photo IDs."""
    person("Pat", "Doe")
    assert pairs(rows_for()) == [
        ("Pilot certificates", "Pat Doe"),
        ("Medicals", "Pat Doe"),
        ("Photo IDs", "Pat Doe"),
    ]


def test_an_aircraft_with_unverified_insurance_is_listed_by_n_number() -> None:
    """The aircraft's row is under Aircraft insurance, named by its N-number."""
    AircraftFactory(n_number="N123AB")
    assert pairs(rows_for()) == [("Aircraft insurance", "N123AB")]


def test_a_verified_item_is_left_out_by_default(dart_leader: User) -> None:
    """With no ``status``, only the items still to verify are listed."""
    profile = person("Pat", "Doe")
    profile.medical_verified_at = STAMP
    profile.medical_verified_by = dart_leader
    profile.save()
    assert pairs(rows_for()) == [("Pilot certificates", "Pat Doe"), ("Photo IDs", "Pat Doe")]


def test_status_verified_lists_the_verified_items_alone() -> None:
    """``?status=verified`` keeps the verified medical and nothing else."""
    profile = person("Pat", "Doe")
    profile.medical_verified_at = STAMP
    profile.save()
    AircraftFactory(n_number="N123AB")
    assert pairs(rows_for({"status": "verified"})) == [("Medicals", "Pat Doe")]


def test_status_all_lists_every_item() -> None:
    """``?status=all`` lists verified and unverified items alike."""
    profile = person("Pat", "Doe")
    profile.medical_verified_at = STAMP
    profile.save()
    AircraftFactory(n_number="N123AB", insurance_verified_at=STAMP)
    assert pairs(rows_for({"status": "all"})) == [
        ("Pilot certificates", "Pat Doe"),
        ("Medicals", "Pat Doe"),
        ("Photo IDs", "Pat Doe"),
        ("Aircraft insurance", "N123AB"),
    ]


def test_verified_insurance_is_left_out_by_default() -> None:
    """An aircraft whose insurance is verified has nothing to show by default."""
    AircraftFactory(n_number="N123AB", insurance_verified_at=STAMP)
    assert rows_for() == []


def test_a_friend_is_listed() -> None:
    """A friend of CalDART is checkable, so the friend's items are listed."""
    friend = UserFactory(
        email="fr@example.test", first_name="Fay", last_name="Ng", kind=AccountKind.FRIEND
    )
    MemberProfileFactory(user=friend)
    assert [name for _section, name in pairs(rows_for())] == ["Fay Ng"] * 3


@pytest.mark.parametrize(
    "fields",
    [{"kind": AccountKind.DONOR}, {"is_active": False}],
    ids=["donor", "deactivated"],
)
def test_a_donor_or_a_deactivated_account_is_never_listed(fields: dict[str, object]) -> None:
    """Donors and deactivated accounts have nothing to verify."""
    user = UserFactory(email="out@example.test", **fields)
    MemberProfileFactory(user=user)
    assert rows_for({"status": "all"}) == []


def test_an_account_without_a_profile_is_not_listed(verifier: User) -> None:
    """With no profile there are no details to verify."""
    assert rows_for({"status": "all"}) == []


def test_an_aircraft_out_of_service_is_not_listed() -> None:
    """A retired airframe flies no mission, so its insurance is not listed."""
    AircraftFactory(n_number="N123AB", is_active=False)
    assert rows_for({"status": "all"}) == []


def test_people_are_ordered_by_last_name_first_name_then_email() -> None:
    """Within a section, surname, then forename, then address settles the order."""
    person("Ann", "Zed")
    person("Bea", "Abe")
    person("Ann", "Abe")
    names = [row.name for row in rows_for() if row.section == "Medicals"]
    assert names == ["Ann Abe", "Bea Abe", "Ann Zed"]


def test_aircraft_are_ordered_by_n_number() -> None:
    """The insurance rows run in N-number order."""
    AircraftFactory(n_number="N900ZZ")
    AircraftFactory(n_number="N100AA")
    assert [row.name for row in rows_for()] == ["N100AA", "N900ZZ"]


# --------------------------------------------------------------------------
# Cells
# --------------------------------------------------------------------------
def test_a_certificate_reads_its_type_and_number() -> None:
    """DART, *Private · 1234567*, no update yet, and not verified."""
    person(pilot_certificate_type=PilotCertificateType.PRIVATE, certificate_number="1234567")
    assert cells("Pilot certificates", "Pat Doe") == [
        "Palo Alto",
        "Private · 1234567",
        "",
        "No",
        "",
        "",
    ]


def test_a_certificate_with_no_number_reads_its_type_alone() -> None:
    """An empty certificate number leaves the type on its own."""
    person(pilot_certificate_type=PilotCertificateType.NONE, certificate_number="")
    assert cells("Pilot certificates", "Pat Doe")[1] == "None"


def test_a_medical_reads_its_class_and_expiration() -> None:
    """*Third class · expires 2027/03/01*."""
    person(medical_type=MedicalType.THIRD, medical_expiration=date(2027, 3, 1))
    assert cells("Medicals", "Pat Doe")[1] == "Third class · expires 2027/03/01"


def test_no_medical_reads_none() -> None:
    """A member with no medical and no expiration reads *None*."""
    person(medical_type=MedicalType.NONE, medical_expiration=None)
    assert cells("Medicals", "Pat Doe")[1] == "None"


def test_a_photo_id_reads_its_kind() -> None:
    """Only the kind of document is recorded, and only it is printed."""
    person(photo_id_type=PhotoIdType.PASSPORT)
    assert cells("Photo IDs", "Pat Doe")[1] == "Passport"


def test_insurance_reads_the_owner_the_carrier_and_the_expiration() -> None:
    """The DART column carries the owner; the details *Avemco · expires 2027/03/01*."""
    AircraftFactory(
        n_number="N123AB",
        owner_name="Sky Club",
        insurance_carrier="Avemco",
        insurance_expiration=date(2027, 3, 1),
    )
    assert cells("Aircraft insurance", "N123AB")[:2] == [
        "Sky Club",
        "Avemco · expires 2027/03/01",
    ]


def test_insurance_with_nothing_on_file_has_blank_details() -> None:
    """No carrier and no expiration leave the Details cell empty."""
    AircraftFactory(n_number="N123AB", insurance_carrier="", insurance_expiration=None)
    assert cells("Aircraft insurance", "N123AB")[1] == ""


def test_a_person_s_updated_cell_is_when_the_profile_was_last_written() -> None:
    """``profile_updated_at`` printed as ``YYYY/MM/DD``."""
    person(profile_updated_at=STAMP)
    assert cells("Photo IDs", "Pat Doe")[2] == "2026/09/20"


def test_an_aircraft_s_updated_cell_is_when_the_record_was_last_written() -> None:
    """The aircraft's ``updated_at`` printed as ``YYYY/MM/DD``."""
    aircraft = AircraftFactory(n_number="N123AB")
    Aircraft.objects.filter(pk=aircraft.pk).update(updated_at=STAMP)
    assert cells("Aircraft insurance", "N123AB")[2] == "2026/09/20"


def test_a_verified_item_names_who_verified_it_and_when(dart_leader: User) -> None:
    """Verified *Yes*, the verifier's name, and the local day of the stamp."""
    verify_all(person(), dart_leader)
    row = cells("Medicals", "Pat Doe", {"status": "verified"})
    assert row[3:] == ["Yes", "Jordan Keel", "2026/09/20"]


def test_verified_insurance_names_who_verified_it_and_when(dart_leader: User) -> None:
    """The insurance row carries the same three cells."""
    AircraftFactory(
        n_number="N123AB", insurance_verified_at=STAMP, insurance_verified_by=dart_leader
    )
    row = cells("Aircraft insurance", "N123AB", {"status": "verified"})
    assert row[3:] == ["Yes", "Jordan Keel", "2026/09/20"]


def test_an_item_whose_verifier_is_gone_still_reads_verified() -> None:
    """A deleted verifier's account leaves the stamp and a blank name."""
    profile = person()
    profile.photo_id_verified_at = STAMP
    profile.save()
    assert cells("Photo IDs", "Pat Doe", {"status": "verified"})[3:] == ["Yes", "", "2026/09/20"]


def test_the_section_cell_carries_the_section() -> None:
    """The flat CSV keeps each row's section in its first cell."""
    person()
    table = VERIFICATION_REPORT.table({}, fmt="csv", today=TODAY)
    assert [row[0] for row in table.rows] == SECTION_TITLES[:3]


# --------------------------------------------------------------------------
# Filters
# --------------------------------------------------------------------------
@pytest.fixture
def two_darts() -> tuple[Dart, Dart]:
    """Two DARTs, each with a member flying an aircraft of their own."""
    north = DartFactory(name="North Bay")
    south = DartFactory(name="South Bay")
    for dart, first, n_number in [(north, "Nia", "N1NB"), (south, "Sol", "N2SB")]:
        profile = person(first, "Pilot", dart=dart)
        profile.aircraft.add(AircraftFactory(n_number=n_number))
    AircraftFactory(n_number="N3XX")
    return north, south


def test_dart_by_id_keeps_its_people_and_the_aircraft_they_fly(
    two_darts: tuple[Dart, Dart],
) -> None:
    """``?dart=<id>`` lists that DART's member and the airplane the member flies."""
    north, _south = two_darts
    assert pairs(rows_for({"dart": str(north.pk)})) == [
        ("Pilot certificates", "Nia Pilot"),
        ("Medicals", "Nia Pilot"),
        ("Photo IDs", "Nia Pilot"),
        ("Aircraft insurance", "N1NB"),
    ]


def test_dart_by_name_matches_part_of_it(two_darts: tuple[Dart, Dart]) -> None:
    """``?dart=south`` matches South Bay, case-insensitively."""
    names = {name for _section, name in pairs(rows_for({"dart": "south"}))}
    assert names == {"Sol Pilot", "N2SB"}


def test_an_aircraft_two_pilots_of_one_dart_fly_is_listed_once(dart: Dart) -> None:
    """Two pilots of the DART on one airframe do not list it twice."""
    aircraft = AircraftFactory(n_number="N123AB")
    for first in ("Ann", "Bea"):
        person(first, "Pilot", dart=dart).aircraft.add(aircraft)
    rows = rows_for({"dart": str(dart.pk)})
    assert [row.name for row in rows if row.section == "Aircraft insurance"] == ["N123AB"]


def test_status_refuses_anything_else() -> None:
    """An unknown status is refused, keyed by ``status``."""
    with pytest.raises(ValidationError) as caught:
        VERIFICATION_REPORT.query({"status": "maybe"})
    assert caught.value.detail == {
        "status": ["Select a valid choice. maybe is not one of the available choices."]
    }


def test_the_default_status_is_named_among_the_filters() -> None:
    """With nothing given, the PDF subtitle still says the unverified items are listed."""
    assert VERIFICATION_REPORT.query({}).filters == {"status": "unverified"}


def test_the_report_names_the_filters_it_applied(dart: Dart) -> None:
    """Status and DART, in that order, and nothing it does not read."""
    query = VERIFICATION_REPORT.query({"dart": str(dart.pk), "status": "all", "page": "2"})
    assert query.filters == {"status": "all", "dart": str(dart.pk)}


# --------------------------------------------------------------------------
# The endpoints
# --------------------------------------------------------------------------
READERS = (VERIFIER, DART_LEADER, USER_ADMIN, ACCOUNT_ADMIN, SYSTEM_ADMIN)


@pytest.mark.parametrize(("role", "allowed"), role_matrix(*READERS))
def test_the_report_list_offers_the_report_to_its_readers(
    api_client: APIClient, all_role_users: dict[str, User], role: str, allowed: bool
) -> None:
    """Every verifying role, and a system administrator, see ``verification``."""
    api_client.force_login(all_role_users[role])
    slugs = [entry["slug"] for entry in api_client.get(REPORTS_URL).json()]
    assert ("verification" in slugs) is allowed


@pytest.mark.parametrize(("role", "allowed"), role_matrix(*READERS))
def test_the_export_is_for_the_report_s_readers(
    api_client: APIClient, all_role_users: dict[str, User], role: str, allowed: bool
) -> None:
    """Anybody else is refused with a 403."""
    api_client.force_login(all_role_users[role])
    assert api_client.get(CSV_URL).status_code == (200 if allowed else 403)


def test_the_csv_download_is_named_for_the_day(account_admin_client: APIClient) -> None:
    """The file is ``caldart-verification-<YYYY-MM-DD>.csv``."""
    response = account_admin_client.get(CSV_URL)
    assert response["Content-Disposition"] == (
        f'attachment; filename="caldart-verification-{timezone.localdate().isoformat()}.csv"'
    )


def test_the_csv_lists_every_unverified_item_under_its_section(
    api_client: APIClient, dart_leader: User
) -> None:
    """A DART leader's download lists the member's three items and the aircraft's."""
    person("Pat", "Doe")
    AircraftFactory(n_number="N123AB")
    api_client.force_login(dart_leader)
    table = read_csv(api_client.get(CSV_URL, {"columns": "section,name,verified"}))
    assert table == [
        ["Section", "Name", "Verified"],
        ["Pilot certificates", "Pat Doe", "No"],
        ["Medicals", "Pat Doe", "No"],
        ["Photo IDs", "Pat Doe", "No"],
        ["Aircraft insurance", "N123AB", "No"],
    ]


def test_the_csv_refuses_an_unknown_status(account_admin_client: APIClient) -> None:
    """A bad status is a 400 keyed by ``status``."""
    response = account_admin_client.get(CSV_URL, {"status": "maybe"})
    assert response.status_code == 400
    assert response.json() == {
        "status": ["Select a valid choice. maybe is not one of the available choices."]
    }


def test_the_pdf_heads_each_section(account_admin_client: APIClient, pdf_text: PdfText) -> None:
    """Every section title appears on the page, in order, above its rows."""
    person()
    AircraftFactory(n_number="N123AB")
    response = account_admin_client.get(PDF_URL, {"columns": "name,details"})
    strings = pdf_text(response.content)[0]
    assert [text for text in strings if text in SECTION_TITLES] == SECTION_TITLES


def test_the_pdf_says_so_under_an_empty_section(
    account_admin_client: APIClient, pdf_text: PdfText
) -> None:
    """With nothing on file, the first section reads ``Nothing to show.``."""
    strings = pdf_text(account_admin_client.get(PDF_URL).content)[0]
    assert strings[2:4] == ["Pilot certificates", "Nothing to show."]


def subscribe(client: APIClient, recipient: User) -> int:
    """Subscribe ``recipient`` to the monthly verification PDF; the response's status."""
    response = client.post(
        SUBSCRIPTIONS_URL,
        {
            "report": "verification",
            "recipient_email": recipient.email,
            "filters": {"status": "unverified"},
            "columns": [],
            "formats": "pdf",
            "cadence": "monthly",
            "weekday": 0,
        },
        format="json",
    )
    return response.status_code


def test_the_report_can_be_sent_to_a_verifier(
    account_admin_client: APIClient, verifier: User
) -> None:
    """A verifier reads the report, so a subscription for one is set up."""
    assert subscribe(account_admin_client, verifier) == 201


def test_the_report_cannot_be_sent_to_a_treasurer(
    account_admin_client: APIClient, treasurer: User
) -> None:
    """A treasurer holds no verifying role, so sending the report to one is refused."""
    assert subscribe(account_admin_client, treasurer) == 400
