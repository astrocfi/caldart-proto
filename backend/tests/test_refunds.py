"""Refunds: the service, the term cancellation, the email and the endpoint.

The provider is the mock one throughout, so no test here reaches a network.  The
Stripe and PayPal halves -- the refund calls and the two dashboard webhooks --
are exercised in ``test_payments_stripe.py`` and ``test_payments_paypal.py``,
which already own the fakes those providers need.
"""

from __future__ import annotations

import logging
import smtplib
from typing import Any

import pytest
from django.core import mail
from pytest_django.fixtures import Settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.members.models import Membership, MembershipPlan, MembershipStatusChoices
from apps.members.services import cancel_term
from apps.payments import refunds as refund_service
from apps.payments.models import (
    Payment,
    PaymentProvider,
    PaymentStatus,
    Refund,
    RefundReason,
    RefundStatus,
)
from apps.payments.providers.base import ProviderUnavailableError
from apps.payments.providers.mock import MockProvider
from caldart import audit
from caldart.exceptions import DomainValidationError
from tests.conftest import role_matrix
from tests.factories import MembershipFactory, PaymentFactory, RefundFactory

pytestmark = pytest.mark.django_db


def refunds_url(payment: Payment) -> str:
    """The endpoint that issues a refund against ``payment``."""
    return f"/api/v1/admin/payments/{payment.pk}/refunds"


@pytest.fixture(autouse=True)
def _mock_enabled(settings: Settings) -> None:
    """Enable the mock provider, which stands in for a real one in every test here."""
    settings.PAYMENTS_MOCK_ENABLED = True


@pytest.fixture
def paid(member: User, annual_plan: MembershipPlan) -> Payment:
    """A succeeded 6,500-cent mock payment: 4,500 of dues and 2,000 of contribution."""
    return PaymentFactory(
        user=member,
        plan=annual_plan,
        amount_cents=6_500,
        plan_amount_cents=4_500,
        contribution_cents=2_000,
        status=PaymentStatus.SUCCEEDED,
        provider=PaymentProvider.MOCK,
    )


# --------------------------------------------------------------------------
# What is left to refund
# --------------------------------------------------------------------------
def test_a_payment_with_no_refunds_has_all_of_it_left(paid: Payment) -> None:
    """Nothing refunded yet means the whole amount is still refundable."""
    assert refund_service.remaining_cents(paid) == 6_500


def test_a_partial_refund_leaves_the_rest(paid: Payment) -> None:
    """A succeeded refund comes off what is left."""
    RefundFactory(payment=paid, amount_cents=2_000)
    assert refund_service.remaining_cents(paid) == 4_500


def test_a_failed_refund_leaves_the_whole_amount(paid: Payment) -> None:
    """A refund the provider refused gave nothing back, so nothing is off the total."""
    RefundFactory(payment=paid, amount_cents=2_000, status=RefundStatus.FAILED)
    assert refund_service.remaining_cents(paid) == 6_500


# --------------------------------------------------------------------------
# Issuing a refund
# --------------------------------------------------------------------------
def test_a_partial_refund_succeeds_and_leaves_the_payment_partially_refunded(
    paid: Payment, account_admin: User
) -> None:
    """Refunding part of a payment marks it ``partially_refunded``."""
    refund = refund_service.issue_refund(
        paid,
        amount_cents=2_000,
        reason=RefundReason.REQUESTED_BY_MEMBER,
        actor=account_admin,
    )

    assert refund.status == RefundStatus.SUCCEEDED
    paid.refresh_from_db()
    assert paid.status == PaymentStatus.PARTIALLY_REFUNDED


def test_a_partial_refund_records_the_amount_and_the_actor(
    paid: Payment, account_admin: User
) -> None:
    """The row carries what was given back and who issued it."""
    refund = refund_service.issue_refund(
        paid,
        amount_cents=2_000,
        reason=RefundReason.DUPLICATE,
        note="Charged twice on the same day",
        actor=account_admin,
    )

    assert refund.amount_cents == 2_000
    assert refund.requested_by == account_admin
    assert refund.note == "Charged twice on the same day"
    assert refund.reason == RefundReason.DUPLICATE


