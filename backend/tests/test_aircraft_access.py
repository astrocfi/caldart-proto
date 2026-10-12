"""Aircraft are for members: friends and expired members are refused.

A friend of CalDART pays no dues and has nothing to do with aircraft; a member whose
membership has expired keeps the aircraft on their profile but cannot see or change
them; a current member, or one who has joined and not yet paid, uses the register and
their own aircraft; the roles that check members and aircraft use the register
whatever their own membership.  See ``apps.aircraft.access``.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import AccountKind, User
from apps.accounts.roles import ACCOUNT_ADMIN, MEMBER, VERIFIER
from apps.aircraft.models import Aircraft
from apps.members.models import MemberProfile, MembershipPlan
from tests.conftest import ME_URL
from tests.factories import MemberProfileFactory, MembershipFactory, UserFactory

pytestmark = pytest.mark.django_db

REFUSED = {"detail": "Aircraft are for members with a current membership."}
PROFILE_URL = "/api/v1/me/profile"
ATTACH_URL = "/api/v1/me/profile/aircraft"
ADMIN_MEMBERS_URL = "/api/v1/admin/members"

#: Every aircraft endpoint a member reaches, read with GET.
READ_URLS = [
    "/api/v1/aircraft",
    "/api/v1/aircraft/lookup?n_number=N12345",
    "/api/v1/aircraft/types?q=cessna",
    "/api/v1/aircraft/coverage-policy",
    "/api/v1/aircraft/registry",
    "/api/v1/aircraft/registrations?q=N1",
    "/api/v1/aircraft/registry/N12345",
]


def _expired(user: User, plan: MembershipPlan, today: date) -> User:
    """Give ``user`` a term that started and ran out before ``today``."""
    MembershipFactory(
        user=user,
        plan=plan,
        starts_on=today - timedelta(days=400),
        ends_on=today - timedelta(days=35),
    )
    return user


@pytest.fixture
def expired_member(annual_plan: MembershipPlan, today: date) -> User:
    """A member whose only term has run out."""
    user = UserFactory(email="lapsed@example.test", kind=AccountKind.MEMBER, roles=[MEMBER])
    return _expired(user, annual_plan, today)


@pytest.fixture
def current_member(annual_plan: MembershipPlan) -> User:
    """A member with a term covering today."""
    user = UserFactory(email="current@example.test", kind=AccountKind.MEMBER, roles=[MEMBER])
    MembershipFactory(user=user, plan=annual_plan)
    return user


@pytest.fixture
def expired_account_admin(annual_plan: MembershipPlan, today: date) -> User:
    """An account administrator whose own membership has run out."""
    user = UserFactory(
        email="lapsed.admin@example.test", kind=AccountKind.MEMBER, roles=[MEMBER, ACCOUNT_ADMIN]
    )
    return _expired(user, annual_plan, today)


@pytest.fixture
def expired_verifier(annual_plan: MembershipPlan, today: date) -> User:
    """A verifier whose own membership has run out."""
    user = UserFactory(
        email="lapsed.verifier@example.test", kind=AccountKind.MEMBER, roles=[MEMBER, VERIFIER]
    )
    return _expired(user, annual_plan, today)


def client_for(user: User) -> APIClient:
    """A DRF client signed in as ``user``."""
    client = APIClient()
    client.force_login(user)
    return client


# --------------------------------------------------------------------------
# Who is refused
# --------------------------------------------------------------------------
@pytest.mark.parametrize("url", READ_URLS)
@pytest.mark.parametrize("account", ["friend", "expired_member"])
def test_a_friend_or_expired_member_is_refused_every_aircraft_read(
    url: str, account: str, request: pytest.FixtureRequest
) -> None:
    """Every aircraft read answers 403 with the sentence."""
    response = client_for(request.getfixturevalue(account)).get(url)
    assert (response.status_code, response.json()) == (403, REFUSED)


@pytest.mark.parametrize("account", ["friend", "expired_member"])
def test_a_friend_or_expired_member_cannot_add_an_aircraft(
    account: str, request: pytest.FixtureRequest
) -> None:
    """``POST /aircraft`` is refused before the body is read."""
    response = client_for(request.getfixturevalue(account)).post(
        "/api/v1/aircraft", {"n_number": "N4321"}, format="json"
    )
    assert (response.status_code, response.json()) == (403, REFUSED)


@pytest.mark.parametrize("account", ["friend", "expired_member"])
def test_a_friend_or_expired_member_cannot_read_an_aircraft_record(
    account: str, request: pytest.FixtureRequest, aircraft: Aircraft
) -> None:
    """``GET /aircraft/{id}`` is refused."""
    response = client_for(request.getfixturevalue(account)).get(f"/api/v1/aircraft/{aircraft.pk}")
    assert (response.status_code, response.json()) == (403, REFUSED)


@pytest.mark.parametrize("account", ["friend", "expired_member"])
def test_a_friend_or_expired_member_cannot_attach_an_aircraft(
    account: str, request: pytest.FixtureRequest, aircraft: Aircraft
) -> None:
    """``POST /me/profile/aircraft`` is refused."""
    response = client_for(request.getfixturevalue(account)).post(
        ATTACH_URL, {"aircraft_id": aircraft.pk}, format="json"
    )
    assert (response.status_code, response.json()) == (403, REFUSED)


@pytest.mark.parametrize("account", ["friend", "expired_member"])
def test_a_friend_or_expired_member_cannot_detach_an_aircraft(
    account: str, request: pytest.FixtureRequest, aircraft: Aircraft
) -> None:
    """``DELETE /me/profile/aircraft/{id}`` is refused."""
    response = client_for(request.getfixturevalue(account)).delete(f"{ATTACH_URL}/{aircraft.pk}")
    assert (response.status_code, response.json()) == (403, REFUSED)


def test_an_anonymous_caller_is_asked_to_sign_in(api_client: APIClient) -> None:
    """The register still answers 401, not 403, to nobody."""
    assert api_client.get("/api/v1/aircraft").status_code == 401


# --------------------------------------------------------------------------
# Who is admitted
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "account",
    ["current_member", "member", "expired_account_admin", "expired_verifier"],
    ids=["current", "not-yet-paid", "lapsed-account-admin", "lapsed-verifier"],
)
def test_members_and_checking_roles_read_the_register(
    account: str, request: pytest.FixtureRequest
) -> None:
    """A current or not-yet-paid member, and any checking role, read the register."""
    response = client_for(request.getfixturevalue(account)).get("/api/v1/aircraft")
    assert response.status_code == 200


def test_a_current_member_attaches_an_aircraft(current_member: User, aircraft: Aircraft) -> None:
    """``POST /me/profile/aircraft`` works for a current member."""
    response = client_for(current_member).post(
        ATTACH_URL, {"aircraft_id": aircraft.pk}, format="json"
    )
    assert response.status_code == 200


# --------------------------------------------------------------------------
# What the profile and the user payload say
# --------------------------------------------------------------------------
@pytest.fixture
def lapsed_with_aircraft(expired_member: User, aircraft: Aircraft) -> MemberProfile:
    """The expired member's profile, holding the aircraft they added while current."""
    profile: MemberProfile = MemberProfileFactory(user=expired_member)
    profile.aircraft.add(aircraft)
    return profile


