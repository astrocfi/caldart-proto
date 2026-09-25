"""The reminder scan when something goes wrong, or when a run is late.

One failed address does not stop the scan, a run that is late still catches
every member whose term is in a stage, a term that has left one stage is sent
the next rather than nothing, and a late email states the real number of days.
"""

from __future__ import annotations

import logging
import smtplib
from collections.abc import Sequence
from datetime import date, timedelta
from io import StringIO

import pytest
from django.core.mail import EmailMessage
from django.core.mail.backends.locmem import EmailBackend as LocMemEmailBackend
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError
from django.utils import timezone
from pytest_django.fixtures import Settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.mail.models import EmailLog, EmailStatus
from apps.members.models import MembershipPlan
from apps.reminders import services
from apps.reminders.models import ReminderKind, ReminderLog
from apps.reminders.services import KIND_ORDER, send_renewal_reminders
from tests.test_reminders import TODAY, ends_on_for, make_member

pytestmark = pytest.mark.django_db

#: Mail to this address fails when ``failing_smtp`` is in play.
FAILING_ADDRESS = "unreachable@example.test"

#: Every kind catches up after a missed run, because every kind is a stage
#: several days wide.
CATCH_UP_KINDS = list(KIND_ORDER)

RUN_URL = "/api/v1/system/reminders/run"


class OneAddressFailsBackend(LocMemEmailBackend):
    """A locmem backend whose server refuses mail to :data:`FAILING_ADDRESS`."""

    def send_messages(self, email_messages: Sequence[EmailMessage]) -> int:
        """Deliver the whole batch to the locmem outbox and return how many were sent.

        Raises ``smtplib.SMTPDataError`` as soon as a message in the batch names
        ``FAILING_ADDRESS`` as a recipient, before delivering any of them, so a batch
        holding such a message reaches the outbox in full or not at all.  The reminder
        scan sends one message per call, so only the failing recipient's own message
        is lost.
        """
        for message in email_messages:
            if FAILING_ADDRESS in message.to:
                raise smtplib.SMTPDataError(451, b"mailbox temporarily unavailable")
        return super().send_messages(email_messages)


def mailers_using(backend: str) -> dict[str, dict[str, str]]:
    """The ``MAILERS`` setting whose one mailer, ``default``, is ``backend``."""
    return {"default": {"BACKEND": backend}}


@pytest.fixture
def failing_smtp(settings: Settings, mailoutbox: list[EmailMessage]) -> list[EmailMessage]:
    """Deliver to the test outbox, except to :data:`FAILING_ADDRESS`."""
    settings.MAILERS = mailers_using(f"{__name__}.OneAddressFailsBackend")
    return mailoutbox


def late_by(kind: str, days: int) -> date:
    """The expiry date of a term whose ``kind`` reminder is ``days`` days overdue."""
    return ends_on_for(kind) - timedelta(days=days)


# -------------------------------------------------------------------- failures
def test_one_failing_recipient_does_not_stop_the_scan(
    annual_plan: MembershipPlan, failing_smtp: list[EmailMessage]
) -> None:
    """One address refusing delivery still lets the scan send to everyone else."""
    make_member(annual_plan, ends_on_for(ReminderKind.T30), email=FAILING_ADDRESS)
    make_member(annual_plan, ends_on_for(ReminderKind.T30), email="reachable@example.test")

    run = send_renewal_reminders(today=TODAY)

    assert run.failed == 1
    assert run.sent == 1
    assert [m.to[0] for m in failing_smtp] == ["reachable@example.test"]


def test_a_failure_is_counted_against_its_kind(
    annual_plan: MembershipPlan, failing_smtp: list[EmailMessage]
) -> None:
    """A failed send is tallied under the kind that failed, not as a send."""
    make_member(annual_plan, ends_on_for(ReminderKind.T7), email=FAILING_ADDRESS)

    run = send_renewal_reminders(today=TODAY)

    assert run.failed_by_kind == {ReminderKind.T7: 1}
    assert run.sent == 0


