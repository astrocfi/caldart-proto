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
from typing import Any, Protocol

import pytest
import stripe
from pytest_django.fixtures import Settings
from rest_framework.response import Response
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.members.models import Membership, MembershipPlan
from apps.payments.models import (
    Payment,
    PaymentProvider,
    PaymentStatus,
    PaymentWallet,
    Refund,
    RefundReason,
    RefundStatus,
)
from apps.payments.providers import stripe as stripe_provider
from apps.payments.providers.base import ProviderUnavailableError
from apps.payments.providers.stripe import wallet_from_intent
from apps.payments.refunds import issue_refund
from apps.payments.services import create_checkout, fees_are_known
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

CHECKOUT = "/api/v1/payments/checkout"
CONFIRM = "/api/v1/payments/stripe/confirm"
WEBHOOK = "/api/v1/payments/stripe/webhook"

SECRET_KEY = "sk_test_123"  # noqa: S105 - test fixture
WEBHOOK_SECRET = "whsec_test"  # noqa: S105 - test fixture

#: Stripe's own default signature tolerance, in seconds.
SIGNATURE_TOLERANCE_SECONDS = 300


#: What a test is told when it reaches the SDK's real transport.
LIVE_HTTP_REFUSED = "a test tried to reach Stripe over the network"


@pytest.fixture(autouse=True)
def _stripe_configured(settings: Settings) -> None:
    """Configure fake but well-formed Stripe keys and enable the mock provider."""
    settings.STRIPE_SECRET_KEY = SECRET_KEY
    settings.STRIPE_PUBLISHABLE_KEY = "pk_test_123"
    settings.STRIPE_WEBHOOK_SECRET = WEBHOOK_SECRET
    settings.PAYMENTS_MOCK_ENABLED = True


@pytest.fixture(autouse=True)
def _no_live_stripe(monkeypatch: pytest.MonkeyPatch) -> None:
    """Refuse the SDK's real transport, so no test in this module can call Stripe.

    ``respx`` guards the providers that speak ``httpx``; the Stripe SDK brings its own
    transport instead, and every call it makes is built by the provider's
    ``http_client``.  Replacing that with a refusal turns a test that forgot
    ``fake_intents`` into a failure naming this module rather than a live request.
    """

    def refuse() -> stripe.HTTPClient:
        raise AssertionError(LIVE_HTTP_REFUSED)

    monkeypatch.setattr(stripe_provider, "http_client", refuse)


def intent_payload(payment: Payment, **overrides: Any) -> dict[str, Any]:
    """A PaymentIntent as Stripe would return it, expanded on latest_charge."""
    payload: dict[str, Any] = {
        "id": payment.provider_ref or "pi_test_1",
        "object": "payment_intent",
        "status": "succeeded",
        "amount": payment.amount_cents,
        "currency": payment.currency,
        "metadata": {
            "payment_id": str(payment.pk),
            "user_id": str(payment.user_id),
            "plan": payment.plan.slug if payment.plan is not None else "",
        },
        "latest_charge": {
            "id": "ch_test_1",
            "object": "charge",
            "payment_method_details": {"type": "card", "card": {"brand": "visa", "wallet": None}},
        },
    }
    payload.update(overrides)
    return payload


def intent_object(payload: dict[str, Any]) -> stripe.PaymentIntent:
    """The same payload as the SDK object a real call would return."""
    return stripe.PaymentIntent.construct_from(payload, SECRET_KEY)


class PaymentIntentsService(Protocol):
    """The part of Stripe's ``v1.payment_intents`` service the provider calls."""

    def create(
        self, params: dict[str, Any], options: dict[str, Any] | None = None
    ) -> stripe.PaymentIntent:
        """Create a PaymentIntent from ``params``, under the request ``options``."""
        ...

    def retrieve(
        self,
        intent_id: str,
        params: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
    ) -> stripe.PaymentIntent:
        """Return the PaymentIntent named by ``intent_id``."""
        ...