def test_an_expired_members_profile_lists_no_aircraft(
    expired_member: User, lapsed_with_aircraft: MemberProfile
) -> None:
    """``/me/profile`` hides the aircraft while the membership is expired."""
    assert client_for(expired_member).get(PROFILE_URL).json()["aircraft"] == []


def test_an_expired_member_keeps_their_aircraft(lapsed_with_aircraft: MemberProfile) -> None:
    """The attachment is kept, ready for when they renew."""
    assert lapsed_with_aircraft.aircraft.count() == 1


def test_an_administrator_still_sees_an_expired_members_aircraft(
    account_admin_client: APIClient, lapsed_with_aircraft: MemberProfile, aircraft: Aircraft
) -> None:
    """The member record shows every aircraft on the profile."""
    record = account_admin_client.get(f"{ADMIN_MEMBERS_URL}/{lapsed_with_aircraft.user.pk}").json()
    assert [entry["id"] for entry in record["profile"]["aircraft"]] == [aircraft.pk]


def test_a_current_members_profile_lists_their_aircraft(
    current_member: User, aircraft: Aircraft
) -> None:
    """``/me/profile`` lists the aircraft of a member who may use them."""
    profile: MemberProfile = MemberProfileFactory(user=current_member)
    profile.aircraft.add(aircraft)
    listed = client_for(current_member).get(PROFILE_URL).json()["aircraft"]
    assert [entry["id"] for entry in listed] == [aircraft.pk]


@pytest.mark.parametrize(
    ("account", "expected"),
    [
        ("friend", False),
        ("expired_member", False),
        ("current_member", True),
        ("member", True),
        ("expired_account_admin", True),
    ],
)
def test_the_user_payload_says_whether_aircraft_are_open(
    account: str, expected: bool, request: pytest.FixtureRequest
) -> None:
    """``/auth/me`` carries ``can_use_aircraft``, so the portal hides what is refused."""
    payload = client_for(request.getfixturevalue(account)).get(ME_URL).json()
    assert payload["can_use_aircraft"] is expected
