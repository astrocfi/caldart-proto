"""A PayPal renewal charge PayPal did not answer is taken once, or held for a treasurer.

``docs/developer/renewals.rst`` (the scan and the providers) is the contract.  PayPal is
replaced by :class:`PayPalLedger` behind ``respx``: it keeps every order it made, answers
a repeated ``PayPal-Request-Id`` with the order it already made, and can be told to fail
the next create, capture or read with a status or a timeout.  Each test counts the orders
PayPal made, so a charge taken twice cannot pass.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from datetime import date, timedelta
from io import StringIO
from typing import Any

import freezegun
import httpx
import pytest
import respx
from django.core.mail import EmailMessage
from django.core.management import CommandError, call_command
from django.utils import timezone
from pytest_django.fixtures import Settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import ACCOUNT_ADMIN, SYSTEM_ADMIN, TREASURER
from apps.members.models import MembershipPlan, MembershipStatusChoices
from apps.notifications.messages import build_message
from apps.payments.models import (
    MandateProvider,
    MandateStatus,
    Payment,
    PaymentStatus,
    RenewalAttempt,
    RenewalMandate,
    RenewalOutcome,
)
from apps.payments.providers import paypal as paypal_provider
from apps.payments.renewals.charge import ALREADY_PAID_MESSAGE
from apps.payments.renewals.scan import run_auto_renewals
from apps.payments.services import mark_succeeded
from tests.conftest import (
    PAYPAL_SANDBOX,
    RecordedEvents,
    audit_messages,
    paypal_token,
    role_matrix,
)
from tests.factories import MembershipFactory, RenewalMandateFactory, UserFactory

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("paypal_sandbox")]

ORDERS = f"{PAYPAL_SANDBOX}/v2/checkout/orders"

#: Minutes after which a claim nobody finished is taken to have died, in these tests.
STALE_MINUTES = 60

#: PayPal's id for the capture a treasurer copies from its dashboard.
CAPTURE_ID = "CAPTURE-1"

#: A capture PayPal holds for some other payment.
OTHER_CAPTURE_ID = "CAPTURE-OTHER"


def settle_url(attempt_id: int) -> str:
    """Where the treasurer settles a charge held in doubt."""
    return f"/api/v1/admin/renewals/attempts/{attempt_id}/settle"


class PayPalLedger:
    """PayPal's own record of renewal orders, as the provider sees it.

    A create makes one order per ``PayPal-Request-Id`` and answers a repeated id with
    the order it made; :meth:`forget_ids` is the hours passing in which PayPal drops
    them.  Each of ``create_faults``, ``capture_faults`` and ``read_faults`` holds what
    the next calls of that kind do instead of answering: an HTTP status, or ``"timeout"``
    before PayPal acts.  New orders are ``COMPLETED`` with their capture unless
    ``approve_only`` is set, when they wait to be captured.  ``duplicate_invoice`` refuses
    every create as a duplicate of an invoice already paid.
    """

    def __init__(self) -> None:
        """Start with no orders and every call answering."""
        self.orders: dict[str, dict[str, Any]] = {}
        self.request_ids: dict[str, str] = {}
        self.create_faults: list[int | str] = []
        self.capture_faults: list[int | str] = []
        self.read_faults: list[int | str] = []
        self.approve_only = False
        self.duplicate_invoice = False
        self.bodies: list[dict[str, Any]] = []
        self.capture_changes: dict[str, Any] = {}
        self.capture_missing = False

    def made(self) -> int:
        """How many orders PayPal has made: the charges it could take."""
        return len(self.orders)

    def forget_ids(self) -> None:
        """Let PayPal drop the request ids it was holding."""
        self.request_ids.clear()

    def create(self, request: httpx.Request) -> httpx.Response:
        """Make or replay the order for the request's ``PayPal-Request-Id``.

        A ``"lost"`` fault makes or replays the order and then times out, which is
        PayPal having acted with the answer never reaching the scan.
        """
        is_lost = bool(self.create_faults) and self.create_faults[0] == "lost"
        if is_lost:
            self.create_faults.pop(0)
        fault = None if is_lost else self._fault(self.create_faults)
        if fault is not None:
            return fault
        answer = self._make(request)
        if is_lost:
            raise httpx.ReadTimeout("timed out")
        return answer

    def _make(self, request: httpx.Request) -> httpx.Response:
        """Make the order for the request's id, or answer with the one already made."""
        body = json.loads(request.content)
        self.bodies.append(body)
        if self.duplicate_invoice:
            return httpx.Response(
                422,
                json={
                    "name": "UNPROCESSABLE_ENTITY",
                    "details": [{"issue": "DUPLICATE_INVOICE_ID"}],
                },
            )
        request_id = request.headers["PayPal-Request-Id"]
        if request_id not in self.request_ids:
            order_id = f"ORDER-{len(self.orders) + 1}"
            unit = body["purchase_units"][0]
            self.orders[order_id] = {
                "id": order_id,
                "status": "APPROVED" if self.approve_only else "COMPLETED",
                "purchase_units": [
                    {
                        "payments": {
                            "captures": [] if self.approve_only else [self._capture(order_id, unit)]
                        },
                        "_unit": unit,
                    }
                ],
            }
            self.request_ids[request_id] = order_id
        return httpx.Response(201, json=self.orders[self.request_ids[request_id]])

    def capture(self, request: httpx.Request) -> httpx.Response:
        """Capture the order named in the path, once."""
        fault = self._fault(self.capture_faults)
        if fault is not None:
            return fault
        order = self.orders[order_id_in(request)]
        unit = order["purchase_units"][0]
        if not unit["payments"]["captures"]:
            unit["payments"]["captures"] = [self._capture(order["id"], unit["_unit"])]
        order["status"] = "COMPLETED"
        return httpx.Response(201, json=order)

    def read(self, request: httpx.Request) -> httpx.Response:
        """Answer with the order named in the path."""
        fault = self._fault(self.read_faults)
        if fault is not None:
            return fault
        return httpx.Response(200, json=self.orders[order_id_in(request)])

    def read_capture(self, request: httpx.Request) -> httpx.Response:
        """Answer with the one capture of the first order, as the dashboard shows it.

        ``capture_changes`` is laid over it, and ``capture_missing`` answers 404.
        """
        if self.capture_missing:
            return httpx.Response(404, json={"name": "RESOURCE_NOT_FOUND"})
        order = next(iter(self.orders.values()))
        capture = dict(order["purchase_units"][0]["payments"]["captures"][0])
        capture["supplementary_data"] = {"related_ids": {"order_id": order["id"]}}
        capture.update(self.capture_changes)
        return httpx.Response(200, json=capture)

    def _capture(self, order_id: str, unit: dict[str, Any]) -> dict[str, Any]:
        """A completed capture of ``unit``'s amount."""
        return {
            "id": CAPTURE_ID,
            "status": "COMPLETED",
            "custom_id": unit["custom_id"],
            "invoice_id": unit["invoice_id"],
            "amount": unit["amount"],
        }

    @staticmethod
    def _fault(faults: list[int | str]) -> httpx.Response | None:
        """The next fault queued, as the response it gives, or ``None``."""
        if not faults:
            return None
        fault = faults.pop(0)
        if fault == "timeout":
            raise httpx.ReadTimeout("timed out")
        if fault == "connect":
            raise httpx.ConnectError("refused")
        return httpx.Response(int(fault), json={})


