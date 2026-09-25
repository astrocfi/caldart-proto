"""The latest day a ledger date may carry.

A ledger date -- the day a check arrived, the day a payment was matched to a
statement -- is typed by a treasurer whose browser fills in "today" from its own
clock, while the server judges "today" in the organization's time zone.  In the
evening those two disagree for anybody east of the organization: the browser has
reached tomorrow and the server has not.  The money did not arrive in the
future, so the server allows a ledger date one day past its own date rather than
refusing an honest entry.
"""

from __future__ import annotations

import datetime as dt

from django.utils import timezone

#: How far past the organization's own date a ledger date may run.  One day
#: covers every time zone ahead of the organization's; anything later is a typo.
CLOCK_GRACE_DAYS = 1


def latest_ledger_date(today: dt.date | None = None) -> dt.date:
    """The last day a ledger date may name: ``today`` plus :data:`CLOCK_GRACE_DAYS`.

    ``today`` defaults to the organization's current local date.
    """
    if today is None:
        today = timezone.localdate()
    return today + dt.timedelta(days=CLOCK_GRACE_DAYS)


def is_in_the_future(value: dt.date, today: dt.date | None = None) -> bool:
    """True when ``value`` is later than :func:`latest_ledger_date` allows."""
    return value > latest_ledger_date(today)
