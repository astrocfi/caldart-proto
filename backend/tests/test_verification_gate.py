"""The email-verification gate: an unverified session reaches only the verify step's API.

``apps.accounts.middleware.EmailVerificationGateMiddleware`` answers 403 with the code
``email_unverified`` to any ``/api/v1/`` request from a signed-in account whose address
is not verified, except the handful of endpoints the verify screen needs.  A verified
session and an anonymous visitor are untouched, and the user guide stays readable.
``docs/developer/api-auth.rst`` (**Unverified sessions**) describes the gate.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.test import Client
from django.utils import timezone
from pytest_django import Settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.services import make_email_verification_token, send_email_verification
from caldart.views import GUIDE_INDEX
from tests.conftest import GOOD_PASSWORD, LOGIN_URL, ME_URL, REGISTER_URL, RESET_URL
from tests.factories import DEFAULT_PASSWORD, UserFactory

pytestmark = pytest.mark.django_db

GATE_BODY = {"detail": "Verify your email address to continue.", "code": "email_unverified"}

PROFILE_URL = "/api/v1/me/profile"
MEMBERSHIP_URL = "/api/v1/me/membership"
BECOME_FRIEND_URL = "/api/v1/me/kind/friend"
SITE_CONFIG_URL = "/api/v1/site/config"
CSRF_URL = "/api/v1/auth/csrf"
LOGOUT_URL = "/api/v1/auth/logout"
VERIFY_URL = "/api/v1/auth/email/verify"
RESEND_URL = "/api/v1/auth/email/resend"
CHANGE_EMAIL_URL = "/api/v1/auth/email/change"
PASSWORD_RESET_URL = RESET_URL
PASSWORD_RESET_CONFIRM_URL = "/api/v1/auth/password/reset/confirm"  # noqa: S105 - a URL, not a password

GUIDE_HTML = "<h1>User guide</h1>"

#: The verification email's advice for an expired link, which names the verify screen.
RESEND_ADVICE = "press Resend verification message on the screen you land on"


@pytest.fixture
def unverified() -> User:
    """A member whose address has never been verified."""
    user: User = UserFactory(email="unverified@example.test", email_verified_at=None)
    return user


@pytest.fixture
def unverified_client(api_client: APIClient, unverified: User) -> APIClient:
    """An API client signed in as the unverified member."""
    api_client.force_login(unverified)
    return api_client


@pytest.mark.parametrize(
    ("method", "url"),
    [("get", PROFILE_URL), ("get", MEMBERSHIP_URL), ("post", BECOME_FRIEND_URL)],
    ids=["profile", "membership", "become-friend"],
)
def test_an_unverified_session_is_refused_a_member_endpoint(
    unverified_client: APIClient, method: str, url: str
) -> None:
    """A member endpoint answers 403 with the gate's detail and code."""
    response = getattr(unverified_client, method)(url)
    assert (response.status_code, response.json()) == (403, GATE_BODY)


@pytest.mark.parametrize("url", [ME_URL, SITE_CONFIG_URL], ids=["me", "site"])
def test_an_unverified_session_reads_the_allowed_endpoints(
    unverified_client: APIClient, url: str
) -> None:
    """``auth/me`` and ``site/config`` answer 200 to an unverified session."""
    assert unverified_client.get(url).status_code == 200


def test_an_unverified_session_may_fetch_a_csrf_token(unverified_client: APIClient) -> None:
    """``GET /auth/csrf`` answers 204, so the verify screen can post at all."""
    assert unverified_client.get(CSRF_URL).status_code == 204


def test_an_unverified_session_may_sign_out(unverified_client: APIClient) -> None:
    """``POST /auth/logout`` is open to an unverified session."""
    assert unverified_client.post(LOGOUT_URL).status_code == 204


def test_an_unverified_session_may_ask_for_another_link(unverified_client: APIClient) -> None:
    """``POST /auth/email/resend`` is open to an unverified session and answers 202."""
    assert unverified_client.post(RESEND_URL).status_code == 202


def test_an_unverified_session_may_follow_its_link(
    unverified_client: APIClient, unverified: User
) -> None:
    """``POST /auth/email/verify`` is open to an unverified session and answers 200."""
    token = make_email_verification_token(unverified)
    assert unverified_client.post(VERIFY_URL, {"token": token}).status_code == 200


