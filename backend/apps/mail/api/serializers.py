"""Serializers for the email log endpoints."""

from __future__ import annotations

from rest_framework import serializers

from apps.mail.models import EmailLog
from apps.mail.purposes import purpose_label


class EmailLogSerializer(serializers.ModelSerializer[EmailLog]):
    """One row of ``GET /system/emails``.

    ``user_id`` and ``user_name`` are null and empty for a message sent to an
    address with no account behind it.  ``error`` is blank unless ``status`` is
    ``failed``, and ``attachments`` is a comma-separated list of filenames,
    blank when the message carried none.  ``purpose_label`` is the purpose in words,
    from ``apps.mail.purposes``, or the purpose itself when no label names it.
    """

    user_id = serializers.IntegerField(read_only=True, allow_null=True)
    user_name = serializers.SerializerMethodField()
    purpose_label = serializers.SerializerMethodField()

    class Meta:
        model = EmailLog
        fields = [
            "id",
            "to_email",
            "user_id",
            "user_name",
            "purpose",
            "purpose_label",
            "subject",
            "sent_at",
            "status",
            "error",
            "attachments",
        ]
        read_only_fields = fields

    def get_user_name(self, obj: EmailLog) -> str:
        """Return the recipient account's display name, or ``""`` when there is none."""
        return obj.user.display_name if obj.user is not None else ""

    def get_purpose_label(self, obj: EmailLog) -> str:
        """Return the words for the row's purpose, or its template name when unlabeled."""
        return purpose_label(obj.purpose)


class EmailPurposeSerializer(serializers.Serializer[dict[str, str]]):
    """One entry of ``GET /system/emails/purposes``: a purpose and its label."""

    value = serializers.CharField()
    # DRF's Field.label is a different thing from this serializer's own `label`
    # field, so the stubs see the declaration as a narrowing of the attribute.
    label = serializers.CharField()  # type: ignore[assignment]
