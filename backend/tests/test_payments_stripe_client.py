"""The Stripe client's time budget and its idempotency key.

Stripe's library defaults are an 80-second timeout and two retries, which is
longer than every timeout in front of Django.  A slow Stripe response would
reach the browser as a gateway error while the request carried on, so the
provider builds its own client instead, and this module pins both the values
and the deployment limits they must stay under.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from pytest_django.fixtures import Settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.members.models import MembershipPlan
from apps.payments.models import PaymentProvider
from apps.payments.providers import stripe as stripe_provider
from apps.payments.providers.base import ProviderNotConfiguredError
from apps.payments.providers.stripe import (
    STRIPE_MAX_NETWORK_RETRIES,
    STRIPE_TIMEOUT_SECONDS,
    stripe_client,
)
from tests.test_payments_stripe import FakeIntents, fake_stripe_client

pytestmark = pytest.mark.django_db

CHECKOUT = "/api/v1/payments/checkout"
SECRET_KEY = "sk_test_123"  # noqa: S105 - test fixture

REPO_ROOT = Path(__file__).resolve().parents[2]
GUNICORN_CONF = REPO_ROOT / "deploy" / "gunicorn.conf.py"
NGINX_CONF = REPO_ROOT / "deploy" / "nginx" / "caldart.conf"
APACHE_CONF = REPO_ROOT / "deploy" / "apache" / "caldart.conf"

#: Each proxy's request timeout, and the pattern that reads it from its config.
PROXY_TIMEOUTS = [
    pytest.param(GUNICORN_CONF, r"^timeout\s*=\s*(\d+)", id="gunicorn"),
    pytest.param(NGINX_CONF, r"proxy_read_timeout\s+(\d+)s", id="nginx"),
    pytest.param(APACHE_CONF, r"ProxyTimeout\s+(\d+)", id="apache"),
]

#: stripe 15's own defaults, which the provider deliberately does not use.
LIBRARY_DEFAULT_TIMEOUT_SECONDS = 80.0


@pytest.fixture
def _stripe_configured(settings: Settings) -> None:
    """Set fake but well-formed Stripe keys."""
    settings.STRIPE_SECRET_KEY = SECRET_KEY
    settings.STRIPE_PUBLISHABLE_KEY = "pk_test_123"


def configured_seconds(path: Path, pattern: str) -> int:
    """The first timeout ``pattern`` matches in ``path``, in seconds."""
    match = re.search(pattern, path.read_text(), re.MULTILINE)
    assert match is not None, f"No timeout matching {pattern!r} in {path}"
    return int(match.group(1))


def worst_case_seconds() -> float:
    """The longest a Stripe call can take: the first attempt plus its retries."""
    return STRIPE_TIMEOUT_SECONDS * (STRIPE_MAX_NETWORK_RETRIES + 1)


# --------------------------------------------------------------------------
# The client
# --------------------------------------------------------------------------
@pytest.mark.usefixtures("_stripe_configured")
def test_the_client_uses_the_configured_timeout() -> None:
    """The built client's HTTP timeout matches ``STRIPE_TIMEOUT_SECONDS``."""
    # The HTTP client holds the timeout; the SDK exposes it only privately, and its
    # stubs type the attribute as optional even though building a client always sets it.
    http_client = stripe_client()._requestor._client
    assert http_client is not None
    assert http_client._timeout == STRIPE_TIMEOUT_SECONDS  # type: ignore[attr-defined]


@pytest.mark.usefixtures("_stripe_configured")
def test_the_client_uses_the_configured_retry_count() -> None:
    """The built client's retry count matches ``STRIPE_MAX_NETWORK_RETRIES``."""
    assert stripe_client()._requestor._options.max_network_retries == STRIPE_MAX_NETWORK_RETRIES


def test_the_client_carries_the_configured_secret_key(settings: Settings) -> None:
    """The built client's API key is the configured ``STRIPE_SECRET_KEY``."""
    settings.STRIPE_SECRET_KEY = "sk_test_abc"  # noqa: S105 - test fixture
    assert stripe_client()._requestor._options.api_key == "sk_test_abc"


def test_the_client_refuses_to_build_without_a_secret_key(settings: Settings) -> None:
    """Building a client with no secret key raises ``ProviderNotConfiguredError``."""
    settings.STRIPE_SECRET_KEY = ""
    with pytest.raises(ProviderNotConfiguredError, match="STRIPE_SECRET_KEY is empty"):
        stripe_client()


def test_the_budget_is_shorter_than_the_library_default() -> None:
    """The provider's worst-case budget stays under stripe's own 80-second default."""
    assert worst_case_seconds() < LIBRARY_DEFAULT_TIMEOUT_SECONDS


# --------------------------------------------------------------------------
# The budget against the deployment
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("path", "pattern"), PROXY_TIMEOUTS)
def test_the_worst_case_fits_under_each_proxy_timeout(path: Path, pattern: str) -> None:
    """The worst-case Stripe call finishes before each proxy's own timeout."""
    assert worst_case_seconds() < configured_seconds(path, pattern)


# --------------------------------------------------------------------------
# Idempotency
# --------------------------------------------------------------------------
@pytest.mark.usefixtures("_stripe_configured")
def test_checkout_sends_an_idempotency_key_derived_from_the_payment(
    api_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Stripe checkout call carries an idempotency key derived from the payment id."""
    intents = FakeIntents()
    monkeypatch.setattr(stripe_provider, "stripe_client", lambda: fake_stripe_client(intents))

    api_client.force_login(member)
    response = api_client.post(
        CHECKOUT,
        {"plan": "annual", "contribution_cents": 0, "provider": PaymentProvider.STRIPE},
    )

    assert response.status_code == 201
    assert (
        intents.create_options["idempotency_key"]
        == f"caldart-payment-{response.data['payment_id']}-start"
    )
