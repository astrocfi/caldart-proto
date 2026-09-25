"""The seed commands must be safe to run repeatedly."""

from __future__ import annotations

from collections import Counter
from datetime import timedelta
from io import StringIO
from unittest.mock import MagicMock

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.utils import timezone
from faker import Faker
from wagtail.models import Site

from apps.accounts.roles import ROLE_SLUGS, SYSTEM_ADMIN
from apps.accounts.seed import DEMO_ACCOUNTS, DEMO_PASSWORD, GENERATED_MEMBER_COUNT
from apps.aircraft.models import Aircraft
from apps.cms.models import SiteSettings
from apps.darts.models import Dart
from apps.members.models import MemberProfile, Membership, MembershipPlan, MembershipState
from apps.members.seed import DART_SEED
from apps.members.services import membership_status
from apps.payments.models import Payment, PaymentStatus
from apps.payments.seed import HISTORY_MONTHS, MANUAL_PAYMENT_COUNT

User = get_user_model()

#: The payments ``seed_demo`` creates from its fixed random seed: one per term,
#: plus the ones recorded by hand, all succeeded.
SEEDED_PAYMENTS = 73 + MANUAL_PAYMENT_COUNT

#: How many of them the seed refunds: two in full and four contributions, which
#: leaves the first two ``refunded`` and the other four ``partially_refunded``.
SEEDED_FULL_REFUNDS = 2
SEEDED_PARTIAL_REFUNDS = 4

#: Every test here runs `seed_demo`, which seeds the whole demo data set.
pytestmark = [pytest.mark.django_db, pytest.mark.slow]


def _seed() -> None:
    """Run the ``seed_demo`` management command, discarding its stdout."""
    call_command("seed_demo", stdout=StringIO())


