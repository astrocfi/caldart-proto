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
* **Hiding.**  :func:`set_hidden` keeps a sent email off every recipient's **Email to me**
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
from apps.bulk_email.batch import skip_reason, surname_order, type_opt_outs
from apps.bulk_email.models import (
    BulkEmail,
    BulkEmailRecipient,
    BulkEmailRetry,
    BulkEmailStatus,
    CalloutAnswer,
    RecipientStatus,
)
from apps.bulk_email.render import PURPOSE, RenderedCopy, render_copy
from apps.bulk_email.senders import dart_limit
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
NOBODY_TO_RETRY_MESSAGE = (
    "Nobody whose copy failed can be sent one now. Each is marked skipped, with the "
    "reason on their line."
)

#: Why a failed copy is not retried when a later copy has gone, or is going, instead.
SKIP_LATER_COPY = "Sent a later copy instead"

#: Why a copy of a callout's reminder round is not sent again to somebody who has
#: answered the callout since the round was queued.
SKIP_ANSWERED = "Answered the callout"

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
    """**Retry failed**: queue the failed copies of the sent ``bulk`` to go again, now.

    Each ``failed`` row first takes its account's name and address as they are now, so
    an address an administrator has corrected since is the one used, and is asked
    ``apps.bulk_email.batch.skip_reason`` afresh, as a send asks it: a deleted account
    (*Account deleted*), one no longer in the DART a DART leader's email is limited to
    (*Not in your DART*), a deactivated one, an address that is missing, invalid, or
    bounced, an opt-out of the type, an address already sent this round of the email,
    and, for a mission callout, a person a later round's copy reached or is going to
    (:data:`SKIP_LATER_COPY`) all make the row ``skipped`` with that reason, and
    ``skipped_count`` grows.  Every other
    failed row goes back to ``pending`` with its reason cleared.  Every failed row
    leaves ``failed_count``.  When any row went back to ``pending`` the email is queued
    with ``start_at`` at ``now`` and no undo window, and the background sender sends
    those copies alone, each filled in with the person's values as they are then.
    Bounced and skipped copies are not retried, nor is anyone already sent a copy of that
    round or of a later one, and nobody is queued twice.  The
    email keeps its ``started_at``, so it stays read-only (``BulkEmail.can_edit``), and
    **Stop** stops the retry as it stops **Send the rest**.

    Returns the :class:`~apps.bulk_email.models.BulkEmailRetry` recorded, naming
    ``actor``, the time, and the number of copies queued.  Raises ``DomainError`` with
    :data:`NOT_STARTED_MESSAGE` for an email that never started, :data:`STOPPED_MESSAGE`
    for a stopped one, :data:`STILL_SENDING_MESSAGE` for one queued or sending, and
    :data:`NOTHING_FAILED_MESSAGE` when no copy failed; nothing changes then.  When every
    failed row is skipped the skips are kept, nothing is queued or recorded as a retry,
    and ``DomainError`` with :data:`NOBODY_TO_RETRY_MESSAGE` says so.  One
    ``bulk_email.retry`` audit line names ``actor``, the copies queued, and the people
    skipped.
    """
    moment = now if now is not None else timezone.now()
    retry: BulkEmailRetry | None = None
    with transaction.atomic():
        locked = BulkEmail.objects.select_for_update().get(pk=bulk.pk)
        _check_retry(locked)
        failed = list(
            surname_order(locked.recipients.filter(status=RecipientStatus.FAILED)).select_related(
                "user", "user__profile"
            )
        )
        if len(failed) == 0:
            raise DomainError(NOTHING_FAILED_MESSAGE)
        retried, skipped = recheck_rows(locked, failed, moment)
        BulkEmailRecipient.objects.bulk_update(
            failed, ["status", "reason", "name", "email", "updated_at"]
        )
        locked.failed_count = max(locked.failed_count - len(failed), 0)
        locked.skipped_count += skipped
        fields = ["failed_count", "skipped_count", "updated_at"]
        if retried > 0:
            retry = BulkEmailRetry.objects.create(
                bulk_email=locked, requested_by=actor, requested_at=moment, count=retried
            )
            locked.status = BulkEmailStatus.QUEUED
            locked.start_at = moment
            locked.scheduled = False
            fields += ["status", "start_at", "scheduled"]
        locked.save(update_fields=fields)
    audit.record(
        audit.BULK_EMAIL_RETRY, actor=actor, target=locked, recipients=retried, skipped=skipped
    )
    if retry is None:
        raise DomainError(NOBODY_TO_RETRY_MESSAGE)
    return retry


