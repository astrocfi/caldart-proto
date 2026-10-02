"""Renewal reminder bookkeeping."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db import models

from caldart.models import TimestampedModel


class ReminderKind(models.TextChoices):
    """The five renewal reminder stages, in the order a term reaches them.

    The labels name the stages; the words a screen prints for one, such as "60 days
    before expiry", come from the stored :class:`ReminderSchedule`.
    """

    FIRST = "first", "First reminder"
    SECOND = "second", "Second reminder"
    FINAL = "final", "Final reminder"
    EXPIRED = "expired", "Expired"
    LAPSED = "lapsed", "Lapsed"


#: The schedule a fresh installation runs: whole days before expiry for the three
#: stages ahead of it, and whole days after it for the lapsed stage.
DEFAULT_FIRST_DAYS_BEFORE = 60
DEFAULT_SECOND_DAYS_BEFORE = 30
DEFAULT_FINAL_DAYS_BEFORE = 7
DEFAULT_LAPSED_DAYS_AFTER = 30

#: The bounds :func:`schedule_errors` holds a schedule to.  The first reminder goes at
#: most a year ahead, the final one at least a day ahead, and the lapsed one between
#: a week and a year after expiry: the expired stage reaches six days past expiry,
#: so a lapsed stage a week out never meets it.
MAX_DAYS_BEFORE = 365
MIN_FINAL_DAYS_BEFORE = 1
MIN_LAPSED_DAYS_AFTER = 7
MAX_LAPSED_DAYS_AFTER = 365

#: The four editable fields, in the order a form lists them.
SCHEDULE_FIELDS: tuple[str, ...] = (
    "first_days_before",
    "second_days_before",
    "final_days_before",
    "lapsed_days_after",
)


def schedule_errors(
    first_days_before: int,
    second_days_before: int,
    final_days_before: int,
    lapsed_days_after: int,
) -> dict[str, str]:
    """What is wrong with a schedule, keyed by field, or an empty dict when nothing is.

    The rules are ``365 >= first > second > final >= 1`` and ``7 <= lapsed <= 365``.
    Each broken rule is reported against the field it constrains, in a sentence naming
    the reminder and the rule: ``first_days_before`` above 365 or not above
    ``second_days_before``, ``second_days_before`` not above ``final_days_before``,
    ``final_days_before`` below 1, and ``lapsed_days_after`` outside 7 to 365.  A field
    breaking two rules carries the first of them in that order.
    """
    errors: dict[str, str] = {}
    if first_days_before > MAX_DAYS_BEFORE:
        errors["first_days_before"] = (
            f"The first reminder can be at most {MAX_DAYS_BEFORE} days before expiry."
        )
    elif first_days_before <= second_days_before:
        errors["first_days_before"] = (
            "The first reminder must be more days before expiry than the second."
        )
    if second_days_before <= final_days_before:
        errors["second_days_before"] = (
            "The second reminder must be more days before expiry than the final one."
        )
    if final_days_before < MIN_FINAL_DAYS_BEFORE:
        errors["final_days_before"] = (
            f"The final reminder must be at least {MIN_FINAL_DAYS_BEFORE} day before expiry."
        )
    if not MIN_LAPSED_DAYS_AFTER <= lapsed_days_after <= MAX_LAPSED_DAYS_AFTER:
        errors["lapsed_days_after"] = (
            f"The lapsed reminder must be {MIN_LAPSED_DAYS_AFTER} to "
            f"{MAX_LAPSED_DAYS_AFTER} days after expiry."
        )
    return errors


def _days(count: int) -> str:
    """``count`` with "day" or "days", as a label prints it."""
    return f"{count} day" if count == 1 else f"{count} days"


class ReminderSchedule(models.Model):
    """The one record of when each renewal reminder stage falls.

    The three stages before expiry fall ``first_days_before``,
    ``second_days_before`` and ``final_days_before`` whole days ahead of a term's
    ``ends_on``, the ``expired`` stage on the day itself, and the ``lapsed`` stage
    ``lapsed_days_after`` days after it.  A system administrator edits the row on the
    Scheduled page; :func:`schedule_errors` states the rules a schedule keeps.  There
    is only ever one row, with primary key 1: :meth:`load` reads it.
    """

    first_days_before = models.PositiveSmallIntegerField(default=DEFAULT_FIRST_DAYS_BEFORE)
    second_days_before = models.PositiveSmallIntegerField(default=DEFAULT_SECOND_DAYS_BEFORE)
    final_days_before = models.PositiveSmallIntegerField(default=DEFAULT_FINAL_DAYS_BEFORE)
    lapsed_days_after = models.PositiveSmallIntegerField(default=DEFAULT_LAPSED_DAYS_AFTER)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta:
        verbose_name = "reminder schedule"
        verbose_name_plural = "reminder schedule"

    def __str__(self) -> str:
        """Return the days, e.g. ``60/30/7 days before, 30 days after``."""
        return (
            f"{self.first_days_before}/{self.second_days_before}/{self.final_days_before} "
            f"days before, {self.lapsed_days_after} days after"
        )

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Save the schedule as the one row, primary key 1."""
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> ReminderSchedule:
        """The stored schedule, or an unsaved default one (60, 30, 7, 30) before any is.

        Reading never writes: the row first appears when a schedule is saved.
        """
        return cls.objects.filter(pk=1).first() or cls()

    def offsets(self) -> dict[str, int]:
        """Each stage's day relative to expiry, negative before it, by kind.

        The day dates the far end of the stage's span: ``first`` at
        ``-first_days_before``, ``second`` and ``final`` likewise, ``expired`` at 0,
        and ``lapsed`` at ``lapsed_days_after``.  The scanner turns the offsets into
        spans in ``apps.reminders.services.stage_span``.
        """
        return {
            ReminderKind.FIRST: -self.first_days_before,
            ReminderKind.SECOND: -self.second_days_before,
            ReminderKind.FINAL: -self.final_days_before,
            ReminderKind.EXPIRED: 0,
            ReminderKind.LAPSED: self.lapsed_days_after,
        }

    def kind_labels(self) -> dict[str, str]:
        """Each stage in words, by kind, in stage order.

        ``"60 days before expiry"``, ``"30 days before expiry"``, ``"7 days before
        expiry"``, ``"Expired"`` and ``"30 days after expiry"`` for the default
        schedule; a final reminder one day out reads ``"1 day before expiry"``.
        """
        return {
            ReminderKind.FIRST: f"{_days(self.first_days_before)} before expiry",
            ReminderKind.SECOND: f"{_days(self.second_days_before)} before expiry",
            ReminderKind.FINAL: f"{_days(self.final_days_before)} before expiry",
            ReminderKind.EXPIRED: "Expired",
            ReminderKind.LAPSED: f"{_days(self.lapsed_days_after)} after expiry",
        }

    def purpose_labels(self) -> dict[str, str]:
        """Each stage's email purpose, ``reminder_<kind>``, in words, in stage order.

        ``"Renewal reminder (60 days)"``, ``"Renewal reminder (30 days)"``,
        ``"Renewal reminder (7 days)"``, ``"Renewal reminder (expired)"`` and
        ``"Renewal reminder (30 days after)"`` for the default schedule.
        """
        return {
            f"reminder_{ReminderKind.FIRST}": f"Renewal reminder ({_days(self.first_days_before)})",
            f"reminder_{ReminderKind.SECOND}": (
                f"Renewal reminder ({_days(self.second_days_before)})"
            ),
            f"reminder_{ReminderKind.FINAL}": f"Renewal reminder ({_days(self.final_days_before)})",
            f"reminder_{ReminderKind.EXPIRED}": "Renewal reminder (expired)",
            f"reminder_{ReminderKind.LAPSED}": (
                f"Renewal reminder ({_days(self.lapsed_days_after)} after)"
            ),
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
        """Return ``"<kind label> to <email> on <sent_at date>"``."""
        return f"{self.get_kind_display()} to {self.to_email} on {self.sent_at:%Y-%m-%d}"
