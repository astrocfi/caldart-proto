"""``membership_status`` math and ``activate_term`` rules."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date, timedelta

import pytest
from django.contrib.auth.models import AnonymousUser
from freezegun import freeze_time

from apps.accounts.models import User
from apps.members.models import (
    Membership,
    MembershipPlan,
    MembershipSource,
    MembershipStatusChoices,
)
from apps.members.services import activate_term, expire_lapsed_memberships, membership_status
from tests.factories import MembershipFactory, PaymentFactory

pytestmark = pytest.mark.django_db

TODAY = date(2026, 6, 15)


@pytest.fixture
def frozen() -> Iterator[date]:
    """Freeze the clock to ``TODAY`` at midday UTC, and yield that date.

    Midday UTC keeps ``timezone.localdate()`` in America/Los_Angeles on ``TODAY``
    rather than the day before.
    """
    with freeze_time(f"{TODAY.isoformat()} 12:00:00"):
        yield TODAY


def test_no_memberships_is_a_friend(member: User, frozen: date) -> None:
    """A member with no membership terms at all has never paid, so reports ``friend``."""
    assert membership_status(member) == {
        "status": "friend",
        "expires_on": None,
        "plan": None,
        "is_lifetime": False,
    }


def test_anonymous_user_is_a_friend() -> None:
    """An anonymous caller reports status ``friend``, never a lapsed membership."""
    assert membership_status(AnonymousUser())["status"] == "friend"


def test_a_term_covering_today_reports_current(
    member: User, annual_plan: MembershipPlan, frozen: date
) -> None:
    """A term covering today reports current, with its expiry and plan name."""
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


def test_expiry_today_is_still_current(
    member: User, annual_plan: MembershipPlan, frozen: date
) -> None:
    """The last day of a term is inclusive."""
    MembershipFactory(
        user=member, plan=annual_plan, starts_on=TODAY - timedelta(days=364), ends_on=TODAY
    )
    assert membership_status(member)["status"] == "current"


def test_expiry_yesterday_is_expired(
    member: User, annual_plan: MembershipPlan, frozen: date
) -> None:
    """A term that ended yesterday reports expired."""
    MembershipFactory(
        user=member,
        plan=annual_plan,
        starts_on=TODAY - timedelta(days=365),
        ends_on=TODAY - timedelta(days=1),
    )
    assert membership_status(member)["status"] == "expired"


def test_term_starting_tomorrow_is_not_yet_current(
    member: User, annual_plan: MembershipPlan, frozen: date
) -> None:
    """A term that starts tomorrow does not yet count, so the member reads as a friend."""
    MembershipFactory(
        user=member,
        plan=annual_plan,
        starts_on=TODAY + timedelta(days=1),
        ends_on=TODAY + timedelta(days=365),
    )
    assert membership_status(member)["status"] == "friend"


def test_term_starting_today_is_current(
    member: User, annual_plan: MembershipPlan, frozen: date
) -> None:
    """A term that starts today already counts as current."""
    MembershipFactory(
        user=member, plan=annual_plan, starts_on=TODAY, ends_on=TODAY + timedelta(days=364)
    )
    assert membership_status(member)["status"] == "current"


def test_a_lifetime_term_reports_current_with_no_expiry(
    member: User, life_plan: MembershipPlan, frozen: date
) -> None:
    """A lifetime term reports current with no expiry date."""
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


def test_lifetime_wins_over_a_shorter_current_term(
    member: User, annual_plan: MembershipPlan, life_plan: MembershipPlan, frozen: date
) -> None:
    """A lifetime term reports as lifetime even alongside a shorter current term."""
    MembershipFactory(
        user=member, plan=annual_plan, starts_on=TODAY, ends_on=TODAY + timedelta(days=10)
    )
    MembershipFactory(user=member, plan=life_plan, starts_on=TODAY, ends_on=None)
    assert membership_status(member)["is_lifetime"] is True


def test_canceled_term_does_not_count(
    member: User, annual_plan: MembershipPlan, frozen: date
) -> None:
    """A canceled term is not counted, even while its dates cover today."""
    MembershipFactory(
        user=member,
        plan=annual_plan,
        starts_on=TODAY,
        ends_on=TODAY + timedelta(days=364),
        status=MembershipStatusChoices.CANCELED,
    )
    assert membership_status(member)["status"] == "friend"


def test_expired_reports_the_most_recent_term(
    member: User, annual_plan: MembershipPlan, frozen: date
) -> None:
    """An expired member's status reports the most recent term's end date."""
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


def test_membership_status_accepts_an_explicit_date(
    member: User, annual_plan: MembershipPlan
) -> None:
    """``membership_status`` judges coverage against an explicit date, not only today."""
    MembershipFactory(
        user=member,
        plan=annual_plan,
        starts_on=date(2026, 1, 1),
        ends_on=date(2026, 12, 31),
    )
    assert membership_status(member, date(2026, 6, 1))["status"] == "current"
    assert membership_status(member, date(2027, 1, 1))["status"] == "expired"


# -- activate_term ---------------------------------------------------------
def test_new_member_term_starts_today(
    member: User, annual_plan: MembershipPlan, frozen: date
) -> None:
    """A brand-new term starts today and runs the plan's full duration."""
    term = activate_term(member, annual_plan, source=MembershipSource.MANUAL)
    assert term.starts_on == TODAY
    assert term.ends_on == TODAY + timedelta(days=364)
    assert membership_status(member)["status"] == "current"