def fake_stripe_client(payment_intents: PaymentIntentsService) -> SimpleNamespace:
    """A stand-in for ``stripe.StripeClient`` exposing ``v1.payment_intents`` only.

    ``payment_intents`` answers the ``create`` and ``retrieve`` calls the provider
    makes, so a fake such as ``FakeIntents`` stands in for the whole SDK client.
    """
    return SimpleNamespace(v1=SimpleNamespace(payment_intents=payment_intents))


class FakeIntents:
    """Stand-in for ``v1.payment_intents`` that records what it was asked."""

    def __init__(self, payload: dict[str, Any] | None = None) -> None:
        """Start with no recorded calls, answering ``retrieve`` with ``payload``."""
        self.payload = payload or {}
        self.api_key = ""
        self.created: dict[str, Any] = {}
        self.create_options: dict[str, Any] = {}
        self.retrieved: dict[str, Any] = {}

    def create(
        self, params: dict[str, Any], options: dict[str, Any] | None = None
    ) -> stripe.PaymentIntent:
        """Record ``params`` and ``options`` and return a fake created intent."""
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

    def retrieve(
        self,
        intent_id: str,
        params: dict[str, Any] | None = None,
        options: dict[str, Any] | None = None,
    ) -> stripe.PaymentIntent:
        """Record the lookup and return ``self.payload`` as the intent."""
        self.retrieved = {"id": intent_id, **(params or {})}
        return intent_object(self.payload)


@pytest.fixture
def fake_intents(monkeypatch: pytest.MonkeyPatch) -> FakeIntents:
    """Replace ``stripe_client`` with one backed by a recording fake."""
    fake = FakeIntents()

    def client() -> SimpleNamespace:
        # Through the real key lookup, so a missing key still refuses.
        fake.api_key = stripe_provider.secret_key()
        return fake_stripe_client(fake)

    monkeypatch.setattr(stripe_provider, "stripe_client", client)
    return fake


