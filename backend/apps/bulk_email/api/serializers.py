"""Serializers for the bulk email endpoints."""

from __future__ import annotations

import unicodedata
from datetime import datetime
from typing import Any, TypedDict

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from apps.bulk_email.batch import (
    AddResult,
    BatchCounts,
    BatchRow,
    add_label,
    batch_counts,
    batch_rows,
    email_type_name,
    given_filters,
    selected_accounts,
    unknown_filters,
)
from apps.bulk_email.drafts import NOT_SENDABLE_MESSAGE
from apps.bulk_email.job import estimated_finish
from apps.bulk_email.models import (
    BatchAdd,
    BulkEmail,
    BulkEmailStatus,
    RecipientStatus,
)
from apps.bulk_email.render import body_problem, render_message, subject_problem
from apps.bulk_email.reply_to import default_reply_to
from apps.bulk_email.richtext import sanitize
from apps.bulk_email.senders import email_dart_name, sender_notice
from apps.mail.models import EmailType
from apps.mail.types import sendable_types
from caldart.runs import RunActionSerializer

#: What a filter the member list does not have is refused with.
UNKNOWN_FILTER_MESSAGE = "Not a filter of the member list."

#: What a subject that breaks a line is refused with.
ONE_LINE_MESSAGE = "A subject is one line."

#: What a subject carrying a control character, such as a tab, is refused with.
CONTROL_MESSAGE = "A subject cannot carry control characters such as tabs."

#: Unicode's category of control characters.
CONTROL_CATEGORY = "Cc"

#: The longest message a bulk email carries, in characters of HTML.
MAX_BODY_LENGTH = 100_000


def checked_filters(filters: dict[str, str]) -> dict[str, str]:
    """``filters`` as an add stores them, once the member list accepts them.

    Raises ``ValidationError`` keyed by each filter the member list does not have,
    with :data:`UNKNOWN_FILTER_MESSAGE`, and then keyed by each filter whose value the
    member list refuses, with the list's own message.  Blank filters are dropped from
    the answer.
    """
    unknown = unknown_filters(filters)
    if len(unknown) > 0:
        raise ValidationError({key: [UNKNOWN_FILTER_MESSAGE] for key in unknown})
    # Building the queryset runs the member list's own filter checks.
    selected_accounts(filters)
    return given_filters(filters)


def sender_name(bulk: BulkEmail) -> str:
    """The sender's display name, or ``""`` once the account is gone."""
    return bulk.sender.display_name if bulk.sender is not None else ""


class BulkEmailUpdateSerializer(serializers.Serializer[dict[str, Any]]):
    """``PATCH /bulk-email/{id}``'s body: the fields of the message to change.

    Every field may be left out.  ``subject`` is one line of at most 200 characters,
    free of control characters, and ``body`` HTML of at most :data:`MAX_BODY_LENGTH`
    characters, saved sanitized; both may be blank while the email is a draft, and
    both are trimmed.  Either is refused when a recipient field token in it cannot be
    filled in (``apps.bulk_email.render.check_message``).  ``email_type`` is the id of
    a type the caller may send (``GET /email-types/sendable``); any other is refused
    with :data:`apps.bulk_email.drafts.NOT_SENDABLE_MESSAGE`.  ``reply_to`` is a valid
    email address, trimmed, or blank for the default
    (``apps.bulk_email.reply_to.default_reply_to``).  The caller is the context's
    ``user``.
    """

    subject = serializers.CharField(max_length=200, allow_blank=True, required=False)
    body = serializers.CharField(max_length=MAX_BODY_LENGTH, allow_blank=True, required=False)
    email_type = serializers.PrimaryKeyRelatedField(
        queryset=EmailType.objects.all(), required=False
    )
    reply_to = serializers.EmailField(max_length=254, allow_blank=True, required=False)

    def validate_email_type(self, value: EmailType) -> EmailType:
        """Refuse a type the caller may not send."""
        if value not in sendable_types(self.context["user"]):
            raise ValidationError(NOT_SENDABLE_MESSAGE.format(type=value.name))
        return value

    def validate_subject(self, value: str) -> str:
        """Refuse a subject that breaks a line, or carries any other control character.

        A line break is any character ``str.splitlines`` splits on, the Unicode line
        and paragraph separators among them; a control character is one in Unicode's
        ``Cc`` category.  The mail library refuses both in a header.
        """
        if value != "" and value.splitlines() != [value]:
            raise ValidationError(ONE_LINE_MESSAGE)
        if any(unicodedata.category(character) == CONTROL_CATEGORY for character in value):
            raise ValidationError(CONTROL_MESSAGE)
        problem = subject_problem(value)
        if problem is not None:
            raise ValidationError(problem)
        return value

    def validate_body(self, value: str) -> str:
        """Sanitize the message, and refuse one with a token that cannot be filled in."""
        problem = body_problem(value)
        if problem is not None:
            raise ValidationError(problem)
        return sanitize(value)


