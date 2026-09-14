"""The reminder scan when something goes wrong, or when a run is late.

One failed address does not stop the scan, a run that is up to two days late
still catches its cohorts, ``expired`` is never sent late, and a late email
states the real number of days.
"""

from __future__ import annotations

import logging
import smtplib
from datetime import date, timedelta
from io import StringIO

import pytest
from django.core.mail import EmailMessage
from django.core.mail.backends.locmem import EmailBackend as LocMemEmailBackend
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from apps.reminders import services
from apps.reminders.models import ReminderKind, ReminderLog
from apps.reminders.services import WINDOW_DAYS, send_renewal_reminders
from tests.test_reminders import TODAY, ends_on_for, make_member

pytestmark = pytest.mark.django_db

#: Mail to this address fails when ``failing_smtp`` is in play.
FAILING_ADDRESS = "unreachable@example.test"

#: The kinds that catch up after a missed run; ``expired`` never does.
CATCH_UP_KINDS = [
    ReminderKind.T60,
    ReminderKind.T30,
    ReminderKind.T7,
    ReminderKind.POST30,
]

RUN_URL = "/api/v1/system/reminders/run"


class OneAddressFailsBackend(LocMemEmailBackend):
    """A locmem backend whose server refuses mail to :data:`FAILING_ADDRESS`."""

    def send_messages(self, email_messages: list[EmailMessage]) -> int:
        for message in email_messages:
            if FAILING_ADDRESS in message.to:
                raise smtplib.SMTPDataError(451, b"mailbox temporarily unavailable")
        return super().send_messages(email_messages)


@pytest.fixture
def failing_smtp(settings, mailoutbox):
    """Deliver to the test outbox, except to :data:`FAILING_ADDRESS`."""
    settings.EMAIL_BACKEND = f"{__name__}.OneAddressFailsBackend"
    return mailoutbox


def late_by(kind: str, days: int) -> date:
    """The expiry date of a term whose ``kind`` reminder is ``days`` days overdue."""
    return ends_on_for(kind) - timedelta(days=days)


# -------------------------------------------------------------------- failures
def test_one_failing_recipient_does_not_stop_the_scan(annual_plan, failing_smtp):
    make_member(annual_plan, ends_on_for(ReminderKind.T30), email=FAILING_ADDRESS)
    make_member(annual_plan, ends_on_for(ReminderKind.T30), email="reachable@example.test")

    run = send_renewal_reminders(today=TODAY)

    assert run.failed == 1
    assert run.sent == 1
    assert [m.to[0] for m in failing_smtp] == ["reachable@example.test"]


def test_a_failure_is_counted_against_its_kind(annual_plan, failing_smtp):
    make_member(annual_plan, ends_on_for(ReminderKind.T7), email=FAILING_ADDRESS)

    run = send_renewal_reminders(today=TODAY)

    assert run.failed_by_kind == {ReminderKind.T7: 1}
    assert run.sent == 0


def test_a_failed_send_leaves_no_log_row(annual_plan, failing_smtp):
    make_member(annual_plan, ends_on_for(ReminderKind.T30), email=FAILING_ADDRESS)

    send_renewal_reminders(today=TODAY)

    assert ReminderLog.objects.count() == 0


def test_the_failure_log_names_the_ids_but_no_address(annual_plan, failing_smtp, caplog):
    user, membership = make_member(
        annual_plan, ends_on_for(ReminderKind.T30), email=FAILING_ADDRESS
    )

    with caplog.at_level(logging.ERROR, logger="apps.reminders.services"):
        send_renewal_reminders(today=TODAY)

    errors = [record for record in caplog.records if record.levelno == logging.ERROR]
    assert len(errors) == 1
    message = errors[0].getMessage()
    assert FAILING_ADDRESS not in message
    assert f"user={user.pk}" in message
    assert f"membership={membership.pk}" in message
    assert "SMTPDataError" in message


def test_a_failed_send_is_retried_the_next_day(annual_plan, failing_smtp, settings):
    make_member(annual_plan, ends_on_for(ReminderKind.T30), email=FAILING_ADDRESS)

    send_renewal_reminders(today=TODAY)
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    run = send_renewal_reminders(today=TODAY + timedelta(days=1))

    assert run.sent == 1
    assert [m.to[0] for m in failing_smtp] == [FAILING_ADDRESS]


