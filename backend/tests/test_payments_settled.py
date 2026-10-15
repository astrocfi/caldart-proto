"""A payment whose money arrived stays where its refunds left it.

``mark_succeeded`` and ``mark_failed`` are what every provider's confirm call and
webhook reach the money through, so a refunded payment that either of them moved
would reopen the term the refund closed, date the payment into the current period,
and send a second receipt.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from django.core import mail

from apps.members.models import Membership
from apps.payments.models import Payment, PaymentStatus
from apps.payments.refunds import record_dashboard_refund
from apps.payments.services import mark_failed, mark_succeeded
from tests.factories import PaymentFactory

pytestmark = pytest.mark.django_db

#: When the payment in these tests settled, well before the test runs.
SETTLED_AT = datetime(2025, 3, 14, 12, 0, tzinfo=UTC)

REFUNDED_STATUSES = [PaymentStatus.REFUNDED, PaymentStatus.PARTIALLY_REFUNDED]

SETTLED_STATUSES = [PaymentStatus.SUCCEEDED, *REFUNDED_STATUSES]


def settled_payment(status: str) -> Payment:
    """A mock payment that settled at :data:`SETTLED_AT` and now reads ``status``."""
    return PaymentFactory(status=status, completed_at=SETTLED_AT)


@pytest.mark.parametrize("status", REFUNDED_STATUSES)
def test_a_refunded_payment_is_not_marked_succeeded_again(status: str) -> None:
    """A success reported after a refund leaves the payment's status alone."""
    payment = settled_payment(status)

    mark_succeeded(payment)

    payment.refresh_from_db()
    assert payment.status == status


@pytest.mark.parametrize("status", REFUNDED_STATUSES)
def test_a_refunded_payment_keeps_its_completion_date(status: str) -> None:
    """A success reported after a refund does not move the payment's ledger date."""
    payment = settled_payment(status)

    mark_succeeded(payment)

    payment.refresh_from_db()
    assert payment.completed_at == SETTLED_AT


@pytest.mark.parametrize("status", REFUNDED_STATUSES)
def test_a_refunded_payment_does_not_buy_a_second_term(status: str) -> None:
    """A success reported after a refund doesn't activate a membership term."""
    payment = settled_payment(status)

    mark_succeeded(payment)

    assert Membership.objects.filter(payment=payment).count() == 0


@pytest.mark.parametrize("status", REFUNDED_STATUSES)
def test_a_refunded_payment_does_not_send_a_second_receipt(status: str) -> None:
    """A success reported after a refund doesn't email anyone."""
    payment = settled_payment(status)

    mark_succeeded(payment)

    assert len(mail.outbox) == 0


@pytest.mark.parametrize("status", SETTLED_STATUSES)
def test_a_settled_payment_is_never_marked_failed(status: str) -> None:
    """A failure reported for a payment whose money arrived leaves its status alone."""
    payment = settled_payment(status)

    mark_failed(payment, {"event_type": "PAYMENT.CAPTURE.REVERSED"})

    payment.refresh_from_db()
    assert payment.status == status


@pytest.mark.parametrize("status", SETTLED_STATUSES)
def test_a_failure_for_a_settled_payment_keeps_its_stored_response(status: str) -> None:
    """A refused failure does not overwrite what the provider answered when it settled."""
    payment = settled_payment(status)
    payment.raw = {"id": "settled"}
    payment.save(update_fields=["raw"])

    mark_failed(payment, {"event_type": "PAYMENT.CAPTURE.REVERSED"})

    payment.refresh_from_db()
    assert payment.raw == {"id": "settled"}


@pytest.mark.parametrize("status", [PaymentStatus.PENDING, PaymentStatus.FAILED])
def test_a_dashboard_refund_of_an_unsettled_payment_is_not_filed(status: str) -> None:
    """A refund for a payment CalDART never saw settle doesn't write a refund row."""
    payment = PaymentFactory(status=status)

    record_dashboard_refund(
        payment, amount_cents=1_000, provider_ref="REFUND-EARLY", raw={"id": "REFUND-EARLY"}
    )

    assert payment.refunds.count() == 0


@pytest.mark.parametrize("status", [PaymentStatus.PENDING, PaymentStatus.FAILED])
def test_a_dashboard_refund_of_an_unsettled_payment_leaves_its_status(status: str) -> None:
    """A refused dashboard refund leaves the payment where it was, to settle normally."""
    payment = PaymentFactory(status=status)

    record_dashboard_refund(
        payment, amount_cents=1_000, provider_ref="REFUND-EARLY", raw={"id": "REFUND-EARLY"}
    )

    payment.refresh_from_db()
    assert payment.status == status


def test_a_pending_payment_is_marked_failed() -> None:
    """A failure for a payment still waiting on its money marks it failed."""
    payment = PaymentFactory(status=PaymentStatus.PENDING)

    mark_failed(payment)

    payment.refresh_from_db()
    assert payment.status == PaymentStatus.FAILED
