"""A test copy of a bulk email to its sender, and the per-person copy it shares.

``POST /bulk-email/{id}/test`` mails the caller the email as it is saved, filled in with
the caller's own values and built as the background sender builds a copy, under a
subject that starts ``[Test]``.  It touches nothing of the send and is in the email log
under ``bulk_email_test``.  The preview builds each person's copy the same way, so it
ends with that person's own unsubscribe link.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from django.core import mail
from django.core.mail import EmailMultiAlternatives
from freezegun import freeze_time
from rest_framework.test import APIClient

from apps.accounts.roles import DART_LEADER, MANAGEMENT, SYSTEM_ADMIN
from apps.bulk_email import job
from apps.bulk_email.api.checks import TEST_REFUSED_MESSAGE
from apps.bulk_email.checks import NO_SUBJECT, NO_SUBJECT_MESSAGE
from apps.bulk_email.models import BulkEmail, BulkEmailRecipient, BulkEmailStatus
from apps.bulk_email.render import inert_unsubscribe_url
from apps.bulk_email.tests_send import PURPOSE, send_test
from apps.mail.models import EmailLog, EmailStatus, EmailType
from apps.mail.unsubscribe import UnsubscribeLinkError, read_token
from caldart.mail import MailRefusedError
from tests.conftest import role_matrix
from tests.factories import (
    BulkEmailFactory,
    DartFactory,
    add_to_batch,
    make_dart_leader,
    make_person,
)

if TYPE_CHECKING:
    from apps.accounts.models import User

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 4, 6, 17, 0, tzinfo=UTC)

#: A message that greets each person by name.
GREETING = "<p>Dear {first_name|friend},</p><p>See you at Livermore.</p>"

#: An unsubscribe link in a copy's HTML, its signed token captured.
UNSUBSCRIBE_RE = re.compile(r"/mail/unsubscribe/([^\"<\s]+)")


def endpoint(bulk: BulkEmail) -> str:
    """``/api/v1/bulk-email/{id}/test`` for ``bulk``."""
    return f"/api/v1/bulk-email/{bulk.pk}/test"


def html_of(message: object) -> str:
    """The HTML body of a sent ``message``."""
    assert isinstance(message, EmailMultiAlternatives)
    return str(message.alternatives[0][0])


def unsubscribed_by(html: str) -> tuple[User, EmailType]:
    """The account and type the first unsubscribe link in ``html`` names."""
    match = UNSUBSCRIBE_RE.search(html)
    assert match is not None
    return read_token(match.group(1))


@pytest.fixture(autouse=True)
def _no_pacing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Let the sender send without pausing between copies."""
    monkeypatch.setattr(job, "sleep", lambda seconds: None)


@pytest.fixture
def greeting(management: User) -> BulkEmail:
    """A draft greeting each person by first name, with Ann in its batch."""
    bulk = BulkEmailFactory(
        sender=management, subject="Hello {first_name}", body=GREETING, reply_to=""
    )
    add_to_batch(bulk, make_person("ann@example.test", "Ann", "Able"))
    return bulk


# -- who may send a test ------------------------------------------------------------
@pytest.mark.parametrize(("role", "allowed"), role_matrix(MANAGEMENT, SYSTEM_ADMIN))
def test_only_management_sends_a_test(
    api_client: APIClient,
    all_role_users: dict[str, User],
    management: User,
    role: str,
    allowed: bool,
) -> None:
    """``POST /bulk-email/{id}/test`` of a manager's email is for CalDART management.

    A DART leader gets a 404 for another sender's email.
    """
    bulk = BulkEmailFactory(sender=management)
    api_client.force_login(all_role_users[role])
    response = api_client.post(endpoint(bulk))
    assert response.status_code == (200 if allowed else (404 if role == DART_LEADER else 403))


