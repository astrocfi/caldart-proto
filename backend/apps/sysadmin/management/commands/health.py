"""``manage.py health`` -- the database, migrations, disk, backups, and scheduled jobs."""

import json
from typing import Any

from django.core.management.base import BaseCommand, CommandParser

from apps.sysadmin.api.serializers import HealthSerializer
from apps.sysadmin.services import health


class Command(BaseCommand):
    """``manage.py health`` command: prints or emits the system health summary."""

    help = "Print a system health summary."

    def add_arguments(self, parser: CommandParser) -> None:
        """Register ``--json``, which emits the report as JSON instead of a table."""
        parser.add_argument("--json", action="store_true", help="Emit JSON instead of a table.")

    def handle(self, *args: Any, **options: Any) -> None:
        """Print the health report from :func:`apps.sysadmin.services.health`.

        With ``--json``, writes the report as ``GET /system/health`` answers it, as
        indented JSON; otherwise writes one ``label   value`` line per field, with a
        missing value shown as an em dash, and then one line per scheduled job naming
        it and its state.
        """
        report = health()
        if options["json"]:
            self.stdout.write(json.dumps(HealthSerializer(report).data, indent=2))
            return
        for key, value in report.items():
            if key == "scheduled_jobs":
                continue
            label = key.replace("_", " ")
            self.stdout.write(f"{label:<20} {value if value is not None else '\u2014'}")
        for status in report["scheduled_jobs"]:
            self.stdout.write(f"{status.job.label:<28} {status.state.value}")
