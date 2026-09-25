"""``MemberProfile.profile_updated_at``: what stamps it, and what never does.

Every write of profile information -- the member's own edit, an
administrator's edit to the profile or to the account's name or email, an
aircraft attached or detached, and the profile's creation -- goes through
``apps.members.services.touch_profile`` and is proved here.  So is every write
the field is deliberately silent on: a payment, a membership grant or renewal,
a reminder, and a role change.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.core.mail import EmailMessage
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import DART_LEADER, MEMBER
from apps.accounts.services import update_account
from apps.aircraft.models import Aircraft
from apps.members.admin import MemberProfileAdmin
from apps.members.models import MemberProfile, MembershipPlan, MembershipSource
from apps.members.services import (
    activate_term,
    create_member,
    register_member,
    touch_profile,
    update_member,
)
from apps.reminders.models import REMINDER_OFFSETS, ReminderKind
from apps.reminders.services import send_renewal_reminders
from tests.factories import MemberProfileFactory, MembershipFactory, UserFactory

pytestmark = pytest.mark.django_db

ME_PROFILE_URL = "/api/v1/me/profile"
ATTACH_URL = "/api/v1/me/profile/aircraft"

PASSWORD = "Willow-Creek-4471"  # noqa: S105 - test fixture


def detail_url(user: User) -> str:
    """``/admin/members/{id}``, which reads and edits ``user``'s record."""
    return f"/api/v1/admin/members/{user.pk}"


def detach_url(aircraft_id: int) -> str:
    """``/me/profile/aircraft/{id}``, which detaches that aircraft."""
    return f"{ATTACH_URL}/{aircraft_id}"


# --------------------------------------------------------------------------
# Writes that stamp it
# --------------------------------------------------------------------------
def test_registering_stamps_the_new_profile(today: date) -> None:
    """A freshly registered member's profile is stamped the moment it is created."""
    user = register_member(email="joan.ames@example.test", password=PASSWORD)
    assert MemberProfile.objects.get(user=user).profile_updated_at == timezone.now()


def test_creating_a_member_stamps_the_new_profile(account_admin: User, today: date) -> None:
    """A member an administrator creates has its profile stamped right away."""
    user = create_member(account_admin, email="joan.ames@example.test")
    assert MemberProfile.objects.get(user=user).profile_updated_at == timezone.now()


def test_patching_my_profile_stamps_it(
    api_client: APIClient, member: User, profile: MemberProfile, today: date
) -> None:
    """A member's own ``PATCH /me/profile`` stamps their profile as now."""
    api_client.force_login(member)
    assert profile.profile_updated_at is None

    response = api_client.patch(ME_PROFILE_URL, {"phone": "415-555-0199"}, format="json")

    assert response.status_code == 200
    profile.refresh_from_db()
    assert profile.profile_updated_at == timezone.now()


def test_admin_patch_carrying_profile_stamps_it(
    account_admin_client: APIClient, today: date
) -> None:
    """``PATCH /admin/members/{id}`` with a ``profile`` body stamps the profile."""
    target = UserFactory(email="target@example.test", roles=[MEMBER])
    profile = MemberProfileFactory(user=target)
    assert profile.profile_updated_at is None

    response = account_admin_client.patch(
        detail_url(target), {"profile": {"phone": "415-555-0199"}}, format="json"
    )

    assert response.status_code == 200
    target.profile.refresh_from_db()
    assert target.profile.profile_updated_at == timezone.now()


@pytest.mark.parametrize("field", ["email", "first_name", "last_name"])
def test_admin_patch_carrying_a_name_or_email_stamps_it(
    account_admin_client: APIClient, field: str, today: date
) -> None:
    """A body carrying only the account's name or email still stamps the profile."""
    target = UserFactory(email="target@example.test", roles=[MEMBER])
    profile = MemberProfileFactory(user=target)
    assert profile.profile_updated_at is None
    value = "renamed@example.test" if field == "email" else "Marta"

    response = account_admin_client.patch(detail_url(target), {field: value}, format="json")

    assert response.status_code == 200
    target.profile.refresh_from_db()
    assert target.profile.profile_updated_at == timezone.now()


def test_attaching_an_aircraft_stamps_the_profile(
    api_client: APIClient, member: User, profile: MemberProfile, aircraft: Aircraft, today: date
) -> None:
    """Attaching an aircraft to the caller's profile stamps it."""
    api_client.force_login(member)
    assert profile.profile_updated_at is None

    response = api_client.post(ATTACH_URL, {"aircraft_id": aircraft.id}, format="json")

    assert response.status_code == 200
    profile.refresh_from_db()
    assert profile.profile_updated_at == timezone.now()


def test_detaching_an_aircraft_stamps_the_profile(
    api_client: APIClient, member: User, profile: MemberProfile, aircraft: Aircraft, today: date
) -> None:
    """Detaching an aircraft from the caller's profile stamps it too."""
    profile.aircraft.add(aircraft)
    api_client.force_login(member)
    assert profile.profile_updated_at is None

    response = api_client.delete(detach_url(aircraft.id))

    assert response.status_code == 204
    profile.refresh_from_db()
    assert profile.profile_updated_at == timezone.now()


