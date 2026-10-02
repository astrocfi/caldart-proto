"""``manage.py check_bounces`` -- the hourly read of the bounce mailbox.

Run by ``deploy/systemd/caldart-bounces.timer`` every hour in production.  Safe to
repeat: each message read is marked seen, so the next run reads only what has arrived
since.  With ``BOUNCE_IMAP_URL`` empty the command says bounce checking is off and
exits cleanly; a mailbox that cannot be reached or read makes it exit non-zero, so the
systemd unit goes to ``failed``.
"""

from __future__ import annotations

import argparse
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.mail.bounces import BounceCheckError, check_bounces


class Command(BaseCommand):
    """Runs the bounce check and reports its results to stdout."""

    help = "Read the bounce mailbox and mark every email that bounced."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Register ``--dry-run``."""
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be marked without changing anything or marking mail seen.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Run the check and print its summary.

        Raises ``CommandError`` with the check's own sentence when ``BOUNCE_IMAP_URL``
        is malformed or the mailbox cannot be reached or read.
        """
        try:
            run = check_bounces(dry_run=options["dry_run"])
        except BounceCheckError as exc:
            raise CommandError(str(exc)) from exc

        for line in run.as_lines():
            self.stdout.write(line)
        if not run.enabled:
            return

        style = self.style.WARNING if run.dry_run else self.style.SUCCESS
        verb = "would mark" if run.dry_run else "marked"
        self.stdout.write(
            style(f"{verb} {run.bounced} bounced, {run.unmatched} unmatched, {run.ignored} ignored")
        )
