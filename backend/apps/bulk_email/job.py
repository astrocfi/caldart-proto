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
name and address as they are then.  An email whose sender may no longer send its type
(a deleted account, or a role taken away) is returned unsent instead, with a
``bulk_email.refused`` audit line.  The pending rows are then sent in surname order,
one copy each, through ``caldart.mail.send_templated``, saving each row and the email's
counts as soon as that copy has been tried; a person who turned the type off since
the freeze is skipped then.  When no row is pending the email is
``sent``, and one ``bulk_email.send`` audit line is written.

The sender paces itself to ``BULK_EMAIL_RATE_PER_MINUTE`` copies a minute and opens a
fresh mail connection every ``BULK_EMAIL_BATCH_SIZE`` copies.  A temporary refusal
(:data:`TEMPORARY_CODES`) is tried again after each of :data:`RETRY_DELAYS` seconds; any
other refusal fails the copy at once.  Between copies it reads ``stop_requested``, set
by **Stop**: every copy not yet sent is then ``stopped`` and the email too.

Only one run works at a time: a run holds a database advisory lock for as long as it
works, and a second run that cannot take it does nothing.  A run given a time budget,
as **Run now** gives one, stops claiming and sending once the budget is spent and leaves
the email it was working on ``sending``, for the next run to finish.  A copy that fails
in a way the mail server did not report (a bug, not a refusal) fails that copy with
:data:`UNEXPECTED_REASON`, is logged with its traceback, and the run moves on to the
next email.
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
from django.db.models import Count, F
from django.utils import timezone

from apps.accounts.models import User
from apps.bulk_email.batch import SKIP_OPTED_OUT, batch_rows, snapshot, surname_order
from apps.bulk_email.callouts import (
    closed_reason,
    is_reminder_finish,
    reminder_finished,
    skip_pending,
)
from apps.bulk_email.models import (
    BulkEmail,
    BulkEmailRecipient,
    BulkEmailStatus,
    RecipientStatus,
)
from apps.bulk_email.render import COPY_TEMPLATE, PURPOSE, fill_values, render_copy
from apps.bulk_email.reply_to import claimed_reply_to
from apps.bulk_email.senders import SKIP_NOT_IN_DART, DartLimit, dart_limit, limit_dart
from apps.mail.types import is_opted_out, sendable_types
from apps.members.models import MemberProfile
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

#: Why a copy failed when something other than the mail server went wrong.
UNEXPECTED_REASON = "Unexpected error"

#: The time budget **Run now** gives a run, in seconds: inside the web server's and the
#: proxy's 60-second limit on one request.
REQUEST_BUDGET_SECONDS = 45

#: Who a stop names when the account that pressed **Stop** is gone.
UNKNOWN_STOPPER = "a deleted account"

#: What the transport raises when it cannot open a connection.
CONNECTION_ERRORS: tuple[type[Exception], ...] = (OSError,)

#: The advisory lock key only one run of the sender holds at a time.
SENDER_LOCK_KEY = 0x0B01_E3A1

#: What a run that found another run working says.
BUSY_MESSAGE = "Another run of the bulk email sender is working; this one did nothing."

