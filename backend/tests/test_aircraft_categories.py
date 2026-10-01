"""Aircraft category and airworthiness: the registry import, the record, filters, exports.

``docs/developer/aircraft-registry.rst`` describes how the import reads the two codes,
and ``docs/developer/api-aircraft.rst`` the fields.  Every registry test reads the
fixture in ``apps/aircraft/fixtures/faa``; nothing downloads from the FAA.
"""

from __future__ import annotations

from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.aircraft.models import (
    Aircraft,
    AircraftCategory,
    AircraftType,
    Airworthiness,
    Registration,
)
from apps.aircraft.registry import (
    FIXTURE_DIR,
    airworthiness_for,
    category_for,
    import_registry,
)
from tests.conftest import read_csv
from tests.factories import AircraftFactory, AircraftTypeFactory

pytestmark = pytest.mark.django_db

LIST_URL = "/api/v1/aircraft"
CSV_URL = "/api/v1/reports/aircraft/export.csv"

#: A Robinson R44 II in the fixture, holding a standard airworthiness certificate.
FIXTURE_HELICOPTER = "N781SH"

#: The fixture's Cessna 172S type code.
FIXTURE_AIRPLANE_CODE = "2072439"


@pytest.fixture
def member_client(api_client: APIClient, member: User) -> APIClient:
    """A client signed in as a plain member."""
    api_client.force_login(member)
    return api_client


@pytest.fixture
def admin_client(api_client: APIClient, account_admin: User) -> APIClient:
    """A client signed in as an account administrator."""
    api_client.force_login(account_admin)
    return api_client


def _payload(**overrides: Any) -> dict[str, Any]:
    """A valid ``POST /aircraft`` body for ``N4321Q``, with ``overrides`` merged in."""
    payload: dict[str, Any] = {
        "n_number": "N4321Q",
        "type_id": AircraftTypeFactory(make="Robinson", model="R44").pk,
    }
    payload.update(overrides)
    return payload


# -- the codes ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("1", AircraftCategory.GLIDER),
        ("2", AircraftCategory.BALLOON),
        ("3", AircraftCategory.AIRSHIP),
        ("4", AircraftCategory.AIRPLANE),
        ("5", AircraftCategory.AIRPLANE),
        ("6", AircraftCategory.HELICOPTER),
        ("7", AircraftCategory.WEIGHT_SHIFT),
        ("8", AircraftCategory.POWERED_PARACHUTE),
        ("9", AircraftCategory.GYROPLANE),
        ("H", AircraftCategory.POWERED_LIFT),
        ("h", AircraftCategory.POWERED_LIFT),
        ("O", AircraftCategory.OTHER),
        (" 6 ", AircraftCategory.HELICOPTER),
        ("", ""),
        ("Z", ""),
    ],
)
def test_each_type_acft_code_maps_to_its_category(code: str, expected: str) -> None:
    """``TYPE-ACFT`` names the category; a blank or unknown code names none."""
    assert category_for(code) == expected


@pytest.mark.parametrize(
    ("certification", "expected"),
    [
        ("1N", Airworthiness.STANDARD),
        ("2", Airworthiness.LIMITED),
        ("3", Airworthiness.RESTRICTED),
        ("4E", Airworthiness.EXPERIMENTAL),
        ("5", Airworthiness.PROVISIONAL),
        ("6130", Airworthiness.MULTIPLE),
        ("7", Airworthiness.PRIMARY),
        ("8", Airworthiness.SPECIAL_FLIGHT_PERMIT),
        ("9A", Airworthiness.LIGHT_SPORT),
        ("  1U  ", Airworthiness.STANDARD),
        ("", ""),
        ("X1", ""),
    ],
)
def test_each_certification_maps_to_its_airworthiness(certification: str, expected: str) -> None:
    """The first character of ``CERTIFICATION`` names the classification, or none."""
    assert airworthiness_for(certification) == expected


# -- the import ---------------------------------------------------------------


def test_an_imported_rotorcraft_type_is_a_helicopter() -> None:
    """The fixture's Robinson R44 II type is recorded as a helicopter."""
    import_registry(str(FIXTURE_DIR))
    assert Registration.objects.get(n_number=FIXTURE_HELICOPTER).type.category == "helicopter"


def test_an_imported_fixed_wing_type_is_an_airplane() -> None:
    """A fixed-wing reference row is recorded as an airplane."""
    import_registry(str(FIXTURE_DIR))
    assert AircraftType.objects.get(faa_code=FIXTURE_AIRPLANE_CODE).category == "airplane"


def test_the_fixture_holds_every_category() -> None:
    """Each category is the category of at least one imported type."""
    import_registry(str(FIXTURE_DIR))
    found = set(AircraftType.objects.values_list("category", flat=True))
    assert found == set(AircraftCategory.values)


def test_the_fixture_holds_every_airworthiness_and_a_blank() -> None:
    """Each classification is held by a registration, and some registrations hold none."""
    import_registry(str(FIXTURE_DIR))
    found = set(Registration.objects.values_list("airworthiness", flat=True))
    assert found == {*Airworthiness.values, ""}


def test_an_imported_registration_carries_its_airworthiness() -> None:
    """``N781SH``'s ``1N`` certification is a standard certificate."""
    import_registry(str(FIXTURE_DIR))
    assert Registration.objects.get(n_number=FIXTURE_HELICOPTER).airworthiness == "standard"


