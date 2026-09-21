"""Every list that shows a membership status costs a fixed number of queries.

The membership rule is expressed twice: ``members.services.membership_status``
works it out in Python, one user at a time, and
``members.services.membership_annotations`` restates it as correlated
subqueries.  A list that reached for the Python version would spend a query per
row, so each endpoint below is driven at three rows and at twenty and must
issue the identical pinned number of queries both times.

The payload tests then check that the cheap answer is the same answer: a
current, an expired, a lifetime and a never-joined member all read back exactly
what ``membership_status`` reports.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any, cast

import pytest
from freezegun import freeze_time
from pytest_django.fixtures import DjangoAssertNumQueries
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import MEMBER
from apps.aircraft.models import Aircraft
from apps.members.models import (
    Dart,
    MembershipPlan,
    MembershipStatusChoices,
)
from apps.members.services import MembershipStatusDict, membership_status
from tests.factories import MemberProfileFactory, MembershipFactory, UserFactory

if TYPE_CHECKING:
    # rest_framework.test.APIClient.get() is typed to return this class, but it
    # exists only in the stub: rest_framework monkey-patches Django's test response
    # at runtime rather than defining a real subclass.
    from rest_framework.response import _MonkeyPatchedResponse as ApiResponse

pytestmark = pytest.mark.django_db

ADMIN_USERS = "/api/v1/admin/users"
ADMIN_MEMBERS = "/api/v1/admin/members"
LEADER_SEARCH = "/api/v1/leader/search"
LEADER_AIRCRAFT = "/api/v1/leader/aircraft"
AIRCRAFT_LOOKUP = "/api/v1/aircraft/lookup"

#: The two page sizes every count is pinned at.
PAGE_SIZES: tuple[int, int] = (3, 20)

#: Surname every generated member shares, so one leader search finds them all.
SEARCH_TERM = "Querycount"

#: The histories the population cycles through, one member each.
HISTORIES: tuple[str, ...] = ("current", "expired", "lifetime", "none")

#: Queries per request, whatever the page size.
ADMIN_USERS_QUERIES = 6
ADMIN_MEMBERS_QUERIES = 6
LEADER_SEARCH_QUERIES = 4
AIRCRAFT_DETAIL_QUERIES = 5
AIRCRAFT_LOOKUP_QUERIES = 5
LEADER_AIRCRAFT_QUERIES = 5


def _add_history(
    user: User,
    kind: str,
    annual_plan: MembershipPlan,
    life_plan: MembershipPlan,
    today: date,
    days: Callable[[int], timedelta],
) -> None:
    """Give ``user`` the membership history named by ``kind``."""
    if kind == "current":
        MembershipFactory(
            user=user, plan=annual_plan, starts_on=today - days(100), ends_on=today + days(200)
        )
    elif kind == "expired":
        MembershipFactory(
            user=user,
            plan=annual_plan,
            starts_on=today - days(500),
            ends_on=today - days(100),
            status=MembershipStatusChoices.EXPIRED,
        )
    elif kind == "lifetime":
        MembershipFactory(user=user, plan=life_plan, starts_on=today - days(900), ends_on=None)


@pytest.fixture
def population(
    annual_plan: MembershipPlan,
    life_plan: MembershipPlan,
    dart: Dart,
    aircraft: Aircraft,
    today: date,
    days: Callable[[int], timedelta],
) -> Callable[[int], list[User]]:
    """``population(n)`` -> ``n`` members sharing one airplane and one surname."""

    def build(size: int) -> list[User]:
        people = []
        for index in range(size):
            user = UserFactory(
                email=f"row{index}@example.test",
                first_name=f"Pat{index}",
                last_name=SEARCH_TERM,
                roles=[MEMBER],
            )
            profile = MemberProfileFactory(user=user, dart=dart)
            profile.aircraft.add(aircraft)
            kind = HISTORIES[index % len(HISTORIES)]
            _add_history(user, kind, annual_plan, life_plan, today, days)
            people.append(user)
        return people

    return build


@pytest.fixture
def members(population: Callable[[int], list[User]]) -> dict[str, User]:
    """One member per history, keyed by history name."""
    return dict(zip(HISTORIES, population(len(HISTORIES)), strict=True))


def _serialized(payload: MembershipStatusDict) -> dict[str, Any]:
    """``membership_status`` as the ``membership`` field renders it."""
    expires_on = payload["expires_on"]
    return {
        "status": payload["status"],
        "expires_on": expires_on.isoformat() if expires_on is not None else None,
        "plan": payload["plan"],
        "is_lifetime": payload["is_lifetime"],
    }


def _by_id(response: ApiResponse, key: str) -> dict[int, dict[str, Any]]:
    """Rows of ``response`` keyed by the identifier in ``key``."""
    body = response.json()
    rows = body["results"] if isinstance(body, dict) else body
    return {row[key]: row for row in rows}


def _membership_row(client: APIClient, user: User) -> dict[str, Any]:
    """The ``membership`` payload ``GET /admin/users`` reports for ``user``."""
    response = client.get(ADMIN_USERS, {"page_size": 200})
    return cast(dict[str, Any], _by_id(response, "id")[user.pk]["membership"])


# --------------------------------------------------------------------------
# Query counts
# --------------------------------------------------------------------------
@pytest.mark.parametrize("size", PAGE_SIZES)
def test_admin_users_costs_a_fixed_number_of_queries(
    api_client: APIClient,
    user_admin: User,
    population: Callable[[int], list[User]],
    django_assert_num_queries: DjangoAssertNumQueries,
    size: int,
) -> None:
    """The admin users list costs a fixed number of queries at three and twenty rows."""
    population(size)
    api_client.force_login(user_admin)
    with django_assert_num_queries(ADMIN_USERS_QUERIES):
        response = api_client.get(ADMIN_USERS, {"page_size": 200})
    assert response.status_code == 200


@pytest.mark.parametrize("size", PAGE_SIZES)
def test_admin_members_costs_a_fixed_number_of_queries(
    api_client: APIClient,
    account_admin: User,
    population: Callable[[int], list[User]],
    django_assert_num_queries: DjangoAssertNumQueries,
    size: int,
) -> None:
    """The admin members list costs a fixed number of queries at three and twenty rows."""
    population(size)
    api_client.force_login(account_admin)
    with django_assert_num_queries(ADMIN_MEMBERS_QUERIES):
        response = api_client.get(ADMIN_MEMBERS, {"page_size": 200})
    assert response.status_code == 200


@pytest.mark.parametrize("size", PAGE_SIZES)
def test_leader_search_costs_a_fixed_number_of_queries(
    api_client: APIClient,
    leader: User,
    population: Callable[[int], list[User]],
    django_assert_num_queries: DjangoAssertNumQueries,
    size: int,
) -> None:
    """A leader search costs a fixed number of queries at three and twenty matches."""
    population(size)
    api_client.force_login(leader)
    with django_assert_num_queries(LEADER_SEARCH_QUERIES):
        response = api_client.get(LEADER_SEARCH, {"q": SEARCH_TERM})
    assert len(response.json()) == size


@pytest.mark.parametrize("size", PAGE_SIZES)
def test_aircraft_detail_costs_a_fixed_number_of_queries(
    api_client: APIClient,
    leader: User,
    aircraft: Aircraft,
    population: Callable[[int], list[User]],
    django_assert_num_queries: DjangoAssertNumQueries,
    size: int,
) -> None:
    """The aircraft detail card costs a fixed query count at three or twenty pilots."""
    population(size)
    api_client.force_login(leader)
    with django_assert_num_queries(AIRCRAFT_DETAIL_QUERIES):
        response = api_client.get(f"/api/v1/aircraft/{aircraft.pk}")
    assert len(response.json()["pilots"]) == size


@pytest.mark.parametrize("size", PAGE_SIZES)
def test_aircraft_lookup_costs_a_fixed_number_of_queries(
    api_client: APIClient,
    leader: User,
    aircraft: Aircraft,
    population: Callable[[int], list[User]],
    django_assert_num_queries: DjangoAssertNumQueries,
    size: int,
) -> None:
    """The aircraft lookup costs a fixed number of queries at three and twenty pilots."""
    population(size)
    api_client.force_login(leader)
    with django_assert_num_queries(AIRCRAFT_LOOKUP_QUERIES):
        response = api_client.get(AIRCRAFT_LOOKUP, {"n_number": aircraft.n_number})
    assert len(response.json()["pilots"]) == size


@pytest.mark.parametrize("size", PAGE_SIZES)
def test_leader_aircraft_costs_a_fixed_number_of_queries(
    api_client: APIClient,
    leader: User,
    aircraft: Aircraft,
    population: Callable[[int], list[User]],
    django_assert_num_queries: DjangoAssertNumQueries,
    size: int,
) -> None:
    """The leader aircraft card costs a fixed query count at three or twenty pilots."""
    population(size)
    api_client.force_login(leader)
    with django_assert_num_queries(LEADER_AIRCRAFT_QUERIES):
        response = api_client.get(LEADER_AIRCRAFT, {"n_number": aircraft.n_number})
    assert len(response.json()["pilots"]) == size


# --------------------------------------------------------------------------
# The annotated answer is the same answer
# --------------------------------------------------------------------------
@pytest.mark.parametrize("kind", HISTORIES)
def test_admin_users_membership_matches_the_service(
    api_client: APIClient, user_admin: User, members: dict[str, User], kind: str
) -> None:
    """The admin users list reports the same membership payload as the service."""
    user = members[kind]
    api_client.force_login(user_admin)
    assert _membership_row(api_client, user) == _serialized(membership_status(user))


@pytest.mark.parametrize("kind", HISTORIES)
def test_admin_members_membership_matches_the_service(
    api_client: APIClient, account_admin: User, members: dict[str, User], kind: str
) -> None:
    """The admin members list reports the same membership payload as the service."""
    user = members[kind]
    api_client.force_login(account_admin)
    response = api_client.get(ADMIN_MEMBERS, {"page_size": 200})
    row = _by_id(response, "user_id")[user.pk]
    assert row["membership"] == _serialized(membership_status(user))


@pytest.mark.parametrize("kind", HISTORIES)
def test_leader_search_membership_matches_the_service(
    api_client: APIClient, leader: User, members: dict[str, User], kind: str
) -> None:
    """A leader search reports the same status the service computes."""
    user = members[kind]
    api_client.force_login(leader)
    response = api_client.get(LEADER_SEARCH, {"q": SEARCH_TERM})
    row = _by_id(response, "user_id")[user.pk]
    assert row["membership_status"] == membership_status(user)["status"]


@pytest.mark.parametrize("kind", HISTORIES)
def test_aircraft_pilots_membership_matches_the_service(
    api_client: APIClient, leader: User, aircraft: Aircraft, members: dict[str, User], kind: str
) -> None:
    """An aircraft's pilot list reports the same status the service computes."""
    user = members[kind]
    api_client.force_login(leader)
    response = api_client.get(f"/api/v1/aircraft/{aircraft.pk}")
    pilots = {row["user_id"]: row for row in response.json()["pilots"]}
    assert pilots[user.pk]["membership_status"] == membership_status(user)["status"]


