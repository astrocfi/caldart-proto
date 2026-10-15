"""The guards on starting and finishing a payment the payer sizes or starts at will.

A gift whose amount the payer chooses on its own -- a public gift, a donation from the
portal, a recurring donation -- has a floor, ``DONATION_MINIMUM_CENTS``; a contribution
added to dues has none.  Starting a payment, saving a method, and confirming or
capturing a payment are each rate-limited, per account for a signed-in caller and per
address for the public donation page.  A payment that has settled or failed is answered
from its row: confirming it again never asks the provider.  The docs pages are
``docs/developer/api-payments.rst`` and ``docs/developer/api-renewals.rst``.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Generator
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.test.utils import CaptureQueriesContext
from freezegun import freeze_time
from pytest_django import Settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.members.models import MembershipPlan
from apps.payments.api import views as payment_views
from apps.payments.donations import donation_token
from apps.payments.models import (
    MandateCadence,
    Payment,
    PaymentProvider,
    PaymentStatus,
)
from apps.payments.throttling import START_SCOPE, PaymentStartThrottle
from tests.factories import (
    MembershipFactory,
    MembershipPlanFactory,
    PaymentFactory,
    RenewalMandateFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db

BASE_SETTINGS = Path(__file__).resolve().parents[1] / "caldart" / "settings" / "base.py"

CHECKOUT = "/api/v1/payments/checkout"
PAYMENTS_CONFIG = "/api/v1/payments/config"
STRIPE_CONFIRM = "/api/v1/payments/stripe/confirm"
PAYPAL_CAPTURE = "/api/v1/payments/paypal/capture"
MOCK_COMPLETE = "/api/v1/payments/mock/complete"
RENEWAL_SETUP = "/api/v1/me/renewal/setup"
DONATION_SETUP = "/api/v1/me/donation/setup"
RENEWAL = "/api/v1/me/renewal"
DONATION = "/api/v1/me/donation"
RENEWAL_CONFIRM = "/api/v1/me/renewal/confirm"
DONATION_CONFIRM = "/api/v1/me/donation/confirm"

DONATIONS_CONFIG = "/api/v1/donations/config"
DONATION_CHECKOUT = "/api/v1/donations/checkout"
DONATION_STRIPE_CONFIRM = "/api/v1/donations/stripe/confirm"
DONATION_PAYPAL_CAPTURE = "/api/v1/donations/paypal/capture"
DONATION_MOCK_COMPLETE = "/api/v1/donations/mock/complete"

#: What a gift under the shipped minimum is told.
BELOW_MINIMUM = ["A donation must be at least $5.00."]

#: The throttle answer once a budget of one an hour is spent.
THROTTLED = {"detail": "Request was throttled. Expected available in 3600 seconds."}


@pytest.fixture(autouse=True)
def empty_throttle_cache() -> Generator[None]:
    """The throttle counters are shared state; no test may inherit them."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def member_client(api_client: APIClient, member: User) -> APIClient:
    """A DRF client signed in as an ordinary member."""
    api_client.force_login(member)
    return api_client


def public_gift(**overrides: Any) -> dict[str, Any]:
    """A ``POST /donations/checkout`` body for a $100 mock gift, with ``overrides``."""
    return {
        "first_name": "Pat",
        "last_name": "Giver",
        "email": "pat.giver@example.test",
        "contribution_cents": 10_000,
        "provider": "mock",
        **overrides,
    }


def execute_base_settings() -> ModuleType:
    """Execute ``settings/base.py`` as a throwaway module and return it.

    The module is loaded under its own name, outside ``sys.modules``, so the settings
    the suite runs under are left alone.
    """
    spec = importlib.util.spec_from_file_location("caldart_payment_probe", BASE_SETTINGS)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------
PAYMENT_RATE_VARIABLES = [
    ("PAYMENT_THROTTLE_START", "payment_start", "30/hour"),
    ("PAYMENT_THROTTLE_CONFIRM", "payment_confirm", "30/hour"),
]


@pytest.mark.parametrize(("variable", "scope", "default"), PAYMENT_RATE_VARIABLES)
def test_an_unset_payment_rate_uses_the_shipped_default(
    monkeypatch: pytest.MonkeyPatch, variable: str, scope: str, default: str
) -> None:
    """With no environment variable set, the shipped default rate is used."""
    monkeypatch.delenv(variable, raising=False)

    assert execute_base_settings().PAYMENT_THROTTLE_RATES[scope] == default


