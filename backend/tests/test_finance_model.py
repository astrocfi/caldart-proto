"""The finance data model: payment money fields, refunds, mandates and attempts.

Covers what the rows themselves say -- the derived ``kind``, ``paid_on``,
``receipt_number`` and ``refunded_cents`` on a payment, the shape of a refund, a
renewal mandate and a renewal attempt -- and who reaches the finance endpoints
now that they are guarded by ``IsFinance`` rather than by the account
administrator's role alone.
"""

from __future__ import annotations

from datetime import date

import pytest
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import ACCOUNT_ADMIN, SYSTEM_ADMIN, TREASURER
from apps.members.models import MembershipPlan
from apps.payments.models import (
    MandateProvider,
    MandateStatus,
    PaymentKind,
    PaymentProvider,
    PaymentStatus,
    PaymentWallet,
    Refund,
    RefundReason,
    RefundStatus,
    RenewalAttempt,
    RenewalMandate,
    RenewalOutcome,
)
from caldart import audit
from tests.conftest import role_matrix
from tests.factories import (
    MembershipFactory,
    PaymentFactory,
    RefundFactory,
    RenewalAttemptFactory,
    RenewalMandateFactory,
)

pytestmark = pytest.mark.django_db

PAYMENTS_URL = "/api/v1/admin/payments"
MEMBERS_URL = "/api/v1/admin/members"


# --------------------------------------------------------------------------
# What a payment says about itself
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("with_plan", "contribution_cents", "expected"),
    [
        (True, 0, PaymentKind.MEMBERSHIP),
        (False, 2_000, PaymentKind.CONTRIBUTION),
        (True, 2_000, PaymentKind.BOTH),
    ],
)
def test_payment_kind_reads_the_plan_and_the_contribution(
    annual_plan: MembershipPlan, with_plan: bool, contribution_cents: int, expected: str
) -> None:
    """``kind`` is membership, contribution or both, from the plan and the donation."""
    payment = PaymentFactory(
        plan=annual_plan if with_plan else None,
        plan_amount_cents=annual_plan.price_cents if with_plan else 0,
        contribution_cents=contribution_cents,
    )
    assert payment.kind == expected


def test_paid_on_is_the_local_date_the_provider_completed_the_payment() -> None:
    """A provider payment is dated by ``completed_at`` in the local time zone."""
    completed = timezone.now()
    payment = PaymentFactory(status=PaymentStatus.SUCCEEDED, completed_at=completed)
    assert payment.paid_on == timezone.localdate(completed)


def test_paid_on_is_the_day_a_manual_payment_was_received() -> None:
    """A payment recorded by hand is dated by ``received_on``, not by the row's clock."""
    payment = PaymentFactory(
        provider=PaymentProvider.MANUAL,
        wallet=PaymentWallet.CHECK,
        status=PaymentStatus.SUCCEEDED,
        completed_at=timezone.now(),
        received_on=date(2026, 2, 3),
    )
    assert payment.paid_on == date(2026, 2, 3)


def test_paid_on_is_none_while_a_payment_is_still_pending() -> None:
    """A payment nobody has completed has no ledger date at all."""
    assert PaymentFactory(status=PaymentStatus.PENDING, completed_at=None).paid_on is None


def test_receipt_number_pads_the_primary_key_to_six_digits() -> None:
    """The receipt number is ``CALDART-`` and the payment id, zero-padded to six."""
    payment = PaymentFactory()
    assert payment.receipt_number == f"CALDART-{payment.pk:06d}"


def test_refunded_cents_sums_only_the_refunds_that_succeeded() -> None:
    """A pending or failed refund adds nothing to what a payment has given back."""
    payment = PaymentFactory(status=PaymentStatus.SUCCEEDED, amount_cents=10_000)
    RefundFactory(payment=payment, amount_cents=1_500, status=RefundStatus.SUCCEEDED)
    RefundFactory(payment=payment, amount_cents=2_500, status=RefundStatus.SUCCEEDED)
    RefundFactory(payment=payment, amount_cents=9_000, status=RefundStatus.PENDING)
    RefundFactory(payment=payment, amount_cents=9_000, status=RefundStatus.FAILED)
    assert payment.refunded_cents == 4_000


