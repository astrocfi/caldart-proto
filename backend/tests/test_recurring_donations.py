"""Recurring donations: a standing authority to give on a schedule, with no plan.

A mandate that names no plan is a recurring donation.  Anybody who can pay may hold
one, beside at most one mandate that renews a plan, and it charges monthly,
quarterly or yearly.  These tests cover the model's constraints, the schedule, the
scan, the ``/me/donation`` endpoints, a checkout that starts one, the rule that a
contribution lives in one place, and the finance list's ``kind`` filter.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager as ContextManager
from datetime import date, timedelta
from io import StringIO

import pytest
from django.core.mail import EmailMessage
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.utils import timezone
from pytest_django.fixtures import Settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.members.models import MembershipPlan, MembershipStatusChoices
from apps.payments import renewals
from apps.payments.models import (
    MandateCadence,
    MandateProvider,
    MandateStatus,
    Payment,
    RenewalAttempt,
    RenewalMandate,
    RenewalOutcome,
)
from apps.payments.providers.base import PaymentError
from apps.payments.providers.mock import DECLINED_LAST4, MockProvider
from apps.payments.renewals import (
    NOTICE_DAYS,
    advance_by_cadence,
    check_renewable,
    run_auto_renewals,
)
from apps.reminders.services import send_renewal_reminders
from caldart.exceptions import DomainValidationError
from tests.conftest import audit_messages
from tests.factories import MembershipFactory, RenewalMandateFactory

pytestmark = pytest.mark.django_db

#: The type of pytest-django's ``django_capture_on_commit_callbacks`` fixture.
type CaptureOnCommit = Callable[..., ContextManager[list[Callable[[], None]]]]

DONATION = "/api/v1/me/donation"
DONATION_SETUP = "/api/v1/me/donation/setup"
DONATION_CONFIRM = "/api/v1/me/donation/confirm"
RENEWAL = "/api/v1/me/renewal"
RENEWAL_SETUP = "/api/v1/me/renewal/setup"
CHECKOUT = "/api/v1/payments/checkout"
MOCK_COMPLETE = "/api/v1/payments/mock/complete"
ADMIN = "/api/v1/admin/renewals"

#: What a donation in these tests gives each time, in cents.
GIFT_CENTS = 2_500

#: The sentence a second place for a contribution is refused with, for $20.00.
RENEWAL_CONTRIBUTION_MESSAGE = (
    "Your automatic renewal already includes a contribution of $20.00 a year. Set up a "
    "recurring donation and that contribution comes off the renewal; your dues still "
    "renew automatically."
)

#: The sentence a contribution on a renewal is refused with beside a donation.
HAS_DONATION_MESSAGE = "You already have a recurring donation. Change it on the Donate screen."


@pytest.fixture(autouse=True)
def mock_enabled(settings: Settings) -> None:
    """Turn the mock payment provider on for every test in this module."""
    settings.PAYMENTS_MOCK_ENABLED = True


@pytest.fixture
def member_client(api_client: APIClient, member: User) -> APIClient:
    """A DRF client signed in as an ordinary member."""
    api_client.force_login(member)
    return api_client


def donation(user: User, **overrides: object) -> RenewalMandate:
    """An active monthly donation for ``user`` of ``GIFT_CENTS``, due today."""
    fields: dict[str, object] = {
        "user": user,
        "plan": None,
        "contribution_cents": GIFT_CENTS,
        "cadence": MandateCadence.MONTHLY,
    }
    fields.update(overrides)
    return RenewalMandateFactory(**fields)


def current_term(user: User, plan: MembershipPlan, today: date) -> None:
    """Give ``user`` an active term on ``plan`` that runs out in ninety days."""
    MembershipFactory(
        user=user,
        plan=plan,
        starts_on=today - timedelta(days=275),
        ends_on=today + timedelta(days=90),
        status=MembershipStatusChoices.ACTIVE,
    )


def donation_setup_body(**overrides: object) -> dict[str, object]:
    """A well-formed ``POST /me/donation/setup`` body for the mock provider."""
    body: dict[str, object] = {
        "contribution_cents": GIFT_CENTS,
        "provider": MandateProvider.MOCK,
        "cadence": MandateCadence.QUARTERLY,
    }
    body.update(overrides)
    return body


# --------------------------------------------------------------------------
# The model
# --------------------------------------------------------------------------
def test_a_member_may_hold_a_renewal_and_a_donation_at_once(
    member: User, annual_plan: MembershipPlan
) -> None:
    """One mandate with a plan and one without sit side by side."""
    RenewalMandateFactory(user=member, plan=annual_plan)
    donation(member)

    assert member.renewal_mandates.count() == 2


def test_a_second_renewal_for_one_member_is_refused(
    member: User, annual_plan: MembershipPlan
) -> None:
    """``renewal_mandate_one_plan_per_user`` keeps a member to one renewal."""
    RenewalMandateFactory(user=member, plan=annual_plan)

    with (
        pytest.raises(IntegrityError, match="renewal_mandate_one_plan_per_user"),
        transaction.atomic(),
    ):
        RenewalMandateFactory(user=member, plan=annual_plan)


def test_a_second_donation_for_one_member_is_refused(member: User) -> None:
    """``renewal_mandate_one_donation_per_user`` keeps a member to one donation."""
    donation(member)

    with (
        pytest.raises(IntegrityError, match="renewal_mandate_one_donation_per_user"),
        transaction.atomic(),
    ):
        donation(member)


def test_a_mandate_waits_on_one_scheduled_charge_at_a_time(friend: User, today: date) -> None:
    """A mandate may carry only one ``scheduled`` attempt at a time."""
    mandate = donation(friend)
    RenewalAttempt.objects.create(mandate=mandate, scheduled_on=today)

    with (
        pytest.raises(IntegrityError, match="renewal_attempt_one_scheduled_per_mandate"),
        transaction.atomic(),
    ):
        RenewalAttempt.objects.create(mandate=mandate, scheduled_on=today + timedelta(days=1))


def test_a_mandate_is_yearly_unless_told_otherwise(
    member: User, annual_plan: MembershipPlan
) -> None:
    """``cadence`` defaults to yearly, which is what every renewal is."""
    assert RenewalMandateFactory(user=member, plan=annual_plan).cadence == MandateCadence.YEARLY


# --------------------------------------------------------------------------
# The schedule
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("day", "cadence", "expected"),
    [
        (date(2026, 1, 31), MandateCadence.MONTHLY, date(2026, 2, 28)),
        (date(2026, 3, 15), MandateCadence.MONTHLY, date(2026, 4, 15)),
        (date(2026, 12, 10), MandateCadence.MONTHLY, date(2027, 1, 10)),
        (date(2026, 1, 15), MandateCadence.QUARTERLY, date(2026, 4, 15)),
        (date(2026, 11, 30), MandateCadence.QUARTERLY, date(2027, 2, 28)),
        (date(2026, 3, 3), MandateCadence.YEARLY, date(2027, 3, 3)),
        (date(2028, 2, 29), MandateCadence.YEARLY, date(2029, 2, 28)),
    ],
    ids=[
        "monthly-clamps-to-february",
        "monthly-keeps-the-day",
        "monthly-crosses-the-year",
        "quarterly-keeps-the-day",
        "quarterly-clamps-across-the-year",
        "yearly-keeps-the-day",
        "yearly-leap-day",
    ],
)
def test_the_next_charge_moves_on_by_the_cadence(day: date, cadence: str, expected: date) -> None:
    """A cadence adds one, three or twelve months, clamped to a shorter month's end."""
    assert advance_by_cadence(day, cadence) == expected


