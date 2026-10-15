"""``manage.py run_job <command> [options...]`` -- run a scheduled job and record the run.

Every unit under ``deploy/systemd/`` that runs a scheduled job calls its command through
here, and so do the **Run now** presses that start a command in its own process.  The
command's output still goes to standard output and standard error, so the journal keeps
everything, and a :class:`~apps.sysadmin.models.JobRun` row keeps a copy the System
pages read.  The process exits with the status the command alone would have.
"""

from __future__ import annotations

import argparse
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import User
from apps.sysadmin.jobs import JOBS, JOBS_BY_COMMAND
from apps.sysadmin.recording import run_recorded


class Command(BaseCommand):
    """Runs one of the scheduled jobs' commands and records how the run went."""

    help = "Run a scheduled job's command, passing on its options, and record the run."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Register the command name, its options, and ``--started-by``."""
        parser.add_argument(
            "--started-by",
            type=int,
            default=None,
            metavar="USER_ID",
            help="The system administrator who pressed Run now (default: the server).",
        )
        parser.add_argument(
            "job_command",
            metavar="command",
            help=f"One of: {', '.join(job.command for job in JOBS)}.",
        )
        parser.add_argument(
            "job_arguments",
            nargs=argparse.REMAINDER,
            metavar="...",
            help="Options passed on to the command unchanged.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Run the named command with its options and record the run.

        Raises ``CommandError`` when the command is not one of the scheduled jobs', or
        ``--started-by`` doesn't name a user, before anything is recorded.  Otherwise the
        command's own exception, if any, propagates after the run is recorded.
        """
        name = options["job_command"]
        if name not in JOBS_BY_COMMAND:
            raise CommandError(
                f"{name!r} is not a scheduled job; choose one of "
                f"{', '.join(job.command for job in JOBS)}."
            )
        started_by: User | None = None
        if options["started_by"] is not None:
            started_by = User.objects.filter(pk=options["started_by"]).first()
            if started_by is None:
                raise CommandError(f"No user {options['started_by']}.")
        run_recorded(JOBS_BY_COMMAND[name], options["job_arguments"], started_by=started_by)
