"""Aircraft and leader-check services (PLAN §6.6).

The leader check is the one flow that has to work on a phone, in a hangar, in
a hurry, so all of its reasoning lives here and both the API and the exports
read the same answers.
"""

from __future__ import annotations

import re
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.aircraft.models import Aircraft, normalize_n_number
from apps.members.services import membership_status

User = get_user_model()

#: The leader search never returns more than this many people (PLAN §6.6).
SEARCH_LIMIT = 20

_PUNCTUATION = re.compile(r"[^A-Za-z0-9]")


def _cleaned(term: str) -> str:
    """The term with punctuation and spaces removed, upper-cased."""
    return _PUNCTUATION.sub("", term).upper()


def looks_like_registration(term: str) -> bool:
    """True when the term could be an N-number rather than a name.

    A registration always carries a digit; requiring one stops a search for
    "Nate" from matching every US-registered aircraft on file.
    """
    return any(character.isdigit() for character in term)


def search_members(query: str, limit: int = SEARCH_LIMIT) -> QuerySet:
    """Members matching ``query`` by name, email, or an aircraft N-number."""
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

    if looks_like_registration(term):
        matches |= Q(profile__aircraft__n_number=normalize_n_number(term))
        matches |= Q(profile__aircraft__n_number__icontains=_cleaned(term))

    return (
        User.objects.filter(matches)
        .select_related("profile", "profile__dart")
        .distinct()
        .order_by("last_name", "first_name", "email")[:limit]
    )


def search_result(user) -> dict:
    """One row of ``GET /leader/search``."""
    profile = getattr(user, "profile", None)
    dart = profile.dart if profile is not None else None
    return {
        "user_id": user.id,
        "name": user.display_name,
        "email": user.email,
        "dart": dart.name if dart is not None else None,
        "membership_status": membership_status(user)["status"],
    }


def leader_status(user) -> dict:
    """The status card for one member (PLAN §6.6).

    ``go_no_go`` is deliberately two plain booleans: a leader is entitled to
    see *why* a member is a no-go, not just that they are.
    """
    profile = getattr(user, "profile", None)
    status = membership_status(user)
    membership_ok = status["status"] == "current"
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


def aircraft_pilots(aircraft: Aircraft) -> list[dict]:
    """The members who list ``aircraft`` among the planes they commonly fly."""
    profiles = aircraft.pilots.select_related("user").order_by(
        "user__last_name", "user__first_name"
    )
    return [
        {
            "user_id": profile.user_id,
            "name": profile.display_name,
            "email": profile.user.email,
            "membership_status": membership_status(profile.user)["status"],
            "medical_is_current": profile.medical_is_current,
        }
        for profile in profiles
    ]


def pilot_names(aircraft: Aircraft) -> list[str]:
    """Display names of the attached members, for the exports (PLAN §11)."""
    return [profile.display_name for profile in aircraft.pilots.all()]


def insurance_queryset(queryset: QuerySet, state: str) -> QuerySet:
    """Narrow ``queryset`` to ``current``, ``expired`` or ``missing`` cover."""
    today = timezone.localdate()
    if state == "current":
        return queryset.filter(insurance_expiration__gte=today)
    if state == "expired":
        return queryset.filter(insurance_expiration__lt=today)
    if state == "missing":
        return queryset.filter(insurance_expiration__isnull=True)
    return queryset


def expiring_within(queryset: QuerySet, days: int) -> QuerySet:
    """Aircraft whose cover runs out in the next ``days`` days (never expired)."""
    today = timezone.localdate()
    horizon = today + timedelta(days=max(days, 0))
    return queryset.filter(insurance_expiration__gte=today, insurance_expiration__lte=horizon)
