"""``manage.py send_scheduled_reports`` -- the daily run of the report sender.

Run by ``deploy/systemd/caldart-reports.timer`` at 06:00 in production.  It sends
every report subscription that is due and every DART roster not yet sent this month.
Safe to repeat: a sent subscription moves on to its next day and a sent roster is
stamped with the month, so a second run the same day sends nothing again.  The
command exits non-zero when any email could not be sent, so the systemd unit goes to
``failed`` instead of reporting a clean run that reached nobody.
"""

from __future__ import annotations

import argparse
from datetime import date
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.reports.services import run_scheduled_reports


class Command(BaseCommand):
    """Runs the report sender and reports its results to stdout."""

    help = "Send the report subscriptions and the DART rosters that are due."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Register ``--dry-run`` and ``--today`` on the command's argument parser."""
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be sent without writing or emailing anything.",
        )
        parser.add_argument(
            "--today",
            metavar="YYYY-MM-DD",
            help="Run as of this date instead of today. Useful for rehearsals.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Run the sender and print its summary.

        ``--today`` must be an ISO ``YYYY-MM-DD`` date, or ``CommandError`` is raised
        with the invalid value quoted.  After the run, if any email failed to send,
        ``CommandError`` is raised naming how many did, so the command exits non-zero;
        a run with no failures returns normally.
        """
        run_date: date | None = None
        if options["today"]:
            try:
                run_date = date.fromisoformat(options["today"])
            except ValueError as exc:
                raise CommandError(f"--today must be YYYY-MM-DD, not {options['today']!r}") from exc

        run = run_scheduled_reports(today=run_date, dry_run=options["dry_run"])

        for line in run.as_lines():
            self.stdout.write(line)

        style = self.style.WARNING if run.dry_run else self.style.SUCCESS
        verb = "would send" if run.dry_run else "sent"
        self.stdout.write(style(f"{verb} {run.sent}, skipped {run.skipped}"))

        if run.failed > 0:
            plural = "" if run.failed == 1 else "s"
            raise CommandError(
                f"{run.failed} report email{plural} could not be sent; "
                "the run log names the subscription and DART ids"
            )
