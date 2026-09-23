"""Payment provider interface."""

from __future__ import annotations

from typing import Any

from django.http import HttpRequest, HttpResponse

from apps.payments.models import Payment, PaymentProvider


class PaymentError(RuntimeError):
    """A payment could not be completed.  The API turns this into HTTP 400."""


class ProviderNotConfiguredError(PaymentError):
    """The provider is missing its API keys."""


class ProviderUnavailableError(PaymentError):
    """The provider could not be reached, or failed on its own side.

    Raised for transport failures (timeouts, refused connections, unreadable
    responses) and for errors the provider reports about itself, so that an
    outage answers 400 with "try again" instead of 500.  Checkout then deletes
    the pending :class:`~apps.payments.models.Payment` it had just created, and
    a confirmation leaves the payment pending for another attempt.
    """


class PaymentVerificationError(PaymentError):
    """The provider's own record of the payment does not match ours.

    Raised when the amount, currency, status, or metadata returned by Stripe or
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

    @classmethod
    def is_configured(cls) -> bool:
        """Whether the settings this provider needs to take a payment are present.

        Called without instantiating the class, so a provider that cannot be built
        without its keys still answers.  Raises ``NotImplementedError``: every
        subclass must define it.
        """
        raise NotImplementedError

    def start(self, payment: Payment) -> dict[str, Any]:
        """Client-side parameters, e.g. ``{"client_secret": ...}``.

        Raises ``NotImplementedError``: every subclass must define it.
        """
        raise NotImplementedError

    def confirm(self, payment: Payment, **kwargs: Any) -> bool:
        """Verify with the provider and mark the payment succeeded or failed.

        Returns whether the money arrived.  The keyword arguments are the
        provider's own handle on the attempt, such as Stripe's intent id or
        PayPal's order id.  Raises ``NotImplementedError``: every subclass must
        define it.
        """
        raise NotImplementedError

    def handle_webhook(self, request: HttpRequest) -> HttpResponse:
        """Process a provider webhook.  Must be idempotent.

        Raises ``NotImplementedError``: every subclass must define it.
        """
        raise NotImplementedError


_REGISTRY: dict[str, type[Provider]] = {}


def register(cls: type[Provider]) -> type[Provider]:
    """Class decorator registering a provider under its ``slug``.

    Returns ``cls`` unchanged, and raises ``ValueError`` naming the class when its
    ``slug`` is empty.  Registering a slug twice keeps the last class registered.
    """
    if not cls.slug:
        raise ValueError(f"{cls.__name__} must define a slug")
    _REGISTRY[cls.slug] = cls
    return cls


def get_provider(slug: str) -> Provider:
    """Instantiate the provider registered under ``slug``.

    Raises ``ValueError`` naming the slug when no provider is registered under it.
    A slug that is registered but unconfigured still instantiates: it is the call
    to ``start`` or ``confirm`` that raises :class:`ProviderNotConfiguredError`.
    """
    # Import for side effects so the registry is populated.
    from apps.payments import providers  # noqa: F401

    try:
        return _REGISTRY[slug]()
    except KeyError as exc:
        raise ValueError(f"Unknown payment provider '{slug}'") from exc


def available_providers() -> list[str]:
    """Slugs of the registered providers that answer ``is_configured()``.

    The order is the one ``PaymentProvider`` declares -- stripe, paypal, mock -- so
    the checkout screen offers the same choice every time; a registered slug that
    is not one of those choices follows them, in registration order.
    """
    from apps.payments import providers  # noqa: F401

    rank = {slug: position for position, slug in enumerate(PaymentProvider.values)}
    configured = [slug for slug, cls in _REGISTRY.items() if cls.is_configured()]
    return sorted(configured, key=lambda slug: rank.get(slug, len(rank)))
