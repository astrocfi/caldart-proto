"""A bulk email from its draft to its last copy, and the batch of people it goes to.

A :class:`BulkEmail` is one message CalDART management writes: a draft while it is
being written, ``queued`` once **Send** is pressed and until its start time arrives,
``sending`` while the background sender (``apps.bulk_email.job``) works through it,
and ``sent`` or ``stopped`` at the end.  Its people are a batch: every press of
**Add to batch** is a :class:`BatchAdd`, and every person an add brought in is a
:class:`BulkEmailRecipient` row, ``batched`` while the email is a draft.  When the
sender starts the email it freezes the batch: each row becomes ``pending``, or
``skipped`` with the reason, and each pending row then becomes ``sent``, ``failed``,
or ``stopped`` as the send goes on; a sent copy the bounce check later finds refused
becomes ``bounced``.  A :class:`BulkEmailRetry` is one press of **Retry failed**.  A
:class:`BulkEmailImage` is one image a sender put into a message, stored where every
copy links to it.

What CalDART management keeps to use again: an :class:`EmailTemplate` is a saved
message a draft can start from, and a :class:`RecipientGroup` a saved set of people a
batch can add, either the accounts themselves (:class:`RecipientGroupMember`, a fixed
group) or the filters that find them (:class:`RecipientGroupFilter`, a live group).
A mission callout is a bulk email with ``is_callout`` set and one :class:`Callout`
row, which collects each recipient's :class:`CalloutAnswer`.
"""

from __future__ import annotations

import uuid
from pathlib import PurePosixPath

from django.conf import settings
from django.db import models
from django.db.models.functions import Lower

from caldart.models import TimestampedModel

#: The longest name a recipient row keeps: a display name is a 150-character first
#: name, a space, and a 150-character last name, or an address of at most 254.
NAME_MAX_LENGTH = 301

#: The longest DART name a recipient row keeps, as long as ``Dart.name`` itself.
DART_NAME_MAX_LENGTH = 60

#: The longest name a saved template or a saved recipient group may have.
SAVED_NAME_MAX_LENGTH = 80

#: The longest label an add keeps: ``Copied from "<subject>"`` with a 200-character
#: subject fits.
ADD_LABEL_MAX_LENGTH = 220


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


#: The statuses in which an email's content, batch, and schedule can still change,
#: as long as it has never started sending (:attr:`BulkEmail.can_edit`).
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

    ``subject`` and ``body`` may be blank while it is a draft; ``body`` is HTML,
    sanitized on every save (``apps.bulk_email.richtext.sanitize``), and both may
    carry recipient field tokens such as ``{first_name}``
    (``apps.bulk_email.fields``).  ``sender`` owns the draft and sends it, null once
    that account is deleted.  ``email_type`` is the type of email it is
    (``apps.mail.models.EmailType``): null while a draft, required to send, and
    protected, so a type a bulk email names cannot be deleted.  ``dart`` is the DART a
    DART leader's email is limited to (``apps.bulk_email.senders``), recorded when the
    draft is made, at each add and **Send**, and when the send starts; it is null for
    CalDART management's email, and once that DART is deleted.  ``not_sent_reason``
    says why the background sender returned a queued email unsent, blank otherwise and
    once it is queued again.  ``reply_to`` is the address a recipient's reply goes to,
    blank for the default (``apps.bulk_email.reply_to``); **Send** stores the address
    the copies carry.  ``start_at`` is when the send begins: the end of the undo
    window or the time the sender chose, which ``scheduled`` says.
    ``confirm_count`` is the number of people the sender typed to confirm a large
    send, null when the batch was small enough to need none.

    ``started_at`` is when the background sender began, ``sent_at`` when the last copy
    had been tried, and ``stopped_at`` and ``stopped_by`` when and by whom a send was
    stopped part way.  ``stop_requested`` is how **Stop** reaches the sender, which
    reads it between copies.  The counts are kept as each copy is tried, and each
    counts the rows of that status: a copy the bounce check later finds refused moves
    from ``sent_count`` to ``bounced_count``, and **Retry failed** takes the copies it
    queues again out of ``failed_count``.  ``hidden_from_archive`` keeps a sent email
    off every recipient's **Messages** page without changing its history.  ``is_callout``
    marks a mission callout, whose copies carry the answer buttons and whose
    :class:`Callout` row holds when answers close (``apps.bulk_email.callouts``).
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
    email_type = models.ForeignKey(
        "mail.EmailType",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="bulk_emails",
    )
    dart = models.ForeignKey(
        "darts.Dart",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bulk_emails",
    )
    reply_to = models.EmailField(max_length=254, blank=True)
    start_at = models.DateTimeField(null=True, blank=True)
    scheduled = models.BooleanField(default=False)
    not_sent_reason = models.CharField(max_length=200, blank=True)
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
    bounced_count = models.PositiveIntegerField(default=0)
    hidden_from_archive = models.BooleanField(default=False)
    is_callout = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["status", "start_at"])]

    def __str__(self) -> str:
        """Return the subject, or ``"(no subject)"`` for a draft that has none yet."""
        return self.subject or "(no subject)"

    @property
    def can_edit(self) -> bool:
        """True while the content, batch, and schedule can still change.

        That is a draft or a queued email the sender has never started.  Once
        ``started_at`` is set the email holds copies that went, so it never becomes
        editable again, not even while **Send the rest** has it queued.
        """
        return self.status in EDITABLE_STATUSES and self.started_at is None