def test_touching_a_profile_also_moves_its_generic_updated_at(profile: MemberProfile) -> None:
    """``touch_profile`` lists ``updated_at`` in ``update_fields`` alongside the stamp.

    Django skips an ``auto_now`` field left out of ``update_fields``, so without it
    the row's own audit column would disagree with ``profile_updated_at``.
    """
    before = profile.updated_at

    with freeze_time(timezone.now() + timedelta(days=1)):
        touch_profile(profile)

    profile.refresh_from_db()
    assert profile.updated_at > before


# --------------------------------------------------------------------------
# Writes that leave it alone
# --------------------------------------------------------------------------
@pytest.mark.parametrize("source", [MembershipSource.PAYMENT, MembershipSource.MANUAL])
def test_activating_a_term_leaves_the_stamp_alone(
    member: User, annual_plan: MembershipPlan, source: str
) -> None:
    """A payment or a manually granted term never stamps the profile."""
    MemberProfileFactory(user=member)

    activate_term(member, annual_plan, source=source)

    member.profile.refresh_from_db()
    assert member.profile.profile_updated_at is None


def test_a_renewal_leaves_the_stamp_alone(member: User, annual_plan: MembershipPlan) -> None:
    """Renewing an already-covered member never stamps the profile either."""
    MemberProfileFactory(user=member)

    activate_term(member, annual_plan)
    activate_term(member, annual_plan)

    member.profile.refresh_from_db()
    assert member.profile.profile_updated_at is None


def test_a_reminder_leaves_the_stamp_alone(
    member: User,
    profile: MemberProfile,
    annual_plan: MembershipPlan,
    mailoutbox: list[EmailMessage],
    today: date,
) -> None:
    """Sending a renewal reminder about a member never stamps their profile."""
    touch_profile(profile)
    stamp = profile.profile_updated_at
    ends_on = today - timedelta(days=REMINDER_OFFSETS[ReminderKind.T30])
    MembershipFactory(
        user=member, plan=annual_plan, starts_on=ends_on - timedelta(days=364), ends_on=ends_on
    )

    run = send_renewal_reminders(today=today)

    assert run.sent == 1
    assert len(mailoutbox) == 1
    profile.refresh_from_db()
    assert profile.profile_updated_at == stamp


def test_a_role_change_leaves_the_stamp_alone(account_admin: User, member: User) -> None:
    """Editing roles through the account service never stamps the profile."""
    profile = MemberProfileFactory(user=member)
    touch_profile(profile)
    stamp = profile.profile_updated_at

    update_account(account_admin, member, {"roles": [MEMBER, DART_LEADER]})

    profile.refresh_from_db()
    assert profile.profile_updated_at == stamp


def test_admin_patch_with_only_is_active_leaves_the_stamp_alone(
    account_admin_client: APIClient,
) -> None:
    """A body carrying only ``is_active`` never stamps the profile."""
    target = UserFactory(email="target@example.test", roles=[MEMBER])
    profile = MemberProfileFactory(user=target)
    touch_profile(profile)
    stamp = profile.profile_updated_at

    response = account_admin_client.patch(detail_url(target), {"is_active": False}, format="json")

    assert response.status_code == 200
    profile.refresh_from_db()
    assert profile.profile_updated_at == stamp


def test_admin_patch_with_only_a_name_leaves_a_profile_less_target_untouched(
    account_admin_client: APIClient,
) -> None:
    """A name-only edit for a target with no profile creates none and stamps nothing."""
    target = UserFactory(email="target@example.test", roles=[MEMBER])
    assert MemberProfile.objects.filter(user=target).exists() is False

    response = account_admin_client.patch(
        detail_url(target), {"first_name": "Marta"}, format="json"
    )

    assert response.status_code == 200
    assert MemberProfile.objects.filter(user=target).exists() is False


def test_update_member_with_no_account_or_profile_change_leaves_the_stamp_alone(
    account_admin: User, member: User
) -> None:
    """Calling the service with neither half changed touches nothing."""
    profile = MemberProfileFactory(user=member)
    touch_profile(profile)
    stamp = profile.profile_updated_at

    update_member(account_admin, member, account={}, profile=None)

    profile.refresh_from_db()
    assert profile.profile_updated_at == stamp


# --------------------------------------------------------------------------
# The Django admin
# --------------------------------------------------------------------------
def test_the_admin_cannot_edit_the_stamp() -> None:
    """``profile_updated_at`` is read-only in the Django admin, like the other stamps.

    The field is written only by ``touch_profile``; a staff user typing a value
    into it in the admin would make the record disagree with its own history.
    """
    assert "profile_updated_at" in MemberProfileAdmin.readonly_fields
