"""The background sender: it starts each queued bulk email and sends its copies.

:func:`run_sender` is what ``manage.py send_bulk_emails`` runs every minute, from
``caldart-bulk-email.timer``, and what **Run now** on the Scheduled page runs once.  A
run first finishes any email still ``sending`` from an earlier run that stopped part way
(a crash, or a machine that went down), then claims each ``queued`` email whose
``start_at`` has arrived, one at a time.

Claiming an email takes its row with ``select_for_update(skip_locked=True)`` in one
short transaction that sets it ``sending`` and freezes its batch: each ``batched`` row
becomes ``pending``, or ``skipped`` with the reason
(:func:`apps.bulk_email.batch.skip_reason`) as of that moment, and takes the account's
name and address as they are then.  The pending rows are then sent in surname order,
one copy each, through ``caldart.mail.send_templated``, saving each row and the email's
counts as soon as that copy has been tried.  When no row is pending the email is
``sent``, and one ``bulk_email.send`` audit line is written.

The sender paces itself to ``BULK_EMAIL_RATE_PER_MINUTE`` copies a minute and opens a
fresh mail connection every ``BULK_EMAIL_BATCH_SIZE`` copies.  A temporary refusal
(:data:`TEMPORARY_CODES`) is tried again after each of :data:`RETRY_DELAYS` seconds; any
other refusal fails the copy at once.  Between copies it reads ``stop_requested``, set
by **Stop**: every copy not yet sent is then ``stopped`` and the email too.

Only one run works at a time: a run holds a database advisory lock for as long as it
works, and a second run that cannot take it does nothing.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.core.mail import mailers
from django.core.mail.backends.base import BaseEmailBackend
from django.db import connection, transaction
from django.utils import timezone

from apps.bulk_email.batch import batch_rows, snapshot, surname_order
from apps.bulk_email.models import (
    BulkEmail,
    BulkEmailRecipient,
    BulkEmailStatus,
    RecipientStatus,
)
from apps.bulk_email.render import COPY_TEMPLATE, PURPOSE, render_copy
from caldart import audit
from caldart.mail import MailRefusedError, error_name, send_templated
from caldart.runs import RunAction

log = logging.getLogger(__name__)

#: The SMTP reply codes of a temporary refusal, which are worth trying again: the
#: server is busy, a mailbox is briefly unavailable, or storage is short.
TEMPORARY_CODES: frozenset[int] = frozenset({421, 450, 451, 452})

#: The seconds waited before each retry of a temporarily refused copy.
RETRY_DELAYS: tuple[int, ...] = (5, 15, 45)

#: Why a copy failed.
FAILED_REASON = "Refused by the mail server"
GAVE_UP_REASON = f"Temporarily refused, gave up after {len(RETRY_DELAYS)} retries"

#: Who a stop names when the account that pressed **Stop** is gone.
UNKNOWN_STOPPER = "a deleted account"

#: What the transport raises when it cannot open a connection.
CONNECTION_ERRORS: tuple[type[Exception], ...] = (OSError,)

#: The advisory lock key only one run of the sender holds at a time.
SENDER_LOCK_KEY = 0x0B01_E3A1

#: What a run that found another run working says.
BUSY_MESSAGE = "Another run of the bulk email sender is working; this one did nothing."

#: The longest reason a recipient row holds.
REASON_MAX_LENGTH = 200

# The clock and the pause the pacing reads, named here so a test can replace them.
sleep: Callable[[float], None] = time.sleep
monotonic: Callable[[], float] = time.monotonic


@dataclass
class SenderRun:
    """What one run of the sender did.

    ``busy`` is true when another run held the lock and this one did nothing.
    ``emails`` counts the bulk emails it worked on; ``sent`` and ``failed`` the copies
    it tried, and ``skipped`` the people it set aside when it started an email.
    ``actions`` holds one :class:`~caldart.runs.RunAction` per copy tried, whose
    ``kind`` is ``sent`` or ``failed`` and whose ``detail`` is the subject or the
    reason.
    """

    busy: bool = False
    emails: int = 0
    sent: int = 0
    failed: int = 0
    skipped: int = 0
    actions: list[RunAction] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        """The counts and the actions ``POST /system/bulk-email/run`` answers with."""
        return {
            "busy": self.busy,
            "emails": self.emails,
            "sent": self.sent,
            "failed": self.failed,
            "skipped": self.skipped,
            "actions": [action.as_dict() for action in self.actions],
        }

    def as_lines(self) -> list[str]:
        """The run as printable lines: the counts, then one line per copy tried."""
        if self.busy:
            return [BUSY_MESSAGE]
        lines = [
            f"emails           {self.emails}",
            f"sent             {self.sent}",
            f"failed           {self.failed}",
            f"skipped          {self.skipped}",
        ]
        return lines + [
            f"{action.kind} {action.member} <{action.email}> ({action.detail})"
            for action in self.actions
        ]


@dataclass(frozen=True)
class _Attempt:
    """What became of one copy: its status, the reason, and the ``Message-ID`` it had."""

    status: RecipientStatus
    reason: str = ""
    message_id: str = ""


def run_sender(now: datetime | None = None) -> SenderRun:
    """Finish every email left ``sending``, then start every one whose time has come.

    ``now`` is the moment a queued email's ``start_at`` is compared with, the current
    time unless given.  Returns what the run did; a run that finds another run working
    returns at once with ``busy`` set and does nothing.
    """
    moment = now if now is not None else timezone.now()
    run = SenderRun()
    with _sender_lock() as is_held:
        if not is_held:
            log.info("bulk email sender busy: another run holds the lock")
            run.busy = True
            return run
        for unfinished in BulkEmail.objects.filter(status=BulkEmailStatus.SENDING).order_by(
            "started_at", "pk"
        ):
            _send(unfinished, run)
        while (claimed := _claim(moment, run)) is not None:
            _send(claimed, run)
    return run


def estimated_finish(remaining: int, now: datetime) -> datetime:
    """When ``remaining`` copies will have gone at ``BULK_EMAIL_RATE_PER_MINUTE``."""
    return now + _interval_delta(remaining)


@contextmanager
def _sender_lock() -> Iterator[bool]:
    """Hold the sender's advisory lock while the block runs; yield whether it was taken.

    The lock belongs to the database session, so it is released however the block
    ends, and also if the process dies.
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", [SENDER_LOCK_KEY])
        row = cursor.fetchone()
    is_held = row is not None and bool(row[0])
    try:
        yield is_held
    finally:
        if is_held:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [SENDER_LOCK_KEY])


