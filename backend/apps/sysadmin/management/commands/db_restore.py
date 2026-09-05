"""``manage.py db_restore <file>`` — restore a gzipped dump."""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.sysadmin.services import BackupError, backup_dir, restore_backup


class Command(BaseCommand):
    help = "Restore a backup over the current database. Destructive."

    def add_arguments(self, parser):
        parser.add_argument("file", help="Path to a .sql.gz dump, or a name inside BACKUP_DIR.")
        parser.add_argument(
            "--noinput",
            "--no-input",
            action="store_false",
            dest="interactive",
            help="Do not prompt for confirmation.",
        )

    def handle(self, *args, **options):
        path = Path(options["file"])
        if not path.is_file():
            path = backup_dir() / options["file"]

        if options["interactive"]:
            answer = input(f"Restore '{path.name}' over the current database? Type yes: ")
            if answer.strip().lower() != "yes":
                raise CommandError("Aborted.")

        try:
            restore_backup(path)
        except BackupError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"Restored {path}"))
