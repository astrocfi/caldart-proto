"""The rate limit on the payment webhooks, counted per client address.

``POST /payments/stripe/webhook`` and ``POST /payments/paypal/webhook`` take no
session and no CSRF token: the provider's signature is the only gate, and checking a
PayPal signature costs a call to PayPal.  A provider delivers a handful of
notifications per payment, so a caller sending more than
``PAYMENTS_WEBHOOK_THROTTLE_RATE`` from one address is answered 429 before either
handler runs, and a provider that is turned away retries later.  The rate comes from
that setting rather than DRF's ``DEFAULT_THROTTLE_RATES``, so the test settings can
switch it off and a single test can switch it back on with the ``settings`` fixture.
"""

from __future__ import annotations

from django.conf import settings
from rest_framework.request import Request
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

#: The throttle's scope, which names its counters in the cache.
WEBHOOK_SCOPE = "payments_webhook"


class PaymentsWebhookThrottle(SimpleRateThrottle):
    """Throttles both payment webhooks under ``PAYMENTS_WEBHOOK_THROTTLE_RATE``.

    Each client address has its own budget, shared between the two routes.
    """

    scope = WEBHOOK_SCOPE

    def get_rate(self) -> str | None:
        """The configured rate, or ``None`` when the throttle is switched off.

        ``None`` and an empty string both mean off, because DRF treats only ``None``
        as unlimited and an empty string would otherwise fail to parse.
        """
        rate: str | None = settings.PAYMENTS_WEBHOOK_THROTTLE_RATE
        return rate or None

    def get_cache_key(self, request: Request, view: APIView) -> str:
        """The counter's key: the scope and the client address."""
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}
