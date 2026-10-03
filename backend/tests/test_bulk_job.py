"""The background sender: when it starts, how fast it goes, retries, stops, and resumes.

The mail server is the locmem backend, scripted where a test needs it to refuse, and
the pacing's clock and pause are replaced by a fake that only counts, so no test waits.
"""

from __future__ import annotations

import smtplib
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from django.core import mail
from django.core.mail import EmailMessage
from django.core.mail.backends.locmem import EmailBackend
from django.db import connection
from freezegun import freeze_time
from pytest_django import Settings
from rest_framework.test import APIClient

from apps.bulk_email import drafts, job
from apps.bulk_email.models import BulkEmail, BulkEmailStatus, RecipientStatus
from apps.mail.models import EmailLog
from tests.conftest import audit_messages
from tests.factories import BulkEmailFactory, add_to_batch, make_person

if TYPE_CHECKING:
    from apps.accounts.models import User

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 4, 6, 17, 0, tzinfo=UTC)

#: What the scripted mail server does with one message: send it, or raise.
type Outcome = Exception | None


@dataclass
class FakeClock:
    """The pacing's clock and pause: a pause moves the clock on and is recorded."""

    now: float = 0.0
    pauses: list[float] = field(default_factory=list)

    def sleep(self, seconds: float) -> None:
        """Record the pause and move the clock on by it."""
        self.pauses.append(seconds)
        self.now += seconds

    def monotonic(self) -> float:
        """The clock's reading."""
        return self.now


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> FakeClock:
    """Replace the sender's clock and pause with a fake one."""
    fake = FakeClock()
    monkeypatch.setattr(job, "sleep", fake.sleep)
    monkeypatch.setattr(job, "monotonic", fake.monotonic)
    return fake


@pytest.fixture
def script(monkeypatch: pytest.MonkeyPatch, clock: FakeClock) -> list[Outcome]:
    """A list of outcomes the mail server answers with, one per message, in order.

    Once the list is used up every message goes.  Each message that goes is kept in
    ``mail.outbox`` as usual.
    """
    outcomes: list[Outcome] = []
    original = EmailBackend.send_messages

    def send(self: EmailBackend, messages: list[EmailMessage]) -> int:
        if len(outcomes) > 0:
            outcome = outcomes.pop(0)
            if outcome is not None:
                raise outcome
        return original(self, messages)

    monkeypatch.setattr(EmailBackend, "send_messages", send)
    return outcomes


def temporary(code: int = 451) -> smtplib.SMTPResponseException:
    """A temporary refusal, such as ``451 try again later``."""
    return smtplib.SMTPResponseException(code, b"Try again later")


def permanent() -> smtplib.SMTPRecipientsRefused:
    """A permanent refusal: the server will not take the recipient."""
    return smtplib.SMTPRecipientsRefused({"x@example.test": (550, b"No such user")})


def queued_email(sender: User, *people: User, start_at: datetime = NOW) -> BulkEmail:
    """A queued email to ``people``, due at ``start_at``."""
    bulk = BulkEmailFactory(sender=sender, status=BulkEmailStatus.QUEUED, start_at=start_at)
    add_to_batch(bulk, *people)
    return bulk


@pytest.fixture
def three(management: User, clock: FakeClock) -> BulkEmail:
    """A queued email to Ann, Bea, and Cy, due now."""
    return queued_email(
        management,
        make_person("ann@example.test", "Ann", "Able"),
        make_person("bea@example.test", "Bea", "Bell"),
        make_person("cy@example.test", "Cy", "Cole"),
    )


def statuses(bulk: BulkEmail) -> list[tuple[str, str, str]]:
    """Each row's address, status, and reason, in send order."""
    return [
        (row.email, row.status, row.reason) for row in bulk.recipients.order_by("user__last_name")
    ]


def refreshed(bulk: BulkEmail) -> BulkEmail:
    """``bulk`` read afresh."""
    bulk.refresh_from_db()
    return bulk


# --------------------------------------------------------------------------
# When the send starts
# --------------------------------------------------------------------------
def test_nothing_is_sent_before_the_start(management: User, clock: FakeClock) -> None:
    """A queued email waits for its ``start_at``."""
    queued_email(management, make_person("ann@example.test"), start_at=NOW)
    job.run_sender(now=NOW - timedelta(seconds=1))
    assert len(mail.outbox) == 0


