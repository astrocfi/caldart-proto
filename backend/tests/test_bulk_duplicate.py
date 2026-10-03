"""**Duplicate**: a fresh draft copied from a bulk email, sent or not.

The copy is the caller's own draft with the original's subject, message, and type.
Its batch is empty unless the caller asks for the people too, who then join as one
add, their skip reasons worked out as they are now.  The original is not touched.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from rest_framework.test import APIClient

from apps.accounts.roles import MANAGEMENT, MEMBER, SYSTEM_ADMIN
from apps.bulk_email import batch, job
from apps.bulk_email.models import BulkEmail, BulkEmailStatus, RecipientStatus
from apps.bulk_email.templates import duplicate
from tests.conftest import role_matrix
from tests.factories import (
    BulkEmailFactory,
    EmailTypeFactory,
    UserFactory,
    add_to_batch,
    make_person,
)

if TYPE_CHECKING:
    from apps.accounts.models import User

pytestmark = pytest.mark.django_db

PAST = datetime(2026, 1, 1, tzinfo=UTC)


def duplicate_url(bulk: BulkEmail) -> str:
    """``/api/v1/bulk-email/{id}/duplicate`` for ``bulk``."""
    return f"/api/v1/bulk-email/{bulk.pk}/duplicate"


@pytest.fixture(autouse=True)
def _no_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    """Take the pacing's pause out, so a run sends at once."""
    monkeypatch.setattr(job, "sleep", lambda seconds: None)


@pytest.fixture
def other_manager() -> User:
    """Another member of CalDART management, who sent the original."""
    return UserFactory(email="grace@example.test", roles=[MEMBER, MANAGEMENT])


@pytest.fixture
def sent(other_manager: User) -> BulkEmail:
    """An email another manager sent to Ann and Bob."""
    bulk = BulkEmailFactory(
        sender=other_manager,
        subject="Hangar day",
        body='<p>Dear {first_name},</p><p><img src="https://e.test/a.png" alt="Hangar"></p>',
        status=BulkEmailStatus.QUEUED,
        start_at=PAST,
    )
    add_to_batch(
        bulk,
        make_person("ann@example.test", "Ann", "Able"),
        make_person("bob@example.test", "Bob", "Burns"),
    )
    job.run_sender()
    bulk.refresh_from_db()
    return bulk


def test_a_duplicate_is_a_draft_with_the_originals_content(
    management_client: APIClient, sent: BulkEmail
) -> None:
    """The subject, the message with its images, and the type are copied."""
    response = management_client.post(duplicate_url(sent), {}, format="json")
    assert response.status_code == 201
    body = response.json()
    assert (body["status"], body["subject"], body["body"], body["email_type"]) == (
        "draft",
        "Hangar day",
        sent.body,
        sent.email_type_id,
    )


def test_a_duplicate_belongs_to_whoever_pressed_it(
    management_client: APIClient, management: User, sent: BulkEmail
) -> None:
    """The draft's sender is the caller, not the original's sender."""
    copy_id = management_client.post(duplicate_url(sent), {}, format="json").json()["id"]
    assert BulkEmail.objects.get(pk=copy_id).sender == management


def test_a_duplicate_starts_with_an_empty_batch(
    management_client: APIClient, sent: BulkEmail
) -> None:
    """Without the option the batch is empty."""
    body = management_client.post(duplicate_url(sent), {}, format="json").json()
    assert body["batch_count"] == 0


def test_a_duplicate_is_a_fresh_draft_even_beside_an_empty_one(
    management: User, sent: BulkEmail
) -> None:
    """Duplicate never hands back the caller's empty draft, as Compose does."""
    empty = BulkEmailFactory(sender=management, subject="", body="")
    assert duplicate(sent, actor=management, copy_recipients=False).pk != empty.pk


