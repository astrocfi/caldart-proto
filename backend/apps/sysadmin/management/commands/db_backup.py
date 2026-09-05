"""``manage.py db_backup`` — write a gzipped pg_dump into ``BACKUP_DIR``."""

from django.core.management.base import BaseCommand, CommandError

from apps.sysadmin.services import BackupError, create_backup


class Command(BaseCommand):
    help = "Dump the database to backups/caldart-<timestamp>.sql.gz."

    def add_arguments(self, parser):
        parser.add_argument("--name", help="Override the generated file name.")

    def handle(self, *args, **options):
        try:
            backup = create_backup(options.get("name"))
        except BackupError as exc:
            raise CommandError(str(exc)) from exc
        size_mb = backup.size_bytes / (1024 * 1024)
        self.stdout.write(self.style.SUCCESS(f"Wrote {backup.path} ({size_mb:.1f} MB)"))
