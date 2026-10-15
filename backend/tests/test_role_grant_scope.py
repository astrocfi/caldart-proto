"""Who may grant or remove which role, on whose account.

The two-factor roles (``GUARDED_ROLES``) are granted and removed only by somebody who
holds the role, or by a system administrator; any user administrator grants and removes
the others.  A system administrator, a role-less Django superuser among them, may move
every role on anybody else.  Nobody changes their own roles.  The user record reports
which boxes the caller may change as ``assignable_roles``, and the Django admin shows the
roles read-only.
"""

from __future__ import annotations

import logging

import pytest
from django.contrib.admin.sites import site as admin_site
from django.test import Client, RequestFactory
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import (
    DART_LEADER,
    GUARDED_ROLES,
    MANAGEMENT,
    MEMBER,
    ROLE_SLUGS,
    SYSTEM_ADMIN,
    TREASURER,
    USER_ADMIN,
    VERIFIER,
)
from apps.accounts.services import OWN_ROLES_REFUSED, ROLE_NOT_HELD_REFUSED, set_verifier
from caldart.exceptions import DomainPermissionError
from tests.conftest import audit_messages, role_matrix
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

USERS = "/api/v1/admin/users"

#: The roles any user administrator moves, plus their own ``user_admin``.
USER_ADMIN_MOVES = (MEMBER, VERIFIER, DART_LEADER, USER_ADMIN)

#: The guarded roles a user administrator may also hold, every one but ``system_admin``.
HOLDABLE_GUARDED = [slug for slug in GUARDED_ROLES if slug != SYSTEM_ADMIN]


def detail(user: User) -> str:
    """``/admin/users/{id}`` for ``user``."""
    return f"{USERS}/{user.pk}"


@pytest.fixture
def target(db: None) -> User:
    """An account holding no role at all, for a role to be granted to."""
    return UserFactory(email="target@example.test", roles=[])


@pytest.fixture
def bare_superuser(db: None) -> User:
    """A superuser without the ``system_admin`` role, as ``createsuperuser`` makes one."""
    return UserFactory(
        email="bare-root@example.test", roles=[MEMBER], is_superuser=True, is_staff=True
    )


# --------------------------------------------------------------------------
# A user administrator's reach
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("slug", "allowed"), role_matrix(*USER_ADMIN_MOVES))
def test_a_user_admin_grants_only_the_roles_open_to_them(
    api_client: APIClient, user_admin: User, target: User, slug: str, allowed: bool
) -> None:
    """A plain user administrator grants the unguarded roles and their own, no other."""
    api_client.force_login(user_admin)
    response = api_client.patch(detail(target), {"roles": [slug]}, format="json")

    assert response.status_code == (200 if allowed else 400)


@pytest.mark.parametrize(("slug", "allowed"), role_matrix(*USER_ADMIN_MOVES))
def test_a_user_admin_removes_only_the_roles_open_to_them(
    api_client: APIClient, user_admin: User, slug: str, allowed: bool
) -> None:
    """Taking a role away follows the same rule as granting it."""
    holder = UserFactory(email="holder@example.test", roles=[slug])
    api_client.force_login(user_admin)
    api_client.patch(detail(holder), {"roles": []}, format="json")

    holder.refresh_from_db()
    assert (holder.roles == []) is allowed


@pytest.mark.parametrize("slug", HOLDABLE_GUARDED)
def test_a_user_admin_who_holds_a_guarded_role_may_grant_it(
    api_client: APIClient, target: User, slug: str
) -> None:
    """Holding the role is what opens it: a user admin who is also, say, a treasurer."""
    actor = UserFactory(email="ua-plus@example.test", roles=[MEMBER, USER_ADMIN, slug])
    api_client.force_login(actor)
    api_client.patch(detail(target), {"roles": [MEMBER, slug]}, format="json")

    target.refresh_from_db()
    assert target.roles == [MEMBER, slug]


@pytest.mark.parametrize("slug", HOLDABLE_GUARDED)
def test_a_user_admin_who_holds_a_guarded_role_may_remove_it(
    api_client: APIClient, slug: str
) -> None:
    """And may take the same role away from somebody else."""
    actor = UserFactory(email="ua-plus@example.test", roles=[MEMBER, USER_ADMIN, slug])
    holder = UserFactory(email="holder@example.test", roles=[MEMBER, slug])
    api_client.force_login(actor)
    api_client.patch(detail(holder), {"roles": [MEMBER]}, format="json")

    holder.refresh_from_db()
    assert holder.roles == [MEMBER]


