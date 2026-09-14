"""A provider outage is a 400, not a 500, and a captured mismatch is logged.

Every Stripe SDK error and every PayPal transport error is converted to
``ProviderUnavailable``, which the API already turns into a 400.  Checkout then
deletes the pending row it had just created, and confirmation leaves the
payment pending for another attempt.

The test settings raise the root logger to ``ERROR``, so each test that reads
``caplog`` first sets the level on the provider logger it is watching.
"""

from __future__ import annotations

import json
import logging

import httpx
import pytest
import respx
import stripe

from apps.members.models import Membership
from apps.payments.models import Payment, PaymentProvider, PaymentStatus
from apps.payments.providers import paypal
from apps.payments.providers import stripe as stripe_provider
from apps.payments.providers.base import ProviderUnavailable
from apps.payments.services import create_checkout
from tests.test_payments_stripe import fake_stripe_client

pytestmark = pytest.mark.django_db

CHECKOUT = "/api/v1/payments/checkout"
CONFIRM = "/api/v1/payments/stripe/confirm"
CAPTURE = "/api/v1/payments/paypal/capture"
WEBHOOK = "/api/v1/payments/paypal/webhook"

SANDBOX = "https://api-m.sandbox.paypal.com"
TOKEN_URL = f"{SANDBOX}/v1/oauth2/token"
ORDERS_URL = f"{SANDBOX}/v2/checkout/orders"
VERIFY_URL = f"{SANDBOX}/v1/notifications/verify-webhook-signature"

STRIPE_LOGGER = "apps.payments.providers.stripe"
PAYPAL_LOGGER = "apps.payments.providers.paypal"

STRIPE_ERRORS = [
    stripe.APIConnectionError("connection aborted"),
    stripe.RateLimitError("too many requests"),
    stripe.APIError("something went wrong on our end"),
    stripe.AuthenticationError("no valid API key provided"),
]
STRIPE_ERROR_IDS = ["connection", "rate-limit", "api", "authentication"]


@pytest.fixture(autouse=True)
def _providers_configured(settings):
    settings.STRIPE_SECRET_KEY = "sk_test_123"  # noqa: S105 - test fixture
    settings.STRIPE_PUBLISHABLE_KEY = "pk_test_123"
    settings.STRIPE_WEBHOOK_SECRET = "whsec_test"  # noqa: S105 - test fixture
    settings.PAYPAL_CLIENT_ID = "client-id"
    settings.PAYPAL_CLIENT_SECRET = "client-secret"  # noqa: S105 - test fixture
    settings.PAYPAL_ENV = "sandbox"
    settings.PAYPAL_WEBHOOK_ID = ""
    settings.PAYMENTS_MOCK_ENABLED = True
    paypal.reset_token_cache()
    yield
    paypal.reset_token_cache()


class FailingIntents:
    """A ``v1.payment_intents`` service whose every call raises ``error``."""

    def __init__(self, error: stripe.StripeError):
        self.error = error

    def create(self, params, options=None):
        raise self.error

    def retrieve(self, intent_id, params=None, options=None):
        raise self.error


def break_stripe(monkeypatch, error: stripe.StripeError) -> None:
    """Make every Stripe call raise ``error`` instead of reaching the network."""
    client = fake_stripe_client(FailingIntents(error))
    monkeypatch.setattr(stripe_provider, "stripe_client", lambda: client)


def token_route(mock):
    return mock.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "A21AA-token", "expires_in": 32_400})
    )


def capture_payload(payment: Payment, *, value: str | None = None, currency: str = "USD") -> dict:
    return {
        "id": "ORDER-1",
        "status": "COMPLETED",
        "purchase_units": [
            {
                "reference_id": f"payment-{payment.pk}",
                "payments": {
                    "captures": [
                        {
                            "id": "CAPTURE-1",
                            "status": "COMPLETED",
                            "custom_id": str(payment.pk),
                            "amount": {
                                "currency_code": currency,
                                "value": value or f"{payment.amount_cents / 100:.2f}",
                            },
                        }
                    ]
                },
            }
        ],
    }