class BulkEmailAddSerializer(serializers.Serializer[dict[str, Any]]):
    """``POST /bulk-email/{id}/batch/add``'s body: the member list filters to add by.

    ``filters`` are the member list's query parameters, blank ones ignored; left out,
    or empty, it adds every member and friend.
    """

    filters = serializers.DictField(
        child=serializers.CharField(allow_blank=True), required=False, default=dict
    )

    def validate_filters(self, value: dict[str, str]) -> dict[str, str]:
        """Refuse a filter the member list does not have, or a value it refuses."""
        return checked_filters(value)


class BulkEmailAddResultSerializer(serializers.Serializer[AddResult]):
    """What one add did: who joined, who was there already, and the batch's size."""

    added = serializers.IntegerField()
    already_present = serializers.IntegerField()
    count = serializers.IntegerField()


class BulkEmailSendSerializer(serializers.Serializer[dict[str, Any]]):
    """``POST /bulk-email/{id}/send``'s body.

    ``confirm_count`` is the number of people the sender typed, needed only above
    ``BULK_EMAIL_CONFIRM_ABOVE``.  ``start_at`` is when to send, null or left out to
    send once the undo window ends; a time given without an offset is read in the
    site's time zone.
    """

    confirm_count = serializers.IntegerField(min_value=0, required=False, allow_null=True)
    start_at = serializers.DateTimeField(required=False, allow_null=True)


class BulkEmailDetailSerializer(serializers.ModelSerializer[BulkEmail]):
    """One bulk email with everything the compose and detail screens show.

    ``sender`` and ``stopped_by`` are display names, blank when there is none or the
    account is gone.  ``batch_count`` is how many people are in the batch,
    ``receiving_count`` how many of them receive a copy, and ``batch_skipped_count``
    how many do not.  ``remaining`` counts the copies waiting to be sent, and
    ``estimated_finish_at`` is when the last will have gone while the email is
    sending, else null.  ``message_html`` is the whole HTML email as the history
    shows it: the message inside the house layout, its tokens as written.
    ``can_edit`` is true while it is a draft or queued,
    ``confirm_above`` is the batch size above which **Send** asks for the count, and
    ``undo_seconds`` is the undo window the countdown runs over.  ``email_type`` is the
    type's id, null while none is chosen, and ``email_type_name`` its name, blank then.
    ``not_sent_reason`` is why the background sender returned the email unsent, blank
    otherwise.  ``dart_name`` is the DART a DART leader's email goes to, blank for
    CalDART management's (``apps.bulk_email.senders.email_dart_name``).
    ``sender_notice`` says why nobody can be added to the email, naming its sender, while
    it is limited to no DART, and is blank otherwise
    (``apps.bulk_email.senders.sender_notice``).  ``reply_to`` is the address replies
    go to, blank for the default, and ``default_reply_to`` that default for the email's
    sender; once the email is queued ``reply_to`` is the address its copies carry.
    """

    email_type_name = serializers.SerializerMethodField()
    dart_name = serializers.SerializerMethodField()
    sender_notice = serializers.SerializerMethodField()
    default_reply_to = serializers.SerializerMethodField()

    sender = serializers.SerializerMethodField()
    stopped_by = serializers.SerializerMethodField()
    can_edit = serializers.BooleanField(read_only=True)
    batch_count = serializers.SerializerMethodField()
    receiving_count = serializers.SerializerMethodField()
    batch_skipped_count = serializers.SerializerMethodField()
    remaining = serializers.SerializerMethodField()
    estimated_finish_at = serializers.SerializerMethodField()
    confirm_above = serializers.SerializerMethodField()
    undo_seconds = serializers.SerializerMethodField()
    message_html = serializers.SerializerMethodField()

    # The email whose batch was last counted, and its counts: the three count fields
    # read one batch, so it is read once.
    _counted: tuple[int, BatchCounts] | None = None

    class Meta:
        model = BulkEmail
        fields = [
            "id",
            "subject",
            "body",
            "email_type",
            "email_type_name",
            "not_sent_reason",
            "reply_to",
            "default_reply_to",
            "status",
            "sender",
            "sender_id",
            "dart_name",
            "sender_notice",
            "created_at",
            "updated_at",
            "start_at",
            "scheduled",
            "confirm_count",
            "started_at",
            "sent_at",
            "stopped_at",
            "stopped_by",
            "stop_requested",
            "sent_count",
            "failed_count",
            "skipped_count",
            "can_edit",
            "batch_count",
            "receiving_count",
            "batch_skipped_count",
            "remaining",
            "estimated_finish_at",
            "confirm_above",
            "undo_seconds",
            "message_html",
        ]
        read_only_fields = fields

    def _counts(self, bulk: BulkEmail) -> BatchCounts:
        """The batch's counts, worked out once per email this serializer renders."""
        if self._counted is None or self._counted[0] != bulk.pk:
            self._counted = (bulk.pk, batch_counts(batch_rows(bulk)))
        return self._counted[1]

    def get_sender(self, bulk: BulkEmail) -> str:
        """The sender's display name, or ``""`` once the account is gone."""
        return sender_name(bulk)

    def get_email_type_name(self, bulk: BulkEmail) -> str:
        """The type's name, or ``""`` while none is chosen."""
        return email_type_name(bulk)

    def get_dart_name(self, bulk: BulkEmail) -> str:
        """The DART a DART leader's email goes to, or ``""`` for anybody."""
        return email_dart_name(bulk)

    def get_sender_notice(self, bulk: BulkEmail) -> str:
        """Why nobody can be added to the email, or ``""`` when somebody can."""
        return sender_notice(bulk)

    def get_default_reply_to(self, bulk: BulkEmail) -> str:
        """Where replies go when ``reply_to`` is blank, for the email's sender."""
        return default_reply_to(bulk.sender)

    def get_stopped_by(self, bulk: BulkEmail) -> str:
        """Who pressed **Stop**, or ``""`` when nobody did or the account is gone."""
        return bulk.stopped_by.display_name if bulk.stopped_by is not None else ""

    def get_batch_count(self, bulk: BulkEmail) -> int:
        """How many people are in the batch."""
        return self._counts(bulk).count

    def get_receiving_count(self, bulk: BulkEmail) -> int:
        """How many people in the batch receive a copy."""
        return self._counts(bulk).receiving

    def get_batch_skipped_count(self, bulk: BulkEmail) -> int:
        """How many people in the batch receive no copy."""
        return self._counts(bulk).skipped

    def get_remaining(self, bulk: BulkEmail) -> int:
        """How many copies are waiting to be sent."""
        return bulk.recipients.filter(status=RecipientStatus.PENDING).count()

    def get_estimated_finish_at(self, bulk: BulkEmail) -> datetime | None:
        """When the last copy will have gone, while the email is sending; else null."""
        if bulk.status != BulkEmailStatus.SENDING:
            return None
        return timezone.localtime(estimated_finish(self.get_remaining(bulk), timezone.now()))

    def get_confirm_above(self, bulk: BulkEmail) -> int:
        """The batch size above which **Send** asks for the count to be typed."""
        return int(settings.BULK_EMAIL_CONFIRM_ABOVE)

    def get_undo_seconds(self, bulk: BulkEmail) -> int:
        """The undo window: the seconds between **Send** and the first copy."""
        return int(settings.BULK_EMAIL_UNDO_SECONDS)

    def get_message_html(self, bulk: BulkEmail) -> str:
        """The whole HTML email, its recipient field tokens as written."""
        return render_message(bulk.subject, bulk.body, None).html