def test_a_user_admin_without_treasurer_may_not_remove_it(
    api_client: APIClient, user_admin: User, treasurer: User
) -> None:
    """The refusal names the role, against ``roles``."""
    api_client.force_login(user_admin)
    response = api_client.patch(detail(treasurer), {"roles": [MEMBER]}, format="json")

    assert response.json() == {"roles": [ROLE_NOT_HELD_REFUSED.format(roles="Treasurer")]}


def test_the_refusal_names_every_role_not_held_in_privilege_order(
    api_client: APIClient, user_admin: User, target: User
) -> None:
    """Two roles the caller lacks are both named, least privileged first."""
    api_client.force_login(user_admin)
    response = api_client.patch(
        detail(target), {"roles": [MANAGEMENT, TREASURER, DART_LEADER]}, format="json"
    )

    assert response.json() == {
        "roles": [ROLE_NOT_HELD_REFUSED.format(roles="Treasurer, CalDART management")]
    }


def test_a_refused_list_writes_none_of_its_roles(
    api_client: APIClient, user_admin: User, target: User
) -> None:
    """The allowed half of a refused list is not saved either."""
    api_client.force_login(user_admin)
    api_client.patch(detail(target), {"roles": [DART_LEADER, TREASURER]}, format="json")

    target.refresh_from_db()
    assert target.roles == []


