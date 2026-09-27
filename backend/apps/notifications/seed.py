"""Seed the demo notification subscriptions.

Idempotent: re-running updates the two subscriptions rather than adding more.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import OutputWrapper

from apps.accounts.models import User
from apps.notifications.events import EVENTS
from apps.notifications.models import NotificationSubscription

#: ``(demo account key, categories)`` for each subscription: the account hears about
#: every event in those categories.
DEMO_NOTIFICATIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("accountadmin", ("Membership", "Accounts")),
    ("treasurer", ("Money",)),
)


def run(ctx: dict[str, Any], stdout: OutputWrapper | None = None) -> dict[str, Any]:
    """Subscribe the demo account administrator and treasurer to their events.

    The account administrator hears about every Membership and Accounts event, and the
    treasurer about every Money event; both subscriptions are bound to their accounts,
    active, and set up by the account administrator.  Reads ``demo_users`` from ``ctx``
    and returns it unchanged.  When ``stdout`` is given, one summary line is written to
    it.
    """
    demo: dict[str, User] = ctx["demo_users"]
    creator = demo["accountadmin"]
    for key, categories in DEMO_NOTIFICATIONS:
        recipient = demo[key]
        NotificationSubscription.objects.update_or_create(
            recipient_email=recipient.email.lower(),
            defaults={
                "recipient_user": recipient,
                "events": [slug for slug, event in EVENTS.items() if event.category in categories],
                "is_active": True,
                "created_by": creator,
            },
        )
    if stdout is not None:
        stdout.write(f"  notifications: {len(DEMO_NOTIFICATIONS)} subscriptions")
    return ctx
