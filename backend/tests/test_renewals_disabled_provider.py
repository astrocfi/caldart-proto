"""The renewal scan against mandates whose provider is switched off.

A server seeded before ``seed_demo`` learned to leave the mock provider's mandates
out, or one whose ``PAYMENTS_MOCK_ENABLED_IN_PRODUCTION`` was turned on and then off
again, still holds mandates on the mock provider's test card.  The scan puts their
charges off, as it does when a provider cannot be reached, rather than failing.
"""

from __future__ import annotations

from datetime import date, timedelta
from io import StringIO

import pytest
from django.core.mail import EmailMessage
from django.core.management import call_command

from apps.accounts.models import User
from apps.members.models import MembershipPlan, MembershipStatusChoices
from apps.payments.models import (
    MandateCadence,
    Payment,
    RenewalAttempt,
    RenewalMandate,
    RenewalOutcome,
)
from apps.payments.renewals.scan import run_auto_renewals
from caldart import audit
from tests.conftest import audit_messages
from tests.factories import MembershipFactory, RenewalMandateFactory

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("mock_payments_off")]

#: What the recurring donation in these tests gives each time.
GIFT_CENTS = 2_500


def _renewal_due(user: User, plan: MembershipPlan, today: date) -> RenewalMandate:
    """A mock-provider renewal whose charge is due ``today``, already noticed.

    The term ends ``today`` and the scan has run the day before, so the scheduled
    attempt is waiting and its notice has gone out; the notice touches no provider.
    """
    MembershipFactory(
        user=user,
        plan=plan,
        starts_on=today - timedelta(days=364),
        ends_on=today,
        status=MembershipStatusChoices.ACTIVE,
    )
    mandate: RenewalMandate = RenewalMandateFactory(user=user, plan=plan, next_charge_on=today)
    run_auto_renewals(today=today - timedelta(days=1))
    return mandate


def _run_fields(caplog: pytest.LogCaptureFixture) -> dict[str, str]:
    """The ``key=value`` pairs of the one ``renewals.run`` audit line captured."""
    (line,) = [
        message
        for message in audit_messages(caplog)
        if message.startswith(f"action={audit.RENEWALS_RUN} ")
    ]
    return dict(pair.split("=", 1) for pair in line.split())


def test_the_renewals_job_records_no_failure_for_a_disabled_provider(
    member: User,
    annual_plan: MembershipPlan,
    today: date,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """The command runs to its audit record, which counts no refused charge."""
    _renewal_due(member, annual_plan, today)
    audit_log.clear()

    call_command("run_auto_renewals", today=today.isoformat(), stdout=StringIO())

    assert _run_fields(audit_log)["failed"] == "0"


def test_a_charge_a_disabled_provider_stopped_is_put_off(
    member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The scan reports the charge as put off, the way a provider outage is."""
    _renewal_due(member, annual_plan, today)

    run = run_auto_renewals(today=today)

    assert run.skipped_by_reason == {"provider_down": 1}


def test_a_charge_a_disabled_provider_stopped_is_not_left_in_flight(
    member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The attempt is released unclaimed, so a later scan can take it up."""
    _renewal_due(member, annual_plan, today)

    run_auto_renewals(today=today)

    attempt = RenewalAttempt.objects.get()
    assert (attempt.outcome, attempt.attempted_at) == (RenewalOutcome.SCHEDULED, None)


def test_a_disabled_provider_costs_the_member_no_rung_of_the_retry_ladder(
    member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """Nothing was learned about the card, so nothing is held against it."""
    mandate = _renewal_due(member, annual_plan, today)

    run_auto_renewals(today=today)

    mandate.refresh_from_db()
    assert mandate.failure_count == 0


def test_a_disabled_provider_tells_the_member_nothing(
    member: User,
    annual_plan: MembershipPlan,
    today: date,
    mailoutbox: list[EmailMessage],
) -> None:
    """No decline notice goes out for a charge the provider was never asked to take."""
    _renewal_due(member, annual_plan, today)
    mailoutbox.clear()

    run_auto_renewals(today=today)

    assert mailoutbox == []


def test_a_charge_a_disabled_provider_stopped_leaves_no_pending_payment(
    member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The payment row started for the charge is thrown away again."""
    _renewal_due(member, annual_plan, today)

    run_auto_renewals(today=today)

    assert Payment.objects.count() == 0


def test_a_donation_a_disabled_provider_stopped_is_put_off(friend: User, today: date) -> None:
    """A recurring donation due today is put off too, its attempt left scheduled."""
    RenewalMandateFactory(
        user=friend,
        plan=None,
        cadence=MandateCadence.MONTHLY,
        contribution_cents=GIFT_CENTS,
        next_charge_on=today,
    )

    run = run_auto_renewals(today=today)

    assert run.skipped_by_reason == {"provider_down": 1}
