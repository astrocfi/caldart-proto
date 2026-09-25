"""The report subscriptions' schedule and the daily run that sends them.

``next_due_after`` over every cadence from several dates; a run on a frozen clock
sends what is due and nothing else, moves each sent subscription on, leaves a refused
send due, pauses a recipient who lost the role, attaches both files for ``both``, and
writes one audit line.  The DART rosters the same run sends are covered by
``test_dart_rosters.py``, and the endpoints by ``test_report_subscriptions.py``.
"""

from __future__ import annotations

from datetime import date
from io import StringIO

import pytest
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.core.management import call_command
from django.core.management.base import CommandError
from pytest_django.fixtures import Settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import SYSTEM_ADMIN
from apps.cms.models import SiteSettings
from apps.mail.models import EmailLog, EmailStatus
from apps.reports.schedule import next_due_after, schedule_label
from apps.reports.services import run_scheduled_reports
from caldart import audit
from tests.conftest import Golden, PdfText, audit_messages, role_matrix
from tests.factories import ReportSubscriptionFactory

RUN_URL = "/api/v1/system/reports/run"


@pytest.mark.parametrize(
    ("weekday", "day", "expected"),
    [
        (0, date(2026, 9, 25), date(2026, 9, 28)),
        (0, date(2026, 9, 28), date(2026, 10, 5)),
        (4, date(2026, 9, 25), date(2026, 10, 2)),
        (6, date(2026, 12, 30), date(2027, 1, 3)),
        (2, date(2026, 9, 29), date(2026, 9, 30)),
    ],
    ids=[
        "friday-to-monday",
        "monday-to-next-monday",
        "friday-to-friday",
        "across-a-year",
        "next-day",
    ],
)
def test_weekly_is_the_next_chosen_weekday_strictly_after_the_day(
    weekday: int, day: date, expected: date
) -> None:
    """A weekly subscription falls on the next ``weekday`` after ``day``, never on it."""
    assert next_due_after("weekly", weekday, day) == expected


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (date(2026, 9, 25), date(2026, 10, 1)),
        (date(2026, 10, 1), date(2026, 11, 1)),
        (date(2026, 12, 31), date(2027, 1, 1)),
        (date(2027, 1, 31), date(2027, 2, 1)),
    ],
    ids=["mid-month", "on-the-first", "december", "end-of-january"],
)
def test_monthly_is_the_first_of_the_next_month(day: date, expected: date) -> None:
    """A monthly subscription falls on the first of the month after ``day``."""
    assert next_due_after("monthly", 0, day) == expected


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (date(2026, 1, 1), date(2026, 4, 1)),
        (date(2026, 3, 31), date(2026, 4, 1)),
        (date(2026, 4, 1), date(2026, 7, 1)),
        (date(2026, 9, 25), date(2026, 10, 1)),
        (date(2026, 10, 1), date(2027, 1, 1)),
        (date(2026, 12, 31), date(2027, 1, 1)),
    ],
    ids=["new-year", "end-of-march", "april-first", "september", "october-first", "new-years-eve"],
)
def test_quarterly_is_the_first_day_of_the_next_quarter(day: date, expected: date) -> None:
    """A quarterly subscription falls on the next January, April, July or October 1."""
    assert next_due_after("quarterly", 0, day) == expected


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (date(2026, 1, 1), date(2027, 1, 1)),
        (date(2026, 9, 25), date(2027, 1, 1)),
        (date(2026, 12, 31), date(2027, 1, 1)),
    ],
    ids=["new-year", "september", "new-years-eve"],
)
def test_yearly_is_the_next_january_first(day: date, expected: date) -> None:
    """A yearly subscription falls on the next January 1 after ``day``."""
    assert next_due_after("yearly", 0, day) == expected


def test_an_unknown_cadence_is_refused() -> None:
    """A cadence the schedule does not know raises, naming it."""
    with pytest.raises(ValueError, match="Unknown cadence: daily"):
        next_due_after("daily", 0, date(2026, 9, 25))


