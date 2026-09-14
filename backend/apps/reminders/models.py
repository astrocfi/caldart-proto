"""Renewal reminder bookkeeping."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.members.models import TimestampedModel


class ReminderKind(models.TextChoices):
    T60 = "t60", "60 days before expiry"
    T30 = "t30", "30 days before expiry"
    T7 = "t7", "7 days before expiry"
    EXPIRED = "expired", "Expired today"
    POST30 = "post30", "30 days after expiry"


#: Offset in days from the membership expiry date for each kind.  Negative
#: values are before expiry.
REMINDER_OFFSETS: dict[str, int] = {
    ReminderKind.T60: -60,
    ReminderKind.T30: -30,
    ReminderKind.T7: -7,
    ReminderKind.EXPIRED: 0,
    ReminderKind.POST30: 30,
}


class ReminderLog(TimestampedModel):
    """One reminder email sent, used to make the scanner idempotent."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reminder_logs"
    )
    membership = models.ForeignKey(
        "members.Membership", on_delete=models.CASCADE, related_name="reminder_logs"
    )
    kind = models.CharField(max_length=12, choices=ReminderKind.choices)
    sent_at = models.DateTimeField()
    to_email = models.EmailField()

    class Meta:
        ordering = ["-sent_at", "-id"]
        verbose_name = "reminder log entry"
        verbose_name_plural = "reminder log entries"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "membership", "kind"], name="reminders_once_per_kind"
            ),
        ]
        indexes = [
            models.Index(fields=["kind", "-sent_at"], name="reminders_kind_sent_idx"),
            models.Index(fields=["user", "-sent_at"], name="reminders_user_sent_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} to {self.to_email} on {self.sent_at:%Y-%m-%d}"
