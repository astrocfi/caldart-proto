"""Saving and charging a payment method with each provider.

Neither Stripe nor PayPal is called: the Stripe SDK client is replaced by a
recording fake, and PayPal's REST calls are intercepted with ``respx``, so the
mandate half of each provider is exercised against the shapes the real APIs
return.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
import respx
import stripe
from pytest_django.fixtures import Settings

from apps.accounts.models import User
from apps.members.models import MembershipPlan
from apps.payments.models import (
    MandateProvider,
    Payment,
    PaymentProvider,
    PaymentStatus,
    RenewalMandate,
)
from apps.payments.providers import paypal as paypal_provider
from apps.payments.providers import stripe as stripe_provider
from apps.payments.providers.base import (
    PaymentDeclinedError,
    PaymentVerificationError,
    card_label,
    get_provider,
)
from apps.payments.providers.mock import DECLINED_LAST4, MOCK_CARD_LABEL
from apps.payments.providers.paypal import paypal_label
from apps.payments.renewals import begin_mandate
from apps.payments.services import create_checkout
from tests.factories import RenewalMandateFactory

pytestmark = pytest.mark.django_db

SECRET_KEY = "sk_test_mandates"  # noqa: S105 - test fixture
SANDBOX = "https://api-m.sandbox.paypal.com"

#: The approved vault setup token a PayPal confirm is given.  Not a credential:
#: it is a one-use handle on a token PayPal issued to this sandbox account.
SETUP_TOKEN = "sto_1"  # noqa: S105 - a PayPal setup token id, not a password


# --------------------------------------------------------------------------
# The label every provider builds
# --------------------------------------------------------------------------
def test_a_card_label_names_the_brand_the_digits_and_the_expiry() -> None:
    """The member reads one line that identifies the card without exposing it."""
    assert card_label("visa", "4242", 3, 2028) == "Visa ending 4242, expires 03/2028"


def test_a_card_with_no_expiry_is_labeled_without_one() -> None:
    """A provider that gives no expiry still produces a usable label."""
    assert card_label("mastercard", "5555", None, None) == "Mastercard ending 5555"


def test_a_method_with_nothing_known_still_has_a_label() -> None:
    """An unrecognizable saved method never shows the member a blank line."""
    assert card_label("", "", None, None) == "Saved payment method"


def test_a_paypal_account_is_labeled_with_a_masked_address() -> None:
    """The member recognizes their own PayPal account without it being printed."""
    assert paypal_label("maria@example.org") == "PayPal (m***@example.org)"


def test_a_paypal_account_with_no_address_is_labeled_plainly() -> None:
    """PayPal that gives no email address still reads as PayPal."""
    assert paypal_label("") == "PayPal"


# --------------------------------------------------------------------------
# Mock
# --------------------------------------------------------------------------
@pytest.fixture
def mock_enabled(settings: Settings) -> None:
    """Turn the mock payment provider on for this test."""
    settings.PAYMENTS_MOCK_ENABLED = True


def test_the_mock_provider_saves_its_one_test_card(
    mock_enabled: None, member: User, annual_plan: MembershipPlan
) -> None:
    """Confirming a mock mandate gives the test card every mock mandate holds."""
    mandate = RenewalMandateFactory(user=member, plan=annual_plan)
    method = get_provider(MandateProvider.MOCK).confirm_mandate(mandate)
    assert method.label == MOCK_CARD_LABEL


def test_the_mock_provider_takes_a_renewal(
    mock_enabled: None, member: User, annual_plan: MembershipPlan
) -> None:
    """A mock mandate on the ordinary card marks its renewal payment succeeded."""
    mandate = RenewalMandateFactory(user=member, plan=annual_plan)
    payment = create_checkout(member, "annual", 0, PaymentProvider.MOCK)

    get_provider(MandateProvider.MOCK).charge_mandate(mandate, payment)

    payment.refresh_from_db()
    assert payment.status == PaymentStatus.SUCCEEDED


def test_the_mock_decline_card_refuses_every_charge(
    mock_enabled: None, member: User, annual_plan: MembershipPlan
) -> None:
    """The ``0002`` card exists so the decline path can be shown on demand."""
    mandate = RenewalMandateFactory(user=member, plan=annual_plan, method_last4=DECLINED_LAST4)
    payment = create_checkout(member, "annual", 0, PaymentProvider.MOCK)

    with pytest.raises(PaymentDeclinedError, match="Your card was declined"):
        get_provider(MandateProvider.MOCK).charge_mandate(mandate, payment)


# --------------------------------------------------------------------------
# Stripe
# --------------------------------------------------------------------------
class FakeStripe:
    """Stand-in for the SDK client, recording what the provider asked for."""

    def __init__(self) -> None:
        """Start with no recorded calls and nothing to answer with."""
        self.customer_payload: dict[str, Any] = {"id": "cus_test_1"}
        self.setup_payload: dict[str, Any] = {}
        self.intent_payload: dict[str, Any] = {}
        self.decline: stripe.StripeError | None = None
        self.created_intent: dict[str, Any] = {}
        self.created_setup: dict[str, Any] = {}
        self.created_customer: dict[str, Any] = {}
        self.method_payload: dict[str, Any] = {}
        self.retrieved_method = ""

    # -- customers
    def create_customer(self, params: dict[str, Any]) -> stripe.Customer:
        """Record the customer created and answer with ``customer_payload``."""
        self.created_customer = params
        return stripe.Customer.construct_from(self.customer_payload, SECRET_KEY)

    # -- setup intents
    def create_setup(self, params: dict[str, Any]) -> stripe.SetupIntent:
        """Record the SetupIntent created and answer with ``setup_payload``."""
        self.created_setup = params
        return stripe.SetupIntent.construct_from(self.setup_payload, SECRET_KEY)

    def retrieve_setup(
        self, setup_id: str, params: dict[str, Any] | None = None
    ) -> stripe.SetupIntent:
        """Answer with ``setup_payload``, whatever id is asked for."""
        return stripe.SetupIntent.construct_from(self.setup_payload, SECRET_KEY)

    # -- payment methods
    def retrieve_method(self, method_id: str) -> stripe.PaymentMethod:
        """Record the method asked for and answer with ``method_payload``."""
        self.retrieved_method = method_id
        return stripe.PaymentMethod.construct_from(self.method_payload, SECRET_KEY)

    # -- payment intents
    def create_intent(
        self, params: dict[str, Any], options: dict[str, Any] | None = None
    ) -> stripe.PaymentIntent:
        """Record the charge, raise ``decline`` when set, else answer the intent."""
        self.created_intent = params
        if self.decline is not None:
            raise self.decline
        return stripe.PaymentIntent.construct_from(self.intent_payload, SECRET_KEY)

    def as_client(self) -> SimpleNamespace:
        """The object ``stripe_client()`` is replaced with."""
        return SimpleNamespace(
            v1=SimpleNamespace(
                customers=SimpleNamespace(create=self.create_customer),
                setup_intents=SimpleNamespace(
                    create=self.create_setup, retrieve=self.retrieve_setup
                ),
                payment_intents=SimpleNamespace(create=self.create_intent),
                payment_methods=SimpleNamespace(retrieve=self.retrieve_method),
            )
        )


@pytest.fixture
def fake_stripe(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> FakeStripe:
    """Configure Stripe keys and replace its client with a recording fake."""
    settings.STRIPE_SECRET_KEY = SECRET_KEY
    settings.STRIPE_PUBLISHABLE_KEY = "pk_test_mandates"
    fake = FakeStripe()
    monkeypatch.setattr(stripe_provider, "stripe_client", fake.as_client)
    return fake


def stripe_mandate(user: User, plan: MembershipPlan, **overrides: Any) -> RenewalMandate:
    """A Stripe mandate for ``user``, pending unless ``overrides`` say otherwise."""
    return RenewalMandateFactory(user=user, plan=plan, provider=MandateProvider.STRIPE, **overrides)


def test_stripe_creates_a_customer_for_a_mandate_that_has_none(
    fake_stripe: FakeStripe, member: User, annual_plan: MembershipPlan
) -> None:
    """The customer the card is saved against is created once and kept."""
    mandate = stripe_mandate(member, annual_plan, customer_ref="")
    fake_stripe.setup_payload = {"id": "seti_1", "client_secret": "seti_1_secret"}

    get_provider(MandateProvider.STRIPE).start_mandate(mandate)

    mandate.refresh_from_db()
    assert mandate.customer_ref == "cus_test_1"


def test_stripe_hands_the_browser_the_setup_intents_secret(
    fake_stripe: FakeStripe, member: User, annual_plan: MembershipPlan
) -> None:
    """The Payment Element in setup mode needs exactly this one value."""
    mandate = stripe_mandate(member, annual_plan, customer_ref="cus_test_1")
    fake_stripe.setup_payload = {"id": "seti_1", "client_secret": "seti_1_secret"}

    client = get_provider(MandateProvider.STRIPE).start_mandate(mandate)

    assert client == {"client_secret": "seti_1_secret"}


def test_stripe_asks_for_a_method_it_may_use_off_session(
    fake_stripe: FakeStripe, member: User, annual_plan: MembershipPlan
) -> None:
    """The SetupIntent declares off-session usage, or the card cannot be charged later."""
    mandate = stripe_mandate(member, annual_plan, customer_ref="cus_test_1")
    fake_stripe.setup_payload = {"id": "seti_1", "client_secret": "seti_1_secret"}

    get_provider(MandateProvider.STRIPE).start_mandate(mandate)

    assert fake_stripe.created_setup["usage"] == "off_session"


def succeeded_setup(customer: str = "cus_test_1") -> dict[str, Any]:
    """A SetupIntent as Stripe returns it once the card has been saved."""
    return {
        "id": "seti_1",
        "status": "succeeded",
        "customer": customer,
        "payment_method": {
            "id": "pm_test_1",
            "card": {"brand": "visa", "last4": "4242", "exp_month": 3, "exp_year": 2028},
        },
    }


def test_stripe_reads_the_saved_card_back_off_the_setup_intent(
    fake_stripe: FakeStripe, member: User, annual_plan: MembershipPlan
) -> None:
    """Confirming a mandate labels the card the member actually saved."""
    mandate = stripe_mandate(member, annual_plan, customer_ref="cus_test_1")
    fake_stripe.setup_payload = succeeded_setup()

    method = get_provider(MandateProvider.STRIPE).confirm_mandate(mandate, setup_intent_id="seti_1")

    assert method.label == "Visa ending 4242, expires 03/2028"


def test_stripe_refuses_a_setup_intent_belonging_to_another_customer(
    fake_stripe: FakeStripe, member: User, annual_plan: MembershipPlan
) -> None:
    """A member cannot claim somebody else's saved card by naming its intent."""
    mandate = stripe_mandate(member, annual_plan, customer_ref="cus_test_1")
    fake_stripe.setup_payload = succeeded_setup(customer="cus_someone_else")

    with pytest.raises(PaymentVerificationError, match="belongs to another customer"):
        get_provider(MandateProvider.STRIPE).confirm_mandate(mandate, setup_intent_id="seti_1")


