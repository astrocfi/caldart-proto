"""CSRF on the API, for anonymous callers as well as signed-in ones.

Every request here goes through ``csrf_client``, which enforces the check the
way a browser makes the server enforce it.  ``api_client`` deliberately does
not, so these are the only tests that can see a missing token.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from collections.abc import Callable

import pytest
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from pytest_django.fixtures import Settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.members.models import MembershipPlan
from apps.payments.models import PaymentProvider
from apps.payments.services import create_checkout

pytestmark = pytest.mark.django_db

CSRF = "/api/v1/auth/csrf"
REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
LOGOUT = "/api/v1/auth/logout"
ME = "/api/v1/auth/me"
RESET = "/api/v1/auth/password/reset"
RESET_CONFIRM = "/api/v1/auth/password/reset/confirm"
CHECKOUT = "/api/v1/payments/checkout"
STRIPE_WEBHOOK = "/api/v1/payments/stripe/webhook"
PAYPAL_WEBHOOK = "/api/v1/payments/paypal/webhook"

GOOD_PASSWORD = "Sierra-Foothills-2027"  # noqa: S105 - test fixture
ATTACKER_EMAIL = "attacker@evil.test"


def register_payload(**overrides: str) -> dict[str, str]:
    """A valid ``POST /auth/register`` body, with ``overrides`` replacing fields."""
    payload = {
        "email": "new.member@example.test",
        "password": GOOD_PASSWORD,
        "first_name": "Nora",
        "last_name": "Bright",
    }
    payload.update(overrides)
    return payload


def reset_credentials(user: User) -> dict[str, str]:
    """A usable ``uid``/``token`` pair for ``POST /auth/password/reset/confirm``."""
    return {
        "uid": urlsafe_base64_encode(force_bytes(user.pk)),
        "token": default_token_generator.make_token(user),
    }


def bootstrapped_token(
    csrf_headers: Callable[[APIClient], dict[str, str]], client: APIClient
) -> str:
    """The token ``csrf_headers`` bootstraps for ``client``, ready to send as a header."""
    return csrf_headers(client)["HTTP_X_CSRFTOKEN"]


# --------------------------------------------------------------------------
# Anonymous unsafe methods are refused without a token
# --------------------------------------------------------------------------
ANONYMOUS_POSTS = [
    pytest.param(REGISTER, register_payload(), id="register"),
    pytest.param(LOGIN, {"email": "member@example.test", "password": GOOD_PASSWORD}, id="login"),
    pytest.param(LOGOUT, {}, id="logout"),
    pytest.param(RESET, {"email": "member@example.test"}, id="password-reset"),
    pytest.param(
        RESET_CONFIRM,
        {"uid": "x", "token": "y", "new_password": GOOD_PASSWORD},
        id="password-reset-confirm",
    ),
]


@pytest.mark.parametrize(("url", "payload"), ANONYMOUS_POSTS)
def test_an_anonymous_post_without_a_token_is_refused(
    csrf_client: APIClient, member: User, url: str, payload: dict[str, str]
) -> None:
    """Every unsafe anonymous endpoint refuses a request carrying no CSRF token."""
    assert csrf_client.post(url, payload).status_code == 403


@pytest.mark.parametrize(("url", "payload"), ANONYMOUS_POSTS)
def test_a_refusal_explains_that_csrf_failed(
    csrf_client: APIClient, member: User, url: str, payload: dict[str, str]
) -> None:
    """The 403 body names CSRF as the reason, not a generic permission denial."""
    detail = csrf_client.post(url, payload).json()["detail"]

    assert detail.startswith("CSRF Failed")


@pytest.mark.parametrize(("url", "payload"), ANONYMOUS_POSTS)
def test_a_multipart_post_without_a_token_is_refused(
    csrf_client: APIClient, member: User, url: str, payload: dict[str, str]
) -> None:
    """A cross-site HTML form posts multipart, so that shape must be refused too."""
    assert csrf_client.post(url, payload, format="multipart").status_code == 403


# --------------------------------------------------------------------------
# A refused request changes nothing
# --------------------------------------------------------------------------
def test_a_refused_login_sets_no_session_cookie(
    csrf_client: APIClient, member: User, password: str
) -> None:
    """A login refused for a missing token leaves no session cookie behind."""
    csrf_client.post(LOGIN, {"email": member.email, "password": password}, format="multipart")

    assert "sessionid" not in csrf_client.cookies


def test_a_refused_registration_creates_no_user(csrf_client: APIClient) -> None:
    """A registration refused for a missing token creates no account."""
    csrf_client.post(REGISTER, register_payload(email=ATTACKER_EMAIL), format="multipart")

    assert User.objects.filter(email=ATTACKER_EMAIL).exists() is False


def test_a_refused_password_reset_sends_no_email(csrf_client: APIClient, member: User) -> None:
    """A reset request refused for a missing token sends no email."""
    csrf_client.post(RESET, {"email": member.email})

    assert len(mail.outbox) == 0


# --------------------------------------------------------------------------
# With the bootstrapped token, every endpoint behaves normally
# --------------------------------------------------------------------------
def test_the_bootstrap_endpoint_issues_a_token(csrf_client: APIClient) -> None:
    """``GET /auth/csrf`` succeeds even under CSRF enforcement: it is a safe method."""
    assert csrf_client.get(CSRF).status_code == 204


def test_registration_succeeds_with_the_bootstrapped_token(
    csrf_client: APIClient, csrf_headers: Callable[[APIClient], dict[str, str]], db: None
) -> None:
    """Registration succeeds once the bootstrapped token is sent back as a header."""
    token = bootstrapped_token(csrf_headers, csrf_client)

    response = csrf_client.post(REGISTER, register_payload(), HTTP_X_CSRFTOKEN=token)

    assert response.status_code == 201


def test_login_succeeds_with_the_bootstrapped_token(
    csrf_client: APIClient,
    csrf_headers: Callable[[APIClient], dict[str, str]],
    member: User,
    password: str,
) -> None:
    """Login succeeds once the bootstrapped token is sent back as a header."""
    token = bootstrapped_token(csrf_headers, csrf_client)

    response = csrf_client.post(
        LOGIN, {"email": member.email, "password": password}, HTTP_X_CSRFTOKEN=token
    )

    assert response.status_code == 200


def test_logout_succeeds_with_the_bootstrapped_token(
    csrf_client: APIClient, csrf_headers: Callable[[APIClient], dict[str, str]], member: User
) -> None:
    """Logout succeeds once the bootstrapped token is sent back as a header."""
    csrf_client.force_login(member)
    token = bootstrapped_token(csrf_headers, csrf_client)

    assert csrf_client.post(LOGOUT, {}, HTTP_X_CSRFTOKEN=token).status_code == 204


def test_a_password_reset_succeeds_with_the_bootstrapped_token(
    csrf_client: APIClient, csrf_headers: Callable[[APIClient], dict[str, str]], member: User
) -> None:
    """A reset request succeeds once the bootstrapped token is sent back as a header."""
    token = bootstrapped_token(csrf_headers, csrf_client)

    assert (
        csrf_client.post(RESET, {"email": member.email}, HTTP_X_CSRFTOKEN=token).status_code == 204
    )


def test_a_reset_confirm_succeeds_with_the_bootstrapped_token(
    csrf_client: APIClient, csrf_headers: Callable[[APIClient], dict[str, str]], member: User
) -> None:
    """A reset confirmation succeeds once the bootstrapped token is sent as a header."""
    token = bootstrapped_token(csrf_headers, csrf_client)
    payload = reset_credentials(member) | {"new_password": GOOD_PASSWORD}

    assert csrf_client.post(RESET_CONFIRM, payload, HTTP_X_CSRFTOKEN=token).status_code == 204


# --------------------------------------------------------------------------
# CSRF is decided before the permission check
# --------------------------------------------------------------------------
def test_an_anonymous_protected_post_without_a_token_is_403_not_401(
    csrf_client: APIClient, db: None
) -> None:
    """CSRF runs first, so the 401 the permission matrix promises never happens."""
    assert csrf_client.post(CHECKOUT, {"provider": "mock"}).status_code == 403


def test_an_anonymous_protected_post_with_a_token_is_401(
    csrf_client: APIClient, csrf_headers: Callable[[APIClient], dict[str, str]], db: None
) -> None:
    """With a good token, the request reaches the 401 the permission check gives."""
    token = bootstrapped_token(csrf_headers, csrf_client)

    assert (
        csrf_client.post(CHECKOUT, {"provider": "mock"}, HTTP_X_CSRFTOKEN=token).status_code == 401
    )


# --------------------------------------------------------------------------
# Signed-in callers, safe methods, and the webhooks
# --------------------------------------------------------------------------
def test_a_signed_in_checkout_without_a_token_is_refused(
    csrf_client: APIClient, member: User
) -> None:
    """A signed-in checkout still needs a CSRF token: the session alone is not enough."""
    csrf_client.force_login(member)

    assert csrf_client.post(CHECKOUT, {"provider": "mock"}).status_code == 403


def test_a_safe_method_needs_no_token(csrf_client: APIClient, member: User) -> None:
    """A ``GET`` needs no CSRF token even under enforcement."""
    csrf_client.force_login(member)

    assert csrf_client.get(ME).status_code == 200


def test_the_stripe_webhook_needs_no_token(csrf_client: APIClient, settings: Settings) -> None:
    """A bad signature, not a CSRF refusal: the signature is the authentication."""
    settings.STRIPE_WEBHOOK_SECRET = "whsec_test"  # noqa: S105 - test fixture
    body = json.dumps({"id": "evt_unsigned", "object": "event", "type": "ping"})

    response = csrf_client.post(STRIPE_WEBHOOK, data=body, content_type="application/json")

    assert response.status_code == 400


def test_the_paypal_webhook_needs_no_token(csrf_client: APIClient) -> None:
    """The PayPal webhook accepts a request carrying no CSRF token."""
    body = json.dumps({"event_type": "PAYMENT.CAPTURE.COMPLETED", "resource": {}})

    response = csrf_client.post(PAYPAL_WEBHOOK, data=body, content_type="application/json")

    assert response.status_code == 200


def test_a_signed_stripe_webhook_is_handled_without_a_token(
    csrf_client: APIClient, settings: Settings, member: User, annual_plan: MembershipPlan
) -> None:
    """A correctly signed Stripe event is processed with no CSRF token present."""
    secret = "whsec_test"  # noqa: S105 - test fixture
    settings.STRIPE_WEBHOOK_SECRET = secret
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    body = json.dumps(
        {
            "id": "evt_csrf_1",
            "object": "event",
            "type": "payment_intent.processing",
            "data": {"object": {"id": "pi_csrf_1", "metadata": {"payment_id": str(payment.pk)}}},
        }
    )
    issued_at = int(time.time())
    digest = hmac.new(secret.encode(), f"{issued_at}.{body}".encode(), hashlib.sha256).hexdigest()

    response = csrf_client.post(
        STRIPE_WEBHOOK,
        data=body,
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE=f"t={issued_at},v1={digest}",
    )

    assert response.status_code == 200
