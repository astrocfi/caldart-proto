"""A bulk email from its draft to its queue: open, edit, send, schedule, and cancel.

**Send** queues the email to start once the undo window ends, or at the time chosen;
nothing is sent in the request.  A queued email can still change until the background
sender starts it, and can be canceled back to a draft.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from django.core import mail
from freezegun import freeze_time
from pytest_django import Settings
from rest_framework.test import APIClient

from apps.accounts.roles import MANAGEMENT, MEMBER, SYSTEM_ADMIN
from apps.bulk_email import drafts
from apps.bulk_email.job import run_sender
from apps.bulk_email.models import BulkEmail, BulkEmailStatus
from caldart.exceptions import DomainValidationError
from tests.conftest import audit_messages, role_matrix
from tests.factories import BulkEmailFactory, UserFactory, add_to_batch, make_person

if TYPE_CHECKING:
    from apps.accounts.models import User

pytestmark = pytest.mark.django_db

DRAFTS_URL = "/api/v1/bulk-email/drafts"
NOW = datetime(2026, 4, 6, 17, 0, tzinfo=UTC)


def url(bulk: BulkEmail, action: str = "") -> str:
    """``/api/v1/bulk-email/{id}`` for ``bulk``, then ``/<action>`` when one is given."""
    base = f"/api/v1/bulk-email/{bulk.pk}"
    return f"{base}/{action}" if action else base


@pytest.fixture
def ready(management: User) -> BulkEmail:
    """A draft with a subject, a message, and one person in its batch."""
    bulk = BulkEmailFactory(sender=management)
    add_to_batch(bulk, make_person("ann@example.test", "Ann", "Able"))
    return bulk


def status_of(bulk: BulkEmail) -> str:
    """``bulk``'s status, read afresh."""
    bulk.refresh_from_db()
    return bulk.status


# --------------------------------------------------------------------------
# Opening a draft
# --------------------------------------------------------------------------
def test_opening_a_draft_makes_one_for_a_sender_with_none(management: User) -> None:
    """A sender with no empty draft gets a fresh one, owned by them."""
    opened = drafts.open_draft(management)
    assert (opened.created, opened.bulk.sender, opened.bulk.status) == (
        True,
        management,
        BulkEmailStatus.DRAFT,
    )


def test_opening_a_draft_reuses_the_sender_s_empty_one(management: User) -> None:
    """A second open hands back the same empty draft rather than another."""
    first = drafts.open_draft(management).bulk
    assert drafts.open_draft(management) == drafts.OpenedDraft(bulk=first, created=False)


@pytest.mark.parametrize(
    "fields",
    [{"subject": "Hello"}, {"body": "A message."}],
    ids=["subject", "body"],
)
def test_a_draft_with_content_is_not_reused(management: User, fields: dict[str, str]) -> None:
    """A draft with a subject or a message is not empty, so a fresh one is made."""
    BulkEmailFactory(sender=management, **{"subject": "", "body": "", **fields})
    assert drafts.open_draft(management).created is True


def test_a_draft_with_people_is_not_reused(management: User) -> None:
    """A draft whose batch holds somebody is not empty."""
    bulk = BulkEmailFactory(sender=management, subject="", body="")
    add_to_batch(bulk, make_person("ann@example.test"))
    assert drafts.open_draft(management).created is True


def test_another_sender_s_empty_draft_is_not_reused(management: User) -> None:
    """Each sender's empty draft is their own."""
    BulkEmailFactory(sender=UserFactory(email="other@example.test"), subject="", body="")
    assert drafts.open_draft(management).created is True


def test_opening_through_the_api_answers_201_then_200(management_client: APIClient) -> None:
    """The first open makes the draft; the second finds it."""
    first = management_client.post(DRAFTS_URL)
    second = management_client.post(DRAFTS_URL)
    assert (first.status_code, second.status_code, second.json()["id"]) == (
        201,
        200,
        first.json()["id"],
    )


# --------------------------------------------------------------------------
# Editing
# --------------------------------------------------------------------------
def test_a_draft_s_subject_and_message_save(management_client: APIClient, ready: BulkEmail) -> None:
    """``PATCH`` saves the fields given and answers the email."""
    response = management_client.patch(
        url(ready), {"subject": "Hangar day", "body": "Bring gloves."}, format="json"
    )
    assert (response.json()["subject"], response.json()["body"]) == ("Hangar day", "Bring gloves.")