def order_id_in(request: httpx.Request) -> str:
    """The order id in a ``/v2/checkout/orders/<id>[/capture]`` path."""
    match = re.search(r"/v2/checkout/orders/([^/]+)", request.url.path)
    assert match is not None
    return match.group(1)


@pytest.fixture
def ledger(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> Iterator[PayPalLedger]:
    """PayPal behind ``respx``, with no wait between retries and the claim timeout set."""
    settings.RENEWAL_STALE_MINUTES = STALE_MINUTES
    pauses: list[float] = []
    monkeypatch.setattr(paypal_provider, "pause", pauses.append)
    fake = PayPalLedger()
    with respx.mock(assert_all_called=False) as router:
        paypal_token(router)
        router.post(ORDERS).mock(side_effect=fake.create)
        router.post(url__regex=rf"{re.escape(ORDERS)}/[^/]+/capture").mock(side_effect=fake.capture)
        router.get(url__regex=rf"{re.escape(ORDERS)}/[^/]+$").mock(side_effect=fake.read)
        router.get(f"{PAYPAL_SANDBOX}/v2/payments/captures/{CAPTURE_ID}").mock(
            side_effect=fake.read_capture
        )
        router.get(f"{PAYPAL_SANDBOX}/v2/payments/captures/{OTHER_CAPTURE_ID}").mock(
            return_value=httpx.Response(
                200,
                json={
                    "id": OTHER_CAPTURE_ID,
                    "status": "COMPLETED",
                    "custom_id": "999999",
                    "amount": {"currency_code": "USD", "value": "45.00"},
                    "supplementary_data": {"related_ids": {"order_id": "ORDER-OTHER"}},
                },
            )
        )
        yield fake


def renewal_due(user: User, plan: MembershipPlan, today: date) -> RenewalMandate:
    """A PayPal renewal whose charge is due ``today``, its notice already sent."""
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
        provider=MandateProvider.PAYPAL,
        method_ref="vault_1",
        next_charge_on=today,
    )
    run_auto_renewals(today=today - timedelta(days=1))
    return mandate


