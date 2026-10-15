"""``manage.py db_backup`` -- write a gzipped pg_dump into ``BACKUP_DIR``."""

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.sysadmin.services import BackupError, create_backup, prune_backups


class Command(BaseCommand):
    """``manage.py db_backup`` command: writes a gzipped dump and reports its size."""

    help = "Dump the database to backups/caldart-<timestamp>.sql.gz."

    def add_arguments(self, parser: CommandParser) -> None:
        """Register ``--name`` and ``--prune-days``."""
        parser.add_argument("--name", help="Override the generated file name.")
        parser.add_argument(
            "--prune-days",
            type=int,
            default=None,
            metavar="DAYS",
            help="After the dump, delete the generated dumps more than DAYS days old.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Write the dump and print its path and size in MB, then prune if asked.

        With ``--prune-days``, a dump that succeeded is followed by
        :func:`~apps.sysadmin.services.prune_backups`, and each deleted file is named
        on its own line.  Raises ``CommandError`` when neither ``pg_dump`` nor docker
        is available, or ``pg_dump`` itself fails, and then doesn't prune; and when
        ``--prune-days`` is negative, before any dump.
        """
        days = options["prune_days"]
        if days is not None and days < 0:
            raise CommandError(f"--prune-days must be zero or more, not {days}")
        try:
            backup = create_backup(options.get("name"))
        except BackupError as exc:
            raise CommandError(str(exc)) from exc
        size_mb = backup.size_bytes / (1024 * 1024)
        self.stdout.write(self.style.SUCCESS(f"Wrote {backup.path} ({size_mb:.1f} MB)"))
        if days is None:
            return
        for name in prune_backups(days):
            self.stdout.write(f"Deleted {name}, more than {days} days old")