def test_stripe_refuses_a_setup_that_did_not_succeed(
    fake_stripe: FakeStripe, member: User, annual_plan: MembershipPlan
) -> None:
    """A card that was never saved is not turned into a standing authority."""
    mandate = stripe_mandate(member, annual_plan, customer_ref="cus_test_1")
    fake_stripe.setup_payload = {
        "id": "seti_1",
        "status": "requires_payment_method",
        "customer": "cus_test_1",
    }

    with pytest.raises(PaymentVerificationError, match="requires_payment_method"):
        get_provider(MandateProvider.STRIPE).confirm_mandate(mandate, setup_intent_id="seti_1")


def test_stripe_charges_the_saved_method_without_the_member(
    fake_stripe: FakeStripe, member: User, annual_plan: MembershipPlan
) -> None:
    """The renewal charge is confirmed off-session, which is what makes it automatic."""
    mandate = stripe_mandate(member, annual_plan, customer_ref="cus_test_1", method_ref="pm_test_1")
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    fake_stripe.intent_payload = {
        "id": "pi_renewal_1",
        "status": "succeeded",
        "amount": payment.amount_cents,
        "currency": "usd",
        "latest_charge": {"payment_method_details": {"type": "card", "card": {"brand": "visa"}}},
    }

    get_provider(MandateProvider.STRIPE).charge_mandate(mandate, payment)

    assert fake_stripe.created_intent["off_session"] is True


