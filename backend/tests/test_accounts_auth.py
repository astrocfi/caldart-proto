"""Registration, password change and the password-reset flow.

CSRF, login, logout and ``/auth/me``, which the portal shell relies on, are
covered by ``test_auth_api.py``.
"""

from __future__ import annotations

import re
from collections.abc import Generator
from typing import Any

import pytest
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.core.mail.message import EmailMultiAlternatives
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from pytest_django import Settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import MEMBER
from apps.members.models import MemberProfile
from tests.conftest import (
    CHANGE_URL,
    GOOD_PASSWORD,
    LOGIN_URL,
    ME_URL,
    REGISTER_URL,
    RESET_CONFIRM_URL,
    RESET_URL,
    register_payload,
)
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def reset_link_from_outbox() -> tuple[str, str]:
    """``(uid, token)`` pulled out of the most recent reset email."""
    body = str(mail.outbox[-1].body)
    match = re.search(r"/portal/reset-password\?uid=([^&\s]+)&token=([^\s&\"<]+)", body)
    assert match, f"no reset link in:\n{body}"
    return match.group(1), match.group(2)


# --------------------------------------------------------------------------
# Registration
# --------------------------------------------------------------------------
def test_register_creates_a_member_and_signs_them_in(api_client: APIClient) -> None:
    """Registering creates the account, signs it in, and returns the payload."""
    response = api_client.post(REGISTER_URL, register_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new.member@example.test"
    assert body["roles"] == [MEMBER]
    assert body["membership"]["status"] == "none"
    assert body["profile_complete"] is False
    assert set(body) == {
        "id",
        "email",
        "first_name",
        "last_name",
        "roles",
        "is_active",
        "membership",
        "profile_complete",
    }

    user = User.objects.get(email="new.member@example.test")
    assert user.check_password(GOOD_PASSWORD)
    assert user.roles == [MEMBER]
    assert MemberProfile.objects.filter(user=user).exists()

    # The session is live straight away -- no second login round trip.
    assert api_client.get(ME_URL).json()["email"] == user.email


def test_register_never_echoes_the_password(api_client: APIClient) -> None:
    """The registration response never carries the password back."""
    response = api_client.post(REGISTER_URL, register_payload())
    assert "password" not in response.json()


def test_register_rejects_a_duplicate_email(api_client: APIClient, member: User) -> None:
    """A registration reusing an existing email is refused, and no row is duplicated."""
    response = api_client.post(REGISTER_URL, register_payload(email=member.email))
    assert response.status_code == 400
    assert "email" in response.json()
    assert User.objects.filter(email__iexact=member.email).count() == 1


def test_register_rejects_a_duplicate_email_in_another_case(
    api_client: APIClient, member: User
) -> None:
    """The duplicate-email check is case-insensitive."""
    response = api_client.post(REGISTER_URL, register_payload(email=member.email.upper()))
    assert response.status_code == 400
    assert "email" in response.json()


@pytest.mark.parametrize(
    "password",
    ["short", "password", "12345678901"],
)
def test_register_rejects_a_weak_password(api_client: APIClient, password: str) -> None:
    """A password failing Django's validators is refused, and no account is created."""
    response = api_client.post(REGISTER_URL, register_payload(password=password))
    assert response.status_code == 400
    assert "password" in response.json()
    assert not User.objects.filter(email="new.member@example.test").exists()


def test_register_rejects_a_password_that_looks_like_the_email(api_client: APIClient) -> None:
    """The similarity-to-username validator applies to the email address too."""
    response = api_client.post(
        REGISTER_URL,
        register_payload(
            email="norabright@example.test",
            password="norabright",  # noqa: S106 - test fixture
        ),
    )
    assert response.status_code == 400
    assert "password" in response.json()


@pytest.mark.parametrize("field", ["email", "password", "first_name", "last_name"])
def test_register_requires_every_field(api_client: APIClient, field: str) -> None:
    """Omitting any of the four registration fields is refused, naming that field."""
    payload = register_payload()
    payload.pop(field)
    response = api_client.post(REGISTER_URL, payload)
    assert response.status_code == 400
    assert field in response.json()


def test_register_rolls_back_when_the_profile_cannot_be_created(
    api_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``register_member`` is atomic: a half-made account must not survive."""

    def boom(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("profile exploded")

    monkeypatch.setattr(MemberProfile.objects, "get_or_create", boom)
    with pytest.raises(RuntimeError):
        api_client.post(REGISTER_URL, register_payload())
    assert not User.objects.filter(email="new.member@example.test").exists()


# --------------------------------------------------------------------------
# Password change
# --------------------------------------------------------------------------
def test_password_change_requires_authentication(api_client: APIClient) -> None:
    """``POST /auth/password/change`` is 401 for a client with no session."""
    response = api_client.post(
        CHANGE_URL, {"current_password": "whatever", "new_password": GOOD_PASSWORD}
    )
    assert response.status_code == 401


def test_password_change_updates_the_password_and_keeps_the_session(
    api_client: APIClient, member: User, password: str
) -> None:
    """A correct password change updates the password and keeps the session live."""
    api_client.force_login(member)
    response = api_client.post(
        CHANGE_URL, {"current_password": password, "new_password": GOOD_PASSWORD}
    )

    assert response.status_code == 204
    member.refresh_from_db()
    assert member.check_password(GOOD_PASSWORD)
    # Still signed in: `update_session_auth_hash` ran.
    assert api_client.get(ME_URL).status_code == 200


def test_password_change_rejects_a_wrong_current_password(
    api_client: APIClient, member: User
) -> None:
    """A wrong current password is refused, naming the ``current_password`` field."""
    api_client.force_login(member)
    response = api_client.post(
        CHANGE_URL, {"current_password": "not-it", "new_password": GOOD_PASSWORD}
    )
    assert response.status_code == 400
    assert "current_password" in response.json()


def test_password_change_rejects_a_weak_new_password(
    api_client: APIClient, member: User, password: str
) -> None:
    """A weak new password is refused, and the stored password is left unchanged."""
    api_client.force_login(member)
    response = api_client.post(CHANGE_URL, {"current_password": password, "new_password": "abc"})
    assert response.status_code == 400
    assert "new_password" in response.json()
    member.refresh_from_db()
    assert member.check_password(password)


# --------------------------------------------------------------------------
# Password reset -- request
# --------------------------------------------------------------------------
def test_password_reset_emails_a_link(api_client: APIClient, member: User) -> None:
    """Requesting a reset emails one message carrying a valid uid/token link."""
    response = api_client.post(RESET_URL, {"email": member.email})

    assert response.status_code == 204
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == [member.email]
    assert "reset" in message.subject.lower()
    uid, token = reset_link_from_outbox()
    assert uid == urlsafe_base64_encode(force_bytes(member.pk))
    assert default_token_generator.check_token(member, token)


def test_password_reset_sends_a_html_alternative(api_client: APIClient, member: User) -> None:
    """The reset email carries an ``text/html`` alternative with the reset link."""
    api_client.post(RESET_URL, {"email": member.email})
    message = mail.outbox[0]
    assert isinstance(message, EmailMultiAlternatives)
    alternatives = message.alternatives
    assert len(alternatives) == 1
    html, mimetype = alternatives[0]
    assert mimetype == "text/html"
    assert isinstance(html, str)
    assert "/portal/reset-password?uid=" in html


def test_password_reset_matches_the_email_case_insensitively(
    api_client: APIClient, member: User
) -> None:
    """A reset request in a different email case still finds the account."""
    response = api_client.post(RESET_URL, {"email": member.email.upper()})
    assert response.status_code == 204
    assert len(mail.outbox) == 1


def test_password_reset_is_204_for_an_unknown_address(api_client: APIClient) -> None:
    """An unknown address gets the same 204 as a known one, and no email is sent."""
    response = api_client.post(RESET_URL, {"email": "nobody@example.test"})
    assert response.status_code == 204
    assert mail.outbox == []


def test_password_reset_sends_nothing_to_a_deactivated_account(
    api_client: APIClient, member: User
) -> None:
    """A reset request for a deactivated account sends no email."""
    member.is_active = False
    member.save(update_fields=["is_active"])
    response = api_client.post(RESET_URL, {"email": member.email})
    assert response.status_code == 204
    assert mail.outbox == []


def test_password_reset_validates_the_address(api_client: APIClient) -> None:
    """A malformed email address is refused with a 400."""
    response = api_client.post(RESET_URL, {"email": "not-an-email"})
    assert response.status_code == 400


def test_password_reset_link_uses_site_url(
    api_client: APIClient, member: User, settings: Settings
) -> None:
    """The reset link is built from the configured ``SITE_URL``."""
    settings.SITE_URL = "https://caldart.example.org/"
    api_client.post(RESET_URL, {"email": member.email})
    assert "https://caldart.example.org/portal/reset-password?uid=" in mail.outbox[0].body


# --------------------------------------------------------------------------
# Password reset -- confirm
# --------------------------------------------------------------------------
def test_password_reset_confirm_sets_the_new_password(api_client: APIClient, member: User) -> None:
    """A confirmation with a valid uid/token sets the password, and it can log in."""
    api_client.post(RESET_URL, {"email": member.email})
    uid, token = reset_link_from_outbox()

    response = api_client.post(
        RESET_CONFIRM_URL, {"uid": uid, "token": token, "new_password": GOOD_PASSWORD}
    )

    assert response.status_code == 204
    member.refresh_from_db()
    assert member.check_password(GOOD_PASSWORD)
    assert (
        api_client.post(LOGIN_URL, {"email": member.email, "password": GOOD_PASSWORD}).status_code
        == 200
    )


def test_password_reset_token_works_only_once(api_client: APIClient, member: User) -> None:
    """A second confirmation with the same token is refused, naming ``token``."""
    api_client.post(RESET_URL, {"email": member.email})
    uid, token = reset_link_from_outbox()
    payload = {"uid": uid, "token": token, "new_password": GOOD_PASSWORD}

    assert api_client.post(RESET_CONFIRM_URL, payload).status_code == 204
    second = api_client.post(RESET_CONFIRM_URL, payload)
    assert second.status_code == 400
    assert "token" in second.json()


def test_password_reset_confirm_rejects_a_tampered_token(
    api_client: APIClient, member: User
) -> None:
    """A token with its last character changed is refused, naming the ``token`` field."""
    api_client.post(RESET_URL, {"email": member.email})
    uid, token = reset_link_from_outbox()
    response = api_client.post(
        RESET_CONFIRM_URL,
        {"uid": uid, "token": f"{token[:-1]}x", "new_password": GOOD_PASSWORD},
    )
    assert response.status_code == 400
    assert "token" in response.json()


@pytest.mark.parametrize("uid", ["not-base64", urlsafe_base64_encode(b"999999"), ""])
def test_password_reset_confirm_rejects_a_bad_uid(
    api_client: APIClient, member: User, uid: str
) -> None:
    """An unparseable, unknown, or empty uid is refused with a 400."""
    api_client.post(RESET_URL, {"email": member.email})
    _, token = reset_link_from_outbox()
    response = api_client.post(
        RESET_CONFIRM_URL, {"uid": uid, "token": token, "new_password": GOOD_PASSWORD}
    )
    assert response.status_code == 400


def test_password_reset_confirm_rejects_a_weak_password(
    api_client: APIClient, member: User, password: str
) -> None:
    """A weak new password is refused, and the stored password is left unchanged."""
    api_client.post(RESET_URL, {"email": member.email})
    uid, token = reset_link_from_outbox()
    response = api_client.post(
        RESET_CONFIRM_URL, {"uid": uid, "token": token, "new_password": "letmein"}
    )
    assert response.status_code == 400
    assert "new_password" in response.json()
    member.refresh_from_db()
    assert member.check_password(password)


def test_password_reset_confirm_rejects_a_deactivated_account(
    api_client: APIClient, member: User
) -> None:
    """A confirmation for an account deactivated after the email was sent is refused."""
    api_client.post(RESET_URL, {"email": member.email})
    uid, token = reset_link_from_outbox()
    member.is_active = False
    member.save(update_fields=["is_active"])

    response = api_client.post(
        RESET_CONFIRM_URL, {"uid": uid, "token": token, "new_password": GOOD_PASSWORD}
    )
    assert response.status_code == 400


# --------------------------------------------------------------------------
# profile_complete
# --------------------------------------------------------------------------
def test_profile_complete_needs_every_field(
    api_client: APIClient, member: User, profile: MemberProfile
) -> None:
    """Clearing a required profile field flips ``profile_complete`` back to false."""
    api_client.force_login(member)
    assert api_client.get(ME_URL).json()["profile_complete"] is True

    profile.address_line1 = ""
    profile.save(update_fields=["address_line1"])
    assert api_client.get(ME_URL).json()["profile_complete"] is False


def test_profile_complete_is_false_without_a_certificate_answer(
    api_client: APIClient, member: User, profile: MemberProfile
) -> None:
    """A blank pilot certificate type makes the profile incomplete."""
    api_client.force_login(member)
    profile.pilot_certificate_type = ""
    profile.save(update_fields=["pilot_certificate_type"])
    assert api_client.get(ME_URL).json()["profile_complete"] is False


def test_profile_complete_is_false_without_a_profile(api_client: APIClient) -> None:
    """A member with no profile row at all is reported as incomplete."""
    user = UserFactory(email="profileless@example.test", roles=[MEMBER])
    api_client.force_login(user)
    assert api_client.get(ME_URL).json()["profile_complete"] is False


# --------------------------------------------------------------------------
# Throttling
# --------------------------------------------------------------------------
@pytest.fixture
def clear_throttle_cache() -> Generator[None]:
    """Clear the throttle cache before and after the test that requests this fixture."""
    cache.clear()
    yield
    cache.clear()


def test_throttles_are_inert_under_test_settings(api_client: APIClient, member: User) -> None:
    """Every other test depends on this: the shared counter never trips."""
    for _ in range(25):
        response = api_client.post(LOGIN_URL, {"email": member.email, "password": "wrong"})
        assert response.status_code == 400


def test_login_is_throttled_when_a_rate_is_configured(
    api_client: APIClient, member: User, clear_throttle_cache: None, settings: Settings
) -> None:
    """Once ``AUTH_THROTTLE_RATES`` names a login rate, exceeding it returns 429."""
    settings.AUTH_THROTTLE_RATES = {"auth_login": "3/min"}
    for _ in range(3):
        response = api_client.post(LOGIN_URL, {"email": member.email, "password": "wrong"})
        assert response.status_code == 400
    assert (
        api_client.post(LOGIN_URL, {"email": member.email, "password": "wrong"}).status_code == 429
    )


def test_registration_is_throttled_when_a_rate_is_configured(
    api_client: APIClient, clear_throttle_cache: None, settings: Settings
) -> None:
    """Once ``AUTH_THROTTLE_RATES`` names a register rate, exceeding it returns 429."""
    settings.AUTH_THROTTLE_RATES = {"auth_register": "2/hour"}
    for index in range(2):
        response = api_client.post(REGISTER_URL, register_payload(email=f"n{index}@example.test"))
        assert response.status_code == 201
    assert (
        api_client.post(REGISTER_URL, register_payload(email="n9@example.test")).status_code == 429
    )


def test_password_reset_is_throttled_when_a_rate_is_configured(
    api_client: APIClient, member: User, clear_throttle_cache: None, settings: Settings
) -> None:
    """Once ``AUTH_THROTTLE_RATES`` names a reset rate, exceeding it returns 429."""
    settings.AUTH_THROTTLE_RATES = {"auth_password_reset": "1/hour"}
    assert api_client.post(RESET_URL, {"email": member.email}).status_code == 204
    assert api_client.post(RESET_URL, {"email": member.email}).status_code == 429