#: Why a due email went back unsent, kept on the email for the Drafts screen.
NOT_SENT_TYPE = (
    "This email was not sent: you can no longer send {type} email. Choose another type "
    "and send again."
)
NOT_SENT_SENDER_DELETED = (
    "This email was not sent: the account that sent it has been deleted. Send it again "
    "from your own account."
)
NOT_SENT_NO_TYPE = "This email was not sent: it has no type. Choose a type and send again."
NOT_SENT_DART_CHANGED = (
    "Your DART changed, so this email was not sent. Add the people again and send when it is ready."
)
NOT_SENT_NO_DART = (
    "This email was not sent: your profile names no DART, so there is nobody to send to. "
    "Set your DART on My profile and send again."
)

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
    ``out_of_time`` is true when the run's time budget ran out with copies still to
    send, and ``remaining`` counts the copies left for the next run then.
    ``actions`` holds one :class:`~caldart.runs.RunAction` per copy tried, whose
    ``kind`` is ``sent`` or ``failed`` and whose ``detail`` is the subject or the
    reason.  ``tallies`` holds each email's sent and failed copies, by its id.

    ``deadline`` (on the :func:`monotonic` clock) and ``last_start`` are the run's own
    bookkeeping: when its budget runs out, and when its last copy began, which paces
    the next copy whichever email it belongs to.
    """

    busy: bool = False
    emails: int = 0
    sent: int = 0
    failed: int = 0
    skipped: int = 0
    out_of_time: bool = False
    remaining: int = 0
    actions: list[RunAction] = field(default_factory=list)
    tallies: dict[int, list[int]] = field(default_factory=dict)
    deadline: float | None = None
    last_start: float | None = None

    def as_dict(self) -> dict[str, Any]:
        """The counts and the actions ``POST /system/bulk-email/run`` answers with."""
        return {
            "busy": self.busy,
            "emails": self.emails,
            "sent": self.sent,
            "failed": self.failed,
            "skipped": self.skipped,
            "out_of_time": self.out_of_time,
            "remaining": self.remaining,
            "actions": [action.as_dict() for action in self.actions],
        }

    def as_lines(self) -> list[str]:
        """The run as printable lines: the counts, then each email's by its id.

        No line names a person or an address, since the lines go to the journal.
        """
        if self.busy:
            return [BUSY_MESSAGE]
        lines = [
            f"emails           {self.emails}",
            f"sent             {self.sent}",
            f"failed           {self.failed}",
            f"skipped          {self.skipped}",
        ]
        if self.out_of_time:
            lines.append(f"remaining        {self.remaining} (left for the next run)")
        return lines + [
            f"bulk_email {pk}: sent {sent}, failed {failed}"
            for pk, (sent, failed) in self.tallies.items()
        ]

    def is_out_of_time(self) -> bool:
        """True once the run's time budget, if it has one, is spent."""
        return self.deadline is not None and monotonic() >= self.deadline

    def would_overrun(self, seconds: float) -> bool:
        """True when waiting ``seconds`` more would take the run past its budget."""
        return self.deadline is not None and monotonic() + seconds > self.deadline


@dataclass(frozen=True)
class _Attempt:
    """What became of one copy: its status, the reason, and the ``Message-ID`` it had."""

    status: RecipientStatus
    reason: str = ""
    message_id: str = ""