def test_the_send_begins_at_the_start(management: User, clock: FakeClock) -> None:
    """At ``start_at`` the email is sent."""
    bulk = queued_email(management, make_person("ann@example.test"), start_at=NOW)
    job.run_sender(now=NOW)
    assert (refreshed(bulk).status, len(mail.outbox)) == (BulkEmailStatus.SENT, 1)


def test_the_undo_window_holds_the_send_back(
    management: User, clock: FakeClock, settings: Settings
) -> None:
    """Under a frozen clock, a send queued now goes out once the window has passed."""
    settings.BULK_EMAIL_UNDO_SECONDS = 120
    bulk = BulkEmailFactory(sender=management)
    add_to_batch(bulk, make_person("ann@example.test"))
    with freeze_time(NOW):
        drafts.queue(bulk, confirm_count=None, start_at=None, actor=management)
    with freeze_time(NOW + timedelta(seconds=119)):
        job.run_sender()
    sent_early = len(mail.outbox)
    with freeze_time(NOW + timedelta(seconds=120)):
        job.run_sender()
    assert (sent_early, len(mail.outbox)) == (0, 1)


def test_a_scheduled_email_sends_at_its_time_and_not_before(
    management: User, clock: FakeClock
) -> None:
    """A schedule two days ahead is not sent the day before."""
    bulk = BulkEmailFactory(sender=management)
    add_to_batch(bulk, make_person("ann@example.test"))
    start = NOW + timedelta(days=2)
    drafts.queue(bulk, confirm_count=None, start_at=start, actor=management, now=NOW)
    job.run_sender(now=start - timedelta(days=1))
    early = refreshed(bulk).status
    job.run_sender(now=start)
    assert (early, refreshed(bulk).status) == (BulkEmailStatus.QUEUED, BulkEmailStatus.SENT)


def test_an_edit_before_the_start_is_what_goes_out(management: User, clock: FakeClock) -> None:
    """The subject fixed after scheduling is the one sent."""
    bulk = BulkEmailFactory(sender=management)
    add_to_batch(bulk, make_person("ann@example.test"))
    drafts.queue(
        bulk, confirm_count=None, start_at=NOW + timedelta(days=1), actor=management, now=NOW
    )
    drafts.update(bulk, {"subject": "Corrected subject"})
    job.run_sender(now=NOW + timedelta(days=1))
    assert mail.outbox[0].subject == "Corrected subject"


def test_starting_records_when_and_freezes_the_batch(three: BulkEmail) -> None:
    """``started_at`` is set and no row is left ``batched``."""
    with freeze_time(NOW):
        job.run_sender()
    bulk = refreshed(three)
    assert (
        bulk.started_at,
        bulk.recipients.filter(status=RecipientStatus.BATCHED).count(),
    ) == (NOW, 0)


def test_a_skip_is_counted_as_the_send_starts(management: User, clock: FakeClock) -> None:
    """A deactivated person is skipped and counted."""
    bulk = queued_email(
        management,
        make_person("ann@example.test", "Ann", "Able"),
        make_person("gil@example.test", "Gil", "Gone", is_active=False),
    )
    job.run_sender(now=NOW)
    assert (refreshed(bulk).skipped_count, statuses(bulk)) == (
        1,
        [
            ("ann@example.test", RecipientStatus.SENT, ""),
            ("gil@example.test", RecipientStatus.SKIPPED, "Account deactivated"),
        ],
    )


# --------------------------------------------------------------------------
# The copies
# --------------------------------------------------------------------------
def test_every_copy_goes_in_surname_order(three: BulkEmail) -> None:
    """One copy to each person, Able before Bell before Cole."""
    job.run_sender(now=NOW)
    assert [message.to[0] for message in mail.outbox] == [
        "ann@example.test",
        "bea@example.test",
        "cy@example.test",
    ]


def test_a_copy_carries_the_subject_and_the_message(three: BulkEmail) -> None:
    """The plain-text body is the message followed by the footer."""
    job.run_sender(now=NOW)
    message = mail.outbox[0]
    assert (message.subject, str(message.body).startswith(three.body)) == (three.subject, True)


