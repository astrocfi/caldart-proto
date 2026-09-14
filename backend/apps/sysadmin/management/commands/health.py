"""``manage.py health`` — DB connectivity, pending migrations, disk, backups."""

import json

from django.core.management.base import BaseCommand

from apps.sysadmin.services import health


class Command(BaseCommand):
    help = "Print a system health summary."

    def add_arguments(self, parser):
        parser.add_argument("--json", action="store_true", help="Emit JSON instead of a table.")

    def handle(self, *args, **options):
        report = health()
        if options["json"]:
            self.stdout.write(json.dumps(report, indent=2))
            return
        for key, value in report.items():
            label = key.replace("_", " ")
            self.stdout.write(f"{label:<20} {value if value is not None else '—'}")