def run_sender(now: datetime | None = None, *, budget_seconds: float | None = None) -> SenderRun:
    """Finish every email left ``sending``, then start every one whose time has come.

    ``now`` is the moment a queued email's ``start_at`` is compared with, the current
    time unless given.  ``budget_seconds`` limits how long the run works: once it is
    spent the run claims nothing more and stops before its next copy, leaving that
    email ``sending`` for the next run to finish, and the result says how many copies
    are left.  Without it the run works until nothing is due.  Returns what the run
    did; a run that finds another run working returns at once with ``busy`` set and
    does nothing.
    """
    moment = now if now is not None else timezone.now()
    run = SenderRun(deadline=None if budget_seconds is None else monotonic() + budget_seconds)
    with _sender_lock() as is_held:
        if not is_held:
            log.info("bulk email sender busy: another run holds the lock")
            run.busy = True
            return run
        unfinished = list(
            BulkEmail.objects.filter(status=BulkEmailStatus.SENDING).order_by("started_at", "pk")
        )
        for bulk in unfinished:
            if run.out_of_time:
                break
            _send(bulk, run)
        while not run.out_of_time and (claimed := _claim(moment, run)) is not None:
            _send(claimed, run)
    if run.out_of_time:
        run.remaining = BulkEmailRecipient.objects.filter(
            bulk_email__status=BulkEmailStatus.SENDING, status=RecipientStatus.PENDING
        ).count()
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
    An email its sender may no longer send (:func:`_sender_refusal`) is returned unsent
    (:func:`_refuse`), and the next due email is taken instead.  A claimed email's
    ``reply_to`` becomes the address its copies carry
    (``apps.bulk_email.reply_to.claimed_reply_to``).  A mission callout whose answers
    have closed sends nothing: its copies are skipped (:func:`_skip_if_closed`).
    """
    while True:
        with transaction.atomic():
            bulk = (
                BulkEmail.objects.select_for_update(skip_locked=True)
                .filter(status=BulkEmailStatus.QUEUED, start_at__lte=now)
                .order_by("start_at", "pk")
                .first()
            )
            if bulk is None:
                return None
            refusal = _sender_refusal(bulk)
            if refusal is not None:
                _refuse(bulk, refusal)
                continue
            bulk.status = BulkEmailStatus.SENDING
            if bulk.started_at is None:
                bulk.started_at = timezone.now()
                # The DART the batch is frozen against; a resumed send keeps its own.
                bulk.dart = limit_dart(dart_limit(bulk))
            bulk.reply_to = claimed_reply_to(bulk)
            run.skipped += _freeze(bulk)
            run.skipped += _skip_if_closed(bulk)
            bulk.save(
                update_fields=[
                    "status",
                    "started_at",
                    "dart",
                    "reply_to",
                    "skipped_count",
                    "updated_at",
                ]
            )
        return bulk


def _skip_if_closed(bulk: BulkEmail) -> int:
    """Skip every pending copy of ``bulk`` when it is a callout that has closed.

    Each becomes ``skipped`` with ``apps.bulk_email.callouts.CLOSED_REASON``, so a timer
    that runs late, or **Send the rest** after **Close now**, sends nobody a callout that
    can no longer be answered.  ``skipped_count`` grows; answers how many were skipped.
    """
    if closed_reason(bulk) == "":
        return 0
    skipped = skip_pending(bulk)
    bulk.skipped_count += skipped
    return skipped


@dataclass(frozen=True)
class _Refusal:
    """Why a due email is not sent: the audit reason slug and the sentence it keeps."""

    reason: str
    message: str


def _sender_refusal(bulk: BulkEmail) -> _Refusal | None:
    """Why ``bulk``'s sender may no longer send it, or ``None`` when they may.

    The sender's roles as they are now are checked against the type's
    ``sender_roles``, as **Send** checked them: an account deleted since, a role taken
    away, or a type changed to name other roles all refuse it.  So does a DART
    leader's profile that names no DART any more (``apps.bulk_email.senders``), and,
    for an email that has not started, one whose DART changed so that nobody in the
    batch is in it.
    """
    if bulk.email_type is None:
        return _Refusal(reason=audit.REASON_NO_TYPE, message=NOT_SENT_NO_TYPE)
    if bulk.sender is None:
        return _Refusal(reason=audit.REASON_SENDER_DELETED, message=NOT_SENT_SENDER_DELETED)
    if bulk.email_type not in sendable_types(bulk.sender):
        return _Refusal(
            reason=audit.REASON_TYPE_NOT_SENDABLE,
            message=NOT_SENT_TYPE.format(type=bulk.email_type.name),
        )
    limit = dart_limit(bulk)
    if limit is not None and limit.dart is None:
        return _Refusal(reason=audit.REASON_NO_DART, message=NOT_SENT_NO_DART)
    if limit is not None and bulk.started_at is None and _limit_leaves_nobody(bulk, limit):
        return _Refusal(reason=audit.REASON_DART_CHANGED, message=NOT_SENT_DART_CHANGED)
    return None


def _limit_leaves_nobody(bulk: BulkEmail, limit: DartLimit) -> bool:
    """True when ``bulk`` has people in its batch and its DART limit allows none of them.

    That happens when a DART leader's profile names another DART after **Send**: the
    batch was built in the old DART, and sending it would skip everybody.  Rows of
    deleted accounts are left out of the question.
    """
    accounts = [row.account for row in batch_rows(bulk) if row.account is not None]
    return len(accounts) > 0 and not any(limit.allows(account) for account in accounts)


def _refuse(bulk: BulkEmail, refusal: _Refusal) -> None:
    """Return ``bulk`` unsent, keeping ``refusal``'s sentence, and audit it.

    An email that never started goes back to a draft, its batch and content intact and
    its schedule cleared, with ``not_sent_reason`` set for the Drafts screen.  One
    **Send the rest** queued again goes back to ``stopped``, its queued copies with it,
    each naming the sentence.  Either way a WARNING ``bulk_email.refused`` audit line
    names the email and the reason, under the ``command`` actor.
    """
    moment = timezone.now()
    if bulk.started_at is None:
        bulk.status = BulkEmailStatus.DRAFT
        bulk.start_at = None
        bulk.scheduled = False
        bulk.confirm_count = None
    else:
        bulk.status = BulkEmailStatus.STOPPED
        bulk.stopped_at = moment
        bulk.recipients.filter(status=RecipientStatus.PENDING).update(
            status=RecipientStatus.STOPPED,
            reason=refusal.message[:REASON_MAX_LENGTH],
            updated_at=moment,
        )
    bulk.not_sent_reason = refusal.message
    bulk.save(
        update_fields=[
            "status",
            "start_at",
            "scheduled",
            "confirm_count",
            "stopped_at",
            "not_sent_reason",
            "updated_at",
        ]
    )
    log.warning("bulk email not sent: bulk_email=%s reason=%s", bulk.pk, refusal.reason)
    audit.refuse(
        audit.BULK_EMAIL_REFUSED, actor=audit.COMMAND_ACTOR, target=bulk, reason=refusal.reason
    )


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
    """Send every pending copy of ``bulk``, paced, then mark it sent or stopped.

    The stop flag is read before each copy's pause and again after it.  The email is
    left ``sending``, for a later run, when the run's budget runs out or a copy fails
    unexpectedly; that copy is then ``failed`` with :data:`UNEXPECTED_REASON`.
    """
    run.emails += 1
    rows = list(
        surname_order(bulk.recipients.filter(status=RecipientStatus.PENDING)).select_related("user")
    )
    mailer = mailers.default
    # The number of copies tried over the open connection; None while none is open.
    on_connection: int | None = None
    try:
        for row in rows:
            if run.is_out_of_time():
                run.out_of_time = True
                return
            if _is_stop_requested(bulk):
                apply_stop(bulk)
                return
            _pace(run)
            if run.is_out_of_time():
                run.out_of_time = True
                return
            if _is_stop_requested(bulk):
                apply_stop(bulk)
                return
            # Read last, right before the copy goes, so an opt-out or a DART change made
            # during the pause is honored too.
            if _skip_if_unsendable(bulk, row, run):
                continue
            if on_connection is None or on_connection >= settings.BULK_EMAIL_BATCH_SIZE:
                mailer.close()
                _open(mailer, bulk)
                on_connection = 0
            try:
                attempt = _try_copy(bulk, row, mailer, run)
            except Exception:
                # Not a refusal the server reported: a bug.  This copy fails and the
                # run moves on, so one bad email cannot hold every later one back.
                log.exception(
                    "bulk email copy failed unexpectedly: bulk_email=%s recipient=%s",
                    bulk.pk,
                    row.pk,
                )
                _record(
                    bulk,
                    row,
                    _Attempt(status=RecipientStatus.FAILED, reason=UNEXPECTED_REASON),
                    run,
                )
                return
            if attempt is None:
                run.out_of_time = True
                return
            # A failed copy closed the connection, so the next one opens a fresh one.
            on_connection = None if attempt.status == RecipientStatus.FAILED else on_connection + 1
            _record(bulk, row, attempt, run)
    finally:
        mailer.close()
    _finish(bulk)


def _skip_if_unsendable(bulk: BulkEmail, row: BulkEmailRecipient, run: SenderRun) -> bool:
    """Skip ``row`` when its person may no longer be sent ``bulk``, as of now.

    Both are read afresh for every copy, so a change made during a long paced send,
    between **Stop** and **Send the rest**, or before a run that died is resumed, is
    honored.  A person outside the DART a DART leader's email is limited to
    (``apps.bulk_email.senders.dart_limit``, the sender's DART as it is now) is skipped
    with *Not in your DART*, and one who has turned the email's type off with the
    batch's *Opted out of <type>*, and every copy of a mission callout whose answers
    have closed meanwhile with ``apps.bulk_email.callouts.CLOSED_REASON``;
    ``skipped_count`` grows by one.  Returns whether the row was skipped.
    """
    reason = closed_reason(bulk)
    if reason == "" and row.user is not None:
        reason = _unsendable_reason(bulk, row.user)
    if reason == "":
        return False
    row.status = RecipientStatus.SKIPPED
    row.reason = reason
    row.save(update_fields=["status", "reason", "updated_at"])
    bulk.skipped_count += 1
    bulk.save(update_fields=["skipped_count", "updated_at"])
    run.skipped += 1
    return True


def _unsendable_reason(bulk: BulkEmail, account: User) -> str:
    """Why ``account`` may not be sent ``bulk`` now, or ``""`` when it may.

    The account's profile is read afresh, so a DART changed since the row was loaded
    counts.
    """
    limit = dart_limit(bulk)
    if limit is not None:
        profile = MemberProfile.objects.filter(user=account).only("dart_id").first()
        dart_id = profile.dart_id if profile is not None else None
        if limit.dart is None or dart_id != limit.dart.pk:
            return SKIP_NOT_IN_DART
    if bulk.email_type is not None and is_opted_out(account, bulk.email_type):
        return SKIP_OPTED_OUT.format(type=bulk.email_type.name)
    return ""


def _pace(run: SenderRun) -> None:
    """Wait out the rest of the interval since the run's last copy began.

    The interval is 60 seconds over ``BULK_EMAIL_RATE_PER_MINUTE``, measured across
    every email the run sends, so the copies go no faster than that rate however
    quickly the mail server answers and however many small emails are due.  The first
    copy of a run does not wait.
    """
    if run.last_start is not None:
        wait = _interval_seconds(1) - (monotonic() - run.last_start)
        if wait > 0:
            sleep(wait)
    run.last_start = monotonic()


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


def _try_copy(
    bulk: BulkEmail, row: BulkEmailRecipient, mailer: BaseEmailBackend, run: SenderRun
) -> _Attempt | None:
    """Send ``row`` its copy over ``mailer``, retrying a temporary refusal.

    A temporary refusal is tried again after each of :data:`RETRY_DELAYS` seconds,
    over a fresh connection, and gives up with :data:`GAVE_UP_REASON`; any other
    refusal fails at once with :data:`FAILED_REASON`.  Each refusal closes the
    connection, so the next try opens a fresh one rather than writing to a session
    the server may have dropped.  Returns ``None``, leaving the copy ``pending`` for a
    later run, when the next retry's wait would take the run past its budget.

    The copy is filled in with the account's values as they are now, which are kept on
    ``row`` (unsaved; :func:`_record` saves them) so it can be rebuilt as it went.  It
    carries the ``Reply-To`` the claim settled on.
    """
    row.values = fill_values(bulk, row.user)
    copy = render_copy(bulk, row)
    for delay in (0, *RETRY_DELAYS):
        if delay > 0 and run.would_overrun(delay):
            return None
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
                reply_to=bulk.reply_to,
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
    """Save what became of one copy at once: its row first, then the email's count.

    The row is saved first, with its status and ``Message-ID``, outside any transaction
    and before the counts or anything else, so a run that dies after the hand-over leaves
    a copy that went marked ``sent``, and the next run never sends it again.  A crash
    between the two saves therefore leaves the count one short, never a duplicate
    email; :func:`recount` puts the counts right from the rows when the email finishes
    or stops.  The count is added to in the database, not written from ``bulk`` in
    memory, so a bounce the bounce check moves off ``sent_count`` meanwhile
    (``apps.bulk_email.delivery``) is not undone.
    """
    row.status = attempt.status
    row.reason = attempt.reason
    row.message_id = attempt.message_id
    row.tried_at = timezone.now()
    row.save(update_fields=["status", "reason", "message_id", "tried_at", "values", "updated_at"])
    is_sent = attempt.status == RecipientStatus.SENT
    counter = "sent_count" if is_sent else "failed_count"
    BulkEmail.objects.filter(pk=bulk.pk).update(
        **{counter: F(counter) + 1, "updated_at": timezone.now()}
    )
    bulk.refresh_from_db(fields=["sent_count", "failed_count", "updated_at"])
    if is_sent:
        run.sent += 1
    else:
        run.failed += 1
    tally = run.tallies.setdefault(bulk.pk, [0, 0])
    tally[0 if attempt.status == RecipientStatus.SENT else 1] += 1
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


#: Each count an email keeps, and the status of the rows it counts.
COUNTED_STATUSES: dict[str, str] = {
    "sent_count": RecipientStatus.SENT,
    "failed_count": RecipientStatus.FAILED,
    "skipped_count": RecipientStatus.SKIPPED,
    "bounced_count": RecipientStatus.BOUNCED,
}


def recount(bulk: BulkEmail) -> list[str]:
    """Set ``bulk``'s four counts from its rows, unsaved; answer the fields set.

    ``sent_count``, ``failed_count``, ``skipped_count``, and ``bounced_count`` become the
    number of rows, over every round, that are ``sent``, ``failed``, ``skipped``, and
    ``bounced``.  The counts are added to one copy at a time as the send goes, after each
    row is saved (:func:`_record`), so a run that died between the two leaves a count
    short; recounting when the email finishes or stops puts it right.
    """
    by_status = dict(
        bulk.recipients.order_by()
        .values("status")
        .annotate(rows=Count("pk"))
        .values_list("status", "rows")
    )
    for count_field, status in COUNTED_STATUSES.items():
        setattr(bulk, count_field, by_status.get(status, 0))
    return list(COUNTED_STATUSES)


def apply_stop(bulk: BulkEmail) -> None:
    """Mark every copy of ``bulk`` not yet sent ``stopped``, and the email too.

    Each such row's reason names who pressed **Stop**, ``stopped_by``.  One
    ``bulk_email.stop`` audit line names that account and the copies stopped; it is
    written here, when the stop takes effect, so a stop that came too late to keep any
    copy back writes none.  The email's counts are recounted from its rows
    (:func:`recount`).
    """
    bulk.refresh_from_db(fields=["stopped_by"])
    stopper = bulk.stopped_by.display_name if bulk.stopped_by is not None else UNKNOWN_STOPPER
    reason = f"Stopped by {stopper}"[:REASON_MAX_LENGTH]
    moment = timezone.now()
    with transaction.atomic():
        stopped = bulk.recipients.filter(status=RecipientStatus.PENDING).update(
            status=RecipientStatus.STOPPED, reason=reason, updated_at=moment
        )
        bulk.status = BulkEmailStatus.STOPPED
        bulk.stopped_at = moment
        bulk.stop_requested = False
        bulk.save(
            update_fields=[
                "status",
                "stopped_at",
                "stop_requested",
                "updated_at",
                *recount(bulk),
            ]
        )
    log.info("bulk email stopped: bulk_email=%s", bulk.pk)
    audit.record(
        audit.BULK_EMAIL_STOP,
        actor=bulk.stopped_by if bulk.stopped_by is not None else audit.COMMAND_ACTOR,
        target=bulk,
        recipients=stopped,
    )


def _finish(bulk: BulkEmail) -> None:
    """Mark ``bulk`` sent once no copy is pending, and write its audit line.

    A stop that arrived after the last copy has nothing left to stop: its request and
    its ``stopped_by`` are cleared, and no stop is recorded.  The first time an email
    finishes, ``sent_at`` is set and one ``bulk_email.send`` line written.  An email
    finishing again after **Retry failed** keeps its first ``sent_at`` and writes
    :func:`_retry_finished`'s line instead, and a mission callout finishing a round of
    reminders writes ``callout.remind_finished``
    (``apps.bulk_email.callouts.reminder_finished``).  Every time, the email's counts are
    recounted from its rows (:func:`recount`), so a run that died between saving a row
    and its count leaves no count off for good.
    """
    if bulk.recipients.filter(status=RecipientStatus.PENDING).exists():
        return
    is_retry = bulk.sent_at is not None
    bulk.status = BulkEmailStatus.SENT
    if not is_retry:
        bulk.sent_at = timezone.now()
    bulk.stop_requested = False
    bulk.stopped_by = None
    bulk.save(
        update_fields=[
            "status",
            "sent_at",
            "stop_requested",
            "stopped_by",
            "updated_at",
            *recount(bulk),
        ]
    )
    if is_retry and is_reminder_finish(bulk):
        reminder_finished(bulk)
        return
    if is_retry:
        _retry_finished(bulk)
        return
    audit.record(
        audit.BULK_EMAIL_SEND,
        actor=bulk.sender if bulk.sender is not None else audit.COMMAND_ACTOR,
        target=bulk,
        sent=bulk.sent_count,
        skipped=bulk.skipped_count,
        failed=bulk.failed_count,
    )


def _retry_finished(bulk: BulkEmail) -> None:
    """Write the ``bulk_email.retry_finished`` line of ``bulk``'s latest retry.

    It names who pressed **Retry failed** (or the ``command`` actor once that account
    is gone), the copies the retry queued, and how many of the copies tried since it was
    pressed went and failed.
    """
    retry = bulk.retries.order_by("-requested_at", "-pk").select_related("requested_by").first()
    if retry is None:
        return
    tried = bulk.recipients.filter(tried_at__gte=retry.requested_at)
    audit.record(
        audit.BULK_EMAIL_RETRY_FINISHED,
        actor=retry.requested_by if retry.requested_by is not None else audit.COMMAND_ACTOR,
        target=bulk,
        recipients=retry.count,
        sent=tried.filter(status__in=[RecipientStatus.SENT, RecipientStatus.BOUNCED]).count(),
        failed=tried.filter(status=RecipientStatus.FAILED).count(),
    )
