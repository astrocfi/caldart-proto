"""The seed commands must be safe to run repeatedly."""

from __future__ import annotations

from collections import Counter
from datetime import timedelta
from io import StringIO
from itertools import pairwise
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
from apps.payments.models import Payment, PaymentStatus, RenewalMandate
from apps.payments.renewals import _due_attempts, lapsed_term_to_renew, run_auto_renewals
from apps.payments.seed import CATCH_UP_MANDATE_DAYS_AGO, HISTORY_MONTHS, MANUAL_PAYMENT_COUNT
from apps.reports.models import ReportSubscription
from apps.reports.services import due_subscriptions, run_scheduled_reports

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


def test_seed_demo_leaves_no_account_unverified() -> None:
    """Every seeded account's address is verified, as of the moment it was created."""
    _seed()
    assert User.objects.filter(email_verified_at__isnull=True).count() == 0


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


# -- reports -------------------------------------------------------------------
def test_seed_demo_subscribes_the_administrator_and_the_treasurer() -> None:
    """Three subscriptions, all set up by the demo account administrator.

    The membership report goes monthly as a PDF to the account administrator, this
    year's payments quarterly as a CSV to the treasurer, and the aircraft register
    weekly as a CSV and a PDF to the account administrator.
    """
    _seed()

    rows = [
        (
            row.report,
            row.recipient_user.email if row.recipient_user is not None else None,
            row.filters,
            row.formats,
            row.cadence,
            row.created_by.email if row.created_by is not None else None,
        )
        for row in ReportSubscription.objects.order_by("report")
    ]
    assert rows == [
        (
            "aircraft",
            "accountadmin@example.org",
            {},
            "both",
            "weekly",
            "accountadmin@example.org",
        ),
        ("members", "accountadmin@example.org", {}, "pdf", "monthly", "accountadmin@example.org"),
        (
            "payments",
            "treasurer@example.org",
            {"period": "this_year"},
            "csv",
            "quarterly",
            "accountadmin@example.org",
        ),
    ]


def test_seed_demo_keeps_three_subscriptions_on_a_second_run() -> None:
    """Running the seed again updates the three subscriptions rather than adding more."""
    _seed()
    _seed()

    assert ReportSubscription.objects.count() == 3


# -- seed readiness --------------------------------------------------------
def test_seed_demo_leaves_every_subscription_due_today() -> None:
    """Every seeded subscription's ``next_due_on`` is the day the seed runs."""
    _seed()
    today = timezone.localdate()
    subscriptions = list(ReportSubscription.objects.all())
    assert len(subscriptions) == 3
    assert [row.next_due_on for row in subscriptions] == [today] * 3
    assert [row.last_sent_at for row in subscriptions] == [None] * 3


def test_seed_demo_leaves_three_subscriptions_for_the_scheduled_report_job() -> None:
    """``due_subscriptions`` finds every seeded subscription right after a seed."""
    _seed()
    assert due_subscriptions(timezone.localdate()).count() == 3


def test_send_scheduled_reports_sends_every_subscription_and_every_roster() -> None:
    """The daily job sends the three subscriptions and every active DART's roster."""
    _seed()
    run = run_scheduled_reports()
    active_darts = Dart.objects.filter(is_active=True).count()
    assert run.failed == 0
    assert ReportSubscription.objects.filter(last_sent_at__isnull=False).count() == 3
    assert Dart.objects.filter(is_active=True, roster_sent_at__isnull=False).count() == active_darts


def test_seed_demo_leaves_two_renewals_due_for_an_ordinary_charge() -> None:
    """Two generated members hold a scheduled attempt against a term ending today."""
    _seed()
    today = timezone.localdate()
    attempts = _due_attempts(today)
    assert [attempt.membership.ends_on for attempt in attempts] == [today, today]


def test_seed_demo_leaves_a_catch_up_mandate_with_no_attempt() -> None:
    """The catch-up member's mandate has no attempt and a term lapsed ten days back."""
    _seed()
    today = timezone.localdate()
    catch_up = RenewalMandate.objects.get(
        next_charge_on=today - timedelta(days=CATCH_UP_MANDATE_DAYS_AGO)
    )
    assert catch_up.attempts.count() == 0
    term = lapsed_term_to_renew(catch_up.user, today)
    assert term is not None
    assert term.ends_on == today - timedelta(days=CATCH_UP_MANDATE_DAYS_AGO)


def test_run_auto_renewals_charges_the_three_seeded_renewals() -> None:
    """The daily scan charges both due-today renewals and the catch-up one."""
    _seed()
    run = run_auto_renewals()
    assert run.charged == 3
    assert run.failed == 0


def test_seed_demo_never_gives_a_member_overlapping_terms() -> None:
    """No seeded member's terms overlap: each ends before the next one starts.

    Pinning a renewal-seed subject's last term to a fixed end date must shift
    every earlier term of theirs by the same amount, or the pinned term would
    land inside, or short of, the one before it.
    """
    _seed()
    terms_by_user: dict[int, list[Membership]] = {}
    for term in Membership.objects.order_by("user_id", "starts_on", "id"):
        terms_by_user.setdefault(term.user_id, []).append(term)
    for terms in terms_by_user.values():
        for previous, current in pairwise(terms):
            if previous.ends_on is None:
                continue
            assert previous.ends_on < current.starts_on
