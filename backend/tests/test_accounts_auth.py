"""Registration, password change and the password-reset flow.

CSRF, login, logout and ``/auth/me``, which the portal shell relies on, are
covered by ``test_auth_api.py``.
"""

from __future__ import annotations

import re

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.accounts.roles import MEMBER
from apps.members.models import MemberProfile
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

User = get_user_model()

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
ME = "/api/v1/auth/me"
CHANGE = "/api/v1/auth/password/change"
RESET = "/api/v1/auth/password/reset"
RESET_CONFIRM = "/api/v1/auth/password/reset/confirm"

GOOD_PASSWORD = "Sierra-Foothills-2027"  # noqa: S105 - test fixture


def register_payload(**overrides) -> dict:
    payload = {
        "email": "new.member@example.test",
        "password": GOOD_PASSWORD,
        "first_name": "Nora",
        "last_name": "Bright",
    }
    payload.update(overrides)
    return payload


def reset_link_from_outbox() -> tuple[str, str]:
    """``(uid, token)`` pulled out of the most recent reset email."""
    message = mail.outbox[-1]
    match = re.search(r"/portal/reset-password\?uid=([^&\s]+)&token=([^\s&\"<]+)", message.body)
    assert match, f"no reset link in:\n{message.body}"
    return match.group(1), match.group(2)


# --------------------------------------------------------------------------
# Registration
# --------------------------------------------------------------------------
def test_register_creates_a_member_and_signs_them_in(api_client):
    response = api_client.post(REGISTER, register_payload())

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

    # The session is live straight away — no second login round trip.
    assert api_client.get(ME).json()["email"] == user.email


def test_register_never_echoes_the_password(api_client):
    response = api_client.post(REGISTER, register_payload())
    assert "password" not in response.json()


def test_register_rejects_a_duplicate_email(api_client, member):
    response = api_client.post(REGISTER, register_payload(email=member.email))
    assert response.status_code == 400
    assert "email" in response.json()
    assert User.objects.filter(email__iexact=member.email).count() == 1


def test_register_rejects_a_duplicate_email_in_another_case(api_client, member):
    response = api_client.post(REGISTER, register_payload(email=member.email.upper()))
    assert response.status_code == 400
    assert "email" in response.json()


@pytest.mark.parametrize(
    "password",
    ["short", "password", "12345678901"],
)
def test_register_rejects_a_weak_password(api_client, password):
    response = api_client.post(REGISTER, register_payload(password=password))
    assert response.status_code == 400
    assert "password" in response.json()
    assert not User.objects.filter(email="new.member@example.test").exists()


def test_register_rejects_a_password_that_looks_like_the_email(api_client):
    response = api_client.post(
        REGISTER, register_payload(email="norabright@example.test", password="norabright")
    )
    assert response.status_code == 400
    assert "password" in response.json()


@pytest.mark.parametrize("field", ["email", "password", "first_name", "last_name"])
def test_register_requires_every_field(api_client, field):
    payload = register_payload()
    payload.pop(field)
    response = api_client.post(REGISTER, payload)
    assert response.status_code == 400
    assert field in response.json()


def test_register_rolls_back_when_the_profile_cannot_be_created(api_client, monkeypatch):
    """``register_member`` is atomic: a half-made account must not survive."""

    def boom(*args, **kwargs):
        raise RuntimeError("profile exploded")

    monkeypatch.setattr(MemberProfile.objects, "get_or_create", boom)
    with pytest.raises(RuntimeError):
        api_client.post(REGISTER, register_payload())
    assert not User.objects.filter(email="new.member@example.test").exists()


# --------------------------------------------------------------------------
# Password change
# --------------------------------------------------------------------------
def test_password_change_requires_authentication(api_client):
    response = api_client.post(
        CHANGE, {"current_password": "whatever", "new_password": GOOD_PASSWORD}
    )
    assert response.status_code == 401


