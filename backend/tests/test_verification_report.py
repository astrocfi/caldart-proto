"""The CalDART verification report: what a verifier still has to check.

The report has two sections, People and Aircraft insurance, each present even when it
has no rows.  A person is listed once under People, with a check column for each of
their photo ID, certificate, and medical, and an aircraft once under Aircraft insurance
when it has a policy on file.  ``?status=`` chooses whether the rows with something
unverified (the default), the fully verified ones, or all of them are listed.  Every
verifying role reads it, and a subscription can send it to any of them.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING

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
from apps.aircraft.verification_report import (
    VERIFICATION_REPORT,
    VERIFICATION_REPORT_COLUMNS,
    VerificationRow,
)
from apps.darts.models import Dart
from apps.members.models import MedicalType, MemberProfile, PhotoIdType, PilotCertificateType
from apps.reports.registry import REPORTS
from caldart.reports import Params, select_columns
from tests.conftest import PdfText, read_csv, role_matrix
from tests.factories import AircraftFactory, DartFactory, MemberProfileFactory, UserFactory

if TYPE_CHECKING:
    # rest_framework.test.APIClient.post() is typed to return this class, but it
    # exists only in the stub: rest_framework monkey-patches Django's test response
    # at runtime rather than defining a real subclass.
    from rest_framework.response import _MonkeyPatchedResponse as ApiResponse

pytestmark = pytest.mark.django_db

REPORTS_URL = "/api/v1/reports"
CSV_URL = "/api/v1/reports/verification/export.csv"
PDF_URL = "/api/v1/reports/verification/export.pdf"
SUBSCRIPTIONS_URL = "/api/v1/reports/subscriptions"

#: The two sections, in the order the report draws them.
SECTION_TITLES = ["People", "Aircraft insurance"]

#: The day the report is built on in the table tests.
TODAY = date(2026, 9, 26)

#: When the verification tests stamp an item: noon on 09/20/2026 in California.
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


#: Every column of the report, for the tests that read the cells the defaults leave out.
ALL_COLUMNS = ",".join(column.key for column in VERIFICATION_REPORT_COLUMNS)


def cells(section: str, name: str, params: Params | None = None) -> list[str]:
    """Every cell after Section and Name of the row ``(section, name)``, any column."""
    table = VERIFICATION_REPORT.table(
        {**(params or {}), "columns": ALL_COLUMNS}, fmt="csv", today=TODAY
    )
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
    """Twelve columns, Section first; the checks run Photo ID, Certificate, Medical."""
    assert [(column.key, column.label) for column in VERIFICATION_REPORT_COLUMNS] == [
        ("section", "Section"),
        ("name", "Name"),
        ("dart", "DART or owner"),
        ("photo_id", "Photo ID"),
        ("certificate", "Certificate"),
        ("medical", "Medical"),
        ("details", "Details"),
        ("expires", "Expires"),
        ("updated", "Updated"),
        ("verified", "Verified"),
        ("verified_by", "Verified by"),
        ("verified_on", "Verified on"),
    ]


def test_the_default_columns_leave_out_the_stamp() -> None:
    """Choosing no columns prints everything but the three verification stamp columns.

    The check columns already say which items are verified, and the stamp columns are
    always *No* and blank in the default list of what requires validation.
    """
    chosen = select_columns(VERIFICATION_REPORT_COLUMNS, None)
    assert [column.key for column in chosen] == [
        "section",
        "name",
        "dart",
        "photo_id",
        "certificate",
        "medical",
        "details",
        "expires",
        "updated",
    ]


def test_the_default_csv_keeps_each_row_s_section() -> None:
    """A flat CSV has no headings, so its first column says which section a row is in."""
    person()
    table = VERIFICATION_REPORT.table({}, fmt="csv", today=TODAY)
    assert table.header[0] == "Section"


def test_the_default_pdf_leaves_the_section_to_its_headings() -> None:
    """Each PDF section is headed by its title, so the column would only repeat it."""
    person()
    table = VERIFICATION_REPORT.table({}, fmt="pdf", today=TODAY)
    assert table.header == [
        "Name",
        "DART or owner",
        "Photo ID",
        "Certificate",
        "Medical",
        "Details",
        "Expires",
        "Updated",
    ]


def test_a_pdf_that_asks_for_the_section_column_prints_it() -> None:
    """Asked for by name, the Section column is printed in the PDF too."""
    person()
    table = VERIFICATION_REPORT.table({"columns": "section,name"}, fmt="pdf", today=TODAY)
    assert table.header == ["Section", "Name"]


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
    """The two sections, in order, with no rows at all."""
    assert section_titles() == SECTION_TITLES


def test_an_unverified_person_is_listed_once_under_people() -> None:
    """A member with nothing verified has one row, under People."""
    person("Pat", "Doe")
    assert pairs(rows_for()) == [("People", "Pat Doe")]


def test_a_person_s_check_columns_say_each_item_needs_validating() -> None:
    """Photo ID, Certificate, and Medical, in that order, each read *Not verified*."""
    person("Pat", "Doe")
    assert cells("People", "Pat Doe")[1:4] == ["Not verified"] * 3


def test_an_aircraft_with_unverified_insurance_is_listed_by_n_number() -> None:
    """The aircraft's row is under Aircraft insurance, named by its N-number."""
    AircraftFactory(n_number="N123AB")
    assert pairs(rows_for()) == [("Aircraft insurance", "N123AB")]


