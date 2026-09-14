"""``membership_status`` maths and ``activate_term`` rules."""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from freezegun import freeze_time

from apps.members.models import Membership, MembershipSource, MembershipStatusChoices
from apps.members.services import activate_term, expire_lapsed_memberships, membership_status
from tests.factories import MembershipFactory, PaymentFactory

pytestmark = pytest.mark.django_db

TODAY = date(2026, 6, 15)


@pytest.fixture
def frozen():
    # Midday UTC, so ``timezone.localdate()`` in America/Los_Angeles is still
    # ``TODAY`` rather than the day before.
    with freeze_time(f"{TODAY.isoformat()} 12:00:00"):
        yield TODAY


def test_no_memberships_is_none(member, frozen):
    assert membership_status(member) == {
        "status": "none",
        "expires_on": None,
        "plan": None,
        "is_lifetime": False,
    }


def test_anonymous_user_is_none():
    from django.contrib.auth.models import AnonymousUser

    assert membership_status(AnonymousUser())["status"] == "none"


def test_current_term(member, annual_plan, frozen):
    MembershipFactory(
        user=member,
        plan=annual_plan,
        starts_on=TODAY - timedelta(days=10),
        ends_on=TODAY + timedelta(days=354),
    )
    status = membership_status(member)
    assert status["status"] == "current"
    assert status["expires_on"] == TODAY + timedelta(days=354)
    assert status["plan"] == "Annual"
    assert status["is_lifetime"] is False


def test_expiry_today_is_still_current(member, annual_plan, frozen):
    """The last day of a term is inclusive."""
    MembershipFactory(
        user=member, plan=annual_plan, starts_on=TODAY - timedelta(days=364), ends_on=TODAY
    )
    assert membership_status(member)["status"] == "current"


def test_expiry_yesterday_is_expired(member, annual_plan, frozen):
    MembershipFactory(
        user=member,
        plan=annual_plan,
        starts_on=TODAY - timedelta(days=365),
        ends_on=TODAY - timedelta(days=1),
    )
    assert membership_status(member)["status"] == "expired"


def test_term_starting_tomorrow_is_not_yet_current(member, annual_plan, frozen):
    MembershipFactory(
        user=member,
        plan=annual_plan,
        starts_on=TODAY + timedelta(days=1),
        ends_on=TODAY + timedelta(days=365),
    )
    assert membership_status(member)["status"] == "none"


def test_term_starting_today_is_current(member, annual_plan, frozen):
    MembershipFactory(
        user=member, plan=annual_plan, starts_on=TODAY, ends_on=TODAY + timedelta(days=364)
    )
    assert membership_status(member)["status"] == "current"


def test_lifetime_membership(member, life_plan, frozen):
    MembershipFactory(
        user=member, plan=life_plan, starts_on=TODAY - timedelta(days=900), ends_on=None
    )
    status = membership_status(member)
    assert status == {
        "status": "current",
        "expires_on": None,
        "plan": "Life",
        "is_lifetime": True,
    }


def test_lifetime_wins_over_a_shorter_current_term(member, annual_plan, life_plan, frozen):
    MembershipFactory(
        user=member, plan=annual_plan, starts_on=TODAY, ends_on=TODAY + timedelta(days=10)
    )
    MembershipFactory(user=member, plan=life_plan, starts_on=TODAY, ends_on=None)
    assert membership_status(member)["is_lifetime"] is True


def test_cancelled_term_does_not_count(member, annual_plan, frozen):
    MembershipFactory(
        user=member,
        plan=annual_plan,
        starts_on=TODAY,
        ends_on=TODAY + timedelta(days=364),
        status=MembershipStatusChoices.CANCELLED,
    )
    assert membership_status(member)["status"] == "none"


def test_expired_reports_the_most_recent_term(member, annual_plan, frozen):
    MembershipFactory(
        user=member,
        plan=annual_plan,
        starts_on=TODAY - timedelta(days=800),
        ends_on=TODAY - timedelta(days=436),
    )
    latest_end = TODAY - timedelta(days=71)
    MembershipFactory(
        user=member, plan=annual_plan, starts_on=TODAY - timedelta(days=435), ends_on=latest_end
    )
    status = membership_status(member)
    assert status["status"] == "expired"
    assert status["expires_on"] == latest_end


