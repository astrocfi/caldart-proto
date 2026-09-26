"""State changes a payment and a membership term go through after the happy path.

A payment that fails and is tried again, a notification delivered twice, and a
term an administrator cancels before the member buys another one.  Each test
asserts the state on both sides of the change: the payment row, the terms in the
history, and the membership status the member reads.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.members.models import (
    Membership,
    MembershipPlan,
    MembershipSource,
    MembershipState,
    MembershipStatusChoices,
)
from apps.members.services import restore_terms, suspend_terms
from apps.payments.models import Payment, PaymentStatus, PaymentWallet
from apps.payments.services import (
    create_checkout,
    mark_failed,
    mark_succeeded,
    record_provider_event,
)
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

#: The ``annual_plan`` fixture's ``duration_days``, so a term's end date can be
#: stated outright rather than read back from the plan the test just used.
ANNUAL_DAYS = 365


@pytest.fixture
def checkout(member: User, annual_plan: MembershipPlan) -> Payment:
    """A pending mock-provider payment for one annual membership."""
    return create_checkout(member, annual_plan.slug)


# --------------------------------------------------------------------------
# A payment that fails and is tried again
# --------------------------------------------------------------------------
def test_a_failed_payment_activates_nothing(checkout: Payment, member: User) -> None:
    """A failure leaves the payment failed and uncompleted, and the member a friend."""
    failed = mark_failed(checkout, raw={"code": "card_declined"})

    assert failed.status == PaymentStatus.FAILED
    assert failed.completed_at is None
    assert Membership.objects.count() == 0
    assert member.membership_status["status"] == MembershipState.FRIEND


def test_a_failed_payment_that_later_succeeds_activates_the_term(
    checkout: Payment, member: User, annual_plan: MembershipPlan
) -> None:
    """The same payment succeeding after a failure activates the term it paid for."""
    mark_failed(checkout, raw={"code": "card_declined"})

    succeeded = mark_succeeded(checkout, wallet=PaymentWallet.CARD, provider_ref="pi_retry")

    assert succeeded.status == PaymentStatus.SUCCEEDED
    assert succeeded.provider_ref == "pi_retry"
    term = Membership.objects.get()
    assert term.plan == annual_plan
    assert term.source == MembershipSource.PAYMENT
    assert member.membership_status["status"] == MembershipState.CURRENT


def test_the_retry_keeps_the_failure_it_recorded(checkout: Payment) -> None:
    """Succeeding without a ``raw`` payload leaves the failure's payload in place."""
    mark_failed(checkout, raw={"code": "card_declined"})

    succeeded = mark_succeeded(checkout)

    assert succeeded.raw == {"code": "card_declined"}


def test_a_succeeded_payment_is_never_downgraded(checkout: Payment) -> None:
    """A late failure notification cannot take a succeeded payment back."""
    mark_succeeded(checkout)

    still_succeeded = mark_failed(checkout, raw={"code": "too_late"})

    assert still_succeeded.status == PaymentStatus.SUCCEEDED
    assert still_succeeded.raw == {}


# --------------------------------------------------------------------------
# The same notification delivered twice
# --------------------------------------------------------------------------
def test_a_repeated_confirmation_grants_one_term(checkout: Payment) -> None:
    """Confirming the same payment twice leaves exactly one term behind."""
    first = mark_succeeded(checkout, provider_ref="pi_once")
    completed_at = first.completed_at

    second = mark_succeeded(checkout, provider_ref="pi_twice")

    assert Membership.objects.count() == 1
    assert second.completed_at == completed_at
    assert second.provider_ref == "pi_once"


def test_a_webhook_after_the_capture_only_files_the_payload(checkout: Payment) -> None:
    """A provider notification arriving after success records itself and nothing else."""
    mark_succeeded(checkout, provider_ref="pi_captured")

    recorded = record_provider_event(checkout, {"event_type": "PAYMENT.CAPTURE.COMPLETED"})

    assert recorded.status == PaymentStatus.SUCCEEDED
    assert recorded.raw["last_webhook"] == {"event_type": "PAYMENT.CAPTURE.COMPLETED"}
    assert Membership.objects.count() == 1


