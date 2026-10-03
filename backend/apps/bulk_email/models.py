"""A bulk email from its draft to its last copy, and the batch of people it goes to.

A :class:`BulkEmail` is one message CalDART management writes: a draft while it is
being written, ``queued`` once **Send** is pressed and until its start time arrives,
``sending`` while the background sender (``apps.bulk_email.job``) works through it,
and ``sent`` or ``stopped`` at the end.  Its people are a batch: every press of
**Add to batch** is a :class:`BatchAdd`, and every person an add brought in is a
:class:`BulkEmailRecipient` row, ``batched`` while the email is a draft.  When the
sender starts the email it freezes the batch: each row becomes ``pending``, or
``skipped`` with the reason, and each pending row then becomes ``sent``, ``failed``,
or ``stopped`` as the send goes on.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from caldart.models import TimestampedModel

#: The longest name a recipient row keeps: a display name is a 150-character first
#: name, a space, and a 150-character last name, or an address of at most 254.
NAME_MAX_LENGTH = 301

#: The longest DART name a recipient row keeps, as long as ``Dart.name`` itself.
DART_NAME_MAX_LENGTH = 60


class BulkEmailStatus(models.TextChoices):
    """Where a bulk email stands, from its draft to its last copy.

    ``draft`` and ``queued`` can still be changed; ``queued`` has a ``start_at``, the
    end of the undo window or the scheduled time.  ``sending`` is the background
    sender at work, and ``sent`` and ``stopped`` are the two ways it ends.
    """

    DRAFT = "draft", "Draft"
    QUEUED = "queued", "Waiting to send"
    SENDING = "sending", "Sending"
    SENT = "sent", "Sent"
    STOPPED = "stopped", "Stopped"


#: The statuses in which an email's content, batch, and schedule can still change.
EDITABLE_STATUSES: frozenset[str] = frozenset({BulkEmailStatus.DRAFT, BulkEmailStatus.QUEUED})


class RecipientStatus(models.TextChoices):
    """Where one person's copy of a bulk email stands.

    ``batched`` is a row of an email not yet started, whose skip reason is worked out
    afresh whenever the batch is read.  Starting the send turns each into ``pending``
    or ``skipped``; the sender turns each pending row into ``sent`` or ``failed``, and
    a stop turns the rest into ``stopped``.  ``bounced`` is a copy that went and came
    back.
    """

    BATCHED = "batched", "In the batch"
    PENDING = "pending", "Not sent yet"
    SENT = "sent", "Sent"
    FAILED = "failed", "Failed"
    SKIPPED = "skipped", "Skipped"
    STOPPED = "stopped", "Not sent (stopped)"
    BOUNCED = "bounced", "Bounced"


class RecipientKind(models.TextChoices):
    """Whether a person was a member or a friend of CalDART when they joined the batch."""

    MEMBER = "member", "Member"
    FRIEND = "friend", "Friend"


class BulkEmail(TimestampedModel):
    """One email to a batch of members and friends, from its draft to its last copy.

    ``subject`` and ``body`` may be blank while it is a draft; ``body`` is plain text
    whose blank lines separate paragraphs.  ``sender`` owns the draft and sends it,
    null once that account is deleted.  ``start_at`` is when the send begins: the end
    of the undo window or the time the sender chose, which ``scheduled`` says.
    ``confirm_count`` is the number of people the sender typed to confirm a large
    send, null when the batch was small enough to need none.

    ``started_at`` is when the background sender began, ``sent_at`` when the last copy
    had been tried, and ``stopped_at`` and ``stopped_by`` when and by whom a send was
    stopped part way.  ``stop_requested`` is how **Stop** reaches the sender, which
    reads it between copies.  The counts are kept as each copy is tried.
    """

    subject = models.CharField(max_length=200, blank=True)
    body = models.TextField(blank=True)
    status = models.CharField(
        max_length=7, choices=BulkEmailStatus.choices, default=BulkEmailStatus.DRAFT
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bulk_emails_sent",
    )
    start_at = models.DateTimeField(null=True, blank=True)
    scheduled = models.BooleanField(default=False)
    confirm_count = models.PositiveIntegerField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    stopped_at = models.DateTimeField(null=True, blank=True)
    stopped_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bulk_emails_stopped",
    )
    stop_requested = models.BooleanField(default=False)
    sent_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["status", "start_at"])]

    def __str__(self) -> str:
        """Return the subject, or ``"(no subject)"`` for a draft that has none yet."""
        return self.subject or "(no subject)"

    @property
    def can_edit(self) -> bool:
        """True while the content, batch, and schedule can still change."""
        return self.status in EDITABLE_STATUSES


class BatchAdd(TimestampedModel):
    """One press of **Add to batch**: the filters given, and what they added.

    ``filters`` are the member list filters that carried a value.  ``added_count`` is
    how many people joined the batch and ``already_count`` how many the filters chose
    who were in it already.
    """

    bulk_email = models.ForeignKey(BulkEmail, on_delete=models.CASCADE, related_name="adds")
    filters = models.JSONField(default=dict, blank=True)
    added_count = models.PositiveIntegerField(default=0)
    already_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        """Return ``"Add <id> to <bulk email>"``."""
        return f"Add {self.pk} to {self.bulk_email_id}"


class BulkEmailRecipient(TimestampedModel):
    """One person in a bulk email's batch, and what became of their copy.

    ``user`` is the account, null once it is deleted.  ``name``, ``email``, ``kind``,
    and ``dart_name`` are the account's as they were when it joined the batch, and are
    brought up to date when the send starts, so the history keeps what each copy went
    to whatever happens to the account later.  ``email`` is not validated, since an
    invalid address is the reason a copy is skipped.

    ``added_by`` is the add that brought the person in.  ``round`` is 0 for the
    original copies.  ``reason`` says why a copy was skipped, failed, or not sent, and
    is blank otherwise.  ``message_id`` is the ``Message-ID`` the copy went out with,
    and ``tried_at`` when it was last tried.
    """

    bulk_email = models.ForeignKey(BulkEmail, on_delete=models.CASCADE, related_name="recipients")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bulk_emails_received",
    )
    name = models.CharField(max_length=NAME_MAX_LENGTH, blank=True)
    email = models.CharField(max_length=254, blank=True)
    kind = models.CharField(max_length=6, choices=RecipientKind.choices, blank=True)
    dart_name = models.CharField(max_length=DART_NAME_MAX_LENGTH, blank=True)
    added_by = models.ForeignKey(
        BatchAdd,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recipients",
    )
    round = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(
        max_length=7, choices=RecipientStatus.choices, default=RecipientStatus.BATCHED
    )
    reason = models.CharField(max_length=200, blank=True)
    message_id = models.CharField(max_length=255, blank=True)
    tried_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            # One row per account per round: an account already in the batch is not
            # added twice, however many adds choose it.
            models.UniqueConstraint(
                fields=["bulk_email", "user", "round"],
                condition=models.Q(user__isnull=False),
                name="bulk_email_recipient_once_per_round",
            )
        ]
        indexes = [models.Index(fields=["bulk_email", "status"])]

    def __str__(self) -> str:
        """Return ``"<email>: <status>"``."""
        return f"{self.email}: {self.status}"
