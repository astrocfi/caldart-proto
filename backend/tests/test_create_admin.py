"""``manage.py create_admin`` -- create or promote the first administrator."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

import freezegun
import pytest
from django.conf import settings
from django.contrib.auth import SESSION_KEY
from django.contrib.auth.tokens import default_token_generator
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.core.mail import EmailMessage
from django.core.management import call_command
from django.core.management.base import CommandError
from pytest_django.fixtures import DjangoCaptureOnCommitCallbacks
from rest_framework.test import APIClient

from apps.accounts import mfa
from apps.accounts.api.serializers import PasswordChangeSerializer, PasswordResetConfirmSerializer
from apps.accounts.api.views import CHANGED_ELSEWHERE
from apps.accounts.management.commands.create_admin import PROMOTED_NOTICE, PROMOTED_UNMAILED_NOTICE
from apps.accounts.models import AccountKind, User
from apps.accounts.roles import MEMBER, SYSTEM_ADMIN, TREASURER, WEBSITE_ADMIN
from apps.accounts.services import (
    RESET_PATH,
    build_reset_url,
    make_reset_token,
    update_account,
    user_from_uid,
)
from caldart import audit
from tests.conftest import CHANGE_URL, GOOD_PASSWORD, ME_URL, RESET_CONFIRM_URL, RecordedEvents
from tests.factories import DEFAULT_PASSWORD, UserFactory, confirmed_device

if TYPE_CHECKING:
    # rest_framework.test.APIClient.post() is typed to return this class, but it
    # exists only in the stub: rest_framework monkey-patches Django's test response
    # at runtime rather than defining a real subclass.
    from rest_framework.response import _MonkeyPatchedResponse as ApiResponse

pytestmark = pytest.mark.django_db


def _reset_url_query(url: str) -> dict[str, str]:
    """The ``uid`` and ``token`` query parameters a reset link carries."""
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    return {"uid": query["uid"][0], "token": query["token"][0]}


def _mailed_link(message: EmailMessage) -> str:
    """The reset link in the text body of ``message``."""
    match = re.search(r"https?://\S+", str(message.body))
    assert match is not None
    return match.group(0)


def _audit_lines(audit_log: pytest.LogCaptureFixture, action: str) -> list[str]:
    """The audit lines recorded for ``action``."""
    return [
        record.getMessage()
        for record in audit_log.records
        if record.name == audit.LOGGER_NAME
        and record.getMessage().split(" ")[0] == f"action={action}"
    ]


def _stored_session(user: User) -> str:
    """Store a database session signed in to ``user`` and return its key."""
    store = SessionStore()
    store[SESSION_KEY] = str(user.pk)
    store.create()
    assert store.session_key is not None
    return store.session_key


def _sessions_of(user: User) -> int:
    """How many stored sessions are signed in to ``user``."""
    signed_in = str(user.pk)
    return sum(
        1
        for session in Session.objects.all()
        if session.get_decoded().get(SESSION_KEY) == signed_in
    )


# --------------------------------------------------------------------------
# Creating a new account
# --------------------------------------------------------------------------
def test_creates_a_new_account_as_a_system_administrator(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A fresh address becomes an active, staff, superuser account, fully verified."""
    call_command("create_admin", email="new.admin@example.test")
    user = User.objects.get(email="new.admin@example.test")

    assert user.is_active is True
    assert user.is_staff is True
    assert user.is_superuser is True
    assert user.has_usable_password() is False
    assert user.email_verified is True


