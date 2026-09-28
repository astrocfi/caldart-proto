"""The membership plans every CalDART site starts with, and the seeder that writes them.

The table is what ``manage.py seed_plans``, the ``members`` data migration, and the demo
seed all create from, so a site has its plans as soon as it is migrated, whether or not
the demo data is ever loaded.  This module imports no model at import time, so a
migration may import it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from apps.members.models import MembershipPlan


class PlanSpec(TypedDict):
    """One membership plan the seed creates, keyed on its slug."""

    name: str
    slug: str
    price_cents: int
    duration_days: int | None
    sort_order: int
    description: str


#: The membership plans to seed: an annual plan and a lifetime one.
PLANS: tuple[PlanSpec, ...] = (
    {
        "name": "Annual",
        "slug": "annual",
        "price_cents": 4_500,
        "duration_days": 365,
        "sort_order": 1,
        "description": "One year of CalDART membership, renewable each year.",
    },
    {
        "name": "Life",
        "slug": "life",
        "price_cents": 65_000,
        "duration_days": None,
        "sort_order": 2,
        "description": "A lifetime membership. Pay once, never renew.",
    },
)


def seed_plans() -> list[MembershipPlan]:
    """Create or update every plan in :data:`PLANS`, and return them in that order.

    Each is keyed on its slug, so running the seed twice leaves one row per plan with
    the price, duration, and description the table gives it, and ``is_active`` on.
    """
    # Inline: this module is imported by a migration, which must not import models.
    from apps.members.models import MembershipPlan

    plans = []
    for spec in PLANS:
        plan, _ = MembershipPlan.objects.update_or_create(
            slug=spec["slug"],
            defaults={
                "name": spec["name"],
                "price_cents": spec["price_cents"],
                "duration_days": spec["duration_days"],
                "sort_order": spec["sort_order"],
                "description": spec["description"],
                "is_active": True,
            },
        )
        plans.append(plan)
    return plans