# --------------------------------------------------------------------------
# A checkout that settles after the payer deactivated
# --------------------------------------------------------------------------
def test_a_payment_confirmed_after_deactivation_buys_a_suspended_term(
    checkout: Payment, member: User, annual_plan: MembershipPlan
) -> None:
    """A provider confirming a checkout after a self-deactivation buys no coverage.

    The confirmation can outrun the deactivation that happened in the browser
    meanwhile, so the term it buys is created ``suspended`` rather than
    ``active``: an account that cannot sign in gets no membership to use until
    it reactivates.  It also chains after the term the deactivation suspended
    rather than starting today and overlapping it, so reactivating does not cost
    the member most of the year they already paid for.
    """
    current = MembershipFactory(user=member, plan=annual_plan)
    assert current.ends_on is not None  # the annual plan always has one
    member.is_active = False
    member.save(update_fields=["is_active"])
    suspend_terms(member)
    current.refresh_from_db()
    assert current.status == MembershipStatusChoices.SUSPENDED

    mark_succeeded(checkout, provider_ref="pi_after_deactivation")

    term = Membership.objects.get(payment=checkout)
    assert term.status == MembershipStatusChoices.SUSPENDED
    assert term.starts_on == current.ends_on + timedelta(days=1)

    restore_terms(member)
    current.refresh_from_db()
    term.refresh_from_db()
    assert (current.status, term.status) == (
        MembershipStatusChoices.ACTIVE,
        MembershipStatusChoices.ACTIVE,
    )
    assert term.starts_on == current.ends_on + timedelta(days=1)


def test_a_manual_grant_to_a_deactivated_account_is_suspended(
    account_admin_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """An administrator's grant to a deactivated account is suspended, not active.

    A grant is placed by the same rule a payment is, so an account that cannot
    sign in gets no membership to use from it until it reactivates.
    """
    member.is_active = False
    member.save(update_fields=["is_active"])

    response = account_admin_client.post(
        f"/api/v1/admin/members/{member.pk}/memberships",
        {"plan": annual_plan.slug},
        format="json",
    )

    assert (response.status_code, response.json()["status"]) == (201, "suspended")


# --------------------------------------------------------------------------
# A canceled term, and the one bought after it
# --------------------------------------------------------------------------
@pytest.fixture
def canceled_term(
    api_client: APIClient, member: User, account_admin: User, annual_plan: MembershipPlan
) -> Membership:
    """A term an account administrator canceled through the admin term endpoint."""
    payment = create_checkout(member, annual_plan.slug)
    term = mark_succeeded(payment).membership
    api_client.force_login(account_admin)
    response = api_client.patch(
        f"/api/v1/admin/memberships/{term.pk}", {"status": "canceled"}, format="json"
    )
    assert response.status_code == 200
    term.refresh_from_db()
    return term


def test_a_canceled_term_ends_the_membership(canceled_term: Membership, member: User) -> None:
    """Cancellation takes the member out of coverage without deleting the term."""
    assert canceled_term.status == MembershipStatusChoices.CANCELED
    assert member.membership_status["status"] == MembershipState.FRIEND


def test_buying_again_after_a_cancellation_starts_a_term_today(
    canceled_term: Membership, member: User, annual_plan: MembershipPlan
) -> None:
    """The replacement term starts today rather than after the canceled term's dates."""
    payment = create_checkout(member, annual_plan.slug)

    mark_succeeded(payment)

    replacement = Membership.objects.exclude(pk=canceled_term.pk).get()
    assert replacement.starts_on == timezone.localdate()
    assert replacement.ends_on == timezone.localdate() + timedelta(days=ANNUAL_DAYS - 1)


def test_buying_again_after_a_cancellation_restores_coverage(
    canceled_term: Membership, member: User, annual_plan: MembershipPlan
) -> None:
    """The member reads as current again, and the canceled term stays canceled."""
    mark_succeeded(create_checkout(member, annual_plan.slug))

    canceled_term.refresh_from_db()
    assert canceled_term.status == MembershipStatusChoices.CANCELED
    assert member.membership_status["status"] == MembershipState.CURRENT


def test_a_canceled_term_is_kept_in_the_history(
    canceled_term: Membership, member: User, annual_plan: MembershipPlan
) -> None:
    """Both terms survive the replacement, so the history still shows the cancellation."""
    mark_succeeded(create_checkout(member, annual_plan.slug))

    statuses = sorted(member.memberships.values_list("status", flat=True))
    assert statuses == [MembershipStatusChoices.ACTIVE, MembershipStatusChoices.CANCELED]
