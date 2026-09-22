"""The provider registry: ``is_configured`` and the list it builds.

``available_providers`` asks every registered provider whether it is configured,
so a provider that is added to the registry is offered as soon as its own
settings are present.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from pytest_django.fixtures import Settings

from apps.payments.providers import available_providers
from apps.payments.providers.base import _REGISTRY, Provider, register
from apps.payments.providers.mock import MockProvider
from apps.payments.providers.paypal import PayPalProvider
from apps.payments.providers.stripe import StripeProvider


@pytest.fixture
def unconfigured(settings: Settings) -> Settings:
    """Settings with every provider's configuration removed."""
    settings.STRIPE_SECRET_KEY = ""
    settings.STRIPE_PUBLISHABLE_KEY = ""
    settings.PAYPAL_CLIENT_ID = ""
    settings.PAYPAL_CLIENT_SECRET = ""
    settings.PAYMENTS_MOCK_ENABLED = False
    return settings


def test_the_base_provider_leaves_is_configured_to_its_subclasses() -> None:
    """``Provider.is_configured`` raises a bare ``NotImplementedError``."""
    with pytest.raises(NotImplementedError) as refusal:
        Provider.is_configured()
    assert str(refusal.value) == ""


def test_stripe_is_configured_only_with_both_keys(unconfigured: Settings) -> None:
    """Stripe needs the secret key and the publishable key together."""
    unconfigured.STRIPE_SECRET_KEY = "sk_test"  # noqa: S105 - fake key, local to this test
    assert StripeProvider.is_configured() is False

    unconfigured.STRIPE_PUBLISHABLE_KEY = "pk_test"
    assert StripeProvider.is_configured() is True


def test_paypal_is_configured_only_with_both_credentials(unconfigured: Settings) -> None:
    """PayPal needs the client id and the client secret together."""
    unconfigured.PAYPAL_CLIENT_ID = "client-id"
    assert PayPalProvider.is_configured() is False

    unconfigured.PAYPAL_CLIENT_SECRET = "client-secret"  # noqa: S105 - fake credential
    assert PayPalProvider.is_configured() is True


def test_the_mock_provider_follows_its_kill_switch(unconfigured: Settings) -> None:
    """The mock provider is configured exactly while ``PAYMENTS_MOCK_ENABLED`` is on."""
    assert MockProvider.is_configured() is False

    unconfigured.PAYMENTS_MOCK_ENABLED = True
    assert MockProvider.is_configured() is True


def test_available_providers_lists_every_configured_provider(unconfigured: Settings) -> None:
    """Fully configured, the list is stripe, paypal, mock, in that order."""
    unconfigured.STRIPE_SECRET_KEY = "sk_test"  # noqa: S105 - fake key, local to this test
    unconfigured.STRIPE_PUBLISHABLE_KEY = "pk_test"
    unconfigured.PAYPAL_CLIENT_ID = "client-id"
    unconfigured.PAYPAL_CLIENT_SECRET = "client-secret"  # noqa: S105 - fake credential
    unconfigured.PAYMENTS_MOCK_ENABLED = True

    assert available_providers() == ["stripe", "paypal", "mock"]


def test_available_providers_is_empty_when_nothing_is_configured(
    unconfigured: Settings,
) -> None:
    """No provider with its settings present means nothing to offer."""
    assert available_providers() == []


@pytest.fixture
def _extra_provider() -> Iterator[type[Provider]]:
    """Register a configured provider under ``extra`` and remove it afterwards."""

    @register
    class ExtraProvider(Provider):
        """A provider that is always configured."""

        slug = "extra"

        @classmethod
        def is_configured(cls) -> bool:
            """Always ``True``."""
            return True

    yield ExtraProvider
    del _REGISTRY["extra"]


@pytest.mark.usefixtures("_extra_provider")
def test_available_providers_offers_a_provider_the_registry_gained(
    unconfigured: Settings,
) -> None:
    """A registered provider that reports itself configured is offered.

    It follows the declared payment providers, which keeps the checkout order
    of stripe, paypal and mock fixed.
    """
    unconfigured.PAYMENTS_MOCK_ENABLED = True

    assert available_providers() == ["mock", "extra"]
