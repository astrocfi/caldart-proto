"""Each DART's monthly roster, emailed to the people on its list ticked to receive it.

The roster is due on the first run in a month in which the DART has not been sent
one; a DART with nobody to send it to is skipped as ``no_recipients``, and a ticked
person without an address as ``no_email``.  ``GET /reports/rosters`` lists them and
``POST /reports/rosters/send`` sends every one now.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time

import pytest
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.utils import timezone
from pytest_django.fixtures import Settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import ACCOUNT_ADMIN, SYSTEM_ADMIN
from apps.cms.models import SiteSettings
from apps.darts.models import Dart
from apps.mail.models import EmailLog
from apps.reports.services import run_scheduled_reports
from caldart import audit
from tests.conftest import Golden, PdfText, audit_messages, role_matrix
from tests.factories import DartContactFactory, DartFactory, MemberProfileFactory, UserFactory

pytestmark = pytest.mark.django_db

ROSTERS_URL = "/api/v1/reports/rosters"
SEND_URL = "/api/v1/reports/rosters/send"

#: The day the runs below are made on: the first of a month.
TODAY = date(2026, 10, 1)


def at(day: date) -> datetime:
    """Noon on ``day`` in the local timezone."""
    return timezone.make_aware(datetime.combine(day, time(12)))


def ticked_dart(name: str = "Bay Area DART", **fields: object) -> Dart:
    """An active DART with one person ticked to receive the roster, and one not."""
    dart = DartFactory(name=name, **fields)
    DartContactFactory(dart=dart, name="Lee Park", email="lee@example.test", receives_roster=True)
    DartContactFactory(dart=dart, name="Ana Cruz", email="ana@example.test", receives_roster=False)
    return dart


@pytest.fixture
def named_site(settings: Settings, site_settings: SiteSettings) -> None:
    """Pin the organization name and the contact address the emails print."""
    site_settings.org_name = "The California DART Network"
    site_settings.contact_email = "info@caldart.example.org"
    site_settings.save()


# -- who is sent it -----------------------------------------------------------
def test_only_the_ticked_people_are_sent_the_roster(mailoutbox: list[EmailMessage]) -> None:
    """One email per ticked person with an address; an unticked person gets none."""
    ticked_dart()

    run_scheduled_reports(today=TODAY)

    assert [message.to for message in mailoutbox] == [["lee@example.test"]]


def test_each_ticked_person_gets_an_email_of_their_own(mailoutbox: list[EmailMessage]) -> None:
    """Two ticked people are two emails, one to each."""
    dart = ticked_dart()
    DartContactFactory(dart=dart, email="kim@example.test", receives_roster=True)

    run_scheduled_reports(today=TODAY)

    assert sorted(message.to[0] for message in mailoutbox) == [
        "kim@example.test",
        "lee@example.test",
    ]


def test_a_dart_with_nobody_ticked_is_skipped(mailoutbox: list[EmailMessage]) -> None:
    """No ticked person is ``no_recipients``, once for the DART."""
    dart = DartFactory()
    DartContactFactory(dart=dart, receives_roster=False)

    run = run_scheduled_reports(today=TODAY)

    assert run.skipped_by_reason == {"no_recipients": 1}


def test_a_dart_whose_ticked_people_have_no_address_is_skipped(
    mailoutbox: list[EmailMessage],
) -> None:
    """Ticked people without an address are nobody to send to."""
    dart = DartFactory()
    DartContactFactory(dart=dart, email="", receives_roster=True)

    run = run_scheduled_reports(today=TODAY)

    assert run.skipped_by_reason == {"no_recipients": 1}


def test_a_ticked_person_without_an_address_is_skipped_beside_the_others(
    mailoutbox: list[EmailMessage],
) -> None:
    """The roster goes to the rest, and the one without an address is ``no_email``."""
    dart = ticked_dart()
    DartContactFactory(dart=dart, email="", receives_roster=True)

    run = run_scheduled_reports(today=TODAY)

    assert (run.sent, run.skipped_by_reason) == (1, {"no_email": 1})


def test_an_inactive_dart_is_sent_nothing(mailoutbox: list[EmailMessage]) -> None:
    """A DART that has stood down is not sent a roster."""
    ticked_dart(is_active=False)

    run_scheduled_reports(today=TODAY)

    assert mailoutbox == []


# -- when it is due -----------------------------------------------------------
@pytest.mark.parametrize(
    ("sent_on", "today", "is_due"),
    [
        (None, date(2026, 10, 14), True),
        (date(2026, 9, 30), date(2026, 10, 1), True),
        (date(2026, 9, 1), date(2026, 10, 20), True),
        (date(2025, 12, 31), date(2026, 1, 1), True),
        (date(2026, 10, 1), date(2026, 10, 1), False),
        (date(2026, 10, 1), date(2026, 10, 31), False),
    ],
    ids=[
        "never-sent",
        "sent-last-day-of-last-month",
        "missed-the-first",
        "across-a-year",
        "sent-today",
        "sent-earlier-this-month",
    ],
)
def test_a_roster_is_due_once_a_month(
    mailoutbox: list[EmailMessage], sent_on: date | None, today: date, is_due: bool
) -> None:
    """Due on any run in a month the DART has not yet been sent one."""
    ticked_dart(roster_sent_at=None if sent_on is None else at(sent_on))

    run_scheduled_reports(today=today)

    assert len(mailoutbox) == (1 if is_due else 0)


def test_a_sent_roster_is_stamped(mailoutbox: list[EmailMessage], today: date) -> None:
    """``roster_sent_at`` records the send, so the month's later runs send nothing."""
    dart = ticked_dart()

    run_scheduled_reports()
    run_scheduled_reports()

    dart.refresh_from_db()
    assert dart.roster_sent_at is not None
    assert len(mailoutbox) == 1