@pytest.mark.parametrize(
    ("cadence", "weekday", "expected"),
    [
        ("weekly", 0, "weekly on Monday"),
        ("weekly", 6, "weekly on Sunday"),
        ("monthly", 3, "monthly"),
        ("quarterly", 0, "quarterly"),
        ("yearly", 0, "yearly"),
    ],
)
def test_the_schedule_in_words(cadence: str, weekday: int, expected: str) -> None:
    """A weekly schedule names its day; the others are their cadence."""
    assert schedule_label(cadence, weekday) == expected


# -- the run ------------------------------------------------------------------
#: The day every run below is made on: the first of a month.
TODAY = date(2026, 10, 1)


@pytest.fixture
def named_site(settings: Settings, site_settings: SiteSettings) -> None:
    """Pin the organization name and the contact address the emails print."""
    settings.SITE_URL = "https://caldart.example.org/"
    site_settings.org_name = "The California DART Network"
    site_settings.contact_email = "info@caldart.example.org"
    site_settings.save()


@pytest.mark.django_db
def test_a_run_sends_what_is_due_and_nothing_else(mailoutbox: list[EmailMessage]) -> None:
    """Due today or earlier and active is sent; due later, or paused, is not."""
    ReportSubscriptionFactory(recipient_email="today@example.test", next_due_on=TODAY)
    ReportSubscriptionFactory(recipient_email="overdue@example.test", next_due_on=date(2026, 9, 1))
    ReportSubscriptionFactory(recipient_email="later@example.test", next_due_on=date(2026, 10, 2))
    ReportSubscriptionFactory(
        recipient_email="paused@example.test", next_due_on=TODAY, is_active=False
    )

    run_scheduled_reports(today=TODAY)

    assert sorted(message.to[0] for message in mailoutbox) == [
        "overdue@example.test",
        "today@example.test",
    ]


@pytest.mark.django_db
def test_a_sent_subscription_moves_on_to_its_next_day(mailoutbox: list[EmailMessage]) -> None:
    """``next_due_on`` is the schedule's next day after the day it was sent."""
    subscription = ReportSubscriptionFactory(cadence="weekly", weekday=2, next_due_on=TODAY)

    run_scheduled_reports(today=TODAY)

    subscription.refresh_from_db()
    assert subscription.next_due_on == date(2026, 10, 7)


@pytest.mark.django_db
def test_a_sent_subscription_records_when_it_went(mailoutbox: list[EmailMessage]) -> None:
    """``last_sent_at`` is stamped by a send that went out."""
    subscription = ReportSubscriptionFactory(next_due_on=TODAY)

    run_scheduled_reports(today=TODAY)

    subscription.refresh_from_db()
    assert subscription.last_sent_at is not None


@pytest.mark.django_db
def test_a_refused_send_stays_due(refusing_mail_server: None) -> None:
    """A send the mail server refuses is counted and leaves the subscription as it was."""
    subscription = ReportSubscriptionFactory(next_due_on=TODAY)

    run = run_scheduled_reports(today=TODAY)

    subscription.refresh_from_db()
    assert run.failed == 1
    assert subscription.next_due_on == TODAY
    assert subscription.last_sent_at is None


@pytest.mark.django_db
def test_a_refused_send_is_in_the_email_log(refusing_mail_server: None) -> None:
    """The email log keeps the refusal, under the subscription's purpose."""
    ReportSubscriptionFactory(recipient_email="board@example.org", next_due_on=TODAY)

    run_scheduled_reports(today=TODAY)

    entry = EmailLog.objects.get()
    assert (entry.to_email, entry.purpose, entry.status) == (
        "board@example.org",
        "scheduled_report",
        EmailStatus.FAILED,
    )


@pytest.mark.django_db
def test_a_recipient_who_lost_the_role_is_skipped_and_paused(
    treasurer: User, mailoutbox: list[EmailMessage]
) -> None:
    """The members report bound to a treasurer is not sent; the subscription pauses."""
    subscription = ReportSubscriptionFactory(
        recipient_user=treasurer, recipient_email=treasurer.email, next_due_on=TODAY
    )

    run = run_scheduled_reports(today=TODAY)

    subscription.refresh_from_db()
    assert run.skipped_by_reason == {"not_permitted": 1}
    assert subscription.is_active is False
    assert mailoutbox == []


