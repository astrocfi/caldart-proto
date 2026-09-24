"""``manage.py payments_sandbox_check``: verifies credentials without moving money.

Stripe's SDK is replaced with a fake ``v1.balance`` / ``v1.payment_method_configurations``
-- the same technique the Stripe provider tests use; PayPal is mocked at the HTTP layer
with respx, the same technique the PayPal provider tests use. Neither provider's real
transport is ever reached in this module: an unmocked Stripe call raises through the
guard below, and respx refuses any request it was not told to answer.
"""

from __future__ import annotations

from io import StringIO
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
import respx
import stripe
from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from pytest_django.fixtures import Settings

from apps.payments.providers import stripe as stripe_provider

pytestmark = pytest.mark.django_db

SANDBOX = "https://api-m.sandbox.paypal.com"
TOKEN_URL = f"{SANDBOX}/v1/oauth2/token"
WEBHOOKS_URL = f"{SANDBOX}/v1/notifications/webhooks"


@pytest.fixture(autouse=True)
def _no_provider_keys(settings: Settings) -> None:
    """Start every test with neither provider configured, whatever ``.env`` has."""
    settings.STRIPE_SECRET_KEY = ""
    settings.STRIPE_PUBLISHABLE_KEY = ""
    settings.STRIPE_WEBHOOK_SECRET = ""
    settings.PAYPAL_CLIENT_ID = ""
    settings.PAYPAL_CLIENT_SECRET = ""
    settings.PAYPAL_WEBHOOK_ID = ""
    settings.PAYPAL_ENV = "sandbox"
    cache.clear()


@pytest.fixture(autouse=True)
def _no_live_stripe(monkeypatch: pytest.MonkeyPatch) -> None:
    """Refuse the SDK's real transport, the same guard the Stripe provider tests use."""

    def refuse() -> stripe.HTTPClient:
        raise AssertionError("a test tried to reach Stripe over the network")

    monkeypatch.setattr(stripe_provider, "http_client", refuse)


def _stripe_balance(amount: int = 0, currency: str = "usd") -> dict[str, Any]:
    """A Stripe balance payload with one available entry."""
    return {
        "object": "balance",
        "available": [{"amount": amount, "currency": currency, "source_types": {}}],
        "pending": [],
        "livemode": False,
    }


def _stripe_payment_method_configuration(
    *, is_default: bool = True, **methods: bool
) -> dict[str, Any]:
    """A payment method configuration with the given methods available or not."""
    payload: dict[str, Any] = {
        "id": "pmc_1",
        "object": "payment_method_configuration",
        "name": "Default",
        "is_default": is_default,
        "active": True,
    }
    for name, available in methods.items():
        payload[name] = {"available": available}
    return payload