def test_a_draft_may_be_saved_blank(management_client: APIClient, ready: BulkEmail) -> None:
    """Autosave stores a draft half written, a blank subject included."""
    response = management_client.patch(url(ready), {"subject": ""}, format="json")
    assert response.json()["subject"] == ""


@pytest.mark.parametrize(
    ("subject", "message"),
    [
        ("Two\nlines", "A subject is one line."),
        ("A\ttab", "A subject cannot carry control characters such as tabs."),
    ],
    ids=["line-break", "tab"],
)
def test_a_subject_refuses_a_line_break_or_control_character(
    management_client: APIClient, ready: BulkEmail, subject: str, message: str
) -> None:
    """The mail library refuses both in a header, so the subject does too."""
    response = management_client.patch(url(ready), {"subject": subject}, format="json")
    assert response.json() == {"subject": [message]}


def test_editing_a_queued_email_keeps_its_start(ready: BulkEmail, management: User) -> None:
    """A scheduled email can be fixed without moving its start time."""
    start = NOW + timedelta(days=1)
    drafts.queue(ready, confirm_count=None, start_at=start, actor=management, now=NOW)
    edited = drafts.update(ready, {"subject": "Fixed"})
    assert (edited.subject, edited.status, edited.start_at) == (
        "Fixed",
        BulkEmailStatus.QUEUED,
        start,
    )


@pytest.mark.parametrize(
    "status", [BulkEmailStatus.SENDING, BulkEmailStatus.SENT, BulkEmailStatus.STOPPED]
)
def test_a_started_email_cannot_be_edited(
    management_client: APIClient, ready: BulkEmail, status: BulkEmailStatus
) -> None:
    """Once the send has started the email is read-only: a 409 says why."""
    BulkEmail.objects.filter(pk=ready.pk).update(status=status)
    response = management_client.patch(url(ready), {"subject": "Too late"}, format="json")
    assert (response.status_code, response.json()) == (
        409,
        {"detail": "This email has been sent and cannot be changed."},
    )


def test_the_detail_says_whether_the_email_can_change(
    management_client: APIClient, ready: BulkEmail
) -> None:
    """``can_edit`` is false once the email has been sent."""
    BulkEmail.objects.filter(pk=ready.pk).update(status=BulkEmailStatus.SENT)
    assert management_client.get(url(ready)).json()["can_edit"] is False


def test_the_detail_carries_the_batch_counts(
    management_client: APIClient, ready: BulkEmail
) -> None:
    """The screen reads how many are in the batch, receive a copy, and are skipped."""
    add_to_batch(ready, make_person("gone@example.test", is_active=False))
    body = management_client.get(url(ready)).json()
    assert (body["batch_count"], body["receiving_count"], body["batch_skipped_count"]) == (2, 1, 1)


def test_a_draft_can_be_deleted(management_client: APIClient, ready: BulkEmail) -> None:
    """``DELETE`` removes the draft and its batch."""
    response = management_client.delete(url(ready))
    assert (response.status_code, BulkEmail.objects.filter(pk=ready.pk).exists()) == (204, False)


def test_a_queued_email_cannot_be_deleted(
    management_client: APIClient, ready: BulkEmail, management: User
) -> None:
    """A queued email must be canceled before it can be deleted."""
    drafts.queue(ready, confirm_count=None, start_at=None, actor=management)
    response = management_client.delete(url(ready))
    assert (response.status_code, response.json()) == (409, {"detail": drafts.NOT_A_DRAFT_MESSAGE})


# --------------------------------------------------------------------------
# Sending: the undo window and the schedule
# --------------------------------------------------------------------------
def test_send_queues_the_email_to_start_after_the_undo_window(
    ready: BulkEmail, management: User, settings: Settings
) -> None:
    """**Send** sets ``start_at`` to now plus ``BULK_EMAIL_UNDO_SECONDS``."""
    settings.BULK_EMAIL_UNDO_SECONDS = 120
    queued = drafts.queue(ready, confirm_count=None, start_at=None, actor=management, now=NOW)
    assert (queued.status, queued.start_at, queued.scheduled) == (
        BulkEmailStatus.QUEUED,
        NOW + timedelta(seconds=120),
        False,
    )


