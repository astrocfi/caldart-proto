"""The aircraft register API: CRUD, permissions, normalization and filters.

Exports live in ``test_aircraft_exports.py`` and the leader check in
``test_leader_api.py``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import ACCOUNT_ADMIN, MEMBER, SYSTEM_ADMIN
from apps.aircraft.models import Aircraft
from apps.members.models import MemberProfile
from tests.conftest import RegisterDict, role_matrix
from tests.factories import AircraftFactory, MemberProfileFactory, UserFactory

if TYPE_CHECKING:
    # rest_framework.test.APIClient.get() is typed to return this class, but it
    # exists only in the stub: rest_framework monkey-patches Django's test response
    # at runtime rather than defining a real subclass.
    from rest_framework.response import _MonkeyPatchedResponse as ApiResponse

pytestmark = pytest.mark.django_db

LIST_URL = "/api/v1/aircraft"
LOOKUP_URL = "/api/v1/aircraft/lookup"


def detail_url(aircraft: Aircraft) -> str:
    """Build the detail URL for one aircraft."""
    return f"/api/v1/aircraft/{aircraft.pk}"


def valid_payload(**overrides: Any) -> dict[str, Any]:
    """A complete, valid aircraft-creation payload, with ``overrides`` merged in."""
    payload: dict[str, Any] = {
        "n_number": "N4321Q",
        "make": "Cirrus",
        "model": "SR22",
        "year": 2019,
        "owner_type": "individual",
        "owner_name": "Marta Reyes",
        "seats": 4,
        "insurance_carrier": "Avemco",
        "insurance_liability_per_occurrence_cents": 100_000_000,
        "insurance_liability_per_person_cents": 10_000_000,
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------------
# Authentication
# --------------------------------------------------------------------------
def test_list_requires_authentication(api_client: APIClient) -> None:
    """An anonymous caller gets 401, never 403, listing the register."""
    # Unauthenticated API requests are 401, never 403.
    assert api_client.get(LIST_URL).status_code == 401


def test_create_requires_authentication(api_client: APIClient) -> None:
    """An anonymous caller gets 401 creating an aircraft."""
    assert api_client.post(LIST_URL, valid_payload()).status_code == 401


def test_lookup_requires_authentication(api_client: APIClient, aircraft: Aircraft) -> None:
    """An anonymous caller gets 401 looking up an aircraft."""
    assert api_client.get(LOOKUP_URL, {"n_number": aircraft.n_number}).status_code == 401


# --------------------------------------------------------------------------
# Read
# --------------------------------------------------------------------------
def test_any_member_may_list_the_register(
    api_client: APIClient, member: User, aircraft: Aircraft
) -> None:
    """Any member lists the register and sees the insurance fields on each row."""
    api_client.force_login(member)
    response = api_client.get(LIST_URL)
    assert response.status_code == 200
    assert response.json()["count"] == 1
    row = response.json()["results"][0]
    assert row["n_number"] == aircraft.n_number
    assert row["insurance_is_current"] is True
    assert "insurance_summary" in row


def test_detail_shows_the_attached_pilots_to_a_leader(
    api_client: APIClient, dart_leader: User, aircraft: Aircraft, profile: MemberProfile
) -> None:
    """A DART leader sees attached pilots and their medical status on the detail view."""
    profile.aircraft.add(aircraft)
    api_client.force_login(dart_leader)
    response = api_client.get(detail_url(aircraft))
    assert response.status_code == 200
    assert [pilot["user_id"] for pilot in response.json()["pilots"]] == [profile.user_id]
    assert response.json()["pilots"][0]["medical_is_current"] is True


def test_detail_shows_the_attached_pilots_to_an_account_admin(
    api_client: APIClient, account_admin: User, aircraft: Aircraft, profile: MemberProfile
) -> None:
    """An account admin also sees the attached pilots on detail."""
    profile.aircraft.add(aircraft)
    api_client.force_login(account_admin)
    response = api_client.get(detail_url(aircraft))
    assert [pilot["user_id"] for pilot in response.json()["pilots"]] == [profile.user_id]


@pytest.mark.parametrize("url_for", [detail_url, lambda a: f"{LOOKUP_URL}?n_number={a.n_number}"])
def test_a_plain_member_never_learns_who_else_flies_an_aircraft(
    api_client: APIClient,
    member: User,
    aircraft: Aircraft,
    profile: MemberProfile,
    url_for: Callable[[Aircraft], str],
) -> None:
    """``pilots`` carries email, membership and medical: that is leader-check data."""
    profile.aircraft.add(aircraft)
    other = UserFactory(email="other@example.test", roles=[MEMBER])
    api_client.force_login(other)
    response = api_client.get(url_for(aircraft))
    assert response.status_code == 200
    assert "pilots" not in response.json()
    assert response.json()["n_number"] == aircraft.n_number


def test_lookup_shows_the_pilots_to_a_leader(
    api_client: APIClient, dart_leader: User, aircraft: Aircraft, profile: MemberProfile
) -> None:
    """Lookup, like detail, shows the attached pilots to a DART leader."""
    profile.aircraft.add(aircraft)
    api_client.force_login(dart_leader)
    response = api_client.get(LOOKUP_URL, {"n_number": aircraft.n_number})
    assert [pilot["user_id"] for pilot in response.json()["pilots"]] == [profile.user_id]


def test_list_is_paginated_and_ordered_by_n_number(api_client: APIClient, member: User) -> None:
    """The list defaults to ascending N-number order and the standard page envelope."""
    AircraftFactory(n_number="N900ZZ")
    AircraftFactory(n_number="N100AA")
    api_client.force_login(member)
    response = api_client.get(LIST_URL)
    assert [row["n_number"] for row in response.json()["results"]] == ["N100AA", "N900ZZ"]
    assert set(response.json()) == {"count", "next", "previous", "results"}


# --------------------------------------------------------------------------
# Create
# --------------------------------------------------------------------------
def test_member_can_add_an_aircraft_and_becomes_its_creator(
    api_client: APIClient, member: User
) -> None:
    """Creating an aircraft succeeds and records the caller as its creator."""
    api_client.force_login(member)
    response = api_client.post(LIST_URL, valid_payload())
    assert response.status_code == 201
    aircraft = Aircraft.objects.get(pk=response.json()["id"])
    assert aircraft.created_by == member
    assert response.json()["created_by"] == member.pk


@pytest.mark.parametrize(
    ("typed", "stored"),
    [
        ("12345", "N12345"),
        ("n12345", "N12345"),
        ("N-12345", "N12345"),
        ("  n-172 sp ", "N172SP"),
        ("737wt", "N737WT"),
    ],
)
def test_n_number_is_normalized_on_write(
    api_client: APIClient, member: User, typed: str, stored: str
) -> None:
    """Creating an aircraft normalizes the N-number the same way as the model."""
    api_client.force_login(member)
    response = api_client.post(LIST_URL, valid_payload(n_number=typed))
    assert response.status_code == 201, response.json()
    assert response.json()["n_number"] == stored
    assert Aircraft.objects.filter(n_number=stored).exists()


def test_duplicate_n_number_is_rejected_after_normalization(
    api_client: APIClient, member: User
) -> None:
    """A new N-number normalizing to an existing one is rejected with a clear message."""
    AircraftFactory(n_number="N12345")
    api_client.force_login(member)
    response = api_client.post(LIST_URL, valid_payload(n_number="n-12345"))
    assert response.status_code == 400
    assert "already on file" in str(response.json()["n_number"][0])


@pytest.mark.parametrize("blank", ["", "   ", "---"])
def test_blank_n_number_is_rejected(api_client: APIClient, member: User, blank: str) -> None:
    """An N-number that normalizes to an empty string is rejected."""
    api_client.force_login(member)
    response = api_client.post(LIST_URL, valid_payload(n_number=blank))
    assert response.status_code == 400
    assert "n_number" in response.json()


@pytest.mark.parametrize("field", ["make", "model"])
def test_make_and_model_are_required(api_client: APIClient, member: User, field: str) -> None:
    """Omitting or blanking ``make`` or ``model`` is a 400 naming that field."""
    api_client.force_login(member)
    payload = valid_payload()
    del payload[field]
    assert api_client.post(LIST_URL, payload).status_code == 400

    payload = valid_payload(**{field: ""})
    response = api_client.post(LIST_URL, payload)
    assert response.status_code == 400
    assert field in response.json()


@pytest.mark.parametrize(
    "field",
    [
        "insurance_liability_per_occurrence_cents",
        "insurance_liability_per_person_cents",
        "insurance_hull_cents",
    ],
)
def test_money_fields_must_not_be_negative(api_client: APIClient, member: User, field: str) -> None:
    """A negative amount in any money field is rejected with a "$0 or more" message."""
    api_client.force_login(member)
    response = api_client.post(LIST_URL, valid_payload(**{field: -1}))
    assert response.status_code == 400
    assert "$0 or more" in str(response.json()[field][0])


def test_created_by_cannot_be_spoofed(
    api_client: APIClient, member: User, account_admin: User
) -> None:
    """A ``created_by`` value in the body is ignored; the server sets the caller."""
    api_client.force_login(member)
    response = api_client.post(LIST_URL, valid_payload(created_by=account_admin.pk))
    assert response.status_code == 201
    assert Aircraft.objects.get(pk=response.json()["id"]).created_by == member


# --------------------------------------------------------------------------
# Update
# --------------------------------------------------------------------------
def test_creator_may_update_their_own_aircraft(api_client: APIClient, member: User) -> None:
    """The member who created an aircraft may patch it."""
    aircraft = AircraftFactory(n_number="N55CR", created_by=member)
    api_client.force_login(member)
    response = api_client.patch(detail_url(aircraft), {"model": "182T Skylane II"})
    assert response.status_code == 200
    aircraft.refresh_from_db()
    assert aircraft.model == "182T Skylane II"


def test_another_member_may_not_update_someone_elses_aircraft(
    api_client: APIClient, member: User
) -> None:
    """A member who did not create the aircraft gets 403 patching it; nothing changes."""
    owner = UserFactory(email="owner@example.test", roles=[MEMBER])
    aircraft = AircraftFactory(n_number="N56CR", created_by=owner)
    api_client.force_login(member)
    response = api_client.patch(detail_url(aircraft), {"model": "hijacked"})
    assert response.status_code == 403
    aircraft.refresh_from_db()
    assert aircraft.model != "hijacked"


def test_nobody_owns_an_aircraft_created_by_the_seed(api_client: APIClient, member: User) -> None:
    """An aircraft with no creator (seeded) cannot be patched by a plain member."""
    aircraft = AircraftFactory(n_number="N57CR", created_by=None)
    api_client.force_login(member)
    assert api_client.patch(detail_url(aircraft), {"model": "x"}).status_code == 403


def test_account_admin_may_update_any_aircraft(
    api_client: APIClient, account_admin: User, member: User
) -> None:
    """An account admin may patch an aircraft created by someone else."""
    aircraft = AircraftFactory(n_number="N58CR", created_by=member)
    api_client.force_login(account_admin)
    response = api_client.patch(detail_url(aircraft), {"insurance_carrier": "USAIG"})
    assert response.status_code == 200
    aircraft.refresh_from_db()
    assert aircraft.insurance_carrier == "USAIG"


def test_system_admin_may_update_any_aircraft(
    api_client: APIClient, system_admin: User, member: User
) -> None:
    """A system admin may patch an aircraft created by someone else."""
    aircraft = AircraftFactory(n_number="N59CR", created_by=member)
    api_client.force_login(system_admin)
    assert api_client.patch(detail_url(aircraft), {"owner_name": "Club"}).status_code == 200


def test_update_normalizes_a_retyped_n_number(api_client: APIClient, account_admin: User) -> None:
    """Patching the N-number normalizes the new value the same way as creation."""
    aircraft = AircraftFactory(n_number="N60CR")
    api_client.force_login(account_admin)
    response = api_client.patch(detail_url(aircraft), {"n_number": "n-61cr"})
    assert response.status_code == 200
    aircraft.refresh_from_db()
    assert aircraft.n_number == "N61CR"


def test_update_keeping_the_same_n_number_is_not_a_duplicate(
    api_client: APIClient, account_admin: User
) -> None:
    """Patching an aircraft with its own (differently typed) N-number is not rejected."""
    aircraft = AircraftFactory(n_number="N62CR")
    api_client.force_login(account_admin)
    response = api_client.patch(detail_url(aircraft), {"n_number": "62cr", "make": "Piper"})
    assert response.status_code == 200, response.json()
    aircraft.refresh_from_db()
    assert (aircraft.n_number, aircraft.make) == ("N62CR", "Piper")


# --------------------------------------------------------------------------
# Delete
# --------------------------------------------------------------------------
def test_creator_may_not_delete_their_aircraft(api_client: APIClient, member: User) -> None:
    """The member who created an aircraft still cannot delete it."""
    aircraft = AircraftFactory(n_number="N70DL", created_by=member)
    api_client.force_login(member)
    assert api_client.delete(detail_url(aircraft)).status_code == 403
    assert Aircraft.objects.filter(pk=aircraft.pk).exists()


def test_dart_leader_may_not_delete_an_aircraft(api_client: APIClient, dart_leader: User) -> None:
    """A DART leader gets 403 deleting an aircraft."""
    aircraft = AircraftFactory(n_number="N71DL")
    api_client.force_login(dart_leader)
    assert api_client.delete(detail_url(aircraft)).status_code == 403


def test_account_admin_may_delete_an_aircraft(api_client: APIClient, account_admin: User) -> None:
    """An account admin deletes an aircraft and it no longer exists."""
    aircraft = AircraftFactory(n_number="N72DL")
    api_client.force_login(account_admin)
    assert api_client.delete(detail_url(aircraft)).status_code == 204
    assert not Aircraft.objects.filter(pk=aircraft.pk).exists()


@pytest.mark.parametrize(("slug", "allowed"), role_matrix(ACCOUNT_ADMIN, SYSTEM_ADMIN))
def test_role_matrix_for_delete(
    api_client: APIClient, all_role_users: dict[str, User], slug: str, allowed: bool
) -> None:
    """Only account and system admins get 204 deleting; every other role gets 403."""
    aircraft = AircraftFactory(n_number="N800RM")
    api_client.force_login(all_role_users[slug])
    response = api_client.delete(detail_url(aircraft))
    assert response.status_code == (204 if allowed else 403)


# --------------------------------------------------------------------------
# Lookup
# --------------------------------------------------------------------------
@pytest.mark.parametrize("typed", ["N172SP", "n172sp", "n-172-sp", " 172sp "])
def test_lookup_finds_an_aircraft_however_the_n_number_is_typed(
    api_client: APIClient, member: User, typed: str
) -> None:
    """Lookup finds the aircraft regardless of how the N-number is typed or cased."""
    AircraftFactory(n_number="N172SP")
    api_client.force_login(member)
    response = api_client.get(LOOKUP_URL, {"n_number": typed})
    assert response.status_code == 200
    assert response.json()["n_number"] == "N172SP"


def test_lookup_404s_for_an_unknown_n_number(api_client: APIClient, member: User) -> None:
    """Looking up an N-number with no matching aircraft returns 404."""
    api_client.force_login(member)
    assert api_client.get(LOOKUP_URL, {"n_number": "N0000X"}).status_code == 404


def test_lookup_without_an_n_number_is_a_400(api_client: APIClient, member: User) -> None:
    """Looking up with no ``n_number`` query parameter returns 400 naming that field."""
    api_client.force_login(member)
    response = api_client.get(LOOKUP_URL)
    assert response.status_code == 400
    assert "n_number" in response.json()


def test_lookup_is_exact_not_a_prefix_match(api_client: APIClient, member: User) -> None:
    """A prefix of a real N-number does not match the full aircraft."""
    AircraftFactory(n_number="N172SP")
    api_client.force_login(member)
    assert api_client.get(LOOKUP_URL, {"n_number": "N172"}).status_code == 404


# --------------------------------------------------------------------------
# Filters
# --------------------------------------------------------------------------
def numbers(response: ApiResponse) -> list[str]:
    """Extract the ``n_number`` of each row in a paginated list response, in order."""
    return [row["n_number"] for row in response.json()["results"]]


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("172sp", ["N172SP"]),
        ("n-172-sp", ["N172SP"]),
        ("9021", ["N9021K"]),
        ("mooney", ["N33MM"]),
        ("Archer", ["N9021K"]),
        ("Delgado", ["N33MM"]),
        ("flying club", ["N172SP"]),
    ],
)
def test_search_filter_matches_every_searchable_column(
    api_client: APIClient, member: User, register: RegisterDict, query: str, expected: list[str]
) -> None:
    """The ``search`` filter matches N-number, make, model, owner name and free text."""
    api_client.force_login(member)
    assert numbers(api_client.get(LIST_URL, {"search": query})) == expected


def test_make_filter_matches_case_insensitively(
    api_client: APIClient, member: User, register: RegisterDict
) -> None:
    """The ``make`` filter matches case-insensitively on the aircraft's make."""
    api_client.force_login(member)
    assert numbers(api_client.get(LIST_URL, {"make": "cessna"})) == ["N172SP"]


