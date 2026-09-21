"""Payment providers.  Importing this package registers every provider."""

from apps.payments.providers.base import (
    Provider,
    available_providers,
    get_provider,
    register,
)
from apps.payments.providers.mock import MockProvider
from apps.payments.providers.paypal import PayPalProvider
from apps.payments.providers.stripe import StripeProvider

__all__ = [
    "MockProvider",
    "PayPalProvider",
    "Provider",
    "StripeProvider",
    "available_providers",
    "get_provider",
    "register",
]
