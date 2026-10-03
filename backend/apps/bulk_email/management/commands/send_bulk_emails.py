"""``manage.py send_bulk_emails`` -- one run of the bulk email sender.

Run every minute by ``deploy/systemd/caldart-bulk-email.timer`` in production.  It
finishes any bulk email a stopped run left ``sending``, then starts and sends every
queued one whose start time has come (``apps.bulk_email.job.run_sender``).  Safe to
repeat and to overlap: a second run while one is working does nothing.  A copy the mail
server refuses is recorded on its row, so the command exits cleanly whatever the
server said.
"""

from __future__ import annotations

from typing import Any

from django.core.management.base import BaseCommand

from apps.bulk_email.job import run_sender


class Command(BaseCommand):
    """Runs the bulk email sender once and reports what it did to stdout."""

    help = "Send every bulk email whose start time has come."

    def handle(self, *args: Any, **options: Any) -> None:
        """Run the sender and print its summary, then one line per copy tried."""
        run = run_sender()
        for line in run.as_lines():
            self.stdout.write(line)
        if run.busy:
            return
        self.stdout.write(
            self.style.SUCCESS(
                f"sent {run.sent}, failed {run.failed}, skipped {run.skipped} "
                f"across {run.emails} bulk email(s)"
            )
        )