def test_owner_type_filter(api_client: APIClient, member: User, register: RegisterDict) -> None:
    """The ``owner_type`` filter restricts the list to that exact owner type."""
    api_client.force_login(member)
    assert numbers(api_client.get(LIST_URL, {"owner_type": "fbo"})) == ["N44BE"]
    assert numbers(api_client.get(LIST_URL, {"owner_type": "club"})) == ["N172SP"]


def test_owner_type_filter_rejects_an_unknown_choice(
    api_client: APIClient, member: User, register: RegisterDict
) -> None:
    """An ``owner_type`` value outside the declared choices returns 400."""
    api_client.force_login(member)
    assert api_client.get(LIST_URL, {"owner_type": "airline"}).status_code == 400


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("current", ["N172SP", "N9021K"]),
        ("expired", ["N33MM"]),
        ("missing", ["N44BE"]),
    ],
)
def test_insurance_filter(
    api_client: APIClient, member: User, register: RegisterDict, state: str, expected: list[str]
) -> None:
    """The ``insurance`` filter buckets aircraft as current, expired or missing cover."""
    api_client.force_login(member)
    assert sorted(numbers(api_client.get(LIST_URL, {"insurance": state}))) == sorted(expected)


def test_expiring_within_excludes_already_expired_cover(
    api_client: APIClient, member: User, register: RegisterDict
) -> None:
    """``expiring_within`` excludes cover that already expired, even inside the window."""
    api_client.force_login(member)
    assert numbers(api_client.get(LIST_URL, {"expiring_within": 30})) == ["N9021K"]


