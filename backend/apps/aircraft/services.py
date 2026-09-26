"""Aircraft and leader-check services.

The leader check is the one flow that has to work on a phone, in a hangar, in
a hurry, so all of its reasoning lives here and both the API and the exports
read the same answers.
"""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any

from django.contrib.auth import get_user_model
from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.accounts.models import AccountKind
from apps.accounts.models import User as UserModel
from apps.aircraft.models import (
    Aircraft,
    AircraftChange,
    AircraftChangeKind,
    normalize_n_number,
)
from apps.members.models import MembershipState
from apps.members.services import (
    membership_of,
    membership_payload,
    membership_status,
    with_membership,
)
from caldart.phone import normalize_phone

User = get_user_model()

#: The leader search never returns more than this many people.
SEARCH_LIMIT = 20

#: How many digits a search term needs before it is read as a phone number.
#: Seven is a local number; fewer is a certificate or a street number.
PHONE_SEARCH_DIGITS = 7

_PUNCTUATION = re.compile(r"[^A-Za-z0-9]")


# --------------------------------------------------------------------------
# Change history
# --------------------------------------------------------------------------
def changed_fields(aircraft: Aircraft, validated: dict[str, Any]) -> list[str]:
    """The concrete column names in ``validated`` whose value differs from ``aircraft``.

    ``validated`` is a serializer's validated data, so it may also carry a relation
    or a key the table has no column for; such a key is left out.  Compare before
    the save, while ``aircraft`` still holds the stored values: the portal's forms
    resend every field they show, and only the ones that moved are the change.
    """
    columns = {field.name for field in Aircraft._meta.concrete_fields}
    return [
        name
        for name, value in validated.items()
        if name in columns and getattr(aircraft, name) != value
    ]


def record_change(
    aircraft: Aircraft,
    *,
    actor: UserModel | None,
    kind: AircraftChangeKind,
    fields: list[str],
) -> AircraftChange:
    """Log one write to ``aircraft`` and stamp the record with who made it.

    Writes ``updated_by`` (and the automatic ``updated_at``) on the record, then
    returns the stored ``AircraftChange``.  ``actor`` is the signed-in account, or
    ``None`` for a change nobody is signed in for; ``kind`` is ``created`` or
    ``updated``, and ``fields`` names the columns that moved -- empty for a
    creation, where the whole record is the change.
    """
    aircraft.updated_by = actor
    aircraft.save(update_fields=["updated_by", "updated_at"])
    return AircraftChange.objects.create(
        aircraft=aircraft, changed_by=actor, kind=kind, fields=list(fields)
    )


def _cleaned(term: str) -> str:
    """The term with punctuation and spaces removed, upper-cased."""
    return _PUNCTUATION.sub("", term).upper()


def looks_like_registration(term: str) -> bool:
    """True when the term could be an N-number rather than a name.

    A registration always carries a digit; requiring one stops a search for
    "Nate" from matching every US-registered aircraft on file.
    """
    return any(character.isdigit() for character in term)


def checkable_people() -> QuerySet[UserModel]:
    """Every account the leader's member check can find: active members and friends.

    A deactivated account and a donor are never checked, searched for, or listed
    as the pilot of an aircraft.
    """
    return User.objects.filter(is_active=True).exclude(kind=AccountKind.DONOR)


def search_members(query: str, limit: int = SEARCH_LIMIT) -> QuerySet[UserModel]:
    """Members and friends matching ``query`` by name, email, phone number, or N-number.

    Only :func:`checkable_people` are searched.

    A phone number matches on its digits, so ``(415) 555-0100``, ``415-555-0100``
    and ``4155550100`` all find the same person: on an activation a ten-digit
    cell number is the fastest thing a leader has to hand.  Every row carries the
    membership annotations, so :func:`search_result` reads a status without a
    query per person.
    """
    term = (query or "").strip()
    if not term:
        return User.objects.none()

    matches = (
        Q(first_name__icontains=term) | Q(last_name__icontains=term) | Q(email__icontains=term)
    )

    # "Marta Reyes" and "Reyes, Marta" both have to find the same person.
    parts = [part for part in re.split(r"[,\s]+", term) if part]
    if len(parts) >= 2:
        matches |= Q(first_name__icontains=parts[0]) & Q(last_name__icontains=parts[-1])
        matches |= Q(first_name__icontains=parts[-1]) & Q(last_name__icontains=parts[0])

    digits = re.sub(r"\D", "", term)
    if len(digits) >= PHONE_SEARCH_DIGITS:
        stored = normalize_phone(digits)
        matches |= Q(profile__phone=stored) | Q(profile__phone_alt=stored)
        # A partial number: the last four digits are what somebody reads out.
        matches |= Q(profile__phone__endswith=digits[-4:]) & Q(profile__phone__contains=digits[:3])

    if looks_like_registration(term):
        matches |= Q(profile__aircraft__n_number=normalize_n_number(term))
        matches |= Q(profile__aircraft__n_number__icontains=_cleaned(term))

    return with_membership(
        checkable_people()
        .filter(matches)
        .select_related("profile", "profile__dart")
        .distinct()
        .order_by("last_name", "first_name", "email")
    )[:limit]


