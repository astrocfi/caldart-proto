"""``members.services``: registering, creating, editing and deleting a member."""

from __future__ import annotations

import re

import pytest
from django.contrib.auth import get_user_model
from django.core import mail

from apps.accounts.roles import MEMBER
from apps.accounts.services import EMAIL_CHANGE_REFUSED
from apps.members.models import MemberProfile
from apps.members.services import create_member, delete_member, register_member, update_member
from apps.payments.models import PaymentStatus
from caldart.exceptions import DomainPermissionError, DomainValidationError
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

User = get_user_model()

PASSWORD = "Sierra-Foothills-2027"  # noqa: S105 - test fixture

SELF_DELETE_REFUSED = "You cannot delete your own account."
SYSTEM_ADMIN_DELETE_REFUSED = "Only a system administrator can delete a system administrator."


# --------------------------------------------------------------------------
# register_member
# --------------------------------------------------------------------------
def test_register_member_grants_the_member_role() -> None:
    user = register_member(email="joan.ames@example.test", password=PASSWORD)
    assert user.roles == [MEMBER]


def test_register_member_creates_the_empty_profile() -> None:
    """``/me/profile`` is a PATCH, so the row has to exist from the start."""
    user = register_member(email="joan.ames@example.test", password=PASSWORD)
    assert MemberProfile.objects.filter(user=user).count() == 1


def test_register_member_keeps_the_names() -> None:
    user = register_member(
        email="joan.ames@example.test", password=PASSWORD, first_name="Joan", last_name="Ames"
    )
    assert user.display_name == "Joan Ames"