class BulkEmailSummarySerializer(serializers.ModelSerializer[BulkEmail]):
    """One bulk email as the Drafts & scheduled and the Sent lists show it.

    ``batch_count`` is how many people are in the batch and ``remaining`` how many
    copies are waiting to be sent; both come from the list's own annotations.
    ``email_type_name`` is the type's name, blank while none is chosen, and
    ``not_sent_reason`` why the background sender returned the email unsent, blank
    otherwise.  ``dart_name`` is the DART recorded as the one a DART leader's email
    goes to, blank for CalDART management's.
    """

    sender = serializers.SerializerMethodField()
    email_type_name = serializers.SerializerMethodField()
    dart_name = serializers.SerializerMethodField()
    batch_count = serializers.IntegerField(read_only=True)
    remaining = serializers.IntegerField(read_only=True)

    class Meta:
        model = BulkEmail
        fields = [
            "id",
            "subject",
            "email_type_name",
            "not_sent_reason",
            "status",
            "sender",
            "dart_name",
            "created_at",
            "updated_at",
            "start_at",
            "scheduled",
            "started_at",
            "sent_at",
            "stopped_at",
            "stop_requested",
            "sent_count",
            "failed_count",
            "skipped_count",
            "batch_count",
            "remaining",
        ]
        read_only_fields = fields

    def get_sender(self, bulk: BulkEmail) -> str:
        """The sender's display name, or ``""`` once the account is gone."""
        return sender_name(bulk)

    def get_email_type_name(self, bulk: BulkEmail) -> str:
        """The type's name, or ``""`` while none is chosen."""
        return email_type_name(bulk)

    def get_dart_name(self, bulk: BulkEmail) -> str:
        """The recorded DART's name, or ``""`` for none."""
        return str(bulk.dart.name) if bulk.dart is not None else ""