def test_a_racing_run_counts_as_already_sent(annual_plan, mailoutbox, monkeypatch):
    """A log row written between the skip check and the insert is not a failure."""
    user, membership = make_member(annual_plan, ends_on_for(ReminderKind.T30))
    ReminderLog.objects.create(
        user=user,
        membership=membership,
        kind=ReminderKind.T30,
        sent_at=timezone.now(),
        to_email=user.email,
    )
    monkeypatch.setattr(services, "_skip_reason", lambda *args, **kwargs: None)

    run = send_renewal_reminders(today=TODAY)

    assert run.skipped_by_reason == {"already_sent": 1}
    assert run.failed == 0
    assert mailoutbox == []


def test_the_scan_carries_on_after_a_race(annual_plan, mailoutbox, monkeypatch):
    racing, membership = make_member(annual_plan, ends_on_for(ReminderKind.T30))
    ReminderLog.objects.create(
        user=racing,
        membership=membership,
        kind=ReminderKind.T30,
        sent_at=timezone.now(),
        to_email=racing.email,
    )
    make_member(annual_plan, ends_on_for(ReminderKind.T7), email="week@example.test")
    monkeypatch.setattr(services, "_skip_reason", lambda *args, **kwargs: None)

    run = send_renewal_reminders(today=TODAY)

    assert run.sent_by_kind == {ReminderKind.T7: 1}
    assert [m.to[0] for m in mailoutbox] == ["week@example.test"]


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


# ------------------------------------------------------------------- day count
def test_a_late_subject_states_the_real_day_count(annual_plan, mailoutbox):
    make_member(annual_plan, late_by(ReminderKind.T30, 2))

    send_renewal_reminders(today=TODAY)

    assert mailoutbox[0].subject.endswith("your membership expires in 28 days")


def test_a_late_body_states_the_real_day_count(annual_plan, mailoutbox):
    make_member(annual_plan, late_by(ReminderKind.T30, 2))

    send_renewal_reminders(today=TODAY)

    assert "28 days" in mailoutbox[0].body


def test_a_late_post30_subject_states_the_real_day_count(annual_plan, mailoutbox):
    make_member(annual_plan, late_by(ReminderKind.POST30, 1))

    send_renewal_reminders(today=TODAY)

    assert mailoutbox[0].subject.endswith("your membership lapsed 31 days ago")


def test_an_on_time_subject_states_the_nominal_day_count(annual_plan, mailoutbox):
    make_member(annual_plan, ends_on_for(ReminderKind.T7))

    send_renewal_reminders(today=TODAY)

    assert mailoutbox[0].subject.endswith("your membership expires in 7 days")


# --------------------------------------------------------------------- command
def test_the_command_reports_failures_and_exits_non_zero(annual_plan, failing_smtp):
    make_member(
        annual_plan, ends_on_for(ReminderKind.T30, date(2026, 6, 15)), email=FAILING_ADDRESS
    )
    out = StringIO()

    with pytest.raises(CommandError, match="1 reminder could not be sent"):
        call_command("send_renewal_reminders", "--today=2026-06-15", stdout=out)

    assert "failed           1" in out.getvalue()


def test_the_command_still_succeeds_when_nothing_fails(annual_plan, mailoutbox):
    make_member(annual_plan, ends_on_for(ReminderKind.T30, date(2026, 6, 15)))
    out = StringIO()

    call_command("send_renewal_reminders", "--today=2026-06-15", stdout=out)

    assert "failed           0" in out.getvalue()


# -------------------------------------------------------------------- endpoint
def test_the_run_endpoint_still_returns_sent_and_skipped(
    api_client, system_admin, annual_plan, failing_smtp
):
    today = timezone.localdate()
    make_member(annual_plan, today + timedelta(days=30), email=FAILING_ADDRESS)
    api_client.force_login(system_admin)

    body = api_client.post(RUN_URL, {"dry_run": False}).json()

    assert body == {"sent": 0, "skipped": 0}
