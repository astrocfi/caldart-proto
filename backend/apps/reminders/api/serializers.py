"""Serializers for the reminder endpoints (PLAN §6.9)."""

from __future__ import annotations

from rest_framework import serializers

from apps.reminders.models import ReminderLog


class ReminderLogSerializer(serializers.ModelSerializer):
    """One row of ``GET /admin/reminders/log``."""

    user_id = serializers.IntegerField(read_only=True)
    user_name = serializers.SerializerMethodField()
    membership_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = ReminderLog
        fields = ["id", "user_id", "user_name", "membership_id", "kind", "sent_at", "to_email"]
        read_only_fields = fields

    def get_user_name(self, obj: ReminderLog) -> str:
        return obj.user.display_name


class ReminderRunRequestSerializer(serializers.Serializer):
    """``POST /system/reminders/run`` body."""

    dry_run = serializers.BooleanField(default=False)


class ReminderRunResultSerializer(serializers.Serializer):
    """``{sent, skipped}`` (PLAN §6.9)."""

    sent = serializers.IntegerField()
    skipped = serializers.IntegerField()