def test_the_html_body_makes_each_paragraph_a_paragraph(three: BulkEmail) -> None:
    """Each blank-line paragraph of the message is a ``<p>`` in the HTML body."""
    job.run_sender(now=NOW)
    html = str(mail.outbox[0].alternatives[0].content)  # type: ignore[attr-defined]
    assert "<p>Join us at Livermore on Saturday.</p>" in html


def test_each_row_keeps_the_message_id_of_its_copy(three: BulkEmail) -> None:
    """The row's ``message_id`` is the header the copy went with, as the log has it."""
    job.run_sender(now=NOW)
    row = three.recipients.get(email="ann@example.test")
    log = EmailLog.objects.get(to_email="ann@example.test")
    assert (row.message_id, row.message_id == log.message_id) == (
        mail.outbox[0].extra_headers["Message-ID"],
        True,
    )


def test_every_copy_is_in_the_email_log_as_a_bulk_email(three: BulkEmail) -> None:
    """The email log records each copy under the purpose ``bulk_email``."""
    job.run_sender(now=NOW)
    assert set(EmailLog.objects.values_list("purpose", flat=True)) == {"bulk_email"}


def test_each_row_records_when_it_was_tried(three: BulkEmail) -> None:
    """``tried_at`` is the moment the copy was tried."""
    with freeze_time(NOW):
        job.run_sender()
    assert set(three.recipients.values_list("tried_at", flat=True)) == {NOW}


def test_the_send_writes_one_audit_line(
    three: BulkEmail, management: User, audit_log: pytest.LogCaptureFixture
) -> None:
    """``bulk_email.send`` names the sender, the email, and the counts."""
    job.run_sender(now=NOW)
    assert audit_messages(audit_log) == [
        f"action=bulk_email.send actor={management.pk} target={three.pk} sent=3 skipped=0 failed=0"
    ]


def test_the_run_reports_each_copy(three: BulkEmail) -> None:
    """The run's summary counts the copies and names each."""
    run = job.run_sender(now=NOW)
    assert (run.emails, run.sent, [action.email for action in run.actions]) == (
        1,
        3,
        ["ann@example.test", "bea@example.test", "cy@example.test"],
    )


# --------------------------------------------------------------------------
# Pacing and connections
# --------------------------------------------------------------------------
def test_the_copies_are_paced_to_the_rate(
    three: BulkEmail, clock: FakeClock, settings: Settings
) -> None:
    """At 30 a minute each copy after the first waits two seconds."""
    settings.BULK_EMAIL_RATE_PER_MINUTE = 30
    job.run_sender(now=NOW)
    assert clock.pauses == [2.0, 2.0]


