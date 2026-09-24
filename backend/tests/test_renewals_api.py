"""The automatic-renewal endpoints: the member's own mandate and the finance screens.

Every test runs against the mock provider, which saves a test card without
speaking to anybody, so the endpoints are exercised end to end without a
network call.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager as ContextManager
from datetime import date, timedelta

import pytest
from django.core.mail import EmailMessage
from django.utils import timezone
from pytest_django.fixtures import Settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import ACCOUNT_ADMIN, SYSTEM_ADMIN, TREASURER
from apps.members.models import MembershipPlan, MembershipStatusChoices
from apps.payments.models import (
    MandateProvider,
    MandateStatus,
    Payment,
    RenewalAttempt,
    RenewalMandate,
    RenewalOutcome,
)
from apps.payments.providers.mock import MOCK_CARD_LABEL
from apps.payments.renewals import CHARGE_LEAD_DAYS
from tests.conftest import role_matrix
from tests.factories import MembershipFactory, RenewalAttemptFactory, RenewalMandateFactory

pytestmark = pytest.mark.django_db

#: The type of pytest-django's ``django_capture_on_commit_callbacks`` fixture:
#: a context manager that runs the callbacks a transaction queued for commit.
type CaptureOnCommit = Callable[..., ContextManager[list[Callable[[], None]]]]

ME = "/api/v1/me/renewal"
SETUP = "/api/v1/me/renewal/setup"
CONFIRM = "/api/v1/me/renewal/confirm"
ADMIN = "/api/v1/admin/renewals"
ATTEMPTS = "/api/v1/admin/renewals/attempts"
CHECKOUT = "/api/v1/payments/checkout"
MOCK_COMPLETE = "/api/v1/payments/mock/complete"
RUN = "/api/v1/system/renewals/run"


@pytest.fixture(autouse=True)
def mock_enabled(settings: Settings) -> None:
    """Turn the mock payment provider on for every test in this module."""
    settings.PAYMENTS_MOCK_ENABLED = True


@pytest.fixture
def member_client(api_client: APIClient, member: User) -> APIClient:
    """A DRF client signed in as an ordinary member."""
    api_client.force_login(member)
    return api_client


def setup_body(plan: str = "annual", contribution_cents: int = 0) -> dict[str, object]:
    """A well-formed ``POST /me/renewal/setup`` body for the mock provider."""
    return {
        "plan": plan,
        "contribution_cents": contribution_cents,
        "provider": MandateProvider.MOCK,
    }


def turn_on(client: APIClient, **overrides: object) -> None:
    """Turn automatic renewal on through the two-step setup flow."""
    client.post(SETUP, setup_body(**overrides))  # type: ignore[arg-type]
    client.post(CONFIRM, {})


# --------------------------------------------------------------------------
# GET /me/renewal
# --------------------------------------------------------------------------
def test_a_member_with_no_mandate_reads_null(member_client: APIClient) -> None:
    """A member who has never turned renewal on is answered ``null``, not a 404."""
    response = member_client.get(ME)
    assert response.json()["mandate"] is None


def test_an_anonymous_caller_cannot_read_a_mandate(api_client: APIClient) -> None:
    """The renewal endpoints are a member's own, so anonymous is 401."""
    assert api_client.get(ME).status_code == 401


