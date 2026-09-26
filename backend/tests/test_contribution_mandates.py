"""A life member's standing authority: a recurring donation, charged once a year.

A member holding a lifetime term has nothing to renew, so the only mandate they
hold names no plan: a recurring donation.  These tests drive a yearly one through
setup, the advance notice, the charge, a decline, the retries and the pause, and
check that the endpoints refuse a plan anywhere a life member could offer one.
They also cover the words a mandate that both renews and contributes uses, which
neither a plain renewal nor a donation alone would say.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.core.mail import EmailMessage
from django.utils import timezone
from freezegun import freeze_time
from pytest_django.fixtures import DjangoCaptureOnCommitCallbacks
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.members.models import MembershipPlan, MembershipStatusChoices
from apps.payments.models import (
    MandateCadence,
    MandateProvider,
    MandateStatus,
    Payment,
    RenewalMandate,
    RenewalOutcome,
)
from apps.payments.providers.mock import DECLINED_LAST4, mock_method
from apps.payments.renewals import (
    NOTICE_DAYS,
    RETRY_OFFSETS,
    MandateKind,
    advance_by_cadence,
    charge_date,
    check_renewable,
    kind_label,
    mandate_kind,
    run_auto_renewals,
    save_method,
)
from caldart.exceptions import DomainValidationError
from tests.factories import MembershipFactory, RenewalMandateFactory

pytestmark = pytest.mark.django_db

#: What a seeded contribution-only mandate charges each year, in cents.
CONTRIBUTION_CENTS = 5_000


def make_life_member(user: User, plan: MembershipPlan, *, started: date) -> User:
    """Give ``user`` an active lifetime term under ``plan``, starting on ``started``."""
    MembershipFactory(
        user=user,
        plan=plan,
        starts_on=started,
        ends_on=None,
        status=MembershipStatusChoices.ACTIVE,
    )
    return user


def make_contribution_mandate(
    user: User, *, last4: str = "4242", contribution_cents: int = CONTRIBUTION_CENTS
) -> RenewalMandate:
    """An active yearly recurring donation for ``user``, which names no plan.

    Its charge falls one year from today, the day a donation first set up at a
    checkout today next charges on.
    """
    return RenewalMandateFactory(
        user=user,
        plan=None,
        contribution_cents=contribution_cents,
        cadence=MandateCadence.YEARLY,
        next_charge_on=advance_by_cadence(timezone.localdate(), MandateCadence.YEARLY),
        method_last4=last4,
        method_label=f"Test card ending {last4}, expires 12/2030",
    )


# --------------------------------------------------------------------------
# Kind
# --------------------------------------------------------------------------
def test_a_mandate_with_no_plan_reads_as_a_donation(
    member: User, life_plan: MembershipPlan, today: date
) -> None:
    """A life member's authority is a recurring donation and renews nothing."""
    make_life_member(member, life_plan, started=today - timedelta(days=400))

    assert mandate_kind(make_contribution_mandate(member)) == MandateKind.CONTRIBUTION


def test_a_mandate_with_a_plan_and_a_contribution_reads_as_both(
    member: User, annual_plan: MembershipPlan
) -> None:
    """A plan alongside a contribution is a renewal and a contribution together."""
    mandate = RenewalMandateFactory(user=member, plan=annual_plan, contribution_cents=2_000)

    assert mandate_kind(mandate) == MandateKind.BOTH


def test_a_mandate_with_a_plan_alone_reads_as_a_renewal(
    member: User, annual_plan: MembershipPlan
) -> None:
    """A plan and no contribution is a plain renewal."""
    mandate = RenewalMandateFactory(user=member, plan=annual_plan, contribution_cents=0)

    assert mandate_kind(mandate) == MandateKind.RENEWAL


@pytest.mark.parametrize(
    ("kind", "words"),
    [
        (MandateKind.RENEWAL, "automatic renewal"),
        (MandateKind.BOTH, "automatic renewal and contribution"),
        (MandateKind.CONTRIBUTION, "recurring donation"),
    ],
)
def test_each_kind_has_the_words_the_emails_use(kind: str, words: str) -> None:
    """``kind_label`` gives the running prose every email and screen shares."""
    assert kind_label(kind) == words


