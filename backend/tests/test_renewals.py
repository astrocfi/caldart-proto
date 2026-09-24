"""The automatic-renewal scanner: notices, charges, retries, and the pause.

The whole cycle is driven through ``run_auto_renewals`` against the mock
provider, whose ``0002`` card declines every charge, so the failure ladder can
be walked without a real provider.
"""

from __future__ import annotations

import smtplib
from datetime import date, timedelta

import pytest
from django.core.mail import EmailMessage
from django.utils import timezone

from apps.accounts.models import User
from apps.members.models import Membership, MembershipPlan, MembershipStatusChoices
from apps.payments import renewals
from apps.payments.models import (
    MandateStatus,
    Payment,
    PaymentStatus,
    RenewalAttempt,
    RenewalMandate,
    RenewalOutcome,
)
from apps.payments.providers.base import ProviderUnavailableError
from apps.payments.providers.mock import DECLINED_LAST4, MockProvider, mock_method
from apps.payments.renewals import (
    CHARGE_LEAD_DAYS,
    NOTICE_DAYS,
    RETRY_OFFSETS,
    card_expires_on,
    charge_date_for,
    next_charge_on,
    run_auto_renewals,
    save_method,
    term_to_renew,
)
from tests.conftest import Golden
from tests.factories import MembershipFactory, RenewalAttemptFactory, RenewalMandateFactory

pytestmark = pytest.mark.django_db


def make_mandate(
    user: User,
    plan: MembershipPlan,
    *,
    ends_on: date,
    contribution_cents: int = 0,
    last4: str = "4242",
) -> RenewalMandate:
    """An active mandate for ``user`` over a term ending on ``ends_on``.

    The member's first name and the method label are pinned, so the emails the
    golden files compare do not move with whatever name the factory invented.
    """
    user.first_name = "Dana"
    user.save(update_fields=["first_name"])
    MembershipFactory(
        user=user,
        plan=plan,
        starts_on=ends_on - timedelta(days=364),
        ends_on=ends_on,
        status=MembershipStatusChoices.ACTIVE,
    )
    return RenewalMandateFactory(
        user=user,
        plan=plan,
        contribution_cents=contribution_cents,
        method_last4=last4,
        method_label=f"Test card ending {last4}, expires 12/2030",
    )


def subjects(mailbox: list[EmailMessage]) -> list[str]:
    """The subject line of every message sent so far."""
    return [str(message.subject) for message in mailbox]


def refusing_mailer(**kwargs: object) -> None:
    """Stand in for a mail server that will not take the message."""
    raise smtplib.SMTPException("The mail server refused the message.")


# --------------------------------------------------------------------------
# Dates
# --------------------------------------------------------------------------
def test_the_charge_falls_three_days_before_the_term_ends() -> None:
    """A term ending on the 20th is renewed on the 17th, so a decline has room."""
    assert charge_date_for(date(2026, 6, 20)) == date(2026, 6, 17)


def test_the_lead_is_three_days() -> None:
    """The charge lead is stated once, and it is three days."""
    assert CHARGE_LEAD_DAYS == 3


def test_a_card_expires_at_the_end_of_its_printed_month(
    member: User, annual_plan: MembershipPlan
) -> None:
    """An expiry of 02/2028 means the card works to 29 February 2028."""
    mandate = RenewalMandateFactory(
        user=member, plan=annual_plan, method_exp_month=2, method_exp_year=2028
    )
    assert card_expires_on(mandate) == date(2028, 2, 29)


def test_a_method_with_no_expiry_has_no_expiry_date(
    member: User, annual_plan: MembershipPlan
) -> None:
    """A PayPal vault entry carries no card month or year, so it never expires."""
    mandate = RenewalMandateFactory(
        user=member, plan=annual_plan, method_exp_month=None, method_exp_year=None
    )
    assert card_expires_on(mandate) is None


