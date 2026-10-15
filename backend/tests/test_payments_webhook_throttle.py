"""The rate limit on the two payment webhooks, counted per client address.

Both routes are anonymous and CSRF-exempt, so the limit is what keeps a caller who
is not the provider from spending the server, and PayPal's verification quota, on
deliveries without end.  The rate is ``PAYMENTS_WEBHOOK_THROTTLE_RATE``; the test
settings switch it off, and each test here switches it back on.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from django.core.cache import cache
from pytest_django.fixtures import Settings
from rest_framework.test import APIClient

from apps.payments.webhook_throttling import WEBHOOK_SCOPE, PaymentsWebhookThrottle

pytestmark = pytest.mark.django_db

STRIPE_WEBHOOK = "/api/v1/payments/stripe/webhook"
PAYPAL_WEBHOOK = "/api/v1/payments/paypal/webhook"


#: Each webhook with what it answers an unthrottled delivery here: Stripe refuses the
#: signature, and PayPal's route is refused while no webhook id is set.
REFUSALS = [(STRIPE_WEBHOOK, 400), (PAYPAL_WEBHOOK, 404)]


@pytest.fixture(autouse=True)
def _empty_throttle_cache(settings: Settings) -> Iterator[None]:
    """Start and end each test with no counters, and with neither provider able to act.

    A Stripe delivery is refused for its signature and a PayPal one for the missing
    webhook id, so every request reaches the throttle and nothing past it.
    """
    settings.STRIPE_WEBHOOK_SECRET = "whsec_test"  # noqa: S105 - test fixture
    settings.PAYPAL_WEBHOOK_ID = ""
    cache.clear()
    yield
    cache.clear()


def post(client: APIClient, url: str, remote_addr: str = "203.0.113.7") -> int:
    """POST an unsigned notification to ``url`` from ``remote_addr``; the status."""
    body = json.dumps({"event_type": "PAYMENT.CAPTURE.COMPLETED", "resource": {}})
    response = client.post(url, data=body, content_type="application/json", REMOTE_ADDR=remote_addr)
    return response.status_code


@pytest.mark.parametrize(("url", "refusal"), REFUSALS, ids=["stripe", "paypal"])
def test_the_webhook_answers_429_past_the_rate(
    api_client: APIClient, settings: Settings, url: str, refusal: int
) -> None:
    """With a rate of two a minute, the third delivery in the minute is a 429."""
    settings.PAYMENTS_WEBHOOK_THROTTLE_RATE = "2/min"

    statuses = [post(api_client, url) for _ in range(3)]

    assert statuses == [refusal, refusal, 429]


@pytest.mark.parametrize(("url", "refusal"), REFUSALS, ids=["stripe", "paypal"])
def test_the_webhook_counts_each_address_separately(
    api_client: APIClient, settings: Settings, url: str, refusal: int
) -> None:
    """One address spending the budget leaves another address's untouched."""
    settings.PAYMENTS_WEBHOOK_THROTTLE_RATE = "1/min"
    post(api_client, url, remote_addr="203.0.113.7")

    assert post(api_client, url, remote_addr="198.51.100.9") == refusal


@pytest.mark.parametrize(("url", "refusal"), REFUSALS, ids=["stripe", "paypal"])
def test_the_webhook_is_unthrottled_with_no_rate(
    api_client: APIClient, settings: Settings, url: str, refusal: int
) -> None:
    """With the rate switched off, no delivery is refused for its count."""
    settings.PAYMENTS_WEBHOOK_THROTTLE_RATE = None

    statuses = {post(api_client, url) for _ in range(5)}

    assert statuses == {refusal}


@pytest.mark.parametrize("rate", [None, ""], ids=["none", "empty"])
def test_an_empty_rate_makes_the_throttle_inert(settings: Settings, rate: str | None) -> None:
    """``None`` or an empty string for the rate switches the throttle off."""
    settings.PAYMENTS_WEBHOOK_THROTTLE_RATE = rate

    assert PaymentsWebhookThrottle().get_rate() is None


def test_the_throttle_reads_its_rate_from_settings(settings: Settings) -> None:
    """The rate is ``PAYMENTS_WEBHOOK_THROTTLE_RATE``, under ``payments_webhook``."""
    settings.PAYMENTS_WEBHOOK_THROTTLE_RATE = "7/min"

    throttle = PaymentsWebhookThrottle()

    assert (throttle.scope, throttle.get_rate()) == (WEBHOOK_SCOPE, "7/min")
