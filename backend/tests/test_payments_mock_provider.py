"""Mock provider end-to-end: checkout -> success -> current membership."""

from __future__ import annotations

import re

import pytest
from pytest_django.fixtures import Settings

from apps.accounts.models import User
from apps.members.models import Membership, MembershipPlan, MembershipSource
from apps.members.services import membership_status
from apps.payments.models import Payment, PaymentProvider, PaymentStatus, PaymentWallet
from apps.payments.providers import available_providers, get_provider
from apps.payments.providers.base import ProviderNotConfiguredError
from apps.payments.providers.mock import MockPaymentsDisabledError
from apps.payments.services import create_checkout, mark_failed, mark_succeeded
from caldart.exceptions import DomainValidationError

pytestmark = pytest.mark.django_db


def test_create_checkout_computes_the_total(member: User, annual_plan: MembershipPlan) -> None:
    """A checkout's amount is the plan price plus the contribution, exactly."""
    payment = create_checkout(member, "annual", 10_000, PaymentProvider.MOCK)
    assert payment.status == PaymentStatus.PENDING
    assert payment.plan_amount_cents == 4_500
    assert payment.contribution_cents == 10_000
    assert payment.amount_cents == 14_500
    assert payment.currency == "usd"


def test_create_checkout_rejects_an_unknown_plan(member: User, annual_plan: MembershipPlan) -> None:
    """A plan slug that does not exist is refused rather than silently ignored."""
    with pytest.raises(
        DomainValidationError, match=re.escape("Unknown membership plan 'platinum'.")
    ):
        create_checkout(member, "platinum", 0, PaymentProvider.MOCK)


def test_the_unknown_plan_refusal_names_the_plan_field(
    member: User, annual_plan: MembershipPlan
) -> None:
    """The refusal names ``plan`` as the offending field."""
    with pytest.raises(DomainValidationError) as refusal:
        create_checkout(member, "platinum", 0, PaymentProvider.MOCK)
    assert refusal.value.field == "plan"


def test_create_checkout_rejects_an_unknown_provider(
    member: User, annual_plan: MembershipPlan
) -> None:
    """A provider slug outside ``PaymentProvider`` is refused by name."""
    message = re.escape("Unknown payment provider 'bitcoin'.")
    with pytest.raises(DomainValidationError, match=message):
        create_checkout(member, "annual", 0, "bitcoin")


def test_the_unknown_provider_refusal_names_the_provider_field(
    member: User, annual_plan: MembershipPlan
) -> None:
    """The refusal names ``provider`` as the offending field."""
    with pytest.raises(DomainValidationError) as refusal:
        create_checkout(member, "annual", 0, "bitcoin")
    assert refusal.value.field == "provider"


def test_create_checkout_rejects_a_negative_contribution(
    member: User, annual_plan: MembershipPlan
) -> None:
    """A negative contribution is refused rather than subtracted from the total."""
    with pytest.raises(DomainValidationError, match=re.escape("Contribution cannot be negative.")):
        create_checkout(member, "annual", -100, PaymentProvider.MOCK)


def test_the_negative_contribution_refusal_names_the_contribution_field(
    member: User, annual_plan: MembershipPlan
) -> None:
    """The refusal names ``contribution_cents`` as the offending field."""
    with pytest.raises(DomainValidationError) as refusal:
        create_checkout(member, "annual", -100, PaymentProvider.MOCK)
    assert refusal.value.field == "contribution_cents"


def test_create_checkout_rejects_a_zero_total(member: User) -> None:
    """No plan and no contribution leaves nothing to charge, so it is refused."""
    with pytest.raises(DomainValidationError, match=re.escape("Nothing to charge.")):
        create_checkout(member, None, 0, PaymentProvider.MOCK)


def test_the_zero_total_refusal_names_the_amount_field(member: User) -> None:
    """The refusal names ``amount_cents`` as the offending field."""
    with pytest.raises(DomainValidationError) as refusal:
        create_checkout(member, None, 0, PaymentProvider.MOCK)
    assert refusal.value.field == "amount_cents"


def test_donation_only_checkout_has_no_plan(member: User) -> None:
    """A checkout with a contribution and no plan records no plan and the full amount."""
    payment = create_checkout(member, None, 5_000, PaymentProvider.MOCK)
    assert payment.plan is None
    assert payment.amount_cents == 5_000


def test_mock_provider_end_to_end(member: User, annual_plan: MembershipPlan) -> None:
    """Starting and confirming a checkout marks it succeeded and grants a membership."""
    payment = create_checkout(member, "annual", 2_000, PaymentProvider.MOCK)
    provider = get_provider("mock")
    assert provider.start(payment) == {}

    assert provider.confirm(payment, outcome="succeed") is True

    payment.refresh_from_db()
    assert payment.status == PaymentStatus.SUCCEEDED
    assert payment.wallet == PaymentWallet.MOCK
    assert payment.completed_at is not None
    assert payment.provider_ref == f"mock_{payment.pk}"

    status = membership_status(member)
    assert status["status"] == "current"
    assert status["plan"] == "Annual"

    term = Membership.objects.get(payment=payment)
    assert term.source == MembershipSource.PAYMENT