@pytest.mark.parametrize(("variable", "scope", "default"), PAYMENT_RATE_VARIABLES)
def test_an_empty_payment_rate_turns_the_throttle_off(
    monkeypatch: pytest.MonkeyPatch, variable: str, scope: str, default: str
) -> None:
    """An empty environment variable turns that payment throttle off."""
    monkeypatch.setenv(variable, "")

    assert execute_base_settings().PAYMENT_THROTTLE_RATES[scope] is None


def test_a_malformed_payment_rate_stops_start_up(monkeypatch: pytest.MonkeyPatch) -> None:
    """A payment rate DRF could not parse raises ``ImproperlyConfigured`` naming it."""
    monkeypatch.setenv("PAYMENT_THROTTLE_START", "lots")

    with pytest.raises(ImproperlyConfigured, match="PAYMENT_THROTTLE_START"):
        execute_base_settings()


def test_an_empty_payment_rate_makes_the_throttle_inert(settings: Settings) -> None:
    """An empty configured rate makes ``get_rate`` return ``None``."""
    settings.PAYMENT_THROTTLE_RATES = {START_SCOPE: ""}

    assert PaymentStartThrottle().get_rate() is None


def test_the_minimum_defaults_to_five_dollars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unset, ``DONATION_MINIMUM_CENTS`` is 500."""
    monkeypatch.delenv("DONATION_MINIMUM_CENTS", raising=False)

    assert execute_base_settings().DONATION_MINIMUM_CENTS == 500


def test_a_minimum_of_nothing_stops_start_up(monkeypatch: pytest.MonkeyPatch) -> None:
    """A minimum under one cent raises ``ImproperlyConfigured`` naming the variable."""
    monkeypatch.setenv("DONATION_MINIMUM_CENTS", "0")

    with pytest.raises(ImproperlyConfigured, match="DONATION_MINIMUM_CENTS"):
        execute_base_settings()


# --------------------------------------------------------------------------
# The minimum gift
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "body",
    [
        {"plan": None, "contribution_cents": 499, "provider": "mock"},
        {
            "plan": None,
            "contribution_cents": 499,
            "provider": "mock",
            "auto_renew": True,
            "cadence": MandateCadence.MONTHLY,
        },
    ],
    ids=["one-time", "recurring"],
)
def test_a_portal_donation_under_the_minimum_is_refused(
    member_client: APIClient, body: dict[str, Any]
) -> None:
    """A donation of $4.99 from the portal is a 400 naming ``contribution_cents``."""
    response = member_client.post(CHECKOUT, body, format="json")

    assert (response.status_code, response.json()) == (400, {"contribution_cents": BELOW_MINIMUM})


def test_a_refused_portal_donation_writes_no_payment(member_client: APIClient) -> None:
    """The refusal comes before any payment row is made."""
    member_client.post(
        CHECKOUT, {"plan": None, "contribution_cents": 499, "provider": "mock"}, format="json"
    )

    assert Payment.objects.count() == 0


def test_a_portal_donation_of_the_minimum_is_started(member_client: APIClient) -> None:
    """A donation of exactly $5.00 starts."""
    response = member_client.post(
        CHECKOUT, {"plan": None, "contribution_cents": 500, "provider": "mock"}, format="json"
    )

    assert response.status_code == 201


def test_a_small_contribution_on_top_of_dues_is_accepted(
    member_client: APIClient, annual_plan: MembershipPlan
) -> None:
    """A contribution added to a membership fee has no minimum."""
    response = member_client.post(
        CHECKOUT, {"plan": "annual", "contribution_cents": 100, "provider": "mock"}, format="json"
    )

    assert response.status_code == 201


def test_the_minimum_follows_the_setting(member_client: APIClient, settings: Settings) -> None:
    """``DONATION_MINIMUM_CENTS`` sets the floor and the words that state it."""
    settings.DONATION_MINIMUM_CENTS = 1_000

    response = member_client.post(
        CHECKOUT, {"plan": None, "contribution_cents": 999, "provider": "mock"}, format="json"
    )

    assert response.json() == {"contribution_cents": ["A donation must be at least $10.00."]}


def test_a_life_member_donation_under_the_minimum_is_refused(
    member_client: APIClient, member: User, life_plan: MembershipPlan
) -> None:
    """A life member's checkout is a contribution alone, so the floor applies."""
    MembershipFactory(user=member, plan=life_plan)
    response = member_client.post(
        CHECKOUT, {"plan": None, "contribution_cents": 100, "provider": "mock"}, format="json"
    )

    assert response.json() == {"contribution_cents": BELOW_MINIMUM}


