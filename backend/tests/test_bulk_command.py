"""``manage.py send_bulk_emails`` and ``POST /system/bulk-email/run``: one sender run.

The timer runs the command every minute; **Run now** on the Scheduled page runs the same
sender in the request.  Both report what the run did.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from django.core import mail
from django.core.management import call_command
from django.db import connection
from pytest_django import Settings
from rest_framework.test import APIClient

from apps.accounts.roles import SYSTEM_ADMIN
from apps.bulk_email import job
from apps.bulk_email.models import BulkEmail, BulkEmailStatus
from tests.conftest import audit_messages, role_matrix
from tests.factories import BulkEmailFactory, add_to_batch, make_person

if TYPE_CHECKING:
    from apps.accounts.models import User

pytestmark = pytest.mark.django_db

RUN_URL = "/api/v1/system/bulk-email/run"

#: The systemd units under ``deploy/systemd/``.
SYSTEMD_DIR = Path(__file__).resolve().parents[2] / "deploy" / "systemd"

#: A start time long past, so every queued email in these tests is due.
PAST = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _no_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    """Take the pacing's pause out, so a run sends at once."""
    monkeypatch.setattr(job, "sleep", lambda seconds: None)


@pytest.fixture
def due(management: User) -> BulkEmail:
    """A queued email to Ann Able, due already."""
    bulk = BulkEmailFactory(
        sender=management, subject="Hangar day", status=BulkEmailStatus.QUEUED, start_at=PAST
    )
    add_to_batch(bulk, make_person("ann@example.test", "Ann", "Able"))
    return bulk


@pytest.fixture
def another_run_working() -> Iterator[None]:
    """Hold the sender's lock from a second database session, as a run at work does."""
    second = connection.copy()
    try:
        with second.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_lock(%s)", [job.SENDER_LOCK_KEY])
        yield
    finally:
        # Closing the session releases its lock.
        second.close()


def run_command() -> str:
    """Run ``send_bulk_emails`` and return what it printed."""
    out = StringIO()
    call_command("send_bulk_emails", stdout=out)
    return out.getvalue()


# --------------------------------------------------------------------------
# The command
# --------------------------------------------------------------------------
def test_the_command_sends_every_due_email(due: BulkEmail) -> None:
    """One run sends the copy and marks the email sent."""
    run_command()
    due.refresh_from_db()
    assert (due.status, [message.to[0] for message in mail.outbox]) == (
        BulkEmailStatus.SENT,
        ["ann@example.test"],
    )


def test_the_command_prints_its_counts_and_each_email_by_id(due: BulkEmail) -> None:
    """The summary counts the run and names each email by its id, and nobody by name."""
    lines = run_command().splitlines()
    assert lines == [
        "emails           1",
        "sent             1",
        "failed           0",
        "skipped          0",
        f"bulk_email {due.pk}: sent 1, failed 0",
        "sent 1, failed 0, skipped 0 across 1 bulk email(s)",
    ]


def test_the_command_with_nothing_due_sends_nothing(management: User) -> None:
    """A draft is not the sender's business."""
    BulkEmailFactory(sender=management)
    output = run_command()
    assert (len(mail.outbox), output.splitlines()[0]) == (0, "emails           0")


def test_the_command_does_nothing_while_another_run_works(
    due: BulkEmail, another_run_working: None
) -> None:
    """A second run says so and leaves the email for the first."""
    assert (run_command().splitlines(), len(mail.outbox)) == ([job.BUSY_MESSAGE], 0)


def test_running_twice_sends_each_copy_once(due: BulkEmail) -> None:
    """A second run finds nothing left to send."""
    run_command()
    run_command()
    assert len(mail.outbox) == 1


