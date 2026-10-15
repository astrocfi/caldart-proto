"""A renewal charge whose outcome the scan did not learn is taken once, and recorded.

``docs/developer/renewals.rst`` (the scan and the providers) is the contract.  Stripe is
replaced by :class:`StripeLedger`, a fake that remembers every PaymentIntent it made and
honors idempotency keys the way Stripe does, so each test can count the charges Stripe
actually took.  Each scenario breaks the scan at a different point -- an answer lost after
Stripe charged, a request Stripe never received, a scan that died after claiming its
attempt, and a charge Stripe is still processing -- and asserts exactly one charge per
attempt, recorded on the attempt.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import date, timedelta
from types import SimpleNamespace
from typing import Any

import pytest
import stripe
from django.core.mail import EmailMessage
from django.utils import timezone
from pytest_django.fixtures import Settings

from apps.accounts.models import User
from apps.members.models import MembershipPlan, MembershipStatusChoices
from apps.payments.models import (
    MandateProvider,
    Payment,
    PaymentStatus,
    RenewalAttempt,
    RenewalMandate,
    RenewalOutcome,
)
from apps.payments.providers import stripe as stripe_provider
from apps.payments.providers.base import MandateMethod
from apps.payments.renewals.mandates import (
    begin_mandate,
    cancel_mandate,
    discard_pending_mandate,
    save_method,
)
from apps.payments.renewals.scan import run_auto_renewals
from apps.payments.services import create_checkout, mark_succeeded
from tests.conftest import RecordedEvents
from tests.factories import MembershipFactory, RenewalMandateFactory

pytestmark = pytest.mark.django_db

SECRET_KEY = "sk_test_retries"  # noqa: S105 - test fixture

#: Minutes after which a claim nobody finished is taken to have died, in these tests.
STALE_MINUTES = 60

#: What Stripe says about a card it refused.
INSUFFICIENT_FUNDS = "Your card has insufficient funds."


def connection_error() -> stripe.APIConnectionError:
    """The error the SDK raises when Stripe's answer never arrives."""
    # The stripe stubs leave APIConnectionError.__init__ untyped.
    return stripe.APIConnectionError("timed out")  # type: ignore[no-untyped-call]


