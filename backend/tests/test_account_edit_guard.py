"""The account-edit guard on both administrator edit endpoints.

A protected change -- the email address or the active flag -- is refused unless the
actor holds every role the target holds.  A Django superuser counts as a system
administrator whether or not the role group was ever added.  These cases replay the
takeover the guard closes, check the edits that stay allowed, and mark how far a
caller who may also write roles reaches over a second request.  What a refusal
writes to the audit log is ``tests/test_audit_logging.py``.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core import mail

from apps.accounts.roles import ACCOUNT_ADMIN, DART_LEADER, MEMBER, SYSTEM_ADMIN, USER_ADMIN
from apps.accounts.services import (
    EMAIL_CHANGE_REFUSED,
    SELF_DEACTIVATION_REFUSED,
    STATUS_CHANGE_REFUSED,
)
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

User = get_user_model()

USERS = "/api/v1/admin/users"
MEMBERS = "/api/v1/admin/members"
RESET = "/api/v1/auth/password/reset"

#: The address an attacker would move a privileged account to.
ATTACKER_EMAIL = "attacker@example.test"


def user_detail(user) -> str:
    """``/admin/users/{id}`` for ``user``."""
    return f"{USERS}/{user.pk}"


def member_detail(user) -> str:
    """``/admin/members/{user_id}`` for ``user``."""
    return f"{MEMBERS}/{user.pk}"


#: Both edit endpoints, each with the role that opens it.  The slugs double as
#: the names of the role fixtures in ``conftest.py``.
BOTH_ENDPOINTS = [
    pytest.param(USER_ADMIN, user_detail, id="users-endpoint"),
    pytest.param(ACCOUNT_ADMIN, member_detail, id="members-endpoint"),
]

#: The two ways an account counts as a system administrator's, by fixture name: the
#: role group, and the bare Django superuser flag ``createsuperuser`` sets on its own.
PROTECTED_TARGETS = ["system_admin", "bare_superuser"]


@pytest.fixture
def bare_superuser(db):
    """A superuser without the ``system_admin`` role, as ``createsuperuser`` makes one."""
    return UserFactory(
        email="root-no-role@example.test", roles=[MEMBER], is_superuser=True, is_staff=True
    )


# --------------------------------------------------------------------------
# Refused: a target holding roles the actor does not hold
# --------------------------------------------------------------------------
@pytest.mark.parametrize("target_fixture", PROTECTED_TARGETS)
@pytest.mark.parametrize(("actor_role", "detail"), BOTH_ENDPOINTS)
def test_a_lower_admin_cannot_change_a_protected_accounts_email(
    request, api_client, target_fixture, actor_role, detail
) -> None:
    """``is_superuser`` alone protects an account: it means system administrator."""
    target = request.getfixturevalue(target_fixture)
    stored_email = target.email
    api_client.force_login(request.getfixturevalue(actor_role))
    response = api_client.patch(detail(target), {"email": ATTACKER_EMAIL})

    assert response.status_code == 400
    assert response.json()["email"] == [EMAIL_CHANGE_REFUSED]
    target.refresh_from_db()
    assert target.email == stored_email


@pytest.mark.parametrize("target_fixture", PROTECTED_TARGETS)
@pytest.mark.parametrize(("actor_role", "detail"), BOTH_ENDPOINTS)
def test_a_lower_admin_cannot_deactivate_a_protected_account(
    request, api_client, target_fixture, actor_role, detail
) -> None:
    """The Active box is guarded exactly as the address is, on both kinds of target."""
    target = request.getfixturevalue(target_fixture)
    api_client.force_login(request.getfixturevalue(actor_role))
    response = api_client.patch(detail(target), {"is_active": False})

    assert response.status_code == 400
    assert response.json()["is_active"] == [STATUS_CHANGE_REFUSED]
    target.refresh_from_db()
    assert target.is_active is True


def test_an_account_admin_cannot_change_a_user_admins_email(
    api_client, account_admin, user_admin
) -> None:
    """The rule is general: a role the target holds and the actor lacks is enough."""
    api_client.force_login(account_admin)
    response = api_client.patch(member_detail(user_admin), {"email": ATTACKER_EMAIL})

    assert response.status_code == 400
    assert response.json()["email"] == [EMAIL_CHANGE_REFUSED]
    user_admin.refresh_from_db()
    assert user_admin.email == "useradmin@example.test"


def test_a_user_admin_cannot_change_an_account_admins_email(
    api_client, user_admin, account_admin
) -> None:
    api_client.force_login(user_admin)
    response = api_client.patch(user_detail(account_admin), {"email": ATTACKER_EMAIL})

    assert response.status_code == 400
    assert response.json()["email"] == [EMAIL_CHANGE_REFUSED]
    account_admin.refresh_from_db()
    assert account_admin.email == "accountadmin@example.test"


def test_a_user_admin_cannot_deactivate_a_dart_leader(api_client, user_admin, dart_leader) -> None:
    """Any role the actor lacks protects the account, administrative or not."""
    api_client.force_login(user_admin)
    response = api_client.patch(user_detail(dart_leader), {"is_active": False})

    assert response.status_code == 400
    assert response.json()["is_active"] == [STATUS_CHANGE_REFUSED]
    dart_leader.refresh_from_db()
    assert dart_leader.is_active is True


def test_an_account_admin_cannot_deactivate_themselves(api_client, account_admin) -> None:
    api_client.force_login(account_admin)
    response = api_client.patch(member_detail(account_admin), {"is_active": False})

    assert response.status_code == 400
    assert response.json()["is_active"] == [SELF_DEACTIVATION_REFUSED]
    account_admin.refresh_from_db()
    assert account_admin.is_active is True


# --------------------------------------------------------------------------
# Allowed
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("actor_role", "detail"), BOTH_ENDPOINTS)
def test_an_admin_may_still_change_a_plain_members_email(
    request, api_client, member, actor_role, detail
) -> None:
    actor = request.getfixturevalue(actor_role)
    api_client.force_login(actor)
    response = api_client.patch(detail(member), {"email": "marta@example.test"})

    assert response.status_code == 200
    member.refresh_from_db()
    assert member.email == "marta@example.test"


def test_a_system_admin_may_change_another_system_admins_email(
    api_client, system_admin, user_factory
) -> None:
    target = user_factory(email="other-sysadmin@example.test", roles=[MEMBER, SYSTEM_ADMIN])
    api_client.force_login(system_admin)
    response = api_client.patch(user_detail(target), {"email": "moved@example.test"})

    assert response.status_code == 200
    target.refresh_from_db()
    assert target.email == "moved@example.test"


def test_a_role_less_superuser_may_change_a_system_admins_email(
    api_client, bare_superuser, system_admin
) -> None:
    """The superuser flag satisfies the rule for the actor as well as the target."""
    api_client.force_login(bare_superuser)
    response = api_client.patch(user_detail(system_admin), {"email": "moved@example.test"})

    assert response.status_code == 200
    system_admin.refresh_from_db()
    assert system_admin.email == "moved@example.test"


@pytest.mark.parametrize(("actor_role", "detail"), BOTH_ENDPOINTS)
def test_resending_the_stored_values_with_a_name_change_succeeds(
    request, api_client, system_admin, actor_role, detail
) -> None:
    """The portal sends the whole form, so an unchanged protected field is no change."""
    actor = request.getfixturevalue(actor_role)
    api_client.force_login(actor)
    response = api_client.patch(
        detail(system_admin),
        {"email": system_admin.email, "is_active": True, "first_name": "Renamed"},
    )

    assert response.status_code == 200
    system_admin.refresh_from_db()
    assert system_admin.first_name == "Renamed"


def test_an_email_that_differs_only_in_case_is_not_a_change(
    api_client, user_admin, system_admin
) -> None:
    """The save is allowed, and the record keeps the address it was stored under."""
    api_client.force_login(user_admin)
    response = api_client.patch(user_detail(system_admin), {"email": system_admin.email.upper()})

    assert response.status_code == 200
    system_admin.refresh_from_db()
    assert system_admin.email == "sysadmin@example.test"


def test_an_admin_who_may_edit_the_address_saves_the_case_they_sent(
    api_client, system_admin, member
) -> None:
    """Nothing is dropped from a record the actor may edit: the write goes in verbatim."""
    api_client.force_login(system_admin)
    response = api_client.patch(user_detail(member), {"email": member.email.upper()})

    assert response.status_code == 200
    member.refresh_from_db()
    assert member.email == "MEMBER@EXAMPLE.TEST"


def test_a_user_admin_may_still_rename_a_system_admin(api_client, user_admin, system_admin) -> None:
    api_client.force_login(user_admin)
    response = api_client.patch(user_detail(system_admin), {"last_name": "Okonkwo"})

    assert response.status_code == 200
    system_admin.refresh_from_db()
    assert system_admin.last_name == "Okonkwo"


# --------------------------------------------------------------------------
# Roles: the flag that makes an account a system administrator
# --------------------------------------------------------------------------
def test_a_user_admin_may_save_the_whole_form_of_a_role_less_superuser(
    api_client, user_admin, bare_superuser
) -> None:
    """The portal posts every field, so correcting a name resends the stored role list.

    That list is not a write: the groups and the superuser flag stay as they were,
    and the name is saved.
    """
    api_client.force_login(user_admin)
    response = api_client.patch(
        user_detail(bare_superuser),
        {
            "first_name": bare_superuser.first_name,
            "last_name": "Lovelace",
            "email": bare_superuser.email,
            "is_active": True,
            "roles": [MEMBER],
        },
    )

    assert response.status_code == 200
    bare_superuser.refresh_from_db()
    assert bare_superuser.last_name == "Lovelace"
    assert bare_superuser.is_superuser is True
    assert bare_superuser.roles == [MEMBER]


def test_a_user_admin_cannot_change_a_role_less_superusers_roles(
    api_client, user_admin, bare_superuser
) -> None:
    """A different list rebuilds ``is_superuser``, so it drops ``system_admin``."""
    api_client.force_login(user_admin)
    response = api_client.patch(user_detail(bare_superuser), {"roles": [MEMBER, DART_LEADER]})

    assert response.status_code == 400
    assert "roles" in response.json()
    bare_superuser.refresh_from_db()
    assert bare_superuser.roles == [MEMBER]
    assert bare_superuser.is_superuser is True


def test_a_user_admin_cannot_grant_the_system_admin_role_to_a_role_less_superuser(
    api_client, user_admin, bare_superuser
) -> None:
    """Ticking the box grants the role, even on an account that counts as one already."""
    api_client.force_login(user_admin)
    response = api_client.patch(user_detail(bare_superuser), {"roles": [MEMBER, SYSTEM_ADMIN]})

    assert response.status_code == 400
    assert "roles" in response.json()
    bare_superuser.refresh_from_db()
    assert bare_superuser.roles == [MEMBER]


def test_a_system_admin_may_record_the_role_on_a_role_less_superuser(
    api_client, system_admin, bare_superuser
) -> None:
    """The group the account never had is a system administrator's to add."""
    api_client.force_login(system_admin)
    response = api_client.patch(user_detail(bare_superuser), {"roles": [MEMBER, SYSTEM_ADMIN]})

    assert response.status_code == 200
    bare_superuser.refresh_from_db()
    assert bare_superuser.roles == [MEMBER, SYSTEM_ADMIN]
    assert bare_superuser.is_superuser is True