def test_a_stripe_renewal_that_succeeds_marks_the_payment_succeeded(
    fake_stripe: FakeStripe, member: User, annual_plan: MembershipPlan
) -> None:
    """The ordinary success path runs, so the term is activated as at a checkout."""
    mandate = stripe_mandate(member, annual_plan, customer_ref="cus_test_1", method_ref="pm_test_1")
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    fake_stripe.intent_payload = {
        "id": "pi_renewal_1",
        "status": "succeeded",
        "amount": payment.amount_cents,
        "currency": "usd",
        "latest_charge": {"payment_method_details": {"type": "card", "card": {"brand": "visa"}}},
    }

    get_provider(MandateProvider.STRIPE).charge_mandate(mandate, payment)

    payment.refresh_from_db()
    assert payment.status == PaymentStatus.SUCCEEDED


def test_a_stripe_card_error_becomes_the_reason_the_member_is_given(
    fake_stripe: FakeStripe, member: User, annual_plan: MembershipPlan
) -> None:
    """Stripe's own wording is what the failure email quotes."""
    mandate = stripe_mandate(member, annual_plan, customer_ref="cus_test_1", method_ref="pm_test_1")
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    # The SDK's error classes carry no annotations, so the construction is untyped.
    fake_stripe.decline = stripe.CardError(  # type: ignore[no-untyped-call]
        "Your card has insufficient funds.", param="", code="card_declined", json_body={}
    )

    with pytest.raises(PaymentDeclinedError, match="insufficient funds"):
        get_provider(MandateProvider.STRIPE).charge_mandate(mandate, payment)


