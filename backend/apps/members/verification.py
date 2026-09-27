"""Verification of a member's pilot certificate, medical, and photo ID.

An *item* is the unit that is verified: a group of profile fields an authority checks
against a document.  A person has three items, each listed in :data:`ITEMS` with the
fields it covers.  Ratings, the instrument rating, the flight review date, and total
hours are not verified.

Each item is recorded on ``MemberProfile`` as ``<item>_verified_at`` and
``<item>_verified_by``, and read through ``<item>_is_verified``, which is true when
``<item>_verified_at`` is set.  A write that changes the stored value of any field an
item covers clears that item's verification, whoever writes it; a write that changes
nothing clears nothing.  A verified medical whose expiration passes stays verified:
currency and verification are two separate facts.

A holder of any role in ``apps.accounts.roles.VERIFY_ROLES`` may verify an item, a
system administrator and a superuser included.  An aircraft's insurance is the fourth
kind of item, and lives in ``apps.aircraft.verification``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Item:
    """One verified item of a person: its slug, its label, and the fields it covers.

    ``slug`` names the item's columns (``<slug>_verified_at``, ``<slug>_verified_by``)
    and property (``<slug>_is_verified``) on ``MemberProfile``; ``label`` is the item's
    name as every screen prints it; ``fields`` are the ``MemberProfile`` fields whose
    change clears the item's verification.
    """

    slug: str
    label: str
    fields: tuple[str, ...]


#: A person's verified items, in the order the screens list them.
ITEMS: tuple[Item, ...] = (
    Item("certificate", "Pilot certificate", ("pilot_certificate_type", "certificate_number")),
    Item("medical", "Medical", ("medical_type", "medical_expiration")),
    Item("photo_id", "Photo ID", ("photo_id_type",)),
)

#: Item slug -> the item's label, in the order of :data:`ITEMS`.
ITEM_LABELS: dict[str, str] = {item.slug: item.label for item in ITEMS}