def test_renewal_starts_the_day_after_the_current_expiry(
    member: User, annual_plan: MembershipPlan, frozen: date
) -> None:
    """A renewal of a current term starts the day after the current expiry."""
    expiry = TODAY + timedelta(days=40)
    MembershipFactory(
        user=member, plan=annual_plan, starts_on=TODAY - timedelta(days=324), ends_on=expiry
    )
    term = activate_term(member, annual_plan, source=MembershipSource.MANUAL)
    assert term.starts_on == expiry + timedelta(days=1)
    assert term.ends_on == expiry + timedelta(days=365)


def test_renewal_after_expiry_starts_today(
    member: User, annual_plan: MembershipPlan, frozen: date
) -> None:
    """A renewal after the previous term has lapsed starts today."""
    MembershipFactory(
        user=member,
        plan=annual_plan,
        starts_on=TODAY - timedelta(days=400),
        ends_on=TODAY - timedelta(days=36),
    )
    term = activate_term(member, annual_plan, source=MembershipSource.MANUAL)
    assert term.starts_on == TODAY


def test_renewal_on_the_expiry_day_starts_tomorrow(
    member: User, annual_plan: MembershipPlan, frozen: date
) -> None:
    """A renewal made on the current term's last day starts the next day."""
    MembershipFactory(
        user=member, plan=annual_plan, starts_on=TODAY - timedelta(days=364), ends_on=TODAY
    )
    term = activate_term(member, annual_plan, source=MembershipSource.MANUAL)
    assert term.starts_on == TODAY + timedelta(days=1)


def test_lifetime_plan_has_no_end(member: User, life_plan: MembershipPlan, frozen: date) -> None:
    """Activating a lifetime plan creates a term with no end date."""
    term = activate_term(member, life_plan, source=MembershipSource.MANUAL)
    assert term.ends_on is None
    assert membership_status(member)["is_lifetime"] is True


def test_explicit_starts_on_is_respected(
    member: User, annual_plan: MembershipPlan, frozen: date
) -> None:
    """An explicit ``starts_on`` is honored rather than defaulting to today."""
    term = activate_term(
        member, annual_plan, source=MembershipSource.SEED, starts_on=date(2020, 3, 1)
    )
    assert term.starts_on == date(2020, 3, 1)
    assert term.ends_on == date(2021, 2, 28)


def test_activate_term_is_idempotent_on_payment(
    member: User, annual_plan: MembershipPlan, frozen: date
) -> None:
    """Activating a term twice for the same payment creates only one term."""
    payment = PaymentFactory(user=member, plan=annual_plan)
    first = activate_term(member, annual_plan, payment=payment)
    second = activate_term(member, annual_plan, payment=payment)
    assert first.pk == second.pk
    assert Membership.objects.filter(user=member).count() == 1


def test_activate_term_records_granted_by(
    member: User, account_admin: User, annual_plan: MembershipPlan, frozen: date
) -> None:
    """A manually granted term records who granted it and their note."""
    term = activate_term(
        member,
        annual_plan,
        source=MembershipSource.MANUAL,
        granted_by=account_admin,
        note="Comped for volunteering",
    )
    assert term.granted_by == account_admin
    assert term.note == "Comped for volunteering"


def test_new_term_for_a_lifetime_member_starts_today(
    member: User, annual_plan: MembershipPlan, life_plan: MembershipPlan, frozen: date
) -> None:
    """A new annual term for an existing lifetime member still starts today."""
    MembershipFactory(
        user=member, plan=life_plan, starts_on=TODAY - timedelta(days=100), ends_on=None
    )
    term = activate_term(member, annual_plan, source=MembershipSource.MANUAL)
    assert term.starts_on == TODAY


def test_expire_lapsed_memberships(member: User, annual_plan: MembershipPlan, frozen: date) -> None:
    """The lapsed-term sweep expires only the terms whose end date has passed."""
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


def test_covers_is_true_across_the_whole_term(
    member: User, annual_plan: MembershipPlan, frozen: date
) -> None:
    """``Membership.covers`` is true exactly across the term's start and end dates."""
    term = MembershipFactory(
        user=member, plan=annual_plan, starts_on=TODAY, ends_on=TODAY + timedelta(days=9)
    )
    assert term.covers(TODAY)
    assert term.covers(TODAY + timedelta(days=9))
    assert not term.covers(TODAY + timedelta(days=10))
    assert not term.covers(TODAY - timedelta(days=1))
