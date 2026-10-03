"""A bulk email from its draft to the moment the background sender takes it.

A draft belongs to its sender and lives on the server, so it survives a reload and can
be built over several sittings.  :func:`open_draft` hands a sender their one empty
draft, or a fresh one.  The content and the batch can change while the email is a
draft or ``queued`` (the edit rule, :func:`apps.bulk_email.batch.locked_for_edit`);
once the sender has started it, nothing can.

:func:`queue` is **Send**: it checks the email can go, then queues it to start at the
end of the undo window (``BULK_EMAIL_UNDO_SECONDS``) or at the time the sender chose.
Nothing is sent then: the background sender (``apps.bulk_email.job``) starts it.
:func:`cancel` takes a queued email back to a draft, :func:`stop` asks a send in
progress to stop between copies, and :func:`resume` queues the copies a stop left
unsent.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Count, QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.permissions import user_has_any_role
from apps.accounts.roles import MANAGEMENT
from apps.bulk_email.batch import batch_counts, batch_rows, locked_for_edit
from apps.bulk_email.checks import NO_BODY_MESSAGE as NO_BODY_MESSAGE
from apps.bulk_email.checks import NO_SUBJECT_MESSAGE as NO_SUBJECT_MESSAGE
from apps.bulk_email.checks import refuse_on_errors
from apps.bulk_email.job import apply_stop
from apps.bulk_email.models import BulkEmail, BulkEmailStatus, RecipientStatus
from apps.bulk_email.render import check_message
from apps.bulk_email.reply_to import default_reply_to, reply_to_for
from apps.bulk_email.richtext import html_to_text, sanitize
from apps.bulk_email.senders import dart_limit, limit_dart, sender_context, sender_notice
from apps.mail.types import sendable_types
from caldart import audit
from caldart.exceptions import DomainError, DomainPermissionError, DomainValidationError

#: The furthest ahead a send may be scheduled.
MAX_SCHEDULE_AHEAD = timedelta(days=365)

#: Why **Send** is refused.  A blank subject or message is refused with the checks' own
#: words, ``NO_SUBJECT_MESSAGE`` and ``NO_BODY_MESSAGE``, imported above.
NO_TYPE_MESSAGE = "Choose a type."
NOT_SENDABLE_MESSAGE = "You cannot send {type} email. Choose another type."
NOBODY_MESSAGE = "Nobody in the batch can receive this email. Add people to the batch."
CONFIRM_MISSING_MESSAGE = "Type the number of people this email goes to."
PAST_MESSAGE = "Choose a time in the future."
TOO_FAR_MESSAGE = "Choose a time within a year."

#: Why the other actions are refused.
STARTED_MESSAGE = "This email has started sending."
NOT_A_DRAFT_MESSAGE = "Only a draft can be deleted. Cancel the send first."
NOT_SENDING_MESSAGE = "This email is not sending."
NOT_STOPPED_MESSAGE = "Only a stopped email can send the rest."


@dataclass(frozen=True)
class OpenedDraft:
    """The draft :func:`open_draft` handed over, and whether it made it."""

    bulk: BulkEmail
    created: bool


def visible_to(user: User) -> QuerySet[BulkEmail]:
    """The bulk emails ``user`` may open: everyone's for CalDART management.

    CalDART management and a system administrator see every bulk email, with its
    sender; anybody else, a DART leader among them, sees only the ones they are the
    sender of.
    """
    emails = BulkEmail.objects.select_related("sender", "stopped_by", "email_type", "dart")
    if user_has_any_role(user, (MANAGEMENT,)):
        return emails
    return emails.filter(sender=user)


def open_draft(sender: User) -> OpenedDraft:
    """``sender``'s empty draft, or a fresh one when they have none.

    An empty draft has no subject, no message, and nobody in its batch.  When the
    sender has several, the oldest is handed back.  Either way the draft records the
    DART the sender may send to (``apps.bulk_email.senders.sender_context``): a DART
    leader's profile DART, or none for CalDART management.  Raises
    ``DomainPermissionError`` with ``NO_DART_MESSAGE`` for a sender who may send to
    nobody, such as a DART leader whose profile names no DART.
    A fresh draft's ``reply_to`` is the default
    (``apps.bulk_email.reply_to.default_reply_to``), which the compose screen shows for
    the sender to keep or change.
    """
    context = sender_context(sender)
    if not context.can_send:
        raise DomainPermissionError(context.reason)
    empty = (
        BulkEmail.objects.filter(sender=sender, status=BulkEmailStatus.DRAFT, subject="", body="")
        .annotate(people=Count("recipients"))
        .filter(people=0)
        .order_by("pk")
        .first()
    )
    if empty is not None:
        if empty.dart_id != (context.dart.pk if context.dart is not None else None):
            empty.dart = context.dart
            empty.save(update_fields=["dart", "updated_at"])
        return OpenedDraft(bulk=empty, created=False)
    fresh = BulkEmail.objects.create(
        sender=sender, dart=context.dart, reply_to=default_reply_to(sender)
    )
    return OpenedDraft(bulk=fresh, created=True)


def update(bulk: BulkEmail, changes: dict[str, object]) -> BulkEmail:
    """Save ``changes``, field name to value, onto ``bulk``; return it as saved.

    The values are taken as given: the API's serializer has checked them.  Editing a
    queued email leaves its start time alone, but cannot leave it without a subject
    or a message, which it is about to be sent with.  Raises ``DomainValidationError``
    keyed ``subject`` or ``body`` for that, and ``DomainError`` once the email has
    started sending.
    """
    with transaction.atomic():
        locked = locked_for_edit(bulk)
        for name, value in changes.items():
            setattr(locked, name, value)
        if locked.status == BulkEmailStatus.QUEUED:
            _check_content(locked)
        locked.save(update_fields=[*changes, "updated_at"])
    return locked


def delete_draft(bulk: BulkEmail) -> None:
    """Delete the draft ``bulk`` with its batch.

    Raises ``DomainError`` for an email that is queued (cancel it first) or has
    started sending.
    """
    with transaction.atomic():
        locked = locked_for_edit(bulk)
        if locked.status != BulkEmailStatus.DRAFT:
            raise DomainError(NOT_A_DRAFT_MESSAGE)
        locked.delete()


def queue(
    bulk: BulkEmail,
    *,
    confirm_count: int | None,
    start_at: datetime | None,
    actor: User,
    now: datetime | None = None,
) -> BulkEmail:
    """**Send**: queue ``bulk`` to start at ``start_at``, or once the undo window ends.

    The email must have a type that ``actor`` may send, a subject and a message, no
    error among its checks (``apps.bulk_email.checks.error_findings``, a ``Reply-To``
    address that is not valid among them), and somebody in its batch who can receive
    a copy.  A DART leader's email must have a
    DART to go to (``apps.bulk_email.senders.dart_limit``), and records it.  When more
    than ``BULK_EMAIL_CONFIRM_ABOVE`` people would receive it, ``confirm_count`` must be
    that number, the count the sender typed; a batch that changed after the sender typed
    it is refused with the number it holds now.  A ``start_at`` must be after ``now``
    and within a year of it.

    The email becomes ``queued`` with ``start_at`` set to the time given, or to ``now``
    plus ``BULK_EMAIL_UNDO_SECONDS``; ``scheduled`` says which, and ``confirm_count``
    keeps the typed count (null below the threshold), ``reply_to`` keeps the address the
    copies will carry (``apps.bulk_email.reply_to.reply_to_for``), and any
    ``not_sent_reason`` left by the background sender is cleared.  Queuing an email
    that is queued already reschedules it.  Nothing is sent: the background sender
    starts the email once ``start_at`` arrives.  One ``bulk_email.queue`` audit line
    names ``actor``.

    Raises ``DomainValidationError`` keyed ``subject``, ``body``, ``email_type``
    (:data:`NO_TYPE_MESSAGE`, or :data:`NOT_SENDABLE_MESSAGE` naming the type),
    ``batch`` (``apps.bulk_email.senders.sender_notice`` for an email limited to no
    DART, else :data:`NOBODY_MESSAGE`), ``confirm_count``, or ``start_at``, and
    ``DomainError`` once the email has started sending; nothing changes then.  An
    error among the checks that the fields above do not already refuse raises
    ``apps.bulk_email.checks.ChecksFailedError`` with every error.
    """
    moment = now if now is not None else timezone.now()
    with transaction.atomic():
        locked = locked_for_edit(bulk)
        _check_content(locked)
        _check_type(locked, actor)
        refuse_on_errors(locked)
        notice = sender_notice(locked)
        if notice != "":
            raise DomainValidationError("batch", notice)
        locked.dart = limit_dart(dart_limit(locked))
        receiving = batch_counts(batch_rows(locked)).receiving
        if receiving == 0:
            raise DomainValidationError("batch", NOBODY_MESSAGE)
        needs_count = receiving > settings.BULK_EMAIL_CONFIRM_ABOVE
        if needs_count:
            _check_confirm_count(confirm_count, receiving)
        if start_at is not None:
            _check_schedule(start_at, moment)
        locked.status = BulkEmailStatus.QUEUED
        locked.scheduled = start_at is not None
        locked.start_at = (
            start_at
            if start_at is not None
            else moment + timedelta(seconds=settings.BULK_EMAIL_UNDO_SECONDS)
        )
        locked.confirm_count = confirm_count if needs_count else None
        locked.not_sent_reason = ""
        locked.reply_to = reply_to_for(locked)
        locked.save(
            update_fields=[
                "status",
                "scheduled",
                "start_at",
                "confirm_count",
                "not_sent_reason",
                "dart",
                "reply_to",
                "updated_at",
            ]
        )
    audit.record(
        audit.BULK_EMAIL_QUEUE,
        actor=actor,
        target=locked,
        recipients=receiving,
        scheduled=locked.scheduled,
    )
    return locked


def cancel(bulk: BulkEmail, *, actor: User) -> BulkEmail:
    """Take the queued ``bulk`` back to a draft, its batch and content intact.

    A draft is handed back unchanged.  Raises ``DomainError`` with
    :data:`STARTED_MESSAGE` once the background sender has ever started it, which
    includes an email **Send the rest** queued again: it holds copies that went.  One
    ``bulk_email.cancel`` audit line names ``actor``.
    """
    with transaction.atomic():
        locked = BulkEmail.objects.select_for_update().get(pk=bulk.pk)
        if locked.started_at is not None:
            raise DomainError(STARTED_MESSAGE)
        if locked.status == BulkEmailStatus.DRAFT:
            return locked
        if locked.status != BulkEmailStatus.QUEUED:
            raise DomainError(STARTED_MESSAGE)
        locked.status = BulkEmailStatus.DRAFT
        locked.start_at = None
        locked.scheduled = False
        locked.confirm_count = None
        locked.save(
            update_fields=["status", "start_at", "scheduled", "confirm_count", "updated_at"]
        )
    audit.record(audit.BULK_EMAIL_CANCEL, actor=actor, target=locked)
    return locked


def stop(bulk: BulkEmail, *, actor: User) -> BulkEmail:
    """Ask the send of ``bulk`` in progress to stop; return the email.

    For a ``sending`` email the background sender reads the request between copies:
    every copy not yet sent is then marked ``stopped``, naming ``actor``, and the email
    becomes ``stopped``.  An email **Send the rest** queued again, which the sender has
    not picked up yet, stops at once the same way.  The ``bulk_email.stop`` audit line
    is written when the stop takes effect (:func:`apps.bulk_email.job.apply_stop`).
    Raises ``DomainError`` when the email is neither.
    """
    with transaction.atomic():
        locked = BulkEmail.objects.select_for_update().get(pk=bulk.pk)
        is_resumed = locked.status == BulkEmailStatus.QUEUED and locked.started_at is not None
        if locked.status != BulkEmailStatus.SENDING and not is_resumed:
            raise DomainError(NOT_SENDING_MESSAGE)
        locked.stopped_by = actor
        if is_resumed:
            locked.save(update_fields=["stopped_by", "updated_at"])
            apply_stop(locked)
            return locked
        locked.stop_requested = True
        locked.save(update_fields=["stop_requested", "stopped_by", "updated_at"])
    return locked


def resume(bulk: BulkEmail, *, actor: User, now: datetime | None = None) -> BulkEmail:
    """**Send the rest**: queue the copies a stop left unsent, to start at once.

    Every ``stopped`` row goes back to ``pending`` and the email is queued with
    ``start_at`` at ``now``, with no undo window; the background sender sends those
    copies alone, and nobody already sent a copy is sent another.  The email keeps its
    ``started_at``, so it stays read-only and cannot be canceled back to a draft;
    **Stop** stops it again.  Raises
    ``DomainError`` unless the email is ``stopped``.  One ``bulk_email.resume`` audit
    line names ``actor``.
    """
    moment = now if now is not None else timezone.now()
    with transaction.atomic():
        locked = BulkEmail.objects.select_for_update().get(pk=bulk.pk)
        if locked.status != BulkEmailStatus.STOPPED:
            raise DomainError(NOT_STOPPED_MESSAGE)
        resumed = locked.recipients.filter(status=RecipientStatus.STOPPED).update(
            status=RecipientStatus.PENDING, reason=""
        )
        locked.status = BulkEmailStatus.QUEUED
        locked.start_at = moment
        locked.scheduled = False
        locked.stop_requested = False
        locked.stopped_at = None
        locked.stopped_by = None
        locked.save(
            update_fields=[
                "status",
                "start_at",
                "scheduled",
                "stop_requested",
                "stopped_at",
                "stopped_by",
                "updated_at",
            ]
        )
    audit.record(audit.BULK_EMAIL_RESUME, actor=actor, target=locked, recipients=resumed)
    return locked


def confirm_message(receiving: int) -> str:
    """The refusal of a typed count that no longer matches: the batch's count now."""
    people = "1 person" if receiving == 1 else f"{receiving} people"
    return f"The batch has changed: it now holds {people}. Type the new count."


