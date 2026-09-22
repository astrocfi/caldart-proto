"""The DART leader check: search, status card, aircraft card.

The status card answers the question a leader asks before a flight --
"membership current? medical current? insurance current on the plane they are
flying?" -- so the truth table below is the most important test in this app.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import ACCOUNT_ADMIN, DART_LEADER, SYSTEM_ADMIN
from apps.members.models import (
    Dart,
    MedicalType,
    MembershipPlan,
    MembershipStatusChoices,
)
from tests.factories import (
    AircraftFactory,
    MemberProfileFactory,
    MembershipFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db

SEARCH_URL = "/api/v1/leader/search"
AIRCRAFT_URL = "/api/v1/leader/aircraft"


def status_url(user: User) -> str:
    """Return the leader status-card URL for ``user``."""
    return f"/api/v1/leader/members/{user.pk}/status"


@pytest.fixture
def pilot(db: None, dart: Dart, annual_plan: MembershipPlan) -> User:
    """A current member with a current medical and an insured airplane."""
    today = timezone.localdate()
    user = UserFactory(email="marta@example.test", first_name="Marta", last_name="Reyes")
    profile = MemberProfileFactory(
        user=user,
        dart=dart,
        phone="650-555-0100",
        certificate_number="3181234",
        medical_type=MedicalType.THIRD,
        medical_expiration=today + timedelta(days=120),
    )
    profile.aircraft.add(AircraftFactory(n_number="N172SP", make="Cessna", model="172S Skyhawk"))
    MembershipFactory(
        user=user,
        plan=annual_plan,
        starts_on=today - timedelta(days=30),
        ends_on=today + timedelta(days=300),
    )
    return user


# --------------------------------------------------------------------------
# Permissions
# --------------------------------------------------------------------------
@pytest.mark.parametrize("url", [SEARCH_URL, AIRCRAFT_URL])
def test_leader_endpoints_require_authentication(api_client: APIClient, url: str) -> None:
    """An anonymous caller is refused both leader endpoints."""
    assert api_client.get(url).status_code == 401


def test_status_requires_authentication(api_client: APIClient, pilot: User) -> None:
    """An anonymous caller is refused the status card."""
    assert api_client.get(status_url(pilot)).status_code == 401


def test_leader_role_matrix(
    api_client: APIClient, all_role_users: dict[str, User], pilot: User
) -> None:
    """Only a DART leader, account admin or system admin may use the leader endpoints."""
    allowed = {DART_LEADER, ACCOUNT_ADMIN, SYSTEM_ADMIN}
    for slug, user in all_role_users.items():
        api_client.force_login(user)
        expected = 200 if slug in allowed else 403
        assert api_client.get(SEARCH_URL, {"q": "Reyes"}).status_code == expected, slug
        assert api_client.get(status_url(pilot)).status_code == expected, slug
        assert api_client.get(AIRCRAFT_URL, {"n_number": "N172SP"}).status_code == expected, slug
        api_client.logout()


def test_a_plain_member_cannot_check_another_member(
    api_client: APIClient, member: User, pilot: User
) -> None:
    """A plain member is refused the status card for someone else."""
    api_client.force_login(member)
    assert api_client.get(status_url(pilot)).status_code == 403


# --------------------------------------------------------------------------
# Search
# --------------------------------------------------------------------------
@pytest.mark.parametrize("query", ["Reyes", "reyes", "Marta", "Marta Reyes", "Reyes, Marta"])
def test_search_by_name(api_client: APIClient, dart_leader: User, pilot: User, query: str) -> None:
    """A search matches on first name, last name, or either case or order."""
    api_client.force_login(dart_leader)
    response = api_client.get(SEARCH_URL, {"q": query})
    assert response.status_code == 200
    assert [row["user_id"] for row in response.data] == [pilot.pk]


def test_search_by_email(api_client: APIClient, dart_leader: User, pilot: User) -> None:
    """A search matches a full email address."""
    api_client.force_login(dart_leader)
    response = api_client.get(SEARCH_URL, {"q": "marta@example.test"})
    assert [row["user_id"] for row in response.data] == [pilot.pk]


def test_search_by_partial_email(api_client: APIClient, dart_leader: User, pilot: User) -> None:
    """A search matches a partial email address."""
    api_client.force_login(dart_leader)
    assert [row["user_id"] for row in api_client.get(SEARCH_URL, {"q": "marta@"}).data] == [
        pilot.pk
    ]


@pytest.mark.parametrize("query", ["N172SP", "n172sp", "n-172-sp", "172sp"])
def test_search_by_n_number_finds_the_members_who_fly_it(
    api_client: APIClient, dart_leader: User, pilot: User, query: str
) -> None:
    """A search normalizes the N-number regardless of case, dashes, or a missing ``N``."""
    api_client.force_login(dart_leader)
    response = api_client.get(SEARCH_URL, {"q": query})
    assert [row["user_id"] for row in response.data] == [pilot.pk]


def test_search_by_n_number_returns_every_pilot_of_that_aircraft(
    api_client: APIClient, dart_leader: User, pilot: User
) -> None:
    """A search by N-number returns every member who flies that airplane."""
    aircraft = pilot.profile.aircraft.get()
    second = UserFactory(email="owen@example.test", first_name="Owen", last_name="Delgado")
    MemberProfileFactory(user=second).aircraft.add(aircraft)

    api_client.force_login(dart_leader)
    response = api_client.get(SEARCH_URL, {"q": "N172SP"})
    assert {row["user_id"] for row in response.data} == {pilot.pk, second.pk}


def test_search_does_not_treat_a_name_as_a_registration(
    api_client: APIClient, dart_leader: User, pilot: User
) -> None:
    """A name like "Nate" must not match every N-numbered aircraft on file."""
    nate = UserFactory(email="nate@example.test", first_name="Nate", last_name="Cross")
    MemberProfileFactory(user=nate).aircraft.add(AircraftFactory(n_number="N9021K"))

    api_client.force_login(dart_leader)
    response = api_client.get(SEARCH_URL, {"q": "Nate"})
    assert [row["user_id"] for row in response.data] == [nate.pk]


def test_search_result_shape(
    api_client: APIClient, dart_leader: User, pilot: User, dart: Dart
) -> None:
    """A search result row carries the member's id, name, email, dart, and status."""
    api_client.force_login(dart_leader)
    row = api_client.get(SEARCH_URL, {"q": "Reyes"}).data[0]
    assert row == {
        "user_id": pilot.pk,
        "name": "Marta Reyes",
        "email": "marta@example.test",
        "dart": dart.name,
        "membership_status": "current",
    }