class BatchAdd(TimestampedModel):
    """One press of **Add to batch**: the filters given, and what they added.

    ``filters`` are the member list filters that carried a value.  ``added_count`` is
    how many people joined the batch and ``already_count`` how many the filters chose
    who were in it already.  ``group`` is the saved recipient group an add brought in,
    null for an add by filters and once the group is deleted.  ``label`` names an add
    that was not made with filters, such as ``Group: Board`` or ``Copied from
    "Spring newsletter"``, as it read when the add was made; it is blank for an add by
    filters, which is named by its filters.
    """

    bulk_email = models.ForeignKey(BulkEmail, on_delete=models.CASCADE, related_name="adds")
    filters = models.JSONField(default=dict, blank=True)
    group = models.ForeignKey(
        "RecipientGroup",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="adds",
    )
    label = models.CharField(max_length=ADD_LABEL_MAX_LENGTH, blank=True)
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
    is blank otherwise.  ``message_id`` is the ``Message-ID`` the copy went out with;
    on a pending copy it is that of the try being made, saved before the hand-over so a
    run that dies can tell whether it went.  ``tried_at`` is when it was last tried.
    ``values`` are the recipient field values the copy was filled in with, token to
    value, for the fields the message uses only; they are stored when the copy is
    tried, so the copy can be rebuilt as it went whatever happens to the account later.
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
    message_id = models.CharField(max_length=255, blank=True, db_index=True)
    tried_at = models.DateTimeField(null=True, blank=True)
    values = models.JSONField(default=dict, blank=True)

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


class BulkEmailRetry(models.Model):
    """One press of **Retry failed**: who asked, when, and how many copies it queued.

    Every ``failed`` copy of ``bulk_email`` went back to ``pending`` then, for the
    background sender to try again.  ``requested_by`` is null once that account is
    deleted.
    """

    bulk_email = models.ForeignKey(BulkEmail, on_delete=models.CASCADE, related_name="retries")
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bulk_email_retries",
    )
    requested_at = models.DateTimeField()
    count = models.PositiveIntegerField()

    class Meta:
        ordering = ["requested_at", "id"]

    def __str__(self) -> str:
        """Return ``"Retry of <count> copies of <bulk email id>"``."""
        return f"Retry of {self.count} copies of {self.bulk_email_id}"


#: The directory under ``MEDIA_ROOT`` a bulk email's images are stored in.
IMAGE_DIRECTORY = "bulk-email"


def bulk_email_image_path(instance: BulkEmailImage, filename: str) -> str:
    """Return where an image is stored: ``bulk-email/<uuid>.<ext>`` under ``MEDIA_ROOT``.

    The name is a fresh random UUID, so nobody can guess one image's address from
    another's and no upload ever replaces one already sent.  The extension is
    ``filename``'s, lower-cased.
    """
    suffix = PurePosixPath(filename).suffix.lower()
    return f"{IMAGE_DIRECTORY}/{uuid.uuid4().hex}{suffix}"


class BulkEmailImage(TimestampedModel):
    """One image a sender uploaded into a bulk email's message.

    ``file`` is the image as stored, after its type and size were checked and it was
    scaled to fit an email (``apps.bulk_email.images``); ``width`` and ``height`` are
    its stored size in pixels.  Every copy of the email links to the file by its
    absolute URL rather than carrying it, so the file stays where it is for as long
    as a sent copy may be read.  ``uploaded_by`` is the sender, null once that
    account is deleted.
    """

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bulk_email_images",
    )
    file = models.FileField(upload_to=bulk_email_image_path, max_length=100)
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        """Return the stored file's name, ``bulk-email/<uuid>.<ext>``."""
        return self.file.name or ""


