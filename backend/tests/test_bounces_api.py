"""The bounce check from the portal, and what the email log shows of a bounce.

``POST /system/bounces/run`` runs ``apps.mail.bounces.check_bounces`` for a system
administrator; ``GET /system/emails`` and the ``emails`` report filter on the
``bounced`` status and carry when and why a message bounced; ``manage.py
check_bounces`` prints the same run.  See ``docs/developer/api-system.rst``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from pytest_django import Settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import SYSTEM_ADMIN
from apps.mail.models import EmailLog, EmailStatus
from tests.conftest import BounceReport, FakeMailbox, audit_messages, read_csv, role_matrix
from tests.factories import EmailLogFactory, UserFactory

pytestmark = pytest.mark.django_db

RUN_URL = "/api/v1/system/bounces/run"
LIST_URL = "/api/v1/system/emails"
CSV_URL = "/api/v1/reports/emails/export.csv"

DETAIL = "5.1.1 550 5.1.1 User unknown"
BOUNCED_AT = datetime(2026, 10, 1, 18, 0, tzinfo=UTC)


@pytest.fixture
def sent(db: None) -> EmailLog:
    """A message sent to Dana Doe at ``gone@example.com`` with the report's Message-ID."""
    user = UserFactory(email="gone@example.com", first_name="Dana", last_name="Doe")
    return EmailLogFactory(user=user, message_id="<original.1@caldart.example.org>")


@pytest.fixture
def bounced_row(db: None) -> EmailLog:
    """A message the bounce check has already marked bounced."""
    return EmailLogFactory(status=EmailStatus.BOUNCED, bounced_at=BOUNCED_AT, bounce_detail=DETAIL)


# --------------------------------------------------------------------------
# POST /system/bounces/run
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("role", "allowed"), role_matrix(SYSTEM_ADMIN))
def test_only_a_system_administrator_runs_the_bounce_check(
    api_client: APIClient,
    all_role_users: dict[str, User],
    fake_mailbox: FakeMailbox,
    role: str,
    allowed: bool,
) -> None:
    """Reading the bounce mailbox is operations work, refused to every other role."""
    fake_mailbox()
    api_client.force_login(all_role_users[role])

    response = api_client.post(RUN_URL, {"dry_run": True}, format="json")

    assert response.status_code == (200 if allowed else 403)


def test_the_run_answers_its_counts_and_actions(
    system_admin_client: APIClient,
    sent: EmailLog,
    fake_mailbox: FakeMailbox,
    bounce_report: BounceReport,
) -> None:
    """The answer is ``{enabled, bounced, unmatched, ignored, actions}``."""
    fake_mailbox(bounce_report("hard_bounce"), bounce_report("auto_reply"))

    body = system_admin_client.post(RUN_URL, {"dry_run": True}, format="json").json()

    assert body == {
        "enabled": True,
        "bounced": 1,
        "unmatched": 0,
        "ignored": 1,
        "skipped": 0,
        "actions": [
            {
                "kind": "bounced",
                "member": "Dana Doe",
                "email": "gone@example.com",
                "on": sent.sent_at.astimezone().date().isoformat(),
                "amount_cents": None,
                "detail": (
                    "5.1.1 550 5.1.1 <gone@example.com>: Recipient address rejected: "
                    "User unknown in virtual mailbox table"
                ),
            }
        ],
    }


def test_a_run_with_no_body_is_live(
    system_admin_client: APIClient,
    sent: EmailLog,
    fake_mailbox: FakeMailbox,
    bounce_report: BounceReport,
) -> None:
    """``dry_run`` defaults to false, so the row is marked."""
    fake_mailbox(bounce_report("hard_bounce"))

    system_admin_client.post(RUN_URL, {}, format="json")

    sent.refresh_from_db()
    assert sent.status == EmailStatus.BOUNCED


