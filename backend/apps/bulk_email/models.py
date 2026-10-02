"""One email sent to everybody a filter selects, and what became of each copy.

A :class:`BulkEmail` is the message CalDART management wrote, the member list
filters that chose its recipients, who sent it, and how many copies went, failed,
or were skipped.  A :class:`BulkEmailRecipient` is one person the filters
selected: the account, the name and address as they were at send time, and the
result.  A preview stores neither: it only builds the list.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from caldart.models import TimestampedModel


class RecipientStatus(models.TextChoices):
    """What became of one person's copy of a bulk email."""

    SENT = "sent", "Sent"
    FAILED = "failed", "Failed"
    SKIPPED = "skipped", "Skipped"


class BulkEmail(TimestampedModel):
    """One email sent to everybody the member list's filters selected.

    ``body`` is plain text whose blank lines separate paragraphs.  ``filters`` are
    the member list's query parameters that chose the recipients, the ones given a
    value only, as ``ReportSubscription.filters`` stores a report's.  ``sender`` is
    the account that sent it, null once that account is deleted.  ``created_at`` is
    when the send began and ``sent_at`` when every copy had been tried; ``sent_at``
    stays null for a send that never finished.  The three counts add up to the
    recipient rows.
    """

    subject = models.CharField(max_length=200)
    body = models.TextField()
    filters = models.JSONField(default=dict, blank=True)
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bulk_emails_sent",
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    sent_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        """Return ``"<subject> (<created_at date>)"``."""
        return f"{self.subject} ({self.created_at:%Y-%m-%d})"


class BulkEmailRecipient(TimestampedModel):
    """One person a bulk email's filters selected, and what became of their copy.

    ``user`` is the account, null once it is deleted; ``name`` and ``email`` are
    the account's name and address at send time, kept whatever happens to the
    account later.  ``email`` is not validated, since an invalid address is
    recorded as the reason it was skipped.  ``reason`` says why a copy was skipped
    or failed, and is blank for one that went.
    """

    bulk_email = models.ForeignKey(BulkEmail, on_delete=models.CASCADE, related_name="recipients")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="bulk_emails_received",
    )
    name = models.CharField(max_length=200, blank=True)
    email = models.CharField(max_length=254, blank=True)
    status = models.CharField(max_length=7, choices=RecipientStatus.choices)
    reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        """Return ``"<email>: <status>"``."""
        return f"{self.email}: {self.status}"
