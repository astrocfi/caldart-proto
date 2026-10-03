"""What became of a bulk email's copies after they went: bounces, retries, and copies.

The background sender records each copy's immediate answer: ``sent``, ``failed``, or
``skipped``.  This module joins the later picture to it.

* **Bounces.**  The bounce check (``apps.mail.bounces``) marks an email log row
  ``bounced`` when a delivery report arrives for it, hours or days after the send.
  :func:`mark_bounced`, which ``apps.bulk_email.apps`` connects to every save of an
  ``EmailLog``, finds the bulk copy that went out with the same ``Message-ID`` and marks
  it ``bounced`` with the report's detail, moving it from ``sent_count`` to
  ``bounced_count``.
* **Retry failed.**  :func:`retry_failed` puts every ``failed`` copy of a finished send
  back to ``pending`` and queues the email to start at once, as **Send the rest**
  does, recording a :class:`~apps.bulk_email.models.BulkEmailRetry`.  The sender then
  sends those copies afresh; a bounced or skipped copy is never retried.
* **A recipient's copy.**  :func:`recipient_copy` rebuilds one person's copy exactly as
  it went, from the field values stored on the row when it was tried.
* **Hiding.**  :func:`set_hidden` keeps a sent email off every recipient's **Messages**
  page (``apps.bulk_email.archive``) or puts it back, changing nothing else.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from django.db import transaction
from django.db.models import F, Value
from django.db.models.functions import Greatest
from django.utils import timezone

from apps.accounts.models import User
from apps.bulk_email.models import (
    BulkEmail,
    BulkEmailRecipient,
    BulkEmailRetry,
    BulkEmailStatus,
    RecipientStatus,
)
from apps.bulk_email.render import PURPOSE, RenderedCopy, render_copy
from apps.mail.models import EmailLog, EmailStatus
from caldart import audit
from caldart.exceptions import DomainError

log = logging.getLogger(__name__)

#: The longest reason a recipient row holds.
REASON_MAX_LENGTH = 200

#: A bounced copy's reason when the report carried no detail of its own.
BOUNCED_REASON = "The receiving mail server refused it"

#: Why **Retry failed** is refused.
NOT_STARTED_MESSAGE = "This email has not been sent."
STILL_SENDING_MESSAGE = "This email is still sending. Retry the failed copies once it has finished."
STOPPED_MESSAGE = "This email was stopped. Send the rest first, then retry the failed copies."
NOTHING_FAILED_MESSAGE = "No copy failed, so there is nothing to retry."

#: Why a recipient's copy cannot be shown.
NOT_TRIED_MESSAGE = "This person was not sent a copy."


def on_email_log_saved(sender: type[EmailLog], instance: EmailLog, **kwargs: Any) -> None:
    """``post_save`` receiver: tie a bounced bulk email copy back to its bulk email.

    Only a row of the ``bulk_email`` purpose is looked at; :func:`mark_bounced` does
    the rest.  Connected by ``apps.bulk_email.apps.BulkEmailConfig.ready``.
    """
    if instance.purpose != PURPOSE:
        return
    mark_bounced(instance)


def email_log_links(rows: Sequence[EmailLog]) -> dict[int, str]:
    """The Sent page of the bulk email each copy among ``rows`` belongs to, by row id.

    A copy is an email log row of the ``bulk_email`` purpose whose ``message_id`` a
    recipient row carries; its link is ``/bulk-email/sent/<id>``, a portal path.  Every
    other row is left out.  One query answers the whole of ``rows``.  Registered with
    ``apps.mail.links`` by ``apps.bulk_email.apps.BulkEmailConfig.ready``.
    """
    log_ids = {row.message_id: row.pk for row in rows if row.purpose == PURPOSE}
    log_ids.pop("", None)
    if len(log_ids) == 0:
        return {}
    copies = BulkEmailRecipient.objects.filter(message_id__in=log_ids).values_list(
        "message_id", "bulk_email_id"
    )
    return {log_ids[message_id]: f"/bulk-email/sent/{bulk_id}" for message_id, bulk_id in copies}


def mark_bounced(entry: EmailLog) -> BulkEmailRecipient | None:
    """Mark the bulk copy ``entry`` records as bounced; return the row, or ``None``.

    ``entry`` must be ``bounced`` and carry a ``message_id``.  The copy is the
    recipient row that went out with the same ``Message-ID`` and still reads ``sent``:
    it becomes ``bounced`` with the report's ``bounce_detail`` (cut to 200 characters,
    or :data:`BOUNCED_REASON` when the report gave none) as its reason, and its email's
    ``sent_count`` falls by one as its ``bounced_count`` rises by one.  A row that is
    already ``bounced``, or any other row, is left alone, so the same report read twice
    counts once.  Answers ``None`` when there is nothing to mark.
    """
    if entry.status != EmailStatus.BOUNCED or entry.message_id == "":
        return None
    moment = timezone.now()
    with transaction.atomic():
        row = (
            BulkEmailRecipient.objects.select_for_update()
            .filter(message_id=entry.message_id, status=RecipientStatus.SENT)
            .first()
        )
        if row is None:
            return None
        row.status = RecipientStatus.BOUNCED
        row.reason = (entry.bounce_detail or BOUNCED_REASON)[:REASON_MAX_LENGTH]
        row.save(update_fields=["status", "reason", "updated_at"])
        # Counted in the database rather than from a copy in memory, so a bounce read
        # while the background sender is still counting the same email loses nothing.
        BulkEmail.objects.filter(pk=row.bulk_email_id).update(
            sent_count=Greatest(F("sent_count") - 1, Value(0)),
            bounced_count=F("bounced_count") + 1,
            updated_at=moment,
        )
    log.info("bulk email copy bounced: bulk_email=%s recipient=%s", row.bulk_email_id, row.pk)
    return row


def retry_failed(bulk: BulkEmail, *, actor: User, now: datetime | None = None) -> BulkEmailRetry:
    """**Retry failed**: queue every failed copy of the sent ``bulk`` to go again, now.

    Every ``failed`` row goes back to ``pending`` with its reason cleared, and leaves
    ``failed_count``; the email is queued with ``start_at`` at ``now`` and no undo
    window, and the background sender sends those copies alone, each filled in with the
    person's values as they are then.  Bounced and skipped copies are not retried, nor
    is anyone already sent a copy.  The email keeps its ``started_at``, so it stays
    read-only (``BulkEmail.can_edit``), and **Stop** stops the retry as it stops
    **Send the rest**.  Like any send, the sender checks once more that ``bulk``'s
    sender may send its type, and skips anybody who has turned the type off since.

    Returns the :class:`~apps.bulk_email.models.BulkEmailRetry` recorded, naming
    ``actor``, the time, and the number of copies queued.  Raises ``DomainError`` with
    :data:`NOT_STARTED_MESSAGE` for an email that never started, :data:`STOPPED_MESSAGE`
    for a stopped one, :data:`STILL_SENDING_MESSAGE` for one queued or sending, and
    :data:`NOTHING_FAILED_MESSAGE` when no copy failed; nothing changes then.  One
    ``bulk_email.retry`` audit line names ``actor`` and the number of copies.
    """
    moment = now if now is not None else timezone.now()
    with transaction.atomic():
        locked = BulkEmail.objects.select_for_update().get(pk=bulk.pk)
        _check_retry(locked)
        count = locked.recipients.filter(status=RecipientStatus.FAILED).update(
            status=RecipientStatus.PENDING, reason="", updated_at=moment
        )
        if count == 0:
            raise DomainError(NOTHING_FAILED_MESSAGE)
        retry = BulkEmailRetry.objects.create(
            bulk_email=locked, requested_by=actor, requested_at=moment, count=count
        )
        locked.status = BulkEmailStatus.QUEUED
        locked.start_at = moment
        locked.scheduled = False
        locked.failed_count = max(locked.failed_count - count, 0)
        locked.save(update_fields=["status", "start_at", "scheduled", "failed_count", "updated_at"])
    audit.record(audit.BULK_EMAIL_RETRY, actor=actor, target=locked, recipients=count)
    return retry


@dataclass(frozen=True)
class RecipientCopy:
    """One person's copy of a bulk email: their recipient row and the copy as it went."""

    recipient: BulkEmailRecipient
    copy: RenderedCopy


