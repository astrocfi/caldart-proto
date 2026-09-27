"""``manage.py create_admin`` -- create or promote the first administrator."""

from __future__ import annotations

import logging
import re
from urllib.parse import parse_qs, urlparse

import freezegun
import pytest
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMessage
from django.core.management import call_command
from django.core.management.base import CommandError
from pytest_django.fixtures import DjangoCaptureOnCommitCallbacks

from apps.accounts.models import AccountKind, User
from apps.accounts.roles import MEMBER, SYSTEM_ADMIN, TREASURER, WEBSITE_ADMIN
from apps.accounts.services import RESET_PATH, make_reset_token, user_from_uid
from caldart import audit
from tests.conftest import RecordedEvents
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def _reset_url_query(url: str) -> dict[str, str]:
    """The ``uid`` and ``token`` query parameters a reset link carries."""
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    return {"uid": query["uid"][0], "token": query["token"][0]}


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


def test_promoting_an_existing_account_leaves_its_password_untouched(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Promoting an account never rewrites its password hash."""
    existing = UserFactory(email="already.here@example.test", roles=[MEMBER])
    password_hash = existing.password

    call_command("create_admin", email="already.here@example.test")
    existing.refresh_from_db()

    assert existing.password == password_hash


def test_promoting_an_existing_account_leaves_its_names_untouched(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``--first-name``/``--last-name`` given for an existing account are ignored."""
    existing = UserFactory(
        email="already.here@example.test", first_name="Ada", last_name="Okoye", roles=[MEMBER]
    )

    call_command(
        "create_admin", email="already.here@example.test", first_name="Someone", last_name="Else"
    )
    existing.refresh_from_db()

    assert existing.first_name == "Ada"
    assert existing.last_name == "Okoye"


def test_promoting_an_existing_account_does_not_mark_its_email_verified(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Only account creation marks the email verified; promoting one does not."""
    existing = UserFactory(email="already.here@example.test", roles=[MEMBER])
    assert existing.email_verified is False

    call_command("create_admin", email="already.here@example.test")
    existing.refresh_from_db()

    assert existing.email_verified is False


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


def test_runs_the_role_write_with_notifications_suspended(
    capsys: pytest.CaptureFixture[str],
    caplog: pytest.LogCaptureFixture,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """The role write suspends notifications, so the dispatcher never hears it.

    Without ``suspended()``, the subscribed dispatcher would try to build the
    ``roles_changed`` message for the command actor, fail because it names no real
    ``User``, and log an error naming the event -- caught, not raised, so only this
    log line would betray a removed ``suspended()`` block.
    """
    with (
        caplog.at_level(logging.ERROR, logger="apps.notifications.dispatch"),
        django_capture_on_commit_callbacks(execute=True),
    ):
        call_command("create_admin", email="new.admin@example.test")

    assert caplog.text == ""
    assert mailoutbox == []


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
