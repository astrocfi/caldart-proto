"""Stripe: PaymentIntent creation, server-side confirmation and webhooks.

Stripe itself is never called: ``stripe.PaymentIntent.create/retrieve`` and
``stripe.Webhook.construct_event`` are patched, which is exactly the seam the
real integration uses.
"""

from __future__ import annotations

import json

import pytest
import stripe

from apps.members.models import Membership
from apps.payments.models import Payment, PaymentProvider, PaymentStatus, PaymentWallet
from apps.payments.providers import get_provider
from apps.payments.providers.stripe import wallet_from_intent
from apps.payments.services import create_checkout

pytestmark = pytest.mark.django_db

CHECKOUT = "/api/v1/payments/checkout"
CONFIRM = "/api/v1/payments/stripe/confirm"
WEBHOOK = "/api/v1/payments/stripe/webhook"


@pytest.fixture(autouse=True)
def _stripe_configured(settings):
    settings.STRIPE_SECRET_KEY = "sk_test_123"
    settings.STRIPE_PUBLISHABLE_KEY = "pk_test_123"
    settings.STRIPE_WEBHOOK_SECRET = "whsec_test"  # noqa: S105 - test fixture
    settings.PAYMENTS_MOCK_ENABLED = True


def intent_payload(payment: Payment, **overrides) -> dict:
    """A PaymentIntent as Stripe would return it, expanded on latest_charge."""
    payload = {
        "id": payment.provider_ref or "pi_test_1",
        "object": "payment_intent",
        "status": "succeeded",
        "amount": payment.amount_cents,
        "currency": payment.currency,
        "metadata": {
            "payment_id": str(payment.pk),
            "user_id": str(payment.user_id),
            "plan": payment.plan.slug if payment.plan_id else "",
        },
        "latest_charge": {
            "id": "ch_test_1",
            "payment_method_details": {"type": "card", "card": {"brand": "visa", "wallet": None}},
        },
    }
    payload.update(overrides)
    return payload


class FakeIntents:
    """Stand-in for ``stripe.PaymentIntent`` that records what it was asked."""

    def __init__(self, payload: dict | None = None):
        self.payload = payload or {}
        self.created: dict = {}
        self.retrieved: dict = {}

    def create(self, **kwargs):
        self.created = kwargs
        return {
            "id": "pi_test_created",
            "client_secret": "pi_test_created_secret_abc",
            "status": "requires_payment_method",
            "amount": kwargs["amount"],
            "currency": kwargs["currency"],
            "metadata": kwargs["metadata"],
        }

    def retrieve(self, intent_id, **kwargs):
        self.retrieved = {"id": intent_id, **kwargs}
        return self.payload


@pytest.fixture
def fake_intents(monkeypatch):
    fake = FakeIntents()
    monkeypatch.setattr(stripe.PaymentIntent, "create", fake.create)
    monkeypatch.setattr(stripe.PaymentIntent, "retrieve", fake.retrieve)
    return fake


# --------------------------------------------------------------------------
# start: creating the PaymentIntent
# --------------------------------------------------------------------------
def test_checkout_creates_a_payment_intent(api_client, member, annual_plan, fake_intents):
    api_client.force_login(member)
    response = api_client.post(
        CHECKOUT, {"plan": "annual", "contribution_cents": 10_000, "provider": "stripe"}
    )

    assert response.status_code == 201
    assert response.data["client"]["client_secret"] == "pi_test_created_secret_abc"

    created = fake_intents.created
    payment = Payment.objects.get(pk=response.data["payment_id"])
    assert created["amount"] == 14_500 == payment.amount_cents
    assert created["currency"] == "usd"
    assert created["automatic_payment_methods"] == {"enabled": True}
    assert created["receipt_email"] == member.email
    assert created["metadata"] == {
        "payment_id": str(payment.pk),
        "user_id": str(member.pk),
        "plan": "annual",
    }
    assert created["api_key"] == "sk_test_123"
    assert payment.provider_ref == "pi_test_created"


