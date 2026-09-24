"""What a scan reports it did, or would do, person by person.

``RunAction`` carries the member behind each email and each charge.  These tests
cover the line each action prints, and check that the renewal scanner's dry run
names exactly the people a live run then writes to.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.core.mail import EmailMessage
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.members.models import MembershipPlan, MembershipStatusChoices
from apps.payments.renewals import CHARGE_LEAD_DAYS, NOTICE_DAYS, run_auto_renewals
from caldart.runs import CHARGE_KIND, RunAction, action_lines
from tests.factories import MembershipFactory, RenewalMandateFactory

pytestmark = pytest.mark.django_db

#: Where ``POST /system/renewals/run`` lives.
RENEWALS_RUN_URL = "/api/v1/system/renewals/run"

#: A stand-in member for the line-formatting tests, which need no database.
SAMPLE = RunAction(kind="renewal_notice", member="Dana Lee", email="dana@example.org")


def set_up_renewal(user: User, plan: MembershipPlan, *, ends_on: date) -> None:
    """Give ``user`` a term ending on ``ends_on`` and an active mandate over it."""
    MembershipFactory(
        user=user,
        plan=plan,
        starts_on=ends_on - timedelta(days=364),
        ends_on=ends_on,
        status=MembershipStatusChoices.ACTIVE,
    )
    RenewalMandateFactory(user=user, plan=plan)


def kinds_and_emails(actions: list[RunAction]) -> list[tuple[str, str]]:
    """Each action reduced to what happened and who it happened to."""
    return [(action.kind, action.email) for action in actions]


# --------------------------------------------------------------------------
# The printed line
# --------------------------------------------------------------------------
def test_a_rehearsed_email_reads_as_something_that_would_happen() -> None:
    """A dry run's line says ``would email``, names the kind and the address."""
    assert SAMPLE.as_line(dry_run=True) == (
        "would email renewal_notice to Dana Lee <dana@example.org>"
    )


def test_a_sent_email_reads_as_something_that_did_happen() -> None:
    """A live run's line says ``emailed`` instead."""
    assert SAMPLE.as_line(dry_run=False) == "emailed renewal_notice to Dana Lee <dana@example.org>"


def test_a_charge_reads_with_its_amount_and_its_date() -> None:
    """A charge names the money and the day it falls, in dollars and ISO."""
    action = RunAction(
        kind=CHARGE_KIND,
        member="Dana Lee",
        email="dana@example.org",
        on=date(2026, 6, 19),
        amount_cents=4_500,
    )

    assert action.as_line(dry_run=True) == (
        "would charge Dana Lee <dana@example.org> $45.00 on 2026-06-19"
    )


def test_a_detail_is_printed_in_parentheses() -> None:
    """Anything else worth saying follows the rest of the line in brackets."""
    action = RunAction(
        kind="renewal_failed",
        member="Dana Lee",
        email="dana@example.org",
        detail="Your card was declined",
    )

    assert action.as_line(dry_run=False) == (
        "emailed renewal_failed to Dana Lee <dana@example.org> (Your card was declined)"
    )


def test_an_action_serializes_its_date_as_an_iso_string() -> None:
    """``as_dict`` is the JSON the run endpoints answer with."""
    action = RunAction(
        kind=CHARGE_KIND,
        member="Dana Lee",
        email="dana@example.org",
        on=date(2026, 6, 19),
        amount_cents=4_500,
    )

    assert action.as_dict() == {
        "kind": CHARGE_KIND,
        "member": "Dana Lee",
        "email": "dana@example.org",
        "on": "2026-06-19",
        "amount_cents": 4_500,
        "detail": "",
    }


def test_a_scan_with_nothing_to_do_prints_no_action_lines() -> None:
    """No actions means no lines, so the counts stand alone."""
    assert action_lines([], dry_run=True) == []