def test_membership_status_accepts_an_explicit_date(member, annual_plan):
    MembershipFactory(
        user=member,
        plan=annual_plan,
        starts_on=date(2026, 1, 1),
        ends_on=date(2026, 12, 31),
    )
    assert membership_status(member, date(2026, 6, 1))["status"] == "current"
    assert membership_status(member, date(2027, 1, 1))["status"] == "expired"


# -- activate_term ---------------------------------------------------------
def test_new_member_term_starts_today(member, annual_plan, frozen):
    term = activate_term(member, annual_plan, source=MembershipSource.MANUAL)
    assert term.starts_on == TODAY
    assert term.ends_on == TODAY + timedelta(days=364)
    assert membership_status(member)["status"] == "current"


def test_renewal_starts_the_day_after_the_current_expiry(member, annual_plan, frozen):
    expiry = TODAY + timedelta(days=40)
    MembershipFactory(
        user=member, plan=annual_plan, starts_on=TODAY - timedelta(days=324), ends_on=expiry
    )
    term = activate_term(member, annual_plan, source=MembershipSource.MANUAL)
    assert term.starts_on == expiry + timedelta(days=1)
    assert term.ends_on == expiry + timedelta(days=365)


def test_renewal_after_expiry_starts_today(member, annual_plan, frozen):
    MembershipFactory(
        user=member,
        plan=annual_plan,
        starts_on=TODAY - timedelta(days=400),
        ends_on=TODAY - timedelta(days=36),
    )
    term = activate_term(member, annual_plan, source=MembershipSource.MANUAL)
    assert term.starts_on == TODAY


def test_renewal_on_the_expiry_day_starts_tomorrow(member, annual_plan, frozen):
    MembershipFactory(
        user=member, plan=annual_plan, starts_on=TODAY - timedelta(days=364), ends_on=TODAY
    )
    term = activate_term(member, annual_plan, source=MembershipSource.MANUAL)
    assert term.starts_on == TODAY + timedelta(days=1)


def test_lifetime_plan_has_no_end(member, life_plan, frozen):
    term = activate_term(member, life_plan, source=MembershipSource.MANUAL)
    assert term.ends_on is None
    assert membership_status(member)["is_lifetime"] is True


def test_explicit_starts_on_is_respected(member, annual_plan, frozen):
    term = activate_term(
        member, annual_plan, source=MembershipSource.SEED, starts_on=date(2020, 3, 1)
    )
    assert term.starts_on == date(2020, 3, 1)
    assert term.ends_on == date(2021, 2, 28)


def test_activate_term_is_idempotent_on_payment(member, annual_plan, frozen):
    payment = PaymentFactory(user=member, plan=annual_plan)
    first = activate_term(member, annual_plan, payment=payment)
    second = activate_term(member, annual_plan, payment=payment)
    assert first.pk == second.pk
    assert Membership.objects.filter(user=member).count() == 1


def test_activate_term_records_granted_by(member, account_admin, annual_plan, frozen):
    term = activate_term(
        member,
        annual_plan,
        source=MembershipSource.MANUAL,
        granted_by=account_admin,
        note="Comped for volunteering",
    )
    assert term.granted_by == account_admin
    assert term.note == "Comped for volunteering"


def test_new_term_for_a_lifetime_member_starts_today(member, annual_plan, life_plan, frozen):
    MembershipFactory(
        user=member, plan=life_plan, starts_on=TODAY - timedelta(days=100), ends_on=None
    )
    term = activate_term(member, annual_plan, source=MembershipSource.MANUAL)
    assert term.starts_on == TODAY


def test_expire_lapsed_memberships(member, annual_plan, frozen):
    lapsed = MembershipFactory(
        user=member,
        plan=annual_plan,
        starts_on=TODAY - timedelta(days=400),
        ends_on=TODAY - timedelta(days=1),
    )
    live = MembershipFactory(
        user=member, plan=annual_plan, starts_on=TODAY, ends_on=TODAY + timedelta(days=364)
    )
    assert expire_lapsed_memberships(TODAY) == 1
    lapsed.refresh_from_db()
    live.refresh_from_db()
    assert lapsed.status == MembershipStatusChoices.EXPIRED
    assert live.status == MembershipStatusChoices.ACTIVE


def test_membership_covers(member, annual_plan, frozen):
    term = MembershipFactory(
        user=member, plan=annual_plan, starts_on=TODAY, ends_on=TODAY + timedelta(days=9)
    )
    assert term.covers(TODAY)
    assert term.covers(TODAY + timedelta(days=9))
    assert not term.covers(TODAY + timedelta(days=10))
    assert not term.covers(TODAY - timedelta(days=1))
