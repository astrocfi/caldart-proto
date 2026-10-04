"""A queued bulk email whose type changes goes back to a draft.

Who is skipped as opted out follows the type, so the count the sender confirmed no
longer holds once the type changes: the email returns to the drafts with its schedule
cleared, exactly as a change to its batch returns it, whether the type was changed by
hand (``PATCH``) or by **Start from a template**.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from rest_framework.test import APIClient

from apps.accounts.roles import MANAGEMENT
from apps.bulk_email.models import BulkEmail, BulkEmailStatus
from tests.conftest import audit_messages
from tests.factories import BulkEmailFactory, EmailTemplateFactory, EmailTypeFactory

if TYPE_CHECKING:
    from apps.accounts.models import User
    from apps.mail.models import EmailType

pytestmark = pytest.mark.django_db

START = datetime(2027, 1, 4, 16, 0, tzinfo=UTC)


@pytest.fixture
def mission() -> EmailType:
    """A second type CalDART management may send."""
    return EmailTypeFactory(name="Mission Calls", sender_roles=[MANAGEMENT])


@pytest.fixture
def queued(management: User) -> BulkEmail:
    """An Operational email scheduled to start on 01/04/2027, its count confirmed."""
    return BulkEmailFactory(
        sender=management,
        status=BulkEmailStatus.QUEUED,
        start_at=START,
        scheduled=True,
        confirm_count=60,
    )


def schedule(bulk: BulkEmail) -> tuple[str, datetime | None, bool, int | None]:
    """``bulk``'s status, start time, scheduled flag, and confirmed count, read afresh."""
    bulk.refresh_from_db()
    return (bulk.status, bulk.start_at, bulk.scheduled, bulk.confirm_count)


def change_type(client: APIClient, bulk: BulkEmail, how: str, email_type: EmailType) -> int:
    """Change ``bulk``'s type by ``patch`` or ``template``; return the status code."""
    if how == "patch":
        response = client.patch(
            f"/api/v1/bulk-email/{bulk.pk}", {"email_type": email_type.pk}, format="json"
        )
    else:
        template = EmailTemplateFactory(subject=bulk.subject, body=bulk.body, email_type=email_type)
        response = client.post(
            f"/api/v1/bulk-email/{bulk.pk}/apply-template",
            {"template": template.pk},
            format="json",
        )
    return response.status_code


@pytest.mark.parametrize("how", ["patch", "template"])
def test_a_type_change_takes_a_queued_email_back_to_a_draft(
    management_client: APIClient, queued: BulkEmail, mission: EmailType, how: str
) -> None:
    """The schedule and the confirmed count are cleared."""
    assert change_type(management_client, queued, how, mission) == 200
    assert schedule(queued) == (BulkEmailStatus.DRAFT, None, False, None)


@pytest.mark.parametrize("how", ["patch", "template"])
def test_a_type_change_records_why_the_email_went_back(
    management_client: APIClient,
    queued: BulkEmail,
    mission: EmailType,
    management: User,
    audit_log: pytest.LogCaptureFixture,
    how: str,
) -> None:
    """One ``bulk_email.cancel`` line names the reason ``type_changed``."""
    change_type(management_client, queued, how, mission)
    assert audit_messages(audit_log) == [
        f"action=bulk_email.cancel actor={management.pk} target={queued.pk} reason=type_changed"
    ]


@pytest.mark.parametrize("how", ["patch", "template"])
def test_the_same_type_leaves_a_queued_email_scheduled(
    management_client: APIClient, queued: BulkEmail, how: str
) -> None:
    """Choosing the type the email has already changes nothing about its schedule."""
    assert queued.email_type is not None
    change_type(management_client, queued, how, queued.email_type)
    assert schedule(queued) == (BulkEmailStatus.QUEUED, START, True, 60)


def test_a_wording_change_leaves_a_queued_email_scheduled(
    management_client: APIClient, queued: BulkEmail
) -> None:
    """Only the type, among the message's fields, takes it back to a draft."""
    management_client.patch(
        f"/api/v1/bulk-email/{queued.pk}", {"subject": "New subject"}, format="json"
    )
    assert schedule(queued) == (BulkEmailStatus.QUEUED, START, True, 60)
