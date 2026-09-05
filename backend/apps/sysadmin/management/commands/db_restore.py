"""``manage.py db_restore <file>`` — restore a gzipped dump (PLAN §4.7).

Destructive: the ``public`` schema is dropped and recreated before the dump is
replayed, because ``pg_dump`` writes ``CREATE TABLE`` without ``DROP``.
"""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.sysadmin.services import BackupError, backup_dir, restore_backup


class Command(BaseCommand):
    help = "Restore a backup over the current database. Destructive."

    def add_arguments(self, parser):
        parser.add_argument("file", help="Path to a .sql.gz dump, or a name inside BACKUP_DIR.")
        parser.add_argument(
            "--yes",
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
        if not path.is_file():
            raise CommandError(f"No such backup: {options['file']}")

        name = settings.DATABASES["default"]["NAME"]

        if options["interactive"]:
            answer = input(
                f"Restore '{path.name}' over '{name}'? Every existing table is dropped. Type yes: "
            )
            if answer.strip().lower() != "yes":
                raise CommandError("Aborted.")

        self.stdout.write(f"Dropping the public schema in '{name}'…")
        try:
            restore_backup(path)
        except BackupError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(self.style.SUCCESS(f"Restored {path} into '{name}'"))