@pytest.mark.django_db
def test_a_deactivated_recipient_is_skipped_as_not_permitted(
    account_admin: User, mailoutbox: list[EmailMessage]
) -> None:
    """An account that can no longer sign in is sent nothing."""
    account_admin.is_active = False
    account_admin.save(update_fields=["is_active"])
    ReportSubscriptionFactory(
        recipient_user=account_admin, recipient_email=account_admin.email, next_due_on=TODAY
    )

    run = run_scheduled_reports(today=TODAY)

    assert run.skipped_by_reason == {"not_permitted": 1}


@pytest.mark.django_db
def test_both_formats_attach_two_files(mailoutbox: list[EmailMultiAlternatives]) -> None:
    """``both`` attaches the CSV and then the PDF, each dated the day it was built."""
    ReportSubscriptionFactory(formats="both", next_due_on=TODAY)

    run_scheduled_reports(today=TODAY)

    attached = [(name, mimetype) for name, _content, mimetype in mailoutbox[0].attachments]
    assert attached == [
        ("caldart-members-2026-10-01.csv", "text/csv"),
        ("caldart-members-2026-10-01.pdf", "application/pdf"),
    ]


@pytest.mark.django_db
def test_the_attachment_carries_the_chosen_columns(
    mailoutbox: list[EmailMultiAlternatives],
) -> None:
    """The CSV holds exactly the columns the subscription chose, in its order."""
    ReportSubscriptionFactory(formats="csv", columns=["email", "name"], next_due_on=TODAY)

    run_scheduled_reports(today=TODAY)

    _name, content, _mimetype = mailoutbox[0].attachments[0]
    assert content.splitlines()[0] == "Email,Name"


@pytest.mark.django_db
def test_a_period_is_the_one_the_report_is_sent_in(
    mailoutbox: list[EmailMultiAlternatives], pdf_text: PdfText
) -> None:
    """``this_year`` on a payments subscription means the year of the send."""
    ReportSubscriptionFactory(
        report="payments", filters={"period": "this_year"}, formats="pdf", next_due_on=TODAY
    )

    run_scheduled_reports(today=TODAY)

    _name, content, _mimetype = mailoutbox[0].attachments[0]
    assert "from: 2026-01-01 \u00b7 to: 2026-12-31" in pdf_text(bytes(content))[0]


@pytest.mark.django_db
def test_the_subject_names_the_report_and_the_day(mailoutbox: list[EmailMessage]) -> None:
    """The subject reads ``CalDART report: <title> (<Month D, YYYY>)``."""
    ReportSubscriptionFactory(next_due_on=TODAY)

    run_scheduled_reports(today=TODAY)

    assert mailoutbox[0].subject == "CalDART report: CalDART membership report (October 1, 2026)"


@pytest.mark.django_db
def test_the_body_matches_its_recorded_text(
    mailoutbox: list[EmailMessage], named_site: None, fixed_name_admin: User, golden: Golden
) -> None:
    """The plain-text body of a subscription's email, whole."""
    ReportSubscriptionFactory(
        recipient_email="board@example.org",
        filters={"status": "current"},
        formats="both",
        cadence="weekly",
        weekday=3,
        created_by=fixed_name_admin,
        next_due_on=TODAY,
    )

    run_scheduled_reports(today=TODAY)

    golden("scheduled-report.txt", str(mailoutbox[0].body))


@pytest.mark.django_db
def test_a_dry_run_sends_and_changes_nothing(mailoutbox: list[EmailMessage]) -> None:
    """A rehearsal names the email it would send and leaves the subscription due."""
    subscription = ReportSubscriptionFactory(recipient_email="board@example.org", next_due_on=TODAY)

    run = run_scheduled_reports(today=TODAY, dry_run=True)

    subscription.refresh_from_db()
    assert [action.email for action in run.actions] == ["board@example.org"]
    assert mailoutbox == []
    assert subscription.next_due_on == TODAY