def test_send_sends_nothing_in_the_request(management_client: APIClient, ready: BulkEmail) -> None:
    """The request only queues the email; no copy goes."""
    management_client.post(url(ready, "send"), {}, format="json")
    assert len(mail.outbox) == 0


def test_send_answers_the_queued_email(management_client: APIClient, ready: BulkEmail) -> None:
    """``POST .../send`` answers the email, queued."""
    response = management_client.post(url(ready, "send"), {}, format="json")
    assert (response.status_code, response.json()["status"]) == (200, "queued")


def test_scheduling_sets_the_chosen_start(ready: BulkEmail, management: User) -> None:
    """A schedule is kept as given and marked scheduled."""
    start = NOW + timedelta(days=2)
    queued = drafts.queue(ready, confirm_count=None, start_at=start, actor=management, now=NOW)
    assert (queued.start_at, queued.scheduled) == (start, True)


def test_a_time_without_an_offset_is_read_in_the_site_s_time_zone(
    management_client: APIClient, ready: BulkEmail
) -> None:
    """``2026-04-07T08:00`` is 8 a.m. Pacific."""
    with freeze_time(NOW):
        response = management_client.post(
            url(ready, "send"), {"start_at": "2026-04-07T08:00"}, format="json"
        )
    assert response.json()["start_at"] == "2026-04-07T08:00:00-07:00"


@pytest.mark.parametrize(
    ("start_at", "message"),
    [
        (NOW - timedelta(minutes=1), drafts.PAST_MESSAGE),
        (NOW, drafts.PAST_MESSAGE),
        (NOW + timedelta(days=366), drafts.TOO_FAR_MESSAGE),
    ],
    ids=["past", "now", "too-far"],
)
def test_a_schedule_in_the_past_or_too_far_ahead_is_refused(
    ready: BulkEmail, management: User, start_at: datetime, message: str
) -> None:
    """The time must be after now and within a year."""
    with pytest.raises(DomainValidationError, match=message):
        drafts.queue(ready, confirm_count=None, start_at=start_at, actor=management, now=NOW)


def test_a_schedule_a_year_ahead_is_accepted(ready: BulkEmail, management: User) -> None:
    """Exactly a year ahead is still within a year."""
    start = NOW + timedelta(days=365)
    assert drafts.queue(
        ready, confirm_count=None, start_at=start, actor=management, now=NOW
    ).start_at == (start)


def test_rescheduling_a_queued_email_moves_its_start(ready: BulkEmail, management: User) -> None:
    """Sending a queued email again with a new time reschedules it."""
    drafts.queue(
        ready, confirm_count=None, start_at=NOW + timedelta(days=1), actor=management, now=NOW
    )
    later = NOW + timedelta(days=3)
    assert drafts.queue(
        ready, confirm_count=None, start_at=later, actor=management, now=NOW
    ).start_at == (later)


@pytest.mark.parametrize(
    ("field", "change", "message"),
    [
        ("subject", {"subject": " "}, drafts.NO_SUBJECT_MESSAGE),
        ("body", {"body": ""}, drafts.NO_BODY_MESSAGE),
    ],
    ids=["subject", "body"],
)
def test_send_refuses_an_email_without_a_subject_or_message(
    management_client: APIClient,
    ready: BulkEmail,
    field: str,
    change: dict[str, str],
    message: str,
) -> None:
    """Both are needed to send, though a draft may lack them."""
    BulkEmail.objects.filter(pk=ready.pk).update(**change)
    response = management_client.post(url(ready, "send"), {}, format="json")
    assert response.json() == {field: [message]}


def test_send_refuses_a_batch_nobody_in_which_can_receive_it(
    management_client: APIClient, management: User
) -> None:
    """A batch of skips alone is refused under ``batch``."""
    bulk = BulkEmailFactory(sender=management)
    add_to_batch(bulk, make_person("gone@example.test", is_active=False))
    response = management_client.post(url(bulk, "send"), {}, format="json")
    assert response.json() == {"batch": [drafts.NOBODY_MESSAGE]}