def test_expiring_within_widens_with_the_window(
    api_client: APIClient, member: User, register: RegisterDict
) -> None:
    """A wider ``expiring_within`` window includes cover expiring further out."""
    api_client.force_login(member)
    assert sorted(numbers(api_client.get(LIST_URL, {"expiring_within": 365}))) == [
        "N172SP",
        "N9021K",
    ]


def test_expiring_within_zero_days_means_expiring_today(
    api_client: APIClient, member: User, register: RegisterDict
) -> None:
    """``expiring_within=0`` matches cover expiring on today's date."""
    AircraftFactory(n_number="N88TD", insurance_expiration=timezone.localdate())
    api_client.force_login(member)
    assert numbers(api_client.get(LIST_URL, {"expiring_within": 0})) == ["N88TD"]


@pytest.mark.parametrize("window", ["999999999", "1e11", "-5"])
def test_expiring_within_survives_an_absurd_window(
    api_client: APIClient, member: User, register: RegisterDict, window: str
) -> None:
    """An overflowing timedelta would be a 500, not a filter."""
    api_client.force_login(member)
    response = api_client.get(LIST_URL, {"expiring_within": window})
    assert response.status_code == 200


def test_expiring_within_is_clamped_to_ten_years(
    api_client: APIClient, member: User, register: RegisterDict
) -> None:
    """A window far beyond ten years returns the same rows as a ten-year window."""
    api_client.force_login(member)
    wide = numbers(api_client.get(LIST_URL, {"expiring_within": "999999999"}))
    decade = numbers(api_client.get(LIST_URL, {"expiring_within": "3650"}))
    assert wide == decade