class _FakeBalance:
    """Stand-in for ``v1.balance`` answering ``retrieve`` with a fixed payload."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def retrieve(
        self, params: dict[str, Any] | None = None, options: dict[str, Any] | None = None
    ) -> stripe.Balance:
        """Return the fixed balance, ignoring any params the caller sent."""
        return stripe.Balance.construct_from(self.payload, "sk_test_x")


class _FakePaymentMethodConfigurations:
    """Stand-in for ``v1.payment_method_configurations`` answering ``list``."""

    def __init__(self, configurations: list[dict[str, Any]]) -> None:
        self.configurations = configurations

    def list(
        self, params: dict[str, Any] | None = None, options: dict[str, Any] | None = None
    ) -> stripe.ListObject[Any]:
        """Return the fixed configuration list, ignoring any params the caller sent."""
        payload = {"object": "list", "data": self.configurations, "has_more": False, "url": ""}
        return stripe.ListObject.construct_from(payload, "sk_test_x")


def _configure_fake_stripe(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
    *,
    balance: dict[str, Any] | None = None,
    configurations: list[dict[str, Any]] | None = None,
) -> None:
    """Set fake Stripe keys and a fake client answering balance and payment methods."""
    settings.STRIPE_SECRET_KEY = "sk_test_123"  # noqa: S105 - test fixture
    settings.STRIPE_PUBLISHABLE_KEY = "pk_test_123"
    client = SimpleNamespace(
        v1=SimpleNamespace(
            balance=_FakeBalance(balance or _stripe_balance()),
            payment_method_configurations=_FakePaymentMethodConfigurations(configurations or []),
        )
    )
    monkeypatch.setattr(stripe_provider, "stripe_client", lambda: client)


def _configure_paypal(settings: Settings) -> None:
    """Set fake PayPal credentials, without mocking any HTTP call."""
    settings.PAYPAL_CLIENT_ID = "client-id"
    settings.PAYPAL_CLIENT_SECRET = "client-secret"  # noqa: S105 - test fixture


def _token_route(expires_in: int = 3600) -> respx.Route:
    """Mock the PayPal OAuth token endpoint to return a fake token."""
    return respx.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200, json={"access_token": "A21AA-token", "expires_in": expires_in}
        )
    )


def _webhooks_route(*webhook_ids: str) -> respx.Route:
    """Mock the PayPal webhooks list endpoint to return the given webhook ids."""
    webhooks = [{"id": webhook_id, "url": "https://example.org/hook"} for webhook_id in webhook_ids]
    payload = {"webhooks": webhooks}
    return respx.get(WEBHOOKS_URL).mock(return_value=httpx.Response(200, json=payload))


def _run(**options: Any) -> str:
    """Run the command against a captured stdout and return what it printed."""
    out = StringIO()
    call_command("payments_sandbox_check", stdout=out, **options)
    return out.getvalue()


def test_neither_provider_configured_reports_what_is_missing_and_exits_nonzero() -> None:
    """With no keys at all, both providers report not configured and the command fails."""
    out = StringIO()
    with pytest.raises(CommandError, match="no provider is usable"):
        call_command("payments_sandbox_check", stdout=out)
    output = out.getvalue()
    assert "STRIPE_SECRET_KEY / STRIPE_PUBLISHABLE_KEY are empty" in output
    assert "PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET are empty" in output


def test_the_mock_provider_line_is_printed_before_the_command_fails() -> None:
    """The mock line is written even when the command goes on to fail."""
    out = StringIO()
    with pytest.raises(CommandError):
        call_command("payments_sandbox_check", stdout=out)
    assert "mock: available" in out.getvalue()


def test_the_mock_provider_line_reports_disabled_when_the_setting_is_off(
    settings: Settings,
) -> None:
    """A developer who turned the mock provider off sees it reported as disabled."""
    settings.PAYMENTS_MOCK_ENABLED = False
    out = StringIO()
    with pytest.raises(CommandError):
        call_command("payments_sandbox_check", stdout=out)
    output = out.getvalue()
    assert "mock: disabled (PAYMENTS_MOCK_ENABLED=False)" in output
    assert "mock: available" not in output


@respx.mock
def test_a_configured_and_reachable_stripe_reports_its_balance(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    """A working Stripe account's available balance is printed in dollars."""
    _configure_fake_stripe(monkeypatch, settings, balance=_stripe_balance(12345, "usd"))
    output = _run()
    assert "balance: $123.45 usd" in output


