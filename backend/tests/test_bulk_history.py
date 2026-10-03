"""The sent bulk emails: the Sent list, one send's detail, and its results as a CSV.

The Sent list holds every email sending, sent, or stopped, the most recently started
first.  Each send keeps every person in its batch with what became of their copy,
whatever happens to the account later.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from rest_framework.test import APIClient

from apps.accounts.roles import MANAGEMENT, SYSTEM_ADMIN
from apps.bulk_email import job
from apps.bulk_email.models import BulkEmail, BulkEmailStatus, RecipientStatus
from apps.mail.purposes import purpose_label
from tests.conftest import read_csv, role_matrix
from tests.factories import BulkEmailFactory, DartFactory, add_to_batch, make_person

if TYPE_CHECKING:
    from apps.accounts.models import User

pytestmark = pytest.mark.django_db

SENT_URL = "/api/v1/bulk-email/sent"
PAST = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _no_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    """Take the pacing's pause out, so a run sends at once."""
    monkeypatch.setattr(job, "sleep", lambda seconds: None)


@pytest.fixture
def sent(management: User) -> BulkEmail:
    """An email sent to Ann Able, with Gil Gone, deactivated, skipped."""
    team = DartFactory(name="Marin DART")
    bulk = BulkEmailFactory(
        sender=management, subject="Hangar day", status=BulkEmailStatus.QUEUED, start_at=PAST
    )
    add_to_batch(
        bulk,
        make_person("ann@example.test", "Ann", "Able", dart=team),
        make_person("gil@example.test", "Gil", "Gone", dart=team, is_active=False),
    )
    job.run_sender()
    bulk.refresh_from_db()
    return bulk


def test_the_sent_list_holds_started_emails_alone(
    management_client: APIClient, management: User, sent: BulkEmail
) -> None:
    """Drafts and queued emails are on the Drafts & scheduled list instead."""
    BulkEmailFactory(sender=management, subject="Draft")
    BulkEmailFactory(sender=management, subject="Queued", status=BulkEmailStatus.QUEUED)
    stopped = BulkEmailFactory(
        sender=management,
        status=BulkEmailStatus.STOPPED,
        started_at=datetime(2026, 2, 1, tzinfo=UTC),
    )
    ids = [row["id"] for row in management_client.get(SENT_URL).json()]
    assert ids == [sent.pk, stopped.pk]


def test_the_sent_list_puts_the_latest_start_first(
    management_client: APIClient, management: User
) -> None:
    """The most recently started email leads."""
    older = BulkEmailFactory(
        sender=management, status=BulkEmailStatus.SENT, started_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    newer = BulkEmailFactory(
        sender=management, status=BulkEmailStatus.SENT, started_at=datetime(2026, 3, 1, tzinfo=UTC)
    )
    assert [row["id"] for row in management_client.get(SENT_URL).json()] == [newer.pk, older.pk]


def test_a_sent_row_carries_its_counts_and_sender(
    management_client: APIClient, sent: BulkEmail
) -> None:
    """One line per send: the subject, the sender, and what became of the copies."""
    row = management_client.get(SENT_URL).json()[0]
    assert {
        key: row[key]
        for key in (
            "subject",
            "status",
            "sender",
            "sent_count",
            "failed_count",
            "skipped_count",
            "batch_count",
            "remaining",
        )
    } == {
        "subject": "Hangar day",
        "status": "sent",
        "sender": "Hollis Grant",
        "sent_count": 1,
        "failed_count": 0,
        "skipped_count": 1,
        "batch_count": 2,
        "remaining": 0,
    }


def test_a_deleted_sender_reads_as_blank(
    management_client: APIClient, sent: BulkEmail, management: User
) -> None:
    """The send stays when the sender's account goes; its sender is blank."""
    BulkEmail.objects.filter(pk=sent.pk).update(sender=None)
    assert management_client.get(SENT_URL).json()[0]["sender"] == ""


def test_a_recipient_whose_account_is_gone_keeps_their_row(
    management_client: APIClient, sent: BulkEmail
) -> None:
    """The row keeps the name and address the copy went to."""
    sent.recipients.get(email="ann@example.test").user.delete()  # type: ignore[union-attr]
    rows = management_client.get(f"/api/v1/bulk-email/{sent.pk}/batch").json()["rows"]
    assert [(row["user_id"], row["status"]) for row in rows if row["name"] == "Ann Able"] == [
        (None, "sent")
    ]


def test_a_send_s_results_download_as_a_csv(management_client: APIClient, sent: BulkEmail) -> None:
    """One line per person: name, address, kind, DART, result, reason, and email type."""
    response = management_client.get(f"/api/v1/bulk-email/{sent.pk}/recipients.csv")
    assert read_csv(response) == [
        ["Name", "Email", "Kind", "DART", "Result", "Reason", "Email type"],
        ["Ann Able", "ann@example.test", "Friend", "Marin DART", "Sent", "", "Operational"],
        [
            "Gil Gone",
            "gil@example.test",
            "Friend",
            "Marin DART",
            "Skipped",
            "Account deactivated",
            "Operational",
        ],
    ]


def test_a_send_s_csv_is_named_for_the_send(management_client: APIClient, sent: BulkEmail) -> None:
    """The download is named ``caldart-bulk-email-<id>-recipients.csv``."""
    response = management_client.get(f"/api/v1/bulk-email/{sent.pk}/recipients.csv")
    assert response["Content-Disposition"] == (
        f'attachment; filename="caldart-bulk-email-{sent.pk}-recipients.csv"'
    )


def test_a_stopped_copy_reads_not_sent_in_the_csv(
    management_client: APIClient, sent: BulkEmail
) -> None:
    """A copy a stop kept back reads *Not sent (stopped)* with who stopped it."""
    sent.recipients.filter(email="ann@example.test").update(
        status=RecipientStatus.STOPPED, reason="Stopped by Hollis Grant"
    )
    rows = read_csv(management_client.get(f"/api/v1/bulk-email/{sent.pk}/recipients.csv"))
    assert rows[1][4:] == ["Not sent (stopped)", "Stopped by Hollis Grant", "Operational"]


def test_the_bulk_email_purpose_has_a_label() -> None:
    """The email log names every copy *Bulk email*."""
    assert purpose_label("bulk_email") == "Bulk email"


@pytest.mark.parametrize(("role", "allowed"), role_matrix(MANAGEMENT, SYSTEM_ADMIN))
@pytest.mark.parametrize("path", ["/sent", "/{id}", "/{id}/recipients.csv", "/{id}/batch"])
def test_only_management_reads_the_history(
    api_client: APIClient,
    all_role_users: dict[str, User],
    sent: BulkEmail,
    role: str,
    allowed: bool,
    path: str,
) -> None:
    """The Sent list, one send, and its CSV answer CalDART management alone."""
    api_client.force_login(all_role_users[role])
    response = api_client.get("/api/v1/bulk-email" + path.format(id=sent.pk))
    assert response.status_code == (200 if allowed else 403)


@pytest.mark.parametrize(("role", "allowed"), role_matrix(MANAGEMENT, SYSTEM_ADMIN))
@pytest.mark.parametrize("action", ["stop", "resume"])
def test_only_management_stops_and_resumes(
    api_client: APIClient,
    all_role_users: dict[str, User],
    sent: BulkEmail,
    role: str,
    allowed: bool,
    action: str,
) -> None:
    """Stop and Send the rest are CalDART management's; a finished send answers 409."""
    api_client.force_login(all_role_users[role])
    response = api_client.post(f"/api/v1/bulk-email/{sent.pk}/{action}")
    assert response.status_code == (409 if allowed else 403)
