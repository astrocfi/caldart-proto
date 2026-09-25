"""The report subscription endpoints: who may set one up, for whom, and send it now.

``/reports/subscriptions`` is the finance roles' own; each caller sees and touches only
the subscriptions for reports they may read.  A recipient with an account is bound to
it and must be allowed to read the report; an address outside CalDART needs the
caller's confirmation.  ``POST /reports/subscriptions/{id}/send`` sends one at once.
The daily run is covered by ``test_scheduled_reports.py``.
"""

from __future__ import annotations

import logging
from datetime import date

import pytest
from django.core.mail import EmailMessage, EmailMultiAlternatives
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import ACCOUNT_ADMIN, SYSTEM_ADMIN, TREASURER
from apps.mail.models import EmailLog
from apps.reports.models import ReportSubscription
from apps.reports.schedule import next_due_after
from caldart import audit
from tests.conftest import audit_messages, role_matrix
from tests.factories import ReportSubscriptionFactory

pytestmark = pytest.mark.django_db

SUBSCRIPTIONS_URL = "/api/v1/reports/subscriptions"

#: What an address outside CalDART is refused with until the caller confirms it.
CONFIRM_MESSAGE = "Tick the box to confirm this address may receive this report."


def subscription_url(subscription: ReportSubscription) -> str:
    """The detail endpoint of ``subscription``."""
    return f"{SUBSCRIPTIONS_URL}/{subscription.pk}"


def new_subscription(**overrides: object) -> dict[str, object]:
    """A ``POST`` body for a monthly PDF of the members report, with ``overrides``."""
    body: dict[str, object] = {
        "report": "members",
        "recipient_email": "accountadmin@example.test",
        "filters": {},
        "columns": [],
        "formats": "pdf",
        "cadence": "monthly",
        "weekday": 0,
    }
    return {**body, **overrides}


# -- who may manage them ----------------------------------------------------
@pytest.mark.parametrize(("role", "allowed"), role_matrix(TREASURER, ACCOUNT_ADMIN, SYSTEM_ADMIN))
def test_the_subscription_list_is_for_the_finance_roles(
    api_client: APIClient, all_role_users: dict[str, User], role: str, allowed: bool
) -> None:
    """A treasurer, an account administrator and a system administrator may list them."""
    api_client.force_login(all_role_users[role])

    response = api_client.get(SUBSCRIPTIONS_URL)

    assert response.status_code == (200 if allowed else 403)


def test_a_treasurer_sees_only_the_money_reports_subscriptions(
    treasurer_client: APIClient,
) -> None:
    """The members report's subscriptions are hidden from a caller who may not read it."""
    money = ReportSubscriptionFactory(report="payments", recipient_email="a@example.test")
    ReportSubscriptionFactory(report="members", recipient_email="b@example.test")

    rows = treasurer_client.get(SUBSCRIPTIONS_URL).json()

    assert [row["id"] for row in rows] == [money.pk]


def test_a_treasurer_cannot_open_a_members_report_subscription(
    treasurer_client: APIClient,
) -> None:
    """A subscription for a report the caller may not read answers 404."""
    hidden = ReportSubscriptionFactory(report="members")

    assert treasurer_client.get(subscription_url(hidden)).status_code == 404


def test_a_treasurer_cannot_subscribe_anyone_to_the_members_report(
    treasurer_client: APIClient, account_admin: User
) -> None:
    """Setting up a report the caller may not read answers 403."""
    response = treasurer_client.post(SUBSCRIPTIONS_URL, new_subscription(), format="json")

    assert response.status_code == 403


