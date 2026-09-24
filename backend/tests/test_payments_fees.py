"""What a payment cost: the provider's fee, the net, and asking again later.

Each provider reports its fee somewhere different -- Stripe on the charge's
balance transaction, PayPal in the capture's seller receivable breakdown, the
mock provider by arithmetic -- and all three end up in the same two columns.
These tests cover the arithmetic, the defaults, and ``backfill_fees``; the
provider-specific parsing is exercised against real payloads in
``test_payments_stripe.py`` and ``test_payments_paypal.py``.
"""

from __future__ import annotations

import pytest
from pytest_django.fixtures import Settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.members.models import MembershipPlan
from apps.payments.models import Payment, PaymentProvider, PaymentStatus, PaymentWallet
from apps.payments.providers.mock import fee_cents, fees_for
from apps.payments.services import (
    backfill_fees,
    create_checkout,
    fees_are_known,
    mark_succeeded,
    record_fees,
)
from tests.factories import PaymentFactory

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _mock_enabled(settings: Settings) -> None:
    """Enable the mock provider, which every test here charges through."""
    settings.PAYMENTS_MOCK_ENABLED = True


# --------------------------------------------------------------------------
# the mock provider's fee
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("amount_cents", "expected"),
    [(0, 0), (100, 33), (4_500, 161), (14_500, 451), (65_000, 1_915)],
    ids=["nothing", "a dollar", "annual dues", "dues plus a hundred", "a life membership"],
)
def test_the_mock_fee_is_two_point_nine_percent_plus_thirty_cents(
    amount_cents: int, expected: int
) -> None:
    """The mock provider charges a card-shaped fee, and nothing on nothing."""
    assert fee_cents(amount_cents) == expected


def test_the_mock_net_is_the_amount_less_the_fee(member: User, annual_plan: MembershipPlan) -> None:
    """What the mock provider pays across is the charge less what it kept."""
    payment = create_checkout(member, "annual", 10_000, PaymentProvider.MOCK)

    fees = fees_for(payment)

    assert fees.net_cents == payment.amount_cents - fees.fee_cents


def test_a_mock_checkout_records_the_fee_and_the_net(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """Completing a mock payment stores the fee it would have cost."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.MOCK)
    api_client.force_login(member)

    api_client.post("/api/v1/payments/mock/complete", {"payment_id": payment.pk})

    payment.refresh_from_db()
    assert payment.fee_cents == 161
    assert payment.net_cents == 4_339


# --------------------------------------------------------------------------
# what mark_succeeded stores
# --------------------------------------------------------------------------
def test_a_provider_that_reports_both_figures_is_believed(
    member: User, annual_plan: MembershipPlan
) -> None:
    """A fee and a net that do not add up to the amount are stored as reported."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)

    mark_succeeded(payment, fee_cents=200, net_cents=4_250)

    payment.refresh_from_db()
    assert payment.fee_cents == 200
    assert payment.net_cents == 4_250


def test_a_provider_that_reports_only_a_fee_has_its_net_computed(
    member: User, annual_plan: MembershipPlan
) -> None:
    """A fee without a net nets the amount less that fee."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)

    mark_succeeded(payment, fee_cents=161)

    payment.refresh_from_db()
    assert payment.net_cents == 4_339


def test_a_payment_recorded_by_hand_costs_nothing_and_nets_the_whole_amount(
    member: User, annual_plan: MembershipPlan
) -> None:
    """A check carries no provider fee, so its net is the amount on it."""
    payment = PaymentFactory(
        user=member,
        plan=annual_plan,
        provider=PaymentProvider.MANUAL,
        wallet=PaymentWallet.CHECK,
        provider_ref="",
    )

    mark_succeeded(payment)

    payment.refresh_from_db()
    assert payment.fee_cents == 0
    assert payment.net_cents == payment.amount_cents


def test_a_provider_that_has_not_settled_leaves_the_fee_unknown(
    member: User, annual_plan: MembershipPlan
) -> None:
    """A succeeded payment with no figures from the provider reads as unknown."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)

    mark_succeeded(payment)

    payment.refresh_from_db()
    assert fees_are_known(payment) is False


def test_a_recorded_fee_is_known(member: User, annual_plan: MembershipPlan) -> None:
    """A payment whose provider reported its net has a fee we can report."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    mark_succeeded(payment, fee_cents=161)

    payment.refresh_from_db()
    assert fees_are_known(payment) is True


def test_record_fees_fills_in_a_fee_that_arrived_late(
    member: User, annual_plan: MembershipPlan
) -> None:
    """A fee the provider reports afterwards lands on the payment unchanged."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    mark_succeeded(payment)

    record_fees(payment, fee_cents=161, net_cents=4_339)

    payment.refresh_from_db()
    assert payment.fee_cents == 161


def test_record_fees_changes_nothing_else_about_the_payment(
    member: User, annual_plan: MembershipPlan
) -> None:
    """Filing a fee leaves the payment succeeded and its reference alone."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    payment.provider_ref = "pi_test_late"
    payment.save(update_fields=["provider_ref"])
    mark_succeeded(payment)

    updated = record_fees(payment, fee_cents=161, net_cents=4_339)

    assert updated.provider_ref == "pi_test_late"


# --------------------------------------------------------------------------
# backfill_fees
# --------------------------------------------------------------------------
def test_backfill_asks_the_provider_and_stores_what_it_says(
    member: User, annual_plan: MembershipPlan
) -> None:
    """A payment whose fee was never reported gets it from the provider on demand."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.MOCK)
    mark_succeeded(payment)

    backfill_fees(payment)

    payment.refresh_from_db()
    assert payment.fee_cents == 161


def test_backfill_leaves_a_payment_recorded_by_hand_alone(
    member: User, annual_plan: MembershipPlan
) -> None:
    """There is no provider to ask about a check, so nothing is asked."""
    payment = PaymentFactory(
        user=member,
        plan=annual_plan,
        provider=PaymentProvider.MANUAL,
        wallet=PaymentWallet.CHECK,
        provider_ref="",
        status=PaymentStatus.SUCCEEDED,
    )

    assert backfill_fees(payment).fee_cents == 0


def test_backfill_leaves_a_pending_payment_alone(member: User, annual_plan: MembershipPlan) -> None:
    """A payment that has not succeeded has no fee to ask about."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.MOCK)

    backfill_fees(payment)

    payment.refresh_from_db()
    assert payment.net_cents == 0


def test_a_zero_amount_payment_reads_as_known(member: User) -> None:
    """A payment of nothing has nothing to report, so it is not left waiting."""
    payment = PaymentFactory(
        user=member, plan=None, amount_cents=0, plan_amount_cents=0, contribution_cents=0
    )

    assert fees_are_known(payment) is True


def test_the_fee_columns_survive_a_second_confirmation(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A confirmation that races the first does not reset the fee to nothing."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.MOCK)
    api_client.force_login(member)
    api_client.post("/api/v1/payments/mock/complete", {"payment_id": payment.pk})

    mark_succeeded(Payment.objects.get(pk=payment.pk))

    payment.refresh_from_db()
    assert payment.fee_cents == 161
