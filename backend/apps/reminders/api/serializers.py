"""Serializers for the reminder endpoints."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.reminders.models import SCHEDULE_FIELDS, ReminderLog, ReminderSchedule, schedule_errors
from caldart.runs import RunActionSerializer


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


class ReminderRunResultSerializer(serializers.Serializer[dict[str, Any]]):
    """What one scan did: the counts, why it passed members over, and who it wrote to.

    ``skipped_by_reason`` holds one entry per reason that occurred, so a thin run
    explains itself on the screen; ``failed`` counts the sends the mail server
    refused.
    """

    sent = serializers.IntegerField()
    skipped = serializers.IntegerField()
    failed = serializers.IntegerField()
    skipped_by_reason = serializers.DictField(child=serializers.IntegerField())
    actions = RunActionSerializer(many=True)


class ReminderScheduleSerializer(serializers.ModelSerializer[ReminderSchedule]):
    """``GET``/``PUT /admin/reminders/schedule``: when each reminder stage falls.

    ``first_days_before``, ``second_days_before`` and ``final_days_before`` are whole
    days before expiry and ``lapsed_days_after`` whole days after it.  A ``PUT`` sends
    all four, and a schedule breaking a rule of
    :func:`~apps.reminders.models.schedule_errors` is refused with a 400 naming each
    field it breaks.  ``updated_by`` is the display name of the system administrator
    who saved the schedule last and ``updated_at`` when; both are null before anyone
    has, while the defaults (60, 30, 7, 30) apply.
    """

    first_days_before = serializers.IntegerField()
    second_days_before = serializers.IntegerField()
    final_days_before = serializers.IntegerField()
    lapsed_days_after = serializers.IntegerField()
    updated_by = serializers.CharField(
        source="updated_by.display_name", read_only=True, allow_null=True
    )
    updated_at = serializers.DateTimeField(read_only=True, allow_null=True)

    class Meta:
        model = ReminderSchedule
        fields = [*SCHEDULE_FIELDS, "updated_by", "updated_at"]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Return ``attrs`` when the four days keep the schedule's rules.

        Raises ``ValidationError`` keyed by every field that breaks one, each with the
        sentence :func:`~apps.reminders.models.schedule_errors` gives it.
        """
        errors = schedule_errors(
            attrs["first_days_before"],
            attrs["second_days_before"],
            attrs["final_days_before"],
            attrs["lapsed_days_after"],
        )
        if errors:
            raise serializers.ValidationError(errors)
        return attrs