def search_result(user: UserModel) -> dict[str, Any]:
    """One row of ``GET /leader/search``.

    The row answers go/no-go on its own, by exactly the rule the status card
    uses: ``go_no_go`` is a current membership and a current medical, so a
    leader reads the list and only opens the card for the detail.  Everything
    comes from the row the search already fetched, so a result costs no query of
    its own.
    """
    profile = getattr(user, "profile", None)
    dart = profile.dart if profile is not None else None
    status = membership_of(user)["status"]
    medical_ok = bool(profile is not None and profile.medical_is_current)
    return {
        "user_id": user.id,
        "name": user.display_name,
        "email": user.email,
        "dart": dart.name if dart is not None else None,
        "membership_status": status,
        "go_no_go": {
            "membership": status == MembershipState.CURRENT,
            "medical": medical_ok,
        },
    }


def leader_status(user: UserModel) -> dict[str, Any]:
    """The status card for one member.

    ``go_no_go`` is deliberately two plain booleans: a leader is entitled to
    see *why* a member is a no-go, not just that they are.
    """
    profile = getattr(user, "profile", None)
    status = membership_status(user)
    membership_ok = status["status"] == MembershipState.CURRENT
    medical_ok = bool(profile is not None and profile.medical_is_current)
    dart = profile.dart if profile is not None else None

    return {
        "name": user.display_name,
        "email": user.email,
        "phone": profile.phone if profile is not None else "",
        "dart": dart.name if dart is not None else None,
        "membership": {
            "status": status["status"],
            "expires_on": status["expires_on"],
            "plan": status["plan"],
        },
        "certificate": {
            "type": profile.pilot_certificate_type if profile is not None else "none",
            "number": profile.certificate_number if profile is not None else "",
            "ifr_rated": profile.ifr_rated if profile is not None else "na",
            "ratings": list(profile.ratings or []) if profile is not None else [],
        },
        "medical": {
            "type": profile.medical_type if profile is not None else "none",
            "expiration": profile.medical_expiration if profile is not None else None,
            "is_current": medical_ok,
        },
        "aircraft": list(profile.aircraft.all()) if profile is not None else [],
        "go_no_go": {"membership": membership_ok, "medical": medical_ok},
    }


def aircraft_pilots(aircraft: Aircraft) -> list[dict[str, Any]]:
    """The members and friends who list ``aircraft`` among the planes they commonly fly.

    Only :func:`checkable_people` are listed.  One query whatever the number of
    pilots: the membership annotations ride along with the row.
    """
    pilots = with_membership(
        checkable_people().filter(profile__aircraft=aircraft).select_related("profile")
    ).order_by("last_name", "first_name")
    return [
        {
            "user_id": user.pk,
            "name": user.display_name,
            "email": user.email,
            "membership_status": membership_payload(user)["status"],
            "medical_is_current": user.profile.medical_is_current,
        }
        for user in pilots
    ]


def pilot_names(aircraft: Aircraft) -> list[str]:
    """Display names of the attached members, for the exports."""
    return [profile.display_name for profile in aircraft.pilots.all()]


def insurance_queryset(queryset: QuerySet[Aircraft], state: str) -> QuerySet[Aircraft]:
    """Narrow ``queryset`` to ``current``, ``expired``, or ``missing`` cover."""
    today = timezone.localdate()
    if state == "current":
        return queryset.filter(insurance_expiration__gte=today)
    if state == "expired":
        return queryset.filter(insurance_expiration__lt=today)
    if state == "missing":
        return queryset.filter(insurance_expiration__isnull=True)
    return queryset


#: Longest "expiring within" window we will answer.  Ten years is far beyond
#: any useful query, and clamping keeps ``today + timedelta(days=n)`` from
#: raising ``OverflowError`` -- a 500 -- on an absurd query string.
MAX_EXPIRING_WINDOW_DAYS = 3650


def expiring_within(queryset: QuerySet[Aircraft], days: int) -> QuerySet[Aircraft]:
    """Aircraft whose cover runs out in the next ``days`` days (never expired)."""
    today = timezone.localdate()
    window = min(max(days, 0), MAX_EXPIRING_WINDOW_DAYS)
    horizon = today + timedelta(days=window)
    return queryset.filter(insurance_expiration__gte=today, insurance_expiration__lte=horizon)