@pytest.mark.django_db
def test_a_dry_run_leaves_a_recipient_without_the_role_active(treasurer: User) -> None:
    """A rehearsal counts the skip but does not pause the subscription."""
    subscription = ReportSubscriptionFactory(
        recipient_user=treasurer, recipient_email=treasurer.email, next_due_on=TODAY
    )

    run_scheduled_reports(today=TODAY, dry_run=True)

    subscription.refresh_from_db()
    assert subscription.is_active is True


@pytest.mark.django_db
def test_every_run_writes_one_audit_line(
    mailoutbox: list[EmailMessage], audit_log: pytest.LogCaptureFixture
) -> None:
    """The line carries the mode and the three counts, under the command actor."""
    ReportSubscriptionFactory(next_due_on=TODAY)

    run_scheduled_reports(today=TODAY)

    assert audit_messages(audit_log) == [
        f"action={audit.REPORTS_RUN} actor=command target=- dry_run=false sent=1 skipped=0 failed=0"
    ]


@pytest.mark.django_db
def test_the_run_names_each_email_in_its_lines(mailoutbox: list[EmailMessage]) -> None:
    """The printed summary ends with one line per email sent."""
    ReportSubscriptionFactory(recipient_email="board@example.org", next_due_on=TODAY)

    lines = run_scheduled_reports(today=TODAY).as_lines()

    assert lines[-1] == (
        "emailed report to board@example.org <board@example.org> (CalDART membership report, PDF)"
    )


# -- the command and the endpoint --------------------------------------------
@pytest.mark.django_db
def test_the_command_sends_and_reports(mailoutbox: list[EmailMessage]) -> None:
    """``send_scheduled_reports --today`` runs on that day and prints what it sent."""
    ReportSubscriptionFactory(next_due_on=TODAY)
    out = StringIO()

    call_command("send_scheduled_reports", "--today=2026-10-01", stdout=out)

    assert "sent 1, skipped 0" in out.getvalue()


@pytest.mark.django_db
def test_the_command_rehearses_with_dry_run(mailoutbox: list[EmailMessage]) -> None:
    """``--dry-run`` says what it would send and sends nothing."""
    ReportSubscriptionFactory(next_due_on=TODAY)
    out = StringIO()

    call_command("send_scheduled_reports", "--today=2026-10-01", "--dry-run", stdout=out)

    assert "would send 1, skipped 0" in out.getvalue()


@pytest.mark.django_db
def test_the_command_refuses_a_bad_date() -> None:
    """``--today`` must be ``YYYY-MM-DD``."""
    with pytest.raises(CommandError, match="--today must be YYYY-MM-DD, not 'soon'"):
        call_command("send_scheduled_reports", "--today=soon")


@pytest.mark.django_db
def test_the_command_fails_when_a_send_is_refused(refusing_mail_server: None) -> None:
    """A refused send makes the command exit non-zero, so the timer's unit fails."""
    ReportSubscriptionFactory(next_due_on=TODAY)

    with pytest.raises(CommandError, match="1 report email could not be sent"):
        call_command("send_scheduled_reports", "--today=2026-10-01", stdout=StringIO())


@pytest.mark.django_db
@pytest.mark.parametrize(("role", "allowed"), role_matrix(SYSTEM_ADMIN))
def test_the_run_endpoint_is_the_system_administrators(
    api_client: APIClient, all_role_users: dict[str, User], role: str, allowed: bool
) -> None:
    """``POST /system/reports/run`` is for the system administrator alone."""
    api_client.force_login(all_role_users[role])

    response = api_client.post(RUN_URL, {"dry_run": True}, format="json")

    assert response.status_code == (200 if allowed else 403)


@pytest.mark.django_db
def test_the_run_endpoint_answers_the_run(
    api_client: APIClient, system_admin: User, today: date
) -> None:
    """A dry run through the endpoint names what it would send."""
    ReportSubscriptionFactory(recipient_email="board@example.org", next_due_on=today)
    api_client.force_login(system_admin)

    response = api_client.post(RUN_URL, {"dry_run": True}, format="json")

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
