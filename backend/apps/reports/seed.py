"""Seed the demo report subscriptions.

Idempotent: re-running updates the two subscriptions rather than adding more.  The
DART rosters need nothing here; the members seed ticks who receives each one.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import OutputWrapper

from apps.accounts.models import User
from apps.reports.models import ReportFormats, ReportSubscription
from apps.reports.schedule import Cadence, next_due_after

#: ``(report, demo account key, filters, formats, cadence)`` for each subscription.
DEMO_SUBSCRIPTIONS: tuple[tuple[str, str, dict[str, str], str, str], ...] = (
    ("members", "accountadmin", {}, ReportFormats.PDF, Cadence.MONTHLY),
    ("payments", "treasurer", {"period": "this_year"}, ReportFormats.CSV, Cadence.QUARTERLY),
)


def run(ctx: dict[str, Any], stdout: OutputWrapper | None = None) -> dict[str, Any]:
    """Create the demo subscriptions, both set up by the demo account administrator.

    The membership report goes monthly as a PDF to the account administrator, and this
    year's payments quarterly as a CSV to the treasurer, each first due on its
    schedule's next day after ``ctx["today"]``.  Reads ``demo_users`` from ``ctx`` and
    returns it unchanged.  When ``stdout`` is given, one summary line is written to it.
    """
    demo: dict[str, User] = ctx["demo_users"]
    creator = demo["accountadmin"]
    for report, key, filters, formats, cadence in DEMO_SUBSCRIPTIONS:
        recipient = demo[key]
        ReportSubscription.objects.update_or_create(
            report=report,
            recipient_email=recipient.email,
            defaults={
                "recipient_user": recipient,
                "filters": filters,
                "columns": [],
                "formats": formats,
                "cadence": cadence,
                "weekday": 0,
                "is_active": True,
                "created_by": creator,
                "next_due_on": next_due_after(cadence, 0, ctx["today"]),
            },
        )
    if stdout is not None:
        stdout.write(f"  reports: {len(DEMO_SUBSCRIPTIONS)} subscriptions")
    return ctx
