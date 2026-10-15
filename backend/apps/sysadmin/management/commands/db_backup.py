"""``manage.py db_backup`` -- write a gzipped pg_dump into ``BACKUP_DIR``."""

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.sysadmin.services import MIN_PRUNE_DAYS, BackupError, create_backup, prune_backups


class Command(BaseCommand):
    """``manage.py db_backup`` command: writes a gzipped dump and reports its size."""

    help = "Dump the database to backups/caldart-<timestamp>.sql.gz."

    def add_arguments(self, parser: CommandParser) -> None:
        """Register ``--name`` and ``--prune-days``.

        ``--prune-days`` takes its value as text, so an empty one, as systemd passes for
        an unset ``BACKUP_RETENTION_DAYS``, still lets the dump run.
        """
        parser.add_argument("--name", help="Override the generated file name.")
        parser.add_argument(
            "--prune-days",
            default=None,
            metavar="DAYS",
            help="After the dump, delete the generated dumps more than DAYS days old.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Write the dump and print its path and size in MB, then prune if asked.

        Raises ``CommandError`` when neither ``pg_dump`` nor docker is available, or
        ``pg_dump`` itself fails, and then leaves every dump in place.  After a dump
        that succeeded, ``--prune-days`` runs
        :func:`~apps.sysadmin.services.prune_backups` and names each deleted file on its
        own line.  An empty ``--prune-days`` prints a warning and keeps every dump; one
        that is not a whole number of at least :data:`MIN_PRUNE_DAYS` raises
        ``CommandError`` after the dump, keeping every dump, so the unit reads failed
        while the night's dump is still taken.
        """
        try:
            backup = create_backup(options.get("name"))
        except BackupError as exc:
            raise CommandError(str(exc)) from exc
        size_mb = backup.size_bytes / (1024 * 1024)
        self.stdout.write(self.style.SUCCESS(f"Wrote {backup.path} ({size_mb:.1f} MB)"))

        value = options["prune_days"]
        if value is None:
            return
        if value.strip() == "":
            self.stderr.write("--prune-days is empty, so every dump is kept.")
            return
        try:
            days = int(value)
        except ValueError as exc:
            raise CommandError(f"--prune-days must be a whole number, not {value!r}") from exc
        if days < MIN_PRUNE_DAYS:
            raise CommandError(f"--prune-days must be at least {MIN_PRUNE_DAYS}, not {days}")
        for name in prune_backups(days):
            self.stdout.write(f"Deleted {name}, more than {days} days old")
