"""``manage.py db_reset`` -- drop and rebuild the development database."""

from typing import Any

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.sysadmin.services import drop_schema
from caldart import audit


class Command(BaseCommand):
    """``manage.py db_reset`` command: drops the schema, migrates, and seeds roles."""

    help = "Drop the public schema, re-migrate, and optionally re-seed. Destructive."

    def add_arguments(self, parser: CommandParser) -> None:
        """Register ``--seed`` (also run the demo seeders) and ``--noinput``."""
        parser.add_argument(
            "--seed",
            action="store_true",
            help="Also run seed_demo and seed_content after migrating.",
        )
        parser.add_argument(
            "--noinput",
            "--no-input",
            action="store_false",
            dest="interactive",
            help="Do not prompt for confirmation.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Drop the public schema, migrate, seed roles, and optionally seed demo data.

        Prompts for confirmation and raises ``CommandError`` on any answer other
        than ``yes`` unless ``--noinput`` was given. Writes an
        ``caldart.audit.DB_RESET`` audit record on success.
        """
        from django.conf import settings

        name = settings.DATABASES["default"]["NAME"]

        if options["interactive"]:
            answer = input(f"This will DESTROY every table in '{name}'. Type yes to continue: ")
            if answer.strip().lower() != "yes":
                raise CommandError("Aborted.")

        self.stdout.write(f"Dropping the public schema in '{name}'\u2026")
        drop_schema()

        self.stdout.write("Migrating\u2026")
        call_command("migrate", verbosity=0)
        call_command("seed_roles", verbosity=0)

        if options["seed"]:
            self.stdout.write("Seeding\u2026")
            call_command("seed_demo")
            call_command("seed_content")

        audit.record(
            audit.DB_RESET,
            actor=audit.COMMAND_ACTOR,
            database=audit.safe_slug(name),
            seeded=options["seed"],
        )
        self.stdout.write(self.style.SUCCESS(f"Database '{name}' reset."))