# --------------------------------------------------------------------------
# live HTTP guard
# --------------------------------------------------------------------------
def test_a_call_without_the_fake_client_never_reaches_stripe(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A test that forgets ``fake_intents`` fails outright instead of calling Stripe."""
    api_client.force_login(member)
    with pytest.raises(AssertionError, match=LIVE_HTTP_REFUSED):
        api_client.post(CHECKOUT, {"plan": "annual", "contribution_cents": 0, "provider": "stripe"})


# --------------------------------------------------------------------------
# start: creating the PaymentIntent
# --------------------------------------------------------------------------
def test_checkout_creates_a_payment_intent(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, fake_intents: FakeIntents
) -> None:
    """Checkout creates a Stripe PaymentIntent for the full amount, with metadata."""
    api_client.force_login(member)
    response = api_client.post(
        CHECKOUT, {"plan": "annual", "contribution_cents": 10_000, "provider": "stripe"}
    )

    assert response.status_code == 201
    expected_secret = "pi_test_created_secret_abc"  # noqa: S105 - test fixture
    assert response.json()["client"]["client_secret"] == expected_secret

    created = fake_intents.created
    payment = Payment.objects.get(pk=response.json()["payment_id"])
    assert created["amount"] == 14_500 == payment.amount_cents
    assert created["currency"] == "usd"
    assert created["automatic_payment_methods"] == {"enabled": True}
    # CalDART sends the one receipt, so Stripe is never asked to send its own.
    assert "receipt_email" not in created
    assert created["metadata"] == {
        "payment_id": str(payment.pk),
        "user_id": str(member.pk),
        "plan": "annual",
    }
    assert fake_intents.api_key == SECRET_KEY
    assert payment.provider_ref == "pi_test_created"


def test_start_stores_the_intent_as_a_dict(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, fake_intents: FakeIntents
) -> None:
    """The payment's raw field stores the created intent as a plain dict."""
    api_client.force_login(member)
    response = api_client.post(
        CHECKOUT, {"plan": "annual", "contribution_cents": 0, "provider": "stripe"}
    )

    payment = Payment.objects.get(pk=response.json()["payment_id"])
    assert isinstance(payment.raw, dict)
    assert payment.raw["id"] == "pi_test_created"


def test_start_without_a_secret_key_is_a_400(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, settings: Settings
) -> None:
    """Checkout without a secret key is a 400, not a 500, and creates no payment."""
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
def test_confirm_activates_the_membership(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, fake_intents: FakeIntents
) -> None:
    """Confirming a matching intent succeeds and grants a current membership."""
    payment = create_checkout(member, "annual", 2_000, PaymentProvider.STRIPE)
    payment.provider_ref = "pi_test_1"
    payment.save(update_fields=["provider_ref"])
    fake_intents.payload = intent_payload(payment)

    api_client.force_login(member)
    response = api_client.post(
        CONFIRM, {"payment_id": payment.pk, "payment_intent_id": "pi_test_1"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "succeeded"
    assert response.json()["membership"]["status"] == "current"
    assert fake_intents.retrieved["expand"] == ["latest_charge.balance_transaction"]

    payment.refresh_from_db()
    assert payment.wallet == PaymentWallet.CARD
    assert payment.completed_at is not None
    assert Membership.objects.filter(payment=payment).count() == 1


def test_confirm_stores_the_intent_as_a_dict(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, fake_intents: FakeIntents
) -> None:
    """The payment's raw field stores the confirmed intent as a plain dict."""
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
    api_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    fake_intents: FakeIntents,
    wallet_type: str | None,
    expected: PaymentWallet,
) -> None:
    """The wallet is read from the confirmed charge's card details."""
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


def test_wallet_is_unknown_without_a_charge() -> None:
    """An intent with no charge at all reads as an unknown wallet."""
    assert wallet_from_intent({"id": "pi", "latest_charge": None}) == PaymentWallet.UNKNOWN


def test_wallet_is_unknown_for_an_unexpanded_charge() -> None:
    """A charge left as its id string, not expanded, reads as an unknown wallet."""
    assert wallet_from_intent({"id": "pi", "latest_charge": "ch_1"}) == PaymentWallet.UNKNOWN


def test_confirm_rejects_an_amount_mismatch(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, fake_intents: FakeIntents
) -> None:
    """A confirmed intent whose amount does not match the payment is refused."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    fake_intents.payload = intent_payload(payment, id="pi_cheap", amount=100)

    api_client.force_login(member)
    response = api_client.post(CONFIRM, {"payment_id": payment.pk, "payment_intent_id": "pi_cheap"})

    assert response.status_code == 400
    assert "amount" in str(response.json()).lower()
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.PENDING
    assert Membership.objects.count() == 0


def test_confirm_rejects_a_currency_mismatch(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, fake_intents: FakeIntents
) -> None:
    """A confirmed intent in the wrong currency is refused."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    fake_intents.payload = intent_payload(payment, id="pi_eur", currency="eur")

    api_client.force_login(member)
    response = api_client.post(CONFIRM, {"payment_id": payment.pk, "payment_intent_id": "pi_eur"})

    assert response.status_code == 400
    assert Membership.objects.count() == 0


def test_confirm_rejects_metadata_for_another_payment(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, fake_intents: FakeIntents
) -> None:
    """A confirmed intent whose metadata names another payment id is refused."""
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


def test_confirm_marks_a_canceled_intent_failed(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, fake_intents: FakeIntents
) -> None:
    """A canceled intent marks the payment failed and grants no membership."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    fake_intents.payload = intent_payload(payment, id="pi_dead", status="canceled")

    api_client.force_login(member)
    response = api_client.post(CONFIRM, {"payment_id": payment.pk, "payment_intent_id": "pi_dead"})

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.FAILED
    assert Membership.objects.count() == 0


def test_confirm_rejects_an_intent_still_processing(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, fake_intents: FakeIntents
) -> None:
    """An intent still processing is refused rather than treated as succeeded."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    fake_intents.payload = intent_payload(payment, id="pi_wait", status="processing")

    api_client.force_login(member)
    response = api_client.post(CONFIRM, {"payment_id": payment.pk, "payment_intent_id": "pi_wait"})

    assert response.status_code == 400
    assert Membership.objects.count() == 0


def test_confirm_rejects_an_intent_bound_to_another_payment(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, fake_intents: FakeIntents
) -> None:
    """Confirming with an intent id that does not match the payment's own is refused."""
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
    api_client: APIClient,
    member: User,
    user_factory: type[UserFactory],
    annual_plan: MembershipPlan,
    fake_intents: FakeIntents,
) -> None:
    """A signed-in user confirming another member's payment gets a 404, not the data."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    fake_intents.payload = intent_payload(payment, id="pi_x")

    thief = user_factory(email="thief@example.test", roles=["member"])
    api_client.force_login(thief)
    response = api_client.post(CONFIRM, {"payment_id": payment.pk, "payment_intent_id": "pi_x"})
    assert response.status_code == 404


def test_confirm_rejects_a_paypal_payment(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, fake_intents: FakeIntents
) -> None:
    """Confirming a payment that was started through PayPal, not Stripe, is refused."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.PAYPAL)
    api_client.force_login(member)
    response = api_client.post(CONFIRM, {"payment_id": payment.pk, "payment_intent_id": "pi_x"})
    assert response.status_code == 400


def test_confirm_requires_a_session(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """Confirming while signed out is a 401, not a lookup by intent id alone."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    assert api_client.post(CONFIRM, {"payment_id": payment.pk}).status_code == 401


def test_confirm_is_idempotent(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, fake_intents: FakeIntents
) -> None:
    """Confirming the same payment twice grants exactly one membership."""
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


def stripe_event(event_type: str, obj: dict[str, Any]) -> dict[str, Any]:
    """A Stripe event envelope carrying ``obj`` as ``data.object``."""
    return {
        "id": "evt_test_1",
        "object": "event",
        "type": event_type,
        "data": {"object": obj},
    }


def post_webhook(
    client: APIClient, event: dict[str, Any] | None = None, **signature_kwargs: Any
) -> Response:
    """Post ``event`` with a genuine signature over the exact body sent."""
    payload = json.dumps(event or {})
    return client.post(
        WEBHOOK,
        data=payload,
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE=sign_stripe_payload(payload, **signature_kwargs),
    )


def succeeded_event(payment: Payment, intent_id: str, **overrides: Any) -> dict[str, Any]:
    """A ``payment_intent.succeeded`` event wrapping ``payment`` as ``intent_id``."""
    return stripe_event(
        "payment_intent.succeeded", intent_payload(payment, id=intent_id, **overrides)
    )


# --- signature verification -----------------------------------------------
def test_webhook_accepts_a_valid_signature(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A webhook signed with the configured secret is accepted and handled."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    response = post_webhook(api_client, succeeded_event(payment, "pi_signed"))

    assert response.status_code == 200
    assert json.loads(response.content)["handled"] is True


def test_webhook_rejects_a_signature_made_with_another_secret(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A signature made with a different secret is refused with a 400."""
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


def test_webhook_rejects_a_stale_timestamp(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A signature timestamped outside Stripe's own tolerance is refused."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    stale = int(time.time()) - SIGNATURE_TOLERANCE_SECONDS - 1
    response = post_webhook(api_client, succeeded_event(payment, "pi_stale"), timestamp=stale)

    assert response.status_code == 400
    assert json.loads(response.content) == {"detail": "Invalid Stripe signature."}
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.PENDING


def test_webhook_rejects_a_missing_signature_header(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A request with no ``Stripe-Signature`` header at all is refused."""
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


def test_webhook_rejects_a_tampered_body(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A body that differs from the one the signature covers is refused."""
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
def test_webhook_activates_on_payment_intent_succeeded(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A succeeded webhook activates the payment and grants a membership."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    response = post_webhook(api_client, succeeded_event(payment, "pi_hook"))

    assert response.status_code == 200
    assert json.loads(response.content)["handled"] is True

    payment.refresh_from_db()
    assert payment.status == PaymentStatus.SUCCEEDED
    assert payment.provider_ref == "pi_hook"
    assert Membership.objects.filter(payment=payment).count() == 1


def test_webhook_stores_the_intent_as_a_dict(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The payment's raw field stores the webhook's intent as a plain dict."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    post_webhook(api_client, succeeded_event(payment, "pi_hook_raw"))

    payment.refresh_from_db()
    assert isinstance(payment.raw, dict)
    assert payment.raw["id"] == "pi_hook_raw"


def test_webhook_after_confirm_is_a_no_op(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, fake_intents: FakeIntents
) -> None:
    """A webhook that arrives after the client already confirmed changes nothing."""
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


def test_webhook_marks_a_failure(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A failed-intent webhook marks the payment failed and grants no membership."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    event = stripe_event(
        "payment_intent.payment_failed",
        intent_payload(payment, id="pi_fail", status="requires_payment_method"),
    )

    assert post_webhook(api_client, event).status_code == 200
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.FAILED
    assert Membership.objects.count() == 0


def test_webhook_refuses_an_amount_that_does_not_match(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A webhook whose amount does not match is accepted but marked unhandled."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    response = post_webhook(api_client, succeeded_event(payment, "pi_cheap", amount=1))

    assert response.status_code == 200
    assert json.loads(response.content)["handled"] is False
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.PENDING


def test_webhook_ignores_an_unknown_payment(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A webhook naming a payment id that does not exist is accepted but unhandled."""
    event = stripe_event(
        "payment_intent.succeeded",
        {"id": "pi_nobody", "object": "payment_intent", "metadata": {"payment_id": "424242"}},
    )
    response = post_webhook(api_client, event)
    assert response.status_code == 200
    assert json.loads(response.content)["handled"] is False


def test_webhook_ignores_uninteresting_events(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """An event type the webhook does not handle is accepted but marked unhandled."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    event = stripe_event("payment_intent.created", intent_payload(payment, id="pi_ref"))

    response = post_webhook(api_client, event)
    assert json.loads(response.content)["handled"] is False
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.PENDING


def test_webhook_finds_the_payment_by_provider_ref(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A webhook is matched to its payment by provider ref when metadata is missing."""
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


def test_webhook_needs_no_session_or_csrf(
    csrf_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """``csrf_client`` enforces CSRF, so a 403 here would mean the exemption broke."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    assert post_webhook(csrf_client, succeeded_event(payment, "pi_anon")).status_code == 200


# --- fees ------------------------------------------------------------------
def balance_transaction(fee: int, net: int) -> dict[str, Any]:
    """A balance transaction as Stripe expands it onto a charge."""
    return {"id": "txn_test_1", "object": "balance_transaction", "fee": fee, "net": net}


def settled_intent(payment: Payment, intent_id: str, *, fee: int, net: int) -> dict[str, Any]:
    """An intent whose charge carries the balance transaction Stripe settled it on."""
    intent = intent_payload(payment, id=intent_id)
    intent["latest_charge"]["balance_transaction"] = balance_transaction(fee, net)
    return intent


def test_confirm_records_the_fee_from_the_balance_transaction(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, fake_intents: FakeIntents
) -> None:
    """A settled intent's fee and net land on the payment when it is confirmed."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    fake_intents.payload = settled_intent(payment, "pi_fee", fee=161, net=4_339)

    api_client.force_login(member)
    api_client.post(CONFIRM, {"payment_id": payment.pk, "payment_intent_id": "pi_fee"})

    payment.refresh_from_db()
    assert payment.fee_cents == 161


def test_confirm_records_the_net_from_the_balance_transaction(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, fake_intents: FakeIntents
) -> None:
    """The net Stripe reports is stored as reported, not recomputed."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    fake_intents.payload = settled_intent(payment, "pi_net", fee=161, net=4_300)

    api_client.force_login(member)
    api_client.post(CONFIRM, {"payment_id": payment.pk, "payment_intent_id": "pi_net"})

    payment.refresh_from_db()
    assert payment.net_cents == 4_300


def test_an_intent_with_no_balance_transaction_leaves_the_fee_unknown(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, fake_intents: FakeIntents
) -> None:
    """Stripe settles some methods later, and until it does there is no fee to store."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    fake_intents.payload = intent_payload(payment, id="pi_unsettled")

    api_client.force_login(member)
    api_client.post(CONFIRM, {"payment_id": payment.pk, "payment_intent_id": "pi_unsettled"})

    payment.refresh_from_db()
    assert fees_are_known(payment) is False


def test_an_unexpanded_balance_transaction_reads_as_no_fee_yet(
    member: User, annual_plan: MembershipPlan
) -> None:
    """An id where the transaction should be is not a figure we can record."""
    intent = {"latest_charge": {"balance_transaction": "txn_test_1"}}

    assert stripe_provider.fees_from_intent(intent) is None


def charge_event(payment: Payment, intent_id: str, **charge: Any) -> dict[str, Any]:
    """A ``charge.updated`` event for ``payment``, carrying ``charge``'s fields."""
    return stripe_event(
        stripe_provider.CHARGE_UPDATED,
        {
            "id": "ch_test_1",
            "object": "charge",
            "payment_intent": intent_id,
            "metadata": {"payment_id": str(payment.pk)},
            **charge,
        },
    )


def test_charge_updated_fills_in_a_fee_the_payment_did_not_have(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The event that carries the settled balance transaction records the fee."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    post_webhook(api_client, succeeded_event(payment, "pi_late"))

    event = charge_event(payment, "pi_late", balance_transaction=balance_transaction(161, 4_339))
    response = post_webhook(api_client, event)

    assert json.loads(response.content)["handled"] is True
    payment.refresh_from_db()
    assert payment.fee_cents == 161


def test_charge_updated_re_reads_the_intent_when_the_event_carries_no_transaction(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, fake_intents: FakeIntents
) -> None:
    """An unexpanded event sends us back to Stripe rather than giving up."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    post_webhook(api_client, succeeded_event(payment, "pi_refetch"))
    fake_intents.payload = settled_intent(payment, "pi_refetch", fee=175, net=4_325)

    post_webhook(api_client, charge_event(payment, "pi_refetch", balance_transaction="txn_1"))

    payment.refresh_from_db()
    assert payment.net_cents == 4_325


def test_charge_updated_leaves_a_fee_we_already_know_alone(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A second delivery of the same event changes nothing."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    post_webhook(api_client, succeeded_event(payment, "pi_twice"))
    event = charge_event(payment, "pi_twice", balance_transaction=balance_transaction(161, 4_339))
    post_webhook(api_client, event)

    second = post_webhook(
        api_client,
        charge_event(payment, "pi_twice", balance_transaction=balance_transaction(999, 1)),
    )

    assert json.loads(second.content)["handled"] is False
    payment.refresh_from_db()
    assert payment.fee_cents == 161


def test_charge_updated_for_an_unknown_payment_is_acknowledged(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """An event about a payment this installation does not have changes nothing."""
    event = stripe_event(
        stripe_provider.CHARGE_UPDATED,
        {"id": "ch_nobody", "object": "charge", "payment_intent": "pi_nobody", "metadata": {}},
    )

    response = post_webhook(api_client, event)

    assert json.loads(response.content)["handled"] is False


def test_charge_updated_records_the_fee_before_the_payment_has_settled(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """Stripe orders no deliveries, so the fee may arrive before the success does."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)

    event = charge_event(payment, "pi_early", balance_transaction=balance_transaction(161, 4_339))
    response = post_webhook(api_client, event)

    assert json.loads(response.content)["handled"] is True
    payment.refresh_from_db()
    assert payment.fee_cents == 161


def test_a_success_after_an_early_charge_updated_keeps_the_fee(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The success event carries no expanded transaction and must not wipe the fee."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    post_webhook(
        api_client,
        charge_event(payment, "pi_order", balance_transaction=balance_transaction(161, 4_339)),
    )

    post_webhook(api_client, succeeded_event(payment, "pi_order"))

    payment.refresh_from_db()
    assert payment.net_cents == 4_339


# --------------------------------------------------------------------------
# refunds
# --------------------------------------------------------------------------
class FakeRefunds:
    """Stand-in for ``v1.refunds`` that records what it was asked to create."""

    def __init__(self, refund_id: str = "re_test_1") -> None:
        """Start with no recorded call, answering ``create`` with ``refund_id``."""
        self.refund_id = refund_id
        self.created: dict[str, Any] = {}
        self.create_options: dict[str, Any] = {}

    def create(
        self, params: dict[str, Any], options: dict[str, Any] | None = None
    ) -> stripe.Refund:
        """Record ``params`` and ``options`` and answer with a succeeded refund."""
        self.created = params
        self.create_options = options or {}
        return stripe.Refund.construct_from(
            {
                "id": self.refund_id,
                "object": "refund",
                "status": "succeeded",
                "amount": params["amount"],
                "payment_intent": params["payment_intent"],
            },
            SECRET_KEY,
        )


@pytest.fixture
def fake_refunds(monkeypatch: pytest.MonkeyPatch) -> FakeRefunds:
    """Replace ``stripe_client`` with one exposing only ``v1.refunds``."""
    fake = FakeRefunds()

    def client() -> SimpleNamespace:
        stripe_provider.secret_key()
        return SimpleNamespace(v1=SimpleNamespace(refunds=fake))

    monkeypatch.setattr(stripe_provider, "stripe_client", client)
    return fake


def succeeded_stripe_payment(member: User, intent_id: str = "pi_refundable") -> Payment:
    """A succeeded Stripe payment of 4,500 cents carrying ``intent_id``."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    payment.provider_ref = intent_id
    payment.status = PaymentStatus.SUCCEEDED
    payment.save(update_fields=["provider_ref", "status"])
    return payment


def test_a_refund_asks_stripe_for_the_amount_against_the_intent(
    member: User, annual_plan: MembershipPlan, account_admin: User, fake_refunds: FakeRefunds
) -> None:
    """The refund names the PaymentIntent and the cents to give back."""
    payment = succeeded_stripe_payment(member)
    issue_refund(payment, amount_cents=1_500, reason=RefundReason.ERROR, actor=account_admin)

    assert fake_refunds.created["payment_intent"] == "pi_refundable"
    assert fake_refunds.created["amount"] == 1_500


def test_a_refund_carries_an_idempotency_key_of_its_own(
    member: User, annual_plan: MembershipPlan, account_admin: User, fake_refunds: FakeRefunds
) -> None:
    """A call repeated after a timeout gives the money back once."""
    payment = succeeded_stripe_payment(member)
    refund = issue_refund(
        payment, amount_cents=1_500, reason=RefundReason.ERROR, actor=account_admin
    )

    assert fake_refunds.create_options["idempotency_key"] == f"caldart-refund-{refund.pk}"


def test_a_refund_keeps_the_stripe_refund_id(
    member: User, annual_plan: MembershipPlan, account_admin: User, fake_refunds: FakeRefunds
) -> None:
    """The provider reference is what a later webhook is recognized by."""
    payment = succeeded_stripe_payment(member)
    refund = issue_refund(
        payment, amount_cents=1_500, reason=RefundReason.ERROR, actor=account_admin
    )

    assert refund.provider_ref == "re_test_1"


def test_a_stripe_error_leaves_the_refund_failed(
    member: User,
    annual_plan: MembershipPlan,
    account_admin: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stripe refusing the refund is a provider outage, not a 500."""
    payment = succeeded_stripe_payment(member)

    class RefusingRefunds:
        """A ``v1.refunds`` that always raises Stripe's own error."""

        def create(
            self, params: dict[str, Any], options: dict[str, Any] | None = None
        ) -> stripe.Refund:
            """Raise as the SDK does when the API call fails."""
            raise stripe.APIConnectionError("boom")

    def client() -> SimpleNamespace:
        return SimpleNamespace(v1=SimpleNamespace(refunds=RefusingRefunds()))

    monkeypatch.setattr(stripe_provider, "stripe_client", client)

    with pytest.raises(ProviderUnavailableError, match="Stripe could not be reached"):
        issue_refund(payment, amount_cents=1_500, reason=RefundReason.ERROR, actor=account_admin)

    assert Refund.objects.get().status == RefundStatus.FAILED


# --- charge.refunded ------------------------------------------------------
def charge_payload(payment: Payment, refunds: list[dict[str, Any]]) -> dict[str, Any]:
    """A charge as ``charge.refunded`` carries it, with ``refunds.data`` filled in."""
    return {
        "id": "ch_refunded_1",
        "object": "charge",
        "payment_intent": payment.provider_ref,
        "metadata": {"payment_id": str(payment.pk)},
        "refunds": {"object": "list", "data": refunds},
    }


def stripe_refund(refund_id: str, amount: int, status: str = "succeeded") -> dict[str, Any]:
    """One entry of a charge's ``refunds.data``."""
    return {"id": refund_id, "object": "refund", "amount": amount, "status": status}


def test_a_dashboard_refund_webhook_records_the_refund(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """Somebody refunding in Stripe's dashboard still lands in the ledger."""
    payment = succeeded_stripe_payment(member)
    event = stripe_event(
        "charge.refunded", charge_payload(payment, [stripe_refund("re_dash", 1_000)])
    )

    response = post_webhook(api_client, event)

    assert json.loads(response.content)["handled"] is True
    refund = Refund.objects.get()
    assert refund.amount_cents == 1_000
    assert refund.provider_ref == "re_dash"


def test_a_dashboard_refund_webhook_updates_the_payment(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A full refund taken in the dashboard leaves the payment refunded here."""
    payment = succeeded_stripe_payment(member)
    event = stripe_event(
        "charge.refunded",
        charge_payload(payment, [stripe_refund("re_dash_full", payment.amount_cents)]),
    )

    post_webhook(api_client, event)

    payment.refresh_from_db()
    assert payment.status == PaymentStatus.REFUNDED


def test_a_second_delivery_of_charge_refunded_records_nothing(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """Stripe retries a webhook, and the refund id is what makes that harmless."""
    payment = succeeded_stripe_payment(member)
    event = stripe_event(
        "charge.refunded", charge_payload(payment, [stripe_refund("re_twice", 1_000)])
    )

    post_webhook(api_client, event)
    post_webhook(api_client, event)

    assert Refund.objects.count() == 1


def test_a_pending_refund_in_the_webhook_is_not_recorded(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """Only a refund Stripe reports as succeeded has actually given money back."""
    payment = succeeded_stripe_payment(member)
    event = stripe_event(
        "charge.refunded",
        charge_payload(payment, [stripe_refund("re_pending", 1_000, status="pending")]),
    )

    post_webhook(api_client, event)

    assert Refund.objects.count() == 0


def test_charge_refunded_for_an_unknown_payment_is_ignored(api_client: APIClient) -> None:
    """A charge that matches no row of ours is received and left alone."""
    event = stripe_event(
        "charge.refunded",
        {
            "id": "ch_nobody",
            "object": "charge",
            "metadata": {"payment_id": "424242"},
            "refunds": {"data": [stripe_refund("re_nobody", 100)]},
        },
    )

    response = post_webhook(api_client, event)

    assert json.loads(response.content)["handled"] is False
    assert Refund.objects.count() == 0