# --------------------------------------------------------------------------
# What may be set up
# --------------------------------------------------------------------------
def test_a_donation_needs_an_amount(member: User) -> None:
    """A standing authority over nothing is refused, naming ``auto_renew``."""
    with pytest.raises(DomainValidationError, match="A recurring donation needs an amount"):
        check_renewable(None, MandateProvider.MOCK, user=member, contribution_cents=0)


def test_a_friend_with_no_term_may_hold_a_donation(friend: User) -> None:
    """A donation accompanies no membership, so any account may give on a schedule."""
    assert (
        check_renewable(None, MandateProvider.MOCK, user=friend, contribution_cents=GIFT_CENTS)
        is None
    )


# --------------------------------------------------------------------------
# The scan
# --------------------------------------------------------------------------
def test_a_monthly_donation_due_today_is_charged(friend: User, today: date) -> None:
    """The charge is the donation alone, for a friend who holds no term at all."""
    donation(friend, next_charge_on=today)

    run_auto_renewals(today=today)

    payment = Payment.objects.get(user=friend)
    assert payment.contribution_cents == GIFT_CENTS


def test_a_donation_attempt_names_no_term(friend: User, today: date) -> None:
    """There is no membership behind a donation, so the attempt carries none."""
    mandate = donation(friend, next_charge_on=today)

    run_auto_renewals(today=today)

    assert mandate.attempts.get().membership_id is None


