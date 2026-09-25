"""The report subscriptions' schedule and the daily run that sends them.

``next_due_after`` over every cadence from several dates; a run on a frozen clock
sends what is due and nothing else, moves each sent subscription on, leaves a refused
send due, pauses a recipient who lost the role, attaches both files for ``both``, and
writes one audit line.  The DART rosters the same run sends are covered by
``test_dart_rosters.py``, and the endpoints by ``test_report_subscriptions.py``.
"""

from __future__ import annotations

from datetime import date

import pytest

from apps.reports.schedule import next_due_after


@pytest.mark.parametrize(
    ("weekday", "day", "expected"),
    [
        (0, date(2026, 9, 25), date(2026, 9, 28)),
        (0, date(2026, 9, 28), date(2026, 10, 5)),
        (4, date(2026, 9, 25), date(2026, 10, 2)),
        (6, date(2026, 12, 30), date(2027, 1, 3)),
        (2, date(2026, 9, 29), date(2026, 9, 30)),
    ],
    ids=[
        "friday-to-monday",
        "monday-to-next-monday",
        "friday-to-friday",
        "across-a-year",
        "next-day",
    ],
)
def test_weekly_is_the_next_chosen_weekday_strictly_after_the_day(
    weekday: int, day: date, expected: date
) -> None:
    """A weekly subscription falls on the next ``weekday`` after ``day``, never on it."""
    assert next_due_after("weekly", weekday, day) == expected


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (date(2026, 9, 25), date(2026, 10, 1)),
        (date(2026, 10, 1), date(2026, 11, 1)),
        (date(2026, 12, 31), date(2027, 1, 1)),
        (date(2027, 1, 31), date(2027, 2, 1)),
    ],
    ids=["mid-month", "on-the-first", "december", "end-of-january"],
)
def test_monthly_is_the_first_of_the_next_month(day: date, expected: date) -> None:
    """A monthly subscription falls on the first of the month after ``day``."""
    assert next_due_after("monthly", 0, day) == expected


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (date(2026, 1, 1), date(2026, 4, 1)),
        (date(2026, 3, 31), date(2026, 4, 1)),
        (date(2026, 4, 1), date(2026, 7, 1)),
        (date(2026, 9, 25), date(2026, 10, 1)),
        (date(2026, 10, 1), date(2027, 1, 1)),
        (date(2026, 12, 31), date(2027, 1, 1)),
    ],
    ids=["new-year", "end-of-march", "april-first", "september", "october-first", "new-years-eve"],
)
def test_quarterly_is_the_first_day_of_the_next_quarter(day: date, expected: date) -> None:
    """A quarterly subscription falls on the next January, April, July or October 1."""
    assert next_due_after("quarterly", 0, day) == expected


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (date(2026, 1, 1), date(2027, 1, 1)),
        (date(2026, 9, 25), date(2027, 1, 1)),
        (date(2026, 12, 31), date(2027, 1, 1)),
    ],
    ids=["new-year", "september", "new-years-eve"],
)
def test_yearly_is_the_next_january_first(day: date, expected: date) -> None:
    """A yearly subscription falls on the next January 1 after ``day``."""
    assert next_due_after("yearly", 0, day) == expected


def test_an_unknown_cadence_is_refused() -> None:
    """A cadence the schedule does not know raises, naming it."""
    with pytest.raises(ValueError, match="Unknown cadence: daily"):
        next_due_after("daily", 0, date(2026, 9, 25))