def test_a_refund_of_the_whole_amount_marks_the_payment_refunded(
    paid: Payment, account_admin: User
) -> None:
    """Giving all of it back leaves the payment ``refunded``, not partially so."""
    refund_service.issue_refund(
        paid, amount_cents=6_500, reason=RefundReason.ERROR, actor=account_admin
    )

    paid.refresh_from_db()
    assert paid.status == PaymentStatus.REFUNDED


def test_two_partial_refunds_that_total_the_amount_mark_it_refunded(
    paid: Payment, account_admin: User
) -> None:
    """The status follows the running total, not the size of one refund."""
    refund_service.issue_refund(
        paid, amount_cents=2_000, reason=RefundReason.ERROR, actor=account_admin
    )
    refund_service.issue_refund(
        paid, amount_cents=4_500, reason=RefundReason.ERROR, actor=account_admin
    )

    paid.refresh_from_db()
    assert paid.status == PaymentStatus.REFUNDED


def test_a_succeeded_refund_is_stamped_with_the_time_it_was_taken(
    paid: Payment, account_admin: User
) -> None:
    """``refunded_at`` says when the money went back."""
    refund = refund_service.issue_refund(
        paid, amount_cents=1_000, reason=RefundReason.OTHER, actor=account_admin
    )
    assert refund.refunded_at is not None


def test_the_mock_provider_supplies_its_own_reference(
    paid: Payment, account_admin: User
) -> None:
    """A mock refund carries the reference the mock provider made for it."""
    refund = refund_service.issue_refund(
        paid, amount_cents=1_000, reason=RefundReason.OTHER, actor=account_admin
    )
    assert refund.provider_ref == f"mock_refund_{refund.pk}"


def test_a_manual_payment_is_refunded_without_calling_a_provider(
    member: User, annual_plan: MembershipPlan, account_admin: User
) -> None:
    """A check written back by hand leaves a refund row with no provider reference."""
    payment = PaymentFactory(
        user=member,
        plan=annual_plan,
        status=PaymentStatus.SUCCEEDED,
        provider=PaymentProvider.MANUAL,
        provider_ref="",
    )
    refund = refund_service.issue_refund(
        payment, amount_cents=4_500, reason=RefundReason.ERROR, actor=account_admin
    )

    assert refund.status == RefundStatus.SUCCEEDED
    assert refund.provider_ref == ""


# --------------------------------------------------------------------------
# What a refund refuses
# --------------------------------------------------------------------------
def test_a_refund_of_nothing_is_refused(paid: Payment, account_admin: User) -> None:
    """Zero is not an amount, and the complaint is keyed by ``amount_cents``."""
    with pytest.raises(DomainValidationError, match="more than zero") as caught:
        refund_service.issue_refund(
            paid, amount_cents=0, reason=RefundReason.OTHER, actor=account_admin
        )
    assert caught.value.field == "amount_cents"


def test_a_refund_larger_than_what_is_left_is_refused(
    paid: Payment, account_admin: User
) -> None:
    """The message names what is actually left to give back."""
    RefundFactory(payment=paid, amount_cents=2_000)
    with pytest.raises(DomainValidationError, match=r"\$45\.00") as caught:
        refund_service.issue_refund(
            paid, amount_cents=4_501, reason=RefundReason.OTHER, actor=account_admin
        )
    assert caught.value.field == "amount_cents"


def test_an_over_refund_writes_no_row(paid: Payment, account_admin: User) -> None:
    """A refused refund leaves nothing behind."""
    with pytest.raises(DomainValidationError, match=r"\$65\.00"):
        refund_service.issue_refund(
            paid, amount_cents=7_000, reason=RefundReason.OTHER, actor=account_admin
        )
    assert Refund.objects.count() == 0


def test_a_pending_payment_cannot_be_refunded(
    member: User, annual_plan: MembershipPlan, account_admin: User
) -> None:
    """There is no money to give back until the payment succeeded."""
    pending = PaymentFactory(user=member, plan=annual_plan, status=PaymentStatus.PENDING)
    with pytest.raises(DomainValidationError, match="has not succeeded") as caught:
        refund_service.issue_refund(
            pending, amount_cents=1_000, reason=RefundReason.OTHER, actor=account_admin
        )
    assert caught.value.field == "amount_cents"


