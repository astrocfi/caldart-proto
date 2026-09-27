"""Verification of an aircraft's insurance.

An aircraft's insurance is one verified item: the fields in :data:`INSURANCE_FIELDS`,
checked by an authority against the policy.  It is recorded on ``Aircraft`` as
``insurance_verified_at`` and ``insurance_verified_by``, and read through
``insurance_is_verified``, which is true when ``insurance_verified_at`` is set.  A write
that changes the stored value of any insurance field clears the verification, whoever
writes it; a write that changes nothing clears nothing.  Verified insurance whose
expiration passes stays verified: currency and verification are two separate facts.

A holder of any role in ``apps.accounts.roles.VERIFY_ROLES`` may verify it, a system
administrator and a superuser included.  A person's items (pilot certificate, medical,
and photo ID) live in ``apps.members.verification``.
"""

from __future__ import annotations

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