def pending_paypal_payment(member) -> Payment:
    payment = create_checkout(member, "annual", 0, PaymentProvider.PAYPAL)
    payment.provider_ref = "ORDER-1"
    payment.save(update_fields=["provider_ref"])
    return payment


def messages(caplog) -> list[str]:
    return [record.getMessage() for record in caplog.records]


# --------------------------------------------------------------------------
# Stripe
# --------------------------------------------------------------------------
@pytest.mark.parametrize("error", STRIPE_ERRORS, ids=STRIPE_ERROR_IDS)
def test_a_stripe_failure_at_checkout_is_a_400(api_client, member, annual_plan, monkeypatch, error):
    break_stripe(monkeypatch, error)

    api_client.force_login(member)
    response = api_client.post(
        CHECKOUT, {"plan": "annual", "contribution_cents": 0, "provider": "stripe"}
    )

    assert response.status_code == 400
    assert response.data["detail"] == "Stripe could not be reached. Please try again."


@pytest.mark.parametrize("error", STRIPE_ERRORS, ids=STRIPE_ERROR_IDS)
def test_a_stripe_failure_at_checkout_leaves_no_payment_behind(
    api_client, member, annual_plan, monkeypatch, error
):
    break_stripe(monkeypatch, error)

    api_client.force_login(member)
    api_client.post(CHECKOUT, {"plan": "annual", "contribution_cents": 0, "provider": "stripe"})

    assert Payment.objects.count() == 0


def test_a_stripe_failure_at_checkout_logs_the_exception_class(
    api_client, member, annual_plan, monkeypatch, caplog
):
    caplog.set_level(logging.WARNING, logger=STRIPE_LOGGER)
    break_stripe(monkeypatch, stripe.APIConnectionError("aborted"))

    api_client.force_login(member)
    api_client.post(CHECKOUT, {"plan": "annual", "contribution_cents": 0, "provider": "stripe"})

    assert "APIConnectionError" in " ".join(messages(caplog))


def test_a_stripe_failure_at_confirm_is_a_400(api_client, member, annual_plan, monkeypatch):
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    break_stripe(monkeypatch, stripe.APIConnectionError("aborted"))

    api_client.force_login(member)
    response = api_client.post(CONFIRM, {"payment_id": payment.pk, "payment_intent_id": "pi_out"})

    assert response.status_code == 400
    assert response.data["detail"] == "Stripe could not be reached. Please try again."


def test_a_stripe_failure_at_confirm_leaves_the_payment_pending(
    api_client, member, annual_plan, monkeypatch
):
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    break_stripe(monkeypatch, stripe.RateLimitError("slow down"))

    api_client.force_login(member)
    api_client.post(CONFIRM, {"payment_id": payment.pk, "payment_intent_id": "pi_out"})

    payment.refresh_from_db()
    assert payment.status == PaymentStatus.PENDING


def test_a_stripe_failure_never_logs_an_email_address(
    api_client, member, annual_plan, monkeypatch, caplog
):
    caplog.set_level(logging.WARNING, logger=STRIPE_LOGGER)
    break_stripe(monkeypatch, stripe.APIConnectionError("aborted"))

    api_client.force_login(member)
    api_client.post(CHECKOUT, {"plan": "annual", "contribution_cents": 0, "provider": "stripe"})

    logged = " ".join(messages(caplog))
    assert "Stripe payment_intents.create failed" in logged
    assert "@" not in logged


# --------------------------------------------------------------------------
# PayPal: token and order creation
# --------------------------------------------------------------------------
@respx.mock
def test_a_paypal_token_timeout_at_checkout_is_a_400(api_client, member, annual_plan):
    respx.post(TOKEN_URL).mock(side_effect=httpx.ConnectTimeout("timed out"))

    api_client.force_login(member)
    response = api_client.post(
        CHECKOUT, {"plan": "annual", "contribution_cents": 0, "provider": "paypal"}
    )

    assert response.status_code == 400
    assert response.data["detail"] == "PayPal could not be reached. Please try again."


