"""The checkout API: config, checkout, mock completion, lookup.

The role matrix lives here too: who may start a checkout, complete one, and
read a payment back.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from pytest_django.fixtures import Settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import ACCOUNT_ADMIN, MEMBER, SYSTEM_ADMIN
from apps.members.models import Membership, MembershipPlan
from apps.members.services import membership_status
from apps.payments.models import Payment, PaymentProvider, PaymentStatus, PaymentWallet
from tests.conftest import ROLE_MATRIX, role_matrix
from tests.factories import PaymentFactory, UserFactory

pytestmark = pytest.mark.django_db

CONFIG = "/api/v1/payments/config"
CHECKOUT = "/api/v1/payments/checkout"
MOCK_COMPLETE = "/api/v1/payments/mock/complete"


@pytest.fixture(autouse=True)
def _mock_only(settings: Settings) -> None:
    """Default to "only the mock provider is configured"."""
    settings.PAYMENTS_MOCK_ENABLED = True
    settings.STRIPE_SECRET_KEY = ""
    settings.STRIPE_PUBLISHABLE_KEY = ""
    settings.PAYPAL_CLIENT_ID = ""
    settings.PAYPAL_CLIENT_SECRET = ""


def start_mock_checkout(
    api_client: APIClient, plan: str | None = "annual", contribution: int = 0
) -> dict[str, Any]:
    """Start and return a successful mock checkout's response body."""
    response = api_client.post(
        CHECKOUT, {"plan": plan, "contribution_cents": contribution, "provider": "mock"}
    )
    assert response.status_code == 201, response.data
    body: dict[str, Any] = response.data
    return body


# --------------------------------------------------------------------------
# GET /payments/config
# --------------------------------------------------------------------------
def test_config_lists_the_configured_providers(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, life_plan: MembershipPlan
) -> None:
    """With nothing else configured, only the mock provider and the plans are listed."""
    api_client.force_login(member)
    body = api_client.get(CONFIG).data

    assert body["providers"] == ["mock"]
    assert body["stripe_publishable_key"] == ""
    assert body["paypal_client_id"] == ""
    assert [plan["slug"] for plan in body["plans"]] == ["annual", "life"]
    assert body["plans"][0]["price_cents"] == 4_500


def test_config_includes_stripe_and_paypal_when_keys_are_set(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, settings: Settings
) -> None:
    """Configuring Stripe and PayPal keys adds both providers to the list."""
    settings.STRIPE_SECRET_KEY = "sk_test_x"  # noqa: S105 - test fixture
    settings.STRIPE_PUBLISHABLE_KEY = "pk_test_x"
    settings.PAYPAL_CLIENT_ID = "paypal-id"
    settings.PAYPAL_CLIENT_SECRET = "paypal-secret"  # noqa: S105 - test fixture

    api_client.force_login(member)
    body = api_client.get(CONFIG).data

    assert body["providers"] == ["stripe", "paypal", "mock"]
    assert body["stripe_publishable_key"] == "pk_test_x"
    assert body["paypal_client_id"] == "paypal-id"


def test_config_hides_the_mock_provider_in_production(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, settings: Settings
) -> None:
    """Disabling PAYMENTS_MOCK_ENABLED drops the mock provider from the list."""
    settings.PAYMENTS_MOCK_ENABLED = False
    api_client.force_login(member)
    assert api_client.get(CONFIG).data["providers"] == []


