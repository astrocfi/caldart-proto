"""``manage.py db_backup`` — write a gzipped pg_dump into ``BACKUP_DIR``."""

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.sysadmin.services import BackupError, create_backup


class Command(BaseCommand):
    """``manage.py db_backup`` command: writes a gzipped dump and reports its size."""

    help = "Dump the database to backups/caldart-<timestamp>.sql.gz."

    def add_arguments(self, parser: CommandParser) -> None:
        """Register ``--name``, which overrides the generated dump file name."""
        parser.add_argument("--name", help="Override the generated file name.")

    def handle(self, *args: Any, **options: Any) -> None:
        """Write the dump and print its path and size in MB.

        Raises ``CommandError`` when neither ``pg_dump`` nor docker is available,
        or ``pg_dump`` itself fails.
        """
        try:
            backup = create_backup(options.get("name"))
        except BackupError as exc:
            raise CommandError(str(exc)) from exc
        size_mb = backup.size_bytes / (1024 * 1024)
        self.stdout.write(self.style.SUCCESS(f"Wrote {backup.path} ({size_mb:.1f} MB)"))
