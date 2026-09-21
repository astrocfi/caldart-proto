"""``accounts.services``: creating an account and the rules on editing one."""

from __future__ import annotations

import re

import pytest
from django.contrib.auth import get_user_model

from apps.accounts.roles import (
    ACCOUNT_ADMIN,
    DART_LEADER,
    MEMBER,
    SYSTEM_ADMIN,
    WEBSITE_ADMIN,
)
from apps.accounts.services import (
    EMAIL_CHANGE_REFUSED,
    ROLE_CHANGE_REFUSED,
    SELF_DEACTIVATION_REFUSED,
    STATUS_CHANGE_REFUSED,
    create_account,
    update_account,
)
from caldart.exceptions import DomainValidationError
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

User = get_user_model()


# --------------------------------------------------------------------------
# create_account
# --------------------------------------------------------------------------
def test_create_account_grants_the_member_role() -> None:
    user = create_account(email="joan.ames@example.test", password="Sierra-Foothills-2027")
    assert user.roles == [MEMBER]


def test_create_account_stores_the_names_stripped() -> None:
    user = create_account(email="joan.ames@example.test", first_name="  Joan ", last_name=" Ames ")
    assert (user.first_name, user.last_name) == ("Joan", "Ames")


def test_create_account_sets_the_password_it_is_given() -> None:
    user = create_account(email="joan.ames@example.test", password="Sierra-Foothills-2027")
    assert user.check_password("Sierra-Foothills-2027") is True


def test_create_account_without_a_password_leaves_it_unusable() -> None:
    """An invited account can only be opened by following the link that is mailed."""
    user = create_account(email="joan.ames@example.test")
    assert user.has_usable_password() is False


# --------------------------------------------------------------------------
# update_account: plain fields
# --------------------------------------------------------------------------
def test_update_account_writes_the_names(user_admin) -> None:
    target = UserFactory(email="target@example.test", roles=[MEMBER])
    update_account(user_admin, target, {"first_name": "Marta", "last_name": "Reyes"})
    target.refresh_from_db()
    assert target.display_name == "Marta Reyes"


def test_update_account_writes_the_email(user_admin) -> None:
    target = UserFactory(email="target@example.test", roles=[MEMBER])
    update_account(user_admin, target, {"email": "moved@example.test"})
    target.refresh_from_db()
    assert target.email == "moved@example.test"


def test_update_account_deactivates_another_account(user_admin) -> None:
    target = UserFactory(email="target@example.test", roles=[MEMBER])
    update_account(user_admin, target, {"is_active": False})
    target.refresh_from_db()
    assert target.is_active is False


# --------------------------------------------------------------------------
# update_account: self-deactivation
# --------------------------------------------------------------------------
def test_deactivating_your_own_account_is_refused(system_admin) -> None:
    with pytest.raises(DomainValidationError, match=re.escape(SELF_DEACTIVATION_REFUSED)):
        update_account(system_admin, system_admin, {"is_active": False})


def test_the_self_deactivation_refusal_names_the_is_active_field(system_admin) -> None:
    with pytest.raises(DomainValidationError) as refusal:
        update_account(system_admin, system_admin, {"is_active": False})
    assert refusal.value.field == "is_active"


def test_a_refused_self_deactivation_writes_nothing(system_admin) -> None:
    with pytest.raises(DomainValidationError):
        update_account(system_admin, system_admin, {"is_active": False, "first_name": "Ada"})
    system_admin.refresh_from_db()
    assert system_admin.is_active is True


def test_resending_your_own_active_flag_is_not_a_deactivation(user_admin) -> None:
    """The administration form posts every field, so an unmoved flag is no change."""
    update_account(user_admin, user_admin, {"is_active": True, "first_name": "Ada"})
    user_admin.refresh_from_db()
    assert user_admin.first_name == "Ada"


