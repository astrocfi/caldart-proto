"""When a report subscription is next due.

A subscription names a cadence, and :func:`next_due_after` turns that cadence into
the next date the daily run should send it.  The run compares that date with the day
it runs on, so a day the timer missed is made good by the next run.
"""

from __future__ import annotations

from datetime import date, timedelta

from django.db import models


class Cadence(models.TextChoices):
    """How often a subscription is sent."""

    WEEKLY = "weekly", "Weekly"
    MONTHLY = "monthly", "Monthly"
    QUARTERLY = "quarterly", "Quarterly"
    YEARLY = "yearly", "Yearly"


#: Every month of the year.
MONTHS: tuple[int, ...] = tuple(range(1, 13))

#: The months a quarter begins in.
QUARTER_MONTHS: tuple[int, ...] = (1, 4, 7, 10)


def next_due_after(cadence: str, weekday: int, day: date) -> date:
    """The first date strictly after ``day`` on which ``cadence`` falls.

    ``weekly`` is the next ``weekday`` (0 Monday to 6 Sunday) after ``day``, a week
    later when ``day`` is that weekday; ``monthly`` the first of the next month;
    ``quarterly`` the next January, April, July or October 1; ``yearly`` the next
    January 1.  ``weekday`` is read by ``weekly`` alone.  Any other cadence raises
    ``ValueError`` reading ``Unknown cadence: <cadence>``.
    """
    if cadence == Cadence.WEEKLY:
        ahead = (weekday - day.weekday()) % 7 or 7
        return day + timedelta(days=ahead)
    if cadence == Cadence.MONTHLY:
        return _first_of_month_after(day, MONTHS)
    if cadence == Cadence.QUARTERLY:
        return _first_of_month_after(day, QUARTER_MONTHS)
    if cadence == Cadence.YEARLY:
        return date(day.year + 1, 1, 1)
    raise ValueError(f"Unknown cadence: {cadence}")


def _first_of_month_after(day: date, months: tuple[int, ...]) -> date:
    """The first day of the earliest month in ``months`` that begins after ``day``."""
    later = [month for month in months if month > day.month]
    if later:
        return date(day.year, later[0], 1)
    return date(day.year + 1, months[0], 1)


#: The weekday names, Monday first, as ``weekday`` counts them.
WEEKDAY_NAMES: tuple[str, ...] = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


def schedule_label(cadence: str, weekday: int) -> str:
    """The schedule in words, lower case: ``weekly on Monday``, ``monthly``, ``yearly``.

    ``weekday`` names the day for ``weekly`` alone; every other cadence is its own
    name.
    """
    if cadence == Cadence.WEEKLY:
        return f"weekly on {WEEKDAY_NAMES[weekday]}"
    return str(cadence)
