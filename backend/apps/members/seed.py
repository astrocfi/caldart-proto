"""Seed DARTs, membership plans and member profiles.

Also decides each seeded user's *membership target* — the status their history
should end up in — which ``apps.payments.seed`` turns into real payments and
terms through ``members.services.activate_term``.
"""

from __future__ import annotations

from datetime import timedelta

from apps.members.models import (
    RATING_VALUES,
    Dart,
    IfrRated,
    MedicalType,
    MemberProfile,
    MembershipPlan,
    PilotCertificateType,
)

#: The DARTs to seed.
DARTS: tuple[tuple[str, str, str], ...] = (
    ("Angwin", "2O3", "Angwin"),
    ("Central Coast", "SBP", "San Luis Obispo"),
    ("Contra Costa", "CCR", "Concord"),
    ("Half Moon Bay", "HAF", "Half Moon Bay"),
    ("Hayward", "HWD", "Hayward"),
    ("Livermore", "LVK", "Livermore"),
    ("Monterey", "MRY", "Monterey"),
    ("Napa", "APC", "Napa"),
    ("Palo Alto", "PAO", "Palo Alto"),
    ("Reid-Hillview", "RHV", "San Jose"),
    ("San Carlos", "SQL", "San Carlos"),
    ("San Martin (South County)", "E16", "San Martin"),
    ("Santa Monica", "SMO", "Santa Monica"),
    ("Santa Rosa", "STS", "Santa Rosa"),
    ("Watsonville", "WVI", "Watsonville"),
    ("Unaffiliated", "", ""),
)

#: The membership plans to seed.
PLANS: tuple[dict, ...] = (
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


def seed_darts() -> list[Dart]:
    darts = []
    for order, (name, identifier, city) in enumerate(DARTS, start=1):
        dart, _ = Dart.objects.update_or_create(
            name=name,
            defaults={
                "airport_identifier": identifier,
                "city": city,
                "is_active": True,
                "sort_order": order,
            },
        )
        darts.append(dart)
    return darts


def seed_plans() -> list[MembershipPlan]:
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


def _profile_defaults(rng, faker, darts, today) -> dict:
    certificate = rng.choices(
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
        "city": dart.city or faker.city(),
        "state": "CA",
        "postal_code": faker.numerify("9####"),
        "county": rng.choice(CA_COUNTIES),
        "emergency_contact_name": faker.name(),
        "emergency_contact_phone": faker.numerify("###-###-####"),
        "home_airport_identifier": dart.airport_identifier or rng.choice(["SQL", "PAO", "LVK"]),
        "home_airport_city": dart.city or faker.city(),
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
        "vol_ground_team": rng.random() < 0.45,
        "vol_exercise_training": rng.random() < 0.5,
        "vol_member_support": rng.random() < 0.3,
        "vol_fundraising": rng.random() < 0.2,
        "vol_social_media": rng.random() < 0.18,
        "vol_newsletter": rng.random() < 0.25,
        "how_heard": rng.choice(HOW_HEARD),
    }


def _assign_targets(rng, ctx) -> dict[int, str]:
    """Give every seeded user a membership outcome for the payments seed."""
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


def run(ctx: dict, stdout=None) -> dict:
    rng = ctx["rng"]
    faker = ctx["faker"]
    today = ctx["today"]

    darts = seed_darts()
    plans = seed_plans()
    ctx["darts"] = darts
    ctx["plans"] = {plan.slug: plan for plan in plans}

    profiles: list[MemberProfile] = []
    for user in ctx["users"]:
        defaults = _profile_defaults(rng, faker, darts, today)
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


__all__ = ["run", "seed_darts", "seed_plans", "DARTS", "PLANS"]
