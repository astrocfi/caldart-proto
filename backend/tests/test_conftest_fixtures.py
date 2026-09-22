"""The shared fixtures in ``conftest.py`` that are not exercised elsewhere."""

from __future__ import annotations

from datetime import date

from django.utils import timezone


def test_today_freezes_the_clock_at_the_local_date(today: date) -> None:
    """The ``today`` fixture's date matches ``timezone.localdate()`` while frozen.

    A fixture that freezes midnight UTC instead of the current instant would
    read back as the day before in a negative-offset timezone.
    """
    assert timezone.localdate() == today


def test_today_keeps_the_clock_still_during_the_test(today: date) -> None:
    """``timezone.localdate()`` stays exactly ``today`` no matter when it is read."""
    later = timezone.localdate()
    assert later == today