# --------------------------------------------------------------------------
# The rule is evaluated per request, not once at start-up
# --------------------------------------------------------------------------
@pytest.fixture
def expiring_member(
    annual_plan: MembershipPlan, today: date, days: Callable[[int], timedelta]
) -> User:
    """A member whose only term runs out ten days from today."""
    user = UserFactory(email="clock@example.test", roles=[MEMBER])
    MembershipFactory(
        user=user, plan=annual_plan, starts_on=today - days(10), ends_on=today + days(10)
    )
    return user


def test_admin_users_reports_current_before_the_term_ends(
    api_client: APIClient,
    user_admin: User,
    expiring_member: User,
    today: date,
    days: Callable[[int], timedelta],
) -> None:
    """Five days before the term ends, the admin users list still reports current."""
    with freeze_time(f"{(today + days(5)).isoformat()} 12:00:00"):
        api_client.force_login(user_admin)
        row = _membership_row(api_client, expiring_member)
    assert row["status"] == "current"


def test_admin_users_reports_expired_once_the_clock_passes_ends_on(
    api_client: APIClient,
    user_admin: User,
    expiring_member: User,
    today: date,
    days: Callable[[int], timedelta],
) -> None:
    """Proves the queryset, and so ``today``, is built for each request."""
    with freeze_time(f"{(today + days(20)).isoformat()} 12:00:00"):
        api_client.force_login(user_admin)
        row = _membership_row(api_client, expiring_member)
    assert row["status"] == "expired"
