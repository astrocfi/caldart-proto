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
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
import respx
import stripe
from pytest_django.fixtures import Settings
from rest_framework.response import Response
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.members.models import Membership, MembershipPlan
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
    stripe.APIConnectionError("connection aborted"),  # type: ignore[no-untyped-call]  # stripe stubs leave APIConnectionError.__init__ untyped
    stripe.RateLimitError("too many requests"),
    stripe.APIError("something went wrong on our end"),
    stripe.AuthenticationError("no valid API key provided"),
]
STRIPE_ERROR_IDS = ["connection", "rate-limit", "api", "authentication"]


@pytest.fixture(autouse=True)
def _providers_configured(settings: Settings) -> Iterator[None]:
    """Configure fake Stripe and PayPal keys and reset PayPal's token cache."""
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

    def __init__(self, error: stripe.StripeError) -> None:
        """Remember the error every call raises."""
        self.error = error

    def create(
        self, params: dict[str, Any], options: dict[str, Any] | None = None
    ) -> stripe.PaymentIntent:
        """Raise the configured error instead of creating an intent."""
        raise self.error

    def retrieve(
        self,
        intent_id: str,
        params: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
    ) -> stripe.PaymentIntent:
        """Raise the configured error instead of retrieving an intent."""
        raise self.error


def break_stripe(monkeypatch: pytest.MonkeyPatch, error: stripe.StripeError) -> None:
    """Make every Stripe call raise ``error`` instead of reaching the network."""
    client = fake_stripe_client(FailingIntents(error))
    monkeypatch.setattr(stripe_provider, "stripe_client", lambda: client)


def token_route(mock: respx.MockRouter) -> respx.Route:
    """Mock the PayPal OAuth token endpoint to return a fake, long-lived token."""
    return mock.post(TOKEN_URL).mock(
        return_value=httpx.Response(200, json={"access_token": "A21AA-token", "expires_in": 32_400})
    )


def capture_payload(
    payment: Payment, *, value: str | None = None, currency: str = "USD"
) -> dict[str, Any]:
    """A PayPal capture webhook/API payload naming ``payment`` in its custom id."""
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


def pending_paypal_payment(member: User) -> Payment:
    """Start a pending PayPal checkout with its order id already attached."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.PAYPAL)
    payment.provider_ref = "ORDER-1"
    payment.save(update_fields=["provider_ref"])
    return payment


def messages(caplog: pytest.LogCaptureFixture) -> list[str]:
    """Every captured log record's rendered message, in order."""
    return [record.getMessage() for record in caplog.records]


# --------------------------------------------------------------------------
# Stripe
# --------------------------------------------------------------------------
@pytest.mark.parametrize("error", STRIPE_ERRORS, ids=STRIPE_ERROR_IDS)
def test_a_stripe_failure_at_checkout_is_a_400(
    api_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    monkeypatch: pytest.MonkeyPatch,
    error: stripe.StripeError,
) -> None:
    """Any Stripe SDK error at checkout comes back as a 400, not a 500."""
    break_stripe(monkeypatch, error)

    api_client.force_login(member)
    response = api_client.post(
        CHECKOUT, {"plan": "annual", "contribution_cents": 0, "provider": "stripe"}
    )

    assert response.status_code == 400
    assert response.data["detail"] == "Stripe could not be reached. Please try again."


@pytest.mark.parametrize("error", STRIPE_ERRORS, ids=STRIPE_ERROR_IDS)
def test_a_stripe_failure_at_checkout_leaves_no_payment_behind(
    api_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    monkeypatch: pytest.MonkeyPatch,
    error: stripe.StripeError,
) -> None:
    """A Stripe failure at checkout deletes the pending payment it had just created."""
    break_stripe(monkeypatch, error)

    api_client.force_login(member)
    api_client.post(CHECKOUT, {"plan": "annual", "contribution_cents": 0, "provider": "stripe"})

    assert Payment.objects.count() == 0


