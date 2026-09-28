"""``manage.py seed_plans`` -- create the membership plans, idempotently."""

from typing import Any

from django.core.management.base import BaseCommand

from apps.members.plans import PLANS, seed_plans


class Command(BaseCommand):
    """``manage.py seed_plans`` -- create or update the membership plans.

    Writes the plans in ``apps.members.plans.PLANS`` (annual and life), keyed on their
    slugs, so a site that never loads the demo data still has plans to sell, and a
    second run changes nothing but a price or description edited by hand.  Prints one
    line per plan and a closing count.
    """

    help = "Create the CalDART membership plans (idempotent)."

    def handle(self, *args: Any, **options: Any) -> None:
        """Create or update every plan and report how many exist afterwards."""
        self.stdout.write("Seeding membership plans:")
        for plan in seed_plans():
            self.stdout.write(f"  {plan.slug}: {plan.name}")
        self.stdout.write(self.style.SUCCESS(f"{len(PLANS)} plans present."))
