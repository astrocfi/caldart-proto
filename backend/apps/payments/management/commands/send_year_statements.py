"""``manage.py send_year_statements`` -- the yearly run of the statement sender.

Run by ``deploy/systemd/caldart-statements.timer`` at 06:45 on January 15th in
production, once every provider has settled the prior December's payments.
Safe to repeat: a :class:`~apps.payments.models.YearStatement` row is written
per address reached, so a second run for a year already sent reaches nobody
again.  The command exits non-zero when any email could not be sent, so the
systemd unit goes to ``failed`` instead of reporting a clean run that reached
nobody.
"""

from __future__ import annotations

import argparse
from datetime import date
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.payments.reports import FIRST_REPORTABLE_YEAR
from apps.payments.statements import send_year_statements

#: The latest year the sender will look at; matches the bound
#: ``StatementsRunRequestSerializer`` enforces on the API endpoint.
LAST_REPORTABLE_YEAR = 9_000


class Command(BaseCommand):
    """Runs the year-end statement sender and reports its results to stdout."""

    help = "Send the previous year's contribution statements to every active giver."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Register ``--year``, ``--dry-run`` and ``--today``."""
        parser.add_argument(
            "--year",
            type=int,
            help="The calendar year to send statements for. Defaults to the year before --today.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report who would receive a statement without writing or emailing anything.",
        )
        parser.add_argument(
            "--today",
            metavar="YYYY-MM-DD",
            help="Run as of this date instead of today. Useful for rehearsals.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Run the sender and print its summary.

        ``--today`` must be an ISO ``YYYY-MM-DD`` date, or ``CommandError`` is
        raised with the invalid value quoted.  ``--year`` defaults to the
        calendar year before ``--today`` (or before today, without it), and
        must fall between :data:`~apps.payments.reports.FIRST_REPORTABLE_YEAR`
        and :data:`LAST_REPORTABLE_YEAR` or ``CommandError`` is raised naming
        the value given.  After the run, if any statement failed to send,
        ``CommandError`` is raised naming how many did, so the command exits
        non-zero; a run with no failures returns normally.
        """
        run_date: date | None = None
        if options["today"]:
            try:
                run_date = date.fromisoformat(options["today"])
            except ValueError as exc:
                raise CommandError(f"--today must be YYYY-MM-DD, not {options['today']!r}") from exc

        day = run_date or timezone.localdate()
        year = options["year"] if options["year"] is not None else day.year - 1
        if not FIRST_REPORTABLE_YEAR <= year <= LAST_REPORTABLE_YEAR:
            raise CommandError(
                f"--year must be between {FIRST_REPORTABLE_YEAR} and "
                f"{LAST_REPORTABLE_YEAR}, not {year}"
            )

        run = send_year_statements(year, today=day, dry_run=options["dry_run"])

        for line in run.as_lines():
            self.stdout.write(line)

        style = self.style.WARNING if run.dry_run else self.style.SUCCESS
        verb = "would send" if run.dry_run else "sent"
        self.stdout.write(style(f"{verb} {run.sent}, skipped {run.skipped}"))

        if run.failed > 0:
            plural = "" if run.failed == 1 else "s"
            raise CommandError(
                f"{run.failed} statement email{plural} could not be sent; "
                "the run log names the account and the year"
            )
