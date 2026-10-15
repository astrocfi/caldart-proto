"""The user record's two-factor status and its **Reset two-factor** action."""

from __future__ import annotations

from io import StringIO

import pytest
from django.core.mail import EmailMessage
from django.core.management import CommandError, call_command
from pytest_django import Settings
from rest_framework.test import APIClient

from apps.accounts import lockout, mfa
from apps.accounts.models import AccountChange, AccountChangeKind, AccountKind, User
from apps.accounts.roles import MEMBER, SYSTEM_ADMIN, TREASURER, USER_ADMIN
from apps.members.services import TOMBSTONE_CHANGE_REFUSED, tombstone_for
from tests.conftest import LOGIN_URL, ME_URL, audit_messages, role_matrix
from tests.factories import DEFAULT_PASSWORD, UserFactory, confirmed_device

pytestmark = pytest.mark.django_db

USERS_URL = "/api/v1/admin/users"


def reset_url(user: User) -> str:
    """The reset action's address for ``user``."""
    return f"{USERS_URL}/{user.pk}/reset-two-factor"


@pytest.fixture
def subject() -> User:
    """A treasurer with a confirmed device and backup codes, who lost their phone."""
    treasurer = UserFactory(email="tess.reasurer@example.test", roles=[MEMBER, TREASURER])
    confirmed_device(treasurer)
    mfa.replace_recovery_codes(treasurer)
    return treasurer


@pytest.fixture
def admin_client(api_client: APIClient, system_admin: User) -> APIClient:
    """``api_client`` signed in as a system administrator."""
    api_client.force_login(system_admin)
    return api_client


@pytest.mark.parametrize(("role", "allowed"), role_matrix(USER_ADMIN, SYSTEM_ADMIN))
def test_who_may_reset(
    api_client: APIClient, all_role_users: dict[str, User], role: str, allowed: bool
) -> None:
    """User administrators and system administrators; everyone else gets 403."""
    target = UserFactory()
    confirmed_device(target)
    api_client.force_login(all_role_users[role])
    response = api_client.post(reset_url(target))
    assert response.status_code == (200 if allowed else 403)


def test_a_reset_takes_the_device_away(admin_client: APIClient, subject: User) -> None:
    """The record answers with two-factor sign-in off."""
    response = admin_client.post(reset_url(subject))
    assert response.json()["two_factor_enabled"] is False
    assert mfa.recovery_codes_remaining(subject) == 0


def test_a_reset_ends_the_persons_sessions(admin_client: APIClient, subject: User) -> None:
    """Every browser signed in to the account is signed out."""
    theirs = APIClient()
    theirs.force_login(subject)
    admin_client.post(reset_url(subject))
    assert theirs.get(ME_URL).status_code == 401


def test_a_reset_is_in_the_history(
    admin_client: APIClient, subject: User, system_admin: User
) -> None:
    """The user record's History card lists it, under the administrator."""
    admin_client.post(reset_url(subject))
    change = AccountChange.objects.get(user=subject)
    assert (change.kind, change.changed_by) == (AccountChangeKind.MFA_RESET, system_admin)