def test_a_partly_verified_person_is_listed_by_default(dart_leader: User) -> None:
    """With no ``status``, a person with one item still to verify is listed."""
    profile = person("Pat", "Doe")
    profile.medical_verified_at = STAMP
    profile.medical_verified_by = dart_leader
    profile.save()
    assert pairs(rows_for()) == [("People", "Pat Doe")]


def test_a_partly_verified_person_s_checks_say_which_item_is_verified() -> None:
    """The verified medical reads *Verified*, the other two *Not verified*."""
    profile = person("Pat", "Doe")
    profile.medical_verified_at = STAMP
    profile.save()
    assert cells("People", "Pat Doe")[1:4] == ["Not verified", "Not verified", "Verified"]


def test_a_fully_verified_person_is_left_out_by_default(dart_leader: User) -> None:
    """Nothing of theirs requires validation, so the default list leaves them out."""
    verify_all(person("Pat", "Doe"), dart_leader)
    assert rows_for() == []


def test_status_verified_lists_the_fully_verified_alone(dart_leader: User) -> None:
    """``?status=verified`` keeps a person with every item verified, and nobody else."""
    verify_all(person("Ann", "Abe"), dart_leader)
    partly = person("Bea", "Abe")
    partly.medical_verified_at = STAMP
    partly.save()
    AircraftFactory(n_number="N123AB")
    assert pairs(rows_for({"status": "verified"})) == [("People", "Ann Abe")]


