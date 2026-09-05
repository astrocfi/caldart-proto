"""``manage.py db_reset`` — drop and rebuild the development database."""

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from apps.sysadmin.services import drop_schema


class Command(BaseCommand):
    help = "Drop the public schema, re-migrate, and optionally re-seed. Destructive."

    def add_arguments(self, parser):
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

    def handle(self, *args, **options):
        from django.conf import settings

        name = settings.DATABASES["default"]["NAME"]

        if options["interactive"]:
            answer = input(f"This will DESTROY every table in '{name}'. Type yes to continue: ")
            if answer.strip().lower() != "yes":
                raise CommandError("Aborted.")

        self.stdout.write(f"Dropping the public schema in '{name}'…")
        drop_schema()

        self.stdout.write("Migrating…")
        call_command("migrate", verbosity=0)
        call_command("seed_roles", verbosity=0)

        if options["seed"]:
            self.stdout.write("Seeding…")
            call_command("seed_demo")
            try:
                call_command("seed_content")
            except Exception as exc:  # pragma: no cover - until feat/cms-site lands
                self.stdout.write(self.style.WARNING(f"seed_content skipped: {exc}"))

        self.stdout.write(self.style.SUCCESS(f"Database '{name}' reset."))
