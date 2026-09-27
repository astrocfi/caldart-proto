"""The rate limit on address suggestions, counted per signed-in account.

Every suggestion is a call to Geoapify on the project's key, so a member holding a
key down in the street field, or a script with a session, would otherwise spend the
provider's daily quota for everyone.  The rate comes from the
``ADDRESS_SUGGEST_THROTTLE_RATE`` setting rather than DRF's
``DEFAULT_THROTTLE_RATES``, so the test settings can switch it off and a single test
can switch it back on with the ``settings`` fixture.
"""

from __future__ import annotations

from django.conf import settings
from rest_framework.throttling import UserRateThrottle

#: The throttle's scope, which names its counters in the cache.
ADDRESS_SUGGEST_SCOPE = "address_suggest"


class AddressSuggestThrottle(UserRateThrottle):
    """Throttles ``GET /addresses/suggest`` under ``ADDRESS_SUGGEST_THROTTLE_RATE``.

    Each account has its own budget, so one member's typing never slows another's.
    """

    scope = ADDRESS_SUGGEST_SCOPE

    def get_rate(self) -> str | None:
        """The configured rate, or ``None`` when the throttle is switched off.

        ``None`` and an empty string both mean off, because DRF treats only ``None``
        as unlimited and an empty string would otherwise fail to parse.
        """
        rate: str | None = settings.ADDRESS_SUGGEST_THROTTLE_RATE
        return rate or None
