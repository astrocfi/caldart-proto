"""Money taken by hand: a check in the mail, cash at a meeting, a transfer.

``POST /admin/payments/record`` and the service behind it, which creates an
already-succeeded payment with a zero fee and activates whatever term it bought.
"""

from __future__ import annotations

import datetime as dt

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import ACCOUNT_ADMIN, SYSTEM_ADMIN, TREASURER
from apps.members.models import Membership, MembershipPlan
from apps.payments import manual
from apps.payments.dates import CLOCK_GRACE_DAYS
from apps.payments.manual import record_manual_payment
from apps.payments.models import Payment, PaymentProvider, PaymentStatus, PaymentWallet
from caldart.exceptions import DomainValidationError
from tests.conftest import role_matrix

pytestmark = pytest.mark.django_db

RECORD = "/api/v1/admin/payments/record"


def check_body(member: User | None, **overrides: object) -> dict[str, object]:
    """The body of a $45 annual membership paid by check, with ``overrides`` applied."""
    body: dict[str, object] = {
        "user_id": member.pk if member is not None else 0,
        "plan": "annual",
        "contribution_cents": 0,
        "method": PaymentWallet.CHECK.value,
        "reference": "1041",
        "received_on": "2026-03-02",
        "note": "Mailed to the PO box",
    }
    body.update(overrides)
    return body


# --------------------------------------------------------------------------
# The service
# --------------------------------------------------------------------------
def test_a_recorded_payment_is_succeeded_the_moment_it_is_written(
    member: User, treasurer: User, annual_plan: MembershipPlan
) -> None:
    """The money is already in hand, so there is nothing to confirm."""
    payment = record_manual_payment(
        user=member,
        plan_slug="annual",
        contribution_cents=0,
        method=PaymentWallet.CHECK,
        reference="1041",
        received_on=dt.date(2026, 3, 2),
        note="",
        actor=treasurer,
    )
    assert payment.status == PaymentStatus.SUCCEEDED


def test_a_recorded_payment_carries_no_fee_and_a_net_equal_to_the_amount(
    member: User, treasurer: User, annual_plan: MembershipPlan
) -> None:
    """Nobody took a cut of a check, so the whole amount reached the bank."""
    payment = record_manual_payment(
        user=member,
        plan_slug="annual",
        contribution_cents=1_000,
        method=PaymentWallet.CASH,
        reference="",
        received_on=dt.date(2026, 3, 2),
        note="",
        actor=treasurer,
    )
    assert payment.fee_cents == 0
    assert payment.net_cents == payment.amount_cents


def test_a_recorded_payment_is_dated_the_day_the_money_arrived(
    member: User, treasurer: User, annual_plan: MembershipPlan
) -> None:
    """The ledger date is the day of the check, not the day it was keyed in."""
    payment = record_manual_payment(
        user=member,
        plan_slug="annual",
        contribution_cents=0,
        method=PaymentWallet.CHECK,
        reference="1041",
        received_on=dt.date(2026, 3, 2),
        note="",
        actor=treasurer,
    )
    assert payment.paid_on == dt.date(2026, 3, 2)


def test_a_recorded_payment_names_the_administrator_who_wrote_it(
    member: User, treasurer: User, annual_plan: MembershipPlan
) -> None:
    """Somebody keyed this in, and the record says who."""
    payment = record_manual_payment(
        user=member,
        plan_slug="annual",
        contribution_cents=0,
        method=PaymentWallet.CHECK,
        reference="1041",
        received_on=dt.date(2026, 3, 2),
        note="",
        actor=treasurer,
    )
    assert payment.recorded_by == treasurer


def test_a_recorded_payment_activates_the_term_it_bought(
    member: User, treasurer: User, annual_plan: MembershipPlan
) -> None:
    """A check buys exactly the term a card would have bought."""
    payment = record_manual_payment(
        user=member,
        plan_slug="annual",
        contribution_cents=0,
        method=PaymentWallet.CHECK,
        reference="1041",
        received_on=dt.date(2026, 3, 2),
        note="",
        actor=treasurer,
    )
    assert Membership.objects.filter(payment=payment).count() == 1


def test_a_lifetime_plan_can_be_paid_by_check(
    member: User, treasurer: User, life_plan: MembershipPlan
) -> None:
    """A lifetime membership is exactly the kind somebody writes a check for."""
    payment = record_manual_payment(
        user=member,
        plan_slug="life",
        contribution_cents=0,
        method=PaymentWallet.CHECK,
        reference="1042",
        received_on=dt.date(2026, 3, 2),
        note="",
        actor=treasurer,
    )
    assert payment.plan == life_plan


