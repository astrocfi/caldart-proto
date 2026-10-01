"""``manage.py normalize_casing`` -- put stored names and addresses in their saved casing.

Every save already normalizes a person's first and last name
(:func:`caldart.casing.person_name`) and a profile's street and city
(:func:`caldart.casing.title_case_words`); this applies the same rules to the rows stored
before those rules existed, or written past ``save()``.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Iterable
from typing import Any

from django.core.management.base import BaseCommand
from django.db import models, transaction

from apps.accounts.models import User
from apps.members.models import MemberProfile
from caldart.casing import person_name, title_case_words

#: The account columns the command normalizes, and the rule each one follows.
USER_RULES: tuple[tuple[str, Callable[[str], str]], ...] = (
    ("first_name", person_name),
    ("last_name", person_name),
)

#: The profile columns the command normalizes, and the rule each one follows.
PROFILE_RULES: tuple[tuple[str, Callable[[str], str]], ...] = tuple(
    (field, title_case_words) for field in MemberProfile.TITLE_CASE_FIELDS
)


class Command(BaseCommand):
    """Normalizes every stored name, street, and city, listing each change."""

    help = (
        "Title-case first and last names typed in one case, and every street and city, "
        "in the rows already stored."
    )

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Register ``--dry-run`` on the command's argument parser."""
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List what would change without writing anything.",
        )

    @transaction.atomic
    def handle(self, *args: Any, **options: Any) -> None:
        """Normalize every account's names and every profile's street and city.

        Each field whose stored value differs from its normalized one is printed as
        ``<email>: <field> "<old>" -> "<new>"``, accounts first and then profiles, each
        in primary-key order, and the run ends with ``Changed <n> fields.`` (``Would
        change`` under ``--dry-run``).  Only a row with a changed field is written, and
        only its changed columns, by a queryset update that runs no ``save()`` and moves
        no timestamp.  ``--dry-run`` writes nothing.
        """
        dry_run: bool = options["dry_run"]
        users = User.objects.order_by("pk")
        profiles = MemberProfile.objects.select_related("user").order_by("pk")
        count = self._normalize(users, USER_RULES, email=lambda user: user.email, dry_run=dry_run)
        count += self._normalize(
            profiles, PROFILE_RULES, email=lambda profile: profile.user.email, dry_run=dry_run
        )
        verb = "Would change" if dry_run else "Changed"
        plural = "" if count == 1 else "s"
        self.stdout.write(f"{verb} {count} field{plural}.")

    def _normalize[Row: models.Model](
        self,
        rows: Iterable[Row],
        rules: tuple[tuple[str, Callable[[str], str]], ...],
        *,
        email: Callable[[Row], str],
        dry_run: bool,
    ) -> int:
        """Apply ``rules`` to each of ``rows``, print every change, and count them.

        Unless ``dry_run``, each row with a change is written with only its changed
        columns.
        """
        count = 0
        for row in rows:
            changes: dict[str, str] = {}
            for field, rule in rules:
                stored: str = getattr(row, field)
                normalized = rule(stored)
                if normalized != stored:
                    changes[field] = normalized
                    self.stdout.write(f'{email(row)}: {field} "{stored}" -> "{normalized}"')
            count += len(changes)
            if changes and not dry_run:
                type(row)._default_manager.filter(pk=row.pk).update(**changes)
        return count