def test_a_recurring_donation_setup_under_the_minimum_is_refused(
    member_client: APIClient,
) -> None:
    """Setting up $4.99 a month is a 400 naming ``contribution_cents``."""
    response = member_client.post(
        DONATION_SETUP,
        {"contribution_cents": 499, "provider": "mock", "cadence": MandateCadence.MONTHLY},
        format="json",
    )

    assert response.json() == {"contribution_cents": BELOW_MINIMUM}


def test_a_renewal_setup_takes_a_small_contribution(
    member_client: APIClient, annual_plan: MembershipPlan
) -> None:
    """A renewal's contribution rides on its dues, so it has no minimum."""
    response = member_client.post(
        RENEWAL_SETUP,
        {"plan": "annual", "contribution_cents": 100, "provider": "mock"},
        format="json",
    )

    assert response.status_code == 200


def test_changing_a_donation_to_under_the_minimum_is_refused(
    member_client: APIClient, member: User
) -> None:
    """``PATCH /me/donation`` to $1.00 is a 400 naming ``contribution_cents``."""
    RenewalMandateFactory(user=member, plan=None, contribution_cents=2_000)

    response = member_client.patch(DONATION, {"contribution_cents": 100}, format="json")

    assert response.json() == {"contribution_cents": BELOW_MINIMUM}