@respx.mock
def test_a_configured_and_reachable_stripe_lists_only_the_enabled_payment_methods(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    """Only the methods the default configuration marks available are listed."""
    _configure_fake_stripe(
        monkeypatch,
        settings,
        configurations=[
            _stripe_payment_method_configuration(card=True, link=True, us_bank_account=False)
        ],
    )
    output = _run()
    assert "enabled payment methods: card, link" in output
    assert "us_bank_account" not in output


@respx.mock
def test_a_stripe_account_with_no_default_configuration_reports_none_enabled(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    """No default payment method configuration reports as no methods enabled."""
    _configure_fake_stripe(monkeypatch, settings, configurations=[])
    output = _run()
    assert "enabled payment methods: none enabled" in output


@respx.mock
def test_a_stripe_balance_with_no_available_entries_reports_none_reported(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    """An empty ``available`` list reports as no balance, not skipped or crashed on."""
    empty_balance: dict[str, Any] = {
        "object": "balance",
        "available": [],
        "pending": [],
        "livemode": False,
    }
    _configure_fake_stripe(monkeypatch, settings, balance=empty_balance)
    output = _run()
    assert "balance: none reported" in output


@respx.mock
def test_stripe_reports_whether_the_webhook_secret_is_set(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    """The webhook secret's presence is reported without ever printing its value."""
    settings.STRIPE_WEBHOOK_SECRET = "whsec_super_secret"  # noqa: S105 - test fixture
    _configure_fake_stripe(monkeypatch, settings)
    output = _run()
    assert "STRIPE_WEBHOOK_SECRET: set" in output
    assert "whsec_super_secret" not in output


@respx.mock
def test_a_reachable_stripe_lets_the_command_exit_cleanly(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    """A working Stripe alone, with PayPal unconfigured, is enough to succeed."""
    _configure_fake_stripe(monkeypatch, settings)
    output = _run()
    assert "usable: stripe" in output


def _broken_stripe_client() -> SimpleNamespace:
    """A fake Stripe client whose balance call always raises an authentication error."""

    def retrieve(*args: Any, **kwargs: Any) -> None:
        raise stripe.AuthenticationError("Invalid API Key provided.")

    return SimpleNamespace(v1=SimpleNamespace(balance=SimpleNamespace(retrieve=retrieve)))


def test_a_stripe_call_that_is_refused_is_reported_and_fails_the_command(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    """An authentication error from Stripe is reported and the command exits non-zero."""
    settings.STRIPE_SECRET_KEY = "sk_test_bad"  # noqa: S105 - test fixture
    settings.STRIPE_PUBLISHABLE_KEY = "pk_test_bad"
    monkeypatch.setattr(stripe_provider, "stripe_client", _broken_stripe_client)

    out = StringIO()
    with pytest.raises(CommandError, match="configured but not reachable: stripe"):
        call_command("payments_sandbox_check", stdout=out)
    assert "could not reach Stripe" in out.getvalue()


@respx.mock
def test_a_broken_stripe_fails_the_command_even_when_paypal_works(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    """A configured but unreachable Stripe fails the command even with PayPal working."""
    settings.STRIPE_SECRET_KEY = "sk_test_bad"  # noqa: S105 - test fixture
    settings.STRIPE_PUBLISHABLE_KEY = "pk_test_bad"
    monkeypatch.setattr(stripe_provider, "stripe_client", _broken_stripe_client)
    _configure_paypal(settings)
    _token_route()
    _webhooks_route()

    out = StringIO()
    with pytest.raises(CommandError, match="configured but not reachable: stripe"):
        call_command("payments_sandbox_check", stdout=out)
    output = out.getvalue()
    assert "could not reach Stripe" in output
    assert "webhooks configured on this account: 0" in output


@respx.mock
def test_a_configured_and_reachable_paypal_reports_its_webhook_count(
    settings: Settings,
) -> None:
    """A token exchange followed by a webhooks list call reports how many there are."""
    _configure_paypal(settings)
    _token_route()
    _webhooks_route("8ML268241M613560S", "3JN028346V679622A")
    output = _run()
    assert "webhooks configured on this account: 2" in output
    assert "token: fetched (PAYPAL_ENV=sandbox)" in output


@respx.mock
def test_paypal_reports_no_webhook_id_configured_when_it_is_blank(settings: Settings) -> None:
    """With no ``PAYPAL_WEBHOOK_ID`` set, the report says so and matches nothing."""
    _configure_paypal(settings)
    _token_route()
    _webhooks_route("8ML268241M613560S")
    output = _run()
    assert "PAYPAL_WEBHOOK_ID: not set" in output


@respx.mock
def test_paypal_confirms_the_configured_webhook_id_is_found(settings: Settings) -> None:
    """A ``PAYPAL_WEBHOOK_ID`` naming one of the account's webhooks is confirmed found."""
    settings.PAYPAL_WEBHOOK_ID = "8ML268241M613560S"
    _configure_paypal(settings)
    _token_route()
    _webhooks_route("8ML268241M613560S", "3JN028346V679622A")
    output = _run()
    assert "PAYPAL_WEBHOOK_ID: set and found among the account's webhooks" in output


@respx.mock
def test_paypal_flags_a_configured_webhook_id_that_matches_none_of_the_accounts_webhooks(
    settings: Settings,
) -> None:
    """A ``PAYPAL_WEBHOOK_ID`` naming no match is flagged, not silently accepted."""
    settings.PAYPAL_WEBHOOK_ID = "does-not-exist"
    _configure_paypal(settings)
    _token_route()
    _webhooks_route("8ML268241M613560S")
    output = _run()
    assert "PAYPAL_WEBHOOK_ID: set but not found among the account's webhooks" in output


@respx.mock
def test_paypal_credentials_paypal_refuses_are_reported_and_fail_the_command(
    settings: Settings,
) -> None:
    """A 401 from the token endpoint is reported and the command exits non-zero."""
    _configure_paypal(settings)
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(401, json={"error": "invalid_client"}))

    out = StringIO()
    with pytest.raises(CommandError, match="configured but not reachable: paypal"):
        call_command("payments_sandbox_check", stdout=out)
    assert "could not reach PayPal" in out.getvalue()


@respx.mock
def test_both_providers_working_reports_both_as_usable(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    """With both Stripe and PayPal reachable, the command succeeds naming both."""
    _configure_fake_stripe(monkeypatch, settings)
    _configure_paypal(settings)
    _token_route()
    _webhooks_route()
    output = _run()
    assert "usable: stripe, paypal" in output
