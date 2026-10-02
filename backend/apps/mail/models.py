"""The record of every email the installation has sent.

One model, :class:`EmailLog`, written by ``caldart.mail.send_templated`` after
each send.  It answers "what did the system say to this member, and did it
arrive?" for an operator, which no other table does: a reminder log row is the
key that keeps a stage from repeating, not a record of the message.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from caldart.models import TimestampedModel


class EmailStatus(models.TextChoices):
    """Whether the mail server took the message, refused it, or later bounced it.

    ``bounced`` replaces ``sent`` when the bounce check reads a permanent-failure report
    for the message from the bounce mailbox: the relay took it, but the recipient's
    server refused it afterwards.
    """

    SENT = "sent", "Sent"
    FAILED = "failed", "Failed"
    BOUNCED = "bounced", "Bounced"


class EmailLog(TimestampedModel):
    """One email the system tried to send, successfully or not.

    ``purpose`` is the template the body came from -- ``reminder_second``,
    ``renewal_notice``, ``receipt``, ``refund``, ``member_invitation``,
    ``password_reset`` and the rest -- so a row says what kind of message it
    was without reading the subject.  ``user`` is the account the email
    concerned, and is null for a message sent to an address with no account and
    for one whose account has since been deleted.  ``to_name`` is the
    recipient's name as it was at send time -- a DART contact's name, or an
    account holder's display name -- and is blank for a message sent to a bare
    address nobody named.  ``error`` carries the exception class of a refusal
    and is blank on a successful send; ``attachments`` lists the filenames
    that rode along, comma-separated, and is blank when none did.

    ``message_id`` is the ``Message-ID`` header the message went out with, angle
    brackets included, which is how a bounce report is matched back to its row.
    ``bounced_at`` is when the bounce check read a permanent-failure report for the
    message, and ``bounce_detail`` that report's status code and diagnostic text; both
    are empty unless ``status`` is ``bounced``.
    """

    to_email = models.EmailField()
    to_name = models.CharField(max_length=200, blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="email_logs",
    )
    purpose = models.SlugField(max_length=64)
    subject = models.CharField(max_length=255)
    sent_at = models.DateTimeField()
    status = models.CharField(max_length=7, choices=EmailStatus.choices, default=EmailStatus.SENT)
    error = models.CharField(max_length=100, blank=True)
    attachments = models.CharField(max_length=255, blank=True)
    message_id = models.CharField(max_length=255, blank=True, db_index=True)
    bounced_at = models.DateTimeField(null=True, blank=True)
    bounce_detail = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-sent_at", "-id"]
        verbose_name = "email log entry"
        verbose_name_plural = "email log entries"
        indexes = [
            models.Index(fields=["purpose", "-sent_at"], name="mail_purpose_sent_idx"),
            models.Index(fields=["user", "-sent_at"], name="mail_user_sent_idx"),
        ]

    def __str__(self) -> str:
        """Return ``"<purpose> to <address> on <sent_at date> (<status>)"``."""
        return f"{self.purpose} to {self.to_email} on {self.sent_at:%Y-%m-%d} ({self.status})"

    @property
    def recipient_name(self) -> str:
        """The name to show for this row: ``to_name``, or the account's own name.

        Falls back to the linked account's current ``display_name`` when ``to_name``
        is blank, and to ``""`` when there is no account either.
        """
        if self.to_name:
            return self.to_name
        return self.user.display_name if self.user is not None else ""
