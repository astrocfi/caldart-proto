"""The Disaster Airlift Response Teams themselves: their airports and their people.

A DART is more than a column on a member's record.  It is organized around one
or more airports, it is run by a handful of named volunteers, and it has a life
of its own -- it stands up, it retires, it merges -- so it lives in its own app
rather than inside the membership tables that point at it.
"""

from __future__ import annotations

import re
from typing import Any

from django.db import models

from caldart.models import TimestampedModel
from caldart.phone import normalize_phone

#: One airport identifier as this system stores it: exactly three letters or
#: digits.  The four-letter ICAO form is the same field with a ``K`` in front,
#: and that ``K`` is trimmed on the way in, so one airport is written one way
#: everywhere: ``KCRQ`` typed is ``CRQ`` stored.
AIRPORT_IDENTIFIER_RE = re.compile(r"^[A-Z0-9]{3}$")

AIRPORT_IDENTIFIER_MESSAGE = "Use a three-character identifier like PAO, E16, or KLS."

AIRPORT_IDENTIFIERS_MESSAGE = "Use three-character identifiers, separated by commas, like CCR, C83."

#: The longest list of airports a DART may cover.  San Diego's nine is the
#: largest real one; this leaves room without letting the field become prose.
MAX_AIRPORT_IDENTIFIERS = 12

#: How many people a DART may list.  A team is run by a handful of volunteers;
#: a longer list is a roster, which is what the member records are for.
MAX_DART_CONTACTS = 5


#: What separates one identifier from the next.  A comma is what the form
#: asks for; a space alone is what a pasted list often carries, and no
#: identifier holds one, so both are taken.
_SEPARATORS = re.compile(r"[,\s]+")


def normalize_airport_identifier(value: str) -> str:
    """Return one identifier as it is stored: upper-cased, ICAO ``K`` trimmed.

    A four-character identifier beginning with ``K`` is the ICAO spelling of a
    three-character one, so ``KCRQ`` comes back ``CRQ`` and ``KKAB`` comes back
    ``KAB``.  Three characters are returned as they are, ``K`` and all --
    Kelso really is ``KLS`` -- and anything else comes back upper-cased for the
    caller to refuse.
    """
    typed = value.strip().upper()
    if len(typed) == 4 and typed.startswith("K"):
        return typed[1:]
    return typed


def split_airport_identifiers(value: str | None) -> list[str]:
    """Return the identifiers in ``value``, in the order given, as they are stored.

    ``"ccr, c83"``, ``"CCR,C83"`` and ``"CCR C83"`` all come back
    ``["CCR", "C83"]``, and ``"KCRQ, KMYF"`` comes back ``["CRQ", "MYF"]``:
    one airport is spelled one way, whichever way it was typed.  A comma or a
    space separates one from the next, and empty entries are dropped, so a
    trailing comma is not an identifier and a blank value gives an empty
    list.  Nothing here judges whether what is left is well formed;
    that is the serializer's job.
    """
    if not value:
        return []
    return [normalize_airport_identifier(part) for part in _SEPARATORS.split(value) if part.strip()]


def normalize_airport_identifiers(value: str | None) -> str:
    """Return ``value`` as the canonical ``"CCR, C83"`` form.

    One spelling is stored, whichever way it was typed, so the list reads the
    same on every screen and in every export.
    """
    return ", ".join(split_airport_identifiers(value))


class Dart(TimestampedModel):  # type: ignore[django-manager-missing]
    """A local Disaster Airlift Response Team."""

    name = models.CharField(max_length=120, unique=True)
    #: Every field the team flies from, comma-separated: a DART is organized
    #: around its airports, and several of them cover more than one.
    airport_identifiers = models.CharField(
        max_length=120,
        help_text="FAA or ICAO identifiers, separated by commas, e.g. CCR, C83",
    )
    #: Many teams run a site of their own; it is where a visitor finds meeting
    #: times and local contacts that do not belong in this database.
    website_url = models.URLField(
        "website", max_length=200, blank=True, help_text="The team's own site, if it has one."
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        # Alphabetical, everywhere: a reader looking for their own team scans
        # for its name, and no hand-kept ordering can go stale.
        ordering = ["name"]
        verbose_name = "DART"
        verbose_name_plural = "DARTs"
        indexes = [models.Index(fields=["is_active", "name"], name="darts_dart_active_idx")]

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Save the DART with its airports in the canonical ``"CCR, C83"`` form."""
        self.airport_identifiers = normalize_airport_identifiers(self.airport_identifiers)
        super().save(*args, **kwargs)

    @property
    def airports(self) -> list[str]:
        """Every identifier this DART flies from, in the order it was given."""
        return split_airport_identifiers(self.airport_identifiers)

    @property
    def home_airport(self) -> str:
        """The first identifier, which is the one a single-line summary shows."""
        airports = self.airports
        return airports[0] if airports else ""

    def __str__(self) -> str:
        """The name, with its airports in parentheses."""
        if self.airport_identifiers:
            return f"{self.name} ({self.airport_identifiers})"
        return self.name


class DartContact(TimestampedModel):
    """One named volunteer who runs a DART, and how to reach them.

    These are the people an emergency manager or a prospective member asks for
    by name -- the leader, the deputy, the ground-team lead -- which is a
    different thing from the membership record behind them: somebody may be
    listed here whether or not they hold an account, and the listing outlives
    any one person holding the job.
    """

    dart = models.ForeignKey(Dart, on_delete=models.CASCADE, related_name="contacts")
    name = models.CharField(max_length=120)
    title = models.CharField(max_length=80, help_text="The job, e.g. DART leader.")
    phone = models.CharField(max_length=12, blank=True)
    email = models.EmailField(blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "pk"]
        verbose_name = "DART contact"
        verbose_name_plural = "DART contacts"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Save the contact with the phone number in ``XXX-XXX-XXXX`` form."""
        self.phone = normalize_phone(self.phone)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        """The person and the job they do, as a listing prints them."""
        return f"{self.name} ({self.title})"