# --------------------------------------------------------------------------
# update_account: the system_admin role
# --------------------------------------------------------------------------
def test_a_user_admin_cannot_grant_system_admin(user_admin) -> None:
    target = UserFactory(email="target@example.test", roles=[MEMBER])
    with pytest.raises(DomainValidationError, match=re.escape(ROLE_CHANGE_REFUSED)):
        update_account(user_admin, target, {"roles": [MEMBER, SYSTEM_ADMIN]})


def test_the_role_refusal_names_the_roles_field(user_admin) -> None:
    target = UserFactory(email="target@example.test", roles=[MEMBER])
    with pytest.raises(DomainValidationError) as refusal:
        update_account(user_admin, target, {"roles": [MEMBER, SYSTEM_ADMIN]})
    assert refusal.value.field == "roles"


def test_a_user_admin_cannot_revoke_system_admin(user_admin, system_admin) -> None:
    with pytest.raises(DomainValidationError, match=re.escape(ROLE_CHANGE_REFUSED)):
        update_account(user_admin, system_admin, {"roles": [MEMBER]})


def test_a_user_admin_cannot_revoke_the_role_from_a_createsuperuser_account(user_admin) -> None:
    """The superuser flag alone makes the target a system administrator."""
    target = UserFactory(email="root2@example.test", roles=[], is_superuser=True, is_staff=True)
    with pytest.raises(DomainValidationError, match=re.escape(ROLE_CHANGE_REFUSED)):
        update_account(user_admin, target, {"roles": [MEMBER]})


def test_a_system_admin_may_grant_system_admin(system_admin) -> None:
    target = UserFactory(email="target@example.test", roles=[MEMBER])
    update_account(system_admin, target, {"roles": [MEMBER, SYSTEM_ADMIN]})
    target.refresh_from_db()
    assert target.roles == [MEMBER, SYSTEM_ADMIN]


def test_granting_system_admin_sets_the_superuser_flag(system_admin) -> None:
    target = UserFactory(email="target@example.test", roles=[MEMBER])
    update_account(system_admin, target, {"roles": [MEMBER, SYSTEM_ADMIN]})
    target.refresh_from_db()
    assert target.is_superuser is True


def test_revoking_system_admin_clears_the_superuser_flag(system_admin) -> None:
    target = UserFactory(email="target@example.test", roles=[MEMBER, SYSTEM_ADMIN])
    update_account(system_admin, target, {"roles": [MEMBER]})
    target.refresh_from_db()
    assert target.is_superuser is False


def test_granting_website_admin_keeps_the_wagtail_admin_reachable(user_admin) -> None:
    target = UserFactory(email="target@example.test", roles=[MEMBER])
    update_account(user_admin, target, {"roles": [MEMBER, WEBSITE_ADMIN]})
    target.refresh_from_db()
    assert target.is_staff is True


def test_resending_the_roles_an_account_already_holds_is_not_a_write(user_admin) -> None:
    """Rebuilding the flags from an unchanged list would strip a createsuperuser account."""
    target = UserFactory(email="root2@example.test", roles=[], is_superuser=True, is_staff=True)
    update_account(user_admin, target, {"roles": [], "first_name": "Ada"})
    target.refresh_from_db()
    assert target.is_superuser is True


def test_update_account_stores_the_roles_in_privilege_order(system_admin) -> None:
    target = UserFactory(email="target@example.test", roles=[MEMBER])
    update_account(system_admin, target, {"roles": [WEBSITE_ADMIN, MEMBER, DART_LEADER]})
    target.refresh_from_db()
    assert target.roles == [MEMBER, DART_LEADER, WEBSITE_ADMIN]


# --------------------------------------------------------------------------
# update_account: the takeover guard
# --------------------------------------------------------------------------
def test_a_user_admin_cannot_change_an_account_admins_email(user_admin, account_admin) -> None:
    with pytest.raises(DomainValidationError, match=re.escape(EMAIL_CHANGE_REFUSED)):
        update_account(user_admin, account_admin, {"email": "taken.over@example.test"})