def test_password_change_updates_the_password_and_keeps_the_session(api_client, member, password):
    api_client.force_login(member)
    response = api_client.post(
        CHANGE, {"current_password": password, "new_password": GOOD_PASSWORD}
    )

    assert response.status_code == 204
    member.refresh_from_db()
    assert member.check_password(GOOD_PASSWORD)
    # Still signed in: `update_session_auth_hash` ran.
    assert api_client.get(ME).status_code == 200


def test_password_change_rejects_a_wrong_current_password(api_client, member):
    api_client.force_login(member)
    response = api_client.post(
        CHANGE, {"current_password": "not-it", "new_password": GOOD_PASSWORD}
    )
    assert response.status_code == 400
    assert "current_password" in response.json()


def test_password_change_rejects_a_weak_new_password(api_client, member, password):
    api_client.force_login(member)
    response = api_client.post(CHANGE, {"current_password": password, "new_password": "abc"})
    assert response.status_code == 400
    assert "new_password" in response.json()
    member.refresh_from_db()
    assert member.check_password(password)


# --------------------------------------------------------------------------
# Password reset — request
# --------------------------------------------------------------------------
def test_password_reset_emails_a_link(api_client, member):
    response = api_client.post(RESET, {"email": member.email})

    assert response.status_code == 204
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == [member.email]
    assert "reset" in message.subject.lower()
    uid, token = reset_link_from_outbox()
    assert uid == urlsafe_base64_encode(force_bytes(member.pk))
    assert default_token_generator.check_token(member, token)


def test_password_reset_sends_a_html_alternative(api_client, member):
    api_client.post(RESET, {"email": member.email})
    alternatives = mail.outbox[0].alternatives
    assert len(alternatives) == 1
    html, mimetype = alternatives[0]
    assert mimetype == "text/html"
    assert "/portal/reset-password?uid=" in html


def test_password_reset_matches_the_email_case_insensitively(api_client, member):
    response = api_client.post(RESET, {"email": member.email.upper()})
    assert response.status_code == 204
    assert len(mail.outbox) == 1


def test_password_reset_is_204_for_an_unknown_address(api_client):
    response = api_client.post(RESET, {"email": "nobody@example.test"})
    assert response.status_code == 204
    assert mail.outbox == []


def test_password_reset_sends_nothing_to_a_deactivated_account(api_client, member):
    member.is_active = False
    member.save(update_fields=["is_active"])
    response = api_client.post(RESET, {"email": member.email})
    assert response.status_code == 204
    assert mail.outbox == []


def test_password_reset_validates_the_address(api_client):
    response = api_client.post(RESET, {"email": "not-an-email"})
    assert response.status_code == 400


@override_settings(SITE_URL="https://caldart.example.org/")
def test_password_reset_link_uses_site_url(api_client, member):
    api_client.post(RESET, {"email": member.email})
    assert "https://caldart.example.org/portal/reset-password?uid=" in mail.outbox[0].body


# --------------------------------------------------------------------------
# Password reset — confirm
# --------------------------------------------------------------------------
def test_password_reset_confirm_sets_the_new_password(api_client, member):
    api_client.post(RESET, {"email": member.email})
    uid, token = reset_link_from_outbox()

    response = api_client.post(
        RESET_CONFIRM, {"uid": uid, "token": token, "new_password": GOOD_PASSWORD}
    )

    assert response.status_code == 204
    member.refresh_from_db()
    assert member.check_password(GOOD_PASSWORD)
    assert (
        api_client.post(LOGIN, {"email": member.email, "password": GOOD_PASSWORD}).status_code
        == 200
    )


def test_password_reset_token_works_only_once(api_client, member):
    api_client.post(RESET, {"email": member.email})
    uid, token = reset_link_from_outbox()
    payload = {"uid": uid, "token": token, "new_password": GOOD_PASSWORD}

    assert api_client.post(RESET_CONFIRM, payload).status_code == 204
    second = api_client.post(RESET_CONFIRM, payload)
    assert second.status_code == 400
    assert "token" in second.json()