@respx.mock
def test_a_paypal_token_timeout_at_checkout_leaves_no_payment_behind(
    api_client, member, annual_plan
):
    respx.post(TOKEN_URL).mock(side_effect=httpx.ConnectTimeout("timed out"))

    api_client.force_login(member)
    api_client.post(CHECKOUT, {"plan": "annual", "contribution_cents": 0, "provider": "paypal"})

    assert Payment.objects.count() == 0


@respx.mock
def test_a_token_response_that_is_not_json_is_a_400(api_client, member, annual_plan):
    respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, text="<html>maintenance</html>", headers={})
    )

    api_client.force_login(member)
    response = api_client.post(
        CHECKOUT, {"plan": "annual", "contribution_cents": 0, "provider": "paypal"}
    )

    assert response.status_code == 400
    assert response.data["detail"] == "PayPal could not be reached. Please try again."


@respx.mock
def test_an_order_connection_error_at_checkout_is_a_400(api_client, member, annual_plan):
    token_route(respx)
    respx.post(ORDERS_URL).mock(side_effect=httpx.ConnectError("refused"))

    api_client.force_login(member)
    response = api_client.post(
        CHECKOUT, {"plan": "annual", "contribution_cents": 0, "provider": "paypal"}
    )

    assert response.status_code == 400
    assert response.data["detail"] == "PayPal could not be reached. Please try again."


@respx.mock
def test_an_order_connection_error_at_checkout_leaves_no_payment_behind(
    api_client, member, annual_plan
):
    token_route(respx)
    respx.post(ORDERS_URL).mock(side_effect=httpx.ConnectError("refused"))

    api_client.force_login(member)
    api_client.post(CHECKOUT, {"plan": "annual", "contribution_cents": 0, "provider": "paypal"})

    assert Payment.objects.count() == 0


# --------------------------------------------------------------------------
# PayPal: capture
# --------------------------------------------------------------------------
@respx.mock
def test_a_capture_timeout_is_a_400(api_client, member, annual_plan):
    payment = pending_paypal_payment(member)
    token_route(respx)
    respx.post(f"{ORDERS_URL}/ORDER-1/capture").mock(side_effect=httpx.ConnectTimeout("timed out"))

    api_client.force_login(member)
    response = api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER-1"})

    assert response.status_code == 400
    assert response.data["detail"] == "PayPal could not be reached. Please try again."


@respx.mock
def test_a_capture_timeout_leaves_the_payment_pending(api_client, member, annual_plan):
    payment = pending_paypal_payment(member)
    token_route(respx)
    respx.post(f"{ORDERS_URL}/ORDER-1/capture").mock(side_effect=httpx.ConnectTimeout("timed out"))

    api_client.force_login(member)
    api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER-1"})

    payment.refresh_from_db()
    assert payment.status == PaymentStatus.PENDING


@respx.mock
def test_a_capture_timeout_is_logged_with_the_payment_and_amount(
    api_client, member, annual_plan, caplog
):
    caplog.set_level(logging.ERROR, logger=PAYPAL_LOGGER)
    payment = pending_paypal_payment(member)
    token_route(respx)
    respx.post(f"{ORDERS_URL}/ORDER-1/capture").mock(side_effect=httpx.ConnectTimeout("timed out"))

    api_client.force_login(member)
    api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER-1"})

    logged = " ".join(r.getMessage() for r in caplog.records if r.levelno == logging.ERROR)
    assert f"payment {payment.pk}" in logged
    assert f"{payment.amount_cents} cents" in logged


@respx.mock
def test_a_capture_of_the_wrong_amount_is_logged_with_both_amounts(
    api_client, member, annual_plan, caplog
):
    caplog.set_level(logging.ERROR, logger=PAYPAL_LOGGER)
    payment = pending_paypal_payment(member)
    token_route(respx)
    respx.post(f"{ORDERS_URL}/ORDER-1/capture").mock(
        return_value=httpx.Response(201, json=capture_payload(payment, value="1.00"))
    )

    api_client.force_login(member)
    response = api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER-1"})

    assert response.status_code == 400
    logged = " ".join(r.getMessage() for r in caplog.records if r.levelno == logging.ERROR)
    assert f"payment {payment.pk}" in logged
    assert "100 cents" in logged
    assert f"{payment.amount_cents} cents" in logged


