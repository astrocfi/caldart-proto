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
    """Whether the mail server took the message or refused it."""

    SENT = "sent", "Sent"
    FAILED = "failed", "Failed"


class EmailLog(TimestampedModel):
    """One email the system tried to send, successfully or not.

    ``purpose`` is the template the body came from -- ``reminder_t30``,
    ``renewal_notice``, ``receipt``, ``refund``, ``member_invitation``,
    ``password_reset`` and the rest -- so a row says what kind of message it
    was without reading the subject.  ``user`` is the account the email
    concerned, and is null for a message sent to an address with no account and
    for one whose account has since been deleted.  ``error`` carries the
    exception class of a refusal and is blank on a successful send;
    ``attachments`` lists the filenames that rode along, comma-separated, and
    is blank when none did.
    """

    to_email = models.EmailField()
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
    status = models.CharField(max_length=6, choices=EmailStatus.choices, default=EmailStatus.SENT)
    error = models.CharField(max_length=100, blank=True)
    attachments = models.CharField(max_length=255, blank=True)

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
