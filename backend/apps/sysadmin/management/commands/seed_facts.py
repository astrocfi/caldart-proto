"""``manage.py seed_facts`` -- describe the demo data set as JSON.

The end-to-end specs need the values ``seed_demo`` builds its demo accounts
from: the shared password, the address of each named account, and what each
membership plan costs. Reading them from a JSON document keeps them in one
place -- the seed modules -- instead of being copied into a spec that then
drifts when the seed changes.
"""

from __future__ import annotations

import json
from typing import Any

from django.core.management.base import BaseCommand

from apps.accounts.seed import DEMO_ACCOUNTS, DEMO_PASSWORD
from apps.members.models import MembershipPlan


def seed_facts() -> dict[str, Any]:
    """Return the demo data set's facts, ready to serialize as JSON.

    ``demoPassword`` is the password every seeded demo account shares, and
    ``accounts`` maps each demo key (``member``, ``leader``, ``sysadmin`` and the
    rest) to that account's address. ``planPricesCents`` maps each membership
    plan's slug to its price in cents, read from the database so it reflects the
    plans that are actually there.
    """
    return {
        "demoPassword": DEMO_PASSWORD,
        "accounts": {key: email for key, email, *_rest in DEMO_ACCOUNTS},
        "planPricesCents": {
            plan.slug: plan.price_cents for plan in MembershipPlan.objects.order_by("slug")
        },
    }


class Command(BaseCommand):
    """``manage.py seed_facts`` -- print the demo data set's facts as JSON."""

    help = "Print the demo data set's facts as JSON, for the end-to-end specs."

    def handle(self, *args: Any, **options: Any) -> None:
        """Write the facts to stdout as a JSON object, sorted and indented."""
        self.stdout.write(json.dumps(seed_facts(), indent=2, sort_keys=True))