def test_the_run_records_the_caller_as_its_actor(
    system_admin_client: APIClient,
    system_admin: User,
    fake_mailbox: FakeMailbox,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """The ``bounces.run`` audit line names the system administrator who pressed it."""
    fake_mailbox()

    system_admin_client.post(RUN_URL, {"dry_run": False}, format="json")

    assert audit_messages(audit_log) == [
        f"action=bounces.run actor={system_admin.pk} target=- dry_run=false enabled=true "
        "bounced=0 unmatched=0 ignored=0 skipped=0"
    ]


def test_with_checking_off_the_run_says_so(
    system_admin_client: APIClient, settings: Settings
) -> None:
    """An empty ``BOUNCE_IMAP_URL`` answers ``enabled`` false and nothing counted."""
    settings.BOUNCE_IMAP_URL = ""

    body = system_admin_client.post(RUN_URL, {}, format="json").json()

    assert body == {
        "enabled": False,
        "bounced": 0,
        "unmatched": 0,
        "ignored": 0,
        "skipped": 0,
        "actions": [],
    }


def test_an_unreachable_mailbox_is_a_400_naming_the_host(
    system_admin_client: APIClient, fake_mailbox: FakeMailbox
) -> None:
    """The refusal says which server could not be reached, and never the password."""
    fake_mailbox(refuse=TimeoutError("timed out"))

    response = system_admin_client.post(RUN_URL, {}, format="json")

    assert (response.status_code, response.json()) == (
        400,
        {"detail": "Could not reach the bounce mailbox at imap.example.org: timed out"},
    )


# --------------------------------------------------------------------------
# manage.py check_bounces
# --------------------------------------------------------------------------
def test_the_command_prints_the_run(
    sent: EmailLog, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """The command prints the counts, one line per bounce, and a closing tally."""
    fake_mailbox(bounce_report("hard_bounce"))
    out = StringIO()

    call_command("check_bounces", "--dry-run", stdout=out)

    assert out.getvalue().splitlines()[-1] == "would mark 1 bounced, 0 unmatched, 0 ignored"


def test_the_command_with_checking_off_says_so_and_succeeds() -> None:
    """With no mailbox configured the command prints one line and exits cleanly."""
    out = StringIO()

    call_command("check_bounces", stdout=out)

    assert out.getvalue() == "Bounce checking is off: BOUNCE_IMAP_URL is not set.\n"


def test_the_command_fails_when_the_mailbox_cannot_be_reached(fake_mailbox: FakeMailbox) -> None:
    """An unreachable mailbox exits non-zero, so the timer's unit shows ``failed``."""
    fake_mailbox(refuse=ConnectionRefusedError(111, "Connection refused"))

    with pytest.raises(CommandError, match=r"^Could not reach the bounce mailbox at imap"):
        call_command("check_bounces")


# --------------------------------------------------------------------------
# The email log
# --------------------------------------------------------------------------
def test_the_email_log_filters_on_bounced(
    system_admin_client: APIClient, bounced_row: EmailLog
) -> None:
    """``?status=bounced`` lists the bounced messages alone."""
    EmailLogFactory()

    rows = system_admin_client.get(LIST_URL, {"status": "bounced"}).json()["results"]

    assert [row["id"] for row in rows] == [bounced_row.pk]


def test_an_email_log_row_carries_its_bounce(
    system_admin_client: APIClient, bounced_row: EmailLog
) -> None:
    """A bounced row answers its status, when it bounced, and the report's detail."""
    row = system_admin_client.get(LIST_URL).json()["results"][0]

    assert (row["status"], row["bounced_at"], row["bounce_detail"]) == (
        "bounced",
        "2026-10-01T11:00:00-07:00",
        DETAIL,
    )


def test_the_email_log_report_prints_the_bounce(
    system_admin_client: APIClient, bounced_row: EmailLog
) -> None:
    """The ``bounced_at`` and ``bounce_detail`` columns print the local time and why."""
    rows = read_csv(
        system_admin_client.get(CSV_URL, {"columns": "status,bounced_at,bounce_detail"})
    )

    assert rows == [["Status", "Bounced", "Bounce detail"], ["Bounced", "10/01/2026 11:00", DETAIL]]


def test_the_email_log_report_leaves_the_bounce_blank_for_a_sent_message(
    system_admin_client: APIClient,
) -> None:
    """A message that did not bounce has empty bounce cells."""
    EmailLogFactory()

    rows = read_csv(system_admin_client.get(CSV_URL, {"columns": "bounced_at,bounce_detail"}))

    assert rows == [["Bounced", "Bounce detail"], ["", ""]]