def test_an_unverified_session_may_correct_its_address(unverified_client: APIClient) -> None:
    """``POST /auth/email/change`` is open to an unverified session and answers 200."""
    response = unverified_client.post(
        CHANGE_EMAIL_URL,
        {"email": "corrected@example.test", "current_password": DEFAULT_PASSWORD},
    )
    assert response.status_code == 200


def test_an_unverified_session_may_sign_in_again(
    unverified_client: APIClient, user_factory: type[UserFactory]
) -> None:
    """``POST /auth/login`` is open, so the sign-in page can switch to another account."""
    user_factory(email="other@example.test", password=GOOD_PASSWORD)
    response = unverified_client.post(
        LOGIN_URL, {"email": "other@example.test", "password": GOOD_PASSWORD}
    )
    assert response.status_code == 200


def test_an_unverified_session_may_register_another_account(unverified_client: APIClient) -> None:
    """``POST /auth/register`` stays open, as it is to an anonymous visitor."""
    response = unverified_client.post(
        REGISTER_URL,
        {
            "email": "another@example.test",
            "password": GOOD_PASSWORD,
            "first_name": "Ann",
            "last_name": "Other",
        },
    )
    assert response.status_code == 201


def test_an_unverified_session_may_ask_for_a_password_reset(
    unverified_client: APIClient, unverified: User
) -> None:
    """``POST /auth/password/reset`` stays open, as it is to an anonymous visitor."""
    response = unverified_client.post(PASSWORD_RESET_URL, {"email": unverified.email})
    assert response.status_code == 204


def test_an_unverified_session_reaches_the_password_reset_confirmation(
    unverified_client: APIClient,
) -> None:
    """``POST /auth/password/reset/confirm`` is not gated: a bad token is its own 400."""
    response = unverified_client.post(
        PASSWORD_RESET_CONFIRM_URL, {"uid": "x", "token": "y", "new_password": GOOD_PASSWORD}
    )
    assert response.status_code == 400


def test_following_the_link_opens_the_member_endpoints(
    unverified_client: APIClient, unverified: User
) -> None:
    """Once the address is verified, the same session reads a member endpoint."""
    unverified_client.post(VERIFY_URL, {"token": make_email_verification_token(unverified)})
    assert unverified_client.get(MEMBERSHIP_URL).status_code == 200


def test_a_verified_session_is_not_gated(api_client: APIClient) -> None:
    """A verified account reads a member endpoint as before."""
    user = UserFactory(email="verified@example.test", email_verified_at=timezone.now())
    api_client.force_login(user)
    assert api_client.get(MEMBERSHIP_URL).status_code == 200


def test_an_anonymous_request_is_not_gated(api_client: APIClient) -> None:
    """An anonymous visitor gets the API's 401, not the gate's 403."""
    assert api_client.get(MEMBERSHIP_URL).status_code == 401


def test_an_unverified_session_still_reads_the_user_guide(
    client: Client, unverified: User, tmp_path: Path, settings: Settings
) -> None:
    """``/docs/`` is outside the API, so the gate leaves the guide readable."""
    root = tmp_path / "guide"
    root.mkdir()
    (root / GUIDE_INDEX).write_text(GUIDE_HTML)
    settings.USER_GUIDE_ROOT = root
    client.force_login(unverified)
    response = client.get("/docs/")
    response.close()
    assert response.status_code == 200


def test_the_verification_email_sends_an_expired_link_to_the_verify_screen(
    unverified: User,
) -> None:
    """The plain-text body says to sign in and press Resend on the screen that opens."""
    send_email_verification(unverified)
    assert RESEND_ADVICE in " ".join(mail.outbox[0].body.split())


def test_the_verification_email_says_the_same_in_html(unverified: User) -> None:
    """The HTML body gives the same advice as the plain-text one."""
    send_email_verification(unverified)
    message = mail.outbox[0]
    assert isinstance(message, EmailMultiAlternatives)
    html, _mimetype = message.alternatives[0]
    assert RESEND_ADVICE in " ".join(str(html).split())