def test_is_active_filter(api_client: APIClient, member: User, register: RegisterDict) -> None:
    """``is_active`` filters the register; the default list includes inactive aircraft."""
    AircraftFactory(n_number="N77OS", is_active=False)
    api_client.force_login(member)
    assert "N77OS" in numbers(api_client.get(LIST_URL))
    assert "N77OS" not in numbers(api_client.get(LIST_URL, {"is_active": "true"}))
    assert numbers(api_client.get(LIST_URL, {"is_active": "false"})) == ["N77OS"]


def test_ordering_is_stable_across_pages(api_client: APIClient, member: User) -> None:
    """Ties on a non-unique column must not shuffle between pages."""
    for index in range(10):
        AircraftFactory(n_number=f"N{600 + index}TIE", make="Cessna", model="172S")
    api_client.force_login(member)
    query: dict[str, str | int] = {"ordering": "make", "page_size": 4}
    seen: list[str] = []
    for page in (1, 2, 3):
        seen.extend(numbers(api_client.get(LIST_URL, {**query, "page": page})))
    assert len(seen) == len(set(seen)) == 10


def test_filters_combine(api_client: APIClient, member: User, register: RegisterDict) -> None:
    """Two filters combine with AND semantics, narrowing the result further."""
    api_client.force_login(member)
    response = api_client.get(LIST_URL, {"insurance": "current", "make": "piper"})
    assert numbers(response) == ["N9021K"]


