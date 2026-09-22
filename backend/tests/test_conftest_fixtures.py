"""The shared fixtures in ``conftest.py`` that are not exercised elsewhere."""

from __future__ import annotations

import time
from datetime import date

import pytest
from django.utils import timezone

#: Real seconds the stillness test lets pass.  An unfrozen clock advances by
#: this much between the two reads; a frozen one does not move at all.
REAL_SECONDS = 0.05


@pytest.fixture
def local_date_before_freezing() -> date:
    """The local date read before ``today`` freezes the clock.

    A test takes this fixture ahead of ``today`` in its signature, so pytest
    builds it while the clock is still running.
    """
    return timezone.localdate()


def test_today_stops_the_clock_for_the_length_of_the_test(today: date) -> None:
    """``timezone.now()`` reads the same instant however much real time passes."""
    frozen = timezone.now()
    time.sleep(REAL_SECONDS)
    assert timezone.now() == frozen


def test_today_freezes_the_instant_whose_local_date_it_returns(
    local_date_before_freezing: date, today: date
) -> None:
    """The fixture's date is the local date, not the date at midnight UTC.

    Freezing a bare date freezes midnight UTC, which ``timezone.localdate()``
    reads back as the day before in the project's negative-offset timezone.
    """
    assert today == local_date_before_freezing
