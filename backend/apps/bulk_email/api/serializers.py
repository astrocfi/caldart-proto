"""Serializers for the bulk email endpoints."""

from __future__ import annotations

from typing import Any, TypedDict

from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from apps.bulk_email.models import BulkEmail, BulkEmailRecipient
from apps.bulk_email.services import (
    RecipientList,
    given_filters,
    selected_accounts,
    unknown_filters,
)

#: What a filter the member list does not have is refused with.
UNKNOWN_FILTER_MESSAGE = "Not a filter of the member list."

#: The longest message a bulk email carries, in characters.
MAX_BODY_LENGTH = 20000


def checked_filters(filters: dict[str, str]) -> dict[str, str]:
    """``filters`` as a bulk email stores them, once the member list accepts them.

    Raises ``ValidationError`` keyed by each filter the member list does not have,
    with :data:`UNKNOWN_FILTER_MESSAGE`, and then keyed by each filter whose value
    the member list refuses, with the list's own message.  Blank filters are
    dropped from the answer.
    """
    unknown = unknown_filters(filters)
    if len(unknown) > 0:
        raise ValidationError({key: [UNKNOWN_FILTER_MESSAGE] for key in unknown})
    # Building the queryset runs the member list's own filter checks.
    selected_accounts(filters)
    return given_filters(filters)


class BulkEmailMessageSerializer(serializers.Serializer[dict[str, Any]]):
    """The body of a preview and of a send: the message, and who it is aimed at.

    ``subject`` is one line of at most 200 characters and ``body`` plain text, its
    blank lines separating paragraphs; both are required and trimmed.  ``filters``
    are the member list's query parameters, blank ones ignored; it may be left out
    to aim at every member and friend.
    """

    subject = serializers.CharField(
        max_length=200,
        error_messages={"blank": "Write a subject.", "required": "Write a subject."},
    )
    body = serializers.CharField(
        max_length=MAX_BODY_LENGTH,
        error_messages={"blank": "Write the message.", "required": "Write the message."},
    )
    filters = serializers.DictField(
        child=serializers.CharField(allow_blank=True), required=False, default=dict
    )

    def validate_subject(self, value: str) -> str:
        """Refuse a subject that runs over more than one line."""
        if "\n" in value or "\r" in value:
            raise ValidationError("A subject is one line.")
        return value

    def validate_filters(self, value: dict[str, str]) -> dict[str, str]:
        """Refuse a filter the member list does not have, or a value it refuses."""
        return checked_filters(value)


class RecipientDict(TypedDict):
    """One person a preview lists."""

    user_id: int
    name: str
    email: str
    reason: str


class PreviewDict(TypedDict):
    """A preview: who would receive the email, who is skipped, and the two counts."""

    count: int
    skipped_count: int
    recipients: list[RecipientDict]
    skipped: list[RecipientDict]


class BulkEmailPreviewRecipientSerializer(serializers.Serializer[RecipientDict]):
    """One person a preview lists; ``reason`` is blank for one who will be sent a copy."""

    user_id = serializers.IntegerField()
    name = serializers.CharField()
    email = serializers.CharField(allow_blank=True)
    reason = serializers.CharField(allow_blank=True)


class BulkEmailPreviewSerializer(serializers.Serializer[PreviewDict]):
    """``POST /bulk-email/preview``'s answer.

    ``count`` is how many people would be sent a copy, and ``skipped_count`` how
    many the filters select but would be skipped.  ``recipients`` and ``skipped``
    list them, each in surname order.
    """

    count = serializers.IntegerField()
    skipped_count = serializers.IntegerField()
    recipients = BulkEmailPreviewRecipientSerializer(many=True)
    skipped = BulkEmailPreviewRecipientSerializer(many=True)


def preview_payload(chosen: RecipientList) -> PreviewDict:
    """``chosen`` as ``POST /bulk-email/preview`` answers it."""

    def rows(entries: list[Any]) -> list[RecipientDict]:
        return [
            {"user_id": r.user_id, "name": r.name, "email": r.email, "reason": r.reason}
            for r in entries
        ]

    return {
        "count": len(chosen.recipients),
        "skipped_count": len(chosen.skipped),
        "recipients": rows(chosen.recipients),
        "skipped": rows(chosen.skipped),
    }


class BulkEmailRecipientSerializer(serializers.ModelSerializer[BulkEmailRecipient]):
    """One person a sent bulk email selected, and what became of their copy.

    ``user_id`` is null once the account is deleted; ``name`` and ``email`` are as
    they were at send time.  ``status`` is ``sent``, ``failed`` or ``skipped``, and
    ``reason`` is blank for a copy that went.
    """

    user_id = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = BulkEmailRecipient
        fields = ["user_id", "name", "email", "status", "reason"]
        read_only_fields = fields


class BulkEmailSerializer(serializers.ModelSerializer[BulkEmail]):
    """One sent bulk email, as ``GET /bulk-email`` lists it.

    ``filters`` are the member list filters that chose the recipients, those given
    a value only.  ``sender`` is the sender's display name, blank once the account
    is deleted.  ``sent_at`` is null for a send that never finished.
    """

    filters = serializers.DictField(child=serializers.CharField(), read_only=True)
    sender = serializers.SerializerMethodField()

    class Meta:
        model = BulkEmail
        fields = [
            "id",
            "subject",
            "body",
            "filters",
            "sender",
            "created_at",
            "sent_at",
            "sent_count",
            "failed_count",
            "skipped_count",
        ]
        read_only_fields = fields

    def get_sender(self, bulk: BulkEmail) -> str:
        """The sender's display name, or ``""`` once the account is gone."""
        return bulk.sender.display_name if bulk.sender is not None else ""


class BulkEmailDetailSerializer(BulkEmailSerializer):
    """One sent bulk email with every person's result, in the order stored."""

    recipients = BulkEmailRecipientSerializer(many=True, read_only=True)

    class Meta(BulkEmailSerializer.Meta):
        fields = [*BulkEmailSerializer.Meta.fields, "recipients"]
        read_only_fields = fields
