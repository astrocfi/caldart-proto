"""What the notifications app keeps: which address hears about which events.

An event itself is not a row: it is one entry of the catalog in
:mod:`apps.notifications.events`, and a subscription names events by their slugs.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.db import models

from caldart.models import TimestampedModel


class NotificationSubscription(TimestampedModel):
    """One address, and the events it is sent an email about.

    ``recipient_email`` is always filled, stored in lower case, and unique: the address
    of ``recipient_user`` when the subscription is bound to an account, or the address
    typed for somebody outside CalDART.  ``events`` is the list of event slugs, in
    catalog order.  A paused subscription (``is_active`` false) is sent nothing.
    ``created_by`` is the account administrator who set it up, or null once that
    account is gone.
    """

    recipient_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notification_subscriptions",
    )
    recipient_email = models.EmailField(unique=True)
    events = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_notification_subscriptions",
    )

    class Meta:
        ordering = ["recipient_email"]

    def __str__(self) -> str:
        """The address and how many events it hears about."""
        return f"{self.recipient_email}: {len(self.events)} events"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Store the address stripped and in lower case, then save as Django would.

        Doing it here rather than in a serializer means the seed, the Django admin and
        the API all store the address the unique constraint compares.
        """
        self.recipient_email = self.recipient_email.strip().lower()
        super().save(*args, **kwargs)
