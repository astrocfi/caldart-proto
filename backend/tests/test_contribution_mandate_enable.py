"""Turning a life member's automatic contribution on from the Payments screen.

A contribution-only authority names no plan, so confirming the saved method has no
plan slug to record.  The audit record renders that absence rather than refusing it,
which is what lets a life member turn their automatic contribution on at all, and
the record's own ``plan`` field is checked here for both kinds of authority.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from pytest_django.fixtures import Settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.members.models import MembershipPlan, MembershipStatusChoices
from apps.payments.models import MandateStatus, RenewalMandate
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

SETUP = "/api/v1/me/renewal/setup"
CONFIRM = "/api/v1/me/renewal/confirm"

#: What the authority these tests set up charges each year, in cents.
CONTRIBUTION_CENTS = 2_000


@pytest.fixture(autouse=True)
def _mock_only(settings: Settings) -> None:
    """Only the mock provider is configured, so no browser SDK is needed."""
    settings.PAYMENTS_MOCK_ENABLED = True
    settings.STRIPE_SECRET_KEY = ""
    settings.STRIPE_PUBLISHABLE_KEY = ""
    settings.PAYPAL_CLIENT_ID = ""
    settings.PAYPAL_CLIENT_SECRET = ""


@pytest.fixture
def life_member(member: User, life_plan: MembershipPlan, today: date) -> User:
    """The ``member`` fixture's user, holding a lifetime term that never ends."""
    MembershipFactory(
        user=member,
        plan=life_plan,
        starts_on=today - timedelta(days=400),
        ends_on=None,
        status=MembershipStatusChoices.ACTIVE,
    )
    return member


@pytest.fixture
def dated_member(member: User, annual_plan: MembershipPlan, today: date) -> User:
    """The ``member`` fixture's user, holding an annual term that has a year to run."""
    MembershipFactory(
        user=member,
        plan=annual_plan,
        starts_on=today - timedelta(days=30),
        ends_on=today + timedelta(days=335),
        status=MembershipStatusChoices.ACTIVE,
    )
    return member


def enable_contribution(api_client: APIClient, user: User) -> dict[str, object]:
    """Run setup and confirm for ``user`` on the mock provider, and answer the body.

    The answer is the confirm call's own body: the ``{"mandate": ...}`` envelope the
    portal redraws its card from.
    """
    api_client.force_authenticate(user)
    started = api_client.post(
        SETUP, {"contribution_cents": CONTRIBUTION_CENTS, "provider": "mock"}, format="json"
    )
    assert started.status_code == 200, started.json()
    confirmed = api_client.post(CONFIRM, {"setup_intent_id": "", "setup_token": ""}, format="json")
    assert confirmed.status_code == 200, confirmed.json()
    body: dict[str, object] = confirmed.json()
    return body


def test_a_life_member_turns_their_automatic_contribution_on(
    api_client: APIClient, life_member: User
) -> None:
    """The confirmed authority comes back as a contribution, charging no plan."""
    mandate = enable_contribution(api_client, life_member)["mandate"]

    assert isinstance(mandate, dict)
    assert mandate["kind"] == "contribution"


def test_an_enabled_contribution_only_authority_names_no_plan(
    api_client: APIClient, life_member: User
) -> None:
    """The saved method leaves the authority active with no plan to renew."""
    enable_contribution(api_client, life_member)

    stored = RenewalMandate.objects.get(user=life_member)
    assert stored.status == MandateStatus.ACTIVE
    assert stored.plan is None


def test_an_enabled_contribution_only_authority_has_a_next_charge_date(
    api_client: APIClient, life_member: User
) -> None:
    """The card always has a date to show for an active authority."""
    mandate = enable_contribution(api_client, life_member)["mandate"]

    assert isinstance(mandate, dict)
    assert mandate["next_charge_on"] is not None


def test_the_audit_record_of_a_contribution_only_authority_names_no_plan(
    api_client: APIClient, life_member: User, caplog: pytest.LogCaptureFixture
) -> None:
    """``renewal.enable`` carries an empty plan, which the record renders as ``-``."""
    with caplog.at_level("INFO", logger="caldart.audit"):
        enable_contribution(api_client, life_member)

    assert "action=renewal.enable" in caplog.text
    assert "plan=-" in caplog.text


def test_the_audit_record_of_a_renewing_authority_names_its_plan(
    api_client: APIClient, dated_member: User, caplog: pytest.LogCaptureFixture
) -> None:
    """A member with a term to renew has the plan slug in the record."""
    api_client.force_authenticate(dated_member)
    with caplog.at_level("INFO", logger="caldart.audit"):
        started = api_client.post(
            SETUP,
            {"plan": "annual", "contribution_cents": CONTRIBUTION_CENTS, "provider": "mock"},
            format="json",
        )
        assert started.status_code == 200, started.json()
        confirmed = api_client.post(
            CONFIRM, {"setup_intent_id": "", "setup_token": ""}, format="json"
        )
        assert confirmed.status_code == 200, confirmed.json()

    assert "plan=annual" in caplog.text