def test_a_pure_contribution_can_be_recorded(member: User, treasurer: User) -> None:
    """Cash in the bucket at a meeting buys no term and is still a payment."""
    payment = record_manual_payment(
        user=member,
        plan_slug=None,
        contribution_cents=5_000,
        method=PaymentWallet.CASH,
        reference="",
        received_on=dt.date(2026, 3, 2),
        note="",
        actor=treasurer,
    )
    assert payment.kind == "contribution"


def test_a_method_no_hand_could_present_is_refused(
    member: User, treasurer: User, annual_plan: MembershipPlan
) -> None:
    """Only a check, cash, a transfer or "other" can be recorded by hand."""
    with pytest.raises(DomainValidationError, match=r"Unknown payment method 'apple_pay'\."):
        record_manual_payment(
            user=member,
            plan_slug="annual",
            contribution_cents=0,
            method=PaymentWallet.APPLE_PAY,
            reference="",
            received_on=dt.date(2026, 3, 2),
            note="",
            actor=treasurer,
        )


def test_money_cannot_have_arrived_in_the_future(
    member: User, treasurer: User, annual_plan: MembershipPlan, today: dt.date
) -> None:
    """A date past the day's grace is a typo, not a payment."""
    with pytest.raises(DomainValidationError, match="cannot have arrived in the future"):
        record_manual_payment(
            user=member,
            plan_slug="annual",
            contribution_cents=0,
            method=PaymentWallet.CHECK,
            reference="",
            received_on=today + dt.timedelta(days=CLOCK_GRACE_DAYS + 1),
            note="",
            actor=treasurer,
        )


def test_money_dated_by_a_clock_a_day_ahead_is_recorded(
    member: User, treasurer: User, annual_plan: MembershipPlan, today: dt.date
) -> None:
    """A browser already on tomorrow still records a check that arrived today."""
    tomorrow = today + dt.timedelta(days=CLOCK_GRACE_DAYS)
    payment = record_manual_payment(
        user=member,
        plan_slug="annual",
        contribution_cents=0,
        method=PaymentWallet.CHECK,
        reference="",
        received_on=tomorrow,
        note="",
        actor=treasurer,
    )
    assert payment.received_on == tomorrow


def test_a_reference_another_recorded_payment_carries_is_refused(
    member: User, treasurer: User, annual_plan: MembershipPlan
) -> None:
    """Two checks cannot bear the same number: one of them is a duplicate entry."""
    record_manual_payment(
        user=member,
        plan_slug="annual",
        contribution_cents=0,
        method=PaymentWallet.CHECK,
        reference="1041",
        received_on=dt.date(2026, 3, 2),
        note="",
        actor=treasurer,
    )
    with pytest.raises(DomainValidationError, match="already carries the reference '1041'"):
        record_manual_payment(
            user=member,
            plan_slug="annual",
            contribution_cents=0,
            method=PaymentWallet.CHECK,
            reference="1041",
            received_on=dt.date(2026, 3, 3),
            note="",
            actor=treasurer,
        )


