"""The record of every email the installation has sent, and the kinds of bulk email.

:class:`EmailLog` is written by ``caldart.mail.send_templated`` after each send.  It
answers "what did the system say to this member, and did it arrive?" for an operator,
which no other table does: a reminder log row is the key that keeps a stage from
repeating, not a record of the message.

:class:`EmailType` is a kind of bulk email a system administrator configures, and
:class:`EmailOptOut` one person's choice not to receive one of them.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db import models
from django.utils.text import slugify

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


class EmailType(TimestampedModel):
    """A kind of bulk email, such as Operational, Fundraising, or Mission.

    A system administrator keeps the types on the Email types screen.  ``name`` is what
    every screen and every email calls the type, and ``slug`` is ``name`` slugified,
    kept in step on every save; both are unique.  ``description`` says what the type is
    for, in a sentence a member reads beside the switch that turns it off.

    ``allow_opt_out`` decides whether a recipient may turn the type off.  A type that
    allows it carries the unsubscribe headers and footer link; one that does not carries
    neither, and its footer says why the recipient receives it.  Turning it off leaves
    every recorded :class:`EmailOptOut` in place, unapplied, so turning it back on
    restores each one.

    ``sender_roles`` is the list of role slugs whose holders may send the type; a system
    administrator sends every type whatever it names.  ``position`` orders the types on
    every screen, then ``name``.
    """

    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=60, unique=True)
    description = models.TextField()
    allow_opt_out = models.BooleanField(default=True)
    sender_roles = models.JSONField(default=list, blank=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "name"]

    def __str__(self) -> str:
        """Return the type's ``name``."""
        return self.name

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Set ``slug`` from ``name``, then save."""
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class OptOutSource(models.TextChoices):
    """Where an opt-out was recorded.

    ``profile`` is the person's own Email preferences screen, ``unsubscribe`` the
    signed link in an email (or a mail program's one-click unsubscribe button), and
    ``admin`` an account administrator on the member record.
    """

    PROFILE = "profile", "Email preferences"
    UNSUBSCRIBE = "unsubscribe", "Unsubscribe link"
    ADMIN = "admin", "Account administrator"


class EmailOptOut(TimestampedModel):
    """One person's choice not to receive one type of bulk email.

    A row means opted out and its absence opted in, so a new account starts opted in to
    every type.  A row for a type whose ``allow_opt_out`` is off stays in place but does
    not apply until the type allows opt-out again.  ``source`` says where the choice was
    made, and ``created_at`` when.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="email_opt_outs"
    )
    email_type = models.ForeignKey(EmailType, on_delete=models.CASCADE, related_name="opt_outs")
    source = models.CharField(max_length=11, choices=OptOutSource.choices)

    class Meta:
        ordering = ["email_type__position", "email_type__name"]
        constraints = [
            models.UniqueConstraint(fields=["user", "email_type"], name="mail_opt_out_unique"),
        ]

    def __str__(self) -> str:
        """Return ``"<user id> opted out of <type name>"``."""
        return f"{self.user_id} opted out of {self.email_type.name}"