def recheck_rows(
    bulk: BulkEmail, rows: list[BulkEmailRecipient], moment: datetime
) -> tuple[int, int]:
    """Set each of ``rows`` to ``pending`` or ``skipped``; answer how many of each.

    Every path that sends copies of a started email again asks this of the rows it
    takes back: **Retry failed** of the ``failed`` rows, and **Send the rest**
    (``apps.bulk_email.drafts.resume``) of the ``stopped`` ones.  The rows are taken a
    callout's latest round first, so a person whose reminder and first copy both failed
    is retried once, with the reminder.  A row is ``skipped`` with
    :data:`SKIP_LATER_COPY` when its account has a copy of a later round that was sent,
    bounced, or is pending, or one queued earlier in this pass, so nobody is sent an
    earlier copy after a later one, or two copies at once.  A row of a reminder round
    (``round`` above 0) whose account has answered the callout since is ``skipped``
    with :data:`SKIP_ANSWERED`, since a reminder asks only those who have not.  Every
    other row takes its account's name and address as they are now, then
    ``batch.skip_reason`` decides,
    with the DART a DART leader's email is limited to (``senders.dart_limit``, as it is
    now), the type's opt-outs, and the addresses already sent the row's own round of
    this email (or queued in this pass), trimmed and case-folded, so nobody already
    sent a copy of that round is sent another.  The rows are changed in memory; the
    caller saves them.
    """
    opt_outs = type_opt_outs(bulk)
    limit = dart_limit(bulk)
    went = bulk.recipients.filter(
        status__in=[RecipientStatus.SENT, RecipientStatus.BOUNCED, RecipientStatus.PENDING]
    ).values_list("round", "email", "user_id")
    seen: dict[int, set[str]] = {}
    latest: dict[int, int] = {}
    for number, address, user_id in went:
        seen.setdefault(number, set()).add(_folded(address))
        if user_id is not None:
            latest[user_id] = max(latest.get(user_id, number), number)
    answered = _answered(bulk) if any(row.round > 0 for row in rows) else set()
    queued: set[int] = set()
    retried = 0
    # Stable: within a round the rows keep the surname order the caller gave them.
    for row in sorted(rows, key=lambda candidate: -candidate.round):
        account = row.user
        in_round = seen.setdefault(row.round, set())
        if account is not None and (latest.get(account.pk, -1) > row.round or account.pk in queued):
            reason = SKIP_LATER_COPY
        elif account is not None and row.round > 0 and account.pk in answered:
            reason = SKIP_ANSWERED
        else:
            reason = skip_reason(account, in_round, opt_outs=opt_outs, limit=limit)
        if account is not None:
            row.name = account.display_name
            row.email = account.email
        row.updated_at = moment
        row.reason = reason[:REASON_MAX_LENGTH]
        if reason == "":
            row.status = RecipientStatus.PENDING
            in_round.add(_folded(row.email))
            if account is not None:
                queued.add(account.pk)
            retried += 1
        else:
            row.status = RecipientStatus.SKIPPED
    return retried, len(rows) - retried


def _answered(bulk: BulkEmail) -> set[int]:
    """The ids of the accounts that have answered ``bulk``'s callout, if it is one."""
    return set(
        CalloutAnswer.objects.filter(callout__bulk_email=bulk).values_list("user_id", flat=True)
    )


def _folded(address: str) -> str:
    """``address`` trimmed and case-folded, as the batch compares addresses."""
    return address.strip().casefold()


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
    (skipped, stopped, or not sent yet).  The copy is for the sender, not its
    recipient, so its unsubscribe link is inert: it carries no token that could turn
    the recipient's email off.
    """
    row = BulkEmailRecipient.objects.select_related("user").get(bulk_email=bulk, pk=recipient_id)
    if row.tried_at is None:
        raise DomainError(NOT_TRIED_MESSAGE)
    return RecipientCopy(recipient=row, copy=render_copy(bulk, row, inert=True))


def retried_count(bulk: BulkEmail) -> int:
    """How many copies **Retry failed** has queued again for ``bulk``, in all."""
    return sum(retry.count for retry in bulk.retries.all())


def set_hidden(bulk: BulkEmail, *, hidden: bool, actor: User) -> BulkEmail:
    """Keep ``bulk`` off every recipient's **Email to me** page, or put it back.

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
