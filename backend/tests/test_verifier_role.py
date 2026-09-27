"""A DART leader or a user administrator grants and revokes the verifier role.

``PUT /leader/members/{user_id}/verifier`` goes through
``apps.accounts.services.set_verifier``, which writes the role list through
``update_account``: the change is audited as ``account.roles`` and raised as
``roles_changed``, and a list that changes nothing writes nothing.  The contract is
``docs/developer/api-aircraft.rst``.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import AccountKind, User
from apps.accounts.roles import DART_LEADER, MEMBER, SYSTEM_ADMIN, USER_ADMIN, VERIFIER
from apps.accounts.services import set_verifier
from caldart import audit
from tests.conftest import RecordedEvents, audit_messages, role_matrix
from tests.factories import MemberProfileFactory, UserFactory

pytestmark = pytest.mark.django_db


def verifier_url(user: User) -> str:
    """``/leader/members/{user_id}/verifier`` for ``user``."""
    return f"/api/v1/leader/members/{user.pk}/verifier"


@pytest.fixture
def pilot(db: None) -> User:
    """A plain member with a profile, holding no verifier role."""
    user = UserFactory(
        email="pilot@example.test", first_name="Ana", last_name="Bracco", roles=[MEMBER]
    )
    MemberProfileFactory(user=user)
    return user


@pytest.fixture
def leader_client(api_client: APIClient, dart_leader: User) -> APIClient:
    """A client signed in as the ``dart_leader`` fixture."""
    api_client.force_login(dart_leader)
    return api_client


# --------------------------------------------------------------------------
# set_verifier
# --------------------------------------------------------------------------
def test_set_verifier_adds_the_role(dart_leader: User, pilot: User) -> None:
    """``wanted`` true leaves the target holding the verifier role."""
    set_verifier(dart_leader, pilot, wanted=True)
    pilot.refresh_from_db()
    assert pilot.roles == [MEMBER, VERIFIER]


def test_set_verifier_removes_the_role(dart_leader: User, verifier: User) -> None:
    """``wanted`` false takes the verifier role away and keeps the rest."""
    set_verifier(dart_leader, verifier, wanted=False)
    verifier.refresh_from_db()
    assert verifier.roles == [MEMBER]


def test_set_verifier_records_the_role_change(
    dart_leader: User, pilot: User, audit_log: pytest.LogCaptureFixture
) -> None:
    """The grant is audited as ``account.roles`` naming the role added."""
    set_verifier(dart_leader, pilot, wanted=True)
    assert audit_messages(audit_log) == [
        f"action={audit.ACCOUNT_ROLES} actor={dart_leader.pk} target={pilot.pk} "
        "added=verifier removed=-"
    ]


def test_set_verifier_raises_roles_changed(
    dart_leader: User, pilot: User, recorded_events: RecordedEvents
) -> None:
    """The grant is raised as ``roles_changed`` with the leader as the actor."""
    set_verifier(dart_leader, pilot, wanted=True)
    assert recorded_events == [
        (
            "roles_changed",
            {"user": pilot, "added": [VERIFIER], "removed": [], "actor": dart_leader},
        )
    ]


def test_set_verifier_that_changes_nothing_writes_nothing(
    dart_leader: User,
    verifier: User,
    audit_log: pytest.LogCaptureFixture,
    recorded_events: RecordedEvents,
) -> None:
    """Granting a role the target already holds records and raises nothing."""
    set_verifier(dart_leader, verifier, wanted=True)
    assert (audit_messages(audit_log), recorded_events) == ([], [])


# --------------------------------------------------------------------------
# The grant endpoint
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("slug", "allowed"), role_matrix(DART_LEADER, USER_ADMIN, SYSTEM_ADMIN))
def test_verifier_grant_role_matrix(
    api_client: APIClient,
    all_role_users: dict[str, User],
    pilot: User,
    slug: str,
    allowed: bool,
) -> None:
    """Only a DART leader, a user administrator, or a system administrator grants it."""
    api_client.force_login(all_role_users[slug])
    response = api_client.put(verifier_url(pilot), {"verifier": True}, format="json")
    assert response.status_code == (200 if allowed else 403)


def test_granting_answers_the_status_card(leader_client: APIClient, pilot: User) -> None:
    """The response is the status card, reading the member as a verifier."""
    response = leader_client.put(verifier_url(pilot), {"verifier": True}, format="json")
    assert response.json()["is_verifier"] is True


def test_revoking_answers_the_status_card(leader_client: APIClient, verifier: User) -> None:
    """Revoking reads the member as no longer a verifier."""
    response = leader_client.put(verifier_url(verifier), {"verifier": False}, format="json")
    assert response.json()["is_verifier"] is False


def test_the_granted_member_reads_the_role_on_their_own_account(
    leader_client: APIClient, api_client: APIClient, pilot: User
) -> None:
    """``GET /auth/me`` for the member lists the verifier role."""
    leader_client.put(verifier_url(pilot), {"verifier": True}, format="json")
    api_client.force_login(pilot)
    assert api_client.get("/api/v1/auth/me").json()["roles"] == [MEMBER, VERIFIER]


def test_the_verifier_flag_is_required(leader_client: APIClient, pilot: User) -> None:
    """A body without ``verifier`` is refused under that field."""
    response = leader_client.put(verifier_url(pilot), {}, format="json")
    assert (response.status_code, list(response.json())) == (400, ["verifier"])


@pytest.mark.parametrize("kind", ["unknown", "donor", "deactivated"])
def test_granting_answers_404_for_someone_the_check_never_shows(
    leader_client: APIClient, kind: str
) -> None:
    """An unknown id, a donor, and a deactivated account are all 404."""
    if kind == "unknown":
        url = "/api/v1/leader/members/999999/verifier"
    else:
        target = UserFactory(
            kind=AccountKind.DONOR if kind == "donor" else AccountKind.MEMBER,
            is_active=kind != "deactivated",
        )
        url = verifier_url(target)
    assert leader_client.put(url, {"verifier": True}, format="json").status_code == 404