def test_register_member_rolls_back_a_half_made_account(monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise RuntimeError("profile exploded")

    monkeypatch.setattr(MemberProfile.objects, "get_or_create", boom)
    with pytest.raises(RuntimeError, match="profile exploded"):
        register_member(email="joan.ames@example.test", password=PASSWORD)
    assert User.objects.filter(email="joan.ames@example.test").exists() is False


# --------------------------------------------------------------------------
# create_member
# --------------------------------------------------------------------------
def test_create_member_writes_the_profile_fields(account_admin, dart) -> None:
    user = create_member(
        account_admin,
        email="joan.ames@example.test",
        first_name="Joan",
        profile={"phone": "530-555-0142", "dart": dart},
    )
    assert user.profile.phone == "530-555-0142"


def test_create_member_without_a_password_invites_the_account(
    account_admin, site_settings, django_capture_on_commit_callbacks
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        create_member(account_admin, email="joan.ames@example.test")
    assert mail.outbox[0].to == ["joan.ames@example.test"]


def test_the_invitation_is_the_set_your_password_email(
    account_admin, site_settings, django_capture_on_commit_callbacks
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        create_member(account_admin, email="joan.ames@example.test")
    assert mail.outbox[0].subject == f"{site_settings.org_name}: set your password"


def test_create_member_with_a_password_invites_nobody(
    account_admin, django_capture_on_commit_callbacks
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        create_member(account_admin, email="joan.ames@example.test", password=PASSWORD)
    assert len(mail.outbox) == 0


def test_the_invitation_waits_for_the_commit(account_admin, site_settings) -> None:
    """Without the commit the mail is never sent, so a rollback mails nobody."""
    create_member(account_admin, email="joan.ames@example.test")
    assert len(mail.outbox) == 0


def test_create_member_leaves_an_invited_account_without_a_password(account_admin) -> None:
    user = create_member(account_admin, email="joan.ames@example.test")
    assert user.has_usable_password() is False


def test_create_member_creates_a_profile_even_without_one(account_admin) -> None:
    user = create_member(account_admin, email="joan.ames@example.test")
    assert MemberProfile.objects.filter(user=user).count() == 1


def test_create_member_rolls_back_a_half_made_member(account_admin, monkeypatch) -> None:
    def boom(*args, **kwargs):
        raise RuntimeError("profile exploded")

    monkeypatch.setattr(MemberProfile.objects, "create", boom)
    with pytest.raises(RuntimeError, match="profile exploded"):
        create_member(account_admin, email="joan.ames@example.test")
    assert User.objects.filter(email="joan.ames@example.test").exists() is False


# --------------------------------------------------------------------------
# update_member
# --------------------------------------------------------------------------
def test_update_member_writes_the_account_half(account_admin) -> None:
    target = UserFactory(email="target@example.test", roles=[MEMBER])
    update_member(account_admin, target, account={"first_name": "Marta"}, profile=None)
    target.refresh_from_db()
    assert target.first_name == "Marta"


def test_update_member_writes_the_profile_half(account_admin, profile_factory) -> None:
    target = UserFactory(email="target@example.test", roles=[MEMBER])
    profile_factory(user=target)
    update_member(account_admin, target, account={}, profile={"phone": "530-555-0142"})
    target.refresh_from_db()
    assert target.profile.phone == "530-555-0142"


def test_update_member_creates_a_missing_profile(account_admin) -> None:
    target = UserFactory(email="target@example.test", roles=[MEMBER])
    update_member(account_admin, target, account={}, profile={"phone": "530-555-0142"})
    assert MemberProfile.objects.get(user=target).phone == "530-555-0142"


def test_update_member_obeys_the_account_edit_guard(account_admin, system_admin) -> None:
    with pytest.raises(DomainValidationError, match=re.escape(EMAIL_CHANGE_REFUSED)):
        update_member(
            account_admin,
            system_admin,
            account={"email": "taken.over@example.test"},
            profile=None,
        )


def test_a_refused_account_edit_leaves_the_profile_alone(
    account_admin, system_admin, profile_factory
) -> None:
    profile_factory(user=system_admin, phone="530-555-0100")
    with pytest.raises(DomainValidationError):
        update_member(
            account_admin,
            system_admin,
            account={"email": "taken.over@example.test"},
            profile={"phone": "530-555-0142"},
        )
    assert MemberProfile.objects.get(user=system_admin).phone == "530-555-0100"


# --------------------------------------------------------------------------
# delete_member
# --------------------------------------------------------------------------
def test_delete_member_removes_the_account(account_admin) -> None:
    target = UserFactory(email="target@example.test", roles=[MEMBER])
    delete_member(account_admin, target)
    assert User.objects.filter(email="target@example.test").exists() is False


def test_nobody_may_delete_their_own_account(account_admin) -> None:
    with pytest.raises(DomainPermissionError, match=re.escape(SELF_DELETE_REFUSED)):
        delete_member(account_admin, account_admin)


def test_only_a_system_admin_may_delete_a_system_admin(account_admin, system_admin) -> None:
    with pytest.raises(DomainPermissionError, match=re.escape(SYSTEM_ADMIN_DELETE_REFUSED)):
        delete_member(account_admin, system_admin)


def test_a_createsuperuser_account_is_protected_too(account_admin) -> None:
    """The superuser flag alone makes the target a system administrator."""
    target = UserFactory(email="root2@example.test", roles=[], is_superuser=True, is_staff=True)
    with pytest.raises(DomainPermissionError, match=re.escape(SYSTEM_ADMIN_DELETE_REFUSED)):
        delete_member(account_admin, target)


def test_a_system_admin_may_delete_another_system_admin(system_admin) -> None:
    target = UserFactory(email="root2@example.test", roles=[MEMBER], is_superuser=True)
    delete_member(system_admin, target)
    assert User.objects.filter(email="root2@example.test").exists() is False


def test_a_member_with_a_payment_cannot_be_deleted(account_admin, payment_factory) -> None:
    target = UserFactory(email="target@example.test", roles=[MEMBER])
    payment_factory(user=target, status=PaymentStatus.PENDING)
    with pytest.raises(DomainPermissionError, match="which must be kept"):
        delete_member(account_admin, target)


def test_the_payment_refusal_counts_the_records(account_admin, payment_factory) -> None:
    target = UserFactory(email="target@example.test", roles=[MEMBER], first_name="", last_name="")
    payment_factory(user=target)
    payment_factory(user=target)
    with pytest.raises(DomainPermissionError) as refusal:
        delete_member(account_admin, target)
    assert refusal.value.message == (
        "target@example.test has 2 payment records, which must be kept. "
        "Deactivate the account instead."
    )