def test_a_reset_is_audited(
    admin_client: APIClient,
    subject: User,
    system_admin: User,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """One audit line names the administrator and the account."""
    admin_client.post(reset_url(subject))
    assert f"action=account.mfa_reset actor={system_admin.pk} target={subject.pk}" in (
        audit_messages(audit_log)
    )


def test_a_reset_mails_the_person(
    admin_client: APIClient,
    subject: User,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: object,
) -> None:
    """The person is told their second factor was reset."""
    with django_capture_on_commit_callbacks(execute=True):  # type: ignore[operator]
        admin_client.post(reset_url(subject))
    assert [(message.to, message.subject) for message in mailoutbox] == [
        ([subject.email], "CalDART: two-factor sign-in was reset")
    ]


def test_after_a_reset_a_required_role_enrolls_again(
    admin_client: APIClient, subject: User
) -> None:
    """The next sign-in insists on a new device."""
    admin_client.post(reset_url(subject))
    response = APIClient().post(
        LOGIN_URL, {"email": subject.email, "password": DEFAULT_PASSWORD}, format="json"
    )
    assert response.json() == {"mfa": "enroll"}


def test_nobody_resets_their_own(admin_client: APIClient, system_admin: User) -> None:
    """Your own second factor is changed on your profile."""
    confirmed_device(system_admin)
    response = admin_client.post(reset_url(system_admin))
    assert response.json() == {"detail": mfa.SELF_RESET_REFUSED}


def test_a_donor_is_refused(admin_client: APIClient) -> None:
    """A donor doesn't have a portal account."""
    donor = UserFactory(kind=AccountKind.DONOR)
    assert admin_client.post(reset_url(donor)).json() == {"detail": mfa.DONOR_RESET_REFUSED}


def test_a_tombstone_is_refused(admin_client: APIClient, member: User) -> None:
    """A record that keeps a deleted member's payments doesn't take a change."""
    tombstone = tombstone_for(member)
    assert admin_client.post(reset_url(tombstone)).json() == {"detail": TOMBSTONE_CHANGE_REFUSED}


def test_a_user_administrator_cannot_reset_a_system_administrator(
    api_client: APIClient, user_admin: User
) -> None:
    """Only a system administrator resets a system administrator's second factor."""
    target = UserFactory(roles=[MEMBER, SYSTEM_ADMIN])
    confirmed_device(target)
    api_client.force_login(user_admin)
    assert api_client.post(reset_url(target)).json() == {"detail": mfa.RESET_REFUSED}


def test_a_user_administrator_resets_a_treasurer(
    api_client: APIClient, user_admin: User, subject: User
) -> None:
    """A role the user administrator does not hold doesn't bar the reset."""
    api_client.force_login(user_admin)
    assert api_client.post(reset_url(subject)).json()["two_factor_enabled"] is False


def test_an_unknown_account_is_404(admin_client: APIClient) -> None:
    """There isn't anyone to reset."""
    assert admin_client.post(f"{USERS_URL}/999999/reset-two-factor").status_code == 404


# -- the status on the record ------------------------------------------------


def test_the_list_says_who_has_two_factor_on(admin_client: APIClient, subject: User) -> None:
    """Each row carries ``two_factor_enabled``."""
    rows = admin_client.get(USERS_URL, {"search": subject.email}).json()["results"]
    assert [row["two_factor_enabled"] for row in rows] == [True]


def test_the_record_says_two_factor_is_off(admin_client: APIClient, member: User) -> None:
    """An account without a device reads off."""
    record = admin_client.get(f"{USERS_URL}/{member.pk}").json()
    assert record["two_factor_enabled"] is False


# -- the command -------------------------------------------------------------


def test_the_command_resets_from_the_server(subject: User) -> None:
    """``manage.py reset_two_factor`` takes the device away, as the record does."""
    call_command("reset_two_factor", email=subject.email.upper(), stdout=StringIO())
    assert mfa.has_two_factor(subject) is False


def test_the_command_is_recorded_under_the_system(subject: User) -> None:
    """The history reads it as a change that no account made."""
    call_command("reset_two_factor", email=subject.email, stdout=StringIO())
    change = AccountChange.objects.get(user=subject)
    assert (change.kind, change.by_command) == (AccountChangeKind.MFA_RESET, True)


def test_the_command_refuses_an_unknown_address() -> None:
    """There isn't anyone to reset."""
    with pytest.raises(CommandError, match=r"No account has the address 'nobody@example\.test'"):
        call_command("reset_two_factor", email="nobody@example.test", stdout=StringIO())


def test_the_command_clears_the_addresss_lockout(subject: User, settings: Settings) -> None:
    """A reset from the server lets the owner straight back to the sign-in."""
    settings.LOGIN_LOCKOUT_ATTEMPTS = 1
    lockout.record_failure(subject.email)
    call_command("reset_two_factor", email=subject.email, stdout=StringIO())
    assert lockout.lockout_wait(subject.email) is None


def test_clear_lockout_lifts_a_lockout(subject: User, settings: Settings) -> None:
    """``manage.py clear_lockout`` forgets only the counted failures."""
    settings.LOGIN_LOCKOUT_ATTEMPTS = 1
    lockout.record_failure(subject.email)
    call_command("clear_lockout", email=subject.email.upper(), stdout=StringIO())
    assert lockout.lockout_wait(subject.email) is None
    assert mfa.has_two_factor(subject) is True


def test_the_record_says_the_caller_may_reset(admin_client: APIClient, subject: User) -> None:
    """``can_reset_two_factor`` follows the reset rule for the caller."""
    record = admin_client.get(f"{USERS_URL}/{subject.pk}").json()
    assert record["can_reset_two_factor"] is True


def test_a_system_administrators_record_says_a_user_administrator_may_not(
    api_client: APIClient, user_admin: User
) -> None:
    """Only a system administrator resets a system administrator's."""
    target = UserFactory(roles=[MEMBER, SYSTEM_ADMIN])
    api_client.force_login(user_admin)
    assert api_client.get(f"{USERS_URL}/{target.pk}").json()["can_reset_two_factor"] is False


def test_your_own_record_says_you_may_not(admin_client: APIClient, system_admin: User) -> None:
    """Nobody resets their own."""
    record = admin_client.get(f"{USERS_URL}/{system_admin.pk}").json()
    assert record["can_reset_two_factor"] is False