def test_a_reference_taken_after_the_check_is_still_refused(
    member: User,
    treasurer: User,
    annual_plan: MembershipPlan,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two treasurers entering one check at once get the same 400, not a 500."""
    record_manual_payment(
        user=member,
        plan_slug="annual",
        contribution_cents=0,
        method=PaymentWallet.CHECK,
        reference="1041",
        received_on=dt.date(2026, 3, 2),
        note="",
        actor=treasurer,
    )
    # The loser of the race passed the duplicate check before the winner's row
    # existed, which is what a stubbed check stands in for here.
    monkeypatch.setattr(manual, "_reference_taken", lambda reference: False)

    with pytest.raises(DomainValidationError, match="already carries the reference '1041'"):
        record_manual_payment(
            user=member,
            plan_slug="annual",
            contribution_cents=0,
            method=PaymentWallet.CHECK,
            reference="1041",
            received_on=dt.date(2026, 3, 3),
            note="",
            actor=treasurer,
        )


def test_two_recorded_payments_may_both_leave_the_reference_blank(
    member: User, treasurer: User, annual_plan: MembershipPlan
) -> None:
    """Cash has no number, so a blank reference is not a duplicate."""
    for day in (2, 3):
        record_manual_payment(
            user=member,
            plan_slug=None,
            contribution_cents=1_000,
            method=PaymentWallet.CASH,
            reference="",
            received_on=dt.date(2026, 3, day),
            note="",
            actor=treasurer,
        )
    assert Payment.objects.filter(provider=PaymentProvider.MANUAL).count() == 2


def test_a_plan_that_is_not_on_sale_is_refused(
    member: User, treasurer: User, annual_plan: MembershipPlan
) -> None:
    """A slug no active plan carries is refused, keyed by the plan."""
    with pytest.raises(DomainValidationError, match=r"Unknown membership plan 'gold-wings'\."):
        record_manual_payment(
            user=member,
            plan_slug="gold-wings",
            contribution_cents=0,
            method=PaymentWallet.CHECK,
            reference="",
            received_on=dt.date(2026, 3, 2),
            note="",
            actor=treasurer,
        )


# --------------------------------------------------------------------------
# POST /admin/payments/record
# --------------------------------------------------------------------------
def test_the_endpoint_answers_201_with_the_payment(
    treasurer_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The finance screen gets the row it will show back from the create."""
    response = treasurer_client.post(RECORD, check_body(member), format="json")
    assert response.status_code == 201
    assert response.json()["provider"] == "manual"


def test_the_endpoint_keeps_the_check_number_on_the_payment(
    treasurer_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The reference is the provider reference of a payment nobody's provider took."""
    body = treasurer_client.post(RECORD, check_body(member), format="json").json()
    assert body["provider_ref"] == "1041"


def test_the_endpoint_keeps_the_treasurers_note(
    treasurer_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The note is what the treasurer will read back in a year."""
    body = treasurer_client.post(RECORD, check_body(member), format="json").json()
    assert body["note"] == "Mailed to the PO box"


def test_the_endpoint_writes_an_audit_record(
    treasurer_client: APIClient,
    member: User,
    treasurer: User,
    annual_plan: MembershipPlan,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Recording money by hand is a privileged act, so the log says who did it."""
    with caplog.at_level("INFO", logger="caldart.audit"):
        treasurer_client.post(RECORD, check_body(member), format="json")
    assert f"action=payment.record actor={treasurer.pk} target={member.pk}" in caplog.text


def test_the_endpoint_refuses_an_unknown_method(
    treasurer_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A wallet outside the four a hand can present is a 400 keyed by ``method``."""
    response = treasurer_client.post(RECORD, check_body(member, method="apple_pay"), format="json")
    assert response.status_code == 400
    assert "method" in response.json()


def test_the_endpoint_refuses_a_date_in_the_future(
    treasurer_client: APIClient, member: User, annual_plan: MembershipPlan, today: dt.date
) -> None:
    """The service's complaint reaches the caller keyed by ``received_on``."""
    too_late = (today + dt.timedelta(days=CLOCK_GRACE_DAYS + 1)).isoformat()
    response = treasurer_client.post(
        RECORD, check_body(member, received_on=too_late), format="json"
    )
    assert response.json() == {"received_on": ["The money cannot have arrived in the future."]}


def test_the_endpoint_refuses_a_body_that_buys_nothing(
    treasurer_client: APIClient, member: User
) -> None:
    """No plan and no contribution is nothing to record."""
    response = treasurer_client.post(
        RECORD, check_body(member, plan="", contribution_cents=0), format="json"
    )
    assert response.json() == {"amount_cents": ["Nothing to charge."]}


def test_the_endpoint_answers_404_for_an_unknown_member(
    treasurer_client: APIClient, annual_plan: MembershipPlan
) -> None:
    """A member id nobody holds is a 404, not a 400."""
    response = treasurer_client.post(RECORD, check_body(member=None, user_id=9_999), format="json")
    assert response.status_code == 404


@pytest.mark.parametrize(("slug", "allowed"), role_matrix(TREASURER, ACCOUNT_ADMIN, SYSTEM_ADMIN))
def test_recording_is_for_the_finance_roles_only(
    api_client: APIClient,
    all_role_users: dict[str, User],
    member: User,
    annual_plan: MembershipPlan,
    slug: str,
    allowed: bool,
) -> None:
    """Only a treasurer, an account admin or a system admin records money by hand."""
    api_client.force_login(all_role_users[slug])
    response = api_client.post(RECORD, check_body(member), format="json")
    assert response.status_code == (201 if allowed else 403)


def test_recording_rejects_an_anonymous_caller(api_client: APIClient, member: User) -> None:
    """An anonymous caller gets a 401."""
    assert api_client.post(RECORD, check_body(member), format="json").status_code == 401