def test_start_without_a_secret_key_is_a_400(api_client, member, annual_plan, settings):
    settings.STRIPE_SECRET_KEY = ""
    api_client.force_login(member)
    response = api_client.post(
        CHECKOUT, {"plan": "annual", "contribution_cents": 0, "provider": "stripe"}
    )
    # available_providers() drops Stripe entirely without both keys.
    assert response.status_code == 400
    assert Payment.objects.count() == 0


# --------------------------------------------------------------------------
# confirm
# --------------------------------------------------------------------------
def test_confirm_activates_the_membership(api_client, member, annual_plan, fake_intents):
    payment = create_checkout(member, "annual", 2_000, PaymentProvider.STRIPE)
    payment.provider_ref = "pi_test_1"
    payment.save(update_fields=["provider_ref"])
    fake_intents.payload = intent_payload(payment)

    api_client.force_login(member)
    response = api_client.post(
        CONFIRM, {"payment_id": payment.pk, "payment_intent_id": "pi_test_1"}
    )

    assert response.status_code == 200
    assert response.data["status"] == "succeeded"
    assert response.data["membership"]["status"] == "current"
    assert fake_intents.retrieved["expand"] == ["latest_charge"]

    payment.refresh_from_db()
    assert payment.wallet == PaymentWallet.CARD
    assert payment.completed_at is not None
    assert Membership.objects.filter(payment=payment).count() == 1


@pytest.mark.parametrize(
    ("wallet_type", "expected"),
    [
        ("apple_pay", PaymentWallet.APPLE_PAY),
        ("google_pay", PaymentWallet.GOOGLE_PAY),
        ("link", PaymentWallet.LINK),
        (None, PaymentWallet.CARD),
    ],
)
def test_wallet_is_read_from_the_charge(
    api_client, member, annual_plan, fake_intents, wallet_type, expected
):
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    payload = intent_payload(payment, id="pi_wallet")
    payload["latest_charge"]["payment_method_details"]["card"]["wallet"] = (
        {"type": wallet_type} if wallet_type else None
    )
    fake_intents.payload = payload

    api_client.force_login(member)
    api_client.post(CONFIRM, {"payment_id": payment.pk, "payment_intent_id": "pi_wallet"})

    payment.refresh_from_db()
    assert payment.wallet == expected


def test_wallet_is_unknown_without_a_charge():
    assert wallet_from_intent({"id": "pi", "latest_charge": None}) == PaymentWallet.UNKNOWN
    assert wallet_from_intent({"id": "pi", "latest_charge": "ch_1"}) == PaymentWallet.UNKNOWN


def test_confirm_rejects_an_amount_mismatch(api_client, member, annual_plan, fake_intents):
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    fake_intents.payload = intent_payload(payment, id="pi_cheap", amount=100)

    api_client.force_login(member)
    response = api_client.post(CONFIRM, {"payment_id": payment.pk, "payment_intent_id": "pi_cheap"})

    assert response.status_code == 400
    assert "amount" in str(response.data).lower()
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.PENDING
    assert Membership.objects.count() == 0


def test_confirm_rejects_a_currency_mismatch(api_client, member, annual_plan, fake_intents):
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    fake_intents.payload = intent_payload(payment, id="pi_eur", currency="eur")

    api_client.force_login(member)
    response = api_client.post(CONFIRM, {"payment_id": payment.pk, "payment_intent_id": "pi_eur"})

    assert response.status_code == 400
    assert Membership.objects.count() == 0


def test_confirm_rejects_metadata_for_another_payment(
    api_client, member, annual_plan, fake_intents
):
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    other = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    payload = intent_payload(payment, id="pi_wrong_meta")
    payload["metadata"]["payment_id"] = str(other.pk)
    fake_intents.payload = payload

    api_client.force_login(member)
    response = api_client.post(
        CONFIRM, {"payment_id": payment.pk, "payment_intent_id": "pi_wrong_meta"}
    )

    assert response.status_code == 400
    assert Membership.objects.count() == 0


