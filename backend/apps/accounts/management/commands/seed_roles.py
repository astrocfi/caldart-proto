"""Create the role groups (PLAN §4.1).  Idempotent."""

from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand

from apps.accounts.roles import ROLE_SLUGS


def seed_roles(stdout=None) -> list[Group]:
    """Ensure one ``Group`` exists per role slug.  Safe to run repeatedly."""
    groups = []
    for slug in ROLE_SLUGS:
        group, created = Group.objects.get_or_create(name=slug)
        groups.append(group)
        if stdout is not None:
            stdout.write(f"  {'created' if created else 'exists '}  {slug}")
    return groups


class Command(BaseCommand):
    help = "Create the CalDART role groups (idempotent)."

    def handle(self, *args, **options):
        self.stdout.write("Seeding roles:")
        seed_roles(self.stdout)
        self.stdout.write(self.style.SUCCESS(f"{len(ROLE_SLUGS)} roles present."))
