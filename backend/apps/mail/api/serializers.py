"""Serializers for the email log endpoint."""

from __future__ import annotations

from rest_framework import serializers

from apps.mail.models import EmailLog


class EmailLogSerializer(serializers.ModelSerializer[EmailLog]):
    """One row of ``GET /system/emails``.

    ``user_id`` and ``user_name`` are null and empty for a message sent to an
    address with no account behind it.  ``error`` is blank unless ``status`` is
    ``failed``, and ``attachments`` is a comma-separated list of filenames,
    blank when the message carried none.
    """

    user_id = serializers.IntegerField(read_only=True, allow_null=True)
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = EmailLog
        fields = [
            "id",
            "to_email",
            "user_id",
            "user_name",
            "purpose",
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
