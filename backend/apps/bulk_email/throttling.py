"""The rate limit on a bulk email's checks, counted per signed-in account.

Every run of the checks fetches each link in the message from the server, so a sender
pressing **Check again** over and over, or a script with a session, would otherwise
have the server fetch the same addresses without end.  The rate comes from the
``BULK_EMAIL_CHECKS_THROTTLE_RATE`` setting rather than DRF's
``DEFAULT_THROTTLE_RATES``, so the test settings can switch it off and a single test
can switch it back on with the ``settings`` fixture.
"""

from __future__ import annotations

from django.conf import settings
from rest_framework.throttling import UserRateThrottle

#: The throttle's scope, which names its counters in the cache.
CHECKS_SCOPE = "bulk_email_checks"


class BulkEmailChecksThrottle(UserRateThrottle):
    """Throttles ``POST /bulk-email/{id}/checks`` per account.

    The rate is ``BULK_EMAIL_CHECKS_THROTTLE_RATE``.  Each account has its own budget,
    so one sender's checks never slow another's.
    """

    scope = CHECKS_SCOPE

    def get_rate(self) -> str | None:
        """The configured rate, or ``None`` when the throttle is switched off.

        ``None`` and an empty string both mean off, because DRF treats only ``None``
        as unlimited and an empty string would otherwise fail to parse.
        """
        rate: str | None = settings.BULK_EMAIL_CHECKS_THROTTLE_RATE
        return rate or None