def test_a_reimport_updates_a_changed_category() -> None:
    """A type whose category was changed by hand is set back by the next import."""
    import_registry(str(FIXTURE_DIR))
    AircraftType.objects.filter(faa_code=FIXTURE_AIRPLANE_CODE).update(category="glider")
    import_registry(str(FIXTURE_DIR))
    assert AircraftType.objects.get(faa_code=FIXTURE_AIRPLANE_CODE).category == "airplane"


def test_the_registry_lookup_answers_the_category_and_airworthiness(
    member_client: APIClient,
) -> None:
    """``GET /aircraft/registry/{n}`` carries both, which is what prefills the form."""
    import_registry(str(FIXTURE_DIR))
    body = member_client.get(f"/api/v1/aircraft/registry/{FIXTURE_HELICOPTER}").json()
    assert (body["type"]["category"], body["airworthiness"]) == ("helicopter", "standard")


def test_the_type_search_answers_the_category(member_client: APIClient) -> None:
    """A type in the type picker's list carries its category."""
    AircraftTypeFactory(make="Robinson", model="R44", category="helicopter")
    body = member_client.get("/api/v1/aircraft/types", {"q": "robinson r44"}).json()
    assert body[0]["category"] == "helicopter"


# -- the record ---------------------------------------------------------------


def test_an_aircraft_is_added_with_its_category_and_airworthiness(
    member_client: APIClient,
) -> None:
    """Both are written on create and read back."""
    response = member_client.post(
        LIST_URL, _payload(category="helicopter", airworthiness="standard"), format="json"
    )
    assert (response.json()["category"], response.json()["airworthiness"]) == (
        "helicopter",
        "standard",
    )


def test_an_aircraft_added_without_them_records_neither(member_client: APIClient) -> None:
    """Both are optional, and blank when left out."""
    response = member_client.post(LIST_URL, _payload(), format="json")
    stored = Aircraft.objects.get(pk=response.json()["id"])
    assert (stored.category, stored.airworthiness) == ("", "")


@pytest.mark.parametrize("field", ["category", "airworthiness"])
def test_an_unknown_value_is_refused(member_client: APIClient, field: str) -> None:
    """A value outside the choice list is a 400 naming the field."""
    response = member_client.post(LIST_URL, _payload(**{field: "spaceship"}), format="json")
    assert (response.status_code, list(response.json())) == (400, [field])


def test_an_edit_records_the_category_in_the_history(admin_client: APIClient) -> None:
    """Changing the category is a change the record's history names."""
    aircraft = AircraftFactory()
    admin_client.patch(f"{LIST_URL}/{aircraft.pk}", {"category": "glider"}, format="json")
    assert aircraft.changes.get().fields == ["category"]


def test_the_profile_summary_carries_the_category(member_client: APIClient) -> None:
    """The short form My aircraft and the member check read carries both values."""
    aircraft = AircraftFactory(category="gyroplane", airworthiness="experimental")
    response = member_client.post(
        "/api/v1/me/profile/aircraft", {"aircraft_id": aircraft.pk}, format="json"
    )
    summary = response.json()["aircraft"][0]
    assert (summary["category"], summary["airworthiness"]) == ("gyroplane", "experimental")


# -- filters and exports ------------------------------------------------------


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ({"category": "helicopter"}, ["N1HE"]),
        ({"airworthiness": "experimental"}, ["N2EX"]),
        ({"category": "airplane", "airworthiness": "standard"}, ["N3ST"]),
    ],
    ids=["category", "airworthiness", "both"],
)
def test_the_register_filters_by_category_and_airworthiness(
    member_client: APIClient, query: dict[str, str], expected: list[str]
) -> None:
    """``?category=`` and ``?airworthiness=`` narrow the register to matching rows."""
    AircraftFactory(n_number="N1HE", category="helicopter", airworthiness="standard")
    AircraftFactory(n_number="N2EX", category="airplane", airworthiness="experimental")
    AircraftFactory(n_number="N3ST", category="airplane", airworthiness="standard")
    AircraftFactory(n_number="N4NR")
    rows = member_client.get(LIST_URL, query).json()["results"]
    assert [row["n_number"] for row in rows] == expected


def test_an_unknown_category_filter_is_refused(member_client: APIClient) -> None:
    """A filter value outside the choice list is a 400."""
    assert member_client.get(LIST_URL, {"category": "spaceship"}).status_code == 400


def test_the_export_prints_the_category_and_airworthiness(admin_client: APIClient) -> None:
    """The two columns print the labels a reader sees, blank when not recorded."""
    AircraftFactory(n_number="N1HE", category="weight_shift", airworthiness="light_sport")
    AircraftFactory(n_number="N4NR")
    response = admin_client.get(CSV_URL, {"columns": "n_number,category,airworthiness"})
    assert read_csv(response) == [
        ["N-number", "Category", "Airworthiness"],
        ["N1HE", "Weight-shift control", "Light sport"],
        ["N4NR", "", ""],
    ]


def test_the_export_follows_the_category_filter(admin_client: APIClient) -> None:
    """The download holds exactly the rows the filtered register shows."""
    AircraftFactory(n_number="N1HE", category="helicopter")
    AircraftFactory(n_number="N3ST", category="airplane")
    response = admin_client.get(CSV_URL, {"columns": "n_number", "category": "helicopter"})
    assert read_csv(response) == [["N-number"], ["N1HE"]]