def test_search_reports_an_expired_membership(
    api_client: APIClient, dart_leader: User, annual_plan: MembershipPlan
) -> None:
    """A search result reports ``expired`` for a member whose term has lapsed."""
    today = timezone.localdate()
    lapsed = UserFactory(email="lapsed@example.test", first_name="Lee", last_name="Past")
    MemberProfileFactory(user=lapsed)
    MembershipFactory(
        user=lapsed,
        plan=annual_plan,
        starts_on=today - timedelta(days=400),
        ends_on=today - timedelta(days=35),
        status=MembershipStatusChoices.EXPIRED,
    )
    api_client.force_login(dart_leader)
    assert api_client.get(SEARCH_URL, {"q": "Past"}).data[0]["membership_status"] == "expired"


def test_search_with_no_query_returns_nothing(
    api_client: APIClient, dart_leader: User, pilot: User
) -> None:
    """A missing or blank query returns no results rather than everyone."""
    api_client.force_login(dart_leader)
    assert api_client.get(SEARCH_URL).data == []
    assert api_client.get(SEARCH_URL, {"q": "   "}).data == []


def test_search_finds_nothing_for_an_unknown_name(
    api_client: APIClient, dart_leader: User, pilot: User
) -> None:
    """A query that matches nobody returns an empty list, not an error."""
    api_client.force_login(dart_leader)
    assert api_client.get(SEARCH_URL, {"q": "Nobody At All"}).data == []


def test_search_is_capped_at_twenty_results(api_client: APIClient, dart_leader: User) -> None:
    """A search returns at most twenty results even when more members match."""
    for index in range(25):
        UserFactory(email=f"cap{index}@example.test", first_name="Cap", last_name=f"Test{index}")
    api_client.force_login(dart_leader)
    assert len(api_client.get(SEARCH_URL, {"q": "Cap"}).data) == 20


def test_search_does_not_repeat_a_member_who_flies_two_aircraft(
    api_client: APIClient, dart_leader: User, pilot: User
) -> None:
    """A member who flies two matching aircraft appears once in the results."""
    pilot.profile.aircraft.add(AircraftFactory(n_number="N1720P"))
    api_client.force_login(dart_leader)
    assert len(api_client.get(SEARCH_URL, {"q": "172"}).data) == 1


