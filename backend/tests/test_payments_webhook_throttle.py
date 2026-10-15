"""The rate limit on the PayPal webhook, counted per client address or IPv6 ``/64``.

The route is anonymous and CSRF-exempt, and checking a notification costs a call to
PayPal, so the limit is what keeps a caller who is not PayPal from spending the
server and PayPal's verification quota on deliveries without end.  The rate is
``PAYPAL_WEBHOOK_THROTTLE_RATE``; the test settings switch it off, and each test here
switches it back on.  The Stripe webhook, whose check is local, is not throttled.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from django.core.cache import cache
from pytest_django.fixtures import Settings
from rest_framework.test import APIClient

from apps.payments.webhook_throttling import (
    WEBHOOK_SCOPE,
    PayPalWebhookThrottle,
    client_bucket,
)

pytestmark = pytest.mark.django_db

STRIPE_WEBHOOK = "/api/v1/payments/stripe/webhook"
PAYPAL_WEBHOOK = "/api/v1/payments/paypal/webhook"

#: What the PayPal route answers an unthrottled delivery here: no webhook id is set.
NOT_CONFIGURED = 404

#: What the Stripe route answers an unsigned delivery.
BAD_SIGNATURE = 400


@pytest.fixture(autouse=True)
def _empty_throttle_cache(settings: Settings) -> Iterator[None]:
    """Start and end each test with empty counters, and with neither provider able to act.

    A Stripe delivery is refused for its signature and a PayPal one for the missing
    webhook id, so every request reaches the throttle and stops there.
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


def test_the_paypal_webhook_answers_429_past_the_rate(
    api_client: APIClient, settings: Settings
) -> None:
    """With a rate of two a minute, the third delivery in the minute is a 429."""
    settings.PAYPAL_WEBHOOK_THROTTLE_RATE = "2/min"

    statuses = [post(api_client, PAYPAL_WEBHOOK) for _ in range(3)]

    assert statuses == [NOT_CONFIGURED, NOT_CONFIGURED, 429]


def test_the_paypal_webhook_counts_each_address_separately(
    api_client: APIClient, settings: Settings
) -> None:
    """One address spending the budget leaves another address's untouched."""
    settings.PAYPAL_WEBHOOK_THROTTLE_RATE = "1/min"
    post(api_client, PAYPAL_WEBHOOK, remote_addr="203.0.113.7")

    assert post(api_client, PAYPAL_WEBHOOK, remote_addr="198.51.100.9") == NOT_CONFIGURED


def test_the_paypal_webhook_counts_an_ipv6_64_as_one_address(
    api_client: APIClient, settings: Settings
) -> None:
    """Another address inside the same IPv6 ``/64`` shares the budget."""
    settings.PAYPAL_WEBHOOK_THROTTLE_RATE = "1/min"
    post(api_client, PAYPAL_WEBHOOK, remote_addr="2001:db8:1:2::1")

    assert post(api_client, PAYPAL_WEBHOOK, remote_addr="2001:db8:1:2:ffff::9") == 429


def test_the_paypal_webhook_is_unthrottled_without_a_rate(
    api_client: APIClient, settings: Settings
) -> None:
    """With the rate switched off, no delivery is refused for its count."""
    settings.PAYPAL_WEBHOOK_THROTTLE_RATE = None

    statuses = {post(api_client, PAYPAL_WEBHOOK) for _ in range(5)}

    assert statuses == {NOT_CONFIGURED}


def test_the_stripe_webhook_is_not_throttled(api_client: APIClient, settings: Settings) -> None:
    """Stripe's signature is checked locally, so its deliveries are never counted."""
    settings.PAYPAL_WEBHOOK_THROTTLE_RATE = "1/min"

    statuses = {post(api_client, STRIPE_WEBHOOK) for _ in range(3)}

    assert statuses == {BAD_SIGNATURE}


@pytest.mark.parametrize(
    ("ident", "bucket"),
    [
        ("203.0.113.7", "203.0.113.7"),
        ("2001:db8:1:2:3:4:5:6", "2001:db8:1:2::/64"),
        ("::ffff:203.0.113.7", "203.0.113.7"),
        ("203.0.113.7,198.51.100.9", "203.0.113.7,198.51.100.9"),
    ],
    ids=["ipv4", "ipv6", "ipv4-mapped", "not an address"],
)
def test_an_address_is_charged_to_its_bucket(ident: str, bucket: str) -> None:
    """IPv6 is counted by ``/64``; everything else as it is."""
    assert client_bucket(ident) == bucket


@pytest.mark.parametrize("rate", [None, ""], ids=["none", "empty"])
def test_an_empty_rate_makes_the_throttle_inert(settings: Settings, rate: str | None) -> None:
    """``None`` or an empty string for the rate switches the throttle off."""
    settings.PAYPAL_WEBHOOK_THROTTLE_RATE = rate

    assert PayPalWebhookThrottle().get_rate() is None


def test_the_throttle_counts_under_its_scope() -> None:
    """The throttle's counters are named by the ``paypal_webhook`` scope."""
    assert PayPalWebhookThrottle.scope == WEBHOOK_SCOPE


def test_the_throttle_reads_its_rate_from_settings(settings: Settings) -> None:
    """The rate is ``PAYPAL_WEBHOOK_THROTTLE_RATE``."""
    settings.PAYPAL_WEBHOOK_THROTTLE_RATE = "7/min"

    assert PayPalWebhookThrottle().get_rate() == "7/min"