def test_a_stripe_intent_that_wants_authentication_is_a_decline(
    fake_stripe: FakeStripe, member: User, annual_plan: MembershipPlan
) -> None:
    """Nobody is present to authenticate, so the charge is reported as refused."""
    mandate = stripe_mandate(member, annual_plan, customer_ref="cus_test_1", method_ref="pm_test_1")
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    fake_stripe.intent_payload = {
        "id": "pi_renewal_1",
        "status": "requires_action",
        "amount": payment.amount_cents,
        "currency": "usd",
    }

    with pytest.raises(PaymentDeclinedError, match="asked for confirmation"):
        get_provider(MandateProvider.STRIPE).charge_mandate(mandate, payment)


def test_stripe_reads_the_method_a_checkout_saved(
    fake_stripe: FakeStripe, member: User, annual_plan: MembershipPlan
) -> None:
    """A checkout that saved a card hands the mandate that card's details."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    payment.raw = {
        "id": "pi_1",
        "customer": "cus_test_1",
        "payment_method": "pm_test_1",
        "latest_charge": {
            "payment_method_details": {
                "type": "card",
                "card": {"brand": "visa", "last4": "4242", "exp_month": 3, "exp_year": 2028},
            }
        },
    }
    payment.save(update_fields=["raw"])

    method = get_provider(MandateProvider.STRIPE).method_from_payment(payment)

    assert method is not None
    assert method.method_ref == "pm_test_1"


def test_a_stripe_checkout_ignores_a_mandate_that_renews_something_else(
    fake_stripe: FakeStripe, member: User, annual_plan: MembershipPlan
) -> None:
    """A mandate left over from another checkout never vaults this checkout's card."""
    begin_mandate(
        member, plan=annual_plan, contribution_cents=5_000, provider=MandateProvider.STRIPE
    )
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    fake_stripe.intent_payload = {"id": "pi_1", "client_secret": "pi_1_secret"}

    get_provider(MandateProvider.STRIPE).start(payment)

    assert "setup_future_usage" not in fake_stripe.created_intent


def test_stripe_reads_the_method_from_a_webhook_shaped_intent(
    fake_stripe: FakeStripe, member: User, annual_plan: MembershipPlan
) -> None:
    """The webhook stores ``latest_charge`` as a bare id, so the card is fetched."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    payment.raw = {
        "id": "pi_1",
        "customer": "cus_test_1",
        "payment_method": "pm_test_1",
        "latest_charge": "ch_1",
    }
    payment.save(update_fields=["raw"])
    fake_stripe.method_payload = {
        "id": "pm_test_1",
        "card": {"brand": "visa", "last4": "4242", "exp_month": 3, "exp_year": 2028},
    }

    method = get_provider(MandateProvider.STRIPE).method_from_payment(payment)

    assert method is not None
    assert method.label == "Visa ending 4242, expires 03/2028"


def test_a_webhook_shaped_intent_that_saved_no_card_yields_no_method(
    fake_stripe: FakeStripe, member: User, annual_plan: MembershipPlan
) -> None:
    """A method Stripe reports without a card activates nothing."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    payment.raw = {"id": "pi_1", "payment_method": "pm_test_1", "latest_charge": "ch_1"}
    payment.save(update_fields=["raw"])
    fake_stripe.method_payload = {"id": "pm_test_1", "type": "us_bank_account"}

    assert get_provider(MandateProvider.STRIPE).method_from_payment(payment) is None


