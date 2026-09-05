"""Payment providers.  Importing this package registers every provider."""

from apps.payments.providers.base import (  # noqa: F401
    Provider,
    available_providers,
    get_provider,
    register,
)
from apps.payments.providers.mock import MockProvider  # noqa: F401
from apps.payments.providers.paypal import PayPalProvider  # noqa: F401
from apps.payments.providers.stripe import StripeProvider  # noqa: F401

__all__ = [
    "MockProvider",
    "PayPalProvider",
    "Provider",
    "StripeProvider",
    "available_providers",
    "get_provider",
    "register",
]
