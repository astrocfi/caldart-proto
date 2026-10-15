"""``manage.py run_auto_renewals`` -- the daily scan of renewals and recurring donations.

Run by ``deploy/systemd/caldart-renewals.timer`` at 06:30, half an hour before
the reminder scan, so a membership renewed automatically is never also sent a
reminder about running out.  Safe to repeat: every email the scan sends is
keyed on a timestamp of the attempt it belongs to, and an attempt that has been
charged is no longer scheduled.  The Scheduled tasks page starts it with
``--scan-id`` for a live run, so the scan runs outside the web request.
"""

from __future__ import annotations

import argparse
import logging
from datetime import date
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Model

from apps.payments.models import RenewalScan
from apps.payments.renewals.background import STOPPED_WITH_AN_ERROR, close_scan, finish_scan
from apps.payments.renewals.charge import charges_in_doubt
from apps.payments.renewals.scan import RenewalsBusyError, run_auto_renewals
from apps.sysadmin.recording import skip_record
from caldart import audit

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """Runs the automatic-renewal scan and reports its results to stdout."""

    help = (
        "Send renewal notices, charge the renewals and recurring donations due, "
        "and retry or pause failures."
    )

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Register ``--dry-run``, ``--today`` and ``--scan-id`` on the parser."""
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
        parser.add_argument(
            "--scan-id",
            type=int,
            default=None,
            help="Fill in this RenewalScan row, written by the Scheduled tasks page.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Run the scan and print its summary.

        ``--today`` must be an ISO ``YYYY-MM-DD`` date, or ``CommandError`` is
        raised with the invalid value quoted.  ``--scan-id`` names the
        ``RenewalScan`` row a press of **Run now** wrote; ``CommandError`` is raised
        when no such row exists.  The scan's ``renewals.run`` audit record then
        names the system administrator who pressed it, and the row is filled in
        with the run's counts and actions when the scan ends, or closed with
        :data:`~apps.payments.renewals.background.STOPPED_WITH_AN_ERROR` when it
        raises, the exception propagating.

        A live scan that finds another one already running doesn't scan, prints why,
        writes a WARNING ``renewals.run`` audit record with the reason
        ``run_in_progress``, closes its row with that message, and exits cleanly; run
        through ``manage.py run_job``, it doesn't leave a job record, since the scan
        under way keeps its own.

        After the scan, if any charge was refused, or after a live scan any charge is
        held in doubt waiting for a treasurer, ``CommandError`` is raised naming how
        many, so the command exits non-zero and the systemd unit goes to ``failed``
        every morning until somebody settles them, rather than reporting a clean run.
        """
        scan_date: date | None = None
        if options["today"]:
            try:
                scan_date = date.fromisoformat(options["today"])
            except ValueError as exc:
                raise CommandError(f"--today must be YYYY-MM-DD, not {options['today']!r}") from exc

        scan: RenewalScan | None = None
        actor: Model | str = audit.COMMAND_ACTOR
        if options["scan_id"] is not None:
            scan = (
                RenewalScan.objects.select_related("started_by")
                .filter(pk=options["scan_id"])
                .first()
            )
            if scan is None:
                raise CommandError(f"No renewal scan {options['scan_id']}.")
            if scan.started_by is not None:
                actor = scan.started_by

        try:
            run = run_auto_renewals(today=scan_date, dry_run=options["dry_run"], actor=actor)
        except RenewalsBusyError as exc:
            # Another live scan is charging; this one didn't do anything and says so.
            audit.refuse(audit.RENEWALS_RUN, actor=actor, reason=audit.REASON_RUN_IN_PROGRESS)
            if scan is not None:
                close_scan(scan, error=str(exc))
            # The scan already under way keeps its own record of the run.
            skip_record()
            self.stdout.write(self.style.WARNING(str(exc)))
            return
        except Exception:
            # The scan records each member's problem and carries on, so whatever reaches
            # here stopped the whole run; the row says so, and the traceback goes on.
            if scan is not None:
                log.exception("renewal scan %s stopped with an error", scan.pk)
                close_scan(scan, error=STOPPED_WITH_AN_ERROR)
            raise
        if scan is not None:
            finish_scan(scan, run)

        for line in run.as_lines():
            self.stdout.write(line)

        style = self.style.WARNING if run.dry_run else self.style.SUCCESS
        verb = "would charge" if run.dry_run else "charged"
        self.stdout.write(style(f"noticed {run.noticed}, {verb} {run.charged}"))

        problems: list[str] = []
        if run.failed > 0:
            plural = "" if run.failed == 1 else "s"
            problems.append(
                f"{run.failed} renewal charge{plural} was refused; "
                "the renewals screen names the member and the reason"
            )
        doubtful = 0 if run.dry_run else charges_in_doubt()
        if doubtful > 0:
            plural = "" if doubtful == 1 else "s"
            problems.append(
                f"{doubtful} renewal charge{plural} need{'' if plural else 's'} checking; "
                "settle them on the finance Renewals tab"
            )
        if problems:
            raise CommandError("; and ".join(problems))
