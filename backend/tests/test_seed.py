"""The seed commands must be safe to run repeatedly."""

from __future__ import annotations

from collections import Counter
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.accounts.roles import ROLE_SLUGS, SYSTEM_ADMIN
from apps.accounts.seed import DEMO_ACCOUNTS, DEMO_PASSWORD
from apps.aircraft.models import Aircraft
from apps.members.models import Dart, MemberProfile, Membership, MembershipPlan
from apps.members.services import membership_status
from apps.payments.models import Payment, PaymentStatus

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.fixture(scope="module")
def _unused():  # pragma: no cover - placeholder so the module has no import side effects
    return None


def _seed() -> None:
    call_command("seed_demo", stdout=StringIO())


def test_seed_roles_command():
    call_command("seed_roles", stdout=StringIO())
    from django.contrib.auth.models import Group

    assert Group.objects.filter(name__in=ROLE_SLUGS).count() == len(ROLE_SLUGS)


def test_seed_demo_creates_the_documented_accounts():
    _seed()
    for _key, email, _first, _last, roles, is_superuser in DEMO_ACCOUNTS:
        user = User.objects.get(email=email)
        assert user.check_password(DEMO_PASSWORD)
        assert set(roles) <= set(user.roles)
        assert user.is_superuser is is_superuser


def test_sysadmin_is_a_superuser():
    _seed()
    user = User.objects.get(email="sysadmin@example.org")
    assert user.is_superuser and user.is_staff
    assert user.has_role(SYSTEM_ADMIN)


def test_seed_demo_shapes():
    _seed()
    assert Dart.objects.count() == 16
    assert MembershipPlan.objects.count() == 2
    assert MembershipPlan.objects.get(slug="annual").price_cents == 4_500
    assert MembershipPlan.objects.get(slug="life").duration_days is None
    assert User.objects.count() >= 47
    assert MemberProfile.objects.count() == User.objects.count()
    assert Aircraft.objects.count() == 25
    assert Payment.objects.filter(status=PaymentStatus.SUCCEEDED).count() >= 60


def test_seed_demo_covers_every_membership_status():
    _seed()
    counts = Counter(membership_status(u)["status"] for u in User.objects.all())
    assert counts["current"] > 0
    assert counts["expired"] > 0
    assert counts["none"] > 0
    assert any(membership_status(u)["is_lifetime"] for u in User.objects.all())


def test_seed_demo_has_expiring_and_mixed_medicals():
    _seed()
    from datetime import timedelta

    from django.utils import timezone

    today = timezone.localdate()
    soon = today + timedelta(days=30)
    expiring = [
        u
        for u in User.objects.all()
        if (e := membership_status(u)["expires_on"]) and today <= e <= soon
    ]
    assert expiring, "seed should include members expiring within 30 days"

    profiles = MemberProfile.objects.exclude(medical_type="none")
    assert any(not p.medical_is_current for p in profiles)
    assert any(p.medical_is_current for p in profiles)
    assert len({p.pilot_certificate_type for p in MemberProfile.objects.all()}) > 2


def test_seed_demo_payments_are_mixed_and_span_two_years():
    _seed()
    providers = set(Payment.objects.values_list("provider", flat=True))
    assert {"stripe", "paypal"} <= providers
    assert Payment.objects.filter(contribution_cents__gt=0).exists()
    months = Payment.objects.dates("created_at", "month")
    assert len(months) >= 24


def test_seed_demo_memberships_come_from_payments():
    _seed()
    assert Membership.objects.filter(payment__isnull=False).count() == Membership.objects.count()


def test_aircraft_insurance_currency_is_varied():
    _seed()
    current = [a for a in Aircraft.objects.all() if a.insurance_is_current]
    assert current
    assert len(current) < Aircraft.objects.count()
    assert Aircraft.objects.filter(insurance_expiration__isnull=True).exists()


def test_seed_demo_runs_twice_cleanly():
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


def test_seed_demo_creates_the_wagtail_site_root():
    _seed()
    from wagtail.models import Site

    from apps.cms.models import SiteSettings

    site = Site.objects.get(is_default_site=True)
    assert site.root_page.specific_class.__name__ == "HomePage"
    assert SiteSettings.objects.filter(site=site).exists()