def test_a_leader_s_test_goes_to_the_leader_alone(api_client: APIClient) -> None:
    """A leader's test of their own draft reaches them, and nobody in their batch."""
    marin = DartFactory(name="Marin")
    leader = make_dart_leader("lane@example.test", marin)
    bulk = BulkEmailFactory(sender=leader, dart=marin, reply_to="")
    add_to_batch(
        bulk,
        make_person("ann@example.test", "Ann", dart=marin),
        make_person("nat@example.test", "Nat", dart=DartFactory(name="Napa")),
    )
    api_client.force_login(leader)
    response = api_client.post(endpoint(bulk))
    assert (response.status_code, [message.to for message in mail.outbox]) == (
        200,
        [["lane@example.test"]],
    )


def test_a_leader_cannot_test_another_leader_s_draft(api_client: APIClient) -> None:
    """Another leader's email is a 404, and nothing is sent."""
    lane = make_dart_leader("lane@example.test", DartFactory(name="Marin"))
    nell = make_dart_leader("nell@example.test", DartFactory(name="Napa"))
    bulk = BulkEmailFactory(sender=nell, dart=nell.profile.dart)
    api_client.force_login(lane)
    response = api_client.post(endpoint(bulk))
    assert (response.status_code, len(mail.outbox)) == (404, 0)


def test_an_anonymous_caller_is_refused(api_client: APIClient, management: User) -> None:
    """Nobody signed in is a 401, and nothing is sent."""
    response = api_client.post(endpoint(BulkEmailFactory(sender=management)))
    assert response.status_code == 401


# -- what goes, and where -------------------------------------------------------------
def test_a_test_goes_to_the_caller_alone(
    management_client: APIClient, management: User, greeting: BulkEmail
) -> None:
    """One press is one message, to the caller's own address and nobody in the batch."""
    response = management_client.post(endpoint(greeting))
    assert (response.json(), [message.to for message in mail.outbox]) == (
        {"to": management.email},
        [[management.email]],
    )


def test_every_press_sends_one_more(management_client: APIClient, greeting: BulkEmail) -> None:
    """Two presses are two messages: a test is never held back as a repeat."""
    management_client.post(endpoint(greeting))
    management_client.post(endpoint(greeting))
    assert len(mail.outbox) == 2


def test_the_subject_says_it_is_a_test_and_is_filled_in_for_the_caller(
    management_client: APIClient, management: User, greeting: BulkEmail
) -> None:
    """The subject starts ``[Test]`` and carries the caller's own first name."""
    management_client.post(endpoint(greeting))
    assert mail.outbox[0].subject == f"[Test] Hello {management.first_name}"


def test_the_body_is_the_copy_the_send_would_give_the_caller(
    management: User, greeting: BulkEmail
) -> None:
    """Both parts match the copy the background sender sends the same person."""
    add_to_batch(greeting, management)
    with freeze_time(NOW):
        send_test(greeting, actor=management)
        BulkEmail.objects.filter(pk=greeting.pk).update(status=BulkEmailStatus.QUEUED, start_at=NOW)
        job.run_sender(now=NOW)
    test_copy, real_copy = (
        mail.outbox[0],
        next(message for message in mail.outbox[1:] if message.to == [management.email]),
    )
    assert (test_copy.body, html_of(test_copy)) == (real_copy.body, html_of(real_copy))


def test_the_test_carries_the_caller_s_own_unsubscribe_link(
    management: User, greeting: BulkEmail
) -> None:
    """The footer's link turns the email's type off for the caller, as a copy would."""
    send_test(greeting, actor=management)
    assert unsubscribed_by(html_of(mail.outbox[0])) == (management, greeting.email_type)


def test_the_test_carries_the_unsubscribe_headers(management: User, greeting: BulkEmail) -> None:
    """``List-Unsubscribe-Post`` rides along, as on every copy of an opt-out type."""
    send_test(greeting, actor=management)
    assert mail.outbox[0].extra_headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"


def test_the_test_carries_the_reply_to(management: User, greeting: BulkEmail) -> None:
    """Replies to a test go where replies to the real copies will."""
    BulkEmail.objects.filter(pk=greeting.pk).update(reply_to="marin@example.test")
    greeting.refresh_from_db()
    send_test(greeting, actor=management)
    assert mail.outbox[0].reply_to == ["marin@example.test"]