def test_the_roles_guard_keeps_a_role_less_superusers_email_out_of_reach(
    api_client, user_admin, bare_superuser
) -> None:
    """The two-request takeover: try to drop the flag first, then move the address.

    Resending the stored role list changes nothing, so the account still counts as a
    system administrator when the second request arrives.
    """
    api_client.force_login(user_admin)
    api_client.patch(user_detail(bare_superuser), {"roles": [MEMBER]})

    response = api_client.patch(user_detail(bare_superuser), {"email": ATTACKER_EMAIL})

    assert response.status_code == 400
    bare_superuser.refresh_from_db()
    assert bare_superuser.email == "root-no-role@example.test"


# --------------------------------------------------------------------------
# Roles: how far a second request reaches
# --------------------------------------------------------------------------
def test_a_user_admin_lifts_the_refusal_by_granting_themselves_the_missing_role(
    api_client, user_admin, dart_leader
) -> None:
    """The guard judges one write, and granting roles is the user administrator's job.

    Taking ``dart_leader`` for themselves is an ordinary role write, and the address
    it was protecting is then theirs to move.  The user guide says so; this pins the
    boundary, which ``system_admin`` is the one role outside.
    """
    api_client.force_login(user_admin)
    granted = api_client.patch(
        user_detail(user_admin), {"roles": [MEMBER, USER_ADMIN, DART_LEADER]}
    )
    assert granted.status_code == 200

    response = api_client.patch(user_detail(dart_leader), {"email": ATTACKER_EMAIL})

    assert response.status_code == 200
    dart_leader.refresh_from_db()
    assert dart_leader.email == ATTACKER_EMAIL