def test_send_writes_one_audit_line(
    ready: BulkEmail, management: User, audit_log: pytest.LogCaptureFixture
) -> None:
    """``bulk_email.queue`` names the sender, the email, and the count."""
    drafts.queue(ready, confirm_count=None, start_at=None, actor=management)
    assert audit_messages(audit_log) == [
        f"action=bulk_email.queue actor={management.pk} target={ready.pk} "
        "recipients=1 scheduled=false"
    ]


# --------------------------------------------------------------------------
# Confirming a large send by its count
# --------------------------------------------------------------------------
@pytest.fixture
def three_people(ready: BulkEmail) -> BulkEmail:
    """``ready`` with three people who receive a copy."""
    add_to_batch(ready, make_person("bob@example.test"), make_person("cy@example.test"))
    return ready


def test_at_the_threshold_no_count_is_needed(
    three_people: BulkEmail, management: User, settings: Settings
) -> None:
    """Three people with the threshold at three send without a typed count."""
    settings.BULK_EMAIL_CONFIRM_ABOVE = 3
    queued = drafts.queue(three_people, confirm_count=None, start_at=None, actor=management)
    assert (queued.status, queued.confirm_count) == (BulkEmailStatus.QUEUED, None)


def test_above_the_threshold_a_missing_count_is_refused(
    three_people: BulkEmail, management: User, settings: Settings
) -> None:
    """Above the threshold the typed count is required."""
    settings.BULK_EMAIL_CONFIRM_ABOVE = 2
    with pytest.raises(DomainValidationError, match=drafts.CONFIRM_MISSING_MESSAGE):
        drafts.queue(three_people, confirm_count=None, start_at=None, actor=management)


def test_above_the_threshold_the_right_count_is_kept(
    three_people: BulkEmail, management: User, settings: Settings
) -> None:
    """The typed count is stored with the queued email."""
    settings.BULK_EMAIL_CONFIRM_ABOVE = 2
    assert (
        drafts.queue(three_people, confirm_count=3, start_at=None, actor=management).confirm_count
        == 3
    )


def test_a_batch_that_changed_since_the_count_was_typed_is_refused(
    management_client: APIClient, three_people: BulkEmail, settings: Settings
) -> None:
    """The server re-counts and refuses with the new number."""
    settings.BULK_EMAIL_CONFIRM_ABOVE = 2
    add_to_batch(three_people, make_person("dee@example.test"))
    response = management_client.post(
        url(three_people, "send"), {"confirm_count": 3}, format="json"
    )
    assert response.json() == {
        "confirm_count": ["The batch has changed: it now holds 4 people. Type the new count."]
    }


# --------------------------------------------------------------------------
# Canceling
# --------------------------------------------------------------------------
def test_cancel_before_the_start_returns_the_email_to_a_draft(
    ready: BulkEmail, management: User
) -> None:
    """The batch and the content stay; the start time goes."""
    drafts.queue(ready, confirm_count=None, start_at=None, actor=management)
    canceled = drafts.cancel(ready, actor=management)
    assert (
        canceled.status,
        canceled.start_at,
        canceled.subject,
        canceled.recipients.count(),
    ) == (BulkEmailStatus.DRAFT, None, "Spring safety seminar", 1)


def test_a_canceled_email_sends_nothing(ready: BulkEmail, management: User) -> None:
    """The sender finds nothing to start once the email is a draft again."""
    with freeze_time(NOW):
        drafts.queue(ready, confirm_count=None, start_at=None, actor=management)
        drafts.cancel(ready, actor=management)
    with freeze_time(NOW + timedelta(hours=1)):
        run_sender()
    assert len(mail.outbox) == 0


def test_cancel_after_the_start_is_refused(management_client: APIClient, ready: BulkEmail) -> None:
    """Once the sender has started it, a 409 says so."""
    BulkEmail.objects.filter(pk=ready.pk).update(status=BulkEmailStatus.SENDING)
    response = management_client.post(url(ready, "cancel"))
    assert (response.status_code, response.json()) == (
        409,
        {"detail": "This email has started sending."},
    )