def test_refunded_cents_is_zero_when_nothing_was_given_back() -> None:
    """A payment with no refund rows reports zero rather than ``None``."""
    assert PaymentFactory(status=PaymentStatus.SUCCEEDED).refunded_cents == 0


def test_a_manual_payment_records_who_took_it_and_why(account_admin: User) -> None:
    """A payment recorded by hand keeps the check number and the administrator."""
    payment = PaymentFactory(
        provider=PaymentProvider.MANUAL,
        wallet=PaymentWallet.CHECK,
        status=PaymentStatus.SUCCEEDED,
        received_on=date(2026, 2, 3),
        note="Check 1042",
        recorded_by=account_admin,
    )
    payment.refresh_from_db()
    assert payment.note == "Check 1042"
    assert payment.recorded_by == account_admin


def test_reconciling_a_payment_keeps_the_date_and_the_treasurer(treasurer: User) -> None:
    """A matched payment keeps the day it was matched and the treasurer who did it."""
    payment = PaymentFactory(
        status=PaymentStatus.SUCCEEDED,
        reconciled_on=date(2026, 3, 1),
        reconciled_by=treasurer,
    )
    payment.refresh_from_db()
    assert payment.reconciled_by == treasurer
    assert payment.reconciled_on == date(2026, 3, 1)


def test_a_payment_starts_with_no_fee_and_no_receipt() -> None:
    """Fee, net and the receipt stamp default to nothing until a provider reports them."""
    payment = PaymentFactory()
    assert payment.fee_cents == 0
    assert payment.net_cents == 0
    assert payment.receipt_sent_at is None


def test_a_payment_can_be_stored_as_partially_refunded() -> None:
    """The widest status the column holds survives a round trip to the database."""
    payment = PaymentFactory(
        status=PaymentStatus.PARTIALLY_REFUNDED, amount_cents=10_000, completed_at=timezone.now()
    )
    payment.refresh_from_db()
    assert payment.status == "partially_refunded"


# --------------------------------------------------------------------------
# Refunds
# --------------------------------------------------------------------------
def test_a_refund_is_described_by_its_amount_and_status() -> None:
    """``str`` on a refund reads as the dollar amount and the status in brackets."""
    refund = RefundFactory(amount_cents=2_500, status=RefundStatus.SUCCEEDED)
    assert str(refund) == "Refund $25.00 (succeeded)"


def test_a_refund_defaults_to_pending_with_no_provider_reference() -> None:
    """A refund row starts pending, unsent and with nothing from the provider yet."""
    refund = Refund.objects.create(
        payment=PaymentFactory(status=PaymentStatus.SUCCEEDED),
        amount_cents=1_000,
        reason=RefundReason.REQUESTED_BY_MEMBER,
    )
    assert refund.status == RefundStatus.PENDING
    assert refund.provider_ref == ""
    assert refund.refunded_at is None


def test_refunds_read_back_newest_first() -> None:
    """A payment's refunds come back in reverse creation order."""
    payment = PaymentFactory(status=PaymentStatus.SUCCEEDED, amount_cents=10_000)
    first = RefundFactory(payment=payment, amount_cents=1_000)
    second = RefundFactory(payment=payment, amount_cents=2_000)
    assert list(payment.refunds.all()) == [second, first]


# --------------------------------------------------------------------------
# Renewal mandates
# --------------------------------------------------------------------------
def test_a_mandate_is_described_by_its_member_and_method() -> None:
    """``str`` on a mandate reads as the member, the method label and the status."""
    mandate = RenewalMandateFactory(method_label="Visa ending 4242, expires 03/2028")
    assert str(mandate) == f"{mandate.user} \u00b7 Visa ending 4242, expires 03/2028 (active)"


