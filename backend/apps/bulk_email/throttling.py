"""The rate limits on a bulk email's checks, per account, and on a callout's answers.

A callout answer link may send at most ``CALLOUT_ANSWER_THROTTLE_RATE`` answers, counted
per link (:class:`CalloutAnswerThrottle`): each changed answer can email every
subscriber, so a forwarded link must not be able to fill their inboxes.

Every run of the checks fetches each link in the message from the server, so a sender
pressing **Check again** over and over, or a script with a session, would otherwise
have the server fetch the same addresses without end.  The rate comes from the
``BULK_EMAIL_CHECKS_THROTTLE_RATE`` setting rather than DRF's
``DEFAULT_THROTTLE_RATES``, so the test settings can switch it off and a single test
can switch it back on with the ``settings`` fixture.
"""

from __future__ import annotations

import hashlib

from django.conf import settings
from django.http import HttpRequest
from rest_framework.throttling import SimpleRateThrottle, UserRateThrottle

#: The throttle's scope, which names its counters in the cache.
CHECKS_SCOPE = "bulk_email_checks"

#: The callout answer throttle's scope.
CALLOUT_ANSWER_SCOPE = "callout_answer"


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


class CalloutAnswerThrottle(SimpleRateThrottle):
    """Throttles the answers one callout link sends, at ``CALLOUT_ANSWER_THROTTLE_RATE``.

    The counter is keyed by a hash of the link's token, so each recipient's link has its
    own budget and the token itself is never stored.  Call :meth:`allows` with the
    request and the token; the answer page is a plain Django view, with no DRF view.
    """

    scope = CALLOUT_ANSWER_SCOPE

    def __init__(self, token: str) -> None:
        """Remember ``token``, whose answers this throttle counts, then read the rate."""
        self.token = token
        super().__init__()

    def get_rate(self) -> str | None:
        """The configured rate, or ``None`` when the throttle is switched off."""
        rate: str | None = settings.CALLOUT_ANSWER_THROTTLE_RATE
        return rate or None

    def get_cache_key(self, request: object, view: object) -> str:
        """The counter's key: the scope and a SHA-256 digest of the token."""
        digest = hashlib.sha256(self.token.encode()).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": digest}

    def allows(self, request: HttpRequest) -> bool:
        """Count one answer from ``request``; False once the link's budget is spent."""
        return self.allow_request(request, None)  # type: ignore[arg-type]  # no DRF view
