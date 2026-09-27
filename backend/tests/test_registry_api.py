"""The aircraft types and registry endpoints: search, Add a type, lookup, and status.

``docs/developer/api-aircraft.rst`` is the contract.  The search and lookup tests read
the registry fixture, imported as the seed imports it.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from django.utils import timezone
from pytest_django import Settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import ACCOUNT_ADMIN, SYSTEM_ADMIN
from apps.aircraft.models import AircraftType, Registration, RegistryImport
from apps.aircraft.registry import FIXTURE_DIR, import_registry
from tests.conftest import role_matrix
from tests.factories import AircraftTypeFactory

pytestmark = pytest.mark.django_db

TYPES_URL = "/api/v1/aircraft/types"
REGISTRY_URL = "/api/v1/aircraft/registry"

#: A registration the fixture holds: a Cessna 172S built in 1999.
FIXTURE_N_NUMBER = "N128SC"


def registration_url(n_number: str) -> str:
    """The lookup URL for ``n_number``, as typed."""
    return f"{REGISTRY_URL}/{n_number}"


@pytest.fixture
def registry() -> RegistryImport:
    """The fixture registry, imported as the seed imports it."""
    return import_registry(str(FIXTURE_DIR))


@pytest.fixture
def member_client(api_client: APIClient, member: User) -> APIClient:
    """A client signed in as a plain member."""
    api_client.force_login(member)
    return api_client


def _leading(client: APIClient, query: str) -> str:
    """``<make> <model>`` of the first type ``GET /aircraft/types?q=`` answers."""
    first = client.get(TYPES_URL, {"q": query}).json()[0]
    return f"{first['make']} {first['model']}"


# -- search ---------------------------------------------------------------------------


@pytest.mark.parametrize("query", ["cesna 172", "CESSNA 172", "c172", "CESSNA", "cesna", "skyhawk"])
def test_every_spelling_of_a_cessna_172_leads_with_it(
    registry: RegistryImport, member_client: APIClient, query: str
) -> None:
    """However the 172 is typed, the registry's Cessna 172 comes first."""
    assert _leading(member_client, query) == "Cessna 172"


def test_eurofox_finds_the_aeropro_eurofox(
    registry: RegistryImport, member_client: APIClient
) -> None:
    """A type built outside the United States is found by its name."""
    assert _leading(member_client, "eurofox") == "Aeropro Eurofox"


def test_a_search_answers_the_documented_fields(
    registry: RegistryImport, member_client: APIClient
) -> None:
    """Each result is ``{id, make, model, seats, engines, is_custom}``."""
    first = member_client.get(TYPES_URL, {"q": "eurofox"}).json()[0]
    assert set(first) == {"id", "make", "model", "seats", "engines", "is_custom"}


def test_a_blank_search_answers_an_empty_list(member_client: APIClient) -> None:
    """``q`` blank answers ``[]``."""
    assert member_client.get(TYPES_URL, {"q": " "}).json() == []


def test_searching_needs_a_signed_in_user(api_client: APIClient) -> None:
    """An anonymous caller is refused."""
    assert api_client.get(TYPES_URL, {"q": "cessna"}).status_code == 401


# -- Add a type -----------------------------------------------------------------------


def test_an_account_admin_adds_a_custom_type(account_admin_client: APIClient) -> None:
    """A type the FAA has never registered is added, marked custom, and answered 201."""
    response = account_admin_client.post(
        TYPES_URL, {"make": "zenith", "model": "ch 750", "seats": 2, "engines": 1}
    )
    assert (response.status_code, response.json()["is_custom"]) == (201, True)


def test_an_added_type_takes_display_names(account_admin_client: APIClient) -> None:
    """The make and model are written as the registry's would be."""
    response = account_admin_client.post(TYPES_URL, {"make": "cessna aircraft co", "model": "t-51"})
    assert (response.json()["make"], response.json()["model"]) == ("Cessna", "T-51")


def test_an_added_type_is_coded_by_its_id(account_admin_client: APIClient) -> None:
    """A custom type's FAA code is ``CUSTOM-<id>``."""
    created = account_admin_client.post(TYPES_URL, {"make": "Zenith", "model": "CH 750"}).json()
    assert AircraftType.objects.get(pk=created["id"]).faa_code == f"CUSTOM-{created['id']}"


def test_seats_and_engines_are_optional(account_admin_client: APIClient) -> None:
    """A type added without seats or engines leaves them null."""
    created = account_admin_client.post(TYPES_URL, {"make": "Zenith", "model": "CH 750"}).json()
    assert (created["seats"], created["engines"]) == (None, None)


@pytest.mark.parametrize(("make", "model"), [("Cessna", "172S"), ("CESSNA", "172s")])
def test_a_type_already_listed_is_refused(
    account_admin_client: APIClient, make: str, model: str
) -> None:
    """A make and model already listed, in any case, is refused under ``model``."""
    AircraftTypeFactory(make="Cessna", model="172S")
    response = account_admin_client.post(TYPES_URL, {"make": make, "model": model})
    assert (response.status_code, response.json()) == (
        400,
        {"model": ["That aircraft type is already listed."]},
    )


@pytest.mark.parametrize("make", ["Inc.", "."])
def test_a_make_that_normalizes_to_blank_is_refused(
    account_admin_client: APIClient, make: str
) -> None:
    """A corporate suffix or bare punctuation alone is refused under ``make``."""
    response = account_admin_client.post(TYPES_URL, {"make": make, "model": "CH 750"})
    assert (response.status_code, response.json()) == (
        400,
        {"make": ["Enter a name, not only a corporate suffix or punctuation."]},
    )