# --------------------------------------------------------------------------
# Dates
# --------------------------------------------------------------------------
def test_an_active_donation_always_names_its_next_charge(
    member: User, life_plan: MembershipPlan, today: date
) -> None:
    """A life member is never told there is nothing due: the stored day is the date."""
    make_life_member(member, life_plan, started=today - timedelta(days=400))
    mandate = make_contribution_mandate(member)

    assert charge_date(mandate, today) == advance_by_cadence(today, MandateCadence.YEARLY)


def test_a_member_whose_charge_date_went_by_is_charged_today(
    member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """With the term gone the next scan takes the renewal, so the date shown is today."""
    MembershipFactory(
        user=member,
        plan=annual_plan,
        starts_on=today - timedelta(days=400),
        ends_on=today - timedelta(days=5),
        status=MembershipStatusChoices.EXPIRED,
    )
    mandate = RenewalMandateFactory(
        user=member, plan=annual_plan, next_charge_on=today - timedelta(days=5)
    )

    assert charge_date(mandate, today) == today


# --------------------------------------------------------------------------
# What may be set up
# --------------------------------------------------------------------------
def test_a_life_member_may_not_hold_a_plan_that_renews(
    member: User, life_plan: MembershipPlan, annual_plan: MembershipPlan, today: date
) -> None:
    """Offering a plan is refused with the words that point at a contribution."""
    make_life_member(member, life_plan, started=today - timedelta(days=400))

    with pytest.raises(DomainValidationError, match="does not renew; choose a contribution"):
        check_renewable(
            annual_plan, MandateProvider.MOCK, user=member, contribution_cents=CONTRIBUTION_CENTS
        )


def test_a_life_member_must_name_a_contribution_to_charge(
    member: User, life_plan: MembershipPlan, today: date
) -> None:
    """An authority over nothing at all is refused."""
    make_life_member(member, life_plan, started=today - timedelta(days=400))

    with pytest.raises(DomainValidationError, match="A recurring donation needs an amount"):
        check_renewable(None, MandateProvider.MOCK, user=member, contribution_cents=0)


def test_a_life_member_holding_a_contribution_needs_no_plan(
    member: User, life_plan: MembershipPlan, today: date
) -> None:
    """A contribution with no plan is accepted, and no plan comes back."""
    make_life_member(member, life_plan, started=today - timedelta(days=400))

    assert (
        check_renewable(
            None, MandateProvider.MOCK, user=member, contribution_cents=CONTRIBUTION_CENTS
        )
        is None
    )


def test_a_member_with_a_dated_term_may_hold_a_donation(
    member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """A recurring donation accompanies no membership, so a dated term is no bar."""
    MembershipFactory(
        user=member, plan=annual_plan, starts_on=today, ends_on=today + timedelta(days=365)
    )

    assert (
        check_renewable(None, MandateProvider.MOCK, user=member, contribution_cents=2_000) is None
    )


# --------------------------------------------------------------------------
# The scan
# --------------------------------------------------------------------------
def test_the_notice_goes_out_a_fortnight_before_the_contribution(
    member: User, life_plan: MembershipPlan, today: date, mailoutbox: list[EmailMessage]
) -> None:
    """A contribution due inside the notice window earns one advance warning."""
    make_life_member(member, life_plan, started=today - timedelta(days=400))
    mandate = make_contribution_mandate(member)
    due = mandate.next_charge_on

    with freeze_time(timezone.now() + timedelta(days=(due - today).days - NOTICE_DAYS)):
        run_auto_renewals()

    assert str(mailoutbox[-1].subject) == (
        "CalDART: we will take your recurring donation on " + str(due)
    )


def test_the_notice_never_says_the_word_renew(
    member: User, life_plan: MembershipPlan, today: date, mailoutbox: list[EmailMessage]
) -> None:
    """A life member is never told their membership is being renewed."""
    make_life_member(member, life_plan, started=today - timedelta(days=400))
    mandate = make_contribution_mandate(member)
    due = mandate.next_charge_on

    with freeze_time(timezone.now() + timedelta(days=(due - today).days - NOTICE_DAYS)):
        run_auto_renewals()

    assert "renew" not in str(mailoutbox[-1].body)


def test_the_charge_takes_the_contribution_and_extends_no_term(
    member: User, life_plan: MembershipPlan, today: date
) -> None:
    """The payment is the contribution alone, and the lifetime term is untouched."""
    make_life_member(member, life_plan, started=today - timedelta(days=400))
    mandate = make_contribution_mandate(member)
    due = mandate.next_charge_on

    with freeze_time(timezone.now() + timedelta(days=(due - today).days - NOTICE_DAYS)):
        run_auto_renewals()
    with freeze_time(timezone.now() + timedelta(days=(due - today).days)):
        run_auto_renewals()

    payment = Payment.objects.get(user=member)
    assert payment.plan_id is None
    assert payment.contribution_cents == CONTRIBUTION_CENTS
    assert member.memberships.count() == 1


def test_the_charge_email_thanks_the_member_for_the_donation(
    member: User, life_plan: MembershipPlan, today: date, mailoutbox: list[EmailMessage]
) -> None:
    """The message reporting a donation charge says thank you, not renewed."""
    make_life_member(member, life_plan, started=today - timedelta(days=400))
    mandate = make_contribution_mandate(member)
    due = mandate.next_charge_on

    with freeze_time(timezone.now() + timedelta(days=(due - today).days - NOTICE_DAYS)):
        run_auto_renewals()
    with freeze_time(timezone.now() + timedelta(days=(due - today).days)):
        run_auto_renewals()

    assert str(mailoutbox[-1].subject) == "CalDART: thank you for your recurring donation"


def test_a_refused_contribution_is_retried_and_then_paused(
    member: User, life_plan: MembershipPlan, today: date
) -> None:
    """The retry ladder and the pause apply to a contribution exactly as to a renewal."""
    make_life_member(member, life_plan, started=today - timedelta(days=400))
    mandate = make_contribution_mandate(member, last4=DECLINED_LAST4)
    due = mandate.next_charge_on
    offset = (due - today).days

    with freeze_time(timezone.now() + timedelta(days=offset - NOTICE_DAYS)):
        run_auto_renewals()
    day = offset
    for extra in (0, *RETRY_OFFSETS):
        day += extra
        with freeze_time(timezone.now() + timedelta(days=day)):
            run_auto_renewals()

    mandate.refresh_from_db()
    assert mandate.status == MandateStatus.PAUSED


def test_an_annual_mandate_whose_member_became_a_life_member_is_skipped(
    member: User, life_plan: MembershipPlan, annual_plan: MembershipPlan, today: date
) -> None:
    """A granted lifetime term leaves an annual authority with nothing to renew."""
    make_life_member(member, life_plan, started=today - timedelta(days=10))
    RenewalMandateFactory(user=member, plan=annual_plan)

    run = run_auto_renewals(today=today)

    assert run.skipped_by_reason == {"lifetime": 1}


# --------------------------------------------------------------------------
# A mandate that renews and contributes at once
# --------------------------------------------------------------------------
def make_both_mandate(
    user: User, plan: MembershipPlan, *, ends_on: date, last4: str = "4242"
) -> RenewalMandate:
    """A mandate over ``plan`` with a contribution, for a term ending ``ends_on``."""
    MembershipFactory(
        user=user,
        plan=plan,
        starts_on=ends_on - timedelta(days=364),
        ends_on=ends_on,
        status=MembershipStatusChoices.ACTIVE,
    )
    return RenewalMandateFactory(
        user=user,
        plan=plan,
        contribution_cents=CONTRIBUTION_CENTS,
        method_last4=last4,
        method_label=f"Test card ending {last4}, expires 12/2030",
    )


def one_line(body: str) -> str:
    """``body`` with every run of whitespace collapsed, so wrapping does not matter."""
    return " ".join(body.split())


def test_a_refused_charge_says_the_contribution_was_part_of_it(
    member: User, annual_plan: MembershipPlan, today: date, mailoutbox: list[EmailMessage]
) -> None:
    """A decline names both halves of the money, not the membership alone."""
    make_both_mandate(member, annual_plan, ends_on=today + timedelta(days=1), last4=DECLINED_LAST4)

    run_auto_renewals(today=today)

    assert "membership and take your contribution" in one_line(str(mailoutbox[-1].body))


def test_turning_a_mandate_on_says_it_renews_and_contributes(
    member: User,
    annual_plan: MembershipPlan,
    today: date,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """The message that confirms the authority names the contribution it also takes."""
    mandate = make_both_mandate(member, annual_plan, ends_on=today + timedelta(days=100))
    mandate.status = MandateStatus.PENDING
    mandate.save(update_fields=["status"])

    with django_capture_on_commit_callbacks(execute=True):
        save_method(mandate, mock_method(), actor=member)

    assert "membership and take your contribution" in one_line(str(mailoutbox[-1].body))


# --------------------------------------------------------------------------
# The endpoints
# --------------------------------------------------------------------------
def test_setup_refuses_a_plan_from_a_life_member(
    api_client: APIClient, member: User, life_plan: MembershipPlan, annual_plan: MembershipPlan
) -> None:
    """``POST /me/renewal/setup`` names ``auto_renew`` when a life member picks a plan."""
    make_life_member(member, life_plan, started=timezone.localdate() - timedelta(days=400))
    api_client.force_login(member)

    response = api_client.post(
        "/api/v1/me/renewal/setup",
        {"plan": annual_plan.slug, "contribution_cents": 5_000, "provider": MandateProvider.MOCK},
        format="json",
    )

    assert response.status_code == 400
    assert response.json()["auto_renew"] == [
        "A life member's membership does not renew; choose a contribution instead."
    ]


def test_donation_setup_saves_a_life_members_donation(
    api_client: APIClient, member: User, life_plan: MembershipPlan
) -> None:
    """A life member who names a contribution alone gets a mandate with no plan."""
    make_life_member(member, life_plan, started=timezone.localdate() - timedelta(days=400))
    api_client.force_login(member)

    api_client.post(
        "/api/v1/me/donation/setup",
        {"contribution_cents": 5_000, "provider": MandateProvider.MOCK},
        format="json",
    )

    assert RenewalMandate.objects.get(user=member).plan_id is None


def test_the_mandate_envelope_names_the_kind_and_a_date(
    api_client: APIClient, member: User, life_plan: MembershipPlan
) -> None:
    """``GET /me/donation`` tells a life member their authority is a donation."""
    make_life_member(member, life_plan, started=timezone.localdate() - timedelta(days=400))
    make_contribution_mandate(member)
    api_client.force_login(member)

    mandate = api_client.get("/api/v1/me/donation").json()["mandate"]

    assert mandate["kind"] == MandateKind.CONTRIBUTION


def test_a_donation_reports_no_plan(
    api_client: APIClient, member: User, life_plan: MembershipPlan
) -> None:
    """``plan`` is null for an authority that renews nothing."""
    make_life_member(member, life_plan, started=timezone.localdate() - timedelta(days=400))
    make_contribution_mandate(member)
    api_client.force_login(member)

    mandate = api_client.get("/api/v1/me/donation").json()["mandate"]

    assert mandate["plan"] is None


def test_a_donation_charges_the_contribution_alone(
    api_client: APIClient, member: User, life_plan: MembershipPlan
) -> None:
    """The amount the member is shown is the contribution, with no dues added."""
    make_life_member(member, life_plan, started=timezone.localdate() - timedelta(days=400))
    make_contribution_mandate(member)
    api_client.force_login(member)

    mandate = api_client.get("/api/v1/me/donation").json()["mandate"]

    assert mandate["amount_cents"] == CONTRIBUTION_CENTS


def test_a_life_members_scheduled_donation_names_no_term(
    member: User, life_plan: MembershipPlan, today: date
) -> None:
    """The scheduled charge accompanies no membership, the lifetime term included."""
    make_life_member(member, life_plan, started=today - timedelta(days=400))
    mandate = make_contribution_mandate(member)
    due = mandate.next_charge_on

    with freeze_time(timezone.now() + timedelta(days=(due - today).days - NOTICE_DAYS)):
        run_auto_renewals()

    assert mandate.attempts.get(outcome=RenewalOutcome.SCHEDULED).membership_id is None
