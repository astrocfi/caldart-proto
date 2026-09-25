"""What the reports app keeps: saved sets of columns, and subscriptions by email.

A report itself is not a row: it is a :class:`~caldart.reports.ReportSpec` declared by
the app that owns its data, and a row here names one by its slug.
"""

from __future__ import annotations

from django.conf import settings
from django.core.validators import MaxValueValidator
from django.db import models

from apps.reports.schedule import Cadence
from caldart.models import TimestampedModel

#: The longest report slug a row may name.
REPORT_SLUG_LENGTH = 32


class SavedColumnSet(TimestampedModel):
    """A named choice of one report's columns, kept for the account that saved it.

    ``columns`` is the list of column keys, in the order the report prints them.
    One account has at most one set of a given name per report; the name is
    compared exactly, so ``Roster`` and ``roster`` are two sets.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_column_sets"
    )
    report = models.CharField(max_length=REPORT_SLUG_LENGTH)
    name = models.CharField(max_length=60)
    columns = models.JSONField(default=list)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "report", "name"], name="reports_column_set_unique_name"
            )
        ]

    def __str__(self) -> str:
        """The set's name and the report it belongs to."""
        return f"{self.name} ({self.report})"


class ReportFormats(models.TextChoices):
    """Which files a subscription attaches."""

    CSV = "csv", "CSV"
    PDF = "pdf", "PDF"
    BOTH = "both", "Both"


class ReportSubscription(TimestampedModel):
    """One report, emailed to one address on a schedule.

    ``recipient_email`` is always filled: the address of ``recipient_user`` when the
    subscription is bound to an account, or the address typed for someone outside
    CalDART.  ``filters`` are the params the report takes, ``period`` included, and
    ``columns`` the chosen column keys, empty for the report's defaults.  ``weekday``
    (0 Monday to 6 Sunday) is read by the ``weekly`` cadence alone.  ``next_due_on``
    is the first day the daily run sends it; ``last_sent_at`` is when it last went
    out, or null.
    """

    report = models.CharField(max_length=REPORT_SLUG_LENGTH)
    recipient_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="report_subscriptions",
    )
    recipient_email = models.EmailField()
    filters = models.JSONField(default=dict, blank=True)
    columns = models.JSONField(default=list, blank=True)
    formats = models.CharField(max_length=4, choices=ReportFormats.choices)
    cadence = models.CharField(max_length=9, choices=Cadence.choices)
    weekday = models.PositiveSmallIntegerField(default=0, validators=[MaxValueValidator(6)])
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_report_subscriptions",
    )
    last_sent_at = models.DateTimeField(null=True, blank=True)
    next_due_on = models.DateField()

    class Meta:
        ordering = ["report", "recipient_email"]
        indexes = [
            models.Index(fields=["is_active", "next_due_on"], name="reports_sub_due_idx"),
        ]

    def __str__(self) -> str:
        """The report and where it goes."""
        return f"{self.report} to {self.recipient_email}"
