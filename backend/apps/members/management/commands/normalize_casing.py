"""``manage.py normalize_casing`` -- put stored names and addresses in their saved casing.

Every save already normalizes a person's name (:func:`caldart.casing.person_name`): an
account's first and last name, a profile's emergency contact, a DART contact, an
individual aircraft owner, and a DART page's leader; and a profile's street and city
(:func:`caldart.casing.title_case_words`).  This applies the same rules to the rows stored
before those rules existed, or written past ``save()``.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Iterable
from typing import Any

from django.core.management.base import BaseCommand
from django.db import models, transaction

from apps.accounts.models import User
from apps.aircraft.models import Aircraft, OwnerType
from apps.cms.models import DartPage
from apps.darts.models import DartContact
from apps.members.models import MemberProfile
from caldart.casing import person_name, title_case_words

#: The account columns the command normalizes, and the rule each one follows.
USER_RULES: tuple[tuple[str, Callable[[str], str]], ...] = (
    ("first_name", person_name),
    ("last_name", person_name),
)

#: The profile columns the command normalizes, and the rule each one follows.
PROFILE_RULES: tuple[tuple[str, Callable[[str], str]], ...] = (
    *((field, title_case_words) for field in MemberProfile.TITLE_CASE_FIELDS),
    *((field, person_name) for field in MemberProfile.PERSON_NAME_FIELDS),
)

#: The single-name columns of the other models, each a person's name.
DART_CONTACT_RULES: tuple[tuple[str, Callable[[str], str]], ...] = (("name", person_name),)
AIRCRAFT_RULES: tuple[tuple[str, Callable[[str], str]], ...] = (("owner_name", person_name),)
DART_PAGE_RULES: tuple[tuple[str, Callable[[str], str]], ...] = (("leader_name", person_name),)


class Command(BaseCommand):
    """Normalizes every stored person's name, street, and city, listing each change."""

    help = (
        "Title-case people's names typed in one case, and every street and city, "
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
        """Normalize every stored person's name, and every profile's street and city.

        Each field whose stored value differs from its normalized one is printed as
        ``<row>: <field> "<old>" -> "<new>"``, where ``<row>`` is the account's email for
        an account or a profile, ``DART contact <id>``, ``aircraft <N-number>`` (an
        individual owner's only), or ``DART page <id>``, in that order of models and
        each in primary-key order, and the run ends with ``Changed <n> fields.``
        (``Would change`` under ``--dry-run``).  Only a row with a changed field is
        written, and only its changed columns, by a queryset update that runs no
        ``save()`` and moves no timestamp.  ``--dry-run`` writes nothing.
        """
        dry_run: bool = options["dry_run"]
        users = User.objects.order_by("pk")
        profiles = MemberProfile.objects.select_related("user").order_by("pk")
        count = self._normalize(users, USER_RULES, label=lambda user: user.email, dry_run=dry_run)
        count += self._normalize(
            profiles, PROFILE_RULES, label=lambda profile: profile.user.email, dry_run=dry_run
        )
        count += self._normalize(
            DartContact.objects.order_by("pk"),
            DART_CONTACT_RULES,
            label=lambda contact: f"DART contact {contact.pk}",
            dry_run=dry_run,
        )
        count += self._normalize(
            Aircraft.objects.filter(owner_type=OwnerType.INDIVIDUAL).order_by("pk"),
            AIRCRAFT_RULES,
            label=lambda aircraft: f"aircraft {aircraft.n_number}",
            dry_run=dry_run,
        )
        count += self._normalize(
            DartPage.objects.order_by("pk"),
            DART_PAGE_RULES,
            label=lambda page: f"DART page {page.pk}",
            dry_run=dry_run,
        )
        verb = "Would change" if dry_run else "Changed"
        plural = "" if count == 1 else "s"
        self.stdout.write(f"{verb} {count} field{plural}.")

    def _normalize[Row: models.Model](
        self,
        rows: Iterable[Row],
        rules: tuple[tuple[str, Callable[[str], str]], ...],
        *,
        label: Callable[[Row], str],
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
                    self.stdout.write(f'{label(row)}: {field} "{stored}" -> "{normalized}"')
            count += len(changes)
            if changes and not dry_run:
                type(row)._default_manager.filter(pk=row.pk).update(**changes)
        return count
