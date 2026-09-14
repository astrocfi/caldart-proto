"""The reminder scan when a run is late.

A run that is up to two days late still catches its cohorts, ``expired`` is
never sent late, and a caught-up reminder is still logged once.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from apps.reminders.models import ReminderKind, ReminderLog
from apps.reminders.services import WINDOW_DAYS, send_renewal_reminders
from tests.test_reminders import TODAY, ends_on_for, make_member

pytestmark = pytest.mark.django_db

#: The kinds that catch up after a missed run; ``expired`` never does.
CATCH_UP_KINDS = [
    ReminderKind.T60,
    ReminderKind.T30,
    ReminderKind.T7,
    ReminderKind.POST30,
]


def late_by(kind: str, days: int) -> date:
    """The expiry date of a term whose ``kind`` reminder is ``days`` days overdue."""
    return ends_on_for(kind) - timedelta(days=days)


# ---------------------------------------------------------------------- window
@pytest.mark.parametrize("kind", CATCH_UP_KINDS)
@pytest.mark.parametrize("days", [1, 2])
def test_a_run_up_to_two_days_late_still_sends(annual_plan, mailoutbox, kind, days):
    make_member(annual_plan, late_by(kind, days))

    run = send_renewal_reminders(today=TODAY)

    assert run.sent_by_kind == {kind: 1}
    assert len(mailoutbox) == 1


@pytest.mark.parametrize("kind", CATCH_UP_KINDS)
def test_a_run_three_days_late_sends_nothing(annual_plan, mailoutbox, kind):
    make_member(annual_plan, late_by(kind, WINDOW_DAYS))

    run = send_renewal_reminders(today=TODAY)

    assert run.sent == 0
    assert mailoutbox == []


def test_expired_is_never_sent_late(annual_plan, mailoutbox):
    make_member(annual_plan, late_by(ReminderKind.EXPIRED, 1))

    run = send_renewal_reminders(today=TODAY)

    assert run.sent == 0
    assert mailoutbox == []


def test_a_missed_day_is_caught_up_the_next_day(annual_plan, mailoutbox):
    """The scan does not run on the day the cohort is due; the next one covers it."""
    make_member(annual_plan, ends_on_for(ReminderKind.T30))

    run = send_renewal_reminders(today=TODAY + timedelta(days=1))

    assert run.sent_by_kind == {ReminderKind.T30: 1}
    assert len(mailoutbox) == 1


def test_a_caught_up_reminder_is_logged_once(annual_plan, mailoutbox):
    make_member(annual_plan, ends_on_for(ReminderKind.T30))

    send_renewal_reminders(today=TODAY + timedelta(days=1))
    again = send_renewal_reminders(today=TODAY + timedelta(days=2))

    assert ReminderLog.objects.filter(kind=ReminderKind.T30).count() == 1
    assert again.skipped_by_reason == {"already_sent": 1}