def test_a_monthly_donation_moves_on_a_month_after_its_charge(friend: User, today: date) -> None:
    """The next charge falls one month after the day the charge was scheduled for."""
    mandate = donation(friend, next_charge_on=today)

    run_auto_renewals(today=today)

    mandate.refresh_from_db()
    assert mandate.next_charge_on == advance_by_cadence(today, MandateCadence.MONTHLY)


def test_a_monthly_donation_sends_only_the_charged_email(
    friend: User, today: date, mailoutbox: list[EmailMessage]
) -> None:
    """No advance notice goes out for a monthly charge; the receipt is the one message."""
    donation(friend, next_charge_on=today)

    run_auto_renewals(today=today)

    assert [str(message.subject) for message in mailoutbox] == [
        "CalDART: thank you for your recurring donation"
    ]


def test_a_quarterly_donation_a_fortnight_out_is_not_announced(
    friend: User, today: date, mailoutbox: list[EmailMessage]
) -> None:
    """A quarterly charge inside the notice window writes nothing and sends nothing."""
    donation(friend, cadence=MandateCadence.QUARTERLY, next_charge_on=today + timedelta(days=5))

    run = run_auto_renewals(today=today)

    assert run.noticed == 0
    assert RenewalAttempt.objects.count() == 0
    assert mailoutbox == []


def test_a_yearly_donation_is_announced_a_fortnight_ahead(
    friend: User, today: date, mailoutbox: list[EmailMessage]
) -> None:
    """A yearly donation keeps the advance notice every yearly charge gets."""
    due = today + timedelta(days=NOTICE_DAYS)
    donation(friend, cadence=MandateCadence.YEARLY, next_charge_on=due)

    run_auto_renewals(today=today)

    assert str(mailoutbox[-1].subject) == (
        f"CalDART: we will take your recurring donation on {due}"
    )


def test_a_rehearsal_reports_a_monthly_charge_due_today(friend: User, today: date) -> None:
    """A dry run counts the charge it would take, and writes no attempt."""
    donation(friend, next_charge_on=today)

    run = run_auto_renewals(today=today, dry_run=True)

    assert run.charged == 1


def test_a_rehearsal_writes_no_donation_attempt(friend: User, today: date) -> None:
    """Nothing is written by a dry run, however due the charge."""
    donation(friend, next_charge_on=today)

    run_auto_renewals(today=today, dry_run=True)

    assert RenewalAttempt.objects.count() == 0


def test_a_declined_donation_is_retried(friend: User, today: date) -> None:
    """The retry ladder applies to a donation exactly as it does to a renewal."""
    mandate = donation(
        friend, next_charge_on=today, method_last4=DECLINED_LAST4, method_label="Declined"
    )

    run_auto_renewals(today=today)

    assert mandate.attempts.filter(outcome=RenewalOutcome.SCHEDULED).count() == 1


def test_a_renewal_held_by_a_friend_is_skipped(
    friend: User, annual_plan: MembershipPlan, today: date
) -> None:
    """A friend pays no dues, so a renewal they still hold charges nothing."""
    current_term(friend, annual_plan, today)
    RenewalMandateFactory(user=friend, plan=annual_plan, next_charge_on=today)

    run = run_auto_renewals(today=today)

    assert run.skipped_by_reason == {"friend": 1}


def test_a_life_member_donation_is_charged_on_its_day(
    member: User, life_plan: MembershipPlan, today: date
) -> None:
    """A life member's yearly gift is a recurring donation like any other."""
    MembershipFactory(user=member, plan=life_plan, starts_on=today, ends_on=None)
    donation(member, cadence=MandateCadence.YEARLY, next_charge_on=today)

    run_auto_renewals(today=today)

    assert Payment.objects.get(user=member).plan_id is None