@respx.mock
def test_a_capture_in_another_currency_is_logged(api_client, member, annual_plan, caplog):
    caplog.set_level(logging.ERROR, logger=PAYPAL_LOGGER)
    payment = pending_paypal_payment(member)
    token_route(respx)
    respx.post(f"{ORDERS_URL}/ORDER-1/capture").mock(
        return_value=httpx.Response(201, json=capture_payload(payment, currency="CAD"))
    )

    api_client.force_login(member)
    api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER-1"})

    logged = " ".join(r.getMessage() for r in caplog.records if r.levelno == logging.ERROR)
    assert f"payment {payment.pk}" in logged


@respx.mock
def test_a_capture_mismatch_never_logs_an_email_address(api_client, member, annual_plan, caplog):
    caplog.set_level(logging.ERROR, logger=PAYPAL_LOGGER)
    payment = pending_paypal_payment(member)
    token_route(respx)
    respx.post(f"{ORDERS_URL}/ORDER-1/capture").mock(
        return_value=httpx.Response(201, json=capture_payload(payment, value="1.00"))
    )

    api_client.force_login(member)
    api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER-1"})

    logged = " ".join(messages(caplog))
    assert "PayPal capture mismatch" in logged
    assert "@" not in logged


@respx.mock
def test_a_capture_mismatch_grants_no_membership(api_client, member, annual_plan):
    payment = pending_paypal_payment(member)
    token_route(respx)
    respx.post(f"{ORDERS_URL}/ORDER-1/capture").mock(
        return_value=httpx.Response(201, json=capture_payload(payment, value="1.00"))
    )

    api_client.force_login(member)
    api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER-1"})

    assert Membership.objects.count() == 0


# --------------------------------------------------------------------------
# PayPal: webhook signature verification
# --------------------------------------------------------------------------
def capture_completed_event(payment: Payment) -> dict:
    return {
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource": {
            "id": "CAPTURE-1",
            "custom_id": str(payment.pk),
            "status": "COMPLETED",
            "amount": {"currency_code": "USD", "value": f"{payment.amount_cents / 100:.2f}"},
        },
    }


def post_webhook(client, event: dict):
    return client.post(WEBHOOK, data=json.dumps(event), content_type="application/json")


@respx.mock
def test_a_verification_timeout_leaves_the_webhook_unverified(
    api_client, member, annual_plan, settings
):
    settings.PAYPAL_WEBHOOK_ID = "WH-CONFIG"
    payment = pending_paypal_payment(member)
    token_route(respx)
    respx.post(VERIFY_URL).mock(side_effect=httpx.ConnectTimeout("timed out"))

    response = post_webhook(api_client, capture_completed_event(payment))

    assert response.status_code == 200
    assert json.loads(response.content)["verified"] is False


@respx.mock
def test_a_verification_timeout_leaves_the_payment_pending(
    api_client, member, annual_plan, settings
):
    settings.PAYPAL_WEBHOOK_ID = "WH-CONFIG"
    payment = pending_paypal_payment(member)
    token_route(respx)
    respx.post(VERIFY_URL).mock(side_effect=httpx.ConnectTimeout("timed out"))

    post_webhook(api_client, capture_completed_event(payment))

    payment.refresh_from_db()
    assert payment.status == PaymentStatus.PENDING


# --------------------------------------------------------------------------
# The exception itself
# --------------------------------------------------------------------------
@respx.mock
def test_the_token_call_raises_provider_unavailable():
    respx.post(TOKEN_URL).mock(side_effect=httpx.ConnectTimeout("timed out"))
    with pytest.raises(ProviderUnavailable, match="PayPal could not be reached"):
        paypal.access_token()