def recipient_copy(bulk: BulkEmail, recipient_id: int) -> RecipientCopy:
    """The row ``recipient_id`` of ``bulk``, and that person's copy as it went.

    The copy is rebuilt with ``apps.bulk_email.render.render_copy`` from the field
    values stored on the row when it was last tried, never from the account as it is
    now, so it reads as it was sent whatever has changed since.  The row may be of any
    round.  Raises ``BulkEmailRecipient.DoesNotExist`` for a row of another email, and
    ``DomainError`` with :data:`NOT_TRIED_MESSAGE` for a row whose copy was never tried
    (skipped, stopped, or not sent yet).
    """
    row = BulkEmailRecipient.objects.select_related("user").get(bulk_email=bulk, pk=recipient_id)
    if row.tried_at is None:
        raise DomainError(NOT_TRIED_MESSAGE)
    return RecipientCopy(recipient=row, copy=render_copy(bulk, row))


def retried_count(bulk: BulkEmail) -> int:
    """How many copies **Retry failed** has queued again for ``bulk``, in all."""
    return sum(retry.count for retry in bulk.retries.all())


def set_hidden(bulk: BulkEmail, *, hidden: bool, actor: User) -> BulkEmail:
    """Keep ``bulk`` off every recipient's **Messages** page, or put it back.

    Nothing else about the email changes: its copies, counts, and history stay as they
    are, and CalDART management still sees it on the Sent page.  Raises ``DomainError``
    with :data:`NOT_STARTED_MESSAGE` for an email that has never started sending, which
    nobody has received.  One ``bulk_email.hide`` audit line names ``actor`` and the
    choice, written only when it changes.
    """
    with transaction.atomic():
        locked = BulkEmail.objects.select_for_update().get(pk=bulk.pk)
        if locked.started_at is None:
            raise DomainError(NOT_STARTED_MESSAGE)
        if locked.hidden_from_archive == hidden:
            return locked
        locked.hidden_from_archive = hidden
        locked.save(update_fields=["hidden_from_archive", "updated_at"])
    audit.record(audit.BULK_EMAIL_HIDE, actor=actor, target=locked, hidden=hidden)
    return locked


def _check_retry(bulk: BulkEmail) -> None:
    """Refuse **Retry failed** on ``bulk`` unless it is a send that has finished."""
    if bulk.started_at is None:
        raise DomainError(NOT_STARTED_MESSAGE)
    if bulk.status == BulkEmailStatus.STOPPED:
        raise DomainError(STOPPED_MESSAGE)
    if bulk.status != BulkEmailStatus.SENT:
        raise DomainError(STILL_SENDING_MESSAGE)