def test_copying_the_recipients_copies_the_batch_as_one_add(
    management_client: APIClient, sent: BulkEmail
) -> None:
    """The people join as one add, named after the original."""
    copy_id = management_client.post(
        duplicate_url(sent), {"copy_recipients": True}, format="json"
    ).json()["id"]
    body = management_client.get(f"/api/v1/bulk-email/{copy_id}/batch").json()
    assert [(add["label"], add["added_count"]) for add in body["adds"]] == [
        ('Copied from "Hangar day"', 2)
    ]
    assert [(row["email"], row["status"]) for row in body["rows"]] == [
        ("ann@example.test", "batched"),
        ("bob@example.test", "batched"),
    ]


def test_copied_recipients_get_the_skip_reasons_of_now(management: User, sent: BulkEmail) -> None:
    """Somebody deactivated since the original went is skipped in the copy."""
    bob = sent.recipients.get(email="bob@example.test").user
    assert bob is not None
    bob.is_active = False
    bob.save()
    copy = duplicate(sent, actor=management, copy_recipients=True)
    assert [(row.recipient.email, row.reason) for row in batch.batch_rows(copy)] == [
        ("ann@example.test", ""),
        ("bob@example.test", batch.SKIP_DEACTIVATED),
    ]


def test_copied_recipients_carry_their_details_as_they_are_now(
    management: User, sent: BulkEmail
) -> None:
    """A changed address is the copy's, not the address the original went to."""
    ann = sent.recipients.get(email="ann@example.test").user
    assert ann is not None
    ann.email = "ann.able@example.test"
    ann.save()
    copy = duplicate(sent, actor=management, copy_recipients=True)
    assert sorted(copy.recipients.values_list("email", flat=True)) == [
        "ann.able@example.test",
        "bob@example.test",
    ]


def test_a_deleted_account_is_not_copied(management: User, sent: BulkEmail) -> None:
    """Only people whose account still exists join the copy's batch."""
    bob = sent.recipients.get(email="bob@example.test").user
    assert bob is not None
    bob.delete()
    copy = duplicate(sent, actor=management, copy_recipients=True)
    assert list(copy.recipients.values_list("email", flat=True)) == ["ann@example.test"]


def test_duplicating_leaves_the_original_unchanged(
    management_client: APIClient, sent: BulkEmail
) -> None:
    """The original keeps its status, its counts, and its people."""
    before = (sent.status, sent.sent_count, sent.subject, sent.updated_at)
    management_client.post(duplicate_url(sent), {"copy_recipients": True}, format="json")
    sent.refresh_from_db()
    assert (sent.status, sent.sent_count, sent.subject, sent.updated_at) == before
    assert list(sent.recipients.values_list("status", flat=True)) == [
        RecipientStatus.SENT,
        RecipientStatus.SENT,
    ]


def test_a_type_the_caller_may_not_send_is_left_unchosen(
    management: User, other_manager: User
) -> None:
    """The copy has no type when the caller may not send the original's."""
    board = EmailTypeFactory(name="Board", sender_roles=[])
    original = BulkEmailFactory(sender=other_manager, email_type=board)
    assert duplicate(original, actor=management, copy_recipients=False).email_type is None


def test_a_draft_can_be_duplicated_too(management: User) -> None:
    """Any email the caller may open can be copied, not only a sent one."""
    draft = BulkEmailFactory(sender=management, subject="Work in progress")
    assert duplicate(draft, actor=management, copy_recipients=False).subject == ("Work in progress")


def test_duplicating_an_unknown_email_is_not_found(management_client: APIClient) -> None:
    """An email nobody has is a 404."""
    assert management_client.post("/api/v1/bulk-email/9999/duplicate", {}).status_code == 404


@pytest.mark.parametrize(("role", "allowed"), role_matrix(MANAGEMENT, SYSTEM_ADMIN))
def test_only_a_bulk_email_sender_may_duplicate(
    api_client: APIClient,
    all_role_users: dict[str, User],
    sent: BulkEmail,
    role: str,
    allowed: bool,
) -> None:
    """**Duplicate** is CalDART management's and the system administrator's."""
    api_client.force_login(all_role_users[role])
    response = api_client.post(duplicate_url(sent), {"copy_recipients": True}, format="json")
    assert response.status_code == (201 if allowed else 403)
