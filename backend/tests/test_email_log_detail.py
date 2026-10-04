"""One email of the log, opened on its own: ``GET /system/emails/{id}``.

The Sent emails screen opens a row to show everything the log holds about the message:
who it went to, its subject and purpose, when it went, what became of it, and the page
it belongs to.  Like the list, it is a system administrator's alone.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import SYSTEM_ADMIN
from apps.mail.models import EmailLog, EmailStatus
from tests.conftest import role_matrix
from tests.factories import EmailLogFactory, UserFactory

pytestmark = pytest.mark.django_db

#: When the logged message went.
SENT_AT = datetime(2026, 9, 20, 16, 30, tzinfo=UTC)


def detail_url(row: EmailLog) -> str:
    """The detail URL of ``row``."""
    return f"/api/v1/system/emails/{row.pk}"


@pytest.mark.parametrize(("role", "allowed"), role_matrix(SYSTEM_ADMIN))
def test_only_a_system_administrator_opens_an_email(
    api_client: APIClient, all_role_users: dict[str, User], role: str, allowed: bool
) -> None:
    """Every other role is refused with a 403."""
    row = EmailLogFactory()
    api_client.force_login(all_role_users[role])
    assert api_client.get(detail_url(row)).status_code == (200 if allowed else 403)


def test_a_signed_out_visitor_cannot_open_an_email(api_client: APIClient) -> None:
    """Without a session the answer is a 401."""
    assert api_client.get(detail_url(EmailLogFactory())).status_code == 401


def test_an_unknown_email_is_a_404(system_admin_client: APIClient) -> None:
    """An id no row has answers 404."""
    assert system_admin_client.get("/api/v1/system/emails/999999").status_code == 404


def test_the_email_reads_as_its_row_in_the_list(system_admin_client: APIClient) -> None:
    """The detail carries every field the list row does, with the same values."""
    user = UserFactory(email="marta@example.test", first_name="Marta", last_name="Reyes")
    row = EmailLogFactory(
        user=user,
        purpose="password_reset",
        subject="Reset your CalDART password",
        sent_at=SENT_AT,
        status=EmailStatus.FAILED,
        error="SMTPRecipientsRefused",
    )
    data = system_admin_client.get(detail_url(row)).json()
    assert data == {
        "id": row.pk,
        "to_email": "marta@example.test",
        "user_id": user.pk,
        "user_name": "Marta Reyes",
        "purpose": "password_reset",
        "purpose_label": "Password reset",
        "subject": "Reset your CalDART password",
        "sent_at": "2026-09-20T09:30:00-07:00",
        "status": "failed",
        "error": "SMTPRecipientsRefused",
        "attachments": "",
        "bounced_at": None,
        "bounce_detail": "",
        "link": "",
    }