def test_seed_demo_does_not_reseed_the_shared_faker_generator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``seed_demo`` never calls ``Faker.seed``, the classmethod every instance shares.

    Calling it would make every later test's factory-generated data depend on
    whether ``seed_demo`` ran first in this session.
    """
    guard = MagicMock()
    monkeypatch.setattr(Faker, "seed", guard)
    _seed()
    guard.assert_not_called()


def test_every_seeded_town_comes_from_the_town_generator() -> None:
    """A seeded profile's two towns are draws from the seed's own town generator.

    The generator the rest of the demo data is drawn from runs on through the
    aircraft and payment seeds, so a town taken from it would move every name,
    number and payment drawn after it.  Two towns per profile are drawn, in the
    order the profiles are created, so the towns on the seeded profiles are
    exactly the first two per profile that a generator on the same seed gives.
    """
    _seed()
    profiles = list(MemberProfile.objects.all())
    towns = Faker("en_US")
    towns.seed_instance(DART_SEED)
    expected = Counter(towns.city() for _ in range(2 * len(profiles)))
    found = Counter([profile.city for profile in profiles])
    found.update(profile.home_airport_city for profile in profiles)
    assert found == expected


def test_seed_roles_command() -> None:
    """``seed_roles`` creates exactly one group per role slug."""
    call_command("seed_roles", stdout=StringIO())

    assert Group.objects.filter(name__in=ROLE_SLUGS).count() == len(ROLE_SLUGS)


def test_seed_demo_creates_the_documented_accounts() -> None:
    """Every ``DEMO_ACCOUNTS`` entry exists with its documented roles and password."""
    _seed()
    for _key, email, _first, _last, roles, is_superuser in DEMO_ACCOUNTS:
        user = User.objects.get(email=email)
        assert user.check_password(DEMO_PASSWORD) is True
        assert set(user.roles) == set(roles)
        assert user.is_superuser is is_superuser


def test_sysadmin_is_a_superuser() -> None:
    """The seeded ``sysadmin@example.org`` account is a Django superuser and staff."""
    _seed()
    user = User.objects.get(email="sysadmin@example.org")
    assert user.is_superuser is True
    assert user.is_staff is True
    assert user.has_role(SYSTEM_ADMIN) is True


def test_seed_demo_shapes() -> None:
    """The seed produces the documented counts of DARTs, plans, users and aircraft."""
    _seed()
    assert Dart.objects.count() == 16
    assert MembershipPlan.objects.count() == 2
    assert MembershipPlan.objects.get(slug="annual").price_cents == 4_500
    assert MembershipPlan.objects.get(slug="life").duration_days is None
    assert User.objects.count() == len(DEMO_ACCOUNTS) + GENERATED_MEMBER_COUNT
    assert MemberProfile.objects.count() == User.objects.count()
    assert Aircraft.objects.count() == 25
    still_whole = SEEDED_PAYMENTS - SEEDED_FULL_REFUNDS - SEEDED_PARTIAL_REFUNDS
    assert Payment.objects.filter(status=PaymentStatus.SUCCEEDED).count() == still_whole
    assert Payment.objects.filter(status=PaymentStatus.REFUNDED).count() == SEEDED_FULL_REFUNDS
    partially = Payment.objects.filter(status=PaymentStatus.PARTIALLY_REFUNDED).count()
    assert partially == SEEDED_PARTIAL_REFUNDS


def test_seed_demo_covers_every_membership_status() -> None:
    """The seed produces users in every membership status, including a lifetime member."""
    _seed()
    counts = Counter(membership_status(u)["status"] for u in User.objects.all())
    assert counts[MembershipState.CURRENT] == 34
    assert counts[MembershipState.EXPIRED] == 9
    assert counts[MembershipState.NONE] == 5
    lifetime = [u for u in User.objects.all() if membership_status(u)["is_lifetime"]]
    assert len(lifetime) == 6


def test_seed_demo_has_expiring_and_mixed_medicals() -> None:
    """The seed includes a member expiring within 30 days and mixed medical currency."""
    _seed()

    today = timezone.localdate()
    soon = today + timedelta(days=30)
    expiring = [
        u
        for u in User.objects.all()
        if (e := membership_status(u)["expires_on"]) and today <= e <= soon
    ]
    assert len(expiring) == 7

    profiles = MemberProfile.objects.exclude(medical_type="none")
    assert sum(1 for p in profiles if not p.medical_is_current) == 14
    assert sum(1 for p in profiles if p.medical_is_current) == 28
    assert {p.pilot_certificate_type for p in MemberProfile.objects.all()} == {
        "none",
        "student",
        "sport",
        "recreational",
        "private",
        "commercial",
        "atp",
    }


def test_seed_demo_payments_are_mixed_and_span_two_years() -> None:
    """The seed spreads payments across the providers and at least 24 months."""
    _seed()
    providers = set(Payment.objects.values_list("provider", flat=True))
    assert providers == {"stripe", "paypal", "manual"}
    assert Payment.objects.filter(contribution_cents__gt=0).count() == 30 + MANUAL_PAYMENT_COUNT
    months = Payment.objects.dates("created_at", "month")
    oldest, newest = min(months), max(months)
    span = (newest.year - oldest.year) * 12 + newest.month - oldest.month
    # The history the reports are demonstrated on: at least two years of it.
    assert span >= HISTORY_MONTHS


def test_seed_demo_memberships_come_from_payments() -> None:
    """Every seeded membership traces back to a payment."""
    _seed()
    assert Membership.objects.filter(payment__isnull=False).count() == Membership.objects.count()


def test_aircraft_insurance_currency_is_varied() -> None:
    """Some seeded aircraft carry current insurance, some do not, and some have none."""
    _seed()
    current = [a for a in Aircraft.objects.all() if a.insurance_is_current]
    assert len(current) == 18
    assert Aircraft.objects.count() == 25
    assert Aircraft.objects.filter(insurance_expiration__isnull=True).count() == 3


def test_seed_demo_runs_twice_cleanly() -> None:
    """Running ``seed_demo`` a second time leaves every model count unchanged."""
    _seed()
    first = {
        "users": User.objects.count(),
        "profiles": MemberProfile.objects.count(),
        "darts": Dart.objects.count(),
        "plans": MembershipPlan.objects.count(),
        "aircraft": Aircraft.objects.count(),
        "payments": Payment.objects.count(),
        "memberships": Membership.objects.count(),
    }
    _seed()
    second = {
        "users": User.objects.count(),
        "profiles": MemberProfile.objects.count(),
        "darts": Dart.objects.count(),
        "plans": MembershipPlan.objects.count(),
        "aircraft": Aircraft.objects.count(),
        "payments": Payment.objects.count(),
        "memberships": Membership.objects.count(),
    }
    assert first == second


def test_seed_demo_creates_the_wagtail_site_root() -> None:
    """The seed creates the default Wagtail site, rooted at a ``HomePage``."""
    _seed()

    site = Site.objects.get(is_default_site=True)
    assert site.root_page.specific_class.__name__ == "HomePage"
    assert SiteSettings.objects.filter(site=site).exists()