def test_a_role_not_held_is_refused_in_the_audit_log(
    api_client: APIClient,
    user_admin: User,
    target: User,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """The refusal is a WARNING line naming both accounts and the reason."""
    api_client.force_login(user_admin)
    api_client.patch(detail(target), {"roles": [TREASURER]}, format="json")

    assert audit_messages(audit_log, logging.WARNING) == [
        f"action=account.roles actor={user_admin.pk} target={target.pk} reason=roles_not_held"
    ]


def test_a_user_admin_may_change_the_open_roles_of_a_treasurer(
    api_client: APIClient, user_admin: User, treasurer: User
) -> None:
    """A guarded role the target keeps is no obstacle to moving an open one."""
    api_client.force_login(user_admin)
    api_client.patch(detail(treasurer), {"roles": [MEMBER, DART_LEADER, TREASURER]}, format="json")

    treasurer.refresh_from_db()
    assert treasurer.roles == [MEMBER, DART_LEADER, TREASURER]


# --------------------------------------------------------------------------
# A system administrator's reach
# --------------------------------------------------------------------------
@pytest.mark.parametrize("slug", ROLE_SLUGS)
def test_a_system_admin_grants_every_role(
    api_client: APIClient, system_admin: User, target: User, slug: str
) -> None:
    """Every role, held or not."""
    api_client.force_login(system_admin)
    api_client.patch(detail(target), {"roles": [slug]}, format="json")

    target.refresh_from_db()
    assert target.roles == [slug]


@pytest.mark.parametrize("slug", ROLE_SLUGS)
def test_a_system_admin_removes_every_role(
    api_client: APIClient, system_admin: User, slug: str
) -> None:
    """And takes every role away."""
    holder = UserFactory(email="holder@example.test", roles=[slug])
    api_client.force_login(system_admin)
    api_client.patch(detail(holder), {"roles": []}, format="json")

    holder.refresh_from_db()
    assert holder.roles == []


def test_a_role_less_superuser_grants_a_role_it_does_not_hold(
    api_client: APIClient, bare_superuser: User, target: User
) -> None:
    """A Django superuser counts as a system administrator, role group or not."""
    api_client.force_login(bare_superuser)
    api_client.patch(detail(target), {"roles": [TREASURER]}, format="json")

    target.refresh_from_db()
    assert target.roles == [TREASURER]


# --------------------------------------------------------------------------
# Your own roles
# --------------------------------------------------------------------------
@pytest.mark.parametrize("actor_fixture", ["user_admin", "system_admin", "bare_superuser"])
def test_nobody_may_change_their_own_roles(
    api_client: APIClient, request: pytest.FixtureRequest, actor_fixture: str
) -> None:
    """Even a system administrator is refused 403 on their own record."""
    actor: User = request.getfixturevalue(actor_fixture)
    api_client.force_login(actor)
    response = api_client.patch(detail(actor), {"roles": [*actor.roles, DART_LEADER]})

    assert (response.status_code, response.json()) == (403, {"detail": OWN_ROLES_REFUSED})


def test_taking_away_your_own_role_is_refused_too(api_client: APIClient, user_admin: User) -> None:
    """Removing is a change like granting, and leaves the roles as they were."""
    api_client.force_login(user_admin)
    api_client.patch(detail(user_admin), {"roles": [MEMBER]}, format="json")

    user_admin.refresh_from_db()
    assert user_admin.roles == [MEMBER, USER_ADMIN]


def test_changing_your_own_roles_is_refused_in_the_audit_log(
    api_client: APIClient, user_admin: User, audit_log: pytest.LogCaptureFixture
) -> None:
    """The refusal is audited with the reason ``own_account``."""
    api_client.force_login(user_admin)
    api_client.patch(detail(user_admin), {"roles": [MEMBER, USER_ADMIN, TREASURER]}, format="json")

    assert audit_messages(audit_log, logging.WARNING) == [
        f"action=account.roles actor={user_admin.pk} target={user_admin.pk} reason=own_account"
    ]


def test_resending_your_own_roles_unchanged_is_no_change(
    api_client: APIClient, user_admin: User
) -> None:
    """A list that changes nothing is not refused, so a resent form still saves."""
    api_client.force_login(user_admin)
    response = api_client.patch(detail(user_admin), {"roles": [USER_ADMIN, MEMBER]})

    assert response.status_code == 200


def test_a_dart_leader_may_not_make_themselves_a_verifier(dart_leader: User) -> None:
    """The member check's verifier toggle writes roles too, under the same rule."""
    with pytest.raises(DomainPermissionError, match=OWN_ROLES_REFUSED):
        set_verifier(dart_leader, dart_leader, wanted=True)


# --------------------------------------------------------------------------
# What the user record reports
# --------------------------------------------------------------------------
def test_the_record_lists_the_roles_a_user_admin_may_change(
    api_client: APIClient, user_admin: User, member: User
) -> None:
    """The open roles and the caller's own guarded ones, in privilege order."""
    api_client.force_login(user_admin)

    assert api_client.get(detail(member)).json()["assignable_roles"] == list(USER_ADMIN_MOVES)


def test_the_record_lists_every_role_for_a_system_admin(
    api_client: APIClient, system_admin: User, member: User
) -> None:
    """A system administrator may change every box."""
    api_client.force_login(system_admin)

    assert api_client.get(detail(member)).json()["assignable_roles"] == list(ROLE_SLUGS)


def test_the_record_lists_no_role_on_your_own_account(
    api_client: APIClient, system_admin: User
) -> None:
    """Your own record offers no box at all."""
    api_client.force_login(system_admin)

    assert api_client.get(detail(system_admin)).json()["assignable_roles"] == []


def test_a_saved_record_lists_the_roles_too(
    api_client: APIClient, user_admin: User, member: User
) -> None:
    """The ``PATCH`` answer is the same record, so the form stays right after a save."""
    api_client.force_login(user_admin)
    response = api_client.patch(detail(member), {"roles": [MEMBER, VERIFIER]}, format="json")

    assert response.json()["assignable_roles"] == list(USER_ADMIN_MOVES)


# --------------------------------------------------------------------------
# The Django admin
# --------------------------------------------------------------------------
@pytest.mark.parametrize("field", ["groups", "is_superuser", "is_staff"])
def test_the_django_admin_shows_the_role_fields_read_only(
    superuser: User, member: User, field: str
) -> None:
    """Roles and the flags they set change on the user record alone."""
    model_admin = admin_site._registry[User]
    request = RequestFactory().get("/")
    request.user = superuser

    assert field in model_admin.get_readonly_fields(request, member)


def test_posting_groups_to_the_django_admin_changes_no_role(superuser: User, member: User) -> None:
    """A role posted to the change form is ignored."""
    browser = Client()
    browser.force_login(superuser)
    group = User.objects.get(pk=superuser.pk).groups.get()
    response = browser.post(
        f"/django-admin/accounts/user/{member.pk}/change/",
        {
            "first_name": member.first_name,
            "last_name": member.last_name,
            "groups": [group.pk],
            "is_superuser": "on",
            "is_staff": "on",
            "date_joined_0": "2026-01-01",
            "date_joined_1": "00:00:00",
        },
    )

    assert response.status_code == 302
    member.refresh_from_db()
    assert (member.roles, member.is_superuser) == ([MEMBER], False)