class BulkEmailBatchAddSerializer(serializers.ModelSerializer[BatchAdd]):
    """One **Add to batch**: its filters in words and as given, and its counts."""

    # ``Field`` has a ``label`` attribute of its own, which a field of that name shadows.
    label = serializers.SerializerMethodField()  # type: ignore[assignment]
    filters = serializers.DictField(child=serializers.CharField(), read_only=True)

    class Meta:
        model = BatchAdd
        fields = ["id", "label", "filters", "added_count", "already_count", "created_at"]
        read_only_fields = fields

    def get_label(self, add: BatchAdd) -> str:
        """The add's filters in words, such as ``"Kind: Friends only, County: Marin"``."""
        return add_label(add.filters)


class BulkEmailBatchRowDict(TypedDict):
    """One person in the batch, as ``GET /bulk-email/{id}/batch`` lists them."""

    id: int
    user_id: int | None
    name: str
    email: str
    kind: str
    dart_name: str
    added_by: int | None
    status: str
    will_receive: bool
    reason: str
    tried_at: datetime | None


class BulkEmailBatchRowSerializer(serializers.Serializer[BulkEmailBatchRowDict]):
    """One person in the batch.

    ``user_id`` is null once the account is deleted; ``name``, ``email``, ``kind``,
    and ``dart_name`` are the row's own.  ``added_by`` is the id of the add that
    brought the person in, null for none.  ``status`` is the row's; ``will_receive``
    and ``reason`` say whether a copy goes and why not.  ``tried_at`` is when the copy
    was last tried.
    """

    id = serializers.IntegerField()
    user_id = serializers.IntegerField(allow_null=True)
    name = serializers.CharField(allow_blank=True)
    email = serializers.CharField(allow_blank=True)
    kind = serializers.CharField(allow_blank=True)
    dart_name = serializers.CharField(allow_blank=True)
    added_by = serializers.IntegerField(allow_null=True)
    status = serializers.ChoiceField(choices=RecipientStatus.choices)
    will_receive = serializers.BooleanField()
    reason = serializers.CharField(allow_blank=True)
    tried_at = serializers.DateTimeField(allow_null=True)


def batch_row_payload(row: BatchRow) -> BulkEmailBatchRowDict:
    """``row`` as ``GET /bulk-email/{id}/batch`` lists it."""
    recipient = row.recipient
    return {
        "id": recipient.pk,
        "user_id": recipient.user_id,
        "name": recipient.name,
        "email": recipient.email,
        "kind": recipient.kind,
        "dart_name": recipient.dart_name,
        "added_by": recipient.added_by_id,
        "status": recipient.status,
        "will_receive": row.will_receive,
        "reason": row.reason,
        "tried_at": recipient.tried_at,
    }


class BulkEmailBatchSerializer(serializers.Serializer[dict[str, Any]]):
    """``GET /bulk-email/{id}/batch``: the counts, the adds, and every person.

    ``count`` is the batch's size, ``receiving`` how many receive a copy, and
    ``skipped`` how many do not.  ``adds`` are in the order they were pressed, and
    ``rows`` in the order the send goes.
    """

    count = serializers.IntegerField()
    receiving = serializers.IntegerField()
    skipped = serializers.IntegerField()
    adds = BulkEmailBatchAddSerializer(many=True)
    rows = BulkEmailBatchRowSerializer(many=True)


def batch_payload(bulk: BulkEmail) -> dict[str, Any]:
    """``bulk``'s batch as ``GET /bulk-email/{id}/batch`` answers it."""
    rows = batch_rows(bulk)
    counts = batch_counts(rows)
    return {
        "count": counts.count,
        "receiving": counts.receiving,
        "skipped": counts.skipped,
        "adds": list(bulk.adds.all()),
        "rows": [batch_row_payload(row) for row in rows],
    }


class BulkEmailRunResultSerializer(serializers.Serializer[dict[str, object]]):
    """What one run of the bulk email sender did.

    ``busy`` is true when another run was working and this one did nothing.  ``emails``
    counts the bulk emails worked on; ``sent`` and ``failed`` the copies tried, and
    ``skipped`` the people set aside as each email started.  ``out_of_time`` is true
    when the run's time budget ran out with copies still to send, and ``remaining``
    counts them; the next run carries on with them.  Each action is one copy: ``kind``
    is ``sent`` or ``failed``, and ``detail`` the subject or the reason.
    """

    busy = serializers.BooleanField()
    emails = serializers.IntegerField()
    sent = serializers.IntegerField()
    failed = serializers.IntegerField()
    skipped = serializers.IntegerField()
    out_of_time = serializers.BooleanField()
    remaining = serializers.IntegerField()
    actions = RunActionSerializer(many=True)
