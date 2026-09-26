"""The day a standing authority is charged on, which the member chooses.

A mandate stores ``next_charge_on``.  It defaults to the day the membership runs
out -- one year from today for a life member, who has no expiry -- and the member
may name any later day instead.  The scanner notices ``NOTICE_DAYS`` before the
stored date, charges on it, and rolls it forward once the charge goes through.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.core.mail import EmailMessage
from pytest_django.fixtures import Settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.members.models import Membership, MembershipPlan, MembershipStatusChoices
from apps.payments.models import (
    MandateCadence,
    MandateProvider,
    MandateStatus,
    Payment,
    RenewalAttempt,
    RenewalMandate,
    RenewalOutcome,
)
from apps.payments.renewals import (
    CATCH_UP_DAYS,
    NOTICE_DAYS,
    PAST_CHARGE_DATE_MESSAGE,
    RETRY_OFFSETS,
    advance_by_cadence,
    begin_mandate,
    charge_date,
    default_charge_date,
    run_auto_renewals,
)
from tests.factories import MembershipFactory, RenewalAttemptFactory, RenewalMandateFactory

pytestmark = pytest.mark.django_db

CHECKOUT = "/api/v1/payments/checkout"
MOCK_COMPLETE = "/api/v1/payments/mock/complete"
MY_RENEWAL = "/api/v1/me/renewal"
SETUP = "/api/v1/me/renewal/setup"
CONFIRM = "/api/v1/me/renewal/confirm"

#: What the authorities in this module contribute each year, in cents.
CONTRIBUTION_CENTS = 2_000


@pytest.fixture(autouse=True)
def _mock_only(settings: Settings) -> None:
    """Only the mock provider is configured, so no browser SDK is needed."""
    settings.PAYMENTS_MOCK_ENABLED = True
    settings.STRIPE_SECRET_KEY = ""
    settings.STRIPE_PUBLISHABLE_KEY = ""
    settings.PAYPAL_CLIENT_ID = ""
    settings.PAYPAL_CLIENT_SECRET = ""


@pytest.fixture
def expires_on(today: date) -> date:
    """The day the ``dated_member`` fixture's membership runs out."""
    return today + timedelta(days=335)


@pytest.fixture
def dated_member(member: User, annual_plan: MembershipPlan, today: date, expires_on: date) -> User:
    """A member holding an annual term that runs out in a little under a year."""
    MembershipFactory(
        user=member,
        plan=annual_plan,
        starts_on=today - timedelta(days=30),
        ends_on=expires_on,
        status=MembershipStatusChoices.ACTIVE,
    )
    return member


@pytest.fixture
def life_member(member: User, life_plan: MembershipPlan, today: date) -> User:
    """A member holding a lifetime term, whose membership never runs out."""
    MembershipFactory(
        user=member,
        plan=life_plan,
        starts_on=today - timedelta(days=400),
        ends_on=None,
        status=MembershipStatusChoices.ACTIVE,
    )
    return member


def active_mandate(
    user: User, plan: MembershipPlan | None, *, next_charge_on: date, contribution_cents: int = 0
) -> RenewalMandate:
    """An active mock mandate for ``user`` whose next charge falls on a given day."""
    return RenewalMandateFactory(
        user=user,
        plan=plan,
        contribution_cents=contribution_cents,
        next_charge_on=next_charge_on,
    )


def term_of(user: User) -> Membership:
    """The member's term that runs furthest into the future."""
    return user.memberships.order_by("-ends_on")[0]


def hand_renewal(api_client: APIClient, user: User) -> Membership:
    """The member buying another annual term themselves, over the ordinary checkout.

    Answers the term the payment bought.
    """
    api_client.force_authenticate(user)
    started = api_client.post(CHECKOUT, {"plan": "annual", "provider": "mock"}, format="json")
    assert started.status_code == 201, started.json()
    completed = api_client.post(MOCK_COMPLETE, {"payment_id": started.json()["payment_id"]})
    assert completed.status_code == 200, completed.json()
    return Membership.objects.get(payment_id=started.json()["payment_id"])


# --------------------------------------------------------------------------
# The default
# --------------------------------------------------------------------------
def test_the_default_charge_day_is_the_day_the_membership_runs_out(
    dated_member: User, today: date, expires_on: date
) -> None:
    """A member with a dated term is charged on its last day unless they say otherwise."""
    assert default_charge_date(dated_member, today) == expires_on