@pytest.mark.parametrize("missing", ["make", "model"])
def test_make_and_model_are_required(account_admin_client: APIClient, missing: str) -> None:
    """Both names are needed."""
    body = {"make": "Zenith", "model": "CH 750"}
    body.pop(missing)
    response = account_admin_client.post(TYPES_URL, body)
    assert (response.status_code, list(response.json())) == (400, [missing])


@pytest.mark.parametrize(("slug", "allowed"), role_matrix(ACCOUNT_ADMIN, SYSTEM_ADMIN))
def test_role_matrix_for_adding_a_type(
    api_client: APIClient, all_role_users: dict[str, User], slug: str, allowed: bool
) -> None:
    """Only account and system administrators add a type; every other role gets 403."""
    api_client.force_login(all_role_users[slug])
    response = api_client.post(TYPES_URL, {"make": "Zenith", "model": f"CH {slug}"})
    assert response.status_code == (201 if allowed else 403)


# -- lookup ---------------------------------------------------------------------------


def test_a_lookup_answers_the_registration(
    registry: RegistryImport, member_client: APIClient
) -> None:
    """A registered N-number answers its type, year, registrant, and dates."""
    body = member_client.get(registration_url(FIXTURE_N_NUMBER)).json()
    assert (body["n_number"], body["type"]["make"], body["type"]["model"], body["year"]) == (
        "N128SC",
        "Cessna",
        "172S",
        1999,
    )


def test_a_lookup_answers_the_documented_fields(
    registry: RegistryImport, member_client: APIClient
) -> None:
    """The answer carries every field the contract names."""
    body = member_client.get(registration_url(FIXTURE_N_NUMBER)).json()
    assert set(body) == {
        "n_number",
        "type",
        "year",
        "registrant_name",
        "registrant_type",
        "status",
        "certificate_issued_on",
        "expires_on",
        "imported_at",
    }


@pytest.mark.parametrize("typed", ["n128sc", "128SC", "N-128-SC"])
def test_a_lookup_normalizes_the_n_number(
    registry: RegistryImport, member_client: APIClient, typed: str
) -> None:
    """The N-number is found however it is typed."""
    assert member_client.get(registration_url(typed)).json()["n_number"] == "N128SC"


def test_an_unregistered_n_number_answers_404(member_client: APIClient) -> None:
    """A miss names the N-number it looked for."""
    response = member_client.get(registration_url("n99999"))
    assert (response.status_code, response.json()) == (
        404,
        {"detail": "No registration for N99999 in the registry."},
    )


def test_a_blank_n_number_answers_400(member_client: APIClient) -> None:
    """An N-number that normalizes to nothing is refused as the register refuses it."""
    response = member_client.get(registration_url("--"))
    assert (response.status_code, response.json()) == (
        400,
        {"n_number": "Enter a registration, for example N12345."},
    )


def test_a_lookup_needs_a_signed_in_user(api_client: APIClient) -> None:
    """An anonymous caller is refused."""
    assert api_client.get(registration_url(FIXTURE_N_NUMBER)).status_code == 401


# -- status ---------------------------------------------------------------------------


def test_the_status_before_any_import_is_empty(member_client: APIClient) -> None:
    """With no import, there is no date, nothing running, and no last run."""
    assert member_client.get(REGISTRY_URL).json() == {"as_of": None, "running": False, "last": None}


def test_the_status_is_as_of_the_newest_successful_import(
    registry: RegistryImport, member_client: APIClient
) -> None:
    """``as_of`` is when the newest successful import finished."""
    RegistryImport.objects.create(
        finished_at=timezone.now() + timedelta(minutes=5), ok=False, error="Boom."
    )
    as_of = member_client.get(REGISTRY_URL).json()["as_of"]
    assert datetime.fromisoformat(as_of) == registry.finished_at


def test_the_status_reports_the_last_run_whatever_its_outcome(
    registry: RegistryImport, member_client: APIClient
) -> None:
    """``last`` is the newest import row, a failed one included."""
    RegistryImport.objects.create(
        started_at=timezone.now() + timedelta(minutes=1),
        finished_at=timezone.now() + timedelta(minutes=2),
        ok=False,
        error="Boom.",
    )
    last = member_client.get(REGISTRY_URL).json()["last"]
    assert (last["ok"], last["error"]) == (False, "Boom.")


def test_the_status_carries_the_last_runs_counts(
    registry: RegistryImport, member_client: APIClient
) -> None:
    """``last`` names the counts, the source, and the times."""
    last = member_client.get(REGISTRY_URL).json()["last"]
    assert (
        last["types_written"],
        last["registrations_written"],
        last["types_folded"],
        last["source"],
    ) == (330, 210, 0, str(FIXTURE_DIR))


def test_the_status_reads_running_while_an_import_is_under_way(
    member_client: APIClient,
) -> None:
    """An unfinished import younger than the stale limit reads as running."""
    RegistryImport.objects.create(source="https://example.test/registry.zip")
    assert member_client.get(REGISTRY_URL).json()["running"] is True


def test_a_stale_unfinished_import_is_not_running(
    member_client: APIClient, settings: Settings
) -> None:
    """An unfinished import older than the stale limit is not running."""
    settings.REGISTRY_IMPORT_STALE_MINUTES = 30
    RegistryImport.objects.create(started_at=timezone.now() - timedelta(minutes=31))
    assert member_client.get(REGISTRY_URL).json()["running"] is False


def test_the_status_needs_a_signed_in_user(api_client: APIClient) -> None:
    """An anonymous caller is refused."""
    assert api_client.get(REGISTRY_URL).status_code == 401


def test_the_registry_holds_the_lookup_target_once(registry: RegistryImport) -> None:
    """The fixture N-number the lookup tests read is a registration."""
    assert Registration.objects.filter(n_number=FIXTURE_N_NUMBER).count() == 1
