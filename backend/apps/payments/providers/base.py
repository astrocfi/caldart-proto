"""Payment provider interface."""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse

from apps.payments.models import Payment


class PaymentError(RuntimeError):
    """A payment could not be completed.  The API turns this into HTTP 400."""


class ProviderNotConfigured(PaymentError):
    """The provider is missing its API keys."""


class ProviderUnavailable(PaymentError):
    """The provider could not be reached, or failed on its own side.

    Raised for transport failures (timeouts, refused connections, unreadable
    responses) and for errors the provider reports about itself, so that an
    outage answers 400 with "try again" instead of 500.  Checkout then deletes
    the pending :class:`~apps.payments.models.Payment` it had just created, and
    a confirmation leaves the payment pending for another attempt.
    """


class PaymentVerificationError(PaymentError):
    """The provider's own record of the payment does not match ours.

    Raised when the amount, currency, status or metadata returned by Stripe or
    PayPal disagrees with the :class:`~apps.payments.models.Payment` row, which
    is the one thing that must never be trusted to the client.
    """


class Provider:
    """A payment backend.

    ``start`` returns the parameters the browser needs to present the payment
    UI; ``confirm`` verifies server-side and marks the payment succeeded;
    ``handle_webhook`` processes an asynchronous notification.
    """

    slug: str = ""

    def start(self, payment: Payment) -> dict:
        """Client-side parameters, e.g. ``{"client_secret": ...}``."""
        raise NotImplementedError

    def confirm(self, payment: Payment, **kwargs) -> bool:
        """Verify with the provider and mark the payment succeeded or failed."""
        raise NotImplementedError

    def handle_webhook(self, request: HttpRequest) -> HttpResponse:
        """Process a provider webhook.  Must be idempotent."""
        raise NotImplementedError


_REGISTRY: dict[str, type[Provider]] = {}


def register(cls: type[Provider]) -> type[Provider]:
    """Class decorator registering a provider under its ``slug``."""
    if not cls.slug:
        raise ValueError(f"{cls.__name__} must define a slug")
    _REGISTRY[cls.slug] = cls
    return cls


def get_provider(slug: str) -> Provider:
    """Instantiate the provider registered under ``slug``."""
    # Import for side effects so the registry is populated.
    from apps.payments import providers  # noqa: F401

    try:
        return _REGISTRY[slug]()
    except KeyError as exc:
        raise ValueError(f"Unknown payment provider '{slug}'") from exc


def available_providers() -> list[str]:
    """Slugs of providers that are configured well enough to use."""
    from django.conf import settings

    from apps.payments import providers  # noqa: F401

    slugs: list[str] = []
    if settings.STRIPE_SECRET_KEY and settings.STRIPE_PUBLISHABLE_KEY:
        slugs.append("stripe")
    if settings.PAYPAL_CLIENT_ID and settings.PAYPAL_CLIENT_SECRET:
        slugs.append("paypal")
    if settings.PAYMENTS_MOCK_ENABLED:
        slugs.append("mock")
    return slugs