def test_a_user_admin_cannot_grant_themselves_the_system_admin_role(
    api_client, user_admin, system_admin
) -> None:
    """The one role that cannot be self-granted, so the address stays out of reach."""
    api_client.force_login(user_admin)
    granted = api_client.patch(
        user_detail(user_admin), {"roles": [MEMBER, USER_ADMIN, SYSTEM_ADMIN]}
    )
    assert granted.status_code == 400

    response = api_client.patch(user_detail(system_admin), {"email": ATTACKER_EMAIL})

    assert response.status_code == 400
    system_admin.refresh_from_db()
    assert system_admin.email == "sysadmin@example.test"


def test_the_roles_guard_keeps_a_system_admins_email_out_of_reach(
    api_client, user_admin, system_admin
) -> None:
    """The mirror route: strip the role from the target first, then move the address."""
    api_client.force_login(user_admin)
    stripped = api_client.patch(user_detail(system_admin), {"roles": [MEMBER]})
    assert stripped.status_code == 400

    response = api_client.patch(user_detail(system_admin), {"email": ATTACKER_EMAIL})

    assert response.status_code == 400
    system_admin.refresh_from_db()
    assert system_admin.email == "sysadmin@example.test"


def test_a_role_less_superuser_may_grant_the_system_admin_role(
    api_client, bare_superuser, member
) -> None:
    """The superuser flag satisfies the roles guard for the actor as well."""
    api_client.force_login(bare_superuser)
    response = api_client.patch(user_detail(member), {"roles": [MEMBER, SYSTEM_ADMIN]})

    assert response.status_code == 200
    member.refresh_from_db()
    assert member.is_superuser is True