def test_a_stripe_failure_at_checkout_logs_the_exception_class(
    api_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A Stripe failure at checkout logs the SDK exception's class name."""
    caplog.set_level(logging.WARNING, logger=STRIPE_LOGGER)
    break_stripe(
        monkeypatch,
        stripe.APIConnectionError("aborted"),  # type: ignore[no-untyped-call]  # stripe stubs leave APIConnectionError.__init__ untyped
    )

    api_client.force_login(member)
    api_client.post(CHECKOUT, {"plan": "annual", "contribution_cents": 0, "provider": "stripe"})

    assert "APIConnectionError" in " ".join(messages(caplog))


def test_a_stripe_failure_at_confirm_is_a_400(
    api_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Stripe failure at confirm comes back as a 400, not a 500."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    break_stripe(
        monkeypatch,
        stripe.APIConnectionError("aborted"),  # type: ignore[no-untyped-call]  # stripe stubs leave APIConnectionError.__init__ untyped
    )

    api_client.force_login(member)
    response = api_client.post(CONFIRM, {"payment_id": payment.pk, "payment_intent_id": "pi_out"})

    assert response.status_code == 400
    assert response.data["detail"] == "Stripe could not be reached. Please try again."


def test_a_stripe_failure_at_confirm_leaves_the_payment_pending(
    api_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Stripe failure at confirm leaves the payment pending for another attempt."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    break_stripe(monkeypatch, stripe.RateLimitError("slow down"))

    api_client.force_login(member)
    api_client.post(CONFIRM, {"payment_id": payment.pk, "payment_intent_id": "pi_out"})

    payment.refresh_from_db()
    assert payment.status == PaymentStatus.PENDING


def test_a_stripe_failure_never_logs_an_email_address(
    api_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The logged Stripe failure message never includes an email address."""
    caplog.set_level(logging.WARNING, logger=STRIPE_LOGGER)
    break_stripe(
        monkeypatch,
        stripe.APIConnectionError("aborted"),  # type: ignore[no-untyped-call]  # stripe stubs leave APIConnectionError.__init__ untyped
    )

    api_client.force_login(member)
    api_client.post(CHECKOUT, {"plan": "annual", "contribution_cents": 0, "provider": "stripe"})

    logged = " ".join(messages(caplog))
    assert "Stripe payment_intents.create failed" in logged
    assert "@" not in logged


# --------------------------------------------------------------------------
# PayPal: token and order creation
# --------------------------------------------------------------------------
@respx.mock
def test_a_paypal_token_timeout_at_checkout_is_a_400(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A timeout fetching a PayPal token at checkout is a 400, not a 500."""
    respx.post(TOKEN_URL).mock(side_effect=httpx.ConnectTimeout("timed out"))

    api_client.force_login(member)
    response = api_client.post(
        CHECKOUT, {"plan": "annual", "contribution_cents": 0, "provider": "paypal"}
    )

    assert response.status_code == 400
    assert response.data["detail"] == "PayPal could not be reached. Please try again."


@respx.mock
def test_a_paypal_token_timeout_at_checkout_leaves_no_payment_behind(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A PayPal token timeout at checkout leaves no payment row behind."""
    respx.post(TOKEN_URL).mock(side_effect=httpx.ConnectTimeout("timed out"))

    api_client.force_login(member)
    api_client.post(CHECKOUT, {"plan": "annual", "contribution_cents": 0, "provider": "paypal"})

    assert Payment.objects.count() == 0


@respx.mock
def test_a_token_response_that_is_not_json_is_a_400(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A non-JSON token response is treated as a provider outage, a 400."""
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
def test_an_order_connection_error_at_checkout_is_a_400(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A connection error creating the PayPal order is a 400, not a 500."""
    token_route(respx.mock)
    respx.post(ORDERS_URL).mock(side_effect=httpx.ConnectError("refused"))

    api_client.force_login(member)
    response = api_client.post(
        CHECKOUT, {"plan": "annual", "contribution_cents": 0, "provider": "paypal"}
    )

    assert response.status_code == 400
    assert response.data["detail"] == "PayPal could not be reached. Please try again."


@respx.mock
def test_an_order_connection_error_at_checkout_leaves_no_payment_behind(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """An order-creation connection error leaves no payment row behind."""
    token_route(respx.mock)
    respx.post(ORDERS_URL).mock(side_effect=httpx.ConnectError("refused"))

    api_client.force_login(member)
    api_client.post(CHECKOUT, {"plan": "annual", "contribution_cents": 0, "provider": "paypal"})

    assert Payment.objects.count() == 0


# --------------------------------------------------------------------------
# PayPal: capture
# --------------------------------------------------------------------------
@respx.mock
def test_a_capture_timeout_is_a_400(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A timeout capturing a PayPal order is a 400, not a 500."""
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    respx.post(f"{ORDERS_URL}/ORDER-1/capture").mock(side_effect=httpx.ConnectTimeout("timed out"))

    api_client.force_login(member)
    response = api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER-1"})

    assert response.status_code == 400
    assert response.data["detail"] == "PayPal could not be reached. Please try again."


@respx.mock
def test_a_capture_timeout_leaves_the_payment_pending(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A capture timeout leaves the payment pending for another attempt."""
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    respx.post(f"{ORDERS_URL}/ORDER-1/capture").mock(side_effect=httpx.ConnectTimeout("timed out"))

    api_client.force_login(member)
    api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER-1"})

    payment.refresh_from_db()
    assert payment.status == PaymentStatus.PENDING


@respx.mock
def test_a_capture_timeout_is_logged_with_the_payment_and_amount(
    api_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A capture timeout is logged with the payment id and its amount in cents."""
    caplog.set_level(logging.ERROR, logger=PAYPAL_LOGGER)
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    respx.post(f"{ORDERS_URL}/ORDER-1/capture").mock(side_effect=httpx.ConnectTimeout("timed out"))

    api_client.force_login(member)
    api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER-1"})

    logged = " ".join(r.getMessage() for r in caplog.records if r.levelno == logging.ERROR)
    assert f"payment {payment.pk}" in logged
    assert f"{payment.amount_cents} cents" in logged


@respx.mock
def test_a_capture_of_the_wrong_amount_is_logged_with_both_amounts(
    api_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A capture whose amount does not match is logged with both amounts."""
    caplog.set_level(logging.ERROR, logger=PAYPAL_LOGGER)
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
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
def test_a_capture_in_another_currency_is_logged(
    api_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A capture in the wrong currency is logged with the payment id."""
    caplog.set_level(logging.ERROR, logger=PAYPAL_LOGGER)
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    respx.post(f"{ORDERS_URL}/ORDER-1/capture").mock(
        return_value=httpx.Response(201, json=capture_payload(payment, currency="CAD"))
    )

    api_client.force_login(member)
    api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER-1"})

    logged = " ".join(r.getMessage() for r in caplog.records if r.levelno == logging.ERROR)
    assert f"payment {payment.pk}" in logged


@respx.mock
def test_a_capture_mismatch_never_logs_an_email_address(
    api_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The logged capture-mismatch message never includes an email address."""
    caplog.set_level(logging.ERROR, logger=PAYPAL_LOGGER)
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    respx.post(f"{ORDERS_URL}/ORDER-1/capture").mock(
        return_value=httpx.Response(201, json=capture_payload(payment, value="1.00"))
    )

    api_client.force_login(member)
    api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER-1"})

    logged = " ".join(messages(caplog))
    assert "PayPal capture mismatch" in logged
    assert "@" not in logged


@respx.mock
def test_a_capture_mismatch_grants_no_membership(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A capture that does not match the payment grants no membership."""
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    respx.post(f"{ORDERS_URL}/ORDER-1/capture").mock(
        return_value=httpx.Response(201, json=capture_payload(payment, value="1.00"))
    )

    api_client.force_login(member)
    api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER-1"})

    assert Membership.objects.count() == 0


# --------------------------------------------------------------------------
# PayPal: webhook signature verification
# --------------------------------------------------------------------------
def capture_completed_event(payment: Payment) -> dict[str, Any]:
    """A ``PAYMENT.CAPTURE.COMPLETED`` webhook payload naming ``payment``."""
    return {
        "event_type": "PAYMENT.CAPTURE.COMPLETED",
        "resource": {
            "id": "CAPTURE-1",
            "custom_id": str(payment.pk),
            "status": "COMPLETED",
            "amount": {"currency_code": "USD", "value": f"{payment.amount_cents / 100:.2f}"},
        },
    }


def post_webhook(client: APIClient, event: dict[str, Any]) -> Response:
    """Post a PayPal webhook body, unsigned, as PayPal's own headers would arrive."""
    return client.post(WEBHOOK, data=json.dumps(event), content_type="application/json")


@respx.mock
def test_a_verification_timeout_leaves_the_webhook_unverified(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, settings: Settings
) -> None:
    """A timeout verifying a PayPal webhook signature leaves it unverified, not a 500."""
    settings.PAYPAL_WEBHOOK_ID = "WH-CONFIG"
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    respx.post(VERIFY_URL).mock(side_effect=httpx.ConnectTimeout("timed out"))

    response = post_webhook(api_client, capture_completed_event(payment))

    assert response.status_code == 200
    assert json.loads(response.content)["verified"] is False


@respx.mock
def test_a_verification_timeout_leaves_the_payment_pending(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, settings: Settings
) -> None:
    """A webhook signature-verification timeout leaves the payment pending."""
    settings.PAYPAL_WEBHOOK_ID = "WH-CONFIG"
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    respx.post(VERIFY_URL).mock(side_effect=httpx.ConnectTimeout("timed out"))

    post_webhook(api_client, capture_completed_event(payment))

    payment.refresh_from_db()
    assert payment.status == PaymentStatus.PENDING


# --------------------------------------------------------------------------
# The exception itself
# --------------------------------------------------------------------------
@respx.mock
def test_the_token_call_raises_provider_unavailable() -> None:
    """A timeout fetching a PayPal token raises ProviderUnavailable directly."""
    respx.post(TOKEN_URL).mock(side_effect=httpx.ConnectTimeout("timed out"))
    with pytest.raises(ProviderUnavailable, match="PayPal could not be reached"):
        paypal.access_token()