def test_a_test_touches_nothing_of_the_send(
    management_client: APIClient, greeting: BulkEmail
) -> None:
    """The email stays a draft with the same batch, and no copy is counted."""
    management_client.post(endpoint(greeting))
    greeting.refresh_from_db()
    assert (
        greeting.status,
        greeting.sent_count,
        BulkEmailRecipient.objects.filter(bulk_email=greeting).count(),
        BulkEmailRecipient.objects.filter(bulk_email=greeting, tried_at__isnull=False).count(),
    ) == (BulkEmailStatus.DRAFT, 0, 1, 0)


def test_a_test_is_in_the_email_log_under_its_own_purpose(
    management_client: APIClient, management: User, greeting: BulkEmail
) -> None:
    """One sent row, ``bulk_email_test``, naming the caller's account."""
    management_client.post(endpoint(greeting))
    assert list(EmailLog.objects.values_list("purpose", "user_id", "status")) == [
        (PURPOSE, management.pk, EmailStatus.SENT)
    ]


# -- refusals -------------------------------------------------------------------------
@pytest.mark.usefixtures("refusing_mail_server")
def test_a_refused_test_is_a_503(management_client: APIClient, greeting: BulkEmail) -> None:
    """The caller learns the test did not go, in plain words."""
    response = management_client.post(endpoint(greeting))
    assert (response.status_code, response.json()) == (503, {"detail": TEST_REFUSED_MESSAGE})


@pytest.mark.usefixtures("refusing_mail_server")
def test_a_refused_test_is_logged_as_failed(
    management_client: APIClient, greeting: BulkEmail
) -> None:
    """The email log records the failed send."""
    management_client.post(endpoint(greeting))
    assert list(EmailLog.objects.values_list("purpose", "status")) == [
        (PURPOSE, EmailStatus.FAILED)
    ]


@pytest.mark.usefixtures("refusing_mail_server")
def test_send_test_raises_a_refusal(management: User, greeting: BulkEmail) -> None:
    """``send_test`` lets the mail server's refusal through to its caller."""
    with pytest.raises(MailRefusedError, match="SMTPException"):
        send_test(greeting, actor=management)


def test_an_email_with_errors_is_not_tested(management_client: APIClient, management: User) -> None:
    """A 400 lists the checks' errors under ``checks``, and nothing is sent."""
    bulk = BulkEmailFactory(sender=management, subject="", reply_to="pat@example.org")
    response = management_client.post(endpoint(bulk))
    assert (response.status_code, response.json(), len(mail.outbox)) == (
        400,
        {"checks": [{"code": NO_SUBJECT, "level": "error", "message": NO_SUBJECT_MESSAGE}]},
        0,
    )


def test_an_unknown_email_is_a_404(management_client: APIClient) -> None:
    """An id no email carries is a 404."""
    assert management_client.post("/api/v1/bulk-email/999999/test").status_code == 404


# -- the preview is each person's whole copy -----------------------------------------
def test_the_preview_footer_reads_as_the_person_s_copy_does(
    management_client: APIClient, greeting: BulkEmail
) -> None:
    """Ann's preview ends with the footer her copy carries, not the general line."""
    html = management_client.post(
        f"/api/v1/bulk-email/{greeting.pk}/preview", {}, format="json"
    ).json()["html"]
    assert "because you have not turned it off" in html


def test_the_preview_s_unsubscribe_link_unsubscribes_nobody(
    management_client: APIClient, greeting: BulkEmail
) -> None:
    """The link in a preview holds no signed token, so a sender cannot turn Ann's off."""
    html = management_client.post(
        f"/api/v1/bulk-email/{greeting.pk}/preview", {}, format="json"
    ).json()["html"]
    match = UNSUBSCRIBE_RE.search(html)
    assert match is not None
    with pytest.raises(UnsubscribeLinkError, match="not one this site signed"):
        read_token(match.group(1))


def test_the_sender_s_own_preview_carries_the_inert_link_too(
    management_client: APIClient, management: User
) -> None:
    """With nobody in the batch, the caller's own preview has the same inert link."""
    bulk = BulkEmailFactory(sender=management)
    html = management_client.post(
        f"/api/v1/bulk-email/{bulk.pk}/preview", {}, format="json"
    ).json()["html"]
    assert inert_unsubscribe_url() in html