def test_a_member_holds_at_most_one_mandate() -> None:
    """The mandate is reached from the member as ``renewal_mandate``."""
    mandate = RenewalMandateFactory()
    assert mandate.user.renewal_mandate == mandate


def test_a_new_mandate_is_pending_until_a_payment_activates_it(member: User) -> None:
    """A mandate created at checkout waits at ``pending`` with no charge behind it."""
    mandate = RenewalMandateFactory(user=member, status=MandateStatus.PENDING)
    assert mandate.last_charged_at is None
    assert mandate.failure_count == 0


def test_a_canceled_mandate_records_who_turned_it_off(member: User, treasurer: User) -> None:
    """``canceled_by`` names the member or the administrator who stopped the renewals."""
    canceled_at = timezone.now()
    mandate = RenewalMandateFactory(
        user=member,
        status=MandateStatus.CANCELED,
        canceled_at=canceled_at,
        canceled_by=treasurer,
    )
    mandate.refresh_from_db()
    assert mandate.canceled_by == treasurer


def test_a_mandate_is_never_held_against_a_hand_recorded_payment() -> None:
    """Only a provider that can charge off-session may hold a standing authority."""
    assert MandateProvider.values == ["stripe", "paypal", "mock"]


def test_every_mandate_provider_is_a_payment_provider_under_the_same_label() -> None:
    """``MandateProvider`` is a subset of ``PaymentProvider``, labels included."""
    payment_labels = dict(PaymentProvider.choices)
    assert dict(MandateProvider.choices) == {
        value: payment_labels[value] for value in MandateProvider.values
    }


def test_a_mandate_field_refuses_a_manual_provider(member: User) -> None:
    """Validating a mandate that names ``manual`` reports the provider as invalid."""
    mandate = RenewalMandateFactory(user=member)
    mandate.provider = PaymentProvider.MANUAL
    with pytest.raises(ValidationError) as excinfo:
        mandate.full_clean()
    assert "provider" in excinfo.value.error_dict


def test_a_mandate_carries_its_own_contribution(member: User) -> None:
    """The contribution renewed alongside the dues is kept on the mandate."""
    mandate = RenewalMandateFactory(user=member, contribution_cents=2_000)
    assert mandate.contribution_cents == 2_000


# --------------------------------------------------------------------------
# Renewal attempts
# --------------------------------------------------------------------------
def test_an_attempt_is_described_by_its_date_and_outcome(member: User) -> None:
    """``str`` on an attempt reads as the member, the scheduled day and the outcome."""
    attempt = RenewalAttemptFactory(
        mandate=RenewalMandateFactory(user=member), scheduled_on=date(2026, 6, 1)
    )
    assert str(attempt) == f"{member} \u00b7 2026-06-01 (scheduled)"


def test_a_new_attempt_has_been_neither_noticed_nor_charged() -> None:
    """An attempt starts scheduled, with no payment and none of its emails sent."""
    attempt = RenewalAttemptFactory()
    assert attempt.outcome == RenewalOutcome.SCHEDULED
    assert attempt.payment is None
    assert attempt.noticed_at is None
    assert attempt.attempted_at is None
    assert attempt.result_emailed_at is None


def test_a_retry_points_at_the_attempt_it_retries() -> None:
    """``retry_of`` chains a retry to the failed attempt that caused it."""
    failed = RenewalAttemptFactory(outcome=RenewalOutcome.FAILED, error="Your card was declined")
    retry = RenewalAttemptFactory(mandate=failed.mandate, membership=failed.membership)
    retry.retry_of = failed
    retry.save(update_fields=["retry_of"])
    assert list(failed.retries.all()) == [retry]


def test_an_attempt_belongs_to_the_term_it_renews(
    member: User, annual_plan: MembershipPlan
) -> None:
    """The attempt names the membership whose expiry the charge covers."""
    membership = MembershipFactory(user=member, plan=annual_plan)
    attempt = RenewalAttemptFactory(membership=membership)
    assert attempt.membership == membership