def test_the_email_refusal_names_the_email_field(user_admin, account_admin) -> None:
    with pytest.raises(DomainValidationError) as refusal:
        update_account(user_admin, account_admin, {"email": "taken.over@example.test"})
    assert refusal.value.field == "email"


def test_a_user_admin_cannot_deactivate_an_account_admin(user_admin, account_admin) -> None:
    with pytest.raises(DomainValidationError, match=re.escape(STATUS_CHANGE_REFUSED)):
        update_account(user_admin, account_admin, {"is_active": False})


def test_a_system_admin_may_change_anybodys_email(system_admin, account_admin) -> None:
    update_account(system_admin, account_admin, {"email": "moved@example.test"})
    account_admin.refresh_from_db()
    assert account_admin.email == "moved@example.test"


def test_an_email_resent_in_another_case_is_not_written_back(user_admin, account_admin) -> None:
    """It alters nothing, so it is dropped rather than refused -- or saved."""
    update_account(user_admin, account_admin, {"email": account_admin.email.upper()})
    account_admin.refresh_from_db()
    assert account_admin.email == "accountadmin@example.test"


def test_names_are_never_protected(user_admin, account_admin) -> None:
    update_account(user_admin, account_admin, {"first_name": "Marta"})
    account_admin.refresh_from_db()
    assert account_admin.first_name == "Marta"


def test_a_dart_leaders_email_is_protected_from_a_user_admin(user_admin) -> None:
    """Every role counts towards the guard, administrative or not."""
    target = UserFactory(email="target@example.test", roles=[MEMBER, DART_LEADER])
    with pytest.raises(DomainValidationError, match=re.escape(EMAIL_CHANGE_REFUSED)):
        update_account(user_admin, target, {"email": "taken.over@example.test"})


def test_an_account_admin_may_change_a_plain_members_email(account_admin) -> None:
    target = UserFactory(email="target@example.test", roles=[MEMBER])
    update_account(account_admin, target, {"email": "moved@example.test"})
    target.refresh_from_db()
    assert target.email == "moved@example.test"


# --------------------------------------------------------------------------
# update_account: atomicity
# --------------------------------------------------------------------------
def test_update_account_writes_nothing_when_the_role_sync_fails(system_admin, monkeypatch) -> None:
    def boom(user) -> None:
        raise RuntimeError("flags exploded")

    monkeypatch.setattr("apps.accounts.services.sync_django_flags", boom)
    target = UserFactory(email="target@example.test", roles=[MEMBER])
    with pytest.raises(RuntimeError, match="flags exploded"):
        update_account(
            system_admin,
            target,
            {"email": "moved@example.test", "roles": [MEMBER, ACCOUNT_ADMIN]},
        )
    target.refresh_from_db()
    assert target.email == "target@example.test"


def test_update_account_returns_the_account_it_saved(user_admin) -> None:
    target = UserFactory(email="target@example.test", roles=[MEMBER])
    assert update_account(user_admin, target, {"first_name": "Marta"}) is target


def test_update_account_ignores_a_field_it_does_not_own(user_admin) -> None:
    """Only the account fields are written, whatever else the caller passes."""
    target = UserFactory(email="target@example.test", roles=[MEMBER])
    update_account(user_admin, target, {"first_name": "Marta", "is_superuser": True})
    target.refresh_from_db()
    assert target.is_superuser is False


def test_a_user_admin_cannot_take_over_a_system_admin_account(user_admin, system_admin) -> None:
    """The gap that let a user administrator redirect the reset link and take over."""
    with pytest.raises(DomainValidationError, match=re.escape(EMAIL_CHANGE_REFUSED)):
        update_account(user_admin, system_admin, {"email": "taken.over@example.test"})


def test_a_user_admin_cannot_lock_a_system_admin_out(user_admin, system_admin) -> None:
    with pytest.raises(DomainValidationError, match=re.escape(STATUS_CHANGE_REFUSED)):
        update_account(user_admin, system_admin, {"is_active": False})
