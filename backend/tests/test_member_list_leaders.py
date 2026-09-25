"""The member list for DART leaders.

``GET /admin/members`` admits a DART leader beside the account administrator, and the
leader sees every member, not only their own DART's.  Everything else on the
members-admin API stays with the account administrator: creating a member, reading
or changing one member's record, and granting a term.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import ACCOUNT_ADMIN, DART_LEADER, SYSTEM_ADMIN
from apps.darts.models import Dart
from apps.members.models import MemberProfile
from tests.conftest import read_csv, role_matrix
from tests.factories import DartFactory, MemberProfileFactory, UserFactory

pytestmark = pytest.mark.django_db

LIST_URL = "/api/v1/admin/members"
CSV_URL = "/api/v1/reports/members/export.csv"


@pytest.fixture
def leader_client(api_client: APIClient, dart_leader: User, dart: Dart) -> APIClient:
    """A client signed in as a DART leader whose own profile names ``dart``."""
    MemberProfileFactory(user=dart_leader, dart=dart)
    api_client.force_login(dart_leader)
    return api_client


@pytest.fixture
def other_dart_member() -> User:
    """A member of a DART the leader does not lead."""
    user = UserFactory(email="napa-member@example.test")
    MemberProfileFactory(user=user, dart=DartFactory(name="Napa", airport_identifiers="APC"))
    return user


@pytest.mark.parametrize(("slug", "allowed"), role_matrix(DART_LEADER, ACCOUNT_ADMIN, SYSTEM_ADMIN))
def test_the_member_list_admits_dart_leaders_and_account_administrators(
    api_client: APIClient, all_role_users: dict[str, User], slug: str, allowed: bool
) -> None:
    """``GET /admin/members`` answers 200 to those roles and 403 to every other one."""
    api_client.force_login(all_role_users[slug])
    assert api_client.get(LIST_URL).status_code == (200 if allowed else 403)


def test_a_leader_sees_members_of_every_dart(
    leader_client: APIClient, profile: MemberProfile, other_dart_member: User
) -> None:
    """The list a leader reads is the whole membership, not only the leader's own DART."""
    emails = {row["email"] for row in leader_client.get(LIST_URL).json()["results"]}
    assert {profile.user.email, other_dart_member.email} <= emails


def test_a_leader_filters_the_list_by_dart(
    leader_client: APIClient, profile: MemberProfile, other_dart_member: User
) -> None:
    """A leader narrows the list with the same filters the account administrator has."""
    napa = other_dart_member.profile.dart
    assert napa is not None
    rows = leader_client.get(LIST_URL, {"dart": napa.pk}).json()["results"]
    assert [row["email"] for row in rows] == [other_dart_member.email]


def test_a_leader_downloads_the_entire_report(
    leader_client: APIClient, profile: MemberProfile, other_dart_member: User
) -> None:
    """The members CSV a leader downloads lists members of every DART."""
    table = read_csv(leader_client.get(CSV_URL, {"columns": "email"}))
    assert {profile.user.email, other_dart_member.email} <= {row[0] for row in table[1:]}


def test_a_leader_may_not_create_a_member(leader_client: APIClient) -> None:
    """``POST /admin/members`` stays with the account administrator."""
    response = leader_client.post(LIST_URL, {"email": "new@example.test"}, format="json")
    assert response.status_code == 403


def test_a_leader_may_not_read_one_members_record(
    leader_client: APIClient, profile: MemberProfile
) -> None:
    """``GET /admin/members/{id}`` stays with the account administrator."""
    assert leader_client.get(f"{LIST_URL}/{profile.user.pk}").status_code == 403


def test_a_leader_may_not_grant_a_term(leader_client: APIClient, profile: MemberProfile) -> None:
    """``POST /admin/members/{id}/memberships`` stays with the account administrator."""
    url = f"{LIST_URL}/{profile.user.pk}/memberships"
    assert leader_client.post(url, {"plan": "annual"}, format="json").status_code == 403