def _check_content(bulk: BulkEmail) -> None:
    """Refuse an email without a subject or a message, or one that cannot be filled in.

    A message is missing when its sanitized HTML reads as no text at all (an empty
    paragraph, say).  A token that cannot be filled in is refused as
    ``apps.bulk_email.render.check_message`` says, keyed by its field.
    """
    if bulk.subject.strip() == "":
        raise DomainValidationError("subject", NO_SUBJECT_MESSAGE)
    if html_to_text(sanitize(bulk.body)).strip() == "":
        raise DomainValidationError("body", NO_BODY_MESSAGE)
    problems = check_message(bulk.subject, bulk.body)
    if len(problems) > 0:
        name, problem = next(iter(problems.items()))
        raise DomainValidationError(name, problem)


def _check_type(bulk: BulkEmail, actor: User) -> None:
    """Refuse an email with no type, or one whose type ``actor`` may not send."""
    if bulk.email_type is None:
        raise DomainValidationError("email_type", NO_TYPE_MESSAGE)
    if bulk.email_type not in sendable_types(actor):
        raise DomainValidationError(
            "email_type", NOT_SENDABLE_MESSAGE.format(type=bulk.email_type.name)
        )


def _check_confirm_count(confirm_count: int | None, receiving: int) -> None:
    """Refuse a missing typed count, or one that is not ``receiving``."""
    if confirm_count is None:
        raise DomainValidationError("confirm_count", CONFIRM_MISSING_MESSAGE)
    if confirm_count != receiving:
        raise DomainValidationError("confirm_count", confirm_message(receiving))


def _check_schedule(start_at: datetime, now: datetime) -> None:
    """Refuse a scheduled time that is not after ``now``, or more than a year ahead."""
    if start_at <= now:
        raise DomainValidationError("start_at", PAST_MESSAGE)
    if start_at > now + MAX_SCHEDULE_AHEAD:
        raise DomainValidationError("start_at", TOO_FAR_MESSAGE)