# --------------------------------------------------------------------------
# Delete
# --------------------------------------------------------------------------
def test_an_account_admin_cannot_delete_a_role_less_superuser(
    api_client, account_admin, bare_superuser
) -> None:
    api_client.force_login(account_admin)
    response = api_client.delete(member_detail(bare_superuser))

    assert response.status_code == 403
    assert User.objects.filter(pk=bare_superuser.pk).exists() is True


def test_a_role_less_superuser_may_delete_a_system_admin(
    api_client, bare_superuser, system_admin
) -> None:
    api_client.force_login(bare_superuser)
    response = api_client.delete(member_detail(system_admin))

    assert response.status_code == 204
    assert User.objects.filter(pk=system_admin.pk).exists() is False


# --------------------------------------------------------------------------
# The takeover, end to end
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("actor_role", "detail"), BOTH_ENDPOINTS)
def test_a_refused_email_edit_leaves_the_attacker_no_reset_email(
    request, api_client, system_admin, actor_role, detail
) -> None:
    """The takeover chain: move the address, then ask for a reset link at it."""
    actor = request.getfixturevalue(actor_role)
    api_client.force_login(actor)
    api_client.patch(detail(system_admin), {"email": ATTACKER_EMAIL})
    mail.outbox.clear()

    response = api_client.post(RESET, {"email": ATTACKER_EMAIL})

    assert response.status_code == 204
    assert len(mail.outbox) == 0