def _claim(now: datetime, run: SenderRun) -> BulkEmail | None:
    """Take the next queued email whose time has come, start it, and freeze its batch.

    Returns ``None`` when no queued email is due.  An email another transaction holds,
    such as one whose batch is being changed this instant, is left for the next run.
    """
    with transaction.atomic():
        bulk = (
            BulkEmail.objects.select_for_update(skip_locked=True)
            .filter(status=BulkEmailStatus.QUEUED, start_at__lte=now)
            .order_by("start_at", "pk")
            .first()
        )
        if bulk is None:
            return None
        bulk.status = BulkEmailStatus.SENDING
        if bulk.started_at is None:
            bulk.started_at = timezone.now()
        run.skipped += _freeze(bulk)
        bulk.save(update_fields=["status", "started_at", "skipped_count", "updated_at"])
    return bulk


def _freeze(bulk: BulkEmail) -> int:
    """Settle who ``bulk`` goes to, now; return how many were set aside.

    Each ``batched`` row takes its account's name, address, kind, and DART as they are
    now, and becomes ``pending``, or ``skipped`` with the reason the batch gives it at
    this moment.  Rows already past ``batched``, such as the copies **Send the rest**
    queued again, are left as they are.  ``skipped_count`` grows by the number set
    aside; the caller saves the email.
    """
    moment = timezone.now()
    frozen: list[BulkEmailRecipient] = []
    skipped = 0
    for row in batch_rows(bulk):
        recipient = row.recipient
        if recipient.status != RecipientStatus.BATCHED:
            continue
        if row.account is not None:
            snapshot(recipient, row.account)
        recipient.reason = row.reason
        recipient.status = RecipientStatus.PENDING if row.will_receive else RecipientStatus.SKIPPED
        recipient.updated_at = moment
        skipped += 0 if row.will_receive else 1
        frozen.append(recipient)
    BulkEmailRecipient.objects.bulk_update(
        frozen, ["status", "reason", "name", "email", "kind", "dart_name", "updated_at"]
    )
    bulk.skipped_count += skipped
    return skipped