# --------------------------------------------------------------------------
# Run now
# --------------------------------------------------------------------------
def test_run_now_answers_what_the_run_did(system_admin_client: APIClient, due: BulkEmail) -> None:
    """The answer counts the run and lists each copy as an action."""
    assert system_admin_client.post(RUN_URL).json() == {
        "busy": False,
        "emails": 1,
        "sent": 1,
        "failed": 0,
        "skipped": 0,
        "out_of_time": False,
        "remaining": 0,
        "actions": [
            {
                "kind": "sent",
                "member": "Ann Able",
                "email": "ann@example.test",
                "on": None,
                "amount_cents": None,
                "detail": "Hangar day",
            }
        ],
    }


def test_run_now_writes_one_audit_line(
    system_admin_client: APIClient,
    system_admin: User,
    due: BulkEmail,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """``bulk_email.run`` names the system administrator and the counts."""
    system_admin_client.post(RUN_URL)
    assert (
        f"action=bulk_email.run actor={system_admin.pk} target=- busy=false emails=1 "
        "sent=1 failed=0 skipped=0"
    ) in audit_messages(audit_log)


def test_run_now_says_when_another_run_is_working(
    system_admin_client: APIClient, due: BulkEmail, another_run_working: None
) -> None:
    """``busy`` is true and nothing was sent."""
    body = system_admin_client.post(RUN_URL).json()
    assert (body["busy"], body["emails"], len(mail.outbox)) == (True, 0, 0)


@pytest.mark.parametrize(("role", "allowed"), role_matrix(SYSTEM_ADMIN))
def test_only_a_system_administrator_runs_the_sender(
    api_client: APIClient, all_role_users: dict[str, User], role: str, allowed: bool
) -> None:
    """**Run now** is the system administrator's alone."""
    api_client.force_login(all_role_users[role])
    assert api_client.post(RUN_URL).status_code == (200 if allowed else 403)


# --------------------------------------------------------------------------
# The timer
# --------------------------------------------------------------------------
def test_the_service_runs_the_command_with_no_time_limit() -> None:
    """The oneshot runs ``send_bulk_emails``, and a long send is never cut short."""
    service = (SYSTEMD_DIR / "caldart-bulk-email.service").read_text()
    assert "manage.py send_bulk_emails" in service
    assert "Type=oneshot" in service
    assert "TimeoutStartSec=0" in service


def test_the_timer_fires_every_minute_on_the_minute() -> None:
    """Every minute, to the second, with no randomized delay to spread it."""
    timer = (SYSTEMD_DIR / "caldart-bulk-email.timer").read_text()
    assert "OnCalendar=*-*-* *:*:00" in timer
    assert "AccuracySec=1s" in timer
    assert "RandomizedDelaySec" not in timer


def test_run_now_stops_within_its_budget_and_leaves_the_rest_for_the_timer(
    system_admin_client: APIClient,
    management: User,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """At 30 a minute, a budget of three seconds sends two copies and leaves the third."""
    settings.BULK_EMAIL_RATE_PER_MINUTE = 30
    clock = [0.0]

    def pause(seconds: float) -> None:
        clock[0] += seconds

    monkeypatch.setattr(job, "sleep", pause)
    monkeypatch.setattr(job, "monotonic", lambda: clock[0])
    monkeypatch.setattr(job, "REQUEST_BUDGET_SECONDS", 3)
    monkeypatch.setattr("apps.bulk_email.api.sender.REQUEST_BUDGET_SECONDS", 3)
    bulk = BulkEmailFactory(sender=management, status=BulkEmailStatus.QUEUED, start_at=PAST)
    add_to_batch(
        bulk,
        make_person("ann@example.test", "Ann", "Able"),
        make_person("bea@example.test", "Bea", "Bell"),
        make_person("cy@example.test", "Cy", "Cole"),
    )
    body = system_admin_client.post(RUN_URL).json()
    bulk.refresh_from_db()
    assert (body["sent"], body["out_of_time"], body["remaining"], bulk.status) == (
        2,
        True,
        1,
        BulkEmailStatus.SENDING,
    )
