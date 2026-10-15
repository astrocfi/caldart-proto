"""Rate limits on the signed-in endpoints that start, or finish, a payment.

Each start asks a provider for a payment intent, an order, or a setup intent, and each
confirmation asks the provider again, so both are counted per account.  Declined
intents are canceled by the providers, and Stripe Radar is the recommended control on
Stripe's side (``docs/developer/payments-setup.rst``).  Each account has its own budget
for each scope, so one member's checkout never slows another's.  The public donation
page's own endpoints are counted by client address instead
(``apps.accounts.throttling``).

Rates come from the ``PAYMENT_THROTTLE_RATES`` setting rather than DRF's
``DEFAULT_THROTTLE_RATES``, so the test settings can switch them off and a single test
can switch one back on with the ``settings`` fixture.  A scope mapped to ``None``, to an
empty string, or absent from the mapping is off.
"""

from __future__ import annotations

from django.conf import settings
from rest_framework.throttling import UserRateThrottle

#: Scope names, also the keys of ``settings.PAYMENT_THROTTLE_RATES``.
START_SCOPE = "payment_start"
CONFIRM_SCOPE = "payment_confirm"


class PaymentScopedThrottle(UserRateThrottle):
    """A per-account throttle whose rate is read from ``PAYMENT_THROTTLE_RATES``."""

    scope = ""

    def get_rate(self) -> str | None:
        """The configured rate, or ``None`` when this scope is switched off.

        ``None``, an empty string, and a missing key all mean off, because DRF treats
        only ``None`` as unlimited and an empty string would otherwise fail to parse.
        """
        rate: str | None = settings.PAYMENT_THROTTLE_RATES.get(self.scope)
        return rate or None


class PaymentStartThrottle(PaymentScopedThrottle):
    """Throttles checkout and the two method setups under the ``payment_start`` rate.

    ``POST /payments/checkout``, ``/me/renewal/setup``, and ``/me/donation/setup``
    share one budget per account, so none of them is a way round the others.
    """

    scope = START_SCOPE


class PaymentConfirmThrottle(PaymentScopedThrottle):
    """Throttles every signed-in confirmation under the ``payment_confirm`` rate.

    ``POST /payments/stripe/confirm``, ``/payments/paypal/capture``,
    ``/me/renewal/confirm``, and ``/me/donation/confirm`` share one budget per account.
    """

    scope = CONFIRM_SCOPE