def test_confirm_marks_a_cancelled_intent_failed(api_client, member, annual_plan, fake_intents):
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    fake_intents.payload = intent_payload(payment, id="pi_dead", status="canceled")

    api_client.force_login(member)
    response = api_client.post(CONFIRM, {"payment_id": payment.pk, "payment_intent_id": "pi_dead"})

    assert response.status_code == 200
    assert response.data["status"] == "failed"
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.FAILED
    assert Membership.objects.count() == 0


def test_confirm_rejects_an_intent_still_processing(api_client, member, annual_plan, fake_intents):
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    fake_intents.payload = intent_payload(payment, id="pi_wait", status="processing")

    api_client.force_login(member)
    response = api_client.post(CONFIRM, {"payment_id": payment.pk, "payment_intent_id": "pi_wait"})

    assert response.status_code == 400
    assert Membership.objects.count() == 0


def test_confirm_rejects_an_intent_bound_to_another_payment(
    api_client, member, annual_plan, fake_intents
):
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    payment.provider_ref = "pi_ours"
    payment.save(update_fields=["provider_ref"])
    fake_intents.payload = intent_payload(payment)

    api_client.force_login(member)
    response = api_client.post(
        CONFIRM, {"payment_id": payment.pk, "payment_intent_id": "pi_theirs"}
    )
    assert response.status_code == 400


def test_confirm_rejects_someone_elses_payment(
    api_client, member, user_factory, annual_plan, fake_intents
):
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    fake_intents.payload = intent_payload(payment, id="pi_x")

    api_client.force_login(user_factory(email="thief@example.test", roles=["member"]))
    response = api_client.post(CONFIRM, {"payment_id": payment.pk, "payment_intent_id": "pi_x"})
    assert response.status_code == 404


def test_confirm_rejects_a_paypal_payment(api_client, member, annual_plan, fake_intents):
    payment = create_checkout(member, "annual", 0, PaymentProvider.PAYPAL)
    api_client.force_login(member)
    response = api_client.post(CONFIRM, {"payment_id": payment.pk, "payment_intent_id": "pi_x"})
    assert response.status_code == 400


def test_confirm_requires_a_session(api_client, member, annual_plan):
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    assert api_client.post(CONFIRM, {"payment_id": payment.pk}).status_code == 401


def test_confirm_is_idempotent(api_client, member, annual_plan, fake_intents):
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    fake_intents.payload = intent_payload(payment, id="pi_twice")

    api_client.force_login(member)
    body = {"payment_id": payment.pk, "payment_intent_id": "pi_twice"}
    assert api_client.post(CONFIRM, body).status_code == 200
    assert api_client.post(CONFIRM, body).status_code == 200
    assert Membership.objects.filter(user=member).count() == 1


# --------------------------------------------------------------------------
# webhook
# --------------------------------------------------------------------------
def stub_construct_event(monkeypatch, event: dict | None, *, valid: bool = True):
    def construct_event(payload, signature, secret):
        if not valid:
            raise stripe.SignatureVerificationError("bad signature", signature)
        assert secret == "whsec_test"
        return event

    monkeypatch.setattr(stripe.Webhook, "construct_event", construct_event)


def post_webhook(client, body: dict | None = None):
    return client.post(
        WEBHOOK,
        data=json.dumps(body or {}),
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE="t=1,v1=deadbeef",
    )


def test_webhook_rejects_a_bad_signature(api_client, member, annual_plan, monkeypatch):
    stub_construct_event(monkeypatch, None, valid=False)
    response = post_webhook(api_client)
    assert response.status_code == 400
    assert "signature" in json.loads(response.content)["detail"].lower()