# --------------------------------------------------------------------------
# Status card
# --------------------------------------------------------------------------
def test_status_card_shape(
    api_client: APIClient, dart_leader: User, pilot: User, dart: Dart
) -> None:
    """The status card reports the member's profile, certificate, medical and go/no-go."""
    api_client.force_login(dart_leader)
    data = api_client.get(status_url(pilot)).data

    assert data["name"] == "Marta Reyes"
    assert data["email"] == "marta@example.test"
    assert data["phone"] == "650-555-0100"
    assert data["dart"] == dart.name
    assert data["membership"]["status"] == "current"
    assert data["membership"]["plan"] == "Annual"
    assert data["certificate"] == {
        "type": "private",
        "number": "3181234",
        "ifr_rated": "yes",
        "ratings": ["instrument"],
    }
    assert data["medical"]["type"] == "third"
    assert data["medical"]["is_current"] is True
    assert data["go_no_go"] == {"membership": True, "medical": True}

    aircraft = data["aircraft"][0]
    assert aircraft["n_number"] == "N172SP"
    assert aircraft["insurance_is_current"] is True
    assert "exp" in aircraft["insurance_summary"]


def test_status_card_404s_for_an_unknown_member(api_client: APIClient, dart_leader: User) -> None:
    """A status card for an unknown member id returns a 404."""
    api_client.force_login(dart_leader)
    assert api_client.get("/api/v1/leader/members/99999/status").status_code == 404


@pytest.mark.parametrize("membership_current", [True, False])
@pytest.mark.parametrize("medical_current", [True, False])
@pytest.mark.parametrize("insurance_current", [True, False])
def test_status_truth_table(
    api_client: APIClient,
    dart_leader: User,
    annual_plan: MembershipPlan,
    membership_current: bool,
    medical_current: bool,
    insurance_current: bool,
) -> None:
    """Membership x medical x insurance: every combination, one assertion each."""
    today = timezone.localdate()
    user = UserFactory(email="matrix@example.test", first_name="Mat", last_name="Rix")
    profile = MemberProfileFactory(
        user=user,
        medical_type=MedicalType.BASICMED,
        medical_expiration=today + timedelta(days=30 if medical_current else -30),
    )
    profile.aircraft.add(
        AircraftFactory(
            n_number="N7TT",
            insurance_expiration=today + timedelta(days=90 if insurance_current else -90),
        )
    )
    if membership_current:
        MembershipFactory(
            user=user, plan=annual_plan, starts_on=today, ends_on=today + timedelta(days=364)
        )
    else:
        MembershipFactory(
            user=user,
            plan=annual_plan,
            starts_on=today - timedelta(days=400),
            ends_on=today - timedelta(days=36),
            status=MembershipStatusChoices.EXPIRED,
        )

    api_client.force_login(dart_leader)
    data = api_client.get(status_url(user)).data

    assert data["go_no_go"]["membership"] is membership_current
    assert data["go_no_go"]["medical"] is medical_current
    assert data["medical"]["is_current"] is medical_current
    assert data["aircraft"][0]["insurance_is_current"] is insurance_current
    # The overall verdict the leader reads: membership AND medical.
    go = data["go_no_go"]["membership"] and data["go_no_go"]["medical"]
    assert go is (membership_current and medical_current)


def test_a_medical_expiring_today_is_still_current(
    api_client: APIClient, dart_leader: User, annual_plan: MembershipPlan
) -> None:
    """A medical that expires today still counts as current."""
    today = timezone.localdate()
    user = UserFactory(email="edge@example.test", first_name="Edge", last_name="Case")
    MemberProfileFactory(user=user, medical_type=MedicalType.THIRD, medical_expiration=today)
    api_client.force_login(dart_leader)
    assert api_client.get(status_url(user)).data["medical"]["is_current"] is True


def test_no_medical_on_file_is_never_current(api_client: APIClient, dart_leader: User) -> None:
    """A member with no medical on file is never a go for medical."""
    user = UserFactory(email="nomed@example.test", first_name="No", last_name="Medical")
    MemberProfileFactory(user=user, medical_type=MedicalType.NONE, medical_expiration=None)
    api_client.force_login(dart_leader)
    data = api_client.get(status_url(user)).data
    assert data["medical"] == {"type": "none", "expiration": None, "is_current": False}
    assert data["go_no_go"]["medical"] is False


def test_a_member_with_no_membership_at_all_is_a_no_go(
    api_client: APIClient, dart_leader: User
) -> None:
    """A member who has never held a membership term is a no-go for membership."""
    user = UserFactory(email="never@example.test", first_name="Never", last_name="Joined")
    MemberProfileFactory(user=user)
    api_client.force_login(dart_leader)
    data = api_client.get(status_url(user)).data
    assert data["membership"] == {"status": "none", "expires_on": None, "plan": None}
    assert data["go_no_go"]["membership"] is False


