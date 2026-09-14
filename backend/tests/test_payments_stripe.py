"""Stripe: PaymentIntent creation, server-side confirmation and webhooks.

Stripe itself is never called.  ``stripe_client`` is replaced by a fake whose
``v1.payment_intents`` service answers with real ``stripe.PaymentIntent``
objects, so the provider is exercised against the types the SDK actually
returns.  Webhook payloads are signed with the configured secret exactly as
Stripe signs them, so the library's own ``construct_event`` verifies every
delivery.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from types import SimpleNamespace

import pytest
import stripe

from apps.members.models import Membership
from apps.payments.models import Payment, PaymentProvider, PaymentStatus, PaymentWallet
from apps.payments.providers import get_provider
from apps.payments.providers import stripe as stripe_provider
from apps.payments.providers.stripe import wallet_from_intent
from apps.payments.services import create_checkout

pytestmark = pytest.mark.django_db

CHECKOUT = "/api/v1/payments/checkout"
CONFIRM = "/api/v1/payments/stripe/confirm"
WEBHOOK = "/api/v1/payments/stripe/webhook"

SECRET_KEY = "sk_test_123"  # noqa: S105 - test fixture
WEBHOOK_SECRET = "whsec_test"  # noqa: S105 - test fixture

#: Stripe's own default signature tolerance, in seconds.
SIGNATURE_TOLERANCE_SECONDS = 300


@pytest.fixture(autouse=True)
def _stripe_configured(settings):
    settings.STRIPE_SECRET_KEY = SECRET_KEY
    settings.STRIPE_PUBLISHABLE_KEY = "pk_test_123"
    settings.STRIPE_WEBHOOK_SECRET = WEBHOOK_SECRET
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
            "object": "charge",
            "payment_method_details": {"type": "card", "card": {"brand": "visa", "wallet": None}},
        },
    }
    payload.update(overrides)
    return payload


def intent_object(payload: dict) -> stripe.PaymentIntent:
    """The same payload as the SDK object a real call would return."""
    return stripe.PaymentIntent.construct_from(payload, SECRET_KEY)


def fake_stripe_client(payment_intents) -> SimpleNamespace:
    """A stand-in for ``stripe.StripeClient`` exposing one service."""
    return SimpleNamespace(v1=SimpleNamespace(payment_intents=payment_intents))


class FakeIntents:
    """Stand-in for ``v1.payment_intents`` that records what it was asked."""

    def __init__(self, payload: dict | None = None):
        self.payload = payload or {}
        self.api_key = ""
        self.created: dict = {}
        self.create_options: dict = {}
        self.retrieved: dict = {}

    def create(self, params, options=None):
        self.created = params
        self.create_options = options or {}
        return intent_object(
            {
                "id": "pi_test_created",
                "object": "payment_intent",
                "client_secret": "pi_test_created_secret_abc",
                "status": "requires_payment_method",
                "amount": params["amount"],
                "currency": params["currency"],
                "metadata": params["metadata"],
            }
        )

    def retrieve(self, intent_id, params=None, options=None):
        self.retrieved = {"id": intent_id, **(params or {})}
        return intent_object(self.payload)


@pytest.fixture
def fake_intents(monkeypatch):
    fake = FakeIntents()

    def client():
        # Through the real key lookup, so a missing key still refuses.
        fake.api_key = stripe_provider.secret_key()
        return fake_stripe_client(fake)

    monkeypatch.setattr(stripe_provider, "stripe_client", client)
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
    assert fake_intents.api_key == SECRET_KEY
    assert payment.provider_ref == "pi_test_created"


def test_start_stores_the_intent_as_a_dict(api_client, member, annual_plan, fake_intents):
    api_client.force_login(member)
    response = api_client.post(
        CHECKOUT, {"plan": "annual", "contribution_cents": 0, "provider": "stripe"}
    )

    payment = Payment.objects.get(pk=response.data["payment_id"])
    assert isinstance(payment.raw, dict)
    assert payment.raw["id"] == "pi_test_created"


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


def test_confirm_stores_the_intent_as_a_dict(api_client, member, annual_plan, fake_intents):
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    fake_intents.payload = intent_payload(payment, id="pi_raw")

    api_client.force_login(member)
    api_client.post(CONFIRM, {"payment_id": payment.pk, "payment_intent_id": "pi_raw"})

    payment.refresh_from_db()
    assert isinstance(payment.raw, dict)
    assert payment.raw["latest_charge"]["id"] == "ch_test_1"


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


def test_wallet_is_unknown_for_an_unexpanded_charge():
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


def test_confirm_marks_a_canceled_intent_failed(api_client, member, annual_plan, fake_intents):
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
def sign_stripe_payload(
    payload: str, *, secret: str = WEBHOOK_SECRET, timestamp: int | None = None
) -> str:
    """The ``Stripe-Signature`` header Stripe would send for ``payload``.

    The scheme is ``t=<unix seconds>,v1=<hex HMAC-SHA256 of "<t>.<payload>">``,
    keyed on the endpoint's signing secret.
    """
    issued_at = int(time.time()) if timestamp is None else timestamp
    digest = hmac.new(
        secret.encode(), f"{issued_at}.{payload}".encode(), hashlib.sha256
    ).hexdigest()
    return f"t={issued_at},v1={digest}"


def stripe_event(event_type: str, obj: dict) -> dict:
    """A Stripe event envelope carrying ``obj`` as ``data.object``."""
    return {
        "id": "evt_test_1",
        "object": "event",
        "type": event_type,
        "data": {"object": obj},
    }


def post_webhook(client, event: dict | None = None, **signature_kwargs):
    """Post ``event`` with a genuine signature over the exact body sent."""
    payload = json.dumps(event or {})
    return client.post(
        WEBHOOK,
        data=payload,
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE=sign_stripe_payload(payload, **signature_kwargs),
    )


def succeeded_event(payment: Payment, intent_id: str, **overrides) -> dict:
    return stripe_event(
        "payment_intent.succeeded", intent_payload(payment, id=intent_id, **overrides)
    )


# --- signature verification -----------------------------------------------
def test_webhook_accepts_a_valid_signature(api_client, member, annual_plan):
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    response = post_webhook(api_client, succeeded_event(payment, "pi_signed"))

    assert response.status_code == 200
    assert json.loads(response.content)["handled"] is True


def test_webhook_rejects_a_signature_made_with_another_secret(api_client, member, annual_plan):
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    response = post_webhook(
        api_client,
        succeeded_event(payment, "pi_wrong_secret"),
        secret="whsec_not_ours",  # noqa: S106 - test fixture
    )

    assert response.status_code == 400
    assert json.loads(response.content) == {"detail": "Invalid Stripe signature."}
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.PENDING


def test_webhook_rejects_a_stale_timestamp(api_client, member, annual_plan):
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    stale = int(time.time()) - SIGNATURE_TOLERANCE_SECONDS - 1
    response = post_webhook(api_client, succeeded_event(payment, "pi_stale"), timestamp=stale)

    assert response.status_code == 400
    assert json.loads(response.content) == {"detail": "Invalid Stripe signature."}
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.PENDING


def test_webhook_rejects_a_missing_signature_header(api_client, member, annual_plan):
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    response = api_client.post(
        WEBHOOK,
        data=json.dumps(succeeded_event(payment, "pi_unsigned")),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert json.loads(response.content) == {"detail": "Invalid Stripe signature."}
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.PENDING


def test_webhook_rejects_a_tampered_body(api_client, member, annual_plan):
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    signed = json.dumps(succeeded_event(payment, "pi_signed_body"))
    tampered = json.dumps(succeeded_event(payment, "pi_swapped_body"))

    response = api_client.post(
        WEBHOOK,
        data=tampered,
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE=sign_stripe_payload(signed),
    )

    assert response.status_code == 400
    assert json.loads(response.content) == {"detail": "Invalid Stripe signature."}
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.PENDING


# --- event handling --------------------------------------------------------
def test_webhook_activates_on_payment_intent_succeeded(api_client, member, annual_plan):
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    response = post_webhook(api_client, succeeded_event(payment, "pi_hook"))

    assert response.status_code == 200
    assert json.loads(response.content)["handled"] is True

    payment.refresh_from_db()
    assert payment.status == PaymentStatus.SUCCEEDED
    assert payment.provider_ref == "pi_hook"
    assert Membership.objects.filter(payment=payment).count() == 1


def test_webhook_stores_the_intent_as_a_dict(api_client, member, annual_plan):
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    post_webhook(api_client, succeeded_event(payment, "pi_hook_raw"))

    payment.refresh_from_db()
    assert isinstance(payment.raw, dict)
    assert payment.raw["id"] == "pi_hook_raw"


def test_webhook_after_confirm_is_a_no_op(api_client, member, annual_plan, fake_intents):
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    fake_intents.payload = intent_payload(payment, id="pi_both")

    api_client.force_login(member)
    api_client.post(CONFIRM, {"payment_id": payment.pk, "payment_intent_id": "pi_both"})
    payment.refresh_from_db()
    completed_at = payment.completed_at

    api_client.logout()
    assert post_webhook(api_client, succeeded_event(payment, "pi_both")).status_code == 200

    payment.refresh_from_db()
    assert payment.completed_at == completed_at
    assert Membership.objects.filter(user=member).count() == 1


def test_webhook_marks_a_failure(api_client, member, annual_plan):
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    event = stripe_event(
        "payment_intent.payment_failed",
        intent_payload(payment, id="pi_fail", status="requires_payment_method"),
    )

    assert post_webhook(api_client, event).status_code == 200
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.FAILED
    assert Membership.objects.count() == 0


def test_webhook_refuses_an_amount_that_does_not_match(api_client, member, annual_plan):
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    response = post_webhook(api_client, succeeded_event(payment, "pi_cheap", amount=1))

    assert response.status_code == 200
    assert json.loads(response.content)["handled"] is False
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.PENDING


def test_webhook_ignores_an_unknown_payment(api_client, member, annual_plan):
    event = stripe_event(
        "payment_intent.succeeded",
        {"id": "pi_nobody", "object": "payment_intent", "metadata": {"payment_id": "424242"}},
    )
    response = post_webhook(api_client, event)
    assert response.status_code == 200
    assert json.loads(response.content)["handled"] is False


def test_webhook_ignores_uninteresting_events(api_client, member, annual_plan):
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    event = stripe_event("charge.refunded", intent_payload(payment, id="pi_ref"))

    response = post_webhook(api_client, event)
    assert json.loads(response.content)["handled"] is False
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.PENDING


def test_webhook_finds_the_payment_by_provider_ref(api_client, member, annual_plan):
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    payment.provider_ref = "pi_by_ref"
    payment.save(update_fields=["provider_ref"])

    intent = intent_payload(payment, id="pi_by_ref")
    intent["metadata"] = {}
    response = post_webhook(api_client, stripe_event("payment_intent.succeeded", intent))

    # Metadata is missing, so verification refuses to activate: the row is
    # found, but nothing is granted on an unverifiable event.
    assert json.loads(response.content)["handled"] is False
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.PENDING


def test_webhook_needs_no_session_or_csrf(csrf_client, member, annual_plan):
    """``csrf_client`` enforces CSRF, so a 403 here would mean the exemption broke."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    assert post_webhook(csrf_client, succeeded_event(payment, "pi_anon")).status_code == 200


def test_stripe_provider_is_registered():
    assert get_provider("stripe").slug == "stripe"
