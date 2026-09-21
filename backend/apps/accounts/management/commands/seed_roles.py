"""Create the role groups.  Idempotent."""

from typing import Any

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, OutputWrapper

from apps.accounts.roles import ROLE_SLUGS


def seed_roles(stdout: OutputWrapper | None = None) -> list[Group]:
    """Ensure one ``Group`` exists per role slug, and return them in slug order.

    Safe to run repeatedly: a group that already exists is returned untouched, and no
    role is ever removed.  When ``stdout`` is given, each slug is written to it as
    ``created`` or ``exists``.
    """
    groups = []
    for slug in ROLE_SLUGS:
        group, created = Group.objects.get_or_create(name=slug)
        groups.append(group)
        if stdout is not None:
            stdout.write(f"  {'created' if created else 'exists '}  {slug}")
    return groups


class Command(BaseCommand):
    """``manage.py seed_roles`` -- create the role groups, idempotently."""

    help = "Create the CalDART role groups (idempotent)."

    def handle(self, *args: Any, **options: Any) -> None:
        """Create any missing role group and report how many roles exist afterwards."""
        self.stdout.write("Seeding roles:")
        seed_roles(self.stdout)
        self.stdout.write(self.style.SUCCESS(f"{len(ROLE_SLUGS)} roles present."))
