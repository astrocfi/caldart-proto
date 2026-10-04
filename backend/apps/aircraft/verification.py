"""Verification of an aircraft's insurance.

An aircraft's insurance is one verified item: the fields in :data:`INSURANCE_FIELDS`,
checked by an authority against the policy.  It is recorded on ``Aircraft`` as
``insurance_verified_at`` and ``insurance_verified_by``, and read through
``insurance_is_verified``, which is true when ``insurance_verified_at`` is set.  A write
that changes the stored value of any insurance field clears the verification, whoever
writes it; a write that changes nothing clears nothing.  Verified insurance whose
expiration passes stays verified: currency and verification are two separate facts.
Insurance with no expiration on file is no policy at all, and is never stamped.

A holder of any role in ``apps.accounts.roles.VERIFY_ROLES`` may verify it, a system
administrator and a superuser included.  A person's items (pilot certificate, medical,
and photo ID) live in ``apps.members.verification``.
"""

from __future__ import annotations

from collections.abc import Mapping

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.aircraft.models import Aircraft
from caldart import audit, events

#: The item's label as every screen prints it.
INSURANCE_LABEL = "Insurance"

#: The ``Aircraft`` fields whose change clears the insurance verification.
INSURANCE_FIELDS: tuple[str, ...] = (
    "insurance_carrier",
    "insurance_policy_number",
    "insurance_liability_per_occurrence_cents",
    "insurance_liability_per_person_cents",
    "insurance_hull_cents",
    "insurance_expiration",
)


def clear_stale_insurance(aircraft: Aircraft, moved_fields: list[str]) -> bool:
    """Clear ``aircraft``'s insurance verification when ``moved_fields`` touches it.

    ``moved_fields`` names the columns a write has just changed
    (:func:`apps.aircraft.services.changed_fields`).  When any of them is in
    :data:`INSURANCE_FIELDS` and the insurance is verified, both verification columns
    are set to ``None`` and saved, and the answer is True.  Otherwise nothing is
    written and the answer is False: a write that moved no insurance field, or one to
    insurance that was not verified, clears nothing.
    """
    if not any(name in INSURANCE_FIELDS for name in moved_fields):
        return False
    if aircraft.insurance_verified_at is None:
        return False
    aircraft.insurance_verified_at = None
    aircraft.insurance_verified_by = None
    aircraft.save(update_fields=["insurance_verified_at", "insurance_verified_by", "updated_at"])
    return True


@transaction.atomic
def verify_insurance(
    aircraft: Aircraft,
    *,
    actor: User,
    changes: Mapping[str, object],
    verified: bool,
) -> Aircraft:
    """Write ``changes`` to ``aircraft``'s insurance and leave it verified or not.

    ``changes`` maps some of :data:`INSURANCE_FIELDS` to the values to write.  The
    record is saved and :func:`apps.aircraft.services.record_updated` records the
    write under ``actor`` -- the history row, the ``aircraft.update`` audit record, the
    ``aircraft_changed`` event when a column moved, and the clearing of a verification
    the change made stale.

    Then, when ``verified`` is true and the insurance is not verified, it is stamped
    with ``timezone.now()`` and ``actor``; verified insurance keeps its stamp.  When
    ``verified`` is false, or the saved record has no ``insurance_expiration`` (no
    policy on file, so nothing to verify), the insurance ends unverified.  The audit
    log records ``aircraft.verify`` with ``verified`` (whether the insurance ends
    verified), and when the verified state before the save differs from the state
    after it, or the insurance was stamped anew, ``verification_changed`` is raised
    once with ``aircraft``, ``verified`` and ``cleared`` as item labels, and
    ``actor``.  Returns the saved aircraft.

    Locks the aircraft row with ``select_for_update`` before reading it, so a save
    racing this one -- the owner's own edit, or another verifier's -- waits for this
    transaction to finish rather than acting on a value this call is about to move.
    """
    # Imported here, not at module level: `apps.aircraft.services` imports this module
    # for `clear_stale_insurance`, so a top-level import back would be circular.
    from apps.aircraft import services

    aircraft = Aircraft.objects.select_for_update().get(pk=aircraft.pk)
    was_verified = aircraft.insurance_is_verified
    moved = services.changed_fields(aircraft, dict(changes))
    for name, value in changes.items():
        setattr(aircraft, name, value)
    aircraft.save()
    services.record_updated(aircraft, actor=actor, fields=moved)

    stamped = False
    verified = verified and aircraft.insurance_expiration is not None
    if verified and not aircraft.insurance_is_verified:
        aircraft.insurance_verified_at = timezone.now()
        aircraft.insurance_verified_by = actor
        stamped = True
    elif not verified:
        aircraft.insurance_verified_at = None
        aircraft.insurance_verified_by = None
    aircraft.save(update_fields=["insurance_verified_at", "insurance_verified_by", "updated_at"])

    cleared = was_verified and not verified
    audit.record(audit.AIRCRAFT_VERIFY, actor=actor, target=aircraft, verified=verified)
    if stamped or cleared:
        events.emit(
            "verification_changed",
            aircraft=aircraft,
            verified=[INSURANCE_LABEL] if stamped else [],
            cleared=[INSURANCE_LABEL] if cleared else [],
            actor=actor,
        )
    return aircraft