def test_a_failed_send_leaves_no_log_row(
    annual_plan: MembershipPlan, failing_smtp: list[EmailMessage]
) -> None:
    """A failed send writes no ``ReminderLog`` row, so a later run can retry it."""
    make_member(annual_plan, ends_on_for(ReminderKind.T30), email=FAILING_ADDRESS)

    send_renewal_reminders(today=TODAY)

    assert ReminderLog.objects.count() == 0


def test_a_failed_send_still_leaves_a_failed_email_log_row(
    annual_plan: MembershipPlan, failing_smtp: list[EmailMessage]
) -> None:
    """Deleting the ``ReminderLog`` row does not take the email log row with it."""
    make_member(annual_plan, ends_on_for(ReminderKind.T30), email=FAILING_ADDRESS)

    send_renewal_reminders(today=TODAY)

    row = EmailLog.objects.get(to_email=FAILING_ADDRESS)
    assert row.status == EmailStatus.FAILED
    assert row.purpose == f"reminder_{ReminderKind.T30}"


def test_an_abort_between_the_log_and_the_send_still_frees_the_reminder(
    annual_plan: MembershipPlan, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ``KeyboardInterrupt`` before the send still deletes the log row."""
    make_member(annual_plan, ends_on_for(ReminderKind.T30))

    def raise_keyboard_interrupt(*args: object, **kwargs: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(services, "send_reminder_email", raise_keyboard_interrupt)

    with pytest.raises(KeyboardInterrupt):
        send_renewal_reminders(today=TODAY)

    assert ReminderLog.objects.count() == 0


def test_a_failed_delete_does_not_replace_the_mail_failure_or_stop_the_scan(
    annual_plan: MembershipPlan, failing_smtp: list[EmailMessage], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ``DatabaseError`` deleting the log row masks neither the failure nor the scan."""
    make_member(annual_plan, ends_on_for(ReminderKind.T30), email=FAILING_ADDRESS)
    make_member(annual_plan, ends_on_for(ReminderKind.T30), email="reachable@example.test")

    def raise_database_error(self: ReminderLog, *args: object, **kwargs: object) -> None:
        raise DatabaseError("connection reset")

    monkeypatch.setattr(ReminderLog, "delete", raise_database_error)

    run = send_renewal_reminders(today=TODAY)

    assert run.failed == 1
    assert run.sent == 1


def test_the_failure_log_names_the_ids_but_no_address(
    annual_plan: MembershipPlan, failing_smtp: list[EmailMessage], caplog: pytest.LogCaptureFixture
) -> None:
    """A failed send logs one error naming the user and membership ids, no address."""
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


def test_a_failed_send_is_retried_the_next_day(
    annual_plan: MembershipPlan, failing_smtp: list[EmailMessage], settings: Settings
) -> None:
    """A term whose reminder failed is still in the catch-up window the next day."""
    make_member(annual_plan, ends_on_for(ReminderKind.T30), email=FAILING_ADDRESS)

    send_renewal_reminders(today=TODAY)
    settings.MAILERS = mailers_using("django.core.mail.backends.locmem.EmailBackend")
    run = send_renewal_reminders(today=TODAY + timedelta(days=1))

    assert run.sent == 1
    assert [m.to[0] for m in failing_smtp] == [FAILING_ADDRESS]


def test_a_failed_expired_send_is_retried_the_next_day(
    annual_plan: MembershipPlan, failing_smtp: list[EmailMessage], settings: Settings
) -> None:
    """The ``expired`` stage runs for a week, so the next run tries the address again."""
    make_member(annual_plan, ends_on_for(ReminderKind.EXPIRED), email=FAILING_ADDRESS)

    send_renewal_reminders(today=TODAY)
    settings.MAILERS = mailers_using("django.core.mail.backends.locmem.EmailBackend")
    run = send_renewal_reminders(today=TODAY + timedelta(days=1))

    assert run.sent == 1
    assert [m.to[0] for m in failing_smtp] == [FAILING_ADDRESS]


def test_a_failed_send_is_given_up_on_once_the_term_leaves_the_stage(
    annual_plan: MembershipPlan, failing_smtp: list[EmailMessage], settings: Settings
) -> None:
    """A week after the expiry day the term is past every stage but ``post30``."""
    make_member(annual_plan, ends_on_for(ReminderKind.EXPIRED), email=FAILING_ADDRESS)

    send_renewal_reminders(today=TODAY)
    settings.MAILERS = mailers_using("django.core.mail.backends.locmem.EmailBackend")
    run = send_renewal_reminders(today=TODAY + timedelta(days=7))

    assert run.sent == 0
    assert failing_smtp == []


def test_a_racing_run_counts_as_already_sent(
    annual_plan: MembershipPlan, mailoutbox: list[EmailMessage], monkeypatch: pytest.MonkeyPatch
) -> None:
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


def test_the_scan_carries_on_after_a_race(
    annual_plan: MembershipPlan, mailoutbox: list[EmailMessage], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A race on one membership does not stop the scan from sending to the next one."""
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
def test_a_run_up_to_two_days_late_still_sends(
    annual_plan: MembershipPlan, mailoutbox: list[EmailMessage], kind: str, days: int
) -> None:
    """A run one or two days late still sends to a cohort whose date has passed."""
    make_member(annual_plan, late_by(kind, days))

    run = send_renewal_reminders(today=TODAY)

    assert run.sent_by_kind == {kind: 1}
    assert len(mailoutbox) == 1


@pytest.mark.parametrize(
    ("kind", "days_late", "sent_kind"),
    [
        (ReminderKind.T60, 30, ReminderKind.T30),
        (ReminderKind.T30, 23, ReminderKind.T7),
        (ReminderKind.T7, 7, ReminderKind.EXPIRED),
        (ReminderKind.EXPIRED, 30, ReminderKind.POST30),
    ],
)
def test_a_run_late_enough_to_miss_a_stage_sends_the_next_one(
    annual_plan: MembershipPlan,
    mailoutbox: list[EmailMessage],
    kind: str,
    days_late: int,
    sent_kind: str,
) -> None:
    """A term that has run out of one stage is sent the stage it is in, not nothing."""
    make_member(annual_plan, late_by(kind, days_late))

    run = send_renewal_reminders(today=TODAY)

    assert run.sent_by_kind == {sent_kind: 1}


def test_a_run_a_month_after_the_last_stage_sends_nothing(
    annual_plan: MembershipPlan, mailoutbox: list[EmailMessage]
) -> None:
    """A term that lapsed more than sixty days ago is past every stage."""
    make_member(annual_plan, late_by(ReminderKind.POST30, 31))

    run = send_renewal_reminders(today=TODAY)

    assert run.sent == 0
    assert mailoutbox == []


def test_an_expired_reminder_missed_on_the_day_goes_out_the_next(
    annual_plan: MembershipPlan, mailoutbox: list[EmailMessage]
) -> None:
    """An ``expired`` reminder the timer missed is sent a day late, saying so."""
    make_member(annual_plan, late_by(ReminderKind.EXPIRED, 1))

    run = send_renewal_reminders(today=TODAY)

    assert run.sent_by_kind == {ReminderKind.EXPIRED: 1}
    assert mailoutbox[0].subject.endswith("your membership expired 1 day ago")


def test_a_missed_day_is_caught_up_the_next_day(
    annual_plan: MembershipPlan, mailoutbox: list[EmailMessage]
) -> None:
    """The scan does not run on the day the cohort is due; the next one covers it."""
    make_member(annual_plan, ends_on_for(ReminderKind.T30))

    run = send_renewal_reminders(today=TODAY + timedelta(days=1))

    assert run.sent_by_kind == {ReminderKind.T30: 1}
    assert len(mailoutbox) == 1


def test_a_caught_up_reminder_is_logged_once(
    annual_plan: MembershipPlan, mailoutbox: list[EmailMessage]
) -> None:
    """A cohort caught up a day late is not sent again by the next day's run."""
    make_member(annual_plan, ends_on_for(ReminderKind.T30))

    send_renewal_reminders(today=TODAY + timedelta(days=1))
    again = send_renewal_reminders(today=TODAY + timedelta(days=2))

    assert ReminderLog.objects.filter(kind=ReminderKind.T30).count() == 1
    assert again.skipped_by_reason == {"already_sent": 1}


# ------------------------------------------------------------------- day count
def test_a_late_subject_states_the_real_day_count(
    annual_plan: MembershipPlan, mailoutbox: list[EmailMessage]
) -> None:
    """A ``t30`` reminder sent two days late states 28 days, not the nominal 30."""
    make_member(annual_plan, late_by(ReminderKind.T30, 2))

    send_renewal_reminders(today=TODAY)

    assert mailoutbox[0].subject.endswith("your membership expires in 28 days")


def test_a_late_body_states_the_real_day_count(
    annual_plan: MembershipPlan, mailoutbox: list[EmailMessage]
) -> None:
    """A late reminder's body states the real day count, matching its subject."""
    make_member(annual_plan, late_by(ReminderKind.T30, 2))

    send_renewal_reminders(today=TODAY)

    assert "28 days" in mailoutbox[0].body


def test_a_late_post30_subject_states_the_real_day_count(
    annual_plan: MembershipPlan, mailoutbox: list[EmailMessage]
) -> None:
    """A ``post30`` reminder sent a day late states 31 days lapsed, not the nominal 30."""
    make_member(annual_plan, late_by(ReminderKind.POST30, 1))

    send_renewal_reminders(today=TODAY)

    assert mailoutbox[0].subject.endswith("your membership lapsed 31 days ago")


def test_an_on_time_subject_states_the_nominal_day_count(
    annual_plan: MembershipPlan, mailoutbox: list[EmailMessage]
) -> None:
    """A reminder sent exactly on its cohort's date states the kind's nominal offset."""
    make_member(annual_plan, ends_on_for(ReminderKind.T7))

    send_renewal_reminders(today=TODAY)

    assert mailoutbox[0].subject.endswith("your membership expires in 7 days")


# --------------------------------------------------------------------- command
def test_the_command_reports_failures_and_exits_non_zero(
    annual_plan: MembershipPlan, failing_smtp: list[EmailMessage]
) -> None:
    """The command raises ``CommandError`` and reports the count of failed sends."""
    make_member(
        annual_plan, ends_on_for(ReminderKind.T30, date(2026, 6, 15)), email=FAILING_ADDRESS
    )
    out = StringIO()

    with pytest.raises(CommandError, match="1 reminder could not be sent"):
        call_command("send_renewal_reminders", "--today=2026-06-15", stdout=out)

    assert "failed           1" in out.getvalue()


def test_the_command_still_succeeds_when_nothing_fails(
    annual_plan: MembershipPlan, mailoutbox: list[EmailMessage]
) -> None:
    """The command reports zero failures and does not raise when every send succeeds."""
    make_member(annual_plan, ends_on_for(ReminderKind.T30, date(2026, 6, 15)))
    out = StringIO()

    call_command("send_renewal_reminders", "--today=2026-06-15", stdout=out)

    assert "failed           0" in out.getvalue()


# -------------------------------------------------------------------- endpoint
def test_the_run_endpoint_still_returns_sent_and_skipped(
    api_client: APIClient,
    system_admin: User,
    annual_plan: MembershipPlan,
    failing_smtp: list[EmailMessage],
) -> None:
    """The run endpoint reports the failure beside the sent and skipped counts."""
    today = timezone.localdate()
    make_member(annual_plan, today + timedelta(days=30), email=FAILING_ADDRESS)
    api_client.force_login(system_admin)

    body = api_client.post(RUN_URL, {"dry_run": False}).json()

    assert body == {
        "sent": 0,
        "skipped": 0,
        "failed": 1,
        "skipped_by_reason": {},
        "actions": [],
    }