def test_a_fully_refunded_payment_cannot_be_refunded_again(
    paid: Payment, account_admin: User
) -> None:
    """Nothing is left, so the second refund is refused by amount."""
    refund_service.issue_refund(
        paid, amount_cents=6_500, reason=RefundReason.ERROR, actor=account_admin
    )
    paid.refresh_from_db()
    with pytest.raises(DomainValidationError, match=r"\$0\.00"):
        refund_service.issue_refund(
            paid, amount_cents=100, reason=RefundReason.OTHER, actor=account_admin
        )


def test_an_unknown_reason_is_refused(paid: Payment, account_admin: User) -> None:
    """The reason must be one of the choices, and the complaint says which field."""
    with pytest.raises(DomainValidationError, match="Unknown refund reason") as caught:
        refund_service.issue_refund(
            paid, amount_cents=100, reason="because", actor=account_admin
        )
    assert caught.value.field == "reason"


# --------------------------------------------------------------------------
# A provider that refuses
# --------------------------------------------------------------------------
def test_a_provider_failure_leaves_a_failed_refund(
    paid: Payment, account_admin: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The row is kept as ``failed`` so the treasurer can see the attempt."""

    def refuse(self: MockProvider, payment: Payment, refund: Refund) -> dict[str, Any]:
        raise ProviderUnavailableError("The provider could not be reached.")

    monkeypatch.setattr(MockProvider, "refund", refuse)

    with pytest.raises(ProviderUnavailableError):
        refund_service.issue_refund(
            paid, amount_cents=1_000, reason=RefundReason.OTHER, actor=account_admin
        )

    assert Refund.objects.get().status == RefundStatus.FAILED


def test_a_provider_failure_leaves_the_payment_succeeded(
    paid: Payment, account_admin: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No money moved, so the payment is not marked refunded in any degree."""

    def refuse(self: MockProvider, payment: Payment, refund: Refund) -> dict[str, Any]:
        raise ProviderUnavailableError("The provider could not be reached.")

    monkeypatch.setattr(MockProvider, "refund", refuse)

    with pytest.raises(ProviderUnavailableError):
        refund_service.issue_refund(
            paid, amount_cents=1_000, reason=RefundReason.OTHER, actor=account_admin
        )

    paid.refresh_from_db()
    assert paid.status == PaymentStatus.SUCCEEDED


# --------------------------------------------------------------------------
# The membership term
# --------------------------------------------------------------------------
def test_cancel_term_marks_the_term_canceled(member: User, annual_plan: MembershipPlan) -> None:
    """A canceled term stops covering the member."""
    term = MembershipFactory(user=member, plan=annual_plan)
    canceled = cancel_term(term, note="Refunded")

    assert canceled.status == MembershipStatusChoices.CANCELED


def test_cancel_term_keeps_the_reason_it_was_given(
    member: User, annual_plan: MembershipPlan
) -> None:
    """The note is what an administrator reads later to see why the term ended."""
    term = MembershipFactory(user=member, plan=annual_plan)
    canceled = cancel_term(term, note="Refunded in full")

    assert canceled.note == "Refunded in full"


def test_cancel_term_keeps_an_existing_note_alongside_the_new_one(
    member: User, annual_plan: MembershipPlan
) -> None:
    """A term that already carried a note keeps it, with the reason appended."""
    term = MembershipFactory(user=member, plan=annual_plan, note="Granted at the airshow")
    canceled = cancel_term(term, note="Refunded in full")

    assert canceled.note == "Granted at the airshow. Refunded in full"


def test_a_refund_can_cancel_the_term_the_payment_bought(
    paid: Payment, member: User, annual_plan: MembershipPlan, account_admin: User
) -> None:
    """``cancel_term`` ends the coverage the refunded payment had bought."""
    term = MembershipFactory(user=member, plan=annual_plan, payment=paid)

    refund = refund_service.issue_refund(
        paid,
        amount_cents=6_500,
        reason=RefundReason.ERROR,
        actor=account_admin,
        cancel_term=True,
    )

    term.refresh_from_db()
    assert term.status == MembershipStatusChoices.CANCELED
    assert str(refund.pk) in term.note


def test_a_refund_leaves_the_term_alone_by_default(
    paid: Payment, member: User, annual_plan: MembershipPlan, account_admin: User
) -> None:
    """Refunding a contribution does not take the membership away."""
    term = MembershipFactory(user=member, plan=annual_plan, payment=paid)

    refund_service.issue_refund(
        paid, amount_cents=2_000, reason=RefundReason.REQUESTED_BY_MEMBER, actor=account_admin
    )

    term.refresh_from_db()
    assert term.status == MembershipStatusChoices.ACTIVE


def test_cancel_term_on_a_payment_that_bought_none_is_harmless(
    member: User, account_admin: User
) -> None:
    """A pure contribution has no term, and asking to cancel one changes nothing."""
    donation = PaymentFactory(
        user=member,
        plan=None,
        amount_cents=2_000,
        plan_amount_cents=0,
        contribution_cents=2_000,
        status=PaymentStatus.SUCCEEDED,
    )
    refund_service.issue_refund(
        donation,
        amount_cents=2_000,
        reason=RefundReason.ERROR,
        actor=account_admin,
        cancel_term=True,
    )

    assert Membership.objects.count() == 0


# --------------------------------------------------------------------------
# The email
# --------------------------------------------------------------------------
def test_a_succeeded_refund_emails_the_member(paid: Payment, account_admin: User) -> None:
    """One message goes to the address on the account."""
    refund_service.issue_refund(
        paid, amount_cents=2_000, reason=RefundReason.REQUESTED_BY_MEMBER, actor=account_admin
    )

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [paid.user.email]


def test_the_refund_email_names_the_amount(paid: Payment, account_admin: User) -> None:
    """The member reads what they are getting back without opening anything."""
    refund_service.issue_refund(
        paid, amount_cents=2_000, reason=RefundReason.REQUESTED_BY_MEMBER, actor=account_admin
    )

    assert "$20.00" in mail.outbox[0].body


def test_the_refund_email_says_the_term_was_canceled(
    paid: Payment, member: User, annual_plan: MembershipPlan, account_admin: User
) -> None:
    """A member whose membership ended with the refund is told so."""
    MembershipFactory(user=member, plan=annual_plan, payment=paid)
    refund_service.issue_refund(
        paid,
        amount_cents=6_500,
        reason=RefundReason.ERROR,
        actor=account_admin,
        cancel_term=True,
    )

    assert "no longer a member" in mail.outbox[0].body


def test_the_refund_email_is_silent_about_a_term_that_stands(
    paid: Payment, member: User, annual_plan: MembershipPlan, account_admin: User
) -> None:
    """A contribution refund leaves the membership, and says nothing about it."""
    MembershipFactory(user=member, plan=annual_plan, payment=paid)
    refund_service.issue_refund(
        paid, amount_cents=2_000, reason=RefundReason.REQUESTED_BY_MEMBER, actor=account_admin
    )

    assert "no longer a member" not in mail.outbox[0].body


def test_a_refused_email_does_not_undo_the_refund(
    paid: Payment, account_admin: User, monkeypatch: pytest.MonkeyPatch, caplog: Any
) -> None:
    """The money is back; a mail server that refuses the notice is logged, not raised."""

    def refuse(**kwargs: Any) -> None:
        raise smtplib.SMTPDataError(451, b"try later")

    monkeypatch.setattr(refund_service, "send_templated", refuse)

    with caplog.at_level(logging.ERROR, logger="apps.payments.refunds"):
        refund = refund_service.issue_refund(
            paid, amount_cents=2_000, reason=RefundReason.OTHER, actor=account_admin
        )

    assert refund.status == RefundStatus.SUCCEEDED
    assert "refund" in caplog.text.lower()


def test_a_failed_refund_emails_nobody(
    paid: Payment, account_admin: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing was given back, so there is nothing to tell the member."""

    def refuse(self: MockProvider, payment: Payment, refund: Refund) -> dict[str, Any]:
        raise ProviderUnavailableError("The provider could not be reached.")

    monkeypatch.setattr(MockProvider, "refund", refuse)

    with pytest.raises(ProviderUnavailableError):
        refund_service.issue_refund(
            paid, amount_cents=1_000, reason=RefundReason.OTHER, actor=account_admin
        )

    assert len(mail.outbox) == 0


# --------------------------------------------------------------------------
# The audit trail
# --------------------------------------------------------------------------
def test_a_refund_is_recorded_in_the_audit_log(
    paid: Payment, account_admin: User, caplog: Any
) -> None:
    """One ``payment.refund`` line names the payment, the amount and the reason."""
    with caplog.at_level(logging.INFO, logger=audit.LOGGER_NAME):
        refund_service.issue_refund(
            paid, amount_cents=2_000, reason=RefundReason.DUPLICATE, actor=account_admin
        )

    lines = [r.message for r in caplog.records if r.message.startswith("action=payment.refund")]
    assert len(lines) == 1
    assert f"target={paid.pk}" in lines[0]
    assert "amount_cents=2000" in lines[0]
    assert "reason=duplicate" in lines[0]


# --------------------------------------------------------------------------
# A refund made in the provider's own dashboard
# --------------------------------------------------------------------------
def test_a_dashboard_refund_is_recorded_against_the_payment(paid: Payment) -> None:
    """The ledger is right even when somebody refunds outside CalDART."""
    refund = refund_service.record_dashboard_refund(
        paid, amount_cents=2_000, provider_ref="re_outside", raw={"id": "re_outside"}
    )

    assert refund is not None
    assert refund.status == RefundStatus.SUCCEEDED
    assert refund.requested_by is None
    assert refund.reason == RefundReason.OTHER
    assert refund.note == refund_service.DASHBOARD_NOTE


def test_a_dashboard_refund_updates_the_payment_status(paid: Payment) -> None:
    """A full refund taken in the dashboard still reads as refunded here."""
    refund_service.record_dashboard_refund(
        paid, amount_cents=6_500, provider_ref="re_outside", raw={}
    )

    paid.refresh_from_db()
    assert paid.status == PaymentStatus.REFUNDED


def test_a_second_delivery_of_a_dashboard_refund_records_nothing(paid: Payment) -> None:
    """The provider's reference is what makes the record idempotent."""
    refund_service.record_dashboard_refund(
        paid, amount_cents=2_000, provider_ref="re_twice", raw={}
    )
    again = refund_service.record_dashboard_refund(
        paid, amount_cents=2_000, provider_ref="re_twice", raw={}
    )

    assert again is None
    assert Refund.objects.count() == 1


def test_a_dashboard_refund_of_one_we_issued_records_nothing(
    paid: Payment, account_admin: User
) -> None:
    """A refund issued here comes back by webhook and must not be counted twice."""
    ours = refund_service.issue_refund(
        paid, amount_cents=2_000, reason=RefundReason.OTHER, actor=account_admin
    )
    again = refund_service.record_dashboard_refund(
        paid, amount_cents=2_000, provider_ref=ours.provider_ref, raw={}
    )

    assert again is None
    assert Refund.objects.count() == 1


def test_a_dashboard_refund_emails_the_member(paid: Payment) -> None:
    """The member hears about it whoever pressed the button."""
    refund_service.record_dashboard_refund(
        paid, amount_cents=2_000, provider_ref="re_mail", raw={}
    )

    assert len(mail.outbox) == 1


def test_a_dashboard_refund_cancels_no_term(
    paid: Payment, member: User, annual_plan: MembershipPlan
) -> None:
    """The treasurer decides about the term; a webhook never does."""
    term = MembershipFactory(user=member, plan=annual_plan, payment=paid)
    refund_service.record_dashboard_refund(
        paid, amount_cents=6_500, provider_ref="re_term", raw={}
    )

    term.refresh_from_db()
    assert term.status == MembershipStatusChoices.ACTIVE


# --------------------------------------------------------------------------
# POST /admin/payments/{id}/refunds
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("role", "allowed"), role_matrix("treasurer", "account_admin"))
def test_only_the_finance_roles_may_issue_a_refund(
    api_client: APIClient,
    all_role_users: dict[str, User],
    paid: Payment,
    role: str,
    allowed: bool,
) -> None:
    """A treasurer and an account administrator refund; every other role is refused."""
    api_client.force_login(all_role_users[role])
    response = api_client.post(
        refunds_url(paid), {"amount_cents": 1_000, "reason": RefundReason.OTHER}
    )

    assert (response.status_code == 201) is allowed


def test_the_system_admin_may_issue_a_refund(
    api_client: APIClient, system_admin: User, paid: Payment
) -> None:
    """A system administrator passes every permission in the project."""
    api_client.force_login(system_admin)
    response = api_client.post(
        refunds_url(paid), {"amount_cents": 1_000, "reason": RefundReason.OTHER}
    )

    assert response.status_code == 201


def test_an_anonymous_caller_is_refused(api_client: APIClient, paid: Payment) -> None:
    """The endpoint is not public."""
    response = api_client.post(
        refunds_url(paid), {"amount_cents": 1_000, "reason": RefundReason.OTHER}
    )
    assert response.status_code == 401


def test_the_response_carries_the_refund(
    treasurer_client: APIClient, paid: Payment
) -> None:
    """The body's ``refund`` is the row just written."""
    response = treasurer_client.post(
        refunds_url(paid),
        {"amount_cents": 2_000, "reason": RefundReason.REQUESTED_BY_MEMBER, "note": "By phone"},
    )

    body = response.json()
    assert body["refund"]["amount_cents"] == 2_000
    assert body["refund"]["status"] == RefundStatus.SUCCEEDED
    assert body["refund"]["note"] == "By phone"


def test_the_response_carries_the_payment_as_it_now_stands(
    treasurer_client: APIClient, paid: Payment
) -> None:
    """The caller needs no second request to redraw the row it refunded."""
    response = treasurer_client.post(
        refunds_url(paid), {"amount_cents": 2_000, "reason": RefundReason.OTHER}
    )

    body = response.json()
    assert body["payment"]["status"] == PaymentStatus.PARTIALLY_REFUNDED
    assert body["payment"]["refunded_cents"] == 2_000


def test_the_endpoint_records_who_asked(treasurer_client: APIClient, treasurer: User, paid: Payment) -> None:
    """``requested_by`` is the administrator behind the request."""
    treasurer_client.post(refunds_url(paid), {"amount_cents": 1_000, "reason": RefundReason.OTHER})

    assert Refund.objects.get().requested_by == treasurer


def test_the_endpoint_can_cancel_the_term(
    treasurer_client: APIClient, paid: Payment, member: User, annual_plan: MembershipPlan
) -> None:
    """``cancel_term`` in the body ends the coverage the payment bought."""
    term = MembershipFactory(user=member, plan=annual_plan, payment=paid)
    treasurer_client.post(
        refunds_url(paid),
        {"amount_cents": 6_500, "reason": RefundReason.ERROR, "cancel_term": True},
    )

    term.refresh_from_db()
    assert term.status == MembershipStatusChoices.CANCELED


def test_too_large_an_amount_is_a_400_keyed_by_the_amount(
    treasurer_client: APIClient, paid: Payment
) -> None:
    """Refunding more than remains names ``amount_cents``."""
    response = treasurer_client.post(
        refunds_url(paid), {"amount_cents": 9_000, "reason": RefundReason.OTHER}
    )

    assert response.status_code == 400
    assert "amount_cents" in response.json()


def test_an_unknown_reason_is_a_400_keyed_by_the_reason(
    treasurer_client: APIClient, paid: Payment
) -> None:
    """The choices are closed, and the complaint says which field is wrong."""
    response = treasurer_client.post(
        refunds_url(paid), {"amount_cents": 1_000, "reason": "because"}
    )

    assert response.status_code == 400
    assert "reason" in response.json()


def test_an_unknown_payment_is_a_404(treasurer_client: APIClient) -> None:
    """There is nothing to refund."""
    response = treasurer_client.post(
        "/api/v1/admin/payments/424242/refunds",
        {"amount_cents": 1_000, "reason": RefundReason.OTHER},
    )
    assert response.status_code == 404


def test_a_provider_that_refuses_is_a_400(
    treasurer_client: APIClient, paid: Payment, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A provider outage is answered with the sentence it gave, not a 500."""

    def refuse(self: MockProvider, payment: Payment, refund: Refund) -> dict[str, Any]:
        raise ProviderUnavailableError("The provider could not be reached.")

    monkeypatch.setattr(MockProvider, "refund", refuse)

    response = treasurer_client.post(
        refunds_url(paid), {"amount_cents": 1_000, "reason": RefundReason.OTHER}
    )

    assert response.status_code == 400
    assert "could not be reached" in response.json()["detail"]
