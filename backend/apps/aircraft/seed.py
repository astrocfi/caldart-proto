"""Seed the aircraft register and attach aircraft to member profiles."""

from __future__ import annotations

import random
from datetime import timedelta
from typing import TYPE_CHECKING, Any

from apps.aircraft.models import Aircraft, OwnerType

if TYPE_CHECKING:
    from io import TextIOBase

AIRCRAFT_COUNT = 25

#: (make, model, typical seats)
AIRFRAMES: tuple[tuple[str, str, int], ...] = (
    ("Cessna", "172S Skyhawk", 4),
    ("Cessna", "182T Skylane", 4),
    ("Cessna", "206H Stationair", 6),
    ("Cessna", "210 Centurion", 6),
    ("Piper", "PA-28-181 Archer", 4),
    ("Piper", "PA-32 Cherokee Six", 6),
    ("Piper", "PA-46 Malibu", 6),
    ("Beechcraft", "A36 Bonanza", 6),
    ("Beechcraft", "B58 Baron", 6),
    ("Mooney", "M20J", 4),
    ("Cirrus", "SR20", 4),
    ("Cirrus", "SR22", 4),
    ("Diamond", "DA40 NG", 4),
    ("Grumman", "AA-5 Tiger", 4),
    ("Maule", "M-7-235", 4),
)

CARRIERS: tuple[str, ...] = (
    "Avemco",
    "Old Republic Aerospace",
    "Global Aerospace",
    "Starr Aviation",
    "USAIG",
    "AIG Aerospace",
)

#: Insurance currency mix so the leader check has all four cases to show.
INSURANCE_MIX: tuple[tuple[str, int], ...] = (
    ("current", 14),
    ("expiring", 4),
    ("expired", 4),
    ("missing", 3),
)


#: The FAA never issues I or O in a registration suffix.
SUFFIX_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"


def _n_number(rng: random.Random) -> str:
    """A plausible, unique-ish US registration."""
    style = rng.random()
    if style < 0.6:
        suffix = rng.choice(SUFFIX_LETTERS) + rng.choice(SUFFIX_LETTERS)
        return f"N{rng.randint(100, 999)}{suffix}"
    if style < 0.85:
        return f"N{rng.randint(1000, 9999)}{rng.choice(SUFFIX_LETTERS)}"
    return f"N{rng.randint(10000, 99999)}"


def run(ctx: dict[str, Any], stdout: TextIOBase | None = None) -> dict[str, Any]:
    """Create the aircraft register and attach airframes to pilot profiles.

    Reads ``rng``, ``faker`` and ``today`` from ``ctx``, and ``profiles`` when present.
    Adds the created ``Aircraft`` list to ``ctx`` under ``aircraft`` and returns
    ``ctx``. Writes a one-line summary to ``stdout`` when given.
    """
    rng = ctx["rng"]
    faker = ctx["faker"]
    today = ctx["today"]
    profiles = ctx.get("profiles", [])

    mix: list[str] = []
    for label, weight in INSURANCE_MIX:
        mix.extend([label] * weight)

    created: list[Aircraft] = []
    seen: set[str] = set()
    attempts = 0
    while len(created) < AIRCRAFT_COUNT and attempts < AIRCRAFT_COUNT * 10:
        attempts += 1
        n_number = _n_number(rng)
        if n_number in seen:
            continue
        seen.add(n_number)

        make, model, seats = rng.choice(AIRFRAMES)
        insurance = mix[len(created) % len(mix)]
        if insurance == "current":
            expiration = today + timedelta(days=rng.randint(45, 700))
        elif insurance == "expiring":
            expiration = today + timedelta(days=rng.randint(1, 30))
        elif insurance == "expired":
            expiration = today - timedelta(days=rng.randint(1, 500))
        else:
            expiration = None

        owner_type = rng.choices(
            [OwnerType.INDIVIDUAL, OwnerType.CLUB, OwnerType.FBO], weights=[70, 20, 10]
        )[0]
        if owner_type == OwnerType.INDIVIDUAL:
            owner_name = faker.name()
        elif owner_type == OwnerType.CLUB:
            owner_name = f"{faker.city()} Flying Club"
        else:
            owner_name = f"{faker.city()} Aviation Services"

        per_occurrence = rng.choice([500_000, 1_000_000, 1_000_000, 2_000_000]) * 100
        per_person = rng.choice([100_000, 100_000, 200_000]) * 100

        aircraft, _ = Aircraft.objects.update_or_create(
            n_number=n_number,
            defaults={
                "make": make,
                "model": model,
                "year": rng.randint(1968, 2024),
                "owner_type": owner_type,
                "owner_name": owner_name,
                "owner_contact": faker.email()
                if rng.random() < 0.6
                else faker.numerify("###-###-####"),
                "seats": seats,
                "insurance_carrier": rng.choice(CARRIERS) if expiration else "",
                "insurance_policy_number": (faker.numerify("AV-########") if expiration else ""),
                "insurance_liability_per_occurrence_cents": per_occurrence if expiration else 0,
                "insurance_liability_per_person_cents": per_person if expiration else 0,
                "insurance_hull_cents": (
                    rng.choice([80_000, 145_000, 260_000, 410_000]) * 100
                    if expiration and rng.random() < 0.8
                    else None
                ),
                "insurance_expiration": expiration,
                "notes": "",
                "is_active": True,
            },
        )
        created.append(aircraft)

    # Attach aircraft to the pilots who fly them.
    pilot_profiles = [p for p in profiles if p.pilot_certificate_type != "none"]
    for profile in pilot_profiles:
        wanted = rng.choices([0, 1, 1, 2, 3], weights=[15, 40, 20, 18, 7])[0]
        if not wanted:
            continue
        chosen = rng.sample(created, k=min(wanted, len(created)))
        profile.aircraft.set(chosen)

    ctx["aircraft"] = created
    if stdout is not None:
        stdout.write(f"  aircraft: {len(created)} airframes, attached to pilots")
    return ctx