def test_config_offers_the_contribution_tiers(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The config lists the fixed contribution tiers with their labels."""
    api_client.force_login(member)
    tiers = api_client.get(CONFIG).data["contribution_tiers"]
    assert [tier["cents"] for tier in tiers] == [
        0,
        2_000,
        10_000,
        30_000,
        100_000,
        300_000,
        1_000_000,
    ]
    assert tiers[1]["label"] == "Participating"


def test_config_omits_inactive_plans(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, life_plan: MembershipPlan
) -> None:
    """An inactive plan is left out of the config's plan list."""
    life_plan.is_active = False
    life_plan.save(update_fields=["is_active"])
    api_client.force_login(member)
    assert [p["slug"] for p in api_client.get(CONFIG).data["plans"]] == ["annual"]


def test_config_requires_a_session(api_client: APIClient, annual_plan: MembershipPlan) -> None:
    """Reading the config while signed out is a 401."""
    assert api_client.get(CONFIG).status_code == 401


# --------------------------------------------------------------------------
# POST /payments/checkout
# --------------------------------------------------------------------------
def test_checkout_creates_a_pending_payment(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """Checkout creates a pending payment for the plan price plus the contribution."""
    api_client.force_login(member)
    body = start_mock_checkout(api_client, contribution=10_000)

    payment = Payment.objects.get(pk=body["payment_id"])
    assert body["provider"] == "mock"
    assert body["client"] == {}
    assert payment.user == member
    assert payment.status == PaymentStatus.PENDING
    assert payment.amount_cents == 14_500
    assert payment.plan_amount_cents == 4_500
    assert payment.contribution_cents == 10_000


def test_checkout_ignores_an_amount_sent_by_the_client(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The server recomputes the total, always."""
    api_client.force_login(member)
    response = api_client.post(
        CHECKOUT,
        {"plan": "annual", "contribution_cents": 0, "provider": "mock", "amount_cents": 1},
    )
    assert response.status_code == 201
    assert Payment.objects.get(pk=response.data["payment_id"]).amount_cents == 4_500


def test_checkout_accepts_a_donation_without_a_plan(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A checkout with a contribution and no plan records no plan and the full amount."""
    api_client.force_login(member)
    response = api_client.post(
        CHECKOUT, {"plan": None, "contribution_cents": 5_000, "provider": "mock"}
    )
    assert response.status_code == 201
    payment = Payment.objects.get(pk=response.data["payment_id"])
    assert payment.plan is None
    assert payment.amount_cents == 5_000


def test_checkout_rejects_an_unknown_plan(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A plan slug that does not exist is refused with a 400 naming the plan field."""
    api_client.force_login(member)
    response = api_client.post(
        CHECKOUT, {"plan": "platinum", "contribution_cents": 0, "provider": "mock"}
    )
    assert response.status_code == 400
    assert "plan" in response.data


def test_checkout_rejects_a_negative_contribution(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A negative contribution is refused with a 400."""
    api_client.force_login(member)
    response = api_client.post(
        CHECKOUT, {"plan": "annual", "contribution_cents": -1, "provider": "mock"}
    )
    assert response.status_code == 400


def test_checkout_rejects_an_unconfigured_provider(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A provider with no keys configured is refused, naming the provider field."""
    api_client.force_login(member)
    response = api_client.post(
        CHECKOUT, {"plan": "annual", "contribution_cents": 0, "provider": "stripe"}
    )
    assert response.status_code == 400
    assert "provider" in response.data


def test_checkout_rejects_an_unknown_provider(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A provider slug outside the known choices is refused with a 400."""
    api_client.force_login(member)
    response = api_client.post(
        CHECKOUT, {"plan": "annual", "contribution_cents": 0, "provider": "bitcoin"}
    )
    assert response.status_code == 400


def test_checkout_requires_a_session(api_client: APIClient, annual_plan: MembershipPlan) -> None:
    """Starting a checkout while signed out is a 401 and creates no payment."""
    response = api_client.post(
        CHECKOUT, {"plan": "annual", "contribution_cents": 0, "provider": "mock"}
    )
    assert response.status_code == 401
    assert Payment.objects.count() == 0


@pytest.mark.parametrize("slug", ROLE_MATRIX)
def test_every_signed_in_role_may_start_a_checkout(
    api_client: APIClient,
    all_role_users: dict[str, User],
    annual_plan: MembershipPlan,
    slug: str,
) -> None:
    """Every signed-in role, not only members, may start a checkout."""
    api_client.force_login(all_role_users[slug])
    response = api_client.post(
        CHECKOUT, {"plan": "annual", "contribution_cents": 0, "provider": "mock"}
    )
    assert response.status_code == 201


# --------------------------------------------------------------------------
# POST /payments/mock/complete
# --------------------------------------------------------------------------
def test_mock_complete_activates_the_membership(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """Completing a checkout through the mock provider grants a current membership."""
    api_client.force_login(member)
    checkout = start_mock_checkout(api_client, contribution=2_000)

    response = api_client.post(
        MOCK_COMPLETE, {"payment_id": checkout["payment_id"], "outcome": "succeed"}
    )
    assert response.status_code == 200
    assert response.data["status"] == "succeeded"
    assert response.data["membership"]["status"] == "current"
    assert response.data["membership"]["plan"] == "Annual"

    payment = Payment.objects.get(pk=checkout["payment_id"])
    assert payment.wallet == PaymentWallet.MOCK
    assert payment.completed_at is not None
    assert Membership.objects.filter(payment=payment).count() == 1


def test_mock_complete_failure_grants_nothing(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """Completing with outcome=fail marks the payment failed and grants no membership."""
    api_client.force_login(member)
    checkout = start_mock_checkout(api_client)

    response = api_client.post(
        MOCK_COMPLETE, {"payment_id": checkout["payment_id"], "outcome": "fail"}
    )
    assert response.status_code == 200
    assert response.data["status"] == "failed"
    assert response.data["membership"]["status"] == "none"
    assert Membership.objects.count() == 0


def test_mock_complete_is_404_when_the_mock_provider_is_off(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, settings: Settings
) -> None:
    """Completing through the mock provider while it is disabled is a 404."""
    api_client.force_login(member)
    checkout = start_mock_checkout(api_client)

    settings.PAYMENTS_MOCK_ENABLED = False
    response = api_client.post(
        MOCK_COMPLETE, {"payment_id": checkout["payment_id"], "outcome": "succeed"}
    )
    assert response.status_code == 404


def test_mock_complete_rejects_another_members_payment(
    api_client: APIClient,
    member: User,
    user_factory: type[UserFactory],
    annual_plan: MembershipPlan,
) -> None:
    """A member cannot complete a payment that belongs to someone else."""
    api_client.force_login(member)
    checkout = start_mock_checkout(api_client)

    other = user_factory(email="other@example.test", roles=[MEMBER])
    api_client.force_login(other)
    response = api_client.post(
        MOCK_COMPLETE, {"payment_id": checkout["payment_id"], "outcome": "succeed"}
    )
    assert response.status_code == 404
    assert Membership.objects.count() == 0


def test_mock_complete_rejects_a_bad_outcome(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """An outcome outside succeed/fail is refused with a 400."""
    api_client.force_login(member)
    checkout = start_mock_checkout(api_client)
    response = api_client.post(
        MOCK_COMPLETE, {"payment_id": checkout["payment_id"], "outcome": "maybe"}
    )
    assert response.status_code == 400


def test_completing_twice_grants_one_term_only(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """Completing the same payment twice grants exactly one membership term."""
    api_client.force_login(member)
    checkout = start_mock_checkout(api_client)
    payload = {"payment_id": checkout["payment_id"], "outcome": "succeed"}

    first = api_client.post(MOCK_COMPLETE, payload)
    second = api_client.post(MOCK_COMPLETE, payload)

    assert first.status_code == second.status_code == 200
    assert Membership.objects.filter(user=member).count() == 1


# --------------------------------------------------------------------------
# Renewal semantics: the new term starts the day after the old one
# --------------------------------------------------------------------------
def test_renewing_starts_the_day_after_the_current_expiry(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A renewal's term starts the day after the current term's expiry."""
    api_client.force_login(member)
    first = start_mock_checkout(api_client)
    api_client.post(MOCK_COMPLETE, {"payment_id": first["payment_id"], "outcome": "succeed"})
    first_expiry = membership_status(member)["expires_on"]

    second = start_mock_checkout(api_client)
    response = api_client.post(
        MOCK_COMPLETE, {"payment_id": second["payment_id"], "outcome": "succeed"}
    )

    terms = list(Membership.objects.filter(user=member).order_by("starts_on"))
    assert len(terms) == 2
    assert terms[0].ends_on is not None
    assert terms[1].starts_on == terms[0].ends_on + timedelta(days=1)
    assert first_expiry is not None
    assert (
        response.data["membership"]["expires_on"]
        == (first_expiry + timedelta(days=365)).isoformat()
    )


def test_a_lifetime_plan_never_expires(
    api_client: APIClient, member: User, life_plan: MembershipPlan
) -> None:
    """A lifetime plan's membership reports is_lifetime true and no expiry date."""
    api_client.force_login(member)
    checkout = start_mock_checkout(api_client, plan="life")
    response = api_client.post(
        MOCK_COMPLETE, {"payment_id": checkout["payment_id"], "outcome": "succeed"}
    )
    assert response.data["membership"]["is_lifetime"] is True
    assert response.data["membership"]["expires_on"] is None


# --------------------------------------------------------------------------
# Retrieve one payment
# --------------------------------------------------------------------------
def test_owner_may_read_their_payment(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The payment's owner may read it back, including its membership status."""
    api_client.force_login(member)
    checkout = start_mock_checkout(api_client)

    response = api_client.get(f"/api/v1/payments/{checkout['payment_id']}")
    assert response.status_code == 200
    assert response.data["status"] == "pending"
    assert response.data["membership"]["status"] == "none"


def test_account_admin_may_read_any_payment(
    api_client: APIClient, member: User, account_admin: User, annual_plan: MembershipPlan
) -> None:
    """An account admin may read any member's payment."""
    api_client.force_login(member)
    checkout = start_mock_checkout(api_client)

    api_client.force_login(account_admin)
    response = api_client.get(f"/api/v1/payments/{checkout['payment_id']}")
    assert response.status_code == 200


def test_another_member_may_not_read_a_payment(
    api_client: APIClient,
    member: User,
    user_factory: type[UserFactory],
    annual_plan: MembershipPlan,
) -> None:
    """A member who does not own the payment gets a 403 reading it."""
    api_client.force_login(member)
    checkout = start_mock_checkout(api_client)

    nosy = user_factory(email="nosy@example.test", roles=[MEMBER])
    api_client.force_login(nosy)
    assert api_client.get(f"/api/v1/payments/{checkout['payment_id']}").status_code == 403


def test_anonymous_may_not_read_a_payment(
    api_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    payment_factory: type[PaymentFactory],
) -> None:
    """An anonymous caller gets a 401 reading any payment."""
    payment = payment_factory(user=member, plan=annual_plan)
    assert api_client.get(f"/api/v1/payments/{payment.pk}").status_code == 401


@pytest.mark.parametrize(("slug", "allowed"), role_matrix(MEMBER, ACCOUNT_ADMIN, SYSTEM_ADMIN))
def test_payment_detail_role_matrix(
    api_client: APIClient,
    all_role_users: dict[str, User],
    annual_plan: MembershipPlan,
    payment_factory: type[PaymentFactory],
    slug: str,
    allowed: bool,
) -> None:
    """Only the owner and an account admin (or system admin) may look."""
    owner = all_role_users[MEMBER]
    payment = payment_factory(user=owner, plan=annual_plan, provider=PaymentProvider.MOCK)
    url = f"/api/v1/payments/{payment.pk}"

    api_client.force_login(all_role_users[slug])
    assert api_client.get(url).status_code == (200 if allowed else 403)


def test_unknown_payment_is_404(api_client: APIClient, member: User) -> None:
    """Reading a payment id that does not exist is a 404."""
    api_client.force_login(member)
    assert api_client.get("/api/v1/payments/999999").status_code == 404
