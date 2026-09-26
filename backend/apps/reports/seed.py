"""Seed the demo report subscriptions.

Idempotent: re-running updates the three subscriptions rather than adding more.  The
DART rosters need nothing here; the members seed ticks who receives each one.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import OutputWrapper

from apps.accounts.models import User
from apps.reports.models import ReportFormats, ReportSubscription
from apps.reports.schedule import Cadence

#: ``(report, demo account key, filters, formats, cadence)`` for each subscription.
#: The aircraft register is weekly, so its ``weekday`` is drawn from the day the seed
#: runs rather than fixed, unlike the other two, whose cadence never reads it.
DEMO_SUBSCRIPTIONS: tuple[tuple[str, str, dict[str, str], str, str], ...] = (
    ("members", "accountadmin", {}, ReportFormats.PDF, Cadence.MONTHLY),
    ("payments", "treasurer", {"period": "this_year"}, ReportFormats.CSV, Cadence.QUARTERLY),
    ("aircraft", "accountadmin", {}, ReportFormats.BOTH, Cadence.WEEKLY),
)


def run(ctx: dict[str, Any], stdout: OutputWrapper | None = None) -> dict[str, Any]:
    """Create the demo subscriptions, all set up by the demo account administrator.

    The membership report goes monthly as a PDF to the account administrator, this
    year's payments quarterly as a CSV to the treasurer, and the aircraft register
    weekly as a CSV and a PDF to the account administrator.  Every one is due the day
    the seed runs (``ctx["today"]``), with no send yet, so the scheduled-report job
    always has real work waiting.  Reads ``demo_users`` from ``ctx`` and returns it
    unchanged.  When ``stdout`` is given, one summary line is written to it.
    """
    demo: dict[str, User] = ctx["demo_users"]
    creator = demo["accountadmin"]
    today = ctx["today"]
    for report, key, filters, formats, cadence in DEMO_SUBSCRIPTIONS:
        recipient = demo[key]
        weekday = today.weekday() if cadence == Cadence.WEEKLY else 0
        ReportSubscription.objects.update_or_create(
            report=report,
            recipient_email=recipient.email,
            defaults={
                "recipient_user": recipient,
                "filters": filters,
                "columns": [],
                "formats": formats,
                "cadence": cadence,
                "weekday": weekday,
                "is_active": True,
                "created_by": creator,
                "next_due_on": today,
            },
        )
    if stdout is not None:
        stdout.write(f"  reports: {len(DEMO_SUBSCRIPTIONS)} subscriptions")
    return ctx