def test_mock_provider_failure_leaves_no_membership(
    member: User, annual_plan: MembershipPlan
) -> None:
    """Confirming a checkout as failed marks it failed and grants no membership."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.MOCK)
    assert get_provider("mock").confirm(payment, outcome="fail") is False
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.FAILED
    assert membership_status(member)["status"] == "friend"


def test_mark_succeeded_is_idempotent(member: User, annual_plan: MembershipPlan) -> None:
    """Keeps the first completion time, wallet, and payload on a second call."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.MOCK)
    mark_succeeded(payment, wallet=PaymentWallet.MOCK, raw={"n": 1})
    first_completed = Payment.objects.get(pk=payment.pk).completed_at
    mark_succeeded(payment, wallet=PaymentWallet.CARD, raw={"n": 2})

    payment.refresh_from_db()
    assert payment.completed_at == first_completed
    assert payment.wallet == PaymentWallet.MOCK
    assert payment.raw == {"n": 1}
    assert Membership.objects.filter(user=member).count() == 1


def test_mark_failed_never_downgrades_a_success(member: User, annual_plan: MembershipPlan) -> None:
    """Marking an already-succeeded payment failed leaves its status succeeded."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.MOCK)
    mark_succeeded(payment)
    mark_failed(payment, {"why": "late webhook"})
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.SUCCEEDED


def test_donation_only_payment_creates_no_membership(member: User) -> None:
    """Succeeding a donation-only payment grants no membership."""
    payment = create_checkout(member, None, 3_000, PaymentProvider.MOCK)
    mark_succeeded(payment)
    assert Membership.objects.filter(user=member).count() == 0


def test_renewal_through_the_mock_provider_extends_the_term(
    member: User, annual_plan: MembershipPlan
) -> None:
    """A second annual payment extends the expiry by exactly one year."""
    first = create_checkout(member, "annual", 0, PaymentProvider.MOCK)
    mark_succeeded(first)
    first_expiry = membership_status(member)["expires_on"]

    second = create_checkout(member, "annual", 0, PaymentProvider.MOCK)
    mark_succeeded(second)

    new_expiry = membership_status(member)["expires_on"]
    assert first_expiry is not None
    assert new_expiry is not None
    assert (new_expiry - first_expiry).days == 365


def test_mock_provider_respects_the_kill_switch(
    member: User, annual_plan: MembershipPlan, settings: Settings
) -> None:
    """Confirming through the mock provider while it is disabled raises."""
    settings.PAYMENTS_MOCK_ENABLED = False
    payment = create_checkout(member, "annual", 0, PaymentProvider.MOCK)
    with pytest.raises(MockPaymentsDisabledError) as refusal:
        get_provider("mock").confirm(payment)
    assert str(refusal.value) == "The mock payment provider is disabled."


def test_available_providers_reflects_configuration(settings: Settings) -> None:
    """The available-providers list follows which providers have keys configured."""
    settings.STRIPE_SECRET_KEY = ""
    settings.STRIPE_PUBLISHABLE_KEY = ""
    settings.PAYPAL_CLIENT_ID = ""
    settings.PAYPAL_CLIENT_SECRET = ""
    settings.PAYMENTS_MOCK_ENABLED = True
    assert available_providers() == ["mock"]

    settings.STRIPE_SECRET_KEY = "sk_test"  # noqa: S105 - test fixture
    settings.STRIPE_PUBLISHABLE_KEY = "pk_test"
    assert available_providers() == ["stripe", "mock"]


def test_unknown_provider_slug() -> None:
    """Looking up a provider slug that does not exist raises ``ValueError``."""
    with pytest.raises(ValueError, match="Unknown payment provider"):
        get_provider("not-a-provider")


#: What each real provider says when the keys it needs are missing.
NOT_CONFIGURED_MESSAGES = {
    "stripe": "Stripe is not configured (STRIPE_SECRET_KEY is empty).",
    "paypal": ("PayPal is not configured (PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET are empty)."),
}


@pytest.mark.parametrize("slug", ["stripe", "paypal"])
def test_real_providers_refuse_to_start_without_keys(
    slug: str, member: User, annual_plan: MembershipPlan, settings: Settings
) -> None:
    """Missing keys are a configuration error naming the settings, not a 500."""
    settings.STRIPE_SECRET_KEY = ""
    settings.PAYPAL_CLIENT_ID = ""
    settings.PAYPAL_CLIENT_SECRET = ""

    payment = create_checkout(member, "annual", 0, PaymentProvider.MOCK)
    provider = get_provider(slug)
    assert provider.slug == slug
    with pytest.raises(ProviderNotConfiguredError) as refusal:
        provider.start(payment)
    assert str(refusal.value) == NOT_CONFIGURED_MESSAGES[slug]
