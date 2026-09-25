"""Seed DARTs, membership plans and member profiles.

Also decides each seeded user's *membership target* -- the status their history
should end up in -- which ``apps.payments.seed`` turns into real payments and
terms through ``members.services.activate_term``.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from typing import Any, TypedDict

from django.core.management.base import OutputWrapper
from django.utils.text import slugify
from faker import Faker

from apps.darts.models import Dart, DartContact
from apps.members.models import (
    RATING_VALUES,
    IfrRated,
    MedicalType,
    MemberProfile,
    MembershipPlan,
    PilotCertificateType,
)

#: The DARTs to seed.
#: Every DART, with the airports it flies from.
#: A team may cover several fields: Contra Costa has two, and San Diego nine.
DARTS: tuple[tuple[str, str], ...] = (
    ("Angwin", "2O3"),
    ("Central Coast", "SBP"),
    ("Contra Costa", "CCR, C83"),
    ("Half Moon Bay", "HAF"),
    ("Hayward", "HWD"),
    ("Livermore", "LVK"),
    ("Monterey", "MRY"),
    ("Napa", "APC"),
    ("Palo Alto", "PAO"),
    ("Reid-Hillview", "RHV"),
    ("San Carlos", "SQL"),
    ("San Diego", "KCRQ, KMYF, KOKB, KRNM, KSEE, KSDM, F70, L08, L18"),
    ("San Martin (South County)", "E16"),
    ("Santa Monica", "SMO"),
    ("Santa Rosa", "STS"),
    ("Watsonville", "WVI"),
)


class PlanSpec(TypedDict):
    """One membership plan the seed creates, keyed on its slug."""

    name: str
    slug: str
    price_cents: int
    duration_days: int | None
    sort_order: int
    description: str


#: The membership plans to seed.
PLANS: tuple[PlanSpec, ...] = (
    {
        "name": "Annual",
        "slug": "annual",
        "price_cents": 4_500,
        "duration_days": 365,
        "sort_order": 1,
        "description": "One year of CalDART membership, renewable each year.",
    },
    {
        "name": "Life",
        "slug": "life",
        "price_cents": 65_000,
        "duration_days": None,
        "sort_order": 2,
        "description": "A lifetime membership. Pay once, never renew.",
    },
)

CA_COUNTIES: tuple[str, ...] = (
    "Alameda",
    "Contra Costa",
    "Los Angeles",
    "Marin",
    "Monterey",
    "Napa",
    "Orange",
    "Sacramento",
    "San Benito",
    "San Luis Obispo",
    "San Mateo",
    "Santa Barbara",
    "Santa Clara",
    "Santa Cruz",
    "Solano",
    "Sonoma",
)

HOW_HEARD: tuple[str, ...] = (
    "EAA chapter meeting",
    "Word of mouth",
    "AOPA article",
    "Airport bulletin board",
    "CalDART booth at an airshow",
    "Web search",
    "Flying club newsletter",
)

#: Membership targets and their weights, so the demo shows mixed statuses.
MEMBERSHIP_TARGETS: tuple[tuple[str, int], ...] = (
    ("current", 18),
    ("expiring", 7),
    ("expired", 8),
    ("lifetime", 4),
    ("none", 4),
)


#: The seed behind the generated contact names, so the example teams read the
#: same on every installation.
DART_SEED = 20260101

#: The people an example DART lists, as ``(title, whether they have a phone)``.
#: Names and addresses are generated, so no real volunteer is named here.
DART_CONTACT_ROLES: tuple[tuple[str, bool], ...] = (
    ("DART leader", True),
    ("Deputy leader", True),
    ("Ground team lead", False),
    ("Communications", False),
)

#: The domain the example contact addresses are built in.
DART_CONTACT_DOMAIN = "caldart.example.org"


def seed_darts(seed: int = DART_SEED) -> list[Dart]:
    """Create or update every DART in :data:`DARTS`, and return them in that order.

    Each is keyed on its name, so running the seed twice leaves one row per
    DART with the airports and website the table gives it, and with the
    same handful of example contacts on it.  ``seed`` fixes the
    generated contact names, so two runs produce the same people.
    """
    faker = Faker("en_US")
    faker.seed_instance(seed)
    rng = random.Random(seed)  # noqa: S311 - demo data, not security-sensitive

    darts = []
    for name, identifiers in DARTS:
        slug = slugify(name)
        dart, _ = Dart.objects.update_or_create(
            name=name,
            defaults={
                "airport_identifiers": identifiers,
                "website_url": f"https://{slug}.{DART_CONTACT_DOMAIN}/",
                "is_active": True,
            },
        )
        seed_dart_contacts(dart, faker, rng)
        darts.append(dart)
    return darts


def seed_dart_contacts(dart: Dart, faker: Faker, rng: random.Random) -> None:
    """Give ``dart`` its example contacts, replacing any it already has.

    Every team gets a leader and a deputy; the other roles are drawn, so the
    list looks like a real one rather than four identical teams.
    """
    dart.contacts.all().delete()
    wanted = DART_CONTACT_ROLES[: rng.randint(2, len(DART_CONTACT_ROLES))]
    for position, (title, has_phone) in enumerate(wanted):
        person = faker.name()
        mailbox = person.lower().replace(" ", ".").replace("'", "")
        DartContact.objects.create(
            dart=dart,
            name=person,
            title=title,
            phone=faker.numerify("###-###-####") if has_phone else "",
            email=f"{mailbox}@{DART_CONTACT_DOMAIN}",
            sort_order=position,
        )


def seed_plans() -> list[MembershipPlan]:
    """Create or update every plan in :data:`PLANS`, and return them in that order.

    Each is keyed on its slug, so running the seed twice leaves one row per
    plan with the price, duration, and description the table gives it.
    """
    plans = []
    for spec in PLANS:
        plan, _ = MembershipPlan.objects.update_or_create(
            slug=spec["slug"],
            defaults={
                "name": spec["name"],
                "price_cents": spec["price_cents"],
                "duration_days": spec["duration_days"],
                "sort_order": spec["sort_order"],
                "description": spec["description"],
                "is_active": True,
            },
        )
        plans.append(plan)
    return plans


def _profile_defaults(
    rng: random.Random,
    faker: Faker,
    towns: Faker,
    darts: list[Dart],
    today: date,
    certificate: str | None = None,
) -> dict[str, Any]:
    """One plausible profile, drawn from ``rng``, ``faker`` and ``towns``.

    The answers hang together: only a pilot carries a medical, a certificate
    number, ratings, hours, and a flight review, and roughly a quarter of pilots
    are given a medical that expired before ``today`` so the leader checks have
    something to fail on.  The DART is drawn from ``darts`` and supplies the
    member's home airport, while ``towns`` supplies the two town names.
    ``certificate`` forces the pilot
    certificate, which the caller uses to make sure every kind appears at least
    once however the draw falls.
    """
    certificate = (
        certificate
        or rng.choices(
            [
                PilotCertificateType.NONE,
                PilotCertificateType.STUDENT,
                PilotCertificateType.SPORT,
                PilotCertificateType.RECREATIONAL,
                PilotCertificateType.PRIVATE,
                PilotCertificateType.COMMERCIAL,
                PilotCertificateType.ATP,
            ],
            weights=[12, 6, 3, 2, 45, 22, 10],
        )[0]
    )
    is_pilot = certificate != PilotCertificateType.NONE

    if not is_pilot:
        medical_type = MedicalType.NONE
        medical_expiration = None
    else:
        medical_type = rng.choices(
            [MedicalType.BASICMED, MedicalType.THIRD, MedicalType.SECOND, MedicalType.FIRST],
            weights=[35, 40, 15, 10],
        )[0]
        # A quarter of pilots carry a lapsed medical, so the leader check has
        # something to fail on.
        if rng.random() < 0.25:
            medical_expiration = today - timedelta(days=rng.randint(1, 900))
        else:
            medical_expiration = today + timedelta(days=rng.randint(10, 1_400))

    ratings: list[str] = []
    if is_pilot:
        pool = list(RATING_VALUES)
        ratings = rng.sample(pool, k=rng.choices([0, 1, 2, 3], weights=[35, 35, 20, 10])[0])

    dart = rng.choice(darts)
    return {
        "phone": faker.numerify("###-###-####"),
        "phone_alt": faker.numerify("###-###-####") if rng.random() < 0.3 else "",
        "address_line1": faker.street_address(),
        "address_line2": "",
        "city": towns.city(),
        "state": "CA",
        "postal_code": faker.numerify("9####"),
        "county": rng.choice(CA_COUNTIES),
        "emergency_contact_name": faker.name(),
        "emergency_contact_phone": faker.numerify("###-###-####"),
        "home_airport_identifier": dart.home_airport or rng.choice(["SQL", "PAO", "LVK"]),
        "home_airport_city": towns.city(),
        "dart": dart,
        "air_care_alliance_number": (faker.numerify("ACA-#####") if rng.random() < 0.35 else ""),
        "pilot_certificate_type": certificate,
        "certificate_number": faker.numerify("#######") if is_pilot else "",
        "ifr_rated": (
            rng.choices([IfrRated.YES, IfrRated.NO], weights=[45, 55])[0]
            if is_pilot
            else IfrRated.NA
        ),
        "ratings": ratings,
        "medical_type": medical_type,
        "medical_expiration": medical_expiration,
        "flight_review_date": (today - timedelta(days=rng.randint(10, 800)) if is_pilot else None),
        "total_hours": rng.randint(60, 6_000) if is_pilot else None,
        "flies_rented_aircraft": is_pilot and rng.random() < 0.2,
        "vol_mission_pilot": is_pilot and rng.random() < 0.5,
        "vol_ground_team": rng.random() < 0.45,
        "vol_exercise_training": rng.random() < 0.5,
        "vol_member_support": rng.random() < 0.3,
        "vol_fundraising": rng.random() < 0.2,
        "vol_social_media": rng.random() < 0.18,
        "vol_newsletter": rng.random() < 0.25,
        "how_heard": rng.choice(HOW_HEARD),
    }


def _assign_targets(rng: random.Random, ctx: dict[str, Any]) -> dict[int, str]:
    """Give every seeded user a membership outcome for the payments seed.

    The demo accounts get fixed outcomes, so the walkthrough always shows the
    same thing, and the generated accounts are dealt from :data:`MEMBERSHIP_TARGETS`
    in the weights it gives.  The answer is keyed by user id.
    """
    targets: dict[int, str] = {}

    demo = ctx["demo_users"]
    targets[demo["member"].pk] = "current"
    targets[demo["expired"].pk] = "expired"
    targets[demo["leader"].pk] = "current"
    targets[demo["useradmin"].pk] = "current"
    targets[demo["accountadmin"].pk] = "lifetime"
    targets[demo["webadmin"].pk] = "current"
    targets[demo["sysadmin"].pk] = "lifetime"

    pool: list[str] = []
    for name, weight in MEMBERSHIP_TARGETS:
        pool.extend([name] * weight)
    rng.shuffle(pool)

    for index, user in enumerate(ctx["generated_users"]):
        targets[user.pk] = pool[index % len(pool)]
    return targets


def run(ctx: dict[str, Any], stdout: OutputWrapper | None = None) -> dict[str, Any]:
    """Seed the DARTs, the plans and one profile per user, and return ``ctx``.

    Reads ``rng``, ``faker``, ``today``, and ``users`` from ``ctx`` and adds
    ``darts``, ``plans`` (keyed by slug), ``profiles`` and ``membership_targets``
    for the seeds that run after this one.  A user who already has a profile has
    it overwritten, so re-seeding leaves one profile per account.  ``stdout``, when
    given, gets a one-line count.
    """
    rng = ctx["rng"]
    faker = ctx["faker"]
    today = ctx["today"]
    # The towns are drawn from an instance of their own: the shared ``faker``
    # runs through every seed module in turn, so taking town names out of it
    # would move the names, numbers and payments that follow it.
    towns = Faker("en_US")
    towns.seed_instance(DART_SEED)

    darts = seed_darts()
    plans = seed_plans()
    ctx["darts"] = darts
    ctx["plans"] = {plan.slug: plan for plan in plans}

    profiles: list[MemberProfile] = []
    # One generated member is dealt each certificate type, so the demo data
    # covers every kind whatever the random draw does with the rest.  The named
    # demo accounts are left to the draw: the walkthrough and the end-to-end
    # suite read them by name, and their certificates are part of that story.
    forced = dict(
        zip(
            [user.pk for user in ctx["generated_users"]],
            PilotCertificateType.values,
            strict=False,
        )
    )
    for user in ctx["users"]:
        defaults = _profile_defaults(rng, faker, towns, darts, today, forced.get(user.pk))
        profile, created = MemberProfile.objects.get_or_create(user=user, defaults=defaults)
        if not created:
            for field, value in defaults.items():
                setattr(profile, field, value)
            profile.save()
        profiles.append(profile)

    ctx["profiles"] = profiles
    ctx["membership_targets"] = _assign_targets(rng, ctx)

    if stdout is not None:
        stdout.write(f"  members: {len(darts)} DARTs, {len(plans)} plans, {len(profiles)} profiles")
    return ctx


__all__ = ["DARTS", "PLANS", "run", "seed_darts", "seed_plans"]
