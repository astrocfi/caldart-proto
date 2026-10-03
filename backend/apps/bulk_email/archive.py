"""The **Messages** page: the bulk emails a person received, each as their own copy.

A bulk email lives in each recipient's mailbox, so one deleted or one that reads badly
in a mail program could not be read again.  Every signed-in person can read the bulk
emails they were sent on the portal's **Messages** page instead, and the **View this
email in your browser** link in every copy opens the same page
(``apps.bulk_email.render.view_url``).

:func:`messages_for` lists the emails whose copy reached the mail server for the reader
(``sent``, or ``bounced`` afterwards), newest first; :func:`message_for` is one of them.
Each is the reader's own copy, filled in from the values stored on the reader's own
recipient row when it went, never from the profile as it is now and never from anybody
else's row.  Only bulk email is here: receipts, reminders, and other mail about the
person's own account are not.  An email CalDART management has hidden
(``BulkEmail.hidden_from_archive``) is not listed and cannot be opened, though its
history stays.  There is no way to show a message to anybody it was not sent to.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db.models import QuerySet

from apps.accounts.models import User
from apps.bulk_email.models import BulkEmail, BulkEmailRecipient, RecipientStatus
from apps.bulk_email.render import RenderedCopy, fill_subject, render_copy, stored_values
from caldart.mail import org_name

#: The statuses of a copy that reached the mail server for its reader.
RECEIVED_STATUSES: frozenset[str] = frozenset({RecipientStatus.SENT, RecipientStatus.BOUNCED})


@dataclass(frozen=True)
class Message:
    """One bulk email as its reader received it.

    ``bulk`` is the email and ``recipient`` the reader's own row, the copy most recently
    sent to them.  ``subject`` is the subject as their copy had it, filled in from the
    row's stored values.
    """

    bulk: BulkEmail
    recipient: BulkEmailRecipient
    subject: str

    @property
    def from_name(self) -> str:
        """The sender's name, or the organization's once the sender's account is gone."""
        return self.bulk.sender.display_name if self.bulk.sender is not None else org_name()


@dataclass(frozen=True)
class OpenedMessage:
    """One message opened: the :class:`Message` and the reader's copy as it went."""

    message: Message
    copy: RenderedCopy


def messages_for(user: User) -> list[Message]:
    """Every bulk email ``user`` received and may read, the most recently sent first.

    One per email, from the reader's copy most recently sent: an email reaches the list
    when one of its recipient rows names ``user`` and reads ``sent`` or ``bounced``, and
    is not hidden from the archive.  A skipped, failed, stopped, or unsent copy is not
    one the reader received.
    """
    messages: list[Message] = []
    seen: set[int] = set()
    for row in _received(user).order_by("-tried_at", "-pk"):
        if row.bulk_email_id in seen:
            continue
        seen.add(row.bulk_email_id)
        messages.append(_message(row))
    return messages


def message_for(user: User, pk: int) -> OpenedMessage:
    """The bulk email ``pk`` as ``user`` received it, with their copy rebuilt as it went.

    The copy is ``apps.bulk_email.render.render_copy`` of the reader's own row, filled
    in from the values stored on it.  Raises ``BulkEmailRecipient.DoesNotExist`` when
    ``user`` did not receive that email, or it is hidden from the archive.
    """
    row = _received(user).filter(bulk_email_id=pk).order_by("-tried_at", "-pk").first()
    if row is None:
        raise BulkEmailRecipient.DoesNotExist
    message = _message(row)
    return OpenedMessage(message=message, copy=render_copy(message.bulk, row))


def _received(user: User) -> QuerySet[BulkEmailRecipient]:
    """``user``'s rows whose copy reached the mail server, of emails not hidden."""
    return BulkEmailRecipient.objects.filter(
        user=user,
        status__in=RECEIVED_STATUSES,
        tried_at__isnull=False,
        bulk_email__hidden_from_archive=False,
    ).select_related("user", "bulk_email", "bulk_email__sender", "bulk_email__email_type")


def _message(row: BulkEmailRecipient) -> Message:
    """The :class:`Message` of the reader's row ``row``."""
    bulk = row.bulk_email
    return Message(
        bulk=bulk,
        recipient=row,
        subject=fill_subject(bulk.subject, stored_values(bulk, row)),
    )