def test_a_lifetime_member_is_current_without_an_expiry(
    api_client: APIClient, dart_leader: User, life_plan: MembershipPlan
) -> None:
    """A lifetime member is current with no expiration date to report."""
    user = UserFactory(email="life@example.test", first_name="Life", last_name="Member")
    MemberProfileFactory(user=user)
    MembershipFactory(user=user, plan=life_plan, ends_on=None)
    api_client.force_login(dart_leader)
    data = api_client.get(status_url(user)).data
    assert data["membership"] == {
        "status": "current",
        "expires_on": None,
        "plan": "Life",
    }
    assert data["go_no_go"]["membership"] is True


def test_status_card_lists_every_attached_aircraft(
    api_client: APIClient, dart_leader: User, pilot: User
) -> None:
    """The status card lists every aircraft attached to the member's profile."""
    pilot.profile.aircraft.add(
        AircraftFactory(
            n_number="N9021K",
            insurance_expiration=None,
            insurance_liability_per_occurrence_cents=0,
            insurance_liability_per_person_cents=0,
        )
    )
    api_client.force_login(dart_leader)
    data = api_client.get(status_url(pilot)).data
    by_number = {row["n_number"]: row for row in data["aircraft"]}
    assert set(by_number) == {"N172SP", "N9021K"}
    assert by_number["N9021K"]["insurance_is_current"] is False
    assert by_number["N9021K"]["insurance_summary"] == "No insurance on file"


def test_status_card_for_a_member_with_no_aircraft(
    api_client: APIClient, dart_leader: User, member: User
) -> None:
    """The status card reports an empty aircraft list for a member who flies none."""
    MemberProfileFactory(user=member)
    api_client.force_login(dart_leader)
    assert api_client.get(status_url(member)).data["aircraft"] == []


def test_status_card_for_a_user_without_a_profile(api_client: APIClient, dart_leader: User) -> None:
    """A user_admin can create an account before the member fills anything in."""
    bare = UserFactory(email="bare@example.test", first_name="Bare", last_name="Account")
    api_client.force_login(dart_leader)
    data = api_client.get(status_url(bare)).data
    assert data["phone"] == ""
    assert data["dart"] is None
    assert data["certificate"]["type"] == "none"
    assert data["go_no_go"] == {"membership": False, "medical": False}


# --------------------------------------------------------------------------
# Aircraft card
# --------------------------------------------------------------------------
@pytest.mark.parametrize("typed", ["N172SP", "n172sp", "n-172sp", "172sp"])
def test_aircraft_card_normalizes_the_n_number(
    api_client: APIClient, dart_leader: User, pilot: User, typed: str
) -> None:
    """The aircraft card normalizes the N-number regardless of case or dashes."""
    api_client.force_login(dart_leader)
    response = api_client.get(AIRCRAFT_URL, {"n_number": typed})
    assert response.status_code == 200
    assert response.data["n_number"] == "N172SP"
    assert response.data["insurance_is_current"] is True


def test_aircraft_card_lists_the_pilots_who_fly_it(
    api_client: APIClient, dart_leader: User, pilot: User
) -> None:
    """The aircraft card lists every pilot who flies that airplane."""
    api_client.force_login(dart_leader)
    data = api_client.get(AIRCRAFT_URL, {"n_number": "N172SP"}).data
    assert data["pilots"] == [
        {
            "user_id": pilot.pk,
            "name": "Marta Reyes",
            "email": "marta@example.test",
            "membership_status": "current",
            "medical_is_current": True,
        }
    ]


def test_aircraft_card_404s_for_an_unknown_n_number(
    api_client: APIClient, dart_leader: User
) -> None:
    """The aircraft card returns a 404 for an N-number on file for no aircraft."""
    api_client.force_login(dart_leader)
    assert api_client.get(AIRCRAFT_URL, {"n_number": "N0000X"}).status_code == 404


def test_aircraft_card_without_an_n_number_is_a_400(
    api_client: APIClient, dart_leader: User
) -> None:
    """The aircraft card refuses a request with no ``n_number`` query parameter."""
    api_client.force_login(dart_leader)
    response = api_client.get(AIRCRAFT_URL)
    assert response.status_code == 400
    assert "n_number" in response.data


def test_aircraft_card_shows_expired_cover(api_client: APIClient, dart_leader: User) -> None:
    """The aircraft card reports lapsed insurance and an empty pilot list."""
    AircraftFactory(
        n_number="N33MM",
        insurance_expiration=timezone.localdate() - timedelta(days=1),
    )
    api_client.force_login(dart_leader)
    data = api_client.get(AIRCRAFT_URL, {"n_number": "N33MM"}).data
    assert data["insurance_is_current"] is False
    assert data["pilots"] == []