def _send(bulk: BulkEmail, run: SenderRun) -> None:
    """Send every pending copy of ``bulk``, paced, then mark it sent or stopped."""
    run.emails += 1
    rows = list(
        surname_order(bulk.recipients.filter(status=RecipientStatus.PENDING)).select_related("user")
    )
    mailer = mailers.default
    # The number of copies tried over the open connection; None while none is open.
    on_connection: int | None = None
    last_start: float | None = None
    try:
        for row in rows:
            if _is_stop_requested(bulk):
                _stop(bulk)
                return
            last_start = _pace(last_start)
            if on_connection is None or on_connection >= settings.BULK_EMAIL_BATCH_SIZE:
                mailer.close()
                _open(mailer, bulk)
                on_connection = 0
            attempt = _try_copy(bulk, row, mailer)
            # A failed copy closed the connection, so the next one opens a fresh one.
            on_connection = None if attempt.status == RecipientStatus.FAILED else on_connection + 1
            _record(bulk, row, attempt, run)
    finally:
        mailer.close()
    _finish(bulk)


def _pace(last_start: float | None) -> float:
    """Wait out the rest of the interval since the last copy began; return now.

    The interval is 60 seconds over ``BULK_EMAIL_RATE_PER_MINUTE``, so the copies go
    no faster than that rate however quickly the mail server answers.  The first copy
    of a run does not wait.
    """
    if last_start is not None:
        wait = _interval_seconds(1) - (monotonic() - last_start)
        if wait > 0:
            sleep(wait)
    return monotonic()


def _interval_seconds(copies: int) -> float:
    """How long ``copies`` copies take at ``BULK_EMAIL_RATE_PER_MINUTE``, in seconds."""
    rate: int = settings.BULK_EMAIL_RATE_PER_MINUTE
    return copies * 60 / max(rate, 1)


def _interval_delta(copies: int) -> timedelta:
    """:func:`_interval_seconds` as a ``timedelta``."""
    return timedelta(seconds=_interval_seconds(copies))


def _open(mailer: BaseEmailBackend, bulk: BulkEmail) -> None:
    """Open ``mailer``'s connection now, when the server answers.

    A server that refuses the connection is logged and the connection is left
    unopened: each copy then tries to reach the server on its own and is recorded as
    failed if it cannot.
    """
    try:
        mailer.open()
    except CONNECTION_ERRORS as exc:
        log.error(
            "bulk email connection refused: bulk_email=%s error=%s",
            bulk.pk,
            type(exc).__name__,
        )


