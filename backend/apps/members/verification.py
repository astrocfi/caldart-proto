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

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import TypedDict

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.members import services
from apps.members.models import MedicalType, MemberProfile, PilotCertificateType
from caldart import audit, events

#: What the member check and the profile form answer for a medical with no expiration.
MEDICAL_EXPIRATION_MESSAGE = "Give the expiration date of your medical certificate."

#: What they answer for a pilot certificate with no number.
CERTIFICATE_NUMBER_MESSAGE = "Give your pilot certificate number."


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

#: ``(slug, label)`` for each item, as a choice list for the API schema.
ITEM_CHOICES: list[tuple[str, str]] = [(item.slug, item.label) for item in ITEMS]


class VerificationState(TypedDict):
    """One item's verified state as the API reports it.

    ``verified`` is whether the item is verified; ``verified_by`` the display name of
    the account that verified it (``None`` while unverified, or once that account is
    deleted); ``verified_at`` when it was verified (``None`` while unverified).
    """

    verified: bool
    verified_by: str | None
    verified_at: datetime | None


def verification_state(verified_at: datetime | None, verified_by: User | None) -> VerificationState:
    """The API's view of one item recorded as ``verified_at`` and ``verified_by``.

    The item is verified when ``verified_at`` is set, whoever is recorded as having
    verified it; ``verified_by`` reads as the account's display name.
    """
    return {
        "verified": verified_at is not None,
        "verified_by": verified_by.display_name if verified_by is not None else None,
        "verified_at": verified_at,
    }


def item_state(profile: MemberProfile, slug: str) -> VerificationState:
    """:func:`verification_state` for the item ``slug`` of ``profile``."""
    return verification_state(
        getattr(profile, f"{slug}_verified_at"), getattr(profile, f"{slug}_verified_by")
    )


def verified_items(profile: MemberProfile) -> list[str]:
    """The slugs of ``profile``'s verified items, in the order of :data:`ITEMS`."""
    return [item.slug for item in ITEMS if getattr(profile, f"{item.slug}_verified_at") is not None]


def is_fully_verified(profile: MemberProfile | None) -> bool:
    """True when ``profile`` exists and every one of its items is verified.

    Reads only the ``*_verified_at`` columns, so a row the caller already fetched
    answers without another query.  An account with no profile has nothing verified.
    """
    if profile is None:
        return False
    return len(verified_items(profile)) == len(ITEMS)


def document_errors(
    *,
    certificate_type: str | None,
    certificate_number: str,
    medical_type: str | None,
    medical_expiration: date | None,
) -> dict[str, str]:
    """The field errors the two document rules find in a profile's merged values.

    A medical class other than ``none`` needs an expiration date, refused against
    ``medical_expiration`` with :data:`MEDICAL_EXPIRATION_MESSAGE`; a pilot
    certificate other than ``none`` needs a number (blank after stripping is none),
    refused against ``certificate_number`` with :data:`CERTIFICATE_NUMBER_MESSAGE`.
    The values are the ones the write would leave in place, and an empty answer
    means both rules hold.  A missing type (``None`` or blank) needs nothing.
    """
    errors: dict[str, str] = {}
    if medical_type and medical_type != MedicalType.NONE and medical_expiration is None:
        errors["medical_expiration"] = MEDICAL_EXPIRATION_MESSAGE
    is_certified = certificate_type and certificate_type != PilotCertificateType.NONE
    if is_certified and len(certificate_number.strip()) == 0:
        errors["certificate_number"] = CERTIFICATE_NUMBER_MESSAGE
    return errors


def clear_stale(profile: MemberProfile, changes: Mapping[str, object]) -> list[str]:
    """Clear every verified item of ``profile`` whose covered fields ``changes`` moves.

    ``changes`` maps profile field names to the values about to be written; call this
    before they are assigned, while ``profile`` still holds the stored values.  An item
    is cleared -- both ``<slug>_verified_at`` and ``<slug>_verified_by`` set to
    ``None`` on ``profile``, not yet saved -- when any field it covers carries a value
    different from the stored one.  A field resent at its stored value, or one no item
    covers, clears nothing.  Returns the slugs of the items that were verified and are
    cleared, in the order of :data:`ITEMS`; an item that was not verified is not
    reported.
    """
    cleared: list[str] = []
    for item in ITEMS:
        moved = any(
            name in changes and changes[name] != getattr(profile, name) for name in item.fields
        )
        if not moved:
            continue
        if getattr(profile, f"{item.slug}_verified_at") is not None:
            cleared.append(item.slug)
        setattr(profile, f"{item.slug}_verified_at", None)
        setattr(profile, f"{item.slug}_verified_by", None)
    return cleared


@transaction.atomic
def verify_member(
    actor: User,
    target: User,
    *,
    changes: Mapping[str, object],
    verified: list[str],
) -> MemberProfile:
    """Write ``changes`` to ``target``'s profile and leave exactly ``verified`` verified.

    ``changes`` maps some of the fields the items cover to the values to write; when it
    is not empty it goes through :func:`apps.members.services.update_member` under
    ``actor``, which clears the items whose fields moved and raises
    ``profile_changed``.  An empty ``changes`` writes no field and leaves
    ``profile_updated_at`` alone.  The profile is created if the account has none.

    Then each slug in ``verified`` names an item that ends verified: one not yet
    verified is stamped with ``timezone.now()`` and ``actor``, and one already verified
    keeps its stamp.  Every item not named ends unverified.  Slugs must come from
    :data:`ITEMS`; the caller validates them.

    The audit log records ``member.verify`` with ``verified`` (the items stamped by
    this save) and ``cleared`` (the items verified before the save and not after), by
    slug.  When either list is not empty, ``verification_changed`` is raised once with
    ``user``, ``verified`` and ``cleared`` as item labels, and ``actor``; a save that
    changes no item's state raises nothing.  Returns the saved profile.
    """
    profile, _ = MemberProfile.objects.get_or_create(user=target)
    before = verified_items(profile)
    if len(changes) > 0:
        services.update_member(actor, target, profile=dict(changes))
        profile.refresh_from_db()

    now = timezone.now()
    stamped: list[str] = []
    for item in ITEMS:
        is_verified = getattr(profile, f"{item.slug}_verified_at") is not None
        if item.slug in verified and not is_verified:
            setattr(profile, f"{item.slug}_verified_at", now)
            setattr(profile, f"{item.slug}_verified_by", actor)
            stamped.append(item.slug)
        elif item.slug not in verified:
            setattr(profile, f"{item.slug}_verified_at", None)
            setattr(profile, f"{item.slug}_verified_by", None)
    profile.save(update_fields=[*_verification_columns(), "updated_at"])

    cleared = [slug for slug in before if slug not in verified]
    audit.record(audit.MEMBER_VERIFY, actor=actor, target=target, verified=stamped, cleared=cleared)
    if len(stamped) > 0 or len(cleared) > 0:
        events.emit(
            "verification_changed",
            user=target,
            verified=[ITEM_LABELS[slug] for slug in stamped],
            cleared=[ITEM_LABELS[slug] for slug in cleared],
            actor=actor,
        )
    return profile


def _verification_columns() -> list[str]:
    """Every verification column of ``MemberProfile``, two per item."""
    return [f"{item.slug}_verified_{part}" for item in ITEMS for part in ("at", "by")]
