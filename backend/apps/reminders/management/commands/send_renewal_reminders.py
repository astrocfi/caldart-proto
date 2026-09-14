"""``manage.py send_renewal_reminders`` — the daily renewal scan.

Run by ``deploy/systemd/caldart-reminders.timer`` at 07:00 in production and by
``make reminders`` in development.  Safe to repeat: ``ReminderLog`` dedupes on
``(user, membership, kind)``.
"""

from __future__ import annotations

from datetime import date

from django.core.management.base import BaseCommand, CommandError

from apps.reminders.services import send_renewal_reminders


class Command(BaseCommand):
    help = "Send t60/t30/t7/expired/post30 renewal reminders and expire lapsed terms."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be sent without writing or emailing anything.",
        )
        parser.add_argument(
            "--today",
            metavar="YYYY-MM-DD",
            help="Scan as of this date instead of today. Useful for rehearsals.",
        )

    def handle(self, *args, **options):
        scan_date: date | None = None
        if options["today"]:
            try:
                scan_date = date.fromisoformat(options["today"])
            except ValueError as exc:
                raise CommandError(f"--today must be YYYY-MM-DD, not {options['today']!r}") from exc

        run = send_renewal_reminders(today=scan_date, dry_run=options["dry_run"])

        for line in run.as_lines():
            self.stdout.write(line)

        style = self.style.WARNING if run.dry_run else self.style.SUCCESS
        verb = "would send" if run.dry_run else "sent"
        self.stdout.write(style(f"{verb} {run.sent}, skipped {run.skipped}"))