def the_attempt() -> RenewalAttempt:
    """The one attempt the scan wrote."""
    return RenewalAttempt.objects.get(retry_of__isnull=True)


def held_in_doubt(ledger: PayPalLedger, member: User, plan: MembershipPlan, today: date) -> None:
    """Leave the member's renewal in doubt: PayPal answered none of the creates."""
    renewal_due(member, plan, today)
    ledger.create_faults = [503, "timeout", 503, 503]
    run_auto_renewals(today=today)


# --------------------------------------------------------------------------
# A create PayPal does not answer
# --------------------------------------------------------------------------
def test_a_create_paypal_answers_on_a_retry_is_charged_once(
    ledger: PayPalLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The scan asks again at once, under the same id, and the charge is recorded."""
    renewal_due(member, annual_plan, today)
    ledger.create_faults = [503, "timeout"]

    run_auto_renewals(today=today)

    assert the_attempt().outcome == RenewalOutcome.SUCCEEDED
    assert ledger.made() == 1


def test_a_create_paypal_never_answers_is_held_in_doubt(
    ledger: PayPalLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """With no order to look up, the attempt waits for a treasurer instead of a retry."""
    held_in_doubt(ledger, member, annual_plan, today)

    attempt = the_attempt()
    assert attempt.in_doubt is True
    assert attempt.outcome == RenewalOutcome.SCHEDULED


def test_a_charge_in_doubt_keeps_its_pending_payment(
    ledger: PayPalLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The payment is neither failed nor thrown away."""
    held_in_doubt(ledger, member, annual_plan, today)

    assert Payment.objects.get().status == PaymentStatus.PENDING


def test_a_charge_in_doubt_is_never_created_again(
    ledger: PayPalLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """Later scans, past PayPal's memory of the id, skip it rather than charge again."""
    held_in_doubt(ledger, member, annual_plan, today)
    ledger.forget_ids()
    created = len(ledger.bodies)

    run = run_auto_renewals(today=today)

    assert run.skipped_by_reason == {"in_doubt": 1}
    assert len(ledger.bodies) == created


def test_a_charge_in_doubt_costs_the_member_nothing(
    ledger: PayPalLedger,
    member: User,
    annual_plan: MembershipPlan,
    today: date,
    mailoutbox: list[EmailMessage],
) -> None:
    """No decline is counted and no email goes out about a charge nobody refused."""
    renewal_due(member, annual_plan, today)
    mailoutbox.clear()
    ledger.create_faults = [503, 503, 503, 503]

    run_auto_renewals(today=today)

    mandate = RenewalMandate.objects.get()
    assert mandate.failure_count == 0
    assert mailoutbox == []


def test_a_charge_in_doubt_is_flagged_to_the_treasurer_once(
    ledger: PayPalLedger,
    member: User,
    annual_plan: MembershipPlan,
    today: date,
    recorded_events: RecordedEvents,
) -> None:
    """One ``renewal_needs_checking`` event, however many scans skip it after."""
    held_in_doubt(ledger, member, annual_plan, today)

    run_auto_renewals(today=today)

    assert [slug for slug, _ in recorded_events].count("renewal_needs_checking") == 1


def test_an_order_paypal_calls_a_duplicate_invoice_is_in_doubt(
    ledger: PayPalLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """PayPal saying the invoice was paid is never read as a decline."""
    mandate = renewal_due(member, annual_plan, today)
    ledger.duplicate_invoice = True

    run_auto_renewals(today=today)

    mandate.refresh_from_db()
    assert the_attempt().in_doubt is True
    assert mandate.failure_count == 0


def test_every_renewal_order_carries_its_own_invoice_id(
    ledger: PayPalLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The invoice id lets PayPal itself refuse a second charge for one payment."""
    renewal_due(member, annual_plan, today)

    run_auto_renewals(today=today)

    payment = Payment.objects.get()
    invoice = ledger.bodies[0]["purchase_units"][0]["invoice_id"]
    assert invoice == f"caldart-renewal-{payment.pk}"


# --------------------------------------------------------------------------
# A scan that died during a create
# --------------------------------------------------------------------------
def sent_and_unanswered(member: User, plan: MembershipPlan, today: date, hours_ago: int) -> None:
    """Leave the renewal claimed by a dead scan that sent its create ``hours_ago``."""
    renewal_due(member, plan, today)
    attempt = the_attempt()
    payment = Payment.objects.create(
        user=member,
        plan=plan,
        amount_cents=plan.price_cents,
        plan_amount_cents=plan.price_cents,
        provider=MandateProvider.PAYPAL,
        charge_method_ref="vault_1",
        charge_sent_at=timezone.now() - timedelta(hours=hours_ago),
    )
    RenewalAttempt.objects.filter(pk=attempt.pk).update(
        payment=payment, attempted_at=timezone.now() - timedelta(minutes=STALE_MINUTES + 1)
    )


def test_a_create_sent_hours_ago_with_no_order_is_held_in_doubt(
    ledger: PayPalLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """Past the hours PayPal keeps the id a repeat could charge again, so none is sent."""
    sent_and_unanswered(member, annual_plan, today, hours_ago=6)

    run_auto_renewals(today=today)

    assert the_attempt().in_doubt is True
    assert ledger.bodies == []


def test_a_create_sent_recently_with_no_order_is_asked_for_again(
    ledger: PayPalLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """Inside those hours the same id brings back the order PayPal made, if any."""
    sent_and_unanswered(member, annual_plan, today, hours_ago=1)
    payment = Payment.objects.get()
    ledger.request_ids[f"caldart-renewal-{payment.pk}"] = "ORDER-1"
    ledger.orders["ORDER-1"] = {
        "id": "ORDER-1",
        "status": "COMPLETED",
        "purchase_units": [
            {
                "payments": {
                    "captures": [
                        {
                            "id": CAPTURE_ID,
                            "status": "COMPLETED",
                            "custom_id": str(payment.pk),
                            "amount": {
                                "currency_code": "USD",
                                "value": f"{payment.amount_cents / 100:.2f}",
                            },
                        }
                    ]
                }
            }
        ],
    }

    run_auto_renewals(today=today)

    assert the_attempt().outcome == RenewalOutcome.SUCCEEDED
    assert ledger.made() == 1


# --------------------------------------------------------------------------
# A capture or a read PayPal does not answer
# --------------------------------------------------------------------------
def test_a_capture_paypal_cannot_answer_is_put_off_with_its_order(
    ledger: PayPalLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """A 503 on the capture keeps the payment, naming its order, for the next scan."""
    renewal_due(member, annual_plan, today)
    ledger.approve_only = True
    ledger.capture_faults = [503]

    run = run_auto_renewals(today=today)

    assert run.skipped_by_reason == {"provider_down": 1}
    assert Payment.objects.get().provider_ref == "ORDER-1"


def test_a_capture_paypal_cannot_answer_is_taken_once_by_the_next_scan(
    ledger: PayPalLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The next scan reads the order back and captures it, making no second order."""
    renewal_due(member, annual_plan, today)
    ledger.approve_only = True
    ledger.capture_faults = [503]
    run_auto_renewals(today=today)
    ledger.forget_ids()

    run_auto_renewals(today=today)

    assert the_attempt().outcome == RenewalOutcome.SUCCEEDED
    assert ledger.made() == 1


def test_a_read_paypal_cannot_answer_is_put_off_again(
    ledger: PayPalLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """A 503 reading the order back fails nothing and makes no order."""
    renewal_due(member, annual_plan, today)
    ledger.approve_only = True
    ledger.capture_faults = [503]
    run_auto_renewals(today=today)
    ledger.read_faults = [503]

    run = run_auto_renewals(today=today)

    assert run.skipped_by_reason == {"provider_down": 1}
    assert Payment.objects.get().status == PaymentStatus.PENDING


def test_a_read_paypal_cannot_answer_is_settled_once_by_a_later_scan(
    ledger: PayPalLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """Once PayPal answers, the one order is captured and recorded."""
    renewal_due(member, annual_plan, today)
    ledger.approve_only = True
    ledger.capture_faults = [503]
    run_auto_renewals(today=today)
    ledger.read_faults = [503]
    run_auto_renewals(today=today)

    run_auto_renewals(today=today)

    assert the_attempt().outcome == RenewalOutcome.SUCCEEDED
    assert ledger.made() == 1


# --------------------------------------------------------------------------
# The treasurer settles a charge in doubt
# --------------------------------------------------------------------------
def made_but_unanswered(
    ledger: PayPalLedger, member: User, plan: MembershipPlan, today: date
) -> None:
    """Leave the renewal in doubt with an order PayPal did make: every answer was lost."""
    renewal_due(member, plan, today)
    ledger.create_faults = ["lost", "lost", "lost", "lost"]
    run_auto_renewals(today=today)


def test_a_treasurer_records_a_charge_in_doubt_as_paid(
    ledger: PayPalLedger,
    treasurer_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    today: date,
) -> None:
    """PayPal's capture id settles the attempt at once, as the scan would."""
    made_but_unanswered(ledger, member, annual_plan, today)

    response = treasurer_client.post(
        settle_url(the_attempt().pk), {"outcome": "paid", "reference": CAPTURE_ID}, format="json"
    )

    assert response.status_code == 200
    assert the_attempt().outcome == RenewalOutcome.SUCCEEDED
    assert ledger.made() == 1


def test_a_charge_recorded_as_paid_emails_the_member_its_renewal(
    ledger: PayPalLedger,
    treasurer_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    today: date,
    mailoutbox: list[EmailMessage],
) -> None:
    """The member hears about the charge once it is settled, as after any charge."""
    made_but_unanswered(ledger, member, annual_plan, today)
    mailoutbox.clear()

    treasurer_client.post(
        settle_url(the_attempt().pk), {"outcome": "paid", "reference": CAPTURE_ID}, format="json"
    )

    assert [str(m.subject).split(": ", 1)[1] for m in mailoutbox] == [
        "your membership has been renewed"
    ]


def test_a_treasurer_releases_a_charge_paypal_never_took(
    ledger: PayPalLedger,
    treasurer_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    today: date,
) -> None:
    """Released, the next scan charges the same payment, and PayPal takes it once."""
    held_in_doubt(ledger, member, annual_plan, today)
    treasurer_client.post(settle_url(the_attempt().pk), {"outcome": "released"}, format="json")

    run_auto_renewals(today=today)

    assert the_attempt().outcome == RenewalOutcome.SUCCEEDED
    assert ledger.made() == 1


def test_a_capture_of_another_payment_settles_nothing(
    ledger: PayPalLedger,
    treasurer_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    today: date,
) -> None:
    """A capture id that belongs elsewhere is refused, and the attempt stays in doubt."""
    held_in_doubt(ledger, member, annual_plan, today)

    response = treasurer_client.post(
        settle_url(the_attempt().pk),
        {"outcome": "paid", "reference": OTHER_CAPTURE_ID},
        format="json",
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "That PayPal capture belongs to another payment."}
    assert the_attempt().in_doubt is True


def test_a_charge_not_in_doubt_cannot_be_settled(
    ledger: PayPalLedger,
    treasurer_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    today: date,
) -> None:
    """Only a charge held for a treasurer is the treasurer's to settle."""
    renewal_due(member, annual_plan, today)

    response = treasurer_client.post(
        settle_url(the_attempt().pk), {"outcome": "released"}, format="json"
    )

    assert response.status_code == 400
    assert response.json() == {"attempt": ["This charge is not waiting to be checked."]}


def test_paid_needs_the_providers_reference(
    ledger: PayPalLedger,
    treasurer_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    today: date,
) -> None:
    """Recording a charge as paid without PayPal's id for it is refused."""
    held_in_doubt(ledger, member, annual_plan, today)

    response = treasurer_client.post(
        settle_url(the_attempt().pk), {"outcome": "paid"}, format="json"
    )

    assert response.status_code == 400
    assert response.json() == {"reference": ["Give the payment provider's id for the charge."]}


def test_settling_writes_an_audit_record(
    ledger: PayPalLedger,
    treasurer_client: APIClient,
    treasurer: User,
    member: User,
    annual_plan: MembershipPlan,
    today: date,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """The record names the treasurer and says whether the charge was paid."""
    held_in_doubt(ledger, member, annual_plan, today)

    treasurer_client.post(settle_url(the_attempt().pk), {"outcome": "released"}, format="json")

    attempt = the_attempt()
    expected = (
        f"action=renewal.settle actor={treasurer.pk} target={member.pk} "
        f"attempt={attempt.pk} payment={attempt.payment_id} outcome=released reference=-"
    )
    assert expected in audit_messages(audit_log)


@pytest.mark.parametrize(("role", "allowed"), role_matrix(TREASURER, ACCOUNT_ADMIN, SYSTEM_ADMIN))
def test_only_the_finance_roles_settle_a_charge(
    ledger: PayPalLedger,
    api_client: APIClient,
    all_role_users: dict[str, User],
    member: User,
    annual_plan: MembershipPlan,
    today: date,
    role: str,
    allowed: bool,
) -> None:
    """A role outside finance is refused before anything is read."""
    held_in_doubt(ledger, member, annual_plan, today)
    api_client.force_login(all_role_users[role])

    response = api_client.post(settle_url(the_attempt().pk), {"outcome": "released"}, format="json")

    assert (response.status_code == 403) is not allowed


def test_the_treasurer_is_told_why_a_charge_needs_checking(
    ledger: PayPalLedger,
    member: User,
    annual_plan: MembershipPlan,
    today: date,
    recorded_events: RecordedEvents,
) -> None:
    """The notification names the amount, the provider, and the reason in its lines."""
    held_in_doubt(ledger, member, annual_plan, today)
    (payload,) = [payload for slug, payload in recorded_events if slug == "renewal_needs_checking"]

    message = build_message("renewal_needs_checking", payload)

    assert dict(message.lines)["Why"] == paypal_provider.UNANSWERED_MESSAGE


# --------------------------------------------------------------------------
# Any answer after silence is doubt; PayPal refusing CalDART is never a decline
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "refusal", [422, 401, 403], ids=["in-progress", "unauthorized", "forbidden"]
)
def test_a_refusal_after_an_unanswered_try_is_held_in_doubt(
    ledger: PayPalLedger, member: User, annual_plan: MembershipPlan, today: date, refusal: int
) -> None:
    """PayPal may hold the first order, so a later refusal is never a decline."""
    mandate = renewal_due(member, annual_plan, today)
    ledger.create_faults = ["lost", refusal]

    run_auto_renewals(today=today)

    mandate.refresh_from_db()
    assert the_attempt().in_doubt is True
    assert mandate.failure_count == 0


def test_a_refusal_after_an_unanswered_try_takes_nothing_twice(
    ledger: PayPalLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """No later scan makes a second order for the payment held in doubt."""
    renewal_due(member, annual_plan, today)
    ledger.create_faults = ["lost", 422]
    run_auto_renewals(today=today)
    ledger.forget_ids()

    run_auto_renewals(today=today)
    run_auto_renewals(today=today + timedelta(days=1))

    assert ledger.made() == 1


@pytest.mark.parametrize("refusal", [401, 403], ids=["unauthorized", "forbidden"])
def test_paypal_refusing_caldart_on_the_first_try_is_put_off(
    ledger: PayPalLedger, member: User, annual_plan: MembershipPlan, today: date, refusal: int
) -> None:
    """PayPal refusing our credentials says nothing about the member's account."""
    mandate = renewal_due(member, annual_plan, today)
    ledger.create_faults = [refusal]

    run = run_auto_renewals(today=today)

    mandate.refresh_from_db()
    assert run.skipped_by_reason == {"provider_down": 1}
    assert mandate.failure_count == 0


def test_paypal_refusing_caldart_on_a_read_is_put_off(
    ledger: PayPalLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """A 401 reading the order back is an outage, not the member's decline."""
    mandate = renewal_due(member, annual_plan, today)
    ledger.approve_only = True
    ledger.capture_faults = [503]
    run_auto_renewals(today=today)
    ledger.read_faults = [401]

    run = run_auto_renewals(today=today)

    mandate.refresh_from_db()
    assert run.skipped_by_reason == {"provider_down": 1}
    assert mandate.failure_count == 0


# --------------------------------------------------------------------------
# A PayPal that is down altogether
# --------------------------------------------------------------------------
def test_a_create_that_never_left_is_put_off_not_held(
    ledger: PayPalLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """A connection never made didn't take anything, so no charge waits for checking."""
    renewal_due(member, annual_plan, today)
    ledger.create_faults = ["connect"]

    run = run_auto_renewals(today=today)

    assert run.skipped_by_reason == {"provider_down": 1}
    assert the_attempt().in_doubt is False


def test_a_token_paypal_will_not_give_is_put_off_not_held(
    member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """With no token nothing was sent, so the charge simply waits for the next run."""
    renewal_due(member, annual_plan, today)
    with respx.mock as router:
        router.post(f"{PAYPAL_SANDBOX}/v1/oauth2/token").mock(return_value=httpx.Response(503))
        run = run_auto_renewals(today=today)

    assert run.skipped_by_reason == {"provider_down": 1}
    assert Payment.objects.count() == 0


def second_renewal_due(plan: MembershipPlan, today: date) -> User:
    """Another member whose PayPal renewal falls due ``today``."""
    other = UserFactory()
    renewal_due(other, plan, today)
    return other


def test_after_one_create_goes_unanswered_the_rest_wait_unsent(
    ledger: PayPalLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The first charge is held in doubt; the second is put off, never sent."""
    renewal_due(member, annual_plan, today)
    second_renewal_due(annual_plan, today)
    ledger.create_faults = [503, 503, 503, 503]

    run = run_auto_renewals(today=today)

    assert run.skipped_by_reason == {"in_doubt": 1, "provider_down": 1}
    assert RenewalAttempt.objects.filter(in_doubt=True).count() == 1


def test_a_charge_the_breaker_put_off_is_not_stamped_as_sent(
    ledger: PayPalLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """Never sent, the second charge cannot later be mistaken for one in doubt."""
    renewal_due(member, annual_plan, today)
    second_renewal_due(annual_plan, today)
    ledger.create_faults = [503, 503, 503, 503]

    run_auto_renewals(today=today)

    assert Payment.objects.filter(charge_sent_at__isnull=False).count() == 1


def test_the_retries_stop_at_their_deadline(
    ledger: PayPalLedger,
    monkeypatch: pytest.MonkeyPatch,
    member: User,
    annual_plan: MembershipPlan,
    today: date,
) -> None:
    """A clock past the deadline stops the asking, and the charge is held in doubt."""
    readings = iter([0.0, paypal_provider.CREATE_DEADLINE_SECONDS])
    monkeypatch.setattr(paypal_provider, "clock", lambda: next(readings, 10_000.0))
    renewal_due(member, annual_plan, today)
    ledger.create_faults = [503, 503, 503, 503]

    run_auto_renewals(today=today)

    assert len(ledger.create_faults) == 3
    assert the_attempt().in_doubt is True


# --------------------------------------------------------------------------
# A charge in doubt never lapses silently
# --------------------------------------------------------------------------
def test_a_release_held_in_doubt_again_is_flagged_again(
    ledger: PayPalLedger,
    treasurer_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    today: date,
    recorded_events: RecordedEvents,
) -> None:
    """Settling clears the flag, so the next hold tells the treasurer again."""
    held_in_doubt(ledger, member, annual_plan, today)
    treasurer_client.post(settle_url(the_attempt().pk), {"outcome": "released"}, format="json")
    ledger.create_faults = [503, 503, 503, 503]

    run_auto_renewals(today=today)

    assert the_attempt().in_doubt is True
    assert [slug for slug, _ in recorded_events].count("renewal_needs_checking") == 2


def test_a_charge_still_in_doubt_when_the_term_ends_is_flagged_again(
    ledger: PayPalLedger,
    member: User,
    annual_plan: MembershipPlan,
    today: date,
    recorded_events: RecordedEvents,
) -> None:
    """Once the membership runs out the treasurer is told again, once."""
    held_in_doubt(ledger, member, annual_plan, today)

    with freezegun.freeze_time(timezone.now() + timedelta(days=2)):
        run_auto_renewals(today=today + timedelta(days=2))
        run_auto_renewals(today=today + timedelta(days=3))

    assert [slug for slug, _ in recorded_events].count("renewal_needs_checking") == 2


def test_the_daily_run_fails_while_a_charge_waits_to_be_checked(
    ledger: PayPalLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The timer's unit goes to failed every morning until somebody settles it."""
    held_in_doubt(ledger, member, annual_plan, today)

    with pytest.raises(CommandError, match="1 renewal charge needs checking"):
        call_command("run_auto_renewals", today=today.isoformat(), stdout=StringIO())


def test_a_charge_in_doubt_whose_payment_succeeded_settles_itself(
    ledger: PayPalLedger, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """A payment marked paid meanwhile answers the doubt, and the attempt is closed."""
    held_in_doubt(ledger, member, annual_plan, today)
    mark_succeeded(Payment.objects.get(), provider_ref="ORDER-1")

    run_auto_renewals(today=today)

    assert the_attempt().outcome == RenewalOutcome.SUCCEEDED


# --------------------------------------------------------------------------
# Settling: replays, closing, and what PayPal says about the capture
# --------------------------------------------------------------------------
def test_settling_again_after_paid_changes_nothing(
    ledger: PayPalLedger,
    treasurer_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    today: date,
) -> None:
    """A second press finds nothing in doubt, and no second charge is recorded."""
    made_but_unanswered(ledger, member, annual_plan, today)
    body = {"outcome": "paid", "reference": CAPTURE_ID}
    treasurer_client.post(settle_url(the_attempt().pk), body, format="json")

    response = treasurer_client.post(settle_url(the_attempt().pk), body, format="json")

    assert response.status_code == 400
    assert Payment.objects.filter(status=PaymentStatus.SUCCEEDED).count() == 1


def test_a_treasurer_closes_a_charge_as_failed(
    ledger: PayPalLedger,
    treasurer_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    today: date,
    mailoutbox: list[EmailMessage],
) -> None:
    """Closed, it isn't charged, the renewal is paused, and the member is told so."""
    held_in_doubt(ledger, member, annual_plan, today)
    mailoutbox.clear()

    treasurer_client.post(settle_url(the_attempt().pk), {"outcome": "failed"}, format="json")

    assert the_attempt().outcome == RenewalOutcome.FAILED
    assert RenewalMandate.objects.get().status == MandateStatus.PAUSED
    assert Payment.objects.get().status == PaymentStatus.FAILED
    assert [str(m.subject).split(": ", 1)[1] for m in mailoutbox] == [
        "we could not renew your membership"
    ]


def test_a_closed_charge_is_never_created_again(
    ledger: PayPalLedger,
    treasurer_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    today: date,
) -> None:
    """The paused renewal charges nothing on the next run."""
    held_in_doubt(ledger, member, annual_plan, today)
    treasurer_client.post(settle_url(the_attempt().pk), {"outcome": "failed"}, format="json")

    run_auto_renewals(today=today + timedelta(days=1))

    assert ledger.bodies == []


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        (
            {"amount": {"currency_code": "USD", "value": "1.00"}},
            "That PayPal capture is for another amount.",
        ),
        (
            {"amount_currency": "EUR"},
            "That PayPal capture is in another currency.",
        ),
        ({"status": "PENDING"}, "That PayPal capture has not completed."),
        ({"supplementary_data": {}}, "PayPal doesn't name an order for that capture."),
    ],
    ids=["amount", "currency", "not-completed", "no-order"],
)
def test_a_capture_that_does_not_match_settles_nothing(
    ledger: PayPalLedger,
    treasurer_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    today: date,
    changes: dict[str, Any],
    message: str,
) -> None:
    """Each check on the capture refuses it by name, and the charge stays in doubt."""
    made_but_unanswered(ledger, member, annual_plan, today)
    if "amount_currency" in changes:
        payment = Payment.objects.get()
        changes = {"amount": {"currency_code": "EUR", "value": f"{payment.amount_cents / 100:.2f}"}}
    ledger.capture_changes = changes

    response = treasurer_client.post(
        settle_url(the_attempt().pk), {"outcome": "paid", "reference": CAPTURE_ID}, format="json"
    )

    assert response.json() == {"detail": message}
    assert the_attempt().in_doubt is True


def test_a_capture_paypal_has_no_record_of_settles_nothing(
    ledger: PayPalLedger,
    treasurer_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    today: date,
) -> None:
    """A 404 from PayPal is refused, naming the id the treasurer gave."""
    made_but_unanswered(ledger, member, annual_plan, today)
    ledger.capture_missing = True

    response = treasurer_client.post(
        settle_url(the_attempt().pk), {"outcome": "paid", "reference": CAPTURE_ID}, format="json"
    )

    assert response.json() == {"detail": f"PayPal doesn't have a capture {CAPTURE_ID}."}


@pytest.mark.parametrize("outcome", ["released", "failed"])
def test_a_payment_already_through_can_only_be_recorded_as_paid(
    ledger: PayPalLedger,
    treasurer_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    today: date,
    outcome: str,
) -> None:
    """Releasing or closing a charge whose money arrived would lose it; both refuse."""
    held_in_doubt(ledger, member, annual_plan, today)
    mark_succeeded(Payment.objects.get(), provider_ref="ORDER-1")

    response = treasurer_client.post(
        settle_url(the_attempt().pk), {"outcome": outcome}, format="json"
    )

    assert response.status_code == 400
    assert response.json() == {"outcome": [ALREADY_PAID_MESSAGE]}
    assert the_attempt().in_doubt is True