class EmailTemplate(TimestampedModel):
    """A saved message that a draft can start from, shared by all CalDART management.

    ``name`` is unique, ignoring case.  ``subject`` and ``body`` are a message as a
    draft holds them: the body is sanitized HTML and both may carry recipient field
    tokens.  ``email_type`` is the type a draft started from it takes, null for none
    and once that type is deleted; ``reply_to`` is the Reply-To address it takes, blank
    for the default.  ``created_by`` is who saved it, null once that account is
    deleted, and ``updated_at`` when it last changed.
    """

    name = models.CharField(max_length=SAVED_NAME_MAX_LENGTH)
    subject = models.CharField(max_length=200, blank=True)
    body = models.TextField(blank=True)
    email_type = models.ForeignKey(
        "mail.EmailType",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bulk_email_templates",
    )
    reply_to = models.EmailField(max_length=254, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bulk_email_templates",
    )

    class Meta:
        ordering = [Lower("name"), "id"]
        constraints = [
            models.UniqueConstraint(Lower("name"), name="bulk_email_template_name_unique"),
        ]

    def __str__(self) -> str:
        """Return the template's name."""
        return self.name


class GroupKind(models.TextChoices):
    """How a saved recipient group holds its people.

    A ``fixed`` group is a list of accounts, which changes only when somebody adds or
    removes one.  A ``live`` group is a list of member list filter sets, run afresh
    each time the group is used, so it follows the membership as it changes.
    """

    FIXED = "fixed", "Fixed"
    LIVE = "live", "Live"


class RecipientGroup(TimestampedModel):
    """A saved set of people a bulk email's batch can add, shared by CalDART management.

    ``name`` is unique, ignoring case.  ``kind`` says whether the group holds accounts
    (``fixed``, :class:`RecipientGroupMember`) or filter sets (``live``,
    :class:`RecipientGroupFilter`); it does not change after the group is made.
    ``created_by`` is who saved it, null once that account is deleted, and
    ``updated_at`` when it, its people, or its filters last changed.
    """

    name = models.CharField(max_length=SAVED_NAME_MAX_LENGTH)
    kind = models.CharField(max_length=5, choices=GroupKind.choices)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bulk_email_groups",
    )

    class Meta:
        ordering = [Lower("name"), "id"]
        constraints = [
            models.UniqueConstraint(Lower("name"), name="bulk_email_group_name_unique"),
        ]

    def __str__(self) -> str:
        """Return the group's name."""
        return self.name


class RecipientGroupMember(TimestampedModel):
    """One account in a fixed recipient group; deleting the account takes it out."""

    group = models.ForeignKey(RecipientGroup, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bulk_email_group_memberships",
    )

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["group", "user"], name="bulk_email_group_member_once"),
        ]

    def __str__(self) -> str:
        """Return ``"<account id> in <group>"``."""
        return f"{self.user_id} in {self.group_id}"


class RecipientGroupFilter(TimestampedModel):
    """One filter set of a live recipient group: member list filters as an add takes them.

    ``filters`` are the member list filters that carried a value; an empty set chooses
    every member and friend.  ``position`` orders the sets on the group's page.
    """

    group = models.ForeignKey(RecipientGroup, on_delete=models.CASCADE, related_name="filter_sets")
    filters = models.JSONField(default=dict, blank=True)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self) -> str:
        """Return ``"Filters <id> of <group>"``."""
        return f"Filters {self.pk} of {self.group_id}"


class CalloutAnswerKind(models.TextChoices):
    """What a recipient of a mission callout answered: whether they can fly."""

    AVAILABLE = "available", "Available"
    LIMITED = "limited", "Available with limits"
    UNAVAILABLE = "unavailable", "Not available"


class Callout(models.Model):
    """The answers side of a mission callout: one per bulk email with ``is_callout`` set.

    ``closes_at`` is when answers stop being taken; ``closed_at`` and ``closed_by`` say
    when, and by whom, **Close now** closed it sooner, null while nobody has.
    ``closed_by`` is null as well once that account is deleted.  ``reminded_at`` is
    when **Remind non-responders** last queued a round of reminders, null before the
    first.  A callout whose ``closes_at`` has passed, or whose ``closed_at`` is set,
    takes no answer.
    """

    bulk_email = models.OneToOneField(BulkEmail, on_delete=models.CASCADE, related_name="callout")
    closes_at = models.DateTimeField()
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="callouts_closed",
    )
    reminded_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        """Return ``"Callout <bulk email id>"``."""
        return f"Callout {self.bulk_email_id}"


class CalloutAnswer(models.Model):
    """One recipient's answer to a mission callout, which they may change until it closes.

    ``answer`` is one of :class:`CalloutAnswerKind`, ``note`` what they added, such as
    *can fly Saturday only*, and ``answered_at`` when they last sent it.  Each person
    answers a callout once; a later answer replaces the earlier one.
    """

    callout = models.ForeignKey(Callout, on_delete=models.CASCADE, related_name="answers")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="callout_answers"
    )
    answer = models.CharField(max_length=11, choices=CalloutAnswerKind.choices)
    note = models.CharField(max_length=500, blank=True)
    answered_at = models.DateTimeField()

    class Meta:
        ordering = ["answered_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["callout", "user"], name="callout_answer_once")
        ]

    def __str__(self) -> str:
        """Return ``"<user id>: <answer>"``."""
        return f"{self.user_id}: {self.answer}"