def test_attempts_read_back_newest_first(member: User) -> None:
    """A mandate's attempts come back with the latest scheduled day first."""
    mandate = RenewalMandateFactory(user=member)
    early = RenewalAttemptFactory(mandate=mandate, scheduled_on=date(2026, 1, 1))
    late = RenewalAttemptFactory(mandate=mandate, scheduled_on=date(2026, 6, 1))
    assert list(mandate.attempts.all()) == [late, early]


# --------------------------------------------------------------------------
# The Django admin
# --------------------------------------------------------------------------
@pytest.mark.parametrize("model", [Refund, RenewalMandate, RenewalAttempt])
def test_the_finance_models_are_registered_in_the_django_admin(model: type) -> None:
    """Refunds, mandates and attempts are browsable in the Django admin."""
    assert admin.site.is_registered(model)


# --------------------------------------------------------------------------
# Who reaches the finance endpoints
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("slug", "allowed"), role_matrix(TREASURER, ACCOUNT_ADMIN, SYSTEM_ADMIN))
def test_role_matrix_for_the_payment_list(
    api_client: APIClient, all_role_users: dict[str, User], slug: str, allowed: bool
) -> None:
    """A treasurer reads the payment list; every role but the finance ones gets 403."""
    api_client.force_login(all_role_users[slug])
    assert api_client.get(PAYMENTS_URL).status_code == (200 if allowed else 403)


@pytest.mark.parametrize(("slug", "allowed"), role_matrix(TREASURER, ACCOUNT_ADMIN, SYSTEM_ADMIN))
def test_role_matrix_for_the_payment_summary(
    api_client: APIClient, all_role_users: dict[str, User], slug: str, allowed: bool
) -> None:
    """The period summary follows the same finance rule as the list."""
    api_client.force_login(all_role_users[slug])
    assert api_client.get(f"{PAYMENTS_URL}/summary").status_code == (200 if allowed else 403)


@pytest.mark.parametrize(("slug", "allowed"), role_matrix(TREASURER, ACCOUNT_ADMIN, SYSTEM_ADMIN))
def test_role_matrix_for_the_payment_export(
    api_client: APIClient, all_role_users: dict[str, User], slug: str, allowed: bool
) -> None:
    """The CSV export follows the same finance rule as the list."""
    api_client.force_login(all_role_users[slug])
    assert api_client.get(f"{PAYMENTS_URL}/export.csv").status_code == (200 if allowed else 403)


def test_a_treasurer_does_not_read_the_member_records(treasurer_client: APIClient) -> None:
    """The member list carries medical and certificate data, so finance is refused it."""
    assert treasurer_client.get(MEMBERS_URL).status_code == 403


def test_a_treasurer_reads_the_payment_list(treasurer_client: APIClient) -> None:
    """The signed-in treasurer fixture reaches the payment list itself."""
    assert treasurer_client.get(PAYMENTS_URL).status_code == 200


# --------------------------------------------------------------------------
# The audit actions the finance area writes
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("constant", "action"),
    [
        (audit.PAYMENT_RECORD, "payment.record"),
        (audit.PAYMENT_REFUND, "payment.refund"),
        (audit.PAYMENT_RECONCILE, "payment.reconcile"),
        (audit.PAYMENT_RECEIPT_RESEND, "payment.receipt_resend"),
        (audit.PAYMENT_NOTE, "payment.note"),
        (audit.RENEWAL_ENABLE, "renewal.enable"),
        (audit.RENEWAL_CANCEL, "renewal.cancel"),
        (audit.RENEWALS_RUN, "renewals.run"),
    ],
)
def test_the_finance_audit_actions_are_named_as_the_journal_shows_them(
    constant: str, action: str
) -> None:
    """Each finance action is the dotted slug the deployment guide's table lists."""
    assert constant == action