class StripeLedger:
    """Stripe's own record of off-session charges, as the provider sees it.

    ``create`` makes one PaymentIntent per idempotency key and answers a repeated key
    with the intent it made the first time, as Stripe does for 24 hours;
    :meth:`forget_keys` is that day passing.  ``unreachable`` times the next creates out
    before Stripe receives them, and ``lose_answers`` makes the intent and then times
    out, which is the case where Stripe has charged and the scan does not know it.
    New intents take ``status``.  ``more_pages`` makes every list say it has more,
    ``missing`` refuses every create as Stripe refuses a deleted card, and
    ``on_create`` runs inside each create, as another process would meanwhile.
    """

    def __init__(self) -> None:
        """Start with no intents, no keys, and every charge succeeding."""
        self.intents: dict[str, dict[str, Any]] = {}
        self.keys: dict[str, str] = {}
        self.keys_presented: list[str] = []
        self.status = "succeeded"
        self.unreachable = 0
        self.lose_answers = 0
        self.more_pages = False
        self.missing = ""
        self.on_create: Callable[[], None] = lambda: None
        self.listed_customers: list[str] = []

    def create(
        self, params: dict[str, Any], options: dict[str, Any] | None = None
    ) -> stripe.PaymentIntent:
        """Make or replay the intent for the request's idempotency key."""
        key = str((options or {}).get("idempotency_key") or "")
        self.keys_presented.append(key)
        if self.unreachable > 0:
            self.unreachable -= 1
            raise connection_error()
        if self.missing:
            # The SDK's error classes carry no annotations, so this call is untyped.
            raise stripe.InvalidRequestError(  # type: ignore[no-untyped-call]
                "No such payment method", param=self.missing, code="resource_missing"
            )
        self.on_create()
        if key not in self.keys:
            intent_id = f"pi_renewal_{len(self.intents) + 1}"
            self.intents[intent_id] = {
                "id": intent_id,
                "object": "payment_intent",
                "status": self.status,
                "amount": params["amount"],
                "currency": params["currency"],
                "customer": params["customer"],
                "metadata": dict(params["metadata"]),
                "created": int(time.time()),
            }
            self.keys[key] = intent_id
        intent = self.intents[self.keys[key]]
        if self.lose_answers > 0:
            self.lose_answers -= 1
            raise connection_error()
        return stripe.PaymentIntent.construct_from(intent, SECRET_KEY)

    def retrieve(
        self,
        intent_id: str,
        params: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
    ) -> stripe.PaymentIntent:
        """Answer with the intent Stripe holds under ``intent_id``."""
        return stripe.PaymentIntent.construct_from(self.intents[intent_id], SECRET_KEY)

    def list(
        self, params: dict[str, Any], options: dict[str, Any] | None = None
    ) -> stripe.ListObject[stripe.PaymentIntent]:
        """Every intent for ``params["customer"]`` created at or after ``created.gte``."""
        since = int(params.get("created", {}).get("gte", 0))
        self.listed_customers.append(str(params.get("customer")))
        data = [
            intent
            for intent in self.intents.values()
            if intent["customer"] == params.get("customer") and intent["created"] >= since
        ]
        return stripe.ListObject.construct_from(
            {
                "object": "list",
                "data": data,
                "has_more": self.more_pages,
                "url": "/v1/payment_intents",
            },
            SECRET_KEY,
        )

    def forget_keys(self) -> None:
        """Let a day pass: Stripe keeps an idempotency key for 24 hours."""
        self.keys.clear()

    def settle(self, status: str, **fields: Any) -> None:
        """Move every intent to ``status``, as Stripe does once processing ends."""
        for intent in self.intents.values():
            intent["status"] = status
            intent.update(fields)

    def charges(self) -> int:
        """How many intents Stripe has made: the charges it could take."""
        return len(self.intents)

    def as_client(self) -> SimpleNamespace:
        """The object ``stripe_client()`` is replaced with."""
        return SimpleNamespace(
            v1=SimpleNamespace(
                payment_intents=SimpleNamespace(
                    create=self.create, retrieve=self.retrieve, list=self.list
                )
            )
        )


