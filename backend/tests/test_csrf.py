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

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.payments.models import PaymentProvider
from apps.payments.services import create_checkout

pytestmark = pytest.mark.django_db

User = get_user_model()

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


def register_payload(**overrides) -> dict:
    payload = {
        "email": "new.member@example.test",
        "password": GOOD_PASSWORD,
        "first_name": "Nora",
        "last_name": "Bright",
    }
    payload.update(overrides)
    return payload


def reset_credentials(user) -> dict:
    """A usable ``uid``/``token`` pair for ``POST /auth/password/reset/confirm``."""
    return {
        "uid": urlsafe_base64_encode(force_bytes(user.pk)),
        "token": default_token_generator.make_token(user),
    }


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
def test_an_anonymous_post_without_a_token_is_refused(csrf_client, member, url, payload) -> None:
    assert csrf_client.post(url, payload).status_code == 403


@pytest.mark.parametrize(("url", "payload"), ANONYMOUS_POSTS)
def test_a_refusal_explains_that_csrf_failed(csrf_client, member, url, payload) -> None:
    detail = csrf_client.post(url, payload).json()["detail"]

    assert detail.startswith("CSRF Failed")


@pytest.mark.parametrize(("url", "payload"), ANONYMOUS_POSTS)
def test_a_multipart_post_without_a_token_is_refused(csrf_client, member, url, payload) -> None:
    """A cross-site HTML form posts multipart, so that shape must be refused too."""
    assert csrf_client.post(url, payload, format="multipart").status_code == 403


# --------------------------------------------------------------------------
# A refused request changes nothing
# --------------------------------------------------------------------------
def test_a_refused_login_sets_no_session_cookie(csrf_client, member, password) -> None:
    csrf_client.post(LOGIN, {"email": member.email, "password": password}, format="multipart")

    assert "sessionid" not in csrf_client.cookies


def test_a_refused_registration_creates_no_user(csrf_client) -> None:
    csrf_client.post(REGISTER, register_payload(email=ATTACKER_EMAIL), format="multipart")

    assert User.objects.filter(email=ATTACKER_EMAIL).exists() is False


def test_a_refused_password_reset_sends_no_email(csrf_client, member) -> None:
    csrf_client.post(RESET, {"email": member.email})

    assert len(mail.outbox) == 0


# --------------------------------------------------------------------------
# With the bootstrapped token, every endpoint behaves normally
# --------------------------------------------------------------------------
def test_the_bootstrap_endpoint_issues_a_token(csrf_client) -> None:
    assert csrf_client.get(CSRF).status_code == 204


def test_registration_succeeds_with_the_bootstrapped_token(csrf_client, csrf_headers, db) -> None:
    headers = csrf_headers(csrf_client)

    response = csrf_client.post(REGISTER, register_payload(), **headers)

    assert response.status_code == 201


def test_login_succeeds_with_the_bootstrapped_token(
    csrf_client, csrf_headers, member, password
) -> None:
    headers = csrf_headers(csrf_client)

    response = csrf_client.post(LOGIN, {"email": member.email, "password": password}, **headers)

    assert response.status_code == 200


def test_logout_succeeds_with_the_bootstrapped_token(csrf_client, csrf_headers, member) -> None:
    csrf_client.force_login(member)
    headers = csrf_headers(csrf_client)

    assert csrf_client.post(LOGOUT, {}, **headers).status_code == 204


def test_a_password_reset_succeeds_with_the_bootstrapped_token(
    csrf_client, csrf_headers, member
) -> None:
    headers = csrf_headers(csrf_client)

    assert csrf_client.post(RESET, {"email": member.email}, **headers).status_code == 204


def test_a_reset_confirm_succeeds_with_the_bootstrapped_token(
    csrf_client, csrf_headers, member
) -> None:
    headers = csrf_headers(csrf_client)
    payload = reset_credentials(member) | {"new_password": GOOD_PASSWORD}

    assert csrf_client.post(RESET_CONFIRM, payload, **headers).status_code == 204


# --------------------------------------------------------------------------
# Signed-in callers, safe methods, and the webhooks
# --------------------------------------------------------------------------
def test_a_signed_in_checkout_without_a_token_is_refused(csrf_client, member) -> None:
    csrf_client.force_login(member)

    assert csrf_client.post(CHECKOUT, {"provider": "mock"}).status_code == 403


def test_a_safe_method_needs_no_token(csrf_client, member) -> None:
    csrf_client.force_login(member)

    assert csrf_client.get(ME).status_code == 200


def test_the_stripe_webhook_needs_no_token(csrf_client, settings) -> None:
    """A bad signature, not a CSRF refusal: the signature is the authentication."""
    settings.STRIPE_WEBHOOK_SECRET = "whsec_test"  # noqa: S105 - test fixture
    body = json.dumps({"id": "evt_unsigned", "object": "event", "type": "ping"})

    response = csrf_client.post(STRIPE_WEBHOOK, data=body, content_type="application/json")

    assert response.status_code == 400


def test_the_paypal_webhook_needs_no_token(csrf_client) -> None:
    body = json.dumps({"event_type": "PAYMENT.CAPTURE.COMPLETED", "resource": {}})

    response = csrf_client.post(PAYPAL_WEBHOOK, data=body, content_type="application/json")

    assert response.status_code == 200


def test_a_signed_stripe_webhook_is_handled_without_a_token(
    csrf_client, settings, member, annual_plan
) -> None:
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