def test_creates_a_new_account_holding_the_three_admin_roles(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A fresh address holds exactly ``member``, ``system_admin``, ``website_admin``."""
    call_command("create_admin", email="new.admin@example.test")
    user = User.objects.get(email="new.admin@example.test")

    assert set(user.roles) == {MEMBER, SYSTEM_ADMIN, WEBSITE_ADMIN}


def test_creates_a_new_account_with_the_given_names(capsys: pytest.CaptureFixture[str]) -> None:
    """``--first-name`` and ``--last-name`` name a freshly created account."""
    call_command(
        "create_admin",
        email="new.admin@example.test",
        first_name="Priya",
        last_name="Nakamura",
    )
    user = User.objects.get(email="new.admin@example.test")

    assert user.first_name == "Priya"
    assert user.last_name == "Nakamura"


def test_creates_a_new_account_with_blank_names_by_default(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Without ``--first-name``/``--last-name`` a freshly created account has none."""
    call_command("create_admin", email="new.admin@example.test")
    user = User.objects.get(email="new.admin@example.test")

    assert user.first_name == ""
    assert user.last_name == ""


# --------------------------------------------------------------------------
# Promoting an existing account
# --------------------------------------------------------------------------
def test_promotes_an_existing_account_to_a_system_administrator(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An existing address is made staff and a superuser, and given the missing roles."""
    existing = UserFactory(email="already.here@example.test", roles=[MEMBER])

    call_command("create_admin", email="already.here@example.test")
    existing.refresh_from_db()

    assert existing.is_staff is True
    assert existing.is_superuser is True
    assert set(existing.roles) == {MEMBER, SYSTEM_ADMIN, WEBSITE_ADMIN}


def test_promoting_an_existing_account_keeps_the_roles_it_already_held(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A role the account already held, beyond the three admin roles, is kept."""
    existing = UserFactory(email="already.here@example.test", roles=[MEMBER, TREASURER])

    call_command("create_admin", email="already.here@example.test")
    existing.refresh_from_db()

    assert set(existing.roles) == {MEMBER, TREASURER, SYSTEM_ADMIN, WEBSITE_ADMIN}


def test_promoting_an_existing_account_clears_its_password(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Whoever set the existing account's password can no longer sign in with it."""
    existing = UserFactory(email="already.here@example.test", roles=[MEMBER])

    call_command("create_admin", email="already.here@example.test")
    existing.refresh_from_db()

    assert existing.has_usable_password() is False


def test_promoting_an_existing_account_ends_its_sessions(
    capsys: pytest.CaptureFixture[str], api_client: APIClient
) -> None:
    """A session the account held before the promotion is deleted."""
    existing = UserFactory(email="already.here@example.test", roles=[MEMBER])
    api_client.force_login(existing)
    session_key = api_client.cookies[settings.SESSION_COOKIE_NAME].value

    call_command("create_admin", email="already.here@example.test")

    assert Session.objects.filter(session_key=session_key).exists() is False


def test_a_session_held_before_the_promotion_no_longer_authenticates(
    capsys: pytest.CaptureFixture[str], api_client: APIClient
) -> None:
    """A client signed in to the account before the promotion is signed out after it."""
    existing = UserFactory(email="already.here@example.test", roles=[MEMBER])
    api_client.force_login(existing)
    assert api_client.get(ME_URL).status_code == 200

    call_command("create_admin", email="already.here@example.test")

    assert api_client.get(ME_URL).status_code == 401


def test_promoting_an_existing_account_leaves_other_sessions_alone(
    capsys: pytest.CaptureFixture[str], api_client: APIClient
) -> None:
    """Another account's session survives the promotion."""
    UserFactory(email="already.here@example.test", roles=[MEMBER])
    bystander = UserFactory(email="bystander@example.test", roles=[MEMBER])
    api_client.force_login(bystander)
    session_key = api_client.cookies[settings.SESSION_COOKIE_NAME].value

    call_command("create_admin", email="already.here@example.test")

    assert Session.objects.filter(session_key=session_key).exists() is True


def test_promoting_an_existing_account_mails_it_a_valid_set_password_link(
    capsys: pytest.CaptureFixture[str],
    mailoutbox: list[EmailMessage],
) -> None:
    """The address is mailed one message whose link resolves to the account."""
    existing = UserFactory(email="already.here@example.test", roles=[MEMBER])

    call_command("create_admin", email="already.here@example.test")
    existing.refresh_from_db()

    assert [message.to for message in mailoutbox] == [["already.here@example.test"]]
    query = _reset_url_query(_mailed_link(mailoutbox[0]))
    assert default_token_generator.check_token(existing, query["token"]) is True


def test_the_mailed_link_says_the_account_was_taken_back(
    capsys: pytest.CaptureFixture[str],
    mailoutbox: list[EmailMessage],
) -> None:
    """The invitation says the old password was cleared, not that an account was made."""
    UserFactory(email="already.here@example.test", roles=[MEMBER])

    call_command("create_admin", email="already.here@example.test")
    body = " ".join(str(mailoutbox[0].body).split())

    assert "Any password the account had has been cleared" in body
    assert "An account has been created for you" not in body


def test_promoting_an_existing_account_says_so_on_standard_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Standard error says the password was cleared and the link mailed."""
    UserFactory(email="already.here@example.test", roles=[MEMBER])

    call_command("create_admin", email="already.here@example.test")

    expected = PROMOTED_NOTICE.format(email="already.here@example.test")
    assert capsys.readouterr().err == f"{expected}\n"


@pytest.mark.usefixtures("refusing_mail_server")
def test_a_refused_set_password_email_does_not_fail_the_promotion(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A refusing mail server still leaves the account promoted and its password gone."""
    existing = UserFactory(email="already.here@example.test", roles=[MEMBER])

    call_command("create_admin", email="already.here@example.test")
    existing.refresh_from_db()

    assert existing.is_superuser is True
    assert existing.has_usable_password() is False


@pytest.mark.usefixtures("refusing_mail_server")
def test_a_refused_set_password_email_is_said_on_standard_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Standard error says the email was refused rather than claiming it went out."""
    UserFactory(email="already.here@example.test", roles=[MEMBER])

    call_command("create_admin", email="already.here@example.test")

    expected = PROMOTED_UNMAILED_NOTICE.format(email="already.here@example.test")
    assert capsys.readouterr().err == f"{expected}\n"


def test_promoting_an_existing_account_still_prints_only_the_link(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Standard output stays the one reset link the install scripts capture."""
    existing = UserFactory(email="already.here@example.test", roles=[MEMBER])

    with freezegun.freeze_time("2026-09-27 12:00:00"):
        call_command("create_admin", email="already.here@example.test")
        existing.refresh_from_db()
        expected = build_reset_url(existing)

    assert capsys.readouterr().out == f"{expected}\n"


def test_a_reset_link_issued_before_the_promotion_no_longer_works(
    capsys: pytest.CaptureFixture[str], api_client: APIClient
) -> None:
    """A reset token made for the account's earlier password is refused afterwards."""
    existing = UserFactory(email="already.here@example.test", roles=[MEMBER])
    uid, token = make_reset_token(existing)

    call_command("create_admin", email="already.here@example.test")
    response = api_client.post(
        RESET_CONFIRM_URL, {"uid": uid, "token": token, "new_password": GOOD_PASSWORD}
    )

    assert response.status_code == 400
    assert response.json() == {"token": [PasswordResetConfirmSerializer.INVALID_LINK]}


def test_promoting_an_existing_account_is_recorded_in_the_audit_log(
    capsys: pytest.CaptureFixture[str],
    api_client: APIClient,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """``account.password_cleared`` names the command actor and the sessions ended."""
    existing = UserFactory(email="already.here@example.test", roles=[MEMBER])
    api_client.force_login(existing)

    call_command("create_admin", email="already.here@example.test")

    assert _audit_lines(audit_log, "account.password_cleared") == [
        f"action=account.password_cleared actor=command target={existing.pk} "
        "sessions=1 unblocked=false two_factor_removed=false"
    ]


def test_the_address_is_verified_under_the_command_actor(
    capsys: pytest.CaptureFixture[str], audit_log: pytest.LogCaptureFixture
) -> None:
    """``account.email_verified`` names the command, not the account, as actor."""
    existing = UserFactory(
        email="already.here@example.test", roles=[MEMBER], email_verified_at=None
    )

    call_command("create_admin", email="already.here@example.test")

    assert _audit_lines(audit_log, "account.email_verified") == [
        f"action=account.email_verified actor=command target={existing.pk}"
    ]


def test_creating_a_new_account_mails_nothing(
    capsys: pytest.CaptureFixture[str],
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """A freshly created account has no password to take back, so nothing is mailed."""
    with django_capture_on_commit_callbacks(execute=True):
        call_command("create_admin", email="new.admin@example.test")

    assert mailoutbox == []


def test_promoting_an_existing_account_replaces_its_names_when_given(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--first-name``/``--last-name`` replace the names whoever registered it chose."""
    existing = UserFactory(
        email="already.here@example.test", first_name="Ada", last_name="Okoye", roles=[MEMBER]
    )

    call_command(
        "create_admin", email="already.here@example.test", first_name="Priya", last_name="Nakamura"
    )
    existing.refresh_from_db()

    assert existing.first_name == "Priya"
    assert existing.last_name == "Nakamura"


def test_promoting_an_existing_account_keeps_its_names_when_none_are_given(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Without ``--first-name``/``--last-name`` the account's names stay as they were."""
    existing = UserFactory(
        email="already.here@example.test", first_name="Ada", last_name="Okoye", roles=[MEMBER]
    )

    call_command("create_admin", email="already.here@example.test")
    existing.refresh_from_db()

    assert existing.first_name == "Ada"
    assert existing.last_name == "Okoye"


def test_promoting_an_existing_account_marks_its_email_verified(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An unverified address is marked verified, as it is for a newly created account."""
    existing = UserFactory(
        email="already.here@example.test", roles=[MEMBER], email_verified_at=None
    )
    assert existing.email_verified is False

    call_command("create_admin", email="already.here@example.test")
    existing.refresh_from_db()

    assert existing.email_verified is True


def test_promoting_a_blocked_account_lifts_the_block(
    capsys: pytest.CaptureFixture[str], audit_log: pytest.LogCaptureFixture
) -> None:
    """A block on reactivating is lifted, and the audit line says so."""
    existing = UserFactory(
        email="already.here@example.test",
        roles=[MEMBER],
        is_active=False,
        reactivation_blocked=True,
    )

    call_command("create_admin", email="already.here@example.test")
    existing.refresh_from_db()

    assert existing.reactivation_blocked is False
    assert _audit_lines(audit_log, "account.password_cleared") == [
        f"action=account.password_cleared actor=command target={existing.pk} "
        "sessions=0 unblocked=true two_factor_removed=false"
    ]


def test_the_link_reopens_a_promoted_account_that_was_blocked_and_deactivated(
    capsys: pytest.CaptureFixture[str], api_client: APIClient
) -> None:
    """The printed link sets the password and reactivates the account."""
    existing = UserFactory(
        email="already.here@example.test",
        roles=[MEMBER],
        is_active=False,
        reactivation_blocked=True,
    )
    call_command("create_admin", email="already.here@example.test")
    query = _reset_url_query(capsys.readouterr().out.strip())

    response = api_client.post(RESET_CONFIRM_URL, {**query, "new_password": GOOD_PASSWORD})
    existing.refresh_from_db()

    assert response.status_code == 204
    assert existing.is_active is True


# --------------------------------------------------------------------------
# An existing donor
# --------------------------------------------------------------------------
def test_an_existing_donor_address_is_a_command_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A donor holds no role and cannot sign in, so promoting one is refused."""
    donor = UserFactory(email="donor@example.test", kind=AccountKind.DONOR)

    with pytest.raises(CommandError, match=re.escape("donor@example.test")):
        call_command("create_admin", email="donor@example.test")

    donor.refresh_from_db()
    assert donor.is_superuser is False
    assert donor.is_staff is False
    assert set(donor.roles) == set()


def test_a_refused_donor_keeps_its_password(capsys: pytest.CaptureFixture[str]) -> None:
    """Refusing a donor changes nothing, its password hash included."""
    donor = UserFactory(email="donor@example.test", kind=AccountKind.DONOR)
    password_hash = donor.password

    with pytest.raises(CommandError, match=re.escape("donor@example.test")):
        call_command("create_admin", email="donor@example.test")
    donor.refresh_from_db()

    assert donor.password == password_hash


def test_a_refused_donor_keeps_its_sessions(capsys: pytest.CaptureFixture[str]) -> None:
    """Refusing a donor ends no session stored for the account."""
    donor = UserFactory(email="donor@example.test", kind=AccountKind.DONOR)
    session_key = _stored_session(donor)

    with pytest.raises(CommandError, match=re.escape("donor@example.test")):
        call_command("create_admin", email="donor@example.test")

    assert Session.objects.filter(session_key=session_key).exists() is True


# --------------------------------------------------------------------------
# Idempotence
# --------------------------------------------------------------------------
def test_running_it_twice_writes_the_account_roles_audit_line_only_once(
    capsys: pytest.CaptureFixture[str],
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """A second run for the same address grants nothing further, so nothing is audited."""
    call_command("create_admin", email="repeat.admin@example.test")
    call_command("create_admin", email="repeat.admin@example.test")

    roles_lines = [
        record.getMessage()
        for record in audit_log.records
        if record.name == audit.LOGGER_NAME and "action=account.roles" in record.getMessage()
    ]
    assert len(roles_lines) == 1


def test_running_it_twice_leaves_the_roles_unchanged(capsys: pytest.CaptureFixture[str]) -> None:
    """A second run for the same address holds exactly the same three roles."""
    call_command("create_admin", email="repeat.admin@example.test")
    call_command("create_admin", email="repeat.admin@example.test")
    user = User.objects.get(email="repeat.admin@example.test")

    assert set(user.roles) == {MEMBER, SYSTEM_ADMIN, WEBSITE_ADMIN}


# --------------------------------------------------------------------------
# The audit trail and the roles_changed event
# --------------------------------------------------------------------------
def test_the_audit_log_records_the_role_grant_under_the_command_actor(
    capsys: pytest.CaptureFixture[str],
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """``account.roles`` is recorded with ``actor=command``, not a portal account's id."""
    call_command("create_admin", email="new.admin@example.test")
    user = User.objects.get(email="new.admin@example.test")

    roles_lines = [
        record.getMessage()
        for record in audit_log.records
        if record.name == audit.LOGGER_NAME and "action=account.roles" in record.getMessage()
    ]
    assert roles_lines == [
        f"action=account.roles actor=command target={user.pk} "
        f"added=website_admin,system_admin removed=-"
    ]


def test_raises_roles_changed_naming_the_command_actor(
    capsys: pytest.CaptureFixture[str],
    recorded_events: RecordedEvents,
) -> None:
    """The ``roles_changed`` event still fires, naming the command actor."""
    call_command("create_admin", email="new.admin@example.test")

    roles_changed = [payload for slug, payload in recorded_events if slug == "roles_changed"]
    assert len(roles_changed) == 1
    assert roles_changed[0]["actor"] == audit.COMMAND_ACTOR


def test_the_dispatcher_builds_the_role_change_for_the_command_actor(
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """The dispatcher hears the role write and builds its message without an error.

    A message it cannot build is logged, not raised, so only this log line would show
    the command actor's role change going unbuilt.
    """
    with (
        caplog.at_level(logging.ERROR, logger="apps.notifications.dispatch"),
        django_capture_on_commit_callbacks(execute=True),
    ):
        call_command("create_admin", email="new.admin@example.test")

    assert caplog.text == ""


# --------------------------------------------------------------------------
# The printed link
# --------------------------------------------------------------------------
def test_prints_only_the_password_reset_link(capsys: pytest.CaptureFixture[str]) -> None:
    """Standard output is exactly the reset URL for the created account, one line."""
    with freezegun.freeze_time("2026-09-27 12:00:00"):
        call_command("create_admin", email="new.admin@example.test")
        user = User.objects.get(email="new.admin@example.test")
        uid, token = make_reset_token(user)

    out = capsys.readouterr().out
    assert out == f"{settings.SITE_URL.rstrip('/')}{RESET_PATH}?uid={uid}&token={token}\n"


def test_the_printed_link_resolves_to_the_reset_form_for_the_right_account(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The link's path, ``uid``, and ``token`` all resolve to the created account."""
    call_command("create_admin", email="new.admin@example.test")
    user = User.objects.get(email="new.admin@example.test")
    url = capsys.readouterr().out.strip()

    assert urlparse(url).path == RESET_PATH
    query = _reset_url_query(url)
    assert user_from_uid(query["uid"]) == user
    assert default_token_generator.check_token(user, query["token"]) is True


def test_running_it_again_still_prints_a_valid_link(capsys: pytest.CaptureFixture[str]) -> None:
    """A second run for the same address still prints a link that resolves."""
    call_command("create_admin", email="repeat.admin@example.test")
    capsys.readouterr()
    call_command("create_admin", email="repeat.admin@example.test")
    second_url = capsys.readouterr().out.strip()
    user = User.objects.get(email="repeat.admin@example.test")

    query = _reset_url_query(second_url)
    assert user_from_uid(query["uid"]) == user
    assert default_token_generator.check_token(user, query["token"]) is True


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------
def test_an_invalid_email_address_is_a_command_error(capsys: pytest.CaptureFixture[str]) -> None:
    """A malformed address raises ``CommandError`` naming it, and creates no account."""
    with pytest.raises(CommandError, match="not-an-email"):
        call_command("create_admin", email="not-an-email")

    assert User.objects.filter(email="not-an-email").exists() is False


# --------------------------------------------------------------------------
# A request already in flight when the account is taken back
# --------------------------------------------------------------------------
def _take_back_mid_change(monkeypatch: pytest.MonkeyPatch, email: str) -> None:
    """Run ``create_admin`` for ``email`` while a password change is being validated.

    The change has already loaded the signed-in account and checked its current
    password, so it holds the hash ``create_admin`` is about to clear.
    """
    validate = PasswordChangeSerializer.validate_new_password

    def take_back_first(self: PasswordChangeSerializer, value: str) -> str:
        call_command("create_admin", email=email)
        return validate(self, value)

    monkeypatch.setattr(PasswordChangeSerializer, "validate_new_password", take_back_first)


def _change_racing_the_take_back(
    monkeypatch: pytest.MonkeyPatch, api_client: APIClient, existing: User
) -> ApiResponse:
    """Post a password change for ``existing`` that ``create_admin`` overtakes."""
    api_client.force_login(existing)
    _take_back_mid_change(monkeypatch, existing.email)
    return api_client.post(
        CHANGE_URL, {"current_password": DEFAULT_PASSWORD, "new_password": GOOD_PASSWORD}
    )


def test_a_password_change_overtaken_by_the_take_back_is_refused(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, api_client: APIClient
) -> None:
    """The change answers 401 with the reason, rather than 204."""
    existing = UserFactory(email="already.here@example.test", roles=[MEMBER])

    response = _change_racing_the_take_back(monkeypatch, api_client, existing)

    assert response.status_code == 401
    assert response.json() == {"detail": CHANGED_ELSEWHERE}


def test_a_password_change_overtaken_by_the_take_back_writes_no_password(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, api_client: APIClient
) -> None:
    """The password the take-back cleared stays unusable."""
    existing = UserFactory(email="already.here@example.test", roles=[MEMBER])

    _change_racing_the_take_back(monkeypatch, api_client, existing)
    existing.refresh_from_db()

    assert existing.has_usable_password() is False


def test_a_password_change_overtaken_by_the_take_back_leaves_no_session(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, api_client: APIClient
) -> None:
    """No session signed in to the account survives."""
    existing = UserFactory(email="already.here@example.test", roles=[MEMBER])

    _change_racing_the_take_back(monkeypatch, api_client, existing)

    assert _sessions_of(existing) == 0


def test_a_password_change_overtaken_by_the_take_back_leaves_the_client_signed_out(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, api_client: APIClient
) -> None:
    """The client that posted the change is not signed in afterwards."""
    existing = UserFactory(email="already.here@example.test", roles=[MEMBER])

    _change_racing_the_take_back(monkeypatch, api_client, existing)

    assert api_client.get(ME_URL).status_code == 401


def test_a_stale_edit_after_the_take_back_keeps_the_password_cleared(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An account edit made from a copy read before the take-back writes no password."""
    UserFactory(email="already.here@example.test", roles=[MEMBER])
    stale = User.objects.get(email="already.here@example.test")

    call_command("create_admin", email="already.here@example.test")
    update_account(stale, stale, {"first_name": "Mallory"})
    fresh = User.objects.get(pk=stale.pk)

    assert fresh.has_usable_password() is False


def test_a_stale_edit_after_the_take_back_keeps_the_superuser_flag(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An account edit made from a copy read before the promotion keeps it a superuser."""
    UserFactory(email="already.here@example.test", roles=[MEMBER])
    stale = User.objects.get(email="already.here@example.test")

    call_command("create_admin", email="already.here@example.test")
    update_account(stale, stale, {"first_name": "Mallory"})
    fresh = User.objects.get(pk=stale.pk)

    assert fresh.is_superuser is True


def test_a_stale_edit_after_the_take_back_keeps_the_roles(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An account edit made from a copy read before the promotion keeps every role."""
    UserFactory(email="already.here@example.test", roles=[MEMBER])
    stale = User.objects.get(email="already.here@example.test")

    call_command("create_admin", email="already.here@example.test")
    update_account(stale, stale, {"first_name": "Mallory"})
    fresh = User.objects.get(pk=stale.pk)

    assert set(fresh.roles) == {MEMBER, SYSTEM_ADMIN, WEBSITE_ADMIN}


def test_promoting_takes_away_a_device_somebody_else_set_up(
    capsys: pytest.CaptureFixture[str], audit_log: pytest.LogCaptureFixture
) -> None:
    """A squatter's authenticator cannot keep the real administrator out."""
    existing = UserFactory(email="squatted@example.test", roles=[MEMBER])
    confirmed_device(existing)
    mfa.replace_recovery_codes(existing)

    call_command("create_admin", email="squatted@example.test")

    assert mfa.has_two_factor(existing) is False
    assert mfa.recovery_codes_remaining(existing) == 0
    assert _audit_lines(audit_log, "account.password_cleared")[0].endswith(
        "two_factor_removed=true"
    )