def test_a_slow_server_shortens_the_wait(
    three: BulkEmail, clock: FakeClock, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Time a copy took counts against the interval, so the rate is a ceiling."""
    settings.BULK_EMAIL_RATE_PER_MINUTE = 30
    original = EmailBackend.send_messages

    def slow(self: EmailBackend, messages: list[EmailMessage]) -> int:
        clock.now += 0.5
        return original(self, messages)

    monkeypatch.setattr(EmailBackend, "send_messages", slow)
    job.run_sender(now=NOW)
    assert clock.pauses == [1.5, 1.5]


def test_a_fresh_connection_is_opened_every_batch(
    three: BulkEmail, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With two copies per connection, three copies open two connections."""
    settings.BULK_EMAIL_BATCH_SIZE = 2
    opened: list[int] = []
    original = EmailBackend.open

    def count_open(self: EmailBackend) -> bool | None:
        opened.append(id(self))
        return original(self)

    monkeypatch.setattr(EmailBackend, "open", count_open)
    job.run_sender(now=NOW)
    assert len(opened) == 2


# --------------------------------------------------------------------------
# Refusals
# --------------------------------------------------------------------------
def test_a_temporary_refusal_is_retried_and_then_succeeds(
    three: BulkEmail, script: list[Outcome], clock: FakeClock, settings: Settings
) -> None:
    """A 451 is tried again after five seconds, and the copy goes."""
    settings.BULK_EMAIL_RATE_PER_MINUTE = 6000
    script.append(temporary(451))
    job.run_sender(now=NOW)
    assert (statuses(three)[0], clock.pauses[0]) == (
        ("ann@example.test", RecipientStatus.SENT, ""),
        5,
    )


def test_a_temporary_refusal_gives_up_after_three_retries(
    three: BulkEmail, script: list[Outcome], clock: FakeClock, settings: Settings
) -> None:
    """Four 421s in a row fail the copy, after waits of 5, 15, and 45 seconds."""
    settings.BULK_EMAIL_RATE_PER_MINUTE = 6000
    script.extend([temporary(421) for _ in range(4)])
    job.run_sender(now=NOW)
    assert (statuses(three)[0], [pause for pause in clock.pauses if pause >= 5]) == (
        ("ann@example.test", RecipientStatus.FAILED, job.GAVE_UP_REASON),
        [5, 15, 45],
    )


def test_a_permanent_refusal_is_not_retried(
    three: BulkEmail, script: list[Outcome], clock: FakeClock, settings: Settings
) -> None:
    """A 550 fails the copy at once, with no retry, and the rest still go."""
    settings.BULK_EMAIL_RATE_PER_MINUTE = 6000
    script.append(permanent())
    job.run_sender(now=NOW)
    assert (statuses(three), [pause for pause in clock.pauses if pause >= 5]) == (
        [
            ("ann@example.test", RecipientStatus.FAILED, job.FAILED_REASON),
            ("bea@example.test", RecipientStatus.SENT, ""),
            ("cy@example.test", RecipientStatus.SENT, ""),
        ],
        [],
    )


def test_a_failed_copy_is_counted(three: BulkEmail, script: list[Outcome]) -> None:
    """The counts say one failed and two went."""
    script.append(permanent())
    job.run_sender(now=NOW)
    bulk = refreshed(three)
    assert (bulk.sent_count, bulk.failed_count, bulk.status) == (2, 1, BulkEmailStatus.SENT)


# --------------------------------------------------------------------------
# Stopping and resuming
# --------------------------------------------------------------------------
@pytest.fixture
def stop_after_first(three: BulkEmail, management: User, monkeypatch: pytest.MonkeyPatch) -> None:
    """Press **Stop** on ``three`` while its first copy is going out."""
    original = EmailBackend.send_messages
    pressed: list[bool] = []

    def send(self: EmailBackend, messages: list[EmailMessage]) -> int:
        if not pressed:
            pressed.append(True)
            drafts.stop(three, actor=management)
        return original(self, messages)

    monkeypatch.setattr(EmailBackend, "send_messages", send)


def test_stopping_part_way_leaves_the_right_statuses(
    three: BulkEmail, stop_after_first: None
) -> None:
    """The copy in flight went; the rest are not sent, naming who stopped them."""
    job.run_sender(now=NOW)
    assert statuses(three) == [
        ("ann@example.test", RecipientStatus.SENT, ""),
        ("bea@example.test", RecipientStatus.STOPPED, "Stopped by Hollis Grant"),
        ("cy@example.test", RecipientStatus.STOPPED, "Stopped by Hollis Grant"),
    ]


def test_a_stopped_email_records_who_and_when(
    three: BulkEmail, management: User, stop_after_first: None
) -> None:
    """The email is ``stopped`` with the time and the account."""
    with freeze_time(NOW):
        job.run_sender()
    bulk = refreshed(three)
    assert (bulk.status, bulk.stopped_at, bulk.stopped_by) == (
        BulkEmailStatus.STOPPED,
        NOW,
        management,
    )


def test_stop_is_refused_when_the_email_is_not_sending(
    management_client: APIClient, three: BulkEmail
) -> None:
    """A queued email is cancelled, not stopped: a 409 says it is not sending."""
    response = management_client.post(f"/api/v1/bulk-email/{three.pk}/stop")
    assert (response.status_code, response.json()) == (409, {"detail": drafts.NOT_SENDING_MESSAGE})


def test_send_the_rest_sends_only_the_copies_a_stop_left(
    three: BulkEmail, management: User, stop_after_first: None
) -> None:
    """After **Send the rest**, Bea and Cy are sent; Ann is not sent a second copy."""
    job.run_sender(now=NOW)
    drafts.resume(three, actor=management, now=NOW)
    job.run_sender(now=NOW)
    bulk = refreshed(three)
    assert (
        [message.to[0] for message in mail.outbox],
        bulk.status,
        bulk.sent_count,
    ) == (
        ["ann@example.test", "bea@example.test", "cy@example.test"],
        BulkEmailStatus.SENT,
        3,
    )


def test_send_the_rest_starts_at_once(
    three: BulkEmail, management: User, stop_after_first: None, settings: Settings
) -> None:
    """There is no undo window on **Send the rest**."""
    settings.BULK_EMAIL_UNDO_SECONDS = 120
    job.run_sender(now=NOW)
    resumed = drafts.resume(three, actor=management, now=NOW)
    assert (resumed.status, resumed.start_at) == (BulkEmailStatus.QUEUED, NOW)


def test_send_the_rest_is_refused_unless_the_email_was_stopped(
    management_client: APIClient, three: BulkEmail
) -> None:
    """Only a stopped email has a rest to send."""
    response = management_client.post(f"/api/v1/bulk-email/{three.pk}/resume")
    assert (response.status_code, response.json()) == (409, {"detail": drafts.NOT_STOPPED_MESSAGE})


# --------------------------------------------------------------------------
# A run that stopped part way
# --------------------------------------------------------------------------
def test_a_crashed_send_is_resumed_with_only_its_pending_copies(
    three: BulkEmail, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A run that died after one copy leaves the rest pending; the next run sends them."""
    original = EmailBackend.send_messages
    calls: list[int] = []

    def crash_on_second(self: EmailBackend, messages: list[EmailMessage]) -> int:
        calls.append(1)
        if len(calls) == 2:
            raise KeyboardInterrupt
        return original(self, messages)

    monkeypatch.setattr(EmailBackend, "send_messages", crash_on_second)
    with pytest.raises(KeyboardInterrupt):
        job.run_sender(now=NOW)
    monkeypatch.setattr(EmailBackend, "send_messages", original)
    job.run_sender(now=NOW)
    assert (
        [message.to[0] for message in mail.outbox],
        refreshed(three).status,
    ) == (
        ["ann@example.test", "bea@example.test", "cy@example.test"],
        BulkEmailStatus.SENT,
    )


@pytest.fixture
def another_run_working() -> Iterator[None]:
    """Hold the sender's lock from a second database session, as a run at work does."""
    second = connection.copy()
    try:
        with second.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_lock(%s)", [job.SENDER_LOCK_KEY])
        yield
    finally:
        # Closing the session releases its lock.
        second.close()


def test_a_run_while_another_works_does_nothing(
    three: BulkEmail, another_run_working: None
) -> None:
    """The sender's lock keeps two runs from sending the same copies."""
    run = job.run_sender(now=NOW)
    assert (run.busy, len(mail.outbox), refreshed(three).status) == (
        True,
        0,
        BulkEmailStatus.QUEUED,
    )


# --------------------------------------------------------------------------
# Progress
# --------------------------------------------------------------------------
def test_the_detail_reports_progress_while_sending(
    management_client: APIClient, three: BulkEmail, settings: Settings
) -> None:
    """Sent, failed, remaining, and the finish estimated at the rate."""
    settings.BULK_EMAIL_RATE_PER_MINUTE = 30
    BulkEmail.objects.filter(pk=three.pk).update(
        status=BulkEmailStatus.SENDING, sent_count=1, failed_count=0
    )
    three.recipients.filter(email="ann@example.test").update(status=RecipientStatus.SENT)
    three.recipients.exclude(email="ann@example.test").update(status=RecipientStatus.PENDING)
    with freeze_time(NOW):
        body = management_client.get(f"/api/v1/bulk-email/{three.pk}").json()
    assert (
        body["sent_count"],
        body["failed_count"],
        body["remaining"],
        body["estimated_finish_at"],
    ) == (1, 0, 2, "2026-04-06T10:00:04-07:00")


def test_no_finish_is_estimated_once_the_send_is_over(
    management_client: APIClient, three: BulkEmail
) -> None:
    """A sent email has nothing left to estimate."""
    job.run_sender(now=NOW)
    assert (
        management_client.get(f"/api/v1/bulk-email/{three.pk}").json()["estimated_finish_at"]
        is None
    )