def test_changing_a_renewal_contribution_to_a_small_one_is_accepted(
    member_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """``PATCH /me/renewal`` takes a $1.00 contribution on top of the dues."""
    RenewalMandateFactory(user=member, plan=annual_plan)

    response = member_client.patch(RENEWAL, {"contribution_cents": 100}, format="json")

    assert response.status_code == 200


def test_a_public_gift_under_the_minimum_is_refused(api_client: APIClient) -> None:
    """A public gift of $4.99 is a 400 naming ``contribution_cents``."""
    response = api_client.post(
        DONATION_CHECKOUT, public_gift(contribution_cents=499), format="json"
    )

    assert (response.status_code, response.json()) == (400, {"contribution_cents": BELOW_MINIMUM})


def test_a_refused_public_gift_makes_no_donor(api_client: APIClient) -> None:
    """The refusal comes before any donor account is found or made."""
    api_client.post(DONATION_CHECKOUT, public_gift(contribution_cents=499), format="json")

    assert not User.objects.filter(email="pat.giver@example.test").exists()


def test_a_public_gift_of_the_minimum_is_started(api_client: APIClient) -> None:
    """A public gift of exactly $5.00 starts."""
    response = api_client.post(
        DONATION_CHECKOUT, public_gift(contribution_cents=500), format="json"
    )

    assert response.status_code == 201


@pytest.mark.parametrize(
    ("url", "signed_in"),
    [(PAYMENTS_CONFIG, True), (DONATIONS_CONFIG, False)],
    ids=["portal", "public"],
)
def test_each_config_names_the_minimum(
    api_client: APIClient,
    member: User,
    settings: Settings,
    url: str,
    signed_in: bool,
) -> None:
    """Both donation forms read the floor from their config."""
    settings.DONATION_MINIMUM_CENTS = 700
    if signed_in:
        api_client.force_login(member)

    assert api_client.get(url).json()["donation_minimum_cents"] == 700


# --------------------------------------------------------------------------
# Throttles
# --------------------------------------------------------------------------
def start_bodies(plan: MembershipPlan) -> dict[str, dict[str, Any]]:
    """A well-formed body for each endpoint that starts a payment or a method."""
    return {
        CHECKOUT: {"plan": plan.slug, "contribution_cents": 0, "provider": "mock"},
        RENEWAL_SETUP: {"plan": plan.slug, "contribution_cents": 0, "provider": "mock"},
        DONATION_SETUP: {"contribution_cents": 2_000, "provider": "mock"},
    }


@pytest.mark.parametrize("url", [CHECKOUT, RENEWAL_SETUP, DONATION_SETUP])
def test_starting_is_throttled_per_account(
    member_client: APIClient, annual_plan: MembershipPlan, settings: Settings, url: str
) -> None:
    """Past the ``payment_start`` rate, a second start within the hour is a 429."""
    settings.PAYMENT_THROTTLE_RATES = {"payment_start": "1/hour"}
    body = start_bodies(annual_plan)[url]
    with freeze_time("2026-10-14 12:00:00"):
        member_client.post(url, body, format="json")
        response = member_client.post(url, body, format="json")

    assert (response.status_code, response.json()) == (429, THROTTLED)


def test_the_start_budget_is_shared_by_checkout_and_setup(
    member_client: APIClient, annual_plan: MembershipPlan, settings: Settings
) -> None:
    """Checkout and saving a method draw on one budget, so neither is a way round it."""
    settings.PAYMENT_THROTTLE_RATES = {"payment_start": "1/hour"}
    bodies = start_bodies(annual_plan)
    with freeze_time("2026-10-14 12:00:00"):
        member_client.post(CHECKOUT, bodies[CHECKOUT], format="json")
        response = member_client.post(DONATION_SETUP, bodies[DONATION_SETUP], format="json")

    assert response.status_code == 429


def test_each_account_has_its_own_start_budget(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, settings: Settings
) -> None:
    """One member's spent budget never stops another member."""
    settings.PAYMENT_THROTTLE_RATES = {"payment_start": "1/hour"}
    body = start_bodies(annual_plan)[CHECKOUT]
    with freeze_time("2026-10-14 12:00:00"):
        api_client.force_login(member)
        api_client.post(CHECKOUT, body, format="json")
        api_client.force_login(UserFactory())
        response = api_client.post(CHECKOUT, body, format="json")

    assert response.status_code == 201


def own_payment(user: User, provider: str) -> Payment:
    """A succeeded ``provider`` payment of ``user``'s, which a confirm answers at once."""
    return PaymentFactory(user=user, provider=provider, status=PaymentStatus.SUCCEEDED)


def confirm_body(payment: Payment, url: str) -> dict[str, Any]:
    """The body ``url`` takes for ``payment``, the token included for a public route.

    A PayPal capture names no order: it captures the one the payment stored.
    """
    body: dict[str, Any] = {"payment_id": payment.pk}
    if url in (STRIPE_CONFIRM, DONATION_STRIPE_CONFIRM):
        body["payment_intent_id"] = payment.provider_ref
    if url.startswith("/api/v1/donations/"):
        body["token"] = donation_token(payment)
    return body


@pytest.mark.parametrize(
    ("url", "provider"),
    [(STRIPE_CONFIRM, PaymentProvider.STRIPE), (PAYPAL_CAPTURE, PaymentProvider.PAYPAL)],
    ids=["stripe", "paypal"],
)
def test_confirming_is_throttled_per_account(
    member_client: APIClient, member: User, settings: Settings, url: str, provider: str
) -> None:
    """Past the ``payment_confirm`` rate, a second confirm within the hour is a 429."""
    settings.PAYMENT_THROTTLE_RATES = {"payment_confirm": "1/hour"}
    body = confirm_body(own_payment(member, provider), url)
    with freeze_time("2026-10-14 12:00:00"):
        member_client.post(url, body, format="json")
        response = member_client.post(url, body, format="json")

    assert (response.status_code, response.json()) == (429, THROTTLED)


@pytest.mark.parametrize(
    ("url", "provider"),
    [
        (DONATION_STRIPE_CONFIRM, PaymentProvider.STRIPE),
        (DONATION_PAYPAL_CAPTURE, PaymentProvider.PAYPAL),
    ],
    ids=["stripe", "paypal"],
)
def test_a_public_confirm_is_throttled_per_address(
    api_client: APIClient, settings: Settings, url: str, provider: str
) -> None:
    """Past the ``donate_confirm`` rate, a second confirm from one address is a 429."""
    settings.AUTH_THROTTLE_RATES = {"donate_confirm": "1/hour"}
    body = confirm_body(own_payment(UserFactory(), provider), url)
    with freeze_time("2026-10-14 12:00:00"):
        api_client.post(url, body, format="json")
        response = api_client.post(url, body, format="json")

    assert (response.status_code, response.json()) == (429, THROTTLED)


def test_a_second_address_keeps_its_own_public_confirm_budget(
    api_client: APIClient, settings: Settings
) -> None:
    """One address spending the ``donate_confirm`` rate never stops another."""
    settings.AUTH_THROTTLE_RATES = {"donate_confirm": "1/hour"}
    body = confirm_body(own_payment(UserFactory(), PaymentProvider.STRIPE), DONATION_STRIPE_CONFIRM)
    with freeze_time("2026-10-14 12:00:00"):
        api_client.post(DONATION_STRIPE_CONFIRM, body, format="json", REMOTE_ADDR="10.0.0.1")
        response = api_client.post(
            DONATION_STRIPE_CONFIRM, body, format="json", REMOTE_ADDR="10.0.0.2"
        )

    assert response.status_code == 200


def test_a_signed_in_session_is_counted_by_address_on_the_public_confirm(
    api_client: APIClient, member: User, settings: Settings
) -> None:
    """Signing in buys no budget of its own on the public route: the address counts."""
    settings.AUTH_THROTTLE_RATES = {"donate_confirm": "1/hour"}
    body = confirm_body(own_payment(UserFactory(), PaymentProvider.STRIPE), DONATION_STRIPE_CONFIRM)
    with freeze_time("2026-10-14 12:00:00"):
        api_client.post(DONATION_STRIPE_CONFIRM, body, format="json")
        api_client.force_login(member)
        response = api_client.post(DONATION_STRIPE_CONFIRM, body, format="json")

    assert response.status_code == 429


def test_each_account_has_its_own_confirm_budget(
    api_client: APIClient, member: User, settings: Settings
) -> None:
    """One member spending the ``payment_confirm`` rate never stops another member."""
    settings.PAYMENT_THROTTLE_RATES = {"payment_confirm": "1/hour"}
    other = UserFactory()
    with freeze_time("2026-10-14 12:00:00"):
        api_client.force_login(member)
        mine = confirm_body(own_payment(member, PaymentProvider.STRIPE), STRIPE_CONFIRM)
        api_client.post(STRIPE_CONFIRM, mine, format="json")
        api_client.force_login(other)
        theirs = confirm_body(own_payment(other, PaymentProvider.STRIPE), STRIPE_CONFIRM)
        response = api_client.post(STRIPE_CONFIRM, theirs, format="json")

    assert response.status_code == 200


@pytest.mark.parametrize("url", [RENEWAL_CONFIRM, DONATION_CONFIRM])
def test_saving_a_method_is_throttled_per_account(
    member_client: APIClient, settings: Settings, url: str
) -> None:
    """The method confirms share the ``payment_confirm`` rate with payment confirms."""
    settings.PAYMENT_THROTTLE_RATES = {"payment_confirm": "1/hour"}
    with freeze_time("2026-10-14 12:00:00"):
        member_client.post(url, {}, format="json")
        response = member_client.post(url, {}, format="json")

    assert (response.status_code, response.json()) == (429, THROTTLED)


# --------------------------------------------------------------------------
# A plan priced under the minimum
# --------------------------------------------------------------------------
@pytest.fixture
def free_plan(db: None) -> MembershipPlan:
    """An active plan that costs nothing."""
    return MembershipPlanFactory(slug="free", name="Free", price_cents=0)


def test_a_free_plan_with_a_tiny_contribution_is_refused(
    member_client: APIClient, free_plan: MembershipPlan
) -> None:
    """A free plan plus one cent is a charge under the minimum, refused as one."""
    response = member_client.post(
        CHECKOUT, {"plan": "free", "contribution_cents": 1, "provider": "mock"}, format="json"
    )

    assert response.json() == {"contribution_cents": ["A payment must be at least $5.00."]}


def test_a_free_plan_with_a_contribution_of_the_minimum_is_started(
    member_client: APIClient, free_plan: MembershipPlan
) -> None:
    """A free plan whose contribution brings the charge to the minimum starts."""
    response = member_client.post(
        CHECKOUT, {"plan": "free", "contribution_cents": 500, "provider": "mock"}, format="json"
    )

    assert response.status_code == 201


def test_a_plan_priced_under_the_minimum_must_reach_it(member_client: APIClient) -> None:
    """A $3.00 plan on its own is a charge under the minimum."""
    MembershipPlanFactory(slug="cheap", name="Cheap", price_cents=300)

    response = member_client.post(
        CHECKOUT, {"plan": "cheap", "contribution_cents": 0, "provider": "mock"}, format="json"
    )

    assert response.status_code == 400


# --------------------------------------------------------------------------
# Confirm once
# --------------------------------------------------------------------------
def test_the_provider_is_asked_while_the_payment_row_is_locked(
    api_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """By the time the provider is asked, the payment's row has been locked."""
    payment = PaymentFactory(user=member, plan=annual_plan, provider=PaymentProvider.MOCK)
    locks_seen: list[int] = []

    with CaptureQueriesContext(connection) as queries:

        def confirm(locked: Payment, **arguments: str) -> bool:
            locks_seen.append(
                sum(
                    "FOR UPDATE" in query["sql"] and '"payments_payment"' in query["sql"]
                    for query in queries.captured_queries
                )
            )
            return True

        monkeypatch.setattr(
            payment_views, "get_provider", lambda slug: SimpleNamespace(confirm=confirm)
        )
        api_client.force_login(member)
        api_client.post(
            MOCK_COMPLETE, {"payment_id": payment.pk, "outcome": "succeed"}, format="json"
        )

    assert locks_seen == [1]


@pytest.fixture
def provider_never_asked(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make any provider lookup by the confirm endpoints fail the test outright."""

    def refuse(slug: str) -> None:
        raise AssertionError(f"The {slug} provider was asked about a settled payment.")

    monkeypatch.setattr(payment_views, "get_provider", refuse)


SETTLED = [
    PaymentStatus.SUCCEEDED,
    PaymentStatus.FAILED,
    PaymentStatus.REFUNDED,
    PaymentStatus.PARTIALLY_REFUNDED,
]

CONFIRM_ROUTES = [
    (STRIPE_CONFIRM, PaymentProvider.STRIPE),
    (PAYPAL_CAPTURE, PaymentProvider.PAYPAL),
    (MOCK_COMPLETE, PaymentProvider.MOCK),
    (DONATION_STRIPE_CONFIRM, PaymentProvider.STRIPE),
    (DONATION_PAYPAL_CAPTURE, PaymentProvider.PAYPAL),
    (DONATION_MOCK_COMPLETE, PaymentProvider.MOCK),
]


def settled_payment(user: User, provider: str, status: str) -> Payment:
    """A ``provider`` payment of ``user``'s that has already reached ``status``."""
    return PaymentFactory(user=user, provider=provider, status=status)


def confirm_again(
    api_client: APIClient, member: User, url: str, payment: Payment
) -> dict[str, Any]:
    """Post ``url`` for ``payment`` as its owner, and return the 200 body."""
    if url.startswith("/api/v1/payments/"):
        api_client.force_login(member)
    body = confirm_body(payment, url)
    if url.endswith("/mock/complete"):
        body["outcome"] = "succeed"
    response = api_client.post(url, body, format="json")
    assert response.status_code == 200, response.content
    answer: dict[str, Any] = response.json()
    return answer


@pytest.mark.parametrize("status", SETTLED)
@pytest.mark.parametrize(("url", "provider"), CONFIRM_ROUTES)
@pytest.mark.usefixtures("provider_never_asked")
def test_a_settled_payment_is_answered_from_its_row(
    api_client: APIClient, member: User, url: str, provider: str, status: str
) -> None:
    """Confirming a settled or failed payment answers its status, asking no provider."""
    payment = settled_payment(member, provider, status)

    assert confirm_again(api_client, member, url, payment)["status"] == status


@pytest.mark.usefixtures("provider_never_asked")
def test_a_failed_payment_cannot_be_succeeded_again(api_client: APIClient, member: User) -> None:
    """A failed mock payment completed with ``succeed`` stays failed."""
    payment = settled_payment(member, PaymentProvider.MOCK, PaymentStatus.FAILED)
    confirm_again(api_client, member, MOCK_COMPLETE, payment)

    payment.refresh_from_db()
    assert payment.status == PaymentStatus.FAILED


def test_a_pending_payment_is_still_confirmed(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The first confirm of a pending payment reaches the provider and settles it."""
    payment = PaymentFactory(user=member, plan=annual_plan, provider=PaymentProvider.MOCK)

    body = confirm_again(api_client, member, MOCK_COMPLETE, payment)

    assert body["status"] == PaymentStatus.SUCCEEDED