def test_a_donation_begun_with_no_day_is_charged_today(life_member: User, today: date) -> None:
    """A recurring donation renews nothing, so with no day of its own it starts today."""
    mandate = begin_mandate(
        life_member,
        plan=None,
        contribution_cents=CONTRIBUTION_CENTS,
        provider=MandateProvider.MOCK,
    )

    assert mandate.next_charge_on == today


def test_a_member_with_no_term_at_all_is_charged_today(member: User, today: date) -> None:
    """With no expiry there is no later day to wait for."""
    assert default_charge_date(member, today) == today


def test_beginning_a_mandate_without_a_date_takes_the_default(
    dated_member: User, annual_plan: MembershipPlan, expires_on: date
) -> None:
    """A mandate begun with no date is stored against the membership's expiry."""
    mandate = begin_mandate(
        dated_member,
        plan=annual_plan,
        contribution_cents=0,
        provider=MandateProvider.MOCK,
    )
    assert mandate.next_charge_on == expires_on


def test_beginning_a_mandate_with_a_date_keeps_it(
    dated_member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The day the member asked for is the day that is stored."""
    chosen = today + timedelta(days=400)
    mandate = begin_mandate(
        dated_member,
        plan=annual_plan,
        contribution_cents=0,
        provider=MandateProvider.MOCK,
        next_charge_on=chosen,
    )
    assert mandate.next_charge_on == chosen


# --------------------------------------------------------------------------
# Reading the date back
# --------------------------------------------------------------------------
def test_a_mandate_that_is_not_active_has_no_charge_date(
    dated_member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """A canceled authority charges nothing, so it answers no date at all."""
    mandate = RenewalMandateFactory(
        user=dated_member,
        plan=annual_plan,
        next_charge_on=today + timedelta(days=10),
        status=MandateStatus.CANCELED,
    )
    assert charge_date(mandate, today) is None


def test_the_charge_date_is_the_stored_day(
    dated_member: User, annual_plan: MembershipPlan, today: date, expires_on: date
) -> None:
    """With nothing scheduled, the stored day is what the screens and emails show."""
    mandate = active_mandate(dated_member, annual_plan, next_charge_on=expires_on)
    assert charge_date(mandate, today) == expires_on


def test_a_stored_day_already_gone_by_reads_as_today(
    dated_member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """A date the scanner missed is answered as today, which is when it is taken."""
    mandate = active_mandate(dated_member, annual_plan, next_charge_on=today - timedelta(days=3))
    assert charge_date(mandate, today) == today


def test_a_scheduled_attempt_sets_the_charge_date(
    dated_member: User, annual_plan: MembershipPlan, today: date, expires_on: date
) -> None:
    """A charge already waiting is the next one, whatever the stored day says."""
    mandate = active_mandate(dated_member, annual_plan, next_charge_on=expires_on)
    waiting = today + timedelta(days=4)
    RenewalAttemptFactory(mandate=mandate, membership=term_of(dated_member), scheduled_on=waiting)
    assert charge_date(mandate, today) == waiting


# --------------------------------------------------------------------------
# Choosing the date over the API
# --------------------------------------------------------------------------
def test_setup_stores_the_day_the_member_chose(
    api_client: APIClient, dated_member: User, today: date
) -> None:
    """``POST /me/renewal/setup`` carries the date into the pending mandate."""
    chosen = today + timedelta(days=200)
    api_client.force_authenticate(dated_member)
    response = api_client.post(
        SETUP,
        {"plan": "annual", "provider": "mock", "next_charge_on": chosen.isoformat()},
        format="json",
    )

    assert response.status_code == 200, response.json()
    assert RenewalMandate.objects.get(user=dated_member).next_charge_on == chosen


def test_setup_refuses_a_day_already_past(
    api_client: APIClient, dated_member: User, today: date
) -> None:
    """A first charge cannot be asked for in the past."""
    api_client.force_authenticate(dated_member)
    response = api_client.post(
        SETUP,
        {
            "plan": "annual",
            "provider": "mock",
            "next_charge_on": (today - timedelta(days=1)).isoformat(),
        },
        format="json",
    )

    assert response.status_code == 400
    assert response.json()["next_charge_on"] == [PAST_CHARGE_DATE_MESSAGE]


def test_patching_the_mandate_moves_the_charge_day(
    api_client: APIClient, dated_member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """``PATCH /me/renewal`` saves the day beside the contribution."""
    active_mandate(dated_member, annual_plan, next_charge_on=today + timedelta(days=10))
    moved = today + timedelta(days=40)
    api_client.force_authenticate(dated_member)
    response = api_client.patch(
        MY_RENEWAL,
        {"contribution_cents": 0, "next_charge_on": moved.isoformat()},
        format="json",
    )

    assert response.status_code == 200, response.json()
    assert RenewalMandate.objects.get(user=dated_member).next_charge_on == moved


def test_patching_without_a_date_leaves_the_charge_day_alone(
    api_client: APIClient, dated_member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """A patch that only changes the contribution does not move the charge."""
    stored = today + timedelta(days=10)
    active_mandate(dated_member, annual_plan, next_charge_on=stored)
    api_client.force_authenticate(dated_member)
    response = api_client.patch(MY_RENEWAL, {"contribution_cents": 2_500}, format="json")

    assert response.status_code == 200, response.json()
    assert RenewalMandate.objects.get(user=dated_member).next_charge_on == stored


def test_patching_the_day_leaves_a_charge_already_scheduled_alone(
    api_client: APIClient, dated_member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """A charge already waiting keeps its day, which is the day the answer carries."""
    mandate = active_mandate(dated_member, annual_plan, next_charge_on=today + timedelta(days=10))
    waiting = today + timedelta(days=3)
    RenewalAttemptFactory(mandate=mandate, membership=term_of(dated_member), scheduled_on=waiting)
    api_client.force_authenticate(dated_member)
    response = api_client.patch(
        MY_RENEWAL,
        {"contribution_cents": 0, "next_charge_on": (today + timedelta(days=40)).isoformat()},
        format="json",
    )

    assert response.status_code == 200, response.json()
    assert response.json()["mandate"]["next_charge_on"] == waiting.isoformat()


def test_patching_refuses_a_day_already_past(
    api_client: APIClient, dated_member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The charge cannot be moved into the past."""
    active_mandate(dated_member, annual_plan, next_charge_on=today + timedelta(days=10))
    api_client.force_authenticate(dated_member)
    response = api_client.patch(
        MY_RENEWAL,
        {"contribution_cents": 0, "next_charge_on": (today - timedelta(days=1)).isoformat()},
        format="json",
    )

    assert response.status_code == 400
    assert response.json()["next_charge_on"] == [PAST_CHARGE_DATE_MESSAGE]


def test_checkout_refuses_a_day_already_past(
    api_client: APIClient, dated_member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """A checkout cannot start a standing authority on a day that has gone."""
    api_client.force_authenticate(dated_member)
    response = api_client.post(
        CHECKOUT,
        {
            "plan": "annual",
            "provider": "mock",
            "auto_renew": True,
            "next_charge_on": (today - timedelta(days=1)).isoformat(),
        },
        format="json",
    )

    assert response.status_code == 400
    assert response.json()["next_charge_on"] == [PAST_CHARGE_DATE_MESSAGE]


def test_a_checkout_with_no_date_charges_on_the_new_terms_expiry(
    api_client: APIClient, dated_member: User, annual_plan: MembershipPlan
) -> None:
    """The term the money buys is what sets the first automatic charge."""
    api_client.force_authenticate(dated_member)
    started = api_client.post(
        CHECKOUT, {"plan": "annual", "provider": "mock", "auto_renew": True}, format="json"
    )
    assert started.status_code == 201, started.json()
    completed = api_client.post(MOCK_COMPLETE, {"payment_id": started.json()["payment_id"]})
    assert completed.status_code == 200, completed.json()

    payment = Payment.objects.get(pk=started.json()["payment_id"])
    bought = Membership.objects.get(payment=payment)
    assert RenewalMandate.objects.get(user=dated_member).next_charge_on == bought.ends_on


def test_a_checkout_keeps_the_day_the_member_chose(
    api_client: APIClient, dated_member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """A chosen date survives the payment that starts the authority."""
    chosen = today + timedelta(days=500)
    api_client.force_authenticate(dated_member)
    started = api_client.post(
        CHECKOUT,
        {
            "plan": "annual",
            "provider": "mock",
            "auto_renew": True,
            "next_charge_on": chosen.isoformat(),
        },
        format="json",
    )
    assert started.status_code == 201, started.json()
    completed = api_client.post(MOCK_COMPLETE, {"payment_id": started.json()["payment_id"]})
    assert completed.status_code == 200, completed.json()

    assert RenewalMandate.objects.get(user=dated_member).next_charge_on == chosen


# --------------------------------------------------------------------------
# The scan
# --------------------------------------------------------------------------
def test_the_notice_goes_out_a_fortnight_before_the_stored_day(
    dated_member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """A stored day exactly ``NOTICE_DAYS`` out is announced and scheduled."""
    charge_on = today + timedelta(days=NOTICE_DAYS)
    mandate = active_mandate(dated_member, annual_plan, next_charge_on=charge_on)

    run = run_auto_renewals(today=today)

    assert run.noticed == 1
    assert mandate.attempts.get().scheduled_on == charge_on


def test_nothing_is_announced_before_the_notice_window(
    dated_member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """A stored day a day further out than the window is left for a later scan."""
    active_mandate(
        dated_member, annual_plan, next_charge_on=today + timedelta(days=NOTICE_DAYS + 1)
    )

    run = run_auto_renewals(today=today)

    assert run.noticed == 0


def test_a_successful_charge_rolls_the_stored_day_to_the_new_expiry(
    dated_member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """After the renewal the stored day is the day the new term runs out."""
    mandate = active_mandate(dated_member, annual_plan, next_charge_on=today)

    run_auto_renewals(today=today)

    mandate.refresh_from_db()
    renewed = dated_member.memberships.order_by("-ends_on").first()
    assert renewed is not None
    assert mandate.next_charge_on == renewed.ends_on


def test_a_yearly_donations_stored_day_rolls_on_a_year(life_member: User, today: date) -> None:
    """A donation has no term, so it moves one cadence on from the day it was taken."""
    mandate = active_mandate(
        life_member, None, next_charge_on=today, contribution_cents=CONTRIBUTION_CENTS
    )

    run_auto_renewals(today=today)

    mandate.refresh_from_db()
    assert mandate.next_charge_on == advance_by_cadence(today, MandateCadence.YEARLY)


def test_a_refused_charge_leaves_the_stored_day_alone(
    dated_member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """A retry lives on the attempt; the day the member chose does not move."""
    mandate = RenewalMandateFactory(
        user=dated_member,
        plan=annual_plan,
        next_charge_on=today,
        method_last4="0002",
        method_label="Test card ending 0002, expires 12/2030",
    )

    run_auto_renewals(today=today)

    mandate.refresh_from_db()
    assert mandate.next_charge_on == today


def test_a_refused_charge_schedules_its_retry_from_the_attempt(
    dated_member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The next try is the first retry offset after the day the charge was refused."""
    mandate = RenewalMandateFactory(
        user=dated_member,
        plan=annual_plan,
        next_charge_on=today,
        method_last4="0002",
        method_label="Test card ending 0002, expires 12/2030",
    )

    run_auto_renewals(today=today)

    retry = mandate.attempts.filter(outcome=RenewalOutcome.SCHEDULED).get()
    assert retry.scheduled_on == today + timedelta(days=RETRY_OFFSETS[0])


def test_a_stored_day_far_enough_behind_pauses_the_mandate(
    dated_member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """A charge missed by longer than the catch-up window is never taken unannounced."""
    term = term_of(dated_member)
    term.ends_on = today - timedelta(days=CATCH_UP_DAYS + 2)
    term.save(update_fields=["ends_on"])
    mandate = active_mandate(dated_member, annual_plan, next_charge_on=term.ends_on)

    run = run_auto_renewals(today=today)

    mandate.refresh_from_db()
    assert run.paused == 1
    assert mandate.status == MandateStatus.PAUSED


def test_a_stored_day_just_behind_is_charged_today(
    dated_member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """A charge missed inside the catch-up window is taken on the day it is found."""
    term = term_of(dated_member)
    term.ends_on = today - timedelta(days=2)
    term.save(update_fields=["ends_on"])
    active_mandate(dated_member, annual_plan, next_charge_on=term.ends_on)

    run = run_auto_renewals(today=today)

    assert run.charged == 1
    assert RenewalAttempt.objects.get(outcome=RenewalOutcome.SUCCEEDED).scheduled_on == today


# --------------------------------------------------------------------------
# Coverage bought outside the scan
# --------------------------------------------------------------------------
def test_a_hand_renewal_moves_the_stored_day_to_the_new_expiry(
    api_client: APIClient, dated_member: User, annual_plan: MembershipPlan, expires_on: date
) -> None:
    """Paying by hand carries the stored day on to the expiry of the term just bought."""
    mandate = active_mandate(dated_member, annual_plan, next_charge_on=expires_on)

    bought = hand_renewal(api_client, dated_member)

    mandate.refresh_from_db()
    assert mandate.next_charge_on == bought.ends_on


def test_a_hand_renewal_keeps_a_day_chosen_early_as_early_as_it_was(
    api_client: APIClient, dated_member: User, annual_plan: MembershipPlan, expires_on: date
) -> None:
    """A day placed a fortnight before the expiry stays a fortnight before it."""
    early = timedelta(days=NOTICE_DAYS)
    mandate = active_mandate(dated_member, annual_plan, next_charge_on=expires_on - early)

    bought = hand_renewal(api_client, dated_member)

    mandate.refresh_from_db()
    assert bought.ends_on is not None
    assert mandate.next_charge_on == bought.ends_on - early


def test_a_hand_renewal_is_not_charged_for_again_on_the_old_day(
    api_client: APIClient, dated_member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """A member who renews a month early is not charged again when the old day comes."""
    term = term_of(dated_member)
    term.ends_on = today + timedelta(days=30)
    term.save(update_fields=["ends_on"])
    active_mandate(dated_member, annual_plan, next_charge_on=term.ends_on)
    hand_renewal(api_client, dated_member)

    run = run_auto_renewals(today=term.ends_on)

    assert run.charged == 0
    assert Payment.objects.count() == 1


def test_a_charge_waiting_when_the_coverage_arrives_is_skipped_and_rolled_on(
    api_client: APIClient, dated_member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """A scheduled charge overtaken by a hand renewal neither charges nor sits still."""
    term = term_of(dated_member)
    term.ends_on = today + timedelta(days=NOTICE_DAYS)
    term.save(update_fields=["ends_on"])
    mandate = active_mandate(dated_member, annual_plan, next_charge_on=term.ends_on)
    RenewalAttemptFactory(mandate=mandate, membership=term, scheduled_on=term.ends_on)
    bought = hand_renewal(api_client, dated_member)

    run = run_auto_renewals(today=term.ends_on)

    mandate.refresh_from_db()
    assert run.skipped_by_reason["already_renewed"] == 1
    assert mandate.next_charge_on == bought.ends_on


# --------------------------------------------------------------------------
# A day the member chose beyond their expiry
# --------------------------------------------------------------------------
def test_a_day_chosen_after_the_expiry_waits_for_its_notice_window(
    dated_member: User, annual_plan: MembershipPlan, today: date, expires_on: date
) -> None:
    """A member who chose a day beyond their expiry lapses until the window opens."""
    chosen = expires_on + timedelta(days=24)
    active_mandate(dated_member, annual_plan, next_charge_on=chosen)

    run = run_auto_renewals(today=chosen - timedelta(days=NOTICE_DAYS + 1))

    assert run.noticed == 0


def test_the_notice_for_a_day_after_the_expiry_promises_no_continuous_coverage(
    dated_member: User,
    annual_plan: MembershipPlan,
    today: date,
    expires_on: date,
    mailoutbox: list[EmailMessage],
) -> None:
    """The member is told their membership lapses until the day they chose."""
    chosen = expires_on + timedelta(days=24)
    active_mandate(dated_member, annual_plan, next_charge_on=chosen)

    run_auto_renewals(today=chosen - timedelta(days=NOTICE_DAYS))

    body = mailoutbox[-1].body
    assert "the day you chose, so your membership lapses until then" in body
    assert "carry straight on" not in body
