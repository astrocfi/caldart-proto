"""``manage.py seed_demo`` — idempotent demo data.

Each app owns ``apps/<app>/seed.py`` exposing ``run(ctx, stdout=None) -> ctx``.
They run in the order below and share one ``ctx`` dict, so a later app can use
the rows an earlier one created.
"""

from __future__ import annotations

import random
from importlib import import_module
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from django.utils import timezone
from faker import Faker

from apps.accounts.management.commands.seed_roles import seed_roles

#: Seed modules in dependency order.
SEED_APPS: tuple[str, ...] = (
    "apps.accounts",
    "apps.members",
    "apps.aircraft",
    "apps.payments",
    "apps.cms",
)

#: Fixed so the demo data is the same on every machine.
RANDOM_SEED = 20260904


class Command(BaseCommand):
    """``manage.py seed_demo`` -- create the demo data set, idempotently."""

    help = "Create the CalDART demo data set (idempotent)."

    def add_arguments(self, parser: CommandParser) -> None:
        """Declare ``--seed``, the integer that makes the generated data reproducible."""
        parser.add_argument(
            "--seed",
            type=int,
            default=RANDOM_SEED,
            help="Random seed, so the generated data is reproducible.",
        )

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        """Seed the roles, then run each app's seeder in dependency order.

        Everything happens in one transaction, so a failure part-way leaves the
        database as it was.  The seeders share one context dictionary, so a later app
        can use the rows an earlier one created.  Re-running updates the existing rows
        rather than duplicating them.
        """
        seed = options["seed"]
        faker = Faker("en_US")
        Faker.seed(seed)

        ctx: dict[str, Any] = {
            "rng": random.Random(seed),  # noqa: S311 - demo data, not security-sensitive
            "faker": faker,
            "today": timezone.localdate(),
            "stdout": self.stdout,
        }

        self.stdout.write("Seeding demo data:")
        seed_roles()

        for dotted in SEED_APPS:
            module = import_module(f"{dotted}.seed")
            module.run(ctx, self.stdout)

        self.stdout.write(self.style.SUCCESS("Demo data ready. Password: caldart-demo"))