@pytest.mark.parametrize(
    ("ordering", "first"),
    [
        ("n_number", "N172SP"),
        ("-n_number", "N9021K"),
        ("make", "N44BE"),
        ("insurance_expiration", "N33MM"),
        ("-insurance_expiration", "N172SP"),
    ],
)
def test_ordering_puts_the_expected_aircraft_first(
    api_client: APIClient, member: User, register: RegisterDict, ordering: str, first: str
) -> None:
    """Each supported ``ordering`` value puts the expected aircraft first."""
    api_client.force_login(member)
    response = api_client.get(LIST_URL, {"ordering": ordering})
    assert numbers(response)[0] == first


@pytest.mark.parametrize("ordering", ["insurance_expiration", "-insurance_expiration"])
def test_aircraft_without_insurance_sort_last_either_way(
    api_client: APIClient, member: User, register: RegisterDict, ordering: str
) -> None:
    """An aircraft with no insurance expiration sorts last, ascending or descending."""
    api_client.force_login(member)
    response = api_client.get(LIST_URL, {"ordering": ordering})
    assert numbers(response)[-1] == "N44BE"


def test_search_matches_a_pilots_aircraft_only_through_the_register(
    api_client: APIClient, member: User, register: RegisterDict
) -> None:
    """The register search is about aircraft; member search is the leader check's job."""
    MemberProfileFactory(user=member).aircraft.add(register["current"])
    api_client.force_login(member)
    assert numbers(api_client.get(LIST_URL, {"search": "Reyes"})) == ["N9021K"]
