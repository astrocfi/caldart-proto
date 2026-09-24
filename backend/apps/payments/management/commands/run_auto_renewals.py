"""``manage.py run_auto_renewals`` -- the daily automatic-renewal scan.

Run by ``deploy/systemd/caldart-renewals.timer`` at 06:30, half an hour before
the reminder scan, so a membership renewed automatically is never also sent a
reminder about running out.  Safe to repeat: every email the scan sends is
keyed on a timestamp of the attempt it belongs to, and an attempt that has been
charged is no longer scheduled.
"""

from __future__ import annotations

import argparse
from datetime import date
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.payments.renewals import run_auto_renewals


class Command(BaseCommand):
    """Runs the automatic-renewal scan and reports its results to stdout."""

    help = "Send renewal notices, charge the renewals due, and retry or pause failures."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Register ``--dry-run`` and ``--today`` on the command's argument parser."""
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would happen without renewing, emailing or charging anything.",
        )
        parser.add_argument(
            "--today",
            metavar="YYYY-MM-DD",
            help="Scan as of this date instead of today. Useful for rehearsals.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Run the scan and print its summary.

        ``--today`` must be an ISO ``YYYY-MM-DD`` date, or ``CommandError`` is
        raised with the invalid value quoted.  After the scan, if any charge was
        refused, ``CommandError`` is raised naming how many were, so the command
        exits non-zero and the systemd unit goes to ``failed`` rather than
        reporting a clean run that took no money.
        """
        scan_date: date | None = None
        if options["today"]:
            try:
                scan_date = date.fromisoformat(options["today"])
            except ValueError as exc:
                raise CommandError(f"--today must be YYYY-MM-DD, not {options['today']!r}") from exc

        run = run_auto_renewals(today=scan_date, dry_run=options["dry_run"])

        for line in run.as_lines():
            self.stdout.write(line)

        style = self.style.WARNING if run.dry_run else self.style.SUCCESS
        verb = "would charge" if run.dry_run else "charged"
        self.stdout.write(style(f"noticed {run.noticed}, {verb} {run.charged}"))

        if run.failed > 0:
            plural = "" if run.failed == 1 else "s"
            raise CommandError(
                f"{run.failed} renewal charge{plural} was refused; "
                "the renewals screen names the member and the reason"
            )