def test_status_all_lists_every_row() -> None:
    """``?status=all`` lists verified and unverified rows alike."""
    profile = person("Pat", "Doe")
    profile.medical_verified_at = STAMP
    profile.save()
    AircraftFactory(n_number="N123AB", insurance_verified_at=STAMP)
    assert pairs(rows_for({"status": "all"})) == [
        ("People", "Pat Doe"),
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
    assert pairs(rows_for()) == [("People", "Fay Ng")]


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
    """Under People, surname, then forename, then address settles the order."""
    person("Ann", "Zed")
    person("Bea", "Abe")
    person("Ann", "Abe")
    names = [row.name for row in rows_for()]
    assert names == ["Ann Abe", "Bea Abe", "Ann Zed"]


def test_aircraft_are_ordered_by_n_number() -> None:
    """The insurance rows run in N-number order."""
    AircraftFactory(n_number="N900ZZ")
    AircraftFactory(n_number="N100AA")
    assert [row.name for row in rows_for()] == ["N100AA", "N900ZZ"]


# --------------------------------------------------------------------------
# Cells
# --------------------------------------------------------------------------
def test_a_person_s_row_reads_the_checks_the_details_and_the_expiry() -> None:
    """DART, the three checks, the details, the medical's expiry, and the day it changed.

    The details name the photo ID, the certificate and its number, and the medical,
    in the order of the check columns; the expiry is a column of its own.
    """
    profile = person(
        photo_id_type=PhotoIdType.PASSPORT,
        pilot_certificate_type=PilotCertificateType.PRIVATE,
        certificate_number="1234567",
        medical_type=MedicalType.THIRD,
        medical_expiration=date(2027, 3, 1),
        profile_updated_at=None,
    )
    MemberProfile.objects.filter(pk=profile.pk).update(created_at=STAMP)
    assert cells("People", "Pat Doe") == [
        "Palo Alto",
        "Not verified",
        "Not verified",
        "Not verified",
        "Passport \u00b7 Private \u00b7 1234567 \u00b7 Third class",
        "03/01/2027",
        "09/20/2026",
        "No",
        "",
        "",
    ]


def test_a_certificate_with_no_number_reads_its_type_alone() -> None:
    """An empty certificate number leaves the type on its own in the details."""
    person(pilot_certificate_type=PilotCertificateType.PRIVATE, certificate_number="")
    assert cells("People", "Pat Doe")[4] == "Driver's license \u00b7 Private \u00b7 Third class"


@pytest.mark.parametrize("status", ["unverified", "all"])
def test_a_person_without_a_medical_reads_not_provided_in_the_medical_check(
    status: str,
) -> None:
    """With no medical there is nothing to verify: the Medical check says so."""
    person(medical_type=MedicalType.NONE, medical_expiration=None)
    assert cells("People", "Pat Doe", {"status": status})[1:4] == [
        "Not verified",
        "Not verified",
        "Not provided",
    ]


def test_a_person_without_a_medical_has_no_expiry() -> None:
    """The Expires cell is the medical's, so it is blank without one."""
    person(medical_type=MedicalType.NONE, medical_expiration=None)
    assert cells("People", "Pat Doe")[5] == ""


def test_a_non_pilot_reads_not_provided_in_the_certificate_check() -> None:
    """*Not a pilot* holds no certificate to verify."""
    person(pilot_certificate_type=PilotCertificateType.NONE, certificate_number="")
    assert cells("People", "Pat Doe")[1:4] == ["Not verified", "Not provided", "Not verified"]


def test_a_person_without_a_photo_id_reads_not_provided_in_the_photo_id_check() -> None:
    """A photo ID of *Not provided* is no document a verifier could check."""
    person(photo_id_type=PhotoIdType.NOT_PROVIDED)
    assert cells("People", "Pat Doe")[1:4] == ["Not provided", "Not verified", "Not verified"]


def test_a_person_who_holds_nothing_is_not_listed() -> None:
    """No certificate, no medical, and no photo ID leave nothing to verify."""
    person(
        pilot_certificate_type=PilotCertificateType.NONE,
        certificate_number="",
        medical_type=MedicalType.NONE,
        medical_expiration=None,
        photo_id_type=PhotoIdType.NOT_PROVIDED,
    )
    assert rows_for({"status": "all"}) == []


def test_an_unheld_item_s_stamp_does_not_make_a_person_verified() -> None:
    """A stamp on a medical of *None* counts for nothing, as on the member check."""
    profile = person(medical_type=MedicalType.NONE, medical_expiration=None)
    profile.medical_verified_at = STAMP
    profile.save()
    assert pairs(rows_for()) == [("People", "Pat Doe")]


def test_insurance_reads_the_owner_the_carrier_and_the_expiry() -> None:
    """The DART column carries the owner, the checks are blank, then carrier, expiry."""
    AircraftFactory(
        n_number="N123AB",
        owner_name="Sky Club",
        insurance_carrier="Avemco",
        insurance_expiration=date(2027, 3, 1),
    )
    assert cells("Aircraft insurance", "N123AB")[:6] == [
        "Sky Club",
        "",
        "",
        "",
        "Avemco",
        "03/01/2027",
    ]


def test_an_aircraft_with_no_policy_on_file_is_not_listed() -> None:
    """Insurance with no expiration is no policy, so there is nothing to verify."""
    AircraftFactory(n_number="N123AB", insurance_carrier="", insurance_expiration=None)
    assert rows_for({"status": "all"}) == []


def test_a_person_s_updated_cell_is_when_the_profile_was_last_written() -> None:
    """``profile_updated_at`` printed as ``MM/DD/YYYY``."""
    person(profile_updated_at=STAMP)
    assert cells("People", "Pat Doe")[6] == "09/20/2026"


def test_a_person_nobody_has_edited_is_updated_when_the_profile_was_made() -> None:
    """A profile with no ``profile_updated_at`` dates its items from its creation."""
    profile = person(profile_updated_at=None)
    MemberProfile.objects.filter(pk=profile.pk).update(created_at=STAMP)
    assert cells("People", "Pat Doe")[6] == "09/20/2026"


def test_an_aircraft_s_updated_cell_is_when_the_record_was_last_written() -> None:
    """The aircraft's ``updated_at`` printed as ``MM/DD/YYYY``."""
    aircraft = AircraftFactory(n_number="N123AB")
    Aircraft.objects.filter(pk=aircraft.pk).update(updated_at=STAMP)
    assert cells("Aircraft insurance", "N123AB")[6] == "09/20/2026"


def test_a_verified_person_names_who_verified_them_and_when(dart_leader: User) -> None:
    """Verified *Yes*, the verifier's name, and the local day of the stamp."""
    verify_all(person(), dart_leader)
    row = cells("People", "Pat Doe", {"status": "verified"})
    assert row[7:] == ["Yes", "Jordan Keel", "09/20/2026"]


def test_a_partly_verified_person_names_the_latest_verification(
    dart_leader: User, verifier: User
) -> None:
    """Verified *No*, with the verifier and the day of the most recent item verified."""
    profile = person()
    profile.photo_id_verified_at = datetime(2026, 9, 1, 19, 0, tzinfo=UTC)
    profile.photo_id_verified_by = verifier
    profile.medical_verified_at = STAMP
    profile.medical_verified_by = dart_leader
    profile.save()
    assert cells("People", "Pat Doe")[7:] == ["No", "Jordan Keel", "09/20/2026"]


def test_verified_insurance_names_who_verified_it_and_when(dart_leader: User) -> None:
    """The insurance row carries the same three cells."""
    AircraftFactory(
        n_number="N123AB", insurance_verified_at=STAMP, insurance_verified_by=dart_leader
    )
    row = cells("Aircraft insurance", "N123AB", {"status": "verified"})
    assert row[7:] == ["Yes", "Jordan Keel", "09/20/2026"]


def test_a_person_whose_verifier_is_gone_still_reads_verified() -> None:
    """A deleted verifier's account leaves the stamp and a blank name."""
    profile = person()
    for slug in ("certificate", "medical", "photo_id"):
        setattr(profile, f"{slug}_verified_at", STAMP)
    profile.save()
    assert cells("People", "Pat Doe", {"status": "verified"})[7:] == ["Yes", "", "09/20/2026"]


def test_the_section_cell_carries_the_section() -> None:
    """The flat CSV keeps each row's section in its first cell."""
    person()
    AircraftFactory(n_number="N123AB")
    table = VERIFICATION_REPORT.table({"columns": ALL_COLUMNS}, fmt="csv", today=TODAY)
    assert [row[0] for row in table.rows] == SECTION_TITLES


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
        ("People", "Nia Pilot"),
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
    """With nothing given, the PDF subtitle says the items not yet verified are listed."""
    assert VERIFICATION_REPORT.query({}).filters == {"Showing": "Not yet verified"}


@pytest.mark.parametrize(("status", "words"), [("verified", "Verified"), ("all", "Everything")])
def test_each_status_is_named_in_words(status: str, words: str) -> None:
    """The subtitle names the status as a reader would say it."""
    assert VERIFICATION_REPORT.query({"status": status}).filters == {"Showing": words}


def test_the_report_names_the_filters_it_applied(dart: Dart) -> None:
    """Status and the DART by name, in that order, and nothing it does not read."""
    query = VERIFICATION_REPORT.query({"dart": str(dart.pk), "status": "all", "page": "2"})
    assert query.filters == {"Showing": "Everything", "DART": dart.name}


def test_a_dart_given_by_part_of_its_name_is_named_as_given() -> None:
    """A name fragment names no one DART, so the subtitle repeats it."""
    assert VERIFICATION_REPORT.query({"dart": "south"}).filters == {
        "Showing": "Not yet verified",
        "DART": "south",
    }


def test_the_pdf_subtitle_reads_in_words(
    account_admin_client: APIClient, pdf_text: PdfText
) -> None:
    """The line under the title reads *Showing: Not yet verified*."""
    strings = pdf_text(account_admin_client.get(PDF_URL).content)[0]
    assert strings[1] == "Showing: Not yet verified"


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


def test_the_csv_lists_everything_requiring_validation_under_its_section(
    api_client: APIClient, dart_leader: User
) -> None:
    """A DART leader's download lists the member once and the aircraft once."""
    person("Pat", "Doe")
    AircraftFactory(n_number="N123AB")
    api_client.force_login(dart_leader)
    table = read_csv(api_client.get(CSV_URL, {"columns": "section,name,verified"}))
    assert table == [
        ["Section", "Name", "Verified"],
        ["People", "Pat Doe", "No"],
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
    assert strings[2:4] == ["People", "Nothing to show."]


def subscribe(client: APIClient, recipient: User) -> ApiResponse:
    """Subscribe ``recipient`` to the monthly verification PDF; the response."""
    return client.post(
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


def test_the_report_can_be_sent_to_a_verifier(
    account_admin_client: APIClient, verifier: User
) -> None:
    """A verifier reads the report, so a subscription for one is set up."""
    assert subscribe(account_admin_client, verifier).status_code == 201


def test_the_report_cannot_be_sent_to_a_treasurer(
    account_admin_client: APIClient, treasurer: User
) -> None:
    """A treasurer holds no verifying role, so sending the report to one is refused."""
    response = subscribe(account_admin_client, treasurer)
    assert response.status_code == 400
    assert response.json() == {
        "recipient_email": [
            f"{treasurer.display_name} does not hold a role that may read this report."
        ]
    }