def test_a_refused_roster_stays_due(refusing_mail_server: None) -> None:
    """A send the mail server refuses leaves the DART unstamped, for the next run."""
    dart = ticked_dart()

    run = run_scheduled_reports(today=TODAY)

    dart.refresh_from_db()
    assert run.failed == 1
    assert dart.roster_sent_at is None


def test_a_refused_roster_is_in_the_email_log(refusing_mail_server: None) -> None:
    """The refusal is logged under the roster's purpose."""
    ticked_dart()

    run_scheduled_reports(today=TODAY)

    assert EmailLog.objects.get().purpose == "dart_roster"


def test_a_dry_run_sends_and_stamps_nothing(mailoutbox: list[EmailMessage]) -> None:
    """A rehearsal names the person and the DART, and leaves the roster due."""
    dart = ticked_dart()

    run = run_scheduled_reports(today=TODAY, dry_run=True)

    dart.refresh_from_db()
    assert [(action.kind, action.member, action.detail) for action in run.actions] == [
        ("roster", "Lee Park", "Bay Area DART")
    ]
    assert mailoutbox == []
    assert dart.roster_sent_at is None


# -- what it says -------------------------------------------------------------
def test_the_roster_lists_the_darts_members_with_the_roster_columns(
    mailoutbox: list[EmailMultiAlternatives], pdf_text: PdfText
) -> None:
    """A PDF of the DART's own members, headed by the roster's eight columns."""
    dart = ticked_dart()
    MemberProfileFactory(user=UserFactory(first_name="Robin", last_name="Ashby"), dart=dart)
    MemberProfileFactory(user=UserFactory(first_name="Other", last_name="Team"))

    run_scheduled_reports(today=TODAY)

    name, content, mimetype = mailoutbox[0].attachments[0]
    text = pdf_text(bytes(content))[0]
    assert (name, mimetype) == ("caldart-members-2026-10-01.pdf", "application/pdf")
    header = ["Name", "Phone", "Email", "Certificate", "Medical", "Medical expires"]
    assert text[text.index("Name") : text.index("Name") + 6] == header
    assert "Robin Ashby" in text
    assert "Other Team" not in text


def test_the_subject_names_the_dart_and_the_day(mailoutbox: list[EmailMessage]) -> None:
    """The subject reads ``<DART name> roster (<Month D, YYYY>)``."""
    ticked_dart()

    run_scheduled_reports(today=TODAY)

    assert mailoutbox[0].subject == "Bay Area DART roster (October 1, 2026)"


