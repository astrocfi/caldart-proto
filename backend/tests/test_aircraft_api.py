"""The aircraft register API: CRUD, permissions, normalization and filters.

Exports live in ``test_aircraft_exports.py`` and the leader check in
``test_leader_api.py``.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.roles import ACCOUNT_ADMIN, MEMBER, SYSTEM_ADMIN
from apps.aircraft.models import Aircraft
from tests.factories import AircraftFactory, MemberProfileFactory, UserFactory

pytestmark = pytest.mark.django_db

LIST_URL = "/api/v1/aircraft"
LOOKUP_URL = "/api/v1/aircraft/lookup"


def detail_url(aircraft: Aircraft) -> str:
    return f"/api/v1/aircraft/{aircraft.pk}"


def valid_payload(**overrides) -> dict:
    payload = {
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
def test_list_requires_authentication(api_client):
    # Unauthenticated API requests are 401, never 403.
    assert api_client.get(LIST_URL).status_code == 401


def test_create_requires_authentication(api_client):
    assert api_client.post(LIST_URL, valid_payload()).status_code == 401


def test_lookup_requires_authentication(api_client, aircraft):
    assert api_client.get(LOOKUP_URL, {"n_number": aircraft.n_number}).status_code == 401


# --------------------------------------------------------------------------
# Read
# --------------------------------------------------------------------------
def test_any_member_may_list_the_register(api_client, member, aircraft):
    api_client.force_login(member)
    response = api_client.get(LIST_URL)
    assert response.status_code == 200
    assert response.data["count"] == 1
    row = response.data["results"][0]
    assert row["n_number"] == aircraft.n_number
    assert row["insurance_is_current"] is True
    assert "insurance_summary" in row


def test_detail_shows_the_attached_pilots_to_a_leader(api_client, dart_leader, aircraft, profile):
    profile.aircraft.add(aircraft)
    api_client.force_login(dart_leader)
    response = api_client.get(detail_url(aircraft))
    assert response.status_code == 200
    assert [pilot["user_id"] for pilot in response.data["pilots"]] == [profile.user_id]
    assert response.data["pilots"][0]["medical_is_current"] is True


def test_detail_shows_the_attached_pilots_to_an_account_admin(
    api_client, account_admin, aircraft, profile
):
    profile.aircraft.add(aircraft)
    api_client.force_login(account_admin)
    response = api_client.get(detail_url(aircraft))
    assert [pilot["user_id"] for pilot in response.data["pilots"]] == [profile.user_id]


@pytest.mark.parametrize("url_for", [detail_url, lambda a: f"{LOOKUP_URL}?n_number={a.n_number}"])
def test_a_plain_member_never_learns_who_else_flies_an_aircraft(
    api_client, member, aircraft, profile, url_for
):
    """``pilots`` carries email, membership and medical: that is leader-check data."""
    profile.aircraft.add(aircraft)
    other = UserFactory(email="other@example.test", roles=[MEMBER])
    api_client.force_login(other)
    response = api_client.get(url_for(aircraft))
    assert response.status_code == 200
    assert "pilots" not in response.data
    assert response.data["n_number"] == aircraft.n_number


def test_lookup_shows_the_pilots_to_a_leader(api_client, dart_leader, aircraft, profile):
    profile.aircraft.add(aircraft)
    api_client.force_login(dart_leader)
    response = api_client.get(LOOKUP_URL, {"n_number": aircraft.n_number})
    assert [pilot["user_id"] for pilot in response.data["pilots"]] == [profile.user_id]


def test_list_is_paginated_and_ordered_by_n_number(api_client, member):
    AircraftFactory(n_number="N900ZZ")
    AircraftFactory(n_number="N100AA")
    api_client.force_login(member)
    response = api_client.get(LIST_URL)
    assert [row["n_number"] for row in response.data["results"]] == ["N100AA", "N900ZZ"]
    assert set(response.data) == {"count", "next", "previous", "results"}


# --------------------------------------------------------------------------
# Create
# --------------------------------------------------------------------------
def test_member_can_add_an_aircraft_and_becomes_its_creator(api_client, member):
    api_client.force_login(member)
    response = api_client.post(LIST_URL, valid_payload())
    assert response.status_code == 201
    aircraft = Aircraft.objects.get(pk=response.data["id"])
    assert aircraft.created_by == member
    assert response.data["created_by"] == member.pk


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
def test_n_number_is_normalized_on_write(api_client, member, typed, stored):
    api_client.force_login(member)
    response = api_client.post(LIST_URL, valid_payload(n_number=typed))
    assert response.status_code == 201, response.data
    assert response.data["n_number"] == stored
    assert Aircraft.objects.filter(n_number=stored).exists()


def test_duplicate_n_number_is_rejected_after_normalization(api_client, member):
    AircraftFactory(n_number="N12345")
    api_client.force_login(member)
    response = api_client.post(LIST_URL, valid_payload(n_number="n-12345"))
    assert response.status_code == 400
    assert "already on file" in str(response.data["n_number"][0])


@pytest.mark.parametrize("blank", ["", "   ", "---"])
def test_blank_n_number_is_rejected(api_client, member, blank):
    api_client.force_login(member)
    response = api_client.post(LIST_URL, valid_payload(n_number=blank))
    assert response.status_code == 400
    assert "n_number" in response.data


@pytest.mark.parametrize("field", ["make", "model"])
def test_make_and_model_are_required(api_client, member, field):
    api_client.force_login(member)
    payload = valid_payload()
    del payload[field]
    assert api_client.post(LIST_URL, payload).status_code == 400

    payload = valid_payload(**{field: ""})
    response = api_client.post(LIST_URL, payload)
    assert response.status_code == 400
    assert field in response.data


@pytest.mark.parametrize(
    "field",
    [
        "insurance_liability_per_occurrence_cents",
        "insurance_liability_per_person_cents",
        "insurance_hull_cents",
    ],
)
def test_money_fields_must_not_be_negative(api_client, member, field):
    api_client.force_login(member)
    response = api_client.post(LIST_URL, valid_payload(**{field: -1}))
    assert response.status_code == 400
    assert "$0 or more" in str(response.data[field][0])


def test_created_by_cannot_be_spoofed(api_client, member, account_admin):
    api_client.force_login(member)
    response = api_client.post(LIST_URL, valid_payload(created_by=account_admin.pk))
    assert response.status_code == 201
    assert Aircraft.objects.get(pk=response.data["id"]).created_by == member


# --------------------------------------------------------------------------
# Update
# --------------------------------------------------------------------------
def test_creator_may_update_their_own_aircraft(api_client, member):
    aircraft = AircraftFactory(n_number="N55CR", created_by=member)
    api_client.force_login(member)
    response = api_client.patch(detail_url(aircraft), {"model": "182T Skylane II"})
    assert response.status_code == 200
    aircraft.refresh_from_db()
    assert aircraft.model == "182T Skylane II"


def test_another_member_may_not_update_someone_elses_aircraft(api_client, member):
    owner = UserFactory(email="owner@example.test", roles=[MEMBER])
    aircraft = AircraftFactory(n_number="N56CR", created_by=owner)
    api_client.force_login(member)
    response = api_client.patch(detail_url(aircraft), {"model": "hijacked"})
    assert response.status_code == 403
    aircraft.refresh_from_db()
    assert aircraft.model != "hijacked"


def test_nobody_owns_an_aircraft_created_by_the_seed(api_client, member):
    aircraft = AircraftFactory(n_number="N57CR", created_by=None)
    api_client.force_login(member)
    assert api_client.patch(detail_url(aircraft), {"model": "x"}).status_code == 403


def test_account_admin_may_update_any_aircraft(api_client, account_admin, member):
    aircraft = AircraftFactory(n_number="N58CR", created_by=member)
    api_client.force_login(account_admin)
    response = api_client.patch(detail_url(aircraft), {"insurance_carrier": "USAIG"})
    assert response.status_code == 200
    aircraft.refresh_from_db()
    assert aircraft.insurance_carrier == "USAIG"


def test_system_admin_may_update_any_aircraft(api_client, system_admin, member):
    aircraft = AircraftFactory(n_number="N59CR", created_by=member)
    api_client.force_login(system_admin)
    assert api_client.patch(detail_url(aircraft), {"owner_name": "Club"}).status_code == 200


def test_update_normalizes_a_retyped_n_number(api_client, account_admin):
    aircraft = AircraftFactory(n_number="N60CR")
    api_client.force_login(account_admin)
    response = api_client.patch(detail_url(aircraft), {"n_number": "n-61cr"})
    assert response.status_code == 200
    aircraft.refresh_from_db()
    assert aircraft.n_number == "N61CR"


def test_update_keeping_the_same_n_number_is_not_a_duplicate(api_client, account_admin):
    aircraft = AircraftFactory(n_number="N62CR")
    api_client.force_login(account_admin)
    response = api_client.patch(detail_url(aircraft), {"n_number": "62cr", "make": "Piper"})
    assert response.status_code == 200, response.data
    aircraft.refresh_from_db()
    assert (aircraft.n_number, aircraft.make) == ("N62CR", "Piper")


# --------------------------------------------------------------------------
# Delete
# --------------------------------------------------------------------------
def test_creator_may_not_delete_their_aircraft(api_client, member):
    aircraft = AircraftFactory(n_number="N70DL", created_by=member)
    api_client.force_login(member)
    assert api_client.delete(detail_url(aircraft)).status_code == 403
    assert Aircraft.objects.filter(pk=aircraft.pk).exists()


def test_dart_leader_may_not_delete_an_aircraft(api_client, dart_leader):
    aircraft = AircraftFactory(n_number="N71DL")
    api_client.force_login(dart_leader)
    assert api_client.delete(detail_url(aircraft)).status_code == 403


def test_account_admin_may_delete_an_aircraft(api_client, account_admin):
    aircraft = AircraftFactory(n_number="N72DL")
    api_client.force_login(account_admin)
    assert api_client.delete(detail_url(aircraft)).status_code == 204
    assert not Aircraft.objects.filter(pk=aircraft.pk).exists()


def test_role_matrix_for_delete(api_client, all_role_users):
    allowed = {ACCOUNT_ADMIN, SYSTEM_ADMIN}
    for index, (slug, user) in enumerate(all_role_users.items()):
        aircraft = AircraftFactory(n_number=f"N{800 + index}RM")
        api_client.force_login(user)
        response = api_client.delete(detail_url(aircraft))
        expected = 204 if slug in allowed else 403
        assert response.status_code == expected, f"{slug} got {response.status_code}"
        api_client.logout()


# --------------------------------------------------------------------------
# Lookup
# --------------------------------------------------------------------------
@pytest.mark.parametrize("typed", ["N172SP", "n172sp", "n-172-sp", " 172sp "])
def test_lookup_finds_an_aircraft_however_the_n_number_is_typed(api_client, member, typed):
    AircraftFactory(n_number="N172SP")
    api_client.force_login(member)
    response = api_client.get(LOOKUP_URL, {"n_number": typed})
    assert response.status_code == 200
    assert response.data["n_number"] == "N172SP"


def test_lookup_404s_for_an_unknown_n_number(api_client, member):
    api_client.force_login(member)
    assert api_client.get(LOOKUP_URL, {"n_number": "N0000X"}).status_code == 404


def test_lookup_without_an_n_number_is_a_400(api_client, member):
    api_client.force_login(member)
    response = api_client.get(LOOKUP_URL)
    assert response.status_code == 400
    assert "n_number" in response.data


def test_lookup_is_exact_not_a_prefix_match(api_client, member):
    AircraftFactory(n_number="N172SP")
    api_client.force_login(member)
    assert api_client.get(LOOKUP_URL, {"n_number": "N172"}).status_code == 404


# --------------------------------------------------------------------------
# Filters
# --------------------------------------------------------------------------
@pytest.fixture
def register(db):
    """A small register covering every insurance state."""
    today = timezone.localdate()
    return {
        "current": AircraftFactory(
            n_number="N172SP",
            make="Cessna",
            model="172S Skyhawk",
            owner_name="Palo Alto Flying Club",
            owner_type="club",
            insurance_expiration=today + timedelta(days=200),
        ),
        "expiring": AircraftFactory(
            n_number="N9021K",
            make="Piper",
            model="PA-28-181 Archer",
            owner_name="Marta Reyes",
            owner_type="individual",
            insurance_expiration=today + timedelta(days=10),
        ),
        "expired": AircraftFactory(
            n_number="N33MM",
            make="Mooney",
            model="M20J",
            owner_name="Owen Delgado",
            owner_type="individual",
            insurance_expiration=today - timedelta(days=5),
        ),
        "missing": AircraftFactory(
            n_number="N44BE",
            make="Beechcraft",
            model="A36 Bonanza",
            owner_name="Hayward Aviation Services",
            owner_type="fbo",
            insurance_expiration=None,
            insurance_carrier="",
        ),
    }


def numbers(response) -> list[str]:
    return [row["n_number"] for row in response.data["results"]]


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
def test_search_filter(api_client, member, register, query, expected):
    api_client.force_login(member)
    assert numbers(api_client.get(LIST_URL, {"search": query})) == expected


def test_make_filter(api_client, member, register):
    api_client.force_login(member)
    assert numbers(api_client.get(LIST_URL, {"make": "cessna"})) == ["N172SP"]


def test_owner_type_filter(api_client, member, register):
    api_client.force_login(member)
    assert numbers(api_client.get(LIST_URL, {"owner_type": "fbo"})) == ["N44BE"]
    assert numbers(api_client.get(LIST_URL, {"owner_type": "club"})) == ["N172SP"]


def test_owner_type_filter_rejects_an_unknown_choice(api_client, member, register):
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
def test_insurance_filter(api_client, member, register, state, expected):
    api_client.force_login(member)
    assert sorted(numbers(api_client.get(LIST_URL, {"insurance": state}))) == sorted(expected)


def test_expiring_within_excludes_already_expired_cover(api_client, member, register):
    api_client.force_login(member)
    assert numbers(api_client.get(LIST_URL, {"expiring_within": 30})) == ["N9021K"]


def test_expiring_within_widens_with_the_window(api_client, member, register):
    api_client.force_login(member)
    assert sorted(numbers(api_client.get(LIST_URL, {"expiring_within": 365}))) == [
        "N172SP",
        "N9021K",
    ]


def test_expiring_within_zero_days_means_expiring_today(api_client, member, register):
    AircraftFactory(n_number="N88TD", insurance_expiration=timezone.localdate())
    api_client.force_login(member)
    assert numbers(api_client.get(LIST_URL, {"expiring_within": 0})) == ["N88TD"]


@pytest.mark.parametrize("window", ["999999999", "1e11", "-5"])
def test_expiring_within_survives_an_absurd_window(api_client, member, register, window):
    """An overflowing timedelta would be a 500, not a filter."""
    api_client.force_login(member)
    response = api_client.get(LIST_URL, {"expiring_within": window})
    assert response.status_code == 200


def test_expiring_within_is_clamped_to_ten_years(api_client, member, register):
    api_client.force_login(member)
    wide = numbers(api_client.get(LIST_URL, {"expiring_within": "999999999"}))
    decade = numbers(api_client.get(LIST_URL, {"expiring_within": "3650"}))
    assert wide == decade


def test_is_active_filter(api_client, member, register):
    AircraftFactory(n_number="N77OS", is_active=False)
    api_client.force_login(member)
    assert "N77OS" in numbers(api_client.get(LIST_URL))
    assert "N77OS" not in numbers(api_client.get(LIST_URL, {"is_active": "true"}))
    assert numbers(api_client.get(LIST_URL, {"is_active": "false"})) == ["N77OS"]


def test_ordering_is_stable_across_pages(api_client, member):
    """Ties on a non-unique column must not shuffle between pages."""
    for index in range(10):
        AircraftFactory(n_number=f"N{600 + index}TIE", make="Cessna", model="172S")
    api_client.force_login(member)
    query = {"ordering": "make", "page_size": 4}
    seen: list[str] = []
    for page in (1, 2, 3):
        seen.extend(numbers(api_client.get(LIST_URL, {**query, "page": page})))
    assert len(seen) == len(set(seen)) == 10


def test_filters_combine(api_client, member, register):
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
def test_ordering(api_client, member, register, ordering, first):
    api_client.force_login(member)
    response = api_client.get(LIST_URL, {"ordering": ordering})
    assert numbers(response)[0] == first


@pytest.mark.parametrize("ordering", ["insurance_expiration", "-insurance_expiration"])
def test_aircraft_without_insurance_sort_last_either_way(api_client, member, register, ordering):
    api_client.force_login(member)
    response = api_client.get(LIST_URL, {"ordering": ordering})
    assert numbers(response)[-1] == "N44BE"


def test_search_matches_a_pilots_aircraft_only_through_the_register(api_client, member, register):
    """The register search is about aircraft; member search is the leader check's job."""
    MemberProfileFactory(user=member).aircraft.add(register["current"])
    api_client.force_login(member)
    assert numbers(api_client.get(LIST_URL, {"search": "Reyes"})) == ["N9021K"]