def test_a_stripe_checkout_that_saved_nothing_yields_no_method(
    fake_stripe: FakeStripe, member: User, annual_plan: MembershipPlan
) -> None:
    """An ordinary one-off payment activates no mandate."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.STRIPE)
    payment.raw = {"id": "pi_1", "latest_charge": {"payment_method_details": {"type": "card"}}}
    payment.save(update_fields=["raw"])

    assert get_provider(MandateProvider.STRIPE).method_from_payment(payment) is None


# --------------------------------------------------------------------------
# PayPal
# --------------------------------------------------------------------------
@pytest.fixture
def paypal_configured(settings: Settings) -> None:
    """Configure sandbox PayPal credentials and empty the token cache."""
    from django.core.cache import cache

    settings.PAYPAL_CLIENT_ID = "paypal-client"
    settings.PAYPAL_CLIENT_SECRET = "paypal-secret"  # noqa: S105 - test fixture
    settings.PAYPAL_ENV = "sandbox"
    cache.delete(paypal_provider.TOKEN_CACHE_KEY)


def mock_token(router: respx.Router) -> None:
    """Answer PayPal's OAuth call so the provider can make its real call."""
    router.post(f"{SANDBOX}/v1/oauth2/token").mock(
        return_value=httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
    )


def test_paypal_hands_the_buttons_a_setup_token(
    paypal_configured: None, member: User, annual_plan: MembershipPlan
) -> None:
    """The buttons approve a vault setup token, which is what ``start_mandate`` gives."""
    mandate = RenewalMandateFactory(user=member, plan=annual_plan, provider=MandateProvider.PAYPAL)
    with respx.mock as router:
        mock_token(router)
        router.post(f"{SANDBOX}/v3/vault/setup-tokens").mock(
            return_value=httpx.Response(201, json={"id": "sto_1"})
        )
        client = get_provider(MandateProvider.PAYPAL).start_mandate(mandate)

    assert client == {"setup_token": "sto_1"}


def test_paypal_exchanges_the_setup_token_for_a_vault_id(
    paypal_configured: None, member: User, annual_plan: MembershipPlan
) -> None:
    """The vault id is the handle every later renewal charge is made against."""
    mandate = RenewalMandateFactory(user=member, plan=annual_plan, provider=MandateProvider.PAYPAL)
    with respx.mock as router:
        mock_token(router)
        router.post(f"{SANDBOX}/v3/vault/payment-tokens").mock(
            return_value=httpx.Response(
                201,
                json={
                    "id": "vault_1",
                    "customer": {"id": "cust_1"},
                    "payment_source": {"paypal": {"email_address": "maria@example.org"}},
                },
            )
        )
        method = get_provider(MandateProvider.PAYPAL).confirm_mandate(
            mandate,
            setup_token=SETUP_TOKEN,
        )

    assert method.method_ref == "vault_1"


def test_paypal_labels_the_vaulted_account_for_the_member(
    paypal_configured: None, member: User, annual_plan: MembershipPlan
) -> None:
    """The member is shown their masked PayPal address, not a vault id."""
    mandate = RenewalMandateFactory(user=member, plan=annual_plan, provider=MandateProvider.PAYPAL)
    with respx.mock as router:
        mock_token(router)
        router.post(f"{SANDBOX}/v3/vault/payment-tokens").mock(
            return_value=httpx.Response(
                201,
                json={
                    "id": "vault_1",
                    "payment_source": {"paypal": {"email_address": "maria@example.org"}},
                },
            )
        )
        method = get_provider(MandateProvider.PAYPAL).confirm_mandate(
            mandate,
            setup_token=SETUP_TOKEN,
        )

    assert method.label == "PayPal (m***@example.org)"


def test_paypal_refuses_a_confirm_with_no_setup_token(
    paypal_configured: None, member: User, annual_plan: MembershipPlan
) -> None:
    """Nothing is asked of PayPal when the browser sent no token."""
    mandate = RenewalMandateFactory(user=member, plan=annual_plan, provider=MandateProvider.PAYPAL)
    with pytest.raises(PaymentVerificationError, match="No PayPal setup token"):
        get_provider(MandateProvider.PAYPAL).confirm_mandate(mandate)