def test_webhook_activates_on_payment_intent_succeeded(
    api_client, member, annual_plan, monkeypatch
):
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    event = {
        "type": "payment_intent.succeeded",
        "data": {"object": intent_payload(payment, id="pi_hook")},
    }
    stub_construct_event(monkeypatch, event)

    response = post_webhook(api_client)
    assert response.status_code == 200
    assert json.loads(response.content)["handled"] is True

    payment.refresh_from_db()
    assert payment.status == PaymentStatus.SUCCEEDED
    assert payment.provider_ref == "pi_hook"
    assert Membership.objects.filter(payment=payment).count() == 1


def test_webhook_after_confirm_is_a_no_op(
    api_client, member, annual_plan, monkeypatch, fake_intents
):
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    fake_intents.payload = intent_payload(payment, id="pi_both")

    api_client.force_login(member)
    api_client.post(CONFIRM, {"payment_id": payment.pk, "payment_intent_id": "pi_both"})
    payment.refresh_from_db()
    completed_at = payment.completed_at

    api_client.logout()
    stub_construct_event(
        monkeypatch,
        {
            "type": "payment_intent.succeeded",
            "data": {"object": intent_payload(payment, id="pi_both")},
        },
    )
    assert post_webhook(api_client).status_code == 200

    payment.refresh_from_db()
    assert payment.completed_at == completed_at
    assert Membership.objects.filter(user=member).count() == 1


def test_webhook_marks_a_failure(api_client, member, annual_plan, monkeypatch):
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    stub_construct_event(
        monkeypatch,
        {
            "type": "payment_intent.payment_failed",
            "data": {
                "object": intent_payload(payment, id="pi_fail", status="requires_payment_method")
            },
        },
    )

    assert post_webhook(api_client).status_code == 200
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.FAILED
    assert Membership.objects.count() == 0


def test_webhook_refuses_an_amount_that_does_not_match(
    api_client, member, annual_plan, monkeypatch
):
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    stub_construct_event(
        monkeypatch,
        {
            "type": "payment_intent.succeeded",
            "data": {"object": intent_payload(payment, id="pi_cheap", amount=1)},
        },
    )

    response = post_webhook(api_client)
    assert response.status_code == 200
    assert json.loads(response.content)["handled"] is False
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.PENDING


def test_webhook_ignores_an_unknown_payment(api_client, member, annual_plan, monkeypatch):
    stub_construct_event(
        monkeypatch,
        {
            "type": "payment_intent.succeeded",
            "data": {"object": {"id": "pi_nobody", "metadata": {"payment_id": "424242"}}},
        },
    )
    response = post_webhook(api_client)
    assert response.status_code == 200
    assert json.loads(response.content)["handled"] is False


def test_webhook_ignores_uninteresting_events(api_client, member, annual_plan, monkeypatch):
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    stub_construct_event(
        monkeypatch,
        {"type": "charge.refunded", "data": {"object": intent_payload(payment, id="pi_ref")}},
    )
    response = post_webhook(api_client)
    assert json.loads(response.content)["handled"] is False
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.PENDING


def test_webhook_finds_the_payment_by_provider_ref(api_client, member, annual_plan, monkeypatch):
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    payment.provider_ref = "pi_by_ref"
    payment.save(update_fields=["provider_ref"])

    intent = intent_payload(payment, id="pi_by_ref")
    intent["metadata"] = {}
    stub_construct_event(
        monkeypatch, {"type": "payment_intent.succeeded", "data": {"object": intent}}
    )

    response = post_webhook(api_client)
    # Metadata is missing, so verification refuses to activate: the row is
    # found, but nothing is granted on an unverifiable event.
    assert json.loads(response.content)["handled"] is False
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.PENDING


def test_webhook_needs_no_session_or_csrf(api_client, member, annual_plan, monkeypatch):
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    stub_construct_event(
        monkeypatch,
        {
            "type": "payment_intent.succeeded",
            "data": {"object": intent_payload(payment, id="pi_anon")},
        },
    )
    api_client.logout()
    assert post_webhook(api_client).status_code == 200


def test_stripe_provider_is_registered():
    assert get_provider("stripe").slug == "stripe"
