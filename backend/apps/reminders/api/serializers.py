"""Serializers for the reminder endpoints."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.reminders.models import ReminderLog


class ReminderLogSerializer(serializers.ModelSerializer[ReminderLog]):
    """One row of ``GET /admin/reminders/log``."""

    user_id = serializers.IntegerField(read_only=True)
    user_name = serializers.SerializerMethodField()
    membership_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = ReminderLog
        fields = ["id", "user_id", "user_name", "membership_id", "kind", "sent_at", "to_email"]
        read_only_fields = fields

    def get_user_name(self, obj: ReminderLog) -> str:
        """Return the reminder recipient's display name."""
        return obj.user.display_name


class ReminderRunRequestSerializer(serializers.Serializer[Any]):
    """``POST /system/reminders/run`` body.

    Validates only that ``dry_run`` is a boolean, defaulting to ``False`` when absent.
    """

    dry_run = serializers.BooleanField(default=False)


class ReminderRunResultSerializer(serializers.Serializer[dict[str, int]]):
    """``{sent, skipped}``, serialized from a plain ``{"sent": int, "skipped": int}``."""

    sent = serializers.IntegerField()
    skipped = serializers.IntegerField()