def captured_order(payment: Payment) -> dict[str, Any]:
    """A vault-sourced order as PayPal returns it once captured."""
    return {
        "id": "order_renewal_1",
        "status": "COMPLETED",
        "purchase_units": [
            {
                "payments": {
                    "captures": [
                        {
                            "id": "capture_1",
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


def test_a_paypal_renewal_charges_the_vaulted_account(
    paypal_configured: None, member: User, annual_plan: MembershipPlan
) -> None:
    """A completed vault-sourced order marks the renewal payment succeeded."""
    mandate = RenewalMandateFactory(
        user=member, plan=annual_plan, provider=MandateProvider.PAYPAL, method_ref="vault_1"
    )
    payment = create_checkout(member, "annual", 0, PaymentProvider.PAYPAL)
    with respx.mock as router:
        mock_token(router)
        router.post(f"{SANDBOX}/v2/checkout/orders").mock(
            return_value=httpx.Response(201, json=captured_order(payment))
        )
        get_provider(MandateProvider.PAYPAL).charge_mandate(mandate, payment)

    payment.refresh_from_db()
    assert payment.status == PaymentStatus.SUCCEEDED


def test_a_paypal_renewal_order_carries_its_own_request_id(
    paypal_configured: None, member: User, annual_plan: MembershipPlan
) -> None:
    """The order is keyed like Stripe's charge, so a repeated scan takes nothing twice."""
    mandate = RenewalMandateFactory(
        user=member, plan=annual_plan, provider=MandateProvider.PAYPAL, method_ref="vault_1"
    )
    payment = create_checkout(member, "annual", 0, PaymentProvider.PAYPAL)
    with respx.mock as router:
        mock_token(router)
        route = router.post(f"{SANDBOX}/v2/checkout/orders").mock(
            return_value=httpx.Response(201, json=captured_order(payment))
        )
        get_provider(MandateProvider.PAYPAL).charge_mandate(mandate, payment)

    request_id = route.calls.last.request.headers["PayPal-Request-Id"]
    assert request_id == f"caldart-renewal-{payment.pk}"


def test_a_paypal_renewal_the_vault_refuses_is_a_decline(
    paypal_configured: None, member: User, annual_plan: MembershipPlan
) -> None:
    """PayPal refusing the saved account is reported as a decline, not an outage."""
    mandate = RenewalMandateFactory(
        user=member, plan=annual_plan, provider=MandateProvider.PAYPAL, method_ref="vault_1"
    )
    payment = create_checkout(member, "annual", 0, PaymentProvider.PAYPAL)
    with respx.mock as router:
        mock_token(router)
        router.post(f"{SANDBOX}/v2/checkout/orders").mock(
            return_value=httpx.Response(422, json={"message": "PAYER_ACTION_REQUIRED"})
        )
        with pytest.raises(PaymentDeclinedError, match="PAYER_ACTION_REQUIRED"):
            get_provider(MandateProvider.PAYPAL).charge_mandate(mandate, payment)


def test_a_paypal_checkout_order_asks_to_vault_when_a_mandate_is_pending(
    paypal_configured: None, member: User, annual_plan: MembershipPlan
) -> None:
    """The checkout order carries the vault instruction, or nothing is ever saved."""
    from apps.payments.renewals import begin_mandate

    payment = create_checkout(member, "annual", 0, PaymentProvider.PAYPAL)
    begin_mandate(member, plan=annual_plan, contribution_cents=0, provider=MandateProvider.PAYPAL)
    with respx.mock as router:
        mock_token(router)
        route = router.post(f"{SANDBOX}/v2/checkout/orders").mock(
            return_value=httpx.Response(201, json={"id": "order_1"})
        )
        get_provider(MandateProvider.PAYPAL).start(payment)

    body = json.loads(route.calls.last.request.content)
    assert body["payment_source"]["paypal"]["attributes"]["vault"]["store_in_vault"] == "ON_SUCCESS"


def test_a_paypal_checkout_without_a_mandate_asks_for_no_vault(
    paypal_configured: None, member: User, annual_plan: MembershipPlan
) -> None:
    """An ordinary payment saves nothing, so the order carries no vault block."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.PAYPAL)
    with respx.mock as router:
        mock_token(router)
        route = router.post(f"{SANDBOX}/v2/checkout/orders").mock(
            return_value=httpx.Response(201, json={"id": "order_1"})
        )
        get_provider(MandateProvider.PAYPAL).start(payment)

    body = json.loads(route.calls.last.request.content)
    assert "attributes" not in body["payment_source"]["paypal"]