@pytest.fixture
def ledger(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> StripeLedger:
    """Configure Stripe, replace its client with a ledger, and fix the claim timeout."""
    settings.STRIPE_SECRET_KEY = SECRET_KEY
    settings.STRIPE_PUBLISHABLE_KEY = "pk_test_retries"
    settings.RENEWAL_STALE_MINUTES = STALE_MINUTES
    fake = StripeLedger()
    monkeypatch.setattr(stripe_provider, "stripe_client", fake.as_client)
    return fake


def renewal_due(user: User, plan: MembershipPlan, today: date) -> RenewalMandate:
    """A Stripe renewal whose charge is due ``today``, its notice already sent.

    The scan of the day before writes the attempt and sends the notice, which touch
    no provider, so the next scan of ``today`` is the one that charges.
    """
    MembershipFactory(
        user=user,
        plan=plan,
        starts_on=today - timedelta(days=364),
        ends_on=today,
        status=MembershipStatusChoices.ACTIVE,
    )
    mandate: RenewalMandate = RenewalMandateFactory(
        user=user,
        plan=plan,
        provider=MandateProvider.STRIPE,
        customer_ref="cus_retries",
        method_ref="pm_retries",
        next_charge_on=today,
    )
    run_auto_renewals(today=today - timedelta(days=1))
    return mandate


def the_attempt() -> RenewalAttempt:
    """The one attempt the scan wrote."""
    return RenewalAttempt.objects.get(retry_of__isnull=True)


def leave_claimed(minutes_ago: int) -> None:
    """Leave the attempt claimed ``minutes_ago``, as a scan that died there leaves it."""
    RenewalAttempt.objects.update(attempted_at=timezone.now() - timedelta(minutes=minutes_ago))


# --------------------------------------------------------------------------
# An answer lost after Stripe charged
# --------------------------------------------------------------------------
def test_a_charge_whose_answer_was_lost_is_not_taken_again(
    ledger: StripeLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The next scan, a day on and past Stripe's key memory, finds the charge made."""
    renewal_due(member, annual_plan, today)
    ledger.lose_answers = 1
    run_auto_renewals(today=today)
    ledger.forget_keys()

    run_auto_renewals(today=today)

    assert ledger.charges() == 1


def test_a_charge_whose_answer_was_lost_is_recorded_by_the_next_scan(
    ledger: StripeLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The charge Stripe made is adopted, so the attempt reads as charged."""
    renewal_due(member, annual_plan, today)
    ledger.lose_answers = 1
    run_auto_renewals(today=today)
    ledger.forget_keys()

    run_auto_renewals(today=today)

    assert the_attempt().outcome == RenewalOutcome.SUCCEEDED


def test_the_next_scan_records_the_intent_stripe_already_made(
    ledger: StripeLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The payment carries the id of the one intent Stripe holds."""
    renewal_due(member, annual_plan, today)
    ledger.lose_answers = 1
    run_auto_renewals(today=today)
    ledger.forget_keys()

    run_auto_renewals(today=today)

    assert Payment.objects.get().provider_ref == "pi_renewal_1"


def test_a_lost_answer_keeps_the_pending_payment_for_the_next_try(
    ledger: StripeLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The payment stays on the attempt, so a retry is keyed as the first try was."""
    renewal_due(member, annual_plan, today)
    ledger.lose_answers = 1

    run_auto_renewals(today=today)

    attempt = the_attempt()
    assert attempt.payment is not None
    assert attempt.payment.status == PaymentStatus.PENDING


def test_a_lost_answer_leaves_the_attempt_scheduled_and_unclaimed(
    ledger: StripeLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """Nothing is known about the card, so the attempt waits for the next scan."""
    renewal_due(member, annual_plan, today)
    ledger.lose_answers = 1

    run_auto_renewals(today=today)

    attempt = the_attempt()
    assert attempt.outcome == RenewalOutcome.SCHEDULED
    assert attempt.attempted_at is None


# --------------------------------------------------------------------------
# A request Stripe never received
# --------------------------------------------------------------------------
def test_a_charge_stripe_never_received_is_taken_once_by_the_next_scan(
    ledger: StripeLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """Finding no earlier charge, the next scan charges, and only once."""
    renewal_due(member, annual_plan, today)
    ledger.unreachable = 1
    run_auto_renewals(today=today)

    run_auto_renewals(today=today)

    assert ledger.charges() == 1


def test_a_retried_charge_presents_the_key_the_first_try_did(
    ledger: StripeLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The pending payment is reused, so Stripe sees one idempotency key twice."""
    renewal_due(member, annual_plan, today)
    ledger.unreachable = 1
    run_auto_renewals(today=today)

    run_auto_renewals(today=today)

    first, second = ledger.keys_presented
    assert first == second


def test_a_charge_stripe_never_received_is_recorded_once_taken(
    ledger: StripeLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The retry's success closes the attempt as charged."""
    renewal_due(member, annual_plan, today)
    ledger.unreachable = 1
    run_auto_renewals(today=today)

    run_auto_renewals(today=today)

    assert the_attempt().outcome == RenewalOutcome.SUCCEEDED


# --------------------------------------------------------------------------
# A scan that died after claiming its attempt
# --------------------------------------------------------------------------
def test_a_claim_a_dead_scan_left_is_charged_once_after_the_timeout(
    ledger: StripeLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """A claim older than ``RENEWAL_STALE_MINUTES`` is taken up and charged."""
    renewal_due(member, annual_plan, today)
    leave_claimed(STALE_MINUTES + 1)

    run_auto_renewals(today=today)

    assert ledger.charges() == 1


def test_a_claim_a_dead_scan_left_is_recorded_after_the_timeout(
    ledger: StripeLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The renewal does not lapse because the scan that claimed it died."""
    renewal_due(member, annual_plan, today)
    leave_claimed(STALE_MINUTES + 1)

    run_auto_renewals(today=today)

    assert the_attempt().outcome == RenewalOutcome.SUCCEEDED


def test_a_claim_younger_than_the_timeout_is_left_to_its_scan(
    ledger: StripeLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """A claim inside the timeout may still be charging, so nobody else charges."""
    renewal_due(member, annual_plan, today)
    leave_claimed(STALE_MINUTES - 1)

    run = run_auto_renewals(today=today)

    assert run.skipped_by_reason == {"in_flight": 1}


def test_a_scan_that_died_after_charging_takes_nothing_twice(
    ledger: StripeLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """Stripe already holds the charge for the attempt's payment, so it is adopted."""
    renewal_due(member, annual_plan, today)
    payment = create_checkout(member, annual_plan.slug, 0, MandateProvider.STRIPE)
    RenewalAttempt.objects.update(payment=payment)
    ledger.create(
        {
            "amount": payment.amount_cents,
            "currency": payment.currency,
            "customer": "cus_retries",
            "metadata": {"payment_id": str(payment.pk)},
        },
        {"idempotency_key": f"caldart-renewal-{payment.pk}"},
    )
    leave_claimed(STALE_MINUTES + 1)
    ledger.forget_keys()

    run_auto_renewals(today=today)

    assert ledger.charges() == 1


# --------------------------------------------------------------------------
# A charge Stripe is still processing
# --------------------------------------------------------------------------
def test_a_charge_stripe_is_still_processing_is_not_a_decline(
    ledger: StripeLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """``processing`` spends no rung of the retry ladder."""
    mandate = renewal_due(member, annual_plan, today)
    ledger.status = "processing"

    run_auto_renewals(today=today)

    mandate.refresh_from_db()
    assert mandate.failure_count == 0


def test_a_processing_charge_is_counted_as_pending(
    ledger: StripeLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The run says why the charge is neither taken nor refused."""
    renewal_due(member, annual_plan, today)
    ledger.status = "processing"

    run = run_auto_renewals(today=today)

    assert run.skipped_by_reason == {"pending": 1}


def test_a_processing_charge_tells_the_member_nothing_yet(
    ledger: StripeLedger,
    member: User,
    annual_plan: MembershipPlan,
    today: date,
    mailoutbox: list[EmailMessage],
) -> None:
    """No charged or failed email goes out before Stripe has an answer."""
    renewal_due(member, annual_plan, today)
    ledger.status = "processing"
    mailoutbox.clear()

    run_auto_renewals(today=today)

    assert mailoutbox == []


def test_a_processing_charge_is_settled_by_the_next_scan(
    ledger: StripeLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """Once Stripe reports ``succeeded`` the next scan records the charge."""
    renewal_due(member, annual_plan, today)
    ledger.status = "processing"
    run_auto_renewals(today=today)
    ledger.settle("succeeded")

    run_auto_renewals(today=today)

    assert the_attempt().outcome == RenewalOutcome.SUCCEEDED


def test_a_processing_charge_is_never_made_again(
    ledger: StripeLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The next scan asks after the intent it made rather than making another."""
    renewal_due(member, annual_plan, today)
    ledger.status = "processing"
    run_auto_renewals(today=today)
    ledger.forget_keys()
    ledger.settle("succeeded")

    run_auto_renewals(today=today)

    assert ledger.charges() == 1


def test_a_charge_the_webhook_settled_is_recorded_by_the_next_scan(
    ledger: StripeLedger,
    member: User,
    annual_plan: MembershipPlan,
    today: date,
    mailoutbox: list[EmailMessage],
) -> None:
    """The member is emailed the charge once the webhook has marked the payment paid."""
    renewal_due(member, annual_plan, today)
    ledger.status = "processing"
    run_auto_renewals(today=today)
    ledger.settle("succeeded")
    # What the ``payment_intent.succeeded`` webhook does with the intent.
    mark_succeeded(Payment.objects.get(), provider_ref="pi_renewal_1")
    mailoutbox.clear()

    run_auto_renewals(today=today)

    assert [str(message.subject).split(": ", 1)[1] for message in mailoutbox] == [
        "your membership has been renewed"
    ]


def test_a_processing_charge_stripe_then_refuses_takes_a_rung(
    ledger: StripeLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """A refusal after processing is an ordinary decline, retried as one."""
    mandate = renewal_due(member, annual_plan, today)
    ledger.status = "processing"
    run_auto_renewals(today=today)
    ledger.settle("requires_payment_method", last_payment_error={"message": INSUFFICIENT_FUNDS})

    run_auto_renewals(today=today)

    mandate.refresh_from_db()
    assert the_attempt().error == INSUFFICIENT_FUNDS
    assert mandate.failure_count == 1


# --------------------------------------------------------------------------
# Renewal turned off while a charge is unsettled
# --------------------------------------------------------------------------
def test_an_unsettled_charge_is_still_recorded_after_renewal_is_turned_off(
    ledger: StripeLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """Money Stripe took before the member turned renewal off is recorded, not lost."""
    mandate = renewal_due(member, annual_plan, today)
    ledger.lose_answers = 1
    run_auto_renewals(today=today)
    cancel_mandate(mandate, actor=member)

    run_auto_renewals(today=today)

    assert Payment.objects.get().status == PaymentStatus.SUCCEEDED


def test_an_unsettled_charge_stripe_never_made_is_dropped_once_renewal_is_off(
    ledger: StripeLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """With no charge at Stripe and renewal off, nothing is charged and nothing kept."""
    mandate = renewal_due(member, annual_plan, today)
    ledger.unreachable = 1
    run_auto_renewals(today=today)
    cancel_mandate(mandate, actor=member)

    run_auto_renewals(today=today)

    assert ledger.charges() == 0
    assert Payment.objects.count() == 0
    assert the_attempt().outcome == RenewalOutcome.SKIPPED


# --------------------------------------------------------------------------
# The member changes card, or provider, while a charge is unsettled
# --------------------------------------------------------------------------
def lose_the_answer(ledger: StripeLedger, member: User, plan: MembershipPlan, today: date) -> None:
    """Leave the member's renewal charged at Stripe, with the answer lost, a day ago."""
    renewal_due(member, plan, today)
    ledger.lose_answers = 1
    run_auto_renewals(today=today)
    ledger.forget_keys()


def test_a_new_card_after_a_lost_answer_takes_nothing_twice(
    ledger: StripeLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The lookup asks after the customer the charge was sent for, not the new card's."""
    lose_the_answer(ledger, member, annual_plan, today)
    mandate = begin_mandate(
        member, plan=annual_plan, contribution_cents=0, provider=MandateProvider.STRIPE
    )
    save_method(
        mandate,
        MandateMethod(method_ref="pm_new", customer_ref="cus_new", label="Visa ending 1111"),
        actor=member,
    )

    run_auto_renewals(today=today)

    assert ledger.charges() == 1
    assert ledger.listed_customers == ["cus_retries"]


def test_an_abandoned_new_setup_keeps_the_unsettled_charge(
    ledger: StripeLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """Throwing the pending setup away keeps the attempt, so the charge is recorded."""
    lose_the_answer(ledger, member, annual_plan, today)
    begin_mandate(member, plan=annual_plan, contribution_cents=0, provider=MandateProvider.STRIPE)
    discard_pending_mandate(member)

    run_auto_renewals(today=today)

    assert the_attempt().outcome == RenewalOutcome.SUCCEEDED
    assert ledger.charges() == 1


def test_a_provider_switch_after_a_lost_answer_still_asks_stripe(
    ledger: StripeLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The payment names the provider it was sent to, whatever the mandate says now."""
    lose_the_answer(ledger, member, annual_plan, today)
    begin_mandate(member, plan=annual_plan, contribution_cents=0, provider=MandateProvider.PAYPAL)

    run_auto_renewals(today=today)

    assert Payment.objects.get().status == PaymentStatus.SUCCEEDED
    assert ledger.charges() == 1


# --------------------------------------------------------------------------
# A scan that lost its claim records nothing
# --------------------------------------------------------------------------
def test_a_scan_whose_claim_was_taken_over_records_nothing(
    ledger: StripeLedger,
    member: User,
    annual_plan: MembershipPlan,
    today: date,
    mailoutbox: list[EmailMessage],
) -> None:
    """Another scan took the claim mid-charge, so this one neither closes nor emails."""
    renewal_due(member, annual_plan, today)
    mailoutbox.clear()

    def take_over() -> None:
        RenewalAttempt.objects.update(attempted_at=timezone.now() + timedelta(seconds=1))

    ledger.on_create = take_over

    run_auto_renewals(today=today)

    assert the_attempt().outcome == RenewalOutcome.SCHEDULED
    assert mailoutbox == []


# --------------------------------------------------------------------------
# A charge pending for days, a lookup that runs long, a card that is gone
# --------------------------------------------------------------------------
def pending_for_days(ledger: StripeLedger, member: User, plan: MembershipPlan, today: date) -> None:
    """Leave the member's renewal processing at Stripe, sent four days ago."""
    renewal_due(member, plan, today)
    ledger.status = "processing"
    run_auto_renewals(today=today)
    Payment.objects.update(charge_sent_at=timezone.now() - timedelta(days=4))


def test_a_charge_pending_for_days_is_flagged_to_the_treasurer_once(
    ledger: StripeLedger,
    member: User,
    annual_plan: MembershipPlan,
    today: date,
    recorded_events: RecordedEvents,
) -> None:
    """A charge still processing three days after it was sent raises one event."""
    pending_for_days(ledger, member, annual_plan, today)

    run_auto_renewals(today=today)
    run_auto_renewals(today=today)

    assert [slug for slug, _ in recorded_events].count("renewal_needs_checking") == 1


def test_a_charge_pending_for_days_is_logged_at_error(
    ledger: StripeLedger,
    member: User,
    annual_plan: MembershipPlan,
    today: date,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The operator's log says which payment has been pending too long."""
    pending_for_days(ledger, member, annual_plan, today)

    with caplog.at_level(logging.ERROR):
        run_auto_renewals(today=today)

    assert any("pending at stripe for more than" in r.getMessage() for r in caplog.records)


def test_a_lookup_with_more_pages_and_no_match_charges_nothing(
    ledger: StripeLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The intent could be on a later page, so the charge is put off, not made again."""
    lose_the_answer(ledger, member, annual_plan, today)
    ledger.intents["pi_renewal_1"]["metadata"]["payment_id"] = "someone-else"
    ledger.more_pages = True

    run = run_auto_renewals(today=today)

    assert run.skipped_by_reason == {"provider_down": 1}
    assert ledger.charges() == 1


def test_a_card_stripe_no_longer_has_is_a_decline(
    ledger: StripeLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """``resource_missing`` on the card is the member's method gone, not an outage."""
    mandate = renewal_due(member, annual_plan, today)
    ledger.missing = "payment_method"

    run_auto_renewals(today=today)

    mandate.refresh_from_db()
    assert mandate.failure_count == 1


def test_a_renewal_with_no_saved_customer_is_a_decline(
    ledger: StripeLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """Nothing can be charged, or looked up, without a customer, so nothing is listed."""
    mandate = renewal_due(member, annual_plan, today)
    RenewalMandate.objects.filter(pk=mandate.pk).update(customer_ref="")

    run_auto_renewals(today=today)

    assert the_attempt().outcome == RenewalOutcome.FAILED
    assert ledger.listed_customers == []
