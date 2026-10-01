"""Seed the aircraft register and attach aircraft to member profiles."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from django.utils import timezone

from apps.accounts.models import User
from apps.aircraft.models import (
    Aircraft,
    AircraftCategory,
    AircraftCoveragePolicy,
    OwnerType,
    Registration,
    RegistrationStatus,
)
from apps.aircraft.registry import FIXTURE_DIR, import_registry

if TYPE_CHECKING:
    from io import TextIOBase

AIRCRAFT_COUNT = 25

#: (make, model): the display names of the aircraft types the seeded aircraft fly,
#: each an entry of the registry fixture.  The n-th aircraft (counting from zero) flies
#: the entry at position n modulo their number, so every one of them is flown.
AIRFRAMES: tuple[tuple[str, str], ...] = (
    ("Cessna", "172S"),
    ("Cessna", "182T"),
    ("Cessna", "206H"),
    ("Cessna", "210"),
    ("Piper", "PA-28-181"),
    ("Piper", "PA-32-300"),
    ("Piper", "PA-46-310P"),
    ("Beechcraft", "A36"),
    ("Beechcraft", "58"),
    ("Mooney", "M20J"),
    ("Cirrus", "SR20"),
    ("Cirrus", "SR22"),
    ("Diamond", "DA 40"),
    ("Grumman American", "AA-5"),
    ("Maule", "M-7-235"),
    ("Aeropro", "Eurofox"),
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


#: Of every ten seeded aircraft, the positions (counting from zero, in seeding order)
#: whose insurance the seeded DART leader has not verified; the other seven are.
UNVERIFIED_POSITIONS = frozenset({2, 5, 8})

#: The statement the seeded coverage policy publishes beside its exclusion of helicopters.
COVERAGE_NOTE = (
    "CalDART's insurance covers airplanes flown on DART missions. Helicopters are not "
    "covered; talk to your DART leader before offering one."
)


def seed_coverage_policy() -> AircraftCoveragePolicy:
    """Write the coverage policy: helicopters excluded, with :data:`COVERAGE_NOTE`."""
    policy = AircraftCoveragePolicy.load()
    policy.excluded_categories = [AircraftCategory.HELICOPTER.value]
    policy.excluded_airworthiness = []
    policy.note = COVERAGE_NOTE
    policy.save()
    return policy


def _seed_registrations() -> list[Registration]:
    """One registration from the fixture for each of the :data:`AIRCRAFT_COUNT` aircraft.

    The n-th is the first valid registration, by N-number, of the n-th aircraft's
    :data:`AIRFRAMES` entry that carries a year and has not been taken already.
    Raises ``LookupError`` naming the entry when the fixture has too few.
    """
    taken: set[str] = set()
    chosen: list[Registration] = []
    for position in range(AIRCRAFT_COUNT):
        make, model = AIRFRAMES[position % len(AIRFRAMES)]
        registration = (
            Registration.objects.filter(
                type__make=make,
                type__model=model,
                status=RegistrationStatus.VALID,
                year__isnull=False,
            )
            .exclude(n_number__in=taken)
            .select_related("type")
            .order_by("n_number")
            .first()
        )
        if registration is None:
            raise LookupError(f"The registry fixture has too few registrations of {make} {model}.")
        taken.add(registration.n_number)
        chosen.append(registration)
    return chosen


def _seed_verification(aircraft: list[Aircraft], leader: User | None) -> None:
    """Verify, as ``leader``, the insurance of every aircraft outside the gaps.

    Positions in :data:`UNVERIFIED_POSITIONS` (of every ten) stay unverified, and so
    does everything when there is no ``leader``.  Both columns are written every time,
    so re-seeding leaves the same state however the previous run ended.
    """
    now = timezone.now()
    for position, record in enumerate(aircraft):
        is_verified = leader is not None and position % 10 not in UNVERIFIED_POSITIONS
        record.insurance_verified_at = now if is_verified else None
        record.insurance_verified_by = leader if is_verified else None
        record.save(update_fields=["insurance_verified_at", "insurance_verified_by", "updated_at"])


def run(ctx: dict[str, Any], stdout: TextIOBase | None = None) -> dict[str, Any]:
    """Import the registry fixture, create the aircraft register, and attach airframes.

    The registry is imported from ``apps/aircraft/fixtures/faa`` through
    :func:`apps.aircraft.registry.import_registry`, and each aircraft takes its
    N-number, type, and year from one of its registrations (see
    :func:`_seed_registrations`), so a registry lookup on a seeded aircraft answers; its
    category and airworthiness are the registration's.  The coverage policy is written
    by :func:`seed_coverage_policy`.
    Reads ``rng``, ``faker``, and ``today`` from ``ctx``, and ``profiles`` when present.
    Adds the created ``Aircraft`` list to ``ctx`` under ``aircraft`` and returns
    ``ctx``. Writes a one-line summary to ``stdout`` when given.  The seeded DART
    leader (``demo_users["leader"]``, when present) verifies the insurance of every
    aircraft outside :data:`UNVERIFIED_POSITIONS`; the rest stay unverified.
    """
    rng = ctx["rng"]
    faker = ctx["faker"]
    today = ctx["today"]
    profiles = ctx.get("profiles", [])

    mix: list[str] = []
    for label, weight in INSURANCE_MIX:
        mix.extend([label] * weight)

    import_registry(str(FIXTURE_DIR))
    created: list[Aircraft] = []
    for registration in _seed_registrations():
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
            n_number=registration.n_number,
            defaults={
                "type": registration.type,
                "year": registration.year,
                "owner_type": owner_type,
                "owner_name": owner_name,
                "owner_contact": faker.email()
                if rng.random() < 0.6
                else faker.numerify("###-###-####"),
                "seats": registration.type.seats,
                "category": registration.type.category,
                "airworthiness": registration.airworthiness,
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

    _seed_verification(created, ctx.get("demo_users", {}).get("leader"))
    seed_coverage_policy()

    # Attach aircraft to the pilots who fly them: at most two each, which is as many
    # registrations as the member report's Aircraft column holds on one line.
    pilot_profiles = [p for p in profiles if p.pilot_certificate_type != "none"]
    for profile in pilot_profiles:
        wanted = rng.choices([0, 1, 2], weights=[15, 60, 25])[0]
        if not wanted:
            continue
        chosen = rng.sample(created, k=min(wanted, len(created)))
        profile.aircraft.set(chosen)

    ctx["aircraft"] = created
    if stdout is not None:
        stdout.write(f"  aircraft: {len(created)} airframes, attached to pilots")
    return ctx