def test_a_member_reads_their_own_mandate(
    member_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The saved method is shown by the label, never by the provider's reference."""
    RenewalMandateFactory(user=member, plan=annual_plan)
    body = member_client.get(ME).json()["mandate"]
    assert body["method_label"] == "Test card ending 4242, expires 12/2030"


def test_the_mandate_reports_what_the_next_charge_comes_to(
    member_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The amount is the plan's price plus the contribution, in cents."""
    RenewalMandateFactory(user=member, plan=annual_plan, contribution_cents=2_500)
    body = member_client.get(ME).json()["mandate"]
    assert body["amount_cents"] == annual_plan.price_cents + 2_500


def test_a_member_never_reads_another_members_mandate(
    member_client: APIClient, annual_plan: MembershipPlan, user_admin: User
) -> None:
    """The endpoint is keyed on the caller, so somebody else's mandate is invisible."""
    RenewalMandateFactory(user=user_admin, plan=annual_plan)
    assert member_client.get(ME).json()["mandate"] is None


# --------------------------------------------------------------------------
# Turning it on
# --------------------------------------------------------------------------
def test_setup_creates_a_pending_mandate(
    member_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """Nothing is active until the method is confirmed."""
    member_client.post(SETUP, setup_body())
    assert RenewalMandate.objects.get(user=member).status == MandateStatus.PENDING


def test_setup_answers_with_the_provider_it_was_asked_for(
    member_client: APIClient, annual_plan: MembershipPlan
) -> None:
    """The browser is told which provider's flow to render."""
    body = member_client.post(SETUP, setup_body()).json()
    assert body["provider"] == MandateProvider.MOCK


def test_setup_refuses_a_lifetime_plan(member_client: APIClient, life_plan: MembershipPlan) -> None:
    """A membership that never expires cannot renew itself."""
    response = member_client.post(SETUP, setup_body(plan="life"))
    assert response.json()["auto_renew"] == [
        "A lifetime membership never expires, so it cannot renew itself."
    ]


def test_setup_refuses_a_lifetime_plan_with_a_400(
    member_client: APIClient, life_plan: MembershipPlan
) -> None:
    """The refusal is a 400, keyed by the field the member set."""
    assert member_client.post(SETUP, setup_body(plan="life")).status_code == 400


def test_setup_refuses_a_plan_that_is_not_on_offer(
    member_client: APIClient, annual_plan: MembershipPlan
) -> None:
    """A slug no active plan carries is refused, naming ``plan``."""
    response = member_client.post(SETUP, setup_body(plan="platinum"))
    assert response.json()["plan"] == "Unknown membership plan 'platinum'."


def test_setup_refuses_a_provider_that_cannot_charge_again(
    member_client: APIClient, annual_plan: MembershipPlan
) -> None:
    """A payment recorded by hand cannot be taken a second time without the member."""
    response = member_client.post(
        SETUP, {"plan": "annual", "contribution_cents": 0, "provider": "manual"}
    )
    assert response.status_code == 400


def test_confirming_a_setup_makes_the_mandate_active(
    member_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The method the browser saved is what turns the authority on."""
    turn_on(member_client)
    assert RenewalMandate.objects.get(user=member).status == MandateStatus.ACTIVE


def test_confirming_a_setup_stores_the_saved_method(
    member_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The mandate carries the label the member will recognize."""
    turn_on(member_client)
    assert RenewalMandate.objects.get(user=member).method_label == MOCK_CARD_LABEL


def test_turning_renewal_on_emails_the_member(
    member_client: APIClient,
    annual_plan: MembershipPlan,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: CaptureOnCommit,
) -> None:
    """A standing authority is never created silently."""
    with django_capture_on_commit_callbacks(execute=True):
        turn_on(member_client)
    assert str(mailoutbox[-1].subject) == "CalDART: automatic renewal is on"


def test_confirming_without_a_setup_is_a_404(
    member_client: APIClient, annual_plan: MembershipPlan
) -> None:
    """There is nothing to confirm before a setup has been started."""
    assert member_client.post(CONFIRM, {}).status_code == 404


# --------------------------------------------------------------------------
# Changing and turning it off
# --------------------------------------------------------------------------
def test_a_member_changes_the_contribution_renewed_with_the_dues(
    member_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The contribution is the member's to change; the dues are the plan's price."""
    RenewalMandateFactory(user=member, plan=annual_plan)
    member_client.patch(ME, {"contribution_cents": 5_000}, format="json")
    assert RenewalMandate.objects.get(user=member).contribution_cents == 5_000


def test_a_member_changes_the_plan_that_renews(
    member_client: APIClient, member: User, annual_plan: MembershipPlan, life_plan: MembershipPlan
) -> None:
    """``plan`` on the patch replaces the plan the mandate renews from now on."""
    RenewalMandateFactory(user=member, plan=life_plan)

    member_client.patch(ME, {"plan": annual_plan.slug, "contribution_cents": 0}, format="json")

    assert RenewalMandate.objects.get(user=member).plan_id == annual_plan.pk


def test_a_patch_without_a_plan_leaves_the_plan_alone(
    member_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """Changing only the contribution does not disturb what renews."""
    RenewalMandateFactory(user=member, plan=annual_plan)

    member_client.patch(ME, {"contribution_cents": 5_000}, format="json")

    assert RenewalMandate.objects.get(user=member).plan_id == annual_plan.pk


def test_a_plan_nobody_offers_is_refused(
    member_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A slug outside the catalog is a 400 keyed by ``plan``."""
    RenewalMandateFactory(user=member, plan=annual_plan)

    response = member_client.patch(ME, {"plan": "nonesuch", "contribution_cents": 0}, format="json")

    assert response.json()["plan"] == "Unknown membership plan 'nonesuch'."


def test_a_life_member_may_not_patch_a_plan_in(
    member_client: APIClient, member: User, life_plan: MembershipPlan, annual_plan: MembershipPlan
) -> None:
    """A life member's authority stays over the contribution alone."""
    MembershipFactory(
        user=member,
        plan=life_plan,
        starts_on=timezone.localdate() - timedelta(days=400),
        ends_on=None,
    )
    RenewalMandateFactory(user=member, plan=None, contribution_cents=5_000)

    response = member_client.patch(
        ME, {"plan": annual_plan.slug, "contribution_cents": 5_000}, format="json"
    )

    assert response.json()["auto_renew"] == [
        "A life member's membership does not renew; choose a contribution instead."
    ]


def test_a_plan_that_never_expires_may_not_be_patched_in(
    member_client: APIClient, member: User, annual_plan: MembershipPlan, life_plan: MembershipPlan
) -> None:
    """A lifetime plan cannot renew itself, so the patch is a 400 keyed ``auto_renew``."""
    RenewalMandateFactory(user=member, plan=annual_plan)

    response = member_client.patch(
        ME, {"plan": life_plan.slug, "contribution_cents": 0}, format="json"
    )

    assert response.json()["auto_renew"] == [
        "A lifetime membership never expires, so it cannot renew itself."
    ]


def test_a_life_member_may_not_patch_their_contribution_away(
    member_client: APIClient, member: User, life_plan: MembershipPlan
) -> None:
    """An authority over nothing at all is refused on the patch as it is at setup."""
    MembershipFactory(
        user=member,
        plan=life_plan,
        starts_on=timezone.localdate() - timedelta(days=400),
        ends_on=None,
    )
    RenewalMandateFactory(user=member, plan=None, contribution_cents=5_000)

    response = member_client.patch(ME, {"contribution_cents": 0}, format="json")

    assert response.json()["auto_renew"] == ["A contribution to charge each year is needed."]


def test_a_negative_contribution_is_refused(
    member_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A contribution outside what a checkout accepts is a 400."""
    RenewalMandateFactory(user=member, plan=annual_plan)
    response = member_client.patch(ME, {"contribution_cents": -1}, format="json")
    assert response.status_code == 400


def test_changing_a_mandate_that_does_not_exist_is_a_404(member_client: APIClient) -> None:
    """There is nothing to change before renewal has been turned on."""
    response = member_client.patch(ME, {"contribution_cents": 100}, format="json")
    assert response.status_code == 404


def test_a_member_turns_renewal_off(
    member_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """Deleting the mandate cancels it rather than erasing the record."""
    RenewalMandateFactory(user=member, plan=annual_plan)
    member_client.delete(ME)
    assert RenewalMandate.objects.get(user=member).status == MandateStatus.CANCELED


def test_turning_renewal_off_answers_204(
    member_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The member is told it worked, with no body to read."""
    RenewalMandateFactory(user=member, plan=annual_plan)
    assert member_client.delete(ME).status_code == 204


def test_turning_renewal_off_drops_every_scheduled_charge(
    member_client: APIClient, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """A charge already scheduled must not go through after the member says stop."""
    mandate = RenewalMandateFactory(user=member, plan=annual_plan)
    membership = MembershipFactory(user=member, plan=annual_plan)
    RenewalAttemptFactory(mandate=mandate, membership=membership, scheduled_on=today)

    member_client.delete(ME)

    assert RenewalAttempt.objects.get().outcome == RenewalOutcome.SKIPPED


def test_turning_renewal_off_emails_the_member(
    member_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: CaptureOnCommit,
) -> None:
    """The member gets written confirmation that nothing further will be charged."""
    RenewalMandateFactory(user=member, plan=annual_plan)
    with django_capture_on_commit_callbacks(execute=True):
        member_client.delete(ME)
    assert str(mailoutbox[-1].subject) == "CalDART: automatic renewal is off"


# --------------------------------------------------------------------------
# Checkout
# --------------------------------------------------------------------------
def checkout(client: APIClient, **overrides: object) -> dict[str, object]:
    """Start a mock checkout, asking for automatic renewal unless told otherwise."""
    body: dict[str, object] = {
        "plan": "annual",
        "contribution_cents": 0,
        "provider": "mock",
        "auto_renew": True,
    }
    body.update(overrides)
    response = client.post(CHECKOUT, body, format="json")
    return dict(response.json())


def test_a_checkout_asking_for_renewal_leaves_a_pending_mandate(
    member_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The mandate exists before the provider is started, so the method is saved."""
    checkout(member_client)
    assert RenewalMandate.objects.get(user=member).status == MandateStatus.PENDING


def test_a_paid_checkout_activates_the_mandate(
    member_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The card the member paid with becomes the one the renewal charges."""
    started = checkout(member_client)
    member_client.post(MOCK_COMPLETE, {"payment_id": started["payment_id"]}, format="json")
    assert RenewalMandate.objects.get(user=member).status == MandateStatus.ACTIVE


def test_a_checkout_that_did_not_ask_for_renewal_creates_no_mandate(
    member_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """An ordinary payment leaves no standing authority behind it."""
    started = checkout(member_client, auto_renew=False)
    member_client.post(MOCK_COMPLETE, {"payment_id": started["payment_id"]}, format="json")
    assert RenewalMandate.objects.filter(user=member).count() == 0


def test_a_checkout_that_declines_renewal_throws_away_an_abandoned_mandate(
    member_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A member who says no is not renewed from a mandate they walked away from."""
    RenewalMandateFactory(
        user=member,
        plan=annual_plan,
        status=MandateStatus.PENDING,
        provider=MandateProvider.MOCK,
        method_ref="",
    )

    checkout(member_client, auto_renew=False)

    assert RenewalMandate.objects.filter(user=member).count() == 0


def test_a_payment_that_declined_renewal_activates_no_abandoned_mandate(
    member_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """Paying without asking to renew never turns a stale mandate on."""
    started = checkout(member_client, auto_renew=False)

    member_client.post(MOCK_COMPLETE, {"payment_id": started["payment_id"]}, format="json")

    assert RenewalMandate.objects.filter(status=MandateStatus.ACTIVE).count() == 0


def test_a_checkout_cannot_ask_to_renew_a_lifetime_plan(
    member_client: APIClient, life_plan: MembershipPlan
) -> None:
    """A membership that never expires is refused, naming ``auto_renew``."""
    body = checkout(member_client, plan="life")
    assert body["auto_renew"] == ["A lifetime membership never expires, so it cannot renew itself."]


def test_a_checkout_refused_for_renewal_leaves_no_pending_payment(
    member_client: APIClient, member: User, life_plan: MembershipPlan
) -> None:
    """The payment started for a refused checkout is deleted again, as for any refusal."""
    checkout(member_client, plan="life")

    assert Payment.objects.filter(user=member).count() == 0


def test_a_checkout_cannot_ask_to_renew_a_pure_contribution(
    member_client: APIClient, annual_plan: MembershipPlan
) -> None:
    """There is no membership to renew when the payment buys no plan."""
    body = checkout(member_client, plan="", contribution_cents=1_000)
    assert body["auto_renew"] == ["Automatic renewal needs a membership plan to renew."]


# --------------------------------------------------------------------------
# The finance screens
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("role", "allowed"), role_matrix(TREASURER, ACCOUNT_ADMIN, SYSTEM_ADMIN))
def test_only_the_finance_roles_list_the_mandates(
    api_client: APIClient, all_role_users: dict[str, User], role: str, allowed: bool
) -> None:
    """The mandates name who pays what, so only the finance roles read them."""
    api_client.force_login(all_role_users[role])
    expected = 200 if allowed else 403
    assert api_client.get(ADMIN).status_code == expected


def test_the_finance_list_narrows_to_one_status(
    treasurer_client: APIClient, annual_plan: MembershipPlan, user_admin: User, member: User
) -> None:
    """``?status=paused`` is how a treasurer finds the renewals that stopped."""
    RenewalMandateFactory(user=member, plan=annual_plan, status=MandateStatus.ACTIVE)
    RenewalMandateFactory(user=user_admin, plan=annual_plan, status=MandateStatus.PAUSED)

    body = treasurer_client.get(ADMIN, {"status": "paused"}).json()

    assert body["count"] == 1


def test_an_unknown_status_filter_is_refused(treasurer_client: APIClient) -> None:
    """A status outside the mandate states is a 400 naming the parameter."""
    response = treasurer_client.get(ADMIN, {"status": "lapsed"})
    assert response.json()["status"] == ["Unknown status 'lapsed'."]


def test_a_treasurer_reads_why_a_mandate_stopped(
    treasurer_client: APIClient, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The reason the last charge was refused is on the mandate, for the support call."""
    mandate = RenewalMandateFactory(user=member, plan=annual_plan, status=MandateStatus.PAUSED)
    membership = MembershipFactory(user=member, plan=annual_plan)
    RenewalAttemptFactory(
        mandate=mandate,
        membership=membership,
        scheduled_on=today,
        outcome=RenewalOutcome.FAILED,
        error="Your card was declined",
    )

    body = treasurer_client.get(f"{ADMIN}/{mandate.pk}").json()

    assert body["last_error"] == "Your card was declined"


def test_a_treasurer_turns_a_members_renewal_off(
    treasurer_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """An administrator can stop a renewal on the member's behalf."""
    mandate = RenewalMandateFactory(user=member, plan=annual_plan)
    treasurer_client.delete(f"{ADMIN}/{mandate.pk}")
    mandate.refresh_from_db()
    assert mandate.status == MandateStatus.CANCELED


def test_an_administrator_cancellation_records_who_did_it(
    treasurer_client: APIClient, member: User, annual_plan: MembershipPlan, treasurer: User
) -> None:
    """The record must not read as though the member turned it off themselves."""
    mandate = RenewalMandateFactory(user=member, plan=annual_plan)
    treasurer_client.delete(f"{ADMIN}/{mandate.pk}")
    mandate.refresh_from_db()
    assert mandate.canceled_by_id == treasurer.pk


def test_an_unknown_mandate_is_a_404(treasurer_client: APIClient) -> None:
    """A renewal that does not exist is a 404, not an empty success."""
    assert treasurer_client.delete(f"{ADMIN}/99999").status_code == 404


def test_the_attempts_list_carries_the_member_behind_each_charge(
    treasurer_client: APIClient, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """A treasurer reading the attempts needs the name, not just the mandate id."""
    mandate = RenewalMandateFactory(user=member, plan=annual_plan)
    membership = MembershipFactory(user=member, plan=annual_plan)
    RenewalAttemptFactory(mandate=mandate, membership=membership, scheduled_on=today)

    body = treasurer_client.get(ATTEMPTS).json()

    assert body["results"][0]["user_name"] == member.display_name


def test_the_attempts_list_narrows_to_one_outcome(
    treasurer_client: APIClient, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """``?outcome=failed`` is how a treasurer finds the charges that were refused."""
    mandate = RenewalMandateFactory(user=member, plan=annual_plan)
    membership = MembershipFactory(user=member, plan=annual_plan)
    RenewalAttemptFactory(mandate=mandate, membership=membership, scheduled_on=today)
    RenewalAttemptFactory(
        mandate=mandate,
        membership=membership,
        scheduled_on=today - timedelta(days=CHARGE_LEAD_DAYS),
        outcome=RenewalOutcome.FAILED,
    )

    body = treasurer_client.get(ATTEMPTS, {"outcome": "failed"}).json()

    assert body["count"] == 1


def test_an_unknown_attempt_outcome_is_refused(treasurer_client: APIClient) -> None:
    """An outcome outside the attempt states is a 400 naming the parameter."""
    response = treasurer_client.get(ATTEMPTS, {"outcome": "bounced"})
    assert response.json()["outcome"] == "Unknown outcome 'bounced'."


# --------------------------------------------------------------------------
# Running the scan by hand
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("role", "allowed"), role_matrix(SYSTEM_ADMIN))
def test_only_a_system_administrator_runs_the_scan(
    api_client: APIClient, all_role_users: dict[str, User], role: str, allowed: bool
) -> None:
    """Charging every due renewal on demand is a system administrator's button."""
    api_client.force_login(all_role_users[role])
    expected = 200 if allowed else 403
    assert api_client.post(RUN, {"dry_run": True}, format="json").status_code == expected


def test_the_run_endpoint_reports_what_it_would_charge(
    api_client: APIClient,
    system_admin: User,
    member: User,
    annual_plan: MembershipPlan,
    today: date,
) -> None:
    """A dry run tells the operator the counts without taking any money."""
    MembershipFactory(
        user=member,
        plan=annual_plan,
        starts_on=today - timedelta(days=364),
        ends_on=today + timedelta(days=CHARGE_LEAD_DAYS),
        status=MembershipStatusChoices.ACTIVE,
    )
    RenewalMandateFactory(user=member, plan=annual_plan)
    api_client.force_login(system_admin)

    body = api_client.post(RUN, {"dry_run": True}, format="json").json()

    assert body["noticed"] == 1


def test_a_dry_run_through_the_endpoint_charges_nobody(
    api_client: APIClient,
    system_admin: User,
    member: User,
    annual_plan: MembershipPlan,
    today: date,
) -> None:
    """A rehearsal writes nothing, so no attempt is left behind."""
    MembershipFactory(
        user=member,
        plan=annual_plan,
        starts_on=today - timedelta(days=364),
        ends_on=today + timedelta(days=CHARGE_LEAD_DAYS),
        status=MembershipStatusChoices.ACTIVE,
    )
    RenewalMandateFactory(user=member, plan=annual_plan)
    api_client.force_login(system_admin)

    api_client.post(RUN, {"dry_run": True}, format="json")

    assert RenewalAttempt.objects.count() == 0