def test_a_donation_does_not_stop_the_renewal_reminders(
    member: User, annual_plan: MembershipPlan, today: date, mailoutbox: list[EmailMessage]
) -> None:
    """Only a mandate that renews a plan covers a member's renewal reminders."""
    MembershipFactory(
        user=member,
        plan=annual_plan,
        starts_on=today - timedelta(days=358),
        ends_on=today + timedelta(days=7),
        status=MembershipStatusChoices.ACTIVE,
    )
    donation(member, next_charge_on=today + timedelta(days=20))

    send_renewal_reminders(today=today)

    assert len(mailoutbox) == 1


# --------------------------------------------------------------------------
# /me/donation
# --------------------------------------------------------------------------
def test_a_member_with_no_donation_reads_null(member_client: APIClient) -> None:
    """``GET /me/donation`` answers the envelope with a null mandate."""
    assert member_client.get(DONATION).json() == {"mandate": None}


def test_the_donation_endpoint_reads_the_donation(
    member_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A member holding both reads the mandate with no plan from ``/me/donation``."""
    RenewalMandateFactory(user=member, plan=annual_plan)
    held = donation(member)

    assert member_client.get(DONATION).json()["mandate"]["id"] == held.pk


def test_the_renewal_endpoint_reads_the_renewal(
    member_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A member holding both reads the mandate with a plan from ``/me/renewal``."""
    held = RenewalMandateFactory(user=member, plan=annual_plan)
    donation(member)

    assert member_client.get(RENEWAL).json()["mandate"]["id"] == held.pk


def test_a_mandate_reports_its_cadence(member_client: APIClient, member: User) -> None:
    """The payload carries the cadence the donation charges on."""
    donation(member)

    assert member_client.get(DONATION).json()["mandate"]["cadence"] == "monthly"


def test_donation_setup_saves_a_pending_donation(
    member_client: APIClient, member: User, today: date
) -> None:
    """Setup writes a pending mandate with no plan, on the cadence and day asked for."""
    later = today + timedelta(days=10)

    member_client.post(DONATION_SETUP, donation_setup_body(next_charge_on=later.isoformat()))

    mandate = RenewalMandate.objects.get(user=member)
    assert (mandate.plan_id, mandate.cadence, mandate.next_charge_on, mandate.status) == (
        None,
        MandateCadence.QUARTERLY,
        later,
        MandateStatus.PENDING,
    )


def test_donation_setup_without_a_day_charges_from_today(
    member_client: APIClient, member: User, today: date
) -> None:
    """Left out, the first charge falls on the day of the setup."""
    member_client.post(DONATION_SETUP, donation_setup_body())

    assert RenewalMandate.objects.get(user=member).next_charge_on == today


def test_donation_confirm_makes_the_donation_active(member_client: APIClient, member: User) -> None:
    """Confirming the saved method turns the donation on."""
    member_client.post(DONATION_SETUP, donation_setup_body())

    body = member_client.post(DONATION_CONFIRM, {}).json()

    assert body["mandate"]["status"] == MandateStatus.ACTIVE


def test_donation_confirm_leaves_a_pending_renewal_alone(
    member_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The donation confirm finds the donation, never the member's renewal."""
    renewal = RenewalMandateFactory(user=member, plan=annual_plan, status=MandateStatus.PENDING)
    member_client.post(DONATION_SETUP, donation_setup_body())

    member_client.post(DONATION_CONFIRM, {})

    renewal.refresh_from_db()
    assert renewal.status == MandateStatus.PENDING


def test_donation_setup_refuses_nothing_to_give(member_client: APIClient) -> None:
    """A donation of nothing is a 400 naming ``auto_renew``."""
    response = member_client.post(DONATION_SETUP, donation_setup_body(contribution_cents=0))

    assert response.json() == {"auto_renew": ["A recurring donation needs an amount to give."]}


def test_patching_a_donation_changes_amount_cadence_and_day(
    member_client: APIClient, member: User, today: date
) -> None:
    """``PATCH /me/donation`` takes the amount, the cadence and the next day together."""
    mandate = donation(member)
    later = today + timedelta(days=40)

    member_client.patch(
        DONATION,
        {"contribution_cents": 9_000, "cadence": "yearly", "next_charge_on": later.isoformat()},
        format="json",
    )

    mandate.refresh_from_db()
    assert (mandate.contribution_cents, mandate.cadence, mandate.next_charge_on) == (
        9_000,
        MandateCadence.YEARLY,
        later,
    )


def test_deleting_the_donation_leaves_the_renewal_on(
    member_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """``DELETE /me/donation`` turns the donation off and nothing else."""
    renewal = RenewalMandateFactory(user=member, plan=annual_plan)
    donation(member)

    member_client.delete(DONATION)

    renewal.refresh_from_db()
    assert renewal.status == MandateStatus.ACTIVE


def test_deleting_the_donation_turns_it_off(member_client: APIClient, member: User) -> None:
    """The donation itself is canceled."""
    mandate = donation(member)

    member_client.delete(DONATION)

    mandate.refresh_from_db()
    assert mandate.status == MandateStatus.CANCELED


def test_turning_a_donation_off_says_so_in_its_own_words(
    member_client: APIClient,
    member: User,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: CaptureOnCommit,
) -> None:
    """The message names a recurring donation, not a renewal or a contribution."""
    donation(member)

    with django_capture_on_commit_callbacks(execute=True):
        member_client.delete(DONATION)

    assert str(mailoutbox[-1].subject) == "CalDART: your recurring donation is off"


# --------------------------------------------------------------------------
# A renewal is always yearly
# --------------------------------------------------------------------------
def test_a_renewal_setup_refuses_any_cadence_but_yearly(
    member_client: APIClient, annual_plan: MembershipPlan
) -> None:
    """Dues are charged once a year, so a monthly renewal is a 400 naming ``cadence``."""
    response = member_client.post(
        RENEWAL_SETUP,
        {"plan": "annual", "provider": MandateProvider.MOCK, "cadence": "monthly"},
        format="json",
    )

    assert response.json() == {"cadence": ["Automatic renewal is charged once a year."]}


def test_a_renewal_patch_refuses_any_cadence_but_yearly(
    member_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The same refusal applies to a change."""
    RenewalMandateFactory(user=member, plan=annual_plan)

    response = member_client.patch(
        RENEWAL, {"contribution_cents": 0, "cadence": "quarterly"}, format="json"
    )

    assert response.json() == {"cadence": ["Automatic renewal is charged once a year."]}


def test_a_renewal_setup_needs_a_plan(member_client: APIClient) -> None:
    """``/me/renewal/setup`` with no plan is refused: a donation has its own endpoint."""
    response = member_client.post(
        RENEWAL_SETUP, {"contribution_cents": GIFT_CENTS, "provider": MandateProvider.MOCK}
    )

    assert response.json() == {
        "auto_renew": ["Automatic renewal needs a membership plan to renew."]
    }


def test_a_checkout_for_a_plan_refuses_a_monthly_renewal(
    member_client: APIClient, annual_plan: MembershipPlan
) -> None:
    """A checkout that buys a plan and asks for a monthly authority is a 400."""
    response = member_client.post(
        CHECKOUT,
        {"plan": "annual", "provider": "mock", "auto_renew": True, "cadence": "monthly"},
        format="json",
    )

    assert response.json() == {"cadence": ["Automatic renewal is charged once a year."]}


# --------------------------------------------------------------------------
# A checkout that starts a donation
# --------------------------------------------------------------------------
def give_monthly(client: APIClient, **overrides: object) -> dict[str, object]:
    """Start a monthly donation checkout with the mock provider and pay it."""
    body: dict[str, object] = {
        "contribution_cents": GIFT_CENTS,
        "provider": "mock",
        "auto_renew": True,
        "cadence": "monthly",
    }
    body.update(overrides)
    response = client.post(CHECKOUT, body, format="json")
    if response.status_code != 201:
        return dict(response.json())
    client.post(MOCK_COMPLETE, {"payment_id": response.json()["payment_id"]}, format="json")
    return {}


def test_a_donation_checkout_charges_today_and_schedules_the_next(
    member_client: APIClient, member: User, today: date
) -> None:
    """The first gift is taken now, and the donation next charges a month on."""
    give_monthly(member_client)

    mandate = RenewalMandate.objects.get(user=member)
    assert (mandate.status, mandate.next_charge_on) == (
        MandateStatus.ACTIVE,
        advance_by_cadence(today, MandateCadence.MONTHLY),
    )


def test_a_donation_checkout_is_open_to_a_friend(
    api_client: APIClient, friend: User, today: date
) -> None:
    """A friend with no term may start a recurring donation at checkout."""
    api_client.force_login(friend)

    give_monthly(api_client)

    assert RenewalMandate.objects.get(user=friend).cadence == MandateCadence.MONTHLY


# --------------------------------------------------------------------------
# One contribution, one place
# --------------------------------------------------------------------------
def test_a_donation_beside_a_contributing_renewal_is_refused(
    member_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """Setup answers the sentence and the code the portal offers to continue from."""
    RenewalMandateFactory(user=member, plan=annual_plan, contribution_cents=2_000)

    response = member_client.post(DONATION_SETUP, donation_setup_body())

    assert response.json() == {
        "detail": RENEWAL_CONTRIBUTION_MESSAGE,
        "code": "renewal_contribution",
    }


def test_a_donation_checkout_beside_a_contributing_renewal_is_refused(
    member_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A checkout that would start the donation is refused the same way."""
    RenewalMandateFactory(user=member, plan=annual_plan, contribution_cents=2_000)

    assert give_monthly(member_client)["code"] == "renewal_contribution"


def test_a_refused_donation_checkout_leaves_no_payment(
    member_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The pending payment is thrown away with the refusal."""
    RenewalMandateFactory(user=member, plan=annual_plan, contribution_cents=2_000)

    give_monthly(member_client)

    assert Payment.objects.filter(user=member).count() == 0


def test_continuing_moves_the_contribution_off_the_renewal(
    member_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """``remove_renewal_contribution`` zeroes the renewal's contribution first."""
    renewal = RenewalMandateFactory(user=member, plan=annual_plan, contribution_cents=2_000)

    member_client.post(DONATION_SETUP, donation_setup_body(remove_renewal_contribution=True))

    renewal.refresh_from_db()
    assert renewal.contribution_cents == 0


def test_continuing_records_the_change_to_the_renewal(
    member_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """The renewal's lost contribution is written down as ``renewal.change``."""
    RenewalMandateFactory(user=member, plan=annual_plan, contribution_cents=2_000)

    member_client.post(DONATION_SETUP, donation_setup_body(remove_renewal_contribution=True))

    assert any("action=renewal.change" in line for line in audit_messages(audit_log))


def test_continuing_at_checkout_starts_the_donation(
    member_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """With the flag the checkout goes through and the donation is on."""
    RenewalMandateFactory(user=member, plan=annual_plan, contribution_cents=2_000)

    give_monthly(member_client, remove_renewal_contribution=True)

    assert RenewalMandate.objects.get(user=member, plan__isnull=True).status == (
        MandateStatus.ACTIVE
    )


def refuse_to_start(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the mock provider refuse to start a payment or a saved method."""

    def refuse(self: MockProvider, target: object) -> dict[str, object]:
        """Refuse, as a provider that will not start does."""
        raise PaymentError("The provider refused to start.")

    monkeypatch.setattr(MockProvider, "start", refuse)
    monkeypatch.setattr(MockProvider, "start_mandate", refuse)


def test_a_setup_the_provider_refuses_leaves_the_renewal_contribution(
    member_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nothing moves off the renewal when the donation's method cannot be started."""
    renewal = RenewalMandateFactory(user=member, plan=annual_plan, contribution_cents=2_000)
    refuse_to_start(monkeypatch)

    member_client.post(DONATION_SETUP, donation_setup_body(remove_renewal_contribution=True))

    renewal.refresh_from_db()
    assert renewal.contribution_cents == 2_000


def test_a_checkout_the_provider_refuses_leaves_the_renewal_contribution(
    member_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nothing moves off the renewal when the donation's first payment cannot start."""
    renewal = RenewalMandateFactory(user=member, plan=annual_plan, contribution_cents=2_000)
    refuse_to_start(monkeypatch)

    give_monthly(member_client, remove_renewal_contribution=True)

    renewal.refresh_from_db()
    assert renewal.contribution_cents == 2_000


def test_a_checkout_the_provider_refuses_leaves_the_donation_on(
    member_client: APIClient, member: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A donation already giving stays active when a new one cannot be started."""
    held = donation(member, cadence=MandateCadence.YEARLY)
    refuse_to_start(monkeypatch)

    give_monthly(member_client)

    held.refresh_from_db()
    assert held.status == MandateStatus.ACTIVE


def test_a_canceled_renewal_contributes_nothing_to_move(
    member_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A renewal that is off takes no contribution, so the donation starts at once."""
    RenewalMandateFactory(
        user=member, plan=annual_plan, contribution_cents=2_000, status=MandateStatus.CANCELED
    )

    response = member_client.post(DONATION_SETUP, donation_setup_body())

    assert response.status_code == 200


def test_a_renewal_contribution_beside_a_donation_is_refused(
    member_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """``PATCH /me/renewal`` refuses to add a contribution while a donation is held."""
    RenewalMandateFactory(user=member, plan=annual_plan)
    donation(member)

    response = member_client.patch(RENEWAL, {"contribution_cents": 1_000}, format="json")

    assert response.json() == {"contribution_cents": [HAS_DONATION_MESSAGE]}


def test_a_renewal_without_a_contribution_beside_a_donation_saves(
    member_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A renewal of the dues alone is fine beside a donation."""
    RenewalMandateFactory(user=member, plan=annual_plan)
    donation(member)

    response = member_client.patch(RENEWAL, {"contribution_cents": 0}, format="json")

    assert response.status_code == 200


def test_a_renewal_setup_with_a_contribution_beside_a_donation_is_refused(
    member_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """Turning a contributing renewal on beside a donation is refused the same way."""
    donation(member)

    response = member_client.post(
        RENEWAL_SETUP,
        {"plan": "annual", "contribution_cents": 1_000, "provider": MandateProvider.MOCK},
        format="json",
    )

    assert response.json() == {"contribution_cents": [HAS_DONATION_MESSAGE]}


# --------------------------------------------------------------------------
# The finance list
# --------------------------------------------------------------------------
def test_the_finance_list_narrows_to_donations(
    treasurer_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """``?kind=contribution`` answers the recurring donations alone."""
    RenewalMandateFactory(user=member, plan=annual_plan)
    held = donation(member)

    rows = treasurer_client.get(ADMIN, {"kind": "contribution"}).json()["results"]

    assert [row["id"] for row in rows] == [held.pk]


def test_the_finance_list_narrows_to_renewals_with_a_contribution(
    treasurer_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """``?kind=both`` answers the renewals that also take a contribution."""
    held = RenewalMandateFactory(user=member, plan=annual_plan, contribution_cents=500)
    donation(member)

    rows = treasurer_client.get(ADMIN, {"kind": "both"}).json()["results"]

    assert [row["id"] for row in rows] == [held.pk]


def test_the_finance_list_refuses_an_unknown_kind(treasurer_client: APIClient) -> None:
    """A kind outside the three is a 400 naming ``kind``."""
    response = treasurer_client.get(ADMIN, {"kind": "gift"})

    assert response.json() == {"kind": ["Unknown kind 'gift'."]}


def test_charging_a_donation_leaves_the_membership_alone(
    member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """A donation charged beside a current term buys no further term."""
    current_term(member, annual_plan, today)
    donation(member, next_charge_on=today)

    run_auto_renewals(today=today)

    assert member.memberships.count() == 1


def test_a_donation_due_is_charged_even_when_already_behind(friend: User, today: date) -> None:
    """A charge day the scanner missed is taken on the next scan."""
    donation(friend, next_charge_on=today - timedelta(days=3))

    run_auto_renewals(today=today)

    assert Payment.objects.filter(user=friend).count() == 1


def test_a_late_charge_sets_the_schedule_from_the_day_it_was_taken(
    friend: User, today: date
) -> None:
    """A charge the scanner took late is scheduled today, and the next follows from it."""
    missed = today - timedelta(days=3)
    mandate = donation(friend, next_charge_on=missed)

    run_auto_renewals(today=today)

    mandate.refresh_from_db()
    assert mandate.next_charge_on == advance_by_cadence(today, MandateCadence.MONTHLY)


def test_a_paused_donation_charges_nothing(friend: User, today: date) -> None:
    """Only an active donation is charged."""
    donation(friend, next_charge_on=today, status=MandateStatus.PAUSED)

    run_auto_renewals(today=today)

    assert not Payment.objects.filter(user=friend).exists()


def test_the_scan_leaves_a_charged_donation_alone_the_same_day(friend: User, today: date) -> None:
    """A second scan the same day takes nothing more."""
    donation(friend, next_charge_on=today)

    run_auto_renewals(today=today)
    run_auto_renewals(today=today)

    assert Payment.objects.filter(user=friend).count() == 1


def test_a_scan_that_loses_the_race_to_schedule_a_charge_takes_it_once(
    friend: User, today: date, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Another scan writes the attempt between this one's look and write: one charge."""
    donation(friend, next_charge_on=today)
    charge_date = renewals.charge_date

    def racing_charge_date(mandate: RenewalMandate, day: date | None = None) -> date | None:
        """Write the attempt as a concurrent scan would, then answer as usual."""
        if not RenewalAttempt.objects.exists():
            RenewalAttempt.objects.create(mandate=mandate, scheduled_on=today)
        return charge_date(mandate, day)

    monkeypatch.setattr(renewals, "charge_date", racing_charge_date)

    run_auto_renewals(today=today)

    assert Payment.objects.filter(user=friend).count() == 1


def _stale_duplicate(friend: User, today: date) -> None:
    """A monthly donation charged today, with a second attempt for today left behind."""
    mandate = donation(friend, next_charge_on=advance_by_cadence(today, MandateCadence.MONTHLY))
    RenewalAttempt.objects.create(
        mandate=mandate, scheduled_on=today, outcome=RenewalOutcome.SUCCEEDED
    )
    RenewalAttempt.objects.create(mandate=mandate, scheduled_on=today)


def test_an_attempt_for_a_charge_already_taken_is_skipped(friend: User, today: date) -> None:
    """An attempt for a day already charged is skipped as ``already_charged``."""
    _stale_duplicate(friend, today)

    run = run_auto_renewals(today=today)

    assert run.skipped_by_reason == {"already_charged": 1}


def test_an_attempt_for_a_charge_already_taken_takes_no_payment(friend: User, today: date) -> None:
    """The giver is not charged a second time for the same day."""
    _stale_duplicate(friend, today)

    run_auto_renewals(today=today)

    assert Payment.objects.filter(user=friend).count() == 0


def test_a_donation_charge_carries_its_receipt(
    friend: User, today: date, mailoutbox: list[EmailMessage]
) -> None:
    """The charged email attaches the receipt, as every charge's email does."""
    donation(friend, next_charge_on=today)

    run_auto_renewals(today=today)

    assert len(mailoutbox[-1].attachments) == 1


def test_clock_today_is_what_the_default_run_uses(friend: User) -> None:
    """A run with no ``today`` charges a donation due on the local date."""
    donation(friend, next_charge_on=timezone.localdate())

    run_auto_renewals()

    assert Payment.objects.filter(user=friend).count() == 1


# --------------------------------------------------------------------------
# The emails and the seed
# --------------------------------------------------------------------------
def test_a_monthly_donation_is_confirmed_in_its_own_cadence(
    member_client: APIClient,
    django_capture_on_commit_callbacks: CaptureOnCommit,
    mailoutbox: list[EmailMessage],
) -> None:
    """The email that confirms a monthly donation says it gives each month."""
    member_client.post(DONATION_SETUP, donation_setup_body(cadence=MandateCadence.MONTHLY))

    with django_capture_on_commit_callbacks(execute=True):
        member_client.post(DONATION_CONFIRM, {})

    assert "each month" in str(mailoutbox[-1].body)


@pytest.mark.slow
def test_the_seed_leaves_one_monthly_donation_nine_days_out(today: date) -> None:
    """One member gives $25.00 each month, next charged nine days out, with no renewal."""
    call_command("seed_demo", stdout=StringIO())

    monthly = RenewalMandate.objects.get(plan__isnull=True, cadence=MandateCadence.MONTHLY)
    assert monthly.status == MandateStatus.ACTIVE
    assert monthly.contribution_cents == GIFT_CENTS
    assert monthly.next_charge_on == today + timedelta(days=9)
    assert not RenewalMandate.objects.filter(user=monthly.user, plan__isnull=False).exists()


@pytest.mark.slow
def test_the_seed_gives_the_account_administrator_a_yearly_donation() -> None:
    """The account administrator, a life member, gives by a yearly recurring donation."""
    call_command("seed_demo", stdout=StringIO())

    held = RenewalMandate.objects.get(user__email="accountadmin@example.org")
    assert held.plan_id is None
    assert held.cadence == MandateCadence.YEARLY