def test_another_manager_can_cancel(
    ready: BulkEmail, management: User, api_client: APIClient
) -> None:
    """Any CalDART management member cancels a queued email, not only its sender."""
    drafts.queue(ready, confirm_count=None, start_at=None, actor=management)
    api_client.force_login(UserFactory(email="second@example.test", roles=[MEMBER, MANAGEMENT]))
    api_client.post(url(ready, "cancel"))
    assert status_of(ready) == BulkEmailStatus.DRAFT


# --------------------------------------------------------------------------
# The lists
# --------------------------------------------------------------------------
def test_the_drafts_list_holds_drafts_and_queued_emails(
    management_client: APIClient, management: User
) -> None:
    """Sent emails are on the Sent list instead."""
    draft = BulkEmailFactory(sender=management, subject="Draft")
    queued = BulkEmailFactory(sender=management, subject="Queued", status=BulkEmailStatus.QUEUED)
    BulkEmailFactory(sender=management, subject="Sent", status=BulkEmailStatus.SENT)
    ids = {row["id"] for row in management_client.get(DRAFTS_URL).json()}
    assert ids == {draft.pk, queued.pk}


def test_management_sees_everyone_s_drafts_with_their_sender(
    management_client: APIClient,
) -> None:
    """Each row names who is writing it."""
    BulkEmailFactory(
        sender=UserFactory(email="ann@example.test", first_name="Ann", last_name="Able")
    )
    assert [row["sender"] for row in management_client.get(DRAFTS_URL).json()] == ["Ann Able"]


def test_a_draft_row_carries_its_batch_count(
    management_client: APIClient, ready: BulkEmail
) -> None:
    """The list says how many people each draft's batch holds."""
    assert management_client.get(DRAFTS_URL).json()[0]["batch_count"] == 1


# --------------------------------------------------------------------------
# Who may call what
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("role", "allowed"), role_matrix(MANAGEMENT, SYSTEM_ADMIN))
@pytest.mark.parametrize(
    ("method", "action", "code"),
    [
        ("get", "", 200),
        ("patch", "", 200),
        ("post", "send", 200),
        ("post", "cancel", 200),
        ("delete", "", 204),
    ],
    ids=["read", "edit", "send", "cancel", "delete"],
)
def test_only_management_reaches_a_draft(
    api_client: APIClient,
    all_role_users: dict[str, User],
    ready: BulkEmail,
    role: str,
    allowed: bool,
    method: str,
    action: str,
    code: int,
) -> None:
    """Every draft endpoint is CalDART management's and the system administrator's."""
    api_client.force_login(all_role_users[role])
    response = getattr(api_client, method)(url(ready, action), {}, format="json")
    assert response.status_code == (code if allowed else 403)


@pytest.mark.parametrize(("role", "allowed"), role_matrix(MANAGEMENT, SYSTEM_ADMIN))
@pytest.mark.parametrize(("method", "code"), [("get", 200), ("post", 201)])
def test_only_management_lists_and_opens_drafts(
    api_client: APIClient,
    all_role_users: dict[str, User],
    role: str,
    allowed: bool,
    method: str,
    code: int,
) -> None:
    """``/bulk-email/drafts`` answers CalDART management alone."""
    api_client.force_login(all_role_users[role])
    response = getattr(api_client, method)(DRAFTS_URL)
    assert response.status_code == (code if allowed else 403)


@pytest.mark.parametrize(
    ("method", "path"),
    [("get", DRAFTS_URL), ("post", DRAFTS_URL), ("get", "/api/v1/bulk-email/sent")],
)
def test_an_anonymous_caller_is_turned_away(
    csrf_client: APIClient,
    csrf_headers: Callable[[APIClient], dict[str, str]],
    method: str,
    path: str,
) -> None:
    """Nobody signed in reaches a bulk email endpoint, even with a CSRF token."""
    response = getattr(csrf_client, method)(path, **csrf_headers(csrf_client))
    assert response.status_code == 401


def test_an_unknown_email_is_not_found(management_client: APIClient) -> None:
    """An id that names no email is a 404."""
    assert management_client.get("/api/v1/bulk-email/999999").status_code == 404