def test_password_reset_confirm_rejects_a_tampered_token(api_client, member):
    api_client.post(RESET, {"email": member.email})
    uid, token = reset_link_from_outbox()
    response = api_client.post(
        RESET_CONFIRM,
        {"uid": uid, "token": f"{token[:-1]}x", "new_password": GOOD_PASSWORD},
    )
    assert response.status_code == 400
    assert "token" in response.json()


@pytest.mark.parametrize("uid", ["not-base64", urlsafe_base64_encode(b"999999"), ""])
def test_password_reset_confirm_rejects_a_bad_uid(api_client, member, uid):
    api_client.post(RESET, {"email": member.email})
    _, token = reset_link_from_outbox()
    response = api_client.post(
        RESET_CONFIRM, {"uid": uid, "token": token, "new_password": GOOD_PASSWORD}
    )
    assert response.status_code == 400


def test_password_reset_confirm_rejects_a_weak_password(api_client, member, password):
    api_client.post(RESET, {"email": member.email})
    uid, token = reset_link_from_outbox()
    response = api_client.post(
        RESET_CONFIRM, {"uid": uid, "token": token, "new_password": "letmein"}
    )
    assert response.status_code == 400
    assert "new_password" in response.json()
    member.refresh_from_db()
    assert member.check_password(password)


def test_password_reset_confirm_rejects_a_deactivated_account(api_client, member):
    api_client.post(RESET, {"email": member.email})
    uid, token = reset_link_from_outbox()
    member.is_active = False
    member.save(update_fields=["is_active"])

    response = api_client.post(
        RESET_CONFIRM, {"uid": uid, "token": token, "new_password": GOOD_PASSWORD}
    )
    assert response.status_code == 400


# --------------------------------------------------------------------------
# profile_complete
# --------------------------------------------------------------------------
def test_profile_complete_needs_every_field(api_client, member, profile):
    api_client.force_login(member)
    assert api_client.get(ME).json()["profile_complete"] is True

    profile.address_line1 = ""
    profile.save(update_fields=["address_line1"])
    assert api_client.get(ME).json()["profile_complete"] is False


def test_profile_complete_is_false_without_a_certificate_answer(api_client, member, profile):
    api_client.force_login(member)
    profile.pilot_certificate_type = ""
    profile.save(update_fields=["pilot_certificate_type"])
    assert api_client.get(ME).json()["profile_complete"] is False


def test_profile_complete_is_false_without_a_profile(api_client):
    user = UserFactory(email="profileless@example.test", roles=[MEMBER])
    api_client.force_login(user)
    assert api_client.get(ME).json()["profile_complete"] is False


# --------------------------------------------------------------------------
# Throttling
# --------------------------------------------------------------------------
@pytest.fixture
def clear_throttle_cache():
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


def test_throttles_are_inert_under_test_settings(api_client, member):
    """Every other test depends on this: the shared counter never trips."""
    for _ in range(25):
        response = api_client.post(LOGIN, {"email": member.email, "password": "wrong"})
        assert response.status_code == 400


@override_settings(AUTH_THROTTLE_RATES={"auth_login": "3/min"})
def test_login_is_throttled_when_a_rate_is_configured(api_client, member, clear_throttle_cache):
    for _ in range(3):
        response = api_client.post(LOGIN, {"email": member.email, "password": "wrong"})
        assert response.status_code == 400
    assert api_client.post(LOGIN, {"email": member.email, "password": "wrong"}).status_code == 429


@override_settings(AUTH_THROTTLE_RATES={"auth_register": "2/hour"})
def test_registration_is_throttled_when_a_rate_is_configured(api_client, clear_throttle_cache):
    for index in range(2):
        response = api_client.post(REGISTER, register_payload(email=f"n{index}@example.test"))
        assert response.status_code == 201
    assert api_client.post(REGISTER, register_payload(email="n9@example.test")).status_code == 429


@override_settings(AUTH_THROTTLE_RATES={"auth_password_reset": "1/hour"})
def test_password_reset_is_throttled_when_a_rate_is_configured(
    api_client, member, clear_throttle_cache
):
    assert api_client.post(RESET, {"email": member.email}).status_code == 204
    assert api_client.post(RESET, {"email": member.email}).status_code == 429