def test_the_list_describes_each_subscription(
    account_admin_client: APIClient, account_admin: User, today: date
) -> None:
    """Each row names the report, the recipient, the schedule and when it next goes."""
    subscription = ReportSubscriptionFactory(
        report="payments",
        recipient_user=account_admin,
        recipient_email=account_admin.email,
        filters={"period": "this_year"},
        columns=["paid_on", "amount"],
        formats="both",
        cadence="weekly",
        weekday=2,
        created_by=account_admin,
        next_due_on=today,
    )

    rows = account_admin_client.get(SUBSCRIPTIONS_URL).json()

    assert rows == [
        {
            "id": subscription.pk,
            "report": "payments",
            "report_title": "CalDART payments",
            "recipient_user": account_admin.pk,
            "recipient_name": "Zoe Yeager",
            "recipient_email": "accountadmin@example.test",
            "filters": {"period": "this_year"},
            "columns": ["paid_on", "amount"],
            "formats": "both",
            "cadence": "weekly",
            "weekday": 2,
            "is_active": True,
            "created_by_name": "Zoe Yeager",
            "last_sent_at": None,
            "next_due_on": today.isoformat(),
        }
    ]


# -- creating one -----------------------------------------------------------
def test_an_address_with_an_account_binds_the_subscription_to_it(
    account_admin_client: APIClient, account_admin: User
) -> None:
    """The recipient's account is found by address, whatever its case."""
    response = account_admin_client.post(
        SUBSCRIPTIONS_URL,
        new_subscription(recipient_email="AccountAdmin@Example.TEST"),
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["recipient_user"] == account_admin.pk


def test_a_bound_subscription_keeps_the_accounts_own_address(
    account_admin_client: APIClient, account_admin: User
) -> None:
    """The address stored is the account's, not the one typed."""
    response = account_admin_client.post(
        SUBSCRIPTIONS_URL,
        new_subscription(recipient_email="AccountAdmin@Example.TEST"),
        format="json",
    )

    assert response.json()["recipient_email"] == "accountadmin@example.test"


def test_a_new_subscription_is_first_due_on_its_next_scheduled_day(
    account_admin_client: APIClient, account_admin: User, today: date
) -> None:
    """``next_due_on`` is the schedule's next day after today; the caller set it up."""
    response = account_admin_client.post(
        SUBSCRIPTIONS_URL, new_subscription(cadence="weekly", weekday=3), format="json"
    )

    subscription = ReportSubscription.objects.get(pk=response.json()["id"])
    assert subscription.next_due_on == next_due_after("weekly", 3, today)
    assert subscription.created_by == account_admin


def test_a_recipient_who_may_not_read_the_report_is_refused(
    account_admin_client: APIClient, treasurer: User
) -> None:
    """A treasurer's address cannot receive the members report."""
    response = account_admin_client.post(
        SUBSCRIPTIONS_URL, new_subscription(recipient_email=treasurer.email), format="json"
    )

    assert response.status_code == 400
    assert response.json() == {
        "recipient_email": ["Casey Lund does not hold a role that may read this report."]
    }


def test_a_bare_address_is_refused_until_it_is_confirmed(
    account_admin_client: APIClient,
) -> None:
    """An address no account holds needs ``confirmed``, keyed so the form can ask."""
    response = account_admin_client.post(
        SUBSCRIPTIONS_URL,
        new_subscription(recipient_email="board@example.org"),
        format="json",
    )

    assert response.status_code == 400
    assert response.json() == {"confirmed": [CONFIRM_MESSAGE]}


def test_a_confirmed_bare_address_is_accepted_unbound(
    account_admin_client: APIClient,
) -> None:
    """With ``confirmed`` the subscription goes to the address alone."""
    response = account_admin_client.post(
        SUBSCRIPTIONS_URL,
        new_subscription(recipient_email="board@example.org", confirmed=True),
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["recipient_user"] is None


def test_confirming_does_not_excuse_an_account_without_the_role(
    account_admin_client: APIClient, treasurer: User
) -> None:
    """``confirmed`` speaks for outside addresses; an account still needs the role."""
    response = account_admin_client.post(
        SUBSCRIPTIONS_URL,
        new_subscription(recipient_email=treasurer.email, confirmed=True),
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.parametrize(
    ("overrides", "errors"),
    [
        ({"report": "nope"}, {"report": ['"nope" is not a valid choice.']}),
        ({"columns": ["nope"]}, {"columns": ["Unknown column: nope"]}),
        ({"columns": ["name", "name"]}, {"columns": ["Repeated column: name"]}),
        (
            {"filters": {"status": "sideways"}},
            {
                "filters": {
                    "status": [
                        "Select a valid choice. sideways is not one of the available choices."
                    ]
                }
            },
        ),
        (
            {"filters": {"columns": "name"}},
            {"filters": {"columns": ["Choose columns with the columns field, not as a filter."]}},
        ),
        ({"weekday": 7}, {"weekday": ["Ensure this value is less than or equal to 6."]}),
        ({"cadence": "daily"}, {"cadence": ['"daily" is not a valid choice.']}),
        ({"formats": "xls"}, {"formats": ['"xls" is not a valid choice.']}),
    ],
    ids=[
        "unknown-report",
        "unknown-column",
        "repeated-column",
        "bad-filter",
        "columns-as-filter",
        "weekday",
        "cadence",
        "formats",
    ],
)
def test_a_bad_subscription_is_refused_with_the_reason(
    account_admin_client: APIClient,
    account_admin: User,
    overrides: dict[str, object],
    errors: dict[str, object],
) -> None:
    """The report, its filters, its columns and the schedule are all checked."""
    response = account_admin_client.post(
        SUBSCRIPTIONS_URL, new_subscription(**overrides), format="json"
    )

    assert response.status_code == 400
    assert response.json() == errors


def test_an_unknown_period_is_refused_under_filters(
    account_admin_client: APIClient, account_admin: User
) -> None:
    """A dated report's ``period`` is checked like any other filter."""
    response = account_admin_client.post(
        SUBSCRIPTIONS_URL,
        new_subscription(report="payments", filters={"period": "someday"}),
        format="json",
    )

    assert response.json() == {"filters": {"period": ["Unknown period 'someday'."]}}


def test_a_fixed_report_takes_no_columns(
    account_admin_client: APIClient, account_admin: User
) -> None:
    """A report whose columns are fixed refuses a column choice."""
    response = account_admin_client.post(
        SUBSCRIPTIONS_URL,
        new_subscription(report="contributions", columns=["name"]),
        format="json",
    )

    assert response.json() == {"columns": ["This report's columns are fixed."]}


# -- changing and removing one ----------------------------------------------
def test_pausing_a_subscription(account_admin_client: APIClient) -> None:
    """``PATCH`` with ``is_active`` false pauses it."""
    subscription = ReportSubscriptionFactory()

    response = account_admin_client.patch(
        subscription_url(subscription), {"is_active": False}, format="json"
    )

    subscription.refresh_from_db()
    assert response.status_code == 200
    assert subscription.is_active is False


def test_changing_the_schedule_moves_the_next_due_day(
    account_admin_client: APIClient, today: date
) -> None:
    """A new cadence or weekday counts the next day from today."""
    subscription = ReportSubscriptionFactory(cadence="monthly", next_due_on=today)

    account_admin_client.patch(
        subscription_url(subscription), {"cadence": "weekly", "weekday": 4}, format="json"
    )

    subscription.refresh_from_db()
    assert subscription.next_due_on == next_due_after("weekly", 4, today)


def test_changing_the_formats_leaves_the_next_due_day(
    account_admin_client: APIClient, today: date
) -> None:
    """An edit that is not to the schedule keeps the day it is due."""
    subscription = ReportSubscriptionFactory(next_due_on=today)

    account_admin_client.patch(subscription_url(subscription), {"formats": "csv"}, format="json")

    subscription.refresh_from_db()
    assert subscription.next_due_on == today


def test_the_recipient_cannot_be_changed(account_admin_client: APIClient) -> None:
    """The address is fixed once set up; ``PATCH`` ignores it."""
    subscription = ReportSubscriptionFactory(recipient_email="first@example.test")

    account_admin_client.patch(
        subscription_url(subscription), {"recipient_email": "other@example.test"}, format="json"
    )

    subscription.refresh_from_db()
    assert subscription.recipient_email == "first@example.test"


def test_resuming_for_a_recipient_who_lost_the_role_is_refused(
    account_admin_client: APIClient, treasurer: User
) -> None:
    """A subscription whose account may no longer read the report stays paused."""
    subscription = ReportSubscriptionFactory(
        recipient_user=treasurer, recipient_email=treasurer.email, is_active=False
    )

    response = account_admin_client.patch(
        subscription_url(subscription), {"is_active": True}, format="json"
    )

    assert response.status_code == 400
    assert response.json() == {
        "is_active": ["Casey Lund does not hold a role that may read this report."]
    }


def test_a_patch_checks_the_columns_against_the_report(
    account_admin_client: APIClient,
) -> None:
    """The columns are checked on every write, not only on the first."""
    subscription = ReportSubscriptionFactory()

    response = account_admin_client.patch(
        subscription_url(subscription), {"columns": ["nope"]}, format="json"
    )

    assert response.json() == {"columns": ["Unknown column: nope"]}


def test_deleting_a_subscription(account_admin_client: APIClient) -> None:
    """``DELETE`` answers 204 and the subscription is gone."""
    subscription = ReportSubscriptionFactory()

    response = account_admin_client.delete(subscription_url(subscription))

    assert response.status_code == 204
    assert ReportSubscription.objects.filter(pk=subscription.pk).exists() is False


# -- sending one now --------------------------------------------------------
def test_send_now_emails_the_report_to_the_recipient(
    account_admin_client: APIClient, mailoutbox: list[EmailMessage]
) -> None:
    """The run result counts one send and names where it went."""
    subscription = ReportSubscriptionFactory(recipient_email="board@example.org")

    response = account_admin_client.post(f"{subscription_url(subscription)}/send")

    assert response.status_code == 200
    assert response.json() == {
        "sent": 1,
        "skipped": 0,
        "failed": 0,
        "skipped_by_reason": {},
        "actions": [
            {
                "kind": "report",
                "member": "board@example.org",
                "email": "board@example.org",
                "on": None,
                "amount_cents": None,
                "detail": "CalDART membership report, PDF",
            }
        ],
    }


def test_send_now_attaches_the_report(
    account_admin_client: APIClient, mailoutbox: list[EmailMultiAlternatives], today: date
) -> None:
    """The email carries the dated PDF the export would download."""
    subscription = ReportSubscriptionFactory()

    account_admin_client.post(f"{subscription_url(subscription)}/send")

    names = [name for name, _content, _mimetype in mailoutbox[0].attachments]
    assert names == [f"caldart-members-{today.isoformat()}.pdf"]


def test_send_now_leaves_the_next_due_day(
    account_admin_client: APIClient, mailoutbox: list[EmailMessage], today: date
) -> None:
    """Sending by hand does not move the schedule, but does stamp ``last_sent_at``."""
    subscription = ReportSubscriptionFactory(next_due_on=date(2099, 1, 1))

    account_admin_client.post(f"{subscription_url(subscription)}/send")

    subscription.refresh_from_db()
    assert subscription.next_due_on == date(2099, 1, 1)
    assert subscription.last_sent_at is not None


def test_send_now_is_recorded_in_the_email_log(
    account_admin_client: APIClient, mailoutbox: list[EmailMessage], account_admin: User
) -> None:
    """The email log names the purpose and the account the report went to."""
    subscription = ReportSubscriptionFactory(
        recipient_user=account_admin, recipient_email=account_admin.email
    )

    account_admin_client.post(f"{subscription_url(subscription)}/send")

    entry = EmailLog.objects.get()
    assert (entry.purpose, entry.user_id) == ("scheduled_report", account_admin.pk)


def test_send_now_writes_one_audit_line(
    account_admin_client: APIClient,
    account_admin: User,
    mailoutbox: list[EmailMessage],
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """The line names the caller, the subscription and what happened."""
    subscription = ReportSubscriptionFactory()

    account_admin_client.post(f"{subscription_url(subscription)}/send")

    assert audit_messages(audit_log, logging.INFO) == [
        f"action={audit.REPORT_SEND} actor={account_admin.pk} target={subscription.pk} "
        "kind=subscription dry_run=false sent=1 skipped=0 failed=0"
    ]


def test_send_now_to_a_hidden_report_is_not_found(treasurer_client: APIClient) -> None:
    """A treasurer cannot send the members report, even by id."""
    subscription = ReportSubscriptionFactory(report="members")

    assert treasurer_client.post(f"{subscription_url(subscription)}/send").status_code == 404
