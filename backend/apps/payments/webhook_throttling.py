"""The rate limit on the PayPal webhook, counted per client address.

``POST /payments/paypal/webhook`` takes no session and no CSRF token: PayPal's
signature is the only gate, and checking it costs a call to PayPal.  PayPal delivers
a handful of notifications per payment, so a caller sending more than
``PAYPAL_WEBHOOK_THROTTLE_RATE`` from one address is answered 429 before the handler
runs, and PayPal, when it is turned away, sends the delivery again later.  The
Stripe webhook is not throttled: its signature is checked locally, at no cost, and a
429 would only delay a real delivery.

An IPv6 caller is counted by its ``/64``, the block one subscriber is usually given,
so stepping through addresses inside it buys no fresh budget.  The rate comes from
the setting rather than DRF's ``DEFAULT_THROTTLE_RATES``, so the test settings can
switch it off and a single test can switch it back on with the ``settings`` fixture.
"""

from __future__ import annotations

import ipaddress

from django.conf import settings
from rest_framework.request import Request
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

#: The throttle's scope, which names its counters in the cache.
WEBHOOK_SCOPE = "paypal_webhook"

#: The IPv6 prefix length one counter covers.
IPV6_PREFIX_LENGTH = 64


def client_bucket(ident: str) -> str:
    """The counter a client address is charged to.

    An IPv6 address is widened to its ``/64`` (``"2001:db8:1:2::/64"``); an IPv4
    address, an IPv4-mapped IPv6 one (as its IPv4 address), and anything that is
    not an address at all are counted as they are.
    """
    try:
        address = ipaddress.ip_address(ident)
    except ValueError:
        return ident
    if isinstance(address, ipaddress.IPv6Address):
        if address.ipv4_mapped is not None:
            return str(address.ipv4_mapped)
        network = ipaddress.ip_network(f"{address}/{IPV6_PREFIX_LENGTH}", strict=False)
        return str(network)
    return ident


class PayPalWebhookThrottle(SimpleRateThrottle):
    """Throttles ``POST /payments/paypal/webhook`` under ``PAYPAL_WEBHOOK_THROTTLE_RATE``.

    Each client address, or IPv6 ``/64``, has its own budget.
    """

    scope = WEBHOOK_SCOPE

    def get_rate(self) -> str | None:
        """The configured rate, or ``None`` when the throttle is switched off.

        ``None`` and an empty string both mean off, because DRF treats only ``None``
        as unlimited and an empty string would otherwise fail to parse.
        """
        rate: str | None = settings.PAYPAL_WEBHOOK_THROTTLE_RATE
        return rate or None

    def get_cache_key(self, request: Request, view: APIView) -> str:
        """The counter's key: the scope and :func:`client_bucket` of the address."""
        ident = client_bucket(self.get_ident(request))
        return self.cache_format % {"scope": self.scope, "ident": ident}