def test_the_body_matches_its_recorded_text(
    mailoutbox: list[EmailMessage], named_site: None, golden: Golden
) -> None:
    """The plain-text body of a roster email, whole, counting the DART's members."""
    dart = ticked_dart()
    MemberProfileFactory(dart=dart)
    MemberProfileFactory(dart=dart)

    run_scheduled_reports(today=TODAY)

    golden("dart-roster.txt", str(mailoutbox[0].body))


# -- the endpoints ------------------------------------------------------------
@pytest.mark.parametrize(("role", "allowed"), role_matrix(ACCOUNT_ADMIN, SYSTEM_ADMIN))
def test_the_roster_list_is_the_account_administrators(
    api_client: APIClient, all_role_users: dict[str, User], role: str, allowed: bool
) -> None:
    """``GET /reports/rosters`` admits the account and system administrators alone."""
    api_client.force_login(all_role_users[role])

    assert api_client.get(ROSTERS_URL).status_code == (200 if allowed else 403)


@pytest.mark.parametrize(("role", "allowed"), role_matrix(ACCOUNT_ADMIN, SYSTEM_ADMIN))
def test_sending_the_rosters_is_the_account_administrators(
    api_client: APIClient, all_role_users: dict[str, User], role: str, allowed: bool
) -> None:
    """``POST /reports/rosters/send`` admits the same two roles."""
    api_client.force_login(all_role_users[role])

    response = api_client.post(SEND_URL, {"dry_run": True}, format="json")

    assert response.status_code == (200 if allowed else 403)


def test_the_roster_list_counts_who_receives_each(account_admin_client: APIClient) -> None:
    """One row per active DART, by name, with its recipients and its last send."""
    sent = ticked_dart(name="Alpha DART", roster_sent_at=at(date(2026, 9, 1)))
    quiet = DartFactory(name="Beta DART")
    DartContactFactory(dart=quiet, email="", receives_roster=True)
    DartFactory(name="Gone DART", is_active=False)

    rows = account_admin_client.get(ROSTERS_URL).json()

    assert rows == [
        {
            "dart_id": sent.pk,
            "name": "Alpha DART",
            "roster_recipients": 1,
            "roster_sent_at": timezone.localtime(at(date(2026, 9, 1))).isoformat(),
        },
        {"dart_id": quiet.pk, "name": "Beta DART", "roster_recipients": 0, "roster_sent_at": None},
    ]


def test_send_now_overrides_the_month(
    account_admin_client: APIClient, mailoutbox: list[EmailMessage], today: date
) -> None:
    """A DART already sent its roster this month is sent it again."""
    ticked_dart(roster_sent_at=timezone.now())

    response = account_admin_client.post(SEND_URL, {}, format="json")

    assert response.json()["sent"] == 1
    assert len(mailoutbox) == 1


def test_send_now_stamps_the_dart(
    account_admin_client: APIClient, mailoutbox: list[EmailMessage]
) -> None:
    """A roster sent by hand counts as the month's."""
    dart = ticked_dart()

    account_admin_client.post(SEND_URL, {}, format="json")

    dart.refresh_from_db()
    assert dart.roster_sent_at is not None


def test_send_now_as_a_dry_run_names_the_people(
    account_admin_client: APIClient, mailoutbox: list[EmailMessage]
) -> None:
    """A rehearsal answers who would be sent the roster, and sends nothing."""
    ticked_dart()

    response = account_admin_client.post(SEND_URL, {"dry_run": True}, format="json")

    assert response.json()["actions"] == [
        {
            "kind": "roster",
            "member": "Lee Park",
            "email": "lee@example.test",
            "on": None,
            "amount_cents": None,
            "detail": "Bay Area DART",
        }
    ]
    assert mailoutbox == []


def test_send_now_writes_one_audit_line_per_dart(
    account_admin_client: APIClient,
    account_admin: User,
    mailoutbox: list[EmailMessage],
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """Each DART's line names the caller, the DART and its own counts."""
    dart = ticked_dart()

    account_admin_client.post(SEND_URL, {}, format="json")

    assert audit_messages(audit_log, logging.INFO) == [
        f"action={audit.REPORT_SEND} actor={account_admin.pk} target={dart.pk} "
        "kind=roster dry_run=false sent=1 skipped=0 failed=0"
    ]
