"""``manage.py import_faa_registry`` -- import the FAA's Releasable Aircraft Database."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.aircraft.models import RegistryImport
from apps.aircraft.registry import import_registry


class Command(BaseCommand):
    """Import the aircraft types and the registrations from the FAA registry.

    ``--source`` names a URL of the zip, a local zip, or a directory holding
    ``ACFTREF.txt`` and ``MASTER.txt``; without it the command reads
    ``FAA_REGISTRY_URL``.  ``--types-only`` skips the master file.  ``--import-id``
    fills in the ``RegistryImport`` row the Health and database page wrote rather than
    creating one.  A failed import is recorded on its row and raises ``CommandError``.
    """

    help = "Import the aircraft types and registrations from the FAA registry."

    def add_arguments(self, parser: CommandParser) -> None:
        """Declare ``--source``, ``--types-only``, and ``--import-id``."""
        parser.add_argument(
            "--source",
            default="",
            help="URL, zip, or directory to read (default: FAA_REGISTRY_URL).",
        )
        parser.add_argument(
            "--types-only",
            action="store_true",
            help="Refresh the aircraft types and skip the registrations.",
        )
        parser.add_argument(
            "--import-id",
            type=int,
            default=None,
            help="Fill in this RegistryImport row instead of creating one.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Run the import and write its counts to stdout.

        Raises ``CommandError`` when ``--import-id`` names no row, and when the import
        fails, with the reason the row records.
        """
        run: RegistryImport | None = None
        if options["import_id"] is not None:
            run = RegistryImport.objects.filter(pk=options["import_id"]).first()
            if run is None:
                raise CommandError(f"No registry import {options['import_id']}.")
        source = options["source"] or settings.FAA_REGISTRY_URL
        try:
            run = import_registry(source, types_only=options["types_only"], run=run)
        except Exception as exc:
            # Every failure is already on the run's row; the operator gets the reason.
            raise CommandError(f"Registry import failed: {exc}") from exc
        summary = (
            f"Imported {run.types_written} types and {run.registrations_written} registrations"
        )
        if run.types_folded > 0:
            summary += f", folded {run.types_folded} hand-added types"
        self.stdout.write(f"{summary}.")
