"""The member check card names the operational roles the person holds.

A leader reading the card before a flight sees whether the person is a DART leader and
whether they are a verifier, each a boolean on ``GET /leader/members/{id}/status``.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import DART_LEADER, VERIFIER
from tests.factories import MemberProfileFactory, UserFactory

pytestmark = pytest.mark.django_db


def _card(client: APIClient, user: User) -> dict[str, object]:
    """The status card of ``user`` as ``client`` reads it."""
    response = client.get(f"/api/v1/leader/members/{user.pk}/status")
    card: dict[str, object] = response.json()
    return card


@pytest.mark.parametrize(
    ("roles", "expected"),
    [
        ((), (False, False)),
        ((DART_LEADER,), (True, False)),
        ((VERIFIER,), (False, True)),
        ((DART_LEADER, VERIFIER), (True, True)),
    ],
    ids=["neither", "leader", "verifier", "both"],
)
def test_the_card_says_whether_the_person_leads_a_dart_and_verifies(
    api_client: APIClient, dart_leader: User, roles: tuple[str, ...], expected: tuple[bool, bool]
) -> None:
    """``(is_dart_leader, is_verifier)`` follow the roles the person holds."""
    person = UserFactory(email="pat@example.test")
    MemberProfileFactory(user=person)
    for role in roles:
        person.add_role(role)
    api_client.force_login(dart_leader)
    card = _card(api_client, person)
    assert (card["is_dart_leader"], card["is_verifier"]) == expected
