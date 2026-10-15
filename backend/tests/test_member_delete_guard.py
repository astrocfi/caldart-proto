"""Deleting and deactivating a member follow the account-edit guard.

``DELETE /admin/members/{user_id}`` is refused 403, and ``POST .../deactivate`` 400,
unless the caller holds every two-factor role the account holds; member, DART leader,
and verifier do not count.  A system administrator, a role-less Django superuser among
them, holds them all.
"""

from __future__ import annotations

import logging

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import (
    ACCOUNT_ADMIN,
    DART_LEADER,
    MEMBER,
    SYSTEM_ADMIN,
    TREASURER,
    VERIFIER,
)
from apps.members.services import ROLES_NOT_HELD_DELETE_REFUSED
from tests.conftest import audit_messages, role_matrix
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

MEMBERS = "/api/v1/admin/members"


def detail(user: User) -> str:
    """``/admin/members/{user_id}`` for ``user``."""
    return f"{MEMBERS}/{user.pk}"


#: The target roles an account administrator may act on: their own two-factor role and
#: every role that is not one.  The system administrator's own refusal is pinned in
#: test_members_admin.py, so the matrices leave that role out.
ACCOUNT_ADMIN_REACH = [
    case
    for case in role_matrix(MEMBER, VERIFIER, DART_LEADER, ACCOUNT_ADMIN)
    if case[0] != SYSTEM_ADMIN
]


@pytest.mark.parametrize(("slug", "allowed"), ACCOUNT_ADMIN_REACH)
def test_an_account_admin_deletes_only_an_account_whose_two_factor_roles_they_hold(
    account_admin_client: APIClient, slug: str, allowed: bool
) -> None:
    """A target holding a two-factor role the account administrator lacks stays."""
    target = UserFactory(email="target@example.test", roles=[MEMBER, slug])
    response = account_admin_client.delete(detail(target))

    assert response.status_code == (204 if allowed else 403)


@pytest.mark.parametrize(("slug", "allowed"), ACCOUNT_ADMIN_REACH)
def test_an_account_admin_deactivates_only_an_account_whose_two_factor_roles_they_hold(
    account_admin_client: APIClient, slug: str, allowed: bool
) -> None:
    """The member record's deactivation follows the same rule."""
    target = UserFactory(email="target@example.test", roles=[MEMBER, slug])
    account_admin_client.post(f"{detail(target)}/deactivate")

    target.refresh_from_db()
    assert target.is_active is (not allowed)


def test_the_refusal_says_why(account_admin_client: APIClient, treasurer: User) -> None:
    """The 403 carries the sentence the service raised."""
    response = account_admin_client.delete(detail(treasurer))

    assert response.json() == {"detail": ROLES_NOT_HELD_DELETE_REFUSED}


def test_a_refused_delete_keeps_the_account(
    account_admin_client: APIClient, treasurer: User
) -> None:
    """Nothing is deleted."""
    account_admin_client.delete(detail(treasurer))

    assert User.objects.filter(pk=treasurer.pk).exists()


def test_a_refused_delete_is_audited(
    account_admin_client: APIClient,
    account_admin: User,
    treasurer: User,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """The refusal is a WARNING line with the reason ``roles_not_held``."""
    account_admin_client.delete(detail(treasurer))

    assert audit_messages(audit_log, logging.WARNING) == [
        f"action=member.delete actor={account_admin.pk} target={treasurer.pk} reason=roles_not_held"
    ]


def test_an_account_admin_who_also_holds_the_role_may_delete(api_client: APIClient) -> None:
    """Holding the target's roles is enough."""
    actor = UserFactory(email="both@example.test", roles=[MEMBER, ACCOUNT_ADMIN, TREASURER])
    target = UserFactory(email="target@example.test", roles=[MEMBER, TREASURER])
    api_client.force_login(actor)

    assert api_client.delete(detail(target)).status_code == 204


def test_a_role_less_superuser_may_delete_a_treasurer(
    api_client: APIClient, treasurer: User
) -> None:
    """A Django superuser counts as a system administrator."""
    actor = UserFactory(
        email="bare-root@example.test", roles=[MEMBER], is_superuser=True, is_staff=True
    )
    api_client.force_login(actor)

    assert api_client.delete(detail(treasurer)).status_code == 204