# --------------------------------------------------------------------------
# The renewal scan
# --------------------------------------------------------------------------
def test_a_rehearsed_notice_names_the_member_and_the_charge_date(
    member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """A dry run says who the advance warning would go to, and when the charge falls."""
    ends_on = today + timedelta(days=NOTICE_DAYS + CHARGE_LEAD_DAYS)
    set_up_renewal(member, annual_plan, ends_on=ends_on)

    run = run_auto_renewals(today=today, dry_run=True)

    assert [action.as_dict() for action in run.actions] == [
        {
            "kind": "renewal_notice",
            "member": member.display_name,
            "email": member.email,
            "on": (ends_on - timedelta(days=CHARGE_LEAD_DAYS)).isoformat(),
            "amount_cents": None,
            "detail": "",
        }
    ]


def test_a_rehearsed_charge_carries_the_amount(
    member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """The charge a dry run would take names the money, in integer cents."""
    set_up_renewal(member, annual_plan, ends_on=today + timedelta(days=CHARGE_LEAD_DAYS))
    run_auto_renewals(today=today - timedelta(days=1))

    run = run_auto_renewals(today=today, dry_run=True)

    charges = [action for action in run.actions if action.kind == CHARGE_KIND]
    assert charges[0].amount_cents == annual_plan.price_cents


def test_a_rehearsal_names_the_people_a_live_run_then_writes_to(
    member: User,
    annual_plan: MembershipPlan,
    today: date,
    mailoutbox: list[EmailMessage],
) -> None:
    """The dry run's list and the live run's list agree, action for action."""
    set_up_renewal(member, annual_plan, ends_on=today + timedelta(days=CHARGE_LEAD_DAYS))
    run_auto_renewals(today=today - timedelta(days=1))

    rehearsed = run_auto_renewals(today=today, dry_run=True)
    live = run_auto_renewals(today=today)

    assert kinds_and_emails(live.actions) == kinds_and_emails(rehearsed.actions)


def test_a_live_run_records_the_charge_it_took(
    member: User,
    annual_plan: MembershipPlan,
    today: date,
    mailoutbox: list[EmailMessage],
) -> None:
    """A live run's actions are the charge and the message reporting it."""
    set_up_renewal(member, annual_plan, ends_on=today + timedelta(days=CHARGE_LEAD_DAYS))
    run_auto_renewals(today=today - timedelta(days=1))

    live = run_auto_renewals(today=today)

    assert [action.kind for action in live.actions] == [CHARGE_KIND, "renewal_charged"]


def test_the_command_prints_who_would_be_written_to(
    member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """``run_auto_renewals --dry-run`` prints one line per member under the counts."""
    ends_on = today + timedelta(days=NOTICE_DAYS + CHARGE_LEAD_DAYS)
    set_up_renewal(member, annual_plan, ends_on=ends_on)

    run = run_auto_renewals(today=today, dry_run=True)

    charge_on = ends_on - timedelta(days=CHARGE_LEAD_DAYS)
    expected = (
        f"would email renewal_notice to {member.display_name} <{member.email}> "
        f"on {charge_on.isoformat()}"
    )
    assert run.as_lines()[-1] == expected


def test_the_run_endpoint_answers_the_actions(
    api_client: APIClient,
    system_admin: User,
    member: User,
    annual_plan: MembershipPlan,
    today: date,
) -> None:
    """``POST /system/renewals/run`` carries the actions beside the counts."""
    set_up_renewal(member, annual_plan, ends_on=today + timedelta(days=NOTICE_DAYS))
    api_client.force_login(system_admin)

    body = api_client.post(RENEWALS_RUN_URL, {"dry_run": True}, format="json").json()

    assert body["actions"][0]["email"] == member.email


def test_the_run_endpoint_answers_an_empty_list_when_nothing_is_due(
    api_client: APIClient, system_admin: User
) -> None:
    """A scan with nothing to do reports no actions rather than leaving the key out."""
    api_client.force_login(system_admin)

    body = api_client.post(RENEWALS_RUN_URL, {"dry_run": True}, format="json").json()

    assert body["actions"] == []