def test_a_lifetime_member_has_no_term_to_renew(
    member: User, life_plan: MembershipPlan, today: date
) -> None:
    """A term that never ends is never renewed, so the scanner finds nothing."""
    MembershipFactory(user=member, plan=life_plan, starts_on=today, ends_on=None)
    assert term_to_renew(member, today) is None


def test_the_term_to_renew_is_the_one_running_furthest_out(
    member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """An early renewal pushes the date the mandate works against further out."""
    MembershipFactory(
        user=member, plan=annual_plan, starts_on=today, ends_on=today + timedelta(days=30)
    )
    later = MembershipFactory(
        user=member,
        plan=annual_plan,
        starts_on=today + timedelta(days=31),
        ends_on=today + timedelta(days=395),
    )
    found = term_to_renew(member, today)
    assert found is not None
    assert found.pk == later.pk


# --------------------------------------------------------------------------
# The advance notice
# --------------------------------------------------------------------------
def test_a_term_running_out_earns_a_scheduled_attempt(
    member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The scan schedules the charge three days before the term's last day."""
    ends_on = today + timedelta(days=NOTICE_DAYS + CHARGE_LEAD_DAYS)
    make_mandate(member, annual_plan, ends_on=ends_on)

    run_auto_renewals(today=today)

    attempt = RenewalAttempt.objects.get()
    assert attempt.scheduled_on == ends_on - timedelta(days=CHARGE_LEAD_DAYS)


def test_the_notice_names_the_date_the_card_will_be_charged(
    member: User, annual_plan: MembershipPlan, today: date, mailoutbox: list[EmailMessage]
) -> None:
    """The advance warning's subject carries the charge date, not the expiry date."""
    ends_on = today + timedelta(days=NOTICE_DAYS + CHARGE_LEAD_DAYS)
    make_mandate(member, annual_plan, ends_on=ends_on)

    run_auto_renewals(today=today)

    charge_on = ends_on - timedelta(days=CHARGE_LEAD_DAYS)
    assert subjects(mailoutbox) == [f"CalDART: we will renew your membership on {charge_on}"]


def test_a_term_further_out_than_the_notice_window_is_left_alone(
    member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """A membership with months to run is not scheduled or emailed yet."""
    make_mandate(
        member, annual_plan, ends_on=today + timedelta(days=NOTICE_DAYS + CHARGE_LEAD_DAYS + 1)
    )

    run_auto_renewals(today=today)

    assert RenewalAttempt.objects.count() == 0


def test_a_second_scan_the_same_day_sends_no_second_notice(
    member: User, annual_plan: MembershipPlan, today: date, mailoutbox: list[EmailMessage]
) -> None:
    """The attempt already on file is what keeps a repeated scan quiet."""
    make_mandate(member, annual_plan, ends_on=today + timedelta(days=NOTICE_DAYS))

    run_auto_renewals(today=today)
    run_auto_renewals(today=today)

    assert len(mailoutbox) == 1


def test_a_paused_mandate_is_not_scanned_for_notices(
    member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """Only an active mandate schedules a charge; a paused one waits for the member."""
    mandate = make_mandate(member, annual_plan, ends_on=today + timedelta(days=NOTICE_DAYS))
    mandate.status = MandateStatus.PAUSED
    mandate.save(update_fields=["status"])

    run_auto_renewals(today=today)

    assert RenewalAttempt.objects.count() == 0


def test_a_dry_run_schedules_nothing_and_sends_nothing(
    member: User, annual_plan: MembershipPlan, today: date, mailoutbox: list[EmailMessage]
) -> None:
    """A rehearsal reports what it would do and writes not one row."""
    make_mandate(member, annual_plan, ends_on=today + timedelta(days=NOTICE_DAYS))

    run = run_auto_renewals(today=today, dry_run=True)

    assert run.noticed == 1
    assert RenewalAttempt.objects.count() == 0
    assert mailoutbox == []


# --------------------------------------------------------------------------
# The charge
# --------------------------------------------------------------------------
def test_a_due_attempt_is_charged_and_buys_the_next_term(
    member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The renewal's term starts the day after the one it renews ends."""
    ends_on = today + timedelta(days=CHARGE_LEAD_DAYS)
    make_mandate(member, annual_plan, ends_on=ends_on)

    run_auto_renewals(today=today)

    renewed = Membership.objects.filter(user=member).order_by("-ends_on").first()
    assert renewed is not None
    assert renewed.starts_on == ends_on + timedelta(days=1)


def test_the_renewal_charges_the_plan_price_plus_the_contribution(
    member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The amount is recomputed from the plan, never carried over from last year."""
    make_mandate(
        member,
        annual_plan,
        ends_on=today + timedelta(days=CHARGE_LEAD_DAYS),
        contribution_cents=2_500,
    )

    run_auto_renewals(today=today)

    payment = Payment.objects.get()
    assert payment.amount_cents == annual_plan.price_cents + 2_500


def test_a_succeeded_renewal_marks_its_attempt_succeeded(
    member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The attempt records the outcome, so the finance screens can read it back."""
    make_mandate(member, annual_plan, ends_on=today + timedelta(days=CHARGE_LEAD_DAYS))

    run_auto_renewals(today=today)

    assert RenewalAttempt.objects.get().outcome == RenewalOutcome.SUCCEEDED


def test_the_member_is_told_the_membership_was_renewed(
    member: User, annual_plan: MembershipPlan, today: date, mailoutbox: list[EmailMessage]
) -> None:
    """A successful charge sends the renewed email, not another notice."""
    make_mandate(member, annual_plan, ends_on=today + timedelta(days=CHARGE_LEAD_DAYS))

    run_auto_renewals(today=today)

    assert "CalDART: your membership has been renewed" in subjects(mailoutbox)


def test_a_scan_that_runs_twice_charges_once(
    member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The attempt leaves ``scheduled`` once it is charged, so it is not charged again."""
    make_mandate(member, annual_plan, ends_on=today + timedelta(days=CHARGE_LEAD_DAYS))

    run_auto_renewals(today=today)
    run_auto_renewals(today=today)

    assert Payment.objects.count() == 1


def test_a_term_renewed_by_hand_in_the_meantime_is_skipped(
    member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """A member who paid by hand is not charged again by the scanner."""
    ends_on = today + timedelta(days=CHARGE_LEAD_DAYS)
    make_mandate(member, annual_plan, ends_on=ends_on)
    run_auto_renewals(today=today - timedelta(days=1))
    MembershipFactory(
        user=member,
        plan=annual_plan,
        starts_on=ends_on + timedelta(days=1),
        ends_on=ends_on + timedelta(days=365),
    )

    run = run_auto_renewals(today=today)

    assert run.skipped_by_reason["already_renewed"] == 1


def test_a_skipped_attempt_takes_no_money(
    member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """Nothing is charged for a term somebody else already renewed."""
    ends_on = today + timedelta(days=CHARGE_LEAD_DAYS)
    make_mandate(member, annual_plan, ends_on=ends_on)
    run_auto_renewals(today=today - timedelta(days=1))
    MembershipFactory(
        user=member,
        plan=annual_plan,
        starts_on=ends_on + timedelta(days=1),
        ends_on=ends_on + timedelta(days=365),
    )

    run_auto_renewals(today=today)

    assert Payment.objects.count() == 0


# --------------------------------------------------------------------------
# Declines, retries, and the pause
# --------------------------------------------------------------------------
def test_a_declined_charge_records_the_providers_reason(
    member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The member is owed the reason, so the attempt keeps the provider's words."""
    make_mandate(
        member,
        annual_plan,
        ends_on=today + timedelta(days=CHARGE_LEAD_DAYS),
        last4=DECLINED_LAST4,
    )

    run_auto_renewals(today=today)

    failed = RenewalAttempt.objects.get(outcome=RenewalOutcome.FAILED)
    assert failed.error == "Your card was declined"


def test_a_declined_charge_leaves_its_payment_failed(
    member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """A refused renewal is a failed payment, never a pending one left hanging."""
    make_mandate(
        member,
        annual_plan,
        ends_on=today + timedelta(days=CHARGE_LEAD_DAYS),
        last4=DECLINED_LAST4,
    )

    run_auto_renewals(today=today)

    assert Payment.objects.get().status == PaymentStatus.FAILED


def test_the_first_retry_is_scheduled_one_day_later(
    member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The retry ladder starts a day after the decline."""
    make_mandate(
        member,
        annual_plan,
        ends_on=today + timedelta(days=CHARGE_LEAD_DAYS),
        last4=DECLINED_LAST4,
    )

    run_auto_renewals(today=today)

    retry = RenewalAttempt.objects.get(outcome=RenewalOutcome.SCHEDULED)
    assert retry.scheduled_on == today + timedelta(days=RETRY_OFFSETS[0])


def test_the_retry_chains_back_to_the_attempt_it_retries(
    member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """``retry_of`` is what ties a ladder of attempts to one renewal."""
    make_mandate(
        member,
        annual_plan,
        ends_on=today + timedelta(days=CHARGE_LEAD_DAYS),
        last4=DECLINED_LAST4,
    )

    run_auto_renewals(today=today)

    retry = RenewalAttempt.objects.get(outcome=RenewalOutcome.SCHEDULED)
    failed = RenewalAttempt.objects.get(outcome=RenewalOutcome.FAILED)
    assert retry.retry_of_id == failed.pk


def test_the_failure_email_names_the_day_of_the_next_attempt(
    member: User, annual_plan: MembershipPlan, today: date, mailoutbox: list[EmailMessage]
) -> None:
    """A member whose card failed is told when it will be tried again."""
    make_mandate(
        member,
        annual_plan,
        ends_on=today + timedelta(days=CHARGE_LEAD_DAYS),
        last4=DECLINED_LAST4,
    )

    run_auto_renewals(today=today)

    body = mailoutbox[-1].body
    next_on = today + timedelta(days=RETRY_OFFSETS[0])
    assert f"We will try again on {next_on.strftime('%B')} {next_on.day}, {next_on.year}" in body


def walk_the_ladder(today: date) -> date:
    """Scan on the charge date and on every retry date; return the last day scanned."""
    run_auto_renewals(today=today)
    day = today
    for offset in RETRY_OFFSETS:
        day = day + timedelta(days=offset)
        run_auto_renewals(today=day)
    return day


def test_a_mandate_is_paused_once_its_retries_run_out(
    member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """A charge and its three retries all failing turns automatic renewal off."""
    mandate = make_mandate(
        member,
        annual_plan,
        ends_on=today + timedelta(days=CHARGE_LEAD_DAYS),
        last4=DECLINED_LAST4,
    )

    walk_the_ladder(today)

    mandate.refresh_from_db()
    assert mandate.status == MandateStatus.PAUSED


def test_every_retry_is_attempted_before_the_pause(
    member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The ladder is the charge plus one attempt per retry offset, all failed."""
    make_mandate(
        member,
        annual_plan,
        ends_on=today + timedelta(days=CHARGE_LEAD_DAYS),
        last4=DECLINED_LAST4,
    )

    walk_the_ladder(today)

    assert RenewalAttempt.objects.filter(outcome=RenewalOutcome.FAILED).count() == (
        len(RETRY_OFFSETS) + 1
    )


def test_the_last_failure_tells_the_member_the_reminders_resume(
    member: User, annual_plan: MembershipPlan, today: date, mailoutbox: list[EmailMessage]
) -> None:
    """The final email says automatic renewal is off rather than naming another try."""
    make_mandate(
        member,
        annual_plan,
        ends_on=today + timedelta(days=CHARGE_LEAD_DAYS),
        last4=DECLINED_LAST4,
    )

    walk_the_ladder(today)

    assert "That was the last attempt" in mailoutbox[-1].body


def test_a_paused_mandate_schedules_nothing_further(
    member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """Once paused, no attempt is left waiting to charge the member again."""
    make_mandate(
        member,
        annual_plan,
        ends_on=today + timedelta(days=CHARGE_LEAD_DAYS),
        last4=DECLINED_LAST4,
    )

    last_day = walk_the_ladder(today)

    assert (
        RenewalAttempt.objects.filter(
            outcome=RenewalOutcome.SCHEDULED, scheduled_on__gte=last_day
        ).count()
        == 0
    )


def test_the_run_counts_the_mandate_it_paused(
    member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The summary an operator reads says how many mandates were turned off."""
    make_mandate(
        member,
        annual_plan,
        ends_on=today + timedelta(days=CHARGE_LEAD_DAYS),
        last4=DECLINED_LAST4,
    )
    run_auto_renewals(today=today)
    day = today
    for offset in RETRY_OFFSETS[:-1]:
        day = day + timedelta(days=offset)
        run_auto_renewals(today=day)

    final = run_auto_renewals(today=day + timedelta(days=RETRY_OFFSETS[-1]))

    assert final.paused == 1


# --------------------------------------------------------------------------
# The card-expiry warning
# --------------------------------------------------------------------------
def expiring_card_mandate(member: User, plan: MembershipPlan, today: date) -> RenewalMandate:
    """A mandate whose card expires at the end of this month, charged next month."""
    mandate = make_mandate(member, plan, ends_on=today + timedelta(days=45))
    mandate.method_exp_month = today.month
    mandate.method_exp_year = today.year
    mandate.save(update_fields=["method_exp_month", "method_exp_year"])
    return mandate


def test_a_card_that_expires_before_the_next_charge_earns_a_warning(
    member: User, annual_plan: MembershipPlan, today: date, mailoutbox: list[EmailMessage]
) -> None:
    """The member is warned while there is still time to save another card."""
    expiring_card_mandate(member, annual_plan, today)

    run_auto_renewals(today=today)

    assert "CalDART: the card we renew your membership with expires soon" in subjects(mailoutbox)


def test_the_card_warning_goes_out_only_once(
    member: User, annual_plan: MembershipPlan, today: date, mailoutbox: list[EmailMessage]
) -> None:
    """A daily scan does not nag the member about the same expiry every morning."""
    expiring_card_mandate(member, annual_plan, today)

    run_auto_renewals(today=today)
    run_auto_renewals(today=today)

    warnings = [s for s in subjects(mailoutbox) if "expires soon" in s]
    assert len(warnings) == 1


def test_a_card_good_past_the_next_charge_earns_no_warning(
    member: User, annual_plan: MembershipPlan, today: date, mailoutbox: list[EmailMessage]
) -> None:
    """A card that outlasts the renewal is nothing to tell the member about."""
    make_mandate(member, annual_plan, ends_on=today + timedelta(days=45))

    run_auto_renewals(today=today)

    assert [s for s in subjects(mailoutbox) if "expires soon" in s] == []


# --------------------------------------------------------------------------
# The run summary
# --------------------------------------------------------------------------
def test_the_summary_reports_the_charge_it_took(
    member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """``charged`` is what an operator reads to know money moved."""
    make_mandate(member, annual_plan, ends_on=today + timedelta(days=CHARGE_LEAD_DAYS))

    run = run_auto_renewals(today=today)

    assert run.as_dict()["charged"] == 1


def test_the_next_charge_date_follows_the_scheduled_attempt(
    member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """Once an attempt is waiting, that is the date the portal shows."""
    ends_on = today + timedelta(days=NOTICE_DAYS)
    mandate = make_mandate(member, annual_plan, ends_on=ends_on)

    run_auto_renewals(today=today)

    assert next_charge_on(mandate, today) == ends_on - timedelta(days=CHARGE_LEAD_DAYS)


def test_a_canceled_mandate_has_no_next_charge_date(
    member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """Nothing is due on a mandate that has been turned off."""
    mandate = make_mandate(member, annual_plan, ends_on=today + timedelta(days=NOTICE_DAYS))
    mandate.status = MandateStatus.CANCELED
    mandate.save(update_fields=["status"])

    assert next_charge_on(mandate, today) is None


# --------------------------------------------------------------------------
# The emails, word for word
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("template", "last4"),
    [("notice", "4242"), ("charged", "4242"), ("failed", DECLINED_LAST4)],
)
def test_the_renewal_emails_read_as_written(
    member: User,
    annual_plan: MembershipPlan,
    today: date,
    mailoutbox: list[EmailMessage],
    golden: Golden,
    template: str,
    last4: str,
) -> None:
    """Every renewal email's plain-text body matches its golden file exactly."""
    days = NOTICE_DAYS + CHARGE_LEAD_DAYS if template == "notice" else CHARGE_LEAD_DAYS
    ends_on = today + timedelta(days=days)
    make_mandate(member, annual_plan, ends_on=ends_on, last4=last4)

    run_auto_renewals(today=today)

    charge_on = ends_on - timedelta(days=CHARGE_LEAD_DAYS)
    replacements = {
        f"{ends_on.strftime('%B')} {ends_on.day}, {ends_on.year}": "<EXPIRES>",
        f"{charge_on.strftime('%B')} {charge_on.day}, {charge_on.year}": "<CHARGE>",
    }
    retry_on = today + timedelta(days=RETRY_OFFSETS[0])
    replacements[f"{retry_on.strftime('%B')} {retry_on.day}, {retry_on.year}"] = "<RETRY>"
    renewed_end = ends_on + timedelta(days=365)
    replacements[f"{renewed_end.strftime('%B')} {renewed_end.day}, {renewed_end.year}"] = (
        "<RENEWED>"
    )
    replacements[str(charge_on)] = "<CHARGE>"
    golden(f"renewal-{template}.txt", str(mailoutbox[-1].body), replace=replacements)


# --------------------------------------------------------------------------
# Two scans at once
# --------------------------------------------------------------------------
def test_an_attempt_another_run_already_took_is_not_charged_again(
    member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """Of two overlapping scans only the one that claimed the attempt charges it."""
    make_mandate(member, annual_plan, ends_on=today + timedelta(days=CHARGE_LEAD_DAYS))
    run_auto_renewals(today=today - timedelta(days=1))
    RenewalAttempt.objects.update(attempted_at=timezone.now())

    run_auto_renewals(today=today)

    assert Payment.objects.count() == 0


def test_an_attempt_another_run_already_took_is_counted_as_in_flight(
    member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The summary says why nothing happened, rather than reporting a charge."""
    make_mandate(member, annual_plan, ends_on=today + timedelta(days=CHARGE_LEAD_DAYS))
    run_auto_renewals(today=today - timedelta(days=1))
    RenewalAttempt.objects.update(attempted_at=timezone.now())

    run = run_auto_renewals(today=today)

    assert run.skipped_by_reason == {"in_flight": 1}


# --------------------------------------------------------------------------
# A provider that cannot be reached
# --------------------------------------------------------------------------
@pytest.fixture
def unreachable_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make every mock charge fail the way an unreachable provider does."""

    def refuse(self: MockProvider, mandate: RenewalMandate, payment: Payment) -> None:
        """Raise as the provider does when its API cannot be reached at all."""
        raise ProviderUnavailableError("We could not reach the payment provider.")

    monkeypatch.setattr(MockProvider, "charge_mandate", refuse)


def test_a_provider_outage_costs_the_member_no_rung_of_the_retry_ladder(
    unreachable_provider: None, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """Nothing was learned about the card, so nothing is held against it."""
    mandate = make_mandate(member, annual_plan, ends_on=today + timedelta(days=CHARGE_LEAD_DAYS))
    run_auto_renewals(today=today - timedelta(days=1))

    run_auto_renewals(today=today)

    mandate.refresh_from_db()
    assert mandate.failure_count == 0


def test_a_provider_outage_leaves_the_mandate_active(
    unreachable_provider: None, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """An outage never turns a member's automatic renewal off."""
    mandate = make_mandate(member, annual_plan, ends_on=today + timedelta(days=CHARGE_LEAD_DAYS))
    run_auto_renewals(today=today - timedelta(days=1))

    run_auto_renewals(today=today)

    mandate.refresh_from_db()
    assert mandate.status == MandateStatus.ACTIVE


def test_a_provider_outage_tells_the_member_nothing(
    unreachable_provider: None,
    member: User,
    annual_plan: MembershipPlan,
    today: date,
    mailoutbox: list[EmailMessage],
) -> None:
    """A member is not written to about a decline that never happened."""
    make_mandate(member, annual_plan, ends_on=today + timedelta(days=CHARGE_LEAD_DAYS))
    run_auto_renewals(today=today - timedelta(days=1))
    mailoutbox.clear()

    run_auto_renewals(today=today)

    assert subjects(mailoutbox) == []


def test_a_charge_a_provider_outage_stopped_is_tried_again(
    unreachable_provider: None, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The attempt is released, still scheduled, so the next scan takes it up."""
    make_mandate(member, annual_plan, ends_on=today + timedelta(days=CHARGE_LEAD_DAYS))
    run_auto_renewals(today=today - timedelta(days=1))

    run_auto_renewals(today=today)

    attempt = RenewalAttempt.objects.get()
    assert attempt.outcome == RenewalOutcome.SCHEDULED


def test_a_charge_a_provider_outage_stopped_leaves_no_pending_payment(
    unreachable_provider: None, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The payment row started for a charge nobody took is thrown away again."""
    make_mandate(member, annual_plan, ends_on=today + timedelta(days=CHARGE_LEAD_DAYS))
    run_auto_renewals(today=today - timedelta(days=1))

    run_auto_renewals(today=today)

    assert Payment.objects.count() == 0


# --------------------------------------------------------------------------
# Turning a paused mandate back on
# --------------------------------------------------------------------------
def pause_over_the_current_term(mandate: RenewalMandate) -> None:
    """Leave ``mandate`` paused with a failed attempt against its member's term."""
    RenewalAttemptFactory(
        mandate=mandate,
        membership=mandate.user.memberships.get(),
        outcome=RenewalOutcome.FAILED,
        error="Your card was declined.",
    )
    mandate.status = MandateStatus.PAUSED
    mandate.failure_count = len(RETRY_OFFSETS) + 1
    mandate.save(update_fields=["status", "failure_count"])


def test_a_reactivated_mandate_is_scheduled_for_the_term_that_paused_it(
    member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """Turning renewal back on rescues the term the failures were against."""
    mandate = make_mandate(member, annual_plan, ends_on=today + timedelta(days=NOTICE_DAYS))
    pause_over_the_current_term(mandate)
    save_method(mandate, mock_method(), actor=member)

    run_auto_renewals(today=today)

    assert RenewalAttempt.objects.filter(outcome=RenewalOutcome.SCHEDULED).count() == 1


def test_a_reactivated_mandate_charges_the_term_that_paused_it(
    member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The rescued term is charged on its charge date, so the membership stands."""
    ends_on = today + timedelta(days=NOTICE_DAYS)
    mandate = make_mandate(member, annual_plan, ends_on=ends_on)
    pause_over_the_current_term(mandate)
    save_method(mandate, mock_method(), actor=member)
    run_auto_renewals(today=today)

    run = run_auto_renewals(today=charge_date_for(ends_on))

    assert run.charged == 1


# --------------------------------------------------------------------------
# A notice the mail server refused
# --------------------------------------------------------------------------
def test_a_notice_the_mail_server_refused_is_sent_again_next_run(
    member: User,
    annual_plan: MembershipPlan,
    today: date,
    mailoutbox: list[EmailMessage],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A member whose mail bounced once still gets their fourteen days' warning."""
    make_mandate(member, annual_plan, ends_on=today + timedelta(days=NOTICE_DAYS))
    monkeypatch.setattr(renewals, "send_templated", refusing_mailer)
    run_auto_renewals(today=today)
    monkeypatch.undo()

    run_auto_renewals(today=today)

    assert subjects(mailoutbox)[-1].startswith("CalDART: we will renew your membership")