def _try_copy(bulk: BulkEmail, row: BulkEmailRecipient, mailer: BaseEmailBackend) -> _Attempt:
    """Send ``row`` its copy over ``mailer``, retrying a temporary refusal.

    A temporary refusal is tried again after each of :data:`RETRY_DELAYS` seconds,
    over a fresh connection, and gives up with :data:`GAVE_UP_REASON`; any other
    refusal fails at once with :data:`FAILED_REASON`.  Each refusal closes the
    connection, so the next try opens a fresh one rather than writing to a session
    the server may have dropped.
    """
    copy = render_copy(bulk, row)
    for delay in (0, *RETRY_DELAYS):
        if delay > 0:
            sleep(delay)
            _open(mailer, bulk)
        try:
            message = send_templated(
                to=row.email,
                subject=copy.subject,
                template=COPY_TEMPLATE,
                context={"text": copy.text, "html": copy.html},
                purpose=PURPOSE,
                user_id=row.user_id,
                to_name=row.name,
                mailer=mailer,
                headers=copy.headers,
            )
        except MailRefusedError as refusal:
            log.error(
                "bulk email copy refused: bulk_email=%s recipient=%s error=%s code=%s",
                bulk.pk,
                row.pk,
                error_name(refusal),
                refusal.code,
            )
            mailer.close()
            if refusal.code not in TEMPORARY_CODES:
                return _Attempt(status=RecipientStatus.FAILED, reason=FAILED_REASON)
            continue
        return _Attempt(status=RecipientStatus.SENT, message_id=message.extra_headers["Message-ID"])
    return _Attempt(status=RecipientStatus.FAILED, reason=GAVE_UP_REASON)


def _record(bulk: BulkEmail, row: BulkEmailRecipient, attempt: _Attempt, run: SenderRun) -> None:
    """Save what became of one copy at once: its row, and the email's count."""
    row.status = attempt.status
    row.reason = attempt.reason
    row.message_id = attempt.message_id
    row.tried_at = timezone.now()
    row.save(update_fields=["status", "reason", "message_id", "tried_at", "updated_at"])
    if attempt.status == RecipientStatus.SENT:
        bulk.sent_count += 1
        run.sent += 1
    else:
        bulk.failed_count += 1
        run.failed += 1
    bulk.save(update_fields=["sent_count", "failed_count", "updated_at"])
    run.actions.append(
        RunAction(
            kind=attempt.status,
            member=row.name,
            email=row.email,
            detail=attempt.reason or bulk.subject,
        )
    )


def _is_stop_requested(bulk: BulkEmail) -> bool:
    """True once **Stop** has been pressed on ``bulk``, read afresh from the database."""
    return BulkEmail.objects.filter(pk=bulk.pk, stop_requested=True).exists()


def _stop(bulk: BulkEmail) -> None:
    """Mark every copy of ``bulk`` not yet sent ``stopped``, and the email too.

    Each such row's reason names who pressed **Stop**.
    """
    bulk.refresh_from_db(fields=["stopped_by"])
    stopper = bulk.stopped_by.display_name if bulk.stopped_by is not None else UNKNOWN_STOPPER
    reason = f"Stopped by {stopper}"[:REASON_MAX_LENGTH]
    moment = timezone.now()
    with transaction.atomic():
        bulk.recipients.filter(status=RecipientStatus.PENDING).update(
            status=RecipientStatus.STOPPED, reason=reason, updated_at=moment
        )
        bulk.status = BulkEmailStatus.STOPPED
        bulk.stopped_at = moment
        bulk.stop_requested = False
        bulk.save(update_fields=["status", "stopped_at", "stop_requested", "updated_at"])
    log.info("bulk email stopped: bulk_email=%s", bulk.pk)


def _finish(bulk: BulkEmail) -> None:
    """Mark ``bulk`` sent once no copy is pending, and write its audit line."""
    if bulk.recipients.filter(status=RecipientStatus.PENDING).exists():
        return
    bulk.status = BulkEmailStatus.SENT
    bulk.sent_at = timezone.now()
    bulk.stop_requested = False
    bulk.save(update_fields=["status", "sent_at", "stop_requested", "updated_at"])
    audit.record(
        audit.BULK_EMAIL_SEND,
        actor=bulk.sender if bulk.sender is not None else audit.COMMAND_ACTOR,
        target=bulk,
        sent=bulk.sent_count,
        skipped=bulk.skipped_count,
        failed=bulk.failed_count,
    )
