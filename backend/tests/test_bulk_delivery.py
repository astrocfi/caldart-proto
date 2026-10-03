"""The delivery report of a sent bulk email: bounces, Retry failed, and each copy.

A bounce the bounce check reads hours later is tied back to the bulk copy that went out
with the same ``Message-ID``.  **Retry failed** sends a fresh copy to the people whose
copy the mail server refused, and to nobody else.  Any copy that was tried can be read
again exactly as it went, from the values stored when it was sent.  See
``docs/developer/bulk-email.rst`` and ``docs/developer/api-bulk-email.rst``.
"""

from __future__ import annotations

import re
import smtplib
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from django.core import mail
from django.core.mail import EmailMessage
from django.core.mail.backends.locmem import EmailBackend
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.test import APIClient

from apps.accounts.roles import MANAGEMENT, SYSTEM_ADMIN
from apps.bulk_email import delivery, job
from apps.bulk_email.models import (
    BulkEmail,
    BulkEmailRecipient,
    BulkEmailRetry,
    BulkEmailStatus,
    RecipientStatus,
)
from apps.mail.bounces import check_bounces
from apps.mail.models import EmailLog, EmailStatus
from caldart.exceptions import DomainError
from tests.conftest import BounceReport, FakeMailbox, audit_messages, read_csv, role_matrix
from tests.factories import BulkEmailFactory, EmailLogFactory, add_to_batch, make_person

if TYPE_CHECKING:
    from apps.accounts.models import User

pytestmark = pytest.mark.django_db

PAST = datetime(2026, 1, 1, tzinfo=UTC)

#: The detail a hard bounce report carries for ``bea@example.test``.
BEA_BOUNCE = (
    "5.1.1 550 5.1.1 <bea@example.test>: Recipient address rejected: "
    "User unknown in virtual mailbox table"
)

#: Addresses the mail server refuses for good while a test runs.
type Refuse = Callable[..., None]


@pytest.fixture(autouse=True)
def _no_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    """Take the pacing's pause out, so a run sends at once."""
    monkeypatch.setattr(job, "sleep", lambda seconds: None)


@pytest.fixture
def refuse(monkeypatch: pytest.MonkeyPatch) -> Refuse:
    """Make the mail server refuse every message to the addresses given, for good.

    Call it with the addresses; call it again with none to let every message through.
    """
    refused: set[str] = set()
    original = EmailBackend.send_messages

    def send(self: EmailBackend, messages: list[EmailMessage]) -> int:
        for message in messages:
            for address in message.to:
                if address in refused:
                    raise smtplib.SMTPRecipientsRefused({address: (550, b"No such user")})
        return original(self, messages)

    monkeypatch.setattr(EmailBackend, "send_messages", send)

    def choose(*addresses: str) -> None:
        refused.clear()
        refused.update(addresses)

    return choose


def send_now(bulk: BulkEmail) -> BulkEmail:
    """Run the background sender once and read ``bulk`` afresh."""
    job.run_sender()
    bulk.refresh_from_db()
    return bulk


def row_of(bulk: BulkEmail, address: str) -> BulkEmailRecipient:
    """``bulk``'s recipient row for ``address``."""
    return bulk.recipients.get(email=address)


def statuses(bulk: BulkEmail) -> dict[str, str]:
    """Each recipient's address and status."""
    return dict(bulk.recipients.values_list("email", "status"))


@pytest.fixture
def mixed(management: User, refuse: Refuse) -> BulkEmail:
    """A sent email: Ann's copy went, Bea's was refused, and Gil, deactivated, skipped."""
    bulk = BulkEmailFactory(
        sender=management,
        subject="Hangar day for {first_name}",
        body="<p>Dear {first_name|friend},</p><p>Bring gloves.</p>",
        status=BulkEmailStatus.QUEUED,
        start_at=PAST,
    )
    add_to_batch(
        bulk,
        make_person("ann@example.test", "Ann", "Able"),
        make_person("bea@example.test", "Bea", "Bell"),
        make_person("gil@example.test", "Gil", "Gone", is_active=False),
    )
    refuse("bea@example.test")
    sent = send_now(bulk)
    refuse()
    mail.outbox.clear()
    return sent


def bounce(row: BulkEmailRecipient, detail: str = BEA_BOUNCE) -> EmailLog:
    """Mark the email log row of ``row``'s copy bounced, as the bounce check does."""
    entry = EmailLog.objects.get(message_id=row.message_id)
    entry.status = EmailStatus.BOUNCED
    entry.bounced_at = timezone.now()
    entry.bounce_detail = detail
    entry.save(update_fields=["status", "bounced_at", "bounce_detail", "updated_at"])
    return entry


# --------------------------------------------------------------------------
# Bounces
# --------------------------------------------------------------------------
def test_a_bounce_the_bounce_check_reads_later_marks_the_bulk_copy(
    management: User, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """The report's ``Message-ID`` names the copy; it reads bounced, with the detail."""
    bulk = BulkEmailFactory(sender=management, status=BulkEmailStatus.QUEUED, start_at=PAST)
    add_to_batch(bulk, make_person("bea@example.test", "Bea", "Bell"))
    send_now(bulk)
    copy = row_of(bulk, "bea@example.test")
    fake_mailbox(
        bounce_report("hard_bounce", recipient="bea@example.test", message_id=copy.message_id)
    )

    check_bounces()

    copy.refresh_from_db()
    assert (copy.status, copy.reason) == (RecipientStatus.BOUNCED, BEA_BOUNCE)


def test_a_bounce_moves_the_copy_from_sent_to_bounced(mixed: BulkEmail) -> None:
    """The counts follow the rows: one fewer sent, one bounced."""
    bounce(row_of(mixed, "ann@example.test"))
    mixed.refresh_from_db()
    assert (mixed.sent_count, mixed.failed_count, mixed.bounced_count) == (0, 1, 1)


def test_a_bounce_read_twice_counts_once(mixed: BulkEmail) -> None:
    """Saving the bounced log row again changes nothing more."""
    entry = bounce(row_of(mixed, "ann@example.test"))
    entry.save()
    mixed.refresh_from_db()
    assert (mixed.sent_count, mixed.bounced_count) == (0, 1)


def test_a_bounce_with_no_detail_gives_a_reason_in_words(mixed: BulkEmail) -> None:
    """A report that said nothing still leaves a reason a sender can read."""
    bounce(row_of(mixed, "ann@example.test"), detail="")
    assert row_of(mixed, "ann@example.test").reason == delivery.BOUNCED_REASON


def test_a_bounce_of_other_mail_leaves_the_bulk_email_alone(mixed: BulkEmail) -> None:
    """A receipt that bounced is not a bulk copy, even to the same person."""
    EmailLogFactory(
        to_email="ann@example.test",
        purpose="receipt",
        status=EmailStatus.BOUNCED,
        message_id=row_of(mixed, "ann@example.test").message_id,
    )
    assert statuses(mixed)["ann@example.test"] == RecipientStatus.SENT


def test_a_bounce_while_the_email_sends_is_not_counted_back(
    management: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A bounce read between two copies stays counted when the sender counts the next."""
    bulk = BulkEmailFactory(sender=management, status=BulkEmailStatus.QUEUED, start_at=PAST)
    add_to_batch(
        bulk,
        make_person("ann@example.test", "Ann", "Able"),
        make_person("bea@example.test", "Bea", "Bell"),
    )

    def bounce_ann(seconds: float) -> None:
        """The pause before Bea's copy: Ann's copy bounces meanwhile."""
        bounce(row_of(bulk, "ann@example.test"))

    monkeypatch.setattr(job, "sleep", bounce_ann)
    sent = send_now(bulk)
    assert (sent.sent_count, sent.bounced_count) == (1, 1)


# --------------------------------------------------------------------------
# Retry failed
# --------------------------------------------------------------------------
def test_retry_failed_sends_a_fresh_copy_to_the_failed_alone(
    mixed: BulkEmail, management: User
) -> None:
    """Only Bea, whose copy was refused, is sent another."""
    delivery.retry_failed(mixed, actor=management)
    send_now(mixed)
    assert [message.to for message in mail.outbox] == [["bea@example.test"]]


def test_retry_failed_leaves_bounced_and_skipped_copies_alone(
    mixed: BulkEmail, management: User
) -> None:
    """A bounced address is bad and a skipped person cannot receive it: no retry."""
    bounce(row_of(mixed, "ann@example.test"))
    delivery.retry_failed(mixed, actor=management)
    assert statuses(mixed) == {
        "ann@example.test": RecipientStatus.BOUNCED,
        "bea@example.test": RecipientStatus.PENDING,
        "gil@example.test": RecipientStatus.SKIPPED,
    }


def test_retry_failed_records_who_when_and_how_many(mixed: BulkEmail, management: User) -> None:
    """Each retry is kept on the email with its time."""
    with freeze_time("2026-04-07T15:00:00Z"):
        delivery.retry_failed(mixed, actor=management)
    retry = BulkEmailRetry.objects.get(bulk_email=mixed)
    assert (retry.requested_by, retry.requested_at, retry.count) == (
        management,
        datetime(2026, 4, 7, 15, 0, tzinfo=UTC),
        1,
    )


def test_retry_failed_queues_the_email_to_start_at_once(mixed: BulkEmail, management: User) -> None:
    """No undo window: the next run of the sender picks it up."""
    with freeze_time("2026-04-07T15:00:00Z"):
        delivery.retry_failed(mixed, actor=management)
    mixed.refresh_from_db()
    assert (mixed.status, mixed.start_at, mixed.scheduled) == (
        BulkEmailStatus.QUEUED,
        datetime(2026, 4, 7, 15, 0, tzinfo=UTC),
        False,
    )


def test_retry_failed_takes_the_copies_out_of_the_failed_count(
    mixed: BulkEmail, management: User
) -> None:
    """While the copies wait they are neither sent nor failed."""
    delivery.retry_failed(mixed, actor=management)
    mixed.refresh_from_db()
    assert (mixed.sent_count, mixed.failed_count) == (1, 0)


def test_a_retried_copy_that_goes_is_counted_sent(mixed: BulkEmail, management: User) -> None:
    """After the retry's send, both copies count as sent and the email is sent again."""
    delivery.retry_failed(mixed, actor=management)
    sent = send_now(mixed)
    assert (sent.status, sent.sent_count, sent.failed_count) == (BulkEmailStatus.SENT, 2, 0)


def test_a_retried_copy_refused_again_is_failed_again(
    mixed: BulkEmail, management: User, refuse: Refuse
) -> None:
    """A copy the server refuses once more is failed again, and can be retried again."""
    delivery.retry_failed(mixed, actor=management)
    refuse("bea@example.test")
    sent = send_now(mixed)
    assert (sent.failed_count, row_of(sent, "bea@example.test").status) == (
        1,
        RecipientStatus.FAILED,
    )


def test_retry_failed_is_audited(
    mixed: BulkEmail, management: User, caplog: pytest.LogCaptureFixture
) -> None:
    """One ``bulk_email.retry`` line names the caller and the copies queued."""
    caplog.set_level("INFO", logger="caldart.audit")
    delivery.retry_failed(mixed, actor=management)
    assert (
        f"action=bulk_email.retry actor={management.pk} target={mixed.pk} recipients=1"
        in audit_messages(caplog)
    )


def test_retry_failed_with_nothing_failed_is_refused(mixed: BulkEmail, management: User) -> None:
    """With every failed copy sent, there is nothing to retry, and nothing changes."""
    mixed.recipients.filter(status=RecipientStatus.FAILED).update(status=RecipientStatus.SENT)
    with pytest.raises(DomainError, match=re.escape(delivery.NOTHING_FAILED_MESSAGE)):
        delivery.retry_failed(mixed, actor=management)


@pytest.mark.parametrize(
    ("status", "message"),
    [
        (BulkEmailStatus.STOPPED, "Send the rest first"),
        (BulkEmailStatus.SENDING, "still sending"),
        (BulkEmailStatus.QUEUED, "still sending"),
    ],
    ids=["stopped", "sending", "queued-again"],
)
def test_retry_failed_waits_for_the_send_to_finish(
    mixed: BulkEmail, management: User, status: BulkEmailStatus, message: str
) -> None:
    """A send that has not finished cannot retry its failed copies yet."""
    BulkEmail.objects.filter(pk=mixed.pk).update(status=status)
    with pytest.raises(DomainError, match=message):
        delivery.retry_failed(mixed, actor=management)


def test_retry_failed_of_an_email_never_sent_is_refused(management: User) -> None:
    """A draft has no copies to retry."""
    draft = BulkEmailFactory(sender=management)
    with pytest.raises(DomainError, match=re.escape(delivery.NOT_STARTED_MESSAGE)):
        delivery.retry_failed(draft, actor=management)


def test_the_retry_endpoint_answers_the_queued_email(
    management_client: APIClient, mixed: BulkEmail
) -> None:
    """``POST .../retry`` answers the email, queued with its retry listed."""
    body = management_client.post(f"/api/v1/bulk-email/{mixed.pk}/retry").json()
    assert (body["status"], body["retried_count"], body["failed_count"]) == ("queued", 1, 0)


def test_the_retry_endpoint_refuses_with_a_sentence(
    management_client: APIClient, mixed: BulkEmail
) -> None:
    """A refusal is a 409 carrying the reason."""
    management_client.post(f"/api/v1/bulk-email/{mixed.pk}/retry")
    response = management_client.post(f"/api/v1/bulk-email/{mixed.pk}/retry")
    assert (response.status_code, response.json()) == (
        409,
        {"detail": delivery.STILL_SENDING_MESSAGE},
    )


# --------------------------------------------------------------------------
# The report
# --------------------------------------------------------------------------
def test_the_detail_counts_every_result(
    management_client: APIClient, mixed: BulkEmail, management: User
) -> None:
    """Sent, failed, skipped, bounced, and retried, each counted."""
    bounce(row_of(mixed, "ann@example.test"))
    delivery.retry_failed(mixed, actor=management)
    send_now(mixed)
    body = management_client.get(f"/api/v1/bulk-email/{mixed.pk}").json()
    assert {
        key: body[key]
        for key in ("sent_count", "failed_count", "skipped_count", "bounced_count", "retried_count")
    } == {
        "sent_count": 1,
        "failed_count": 0,
        "skipped_count": 1,
        "bounced_count": 1,
        "retried_count": 1,
    }


def test_the_detail_lists_each_retry_with_its_time(
    management_client: APIClient, mixed: BulkEmail, management: User
) -> None:
    """Each retry carries when, who, and how many."""
    with freeze_time("2026-04-07T15:00:00Z"):
        delivery.retry_failed(mixed, actor=management)
    retries = management_client.get(f"/api/v1/bulk-email/{mixed.pk}").json()["retries"]
    assert [(row["requested_at"], row["requested_by"], row["count"]) for row in retries] == [
        ("2026-04-07T08:00:00-07:00", "Hollis Grant", 1)
    ]


def test_the_batch_shows_a_bounced_copy_with_its_reason(
    management_client: APIClient, mixed: BulkEmail
) -> None:
    """The per-recipient table reads the bounce and its detail."""
    bounce(row_of(mixed, "ann@example.test"))
    rows = management_client.get(f"/api/v1/bulk-email/{mixed.pk}/batch").json()["rows"]
    assert [(row["status"], row["reason"]) for row in rows if row["name"] == "Ann Able"] == [
        ("bounced", BEA_BOUNCE)
    ]


def test_the_results_csv_carries_the_bounce_and_the_time_tried(
    management_client: APIClient, management: User
) -> None:
    """The CSV reads Bounced with the detail, and when the copy was tried."""
    bulk = BulkEmailFactory(sender=management, status=BulkEmailStatus.QUEUED, start_at=PAST)
    add_to_batch(bulk, make_person("ann@example.test", "Ann", "Able"))
    with freeze_time("2026-04-07T15:00:00Z"):
        send_now(bulk)
    bounce(row_of(bulk, "ann@example.test"))
    rows = read_csv(management_client.get(f"/api/v1/bulk-email/{bulk.pk}/recipients.csv"))
    assert rows[1][4:] == ["Bounced", BEA_BOUNCE, "04/07/2026 08:00", "Operational"]


# --------------------------------------------------------------------------
# One copy as it went
# --------------------------------------------------------------------------
def copy_url(bulk: BulkEmail, row: BulkEmailRecipient) -> str:
    """The address of ``row``'s copy of ``bulk``."""
    return f"/api/v1/bulk-email/{bulk.pk}/recipients/{row.pk}/copy"


def test_a_copy_shows_the_values_it_went_out_with(
    management_client: APIClient, mixed: BulkEmail
) -> None:
    """Ann renamed herself after the send; her copy still says what it said."""
    ann = row_of(mixed, "ann@example.test")
    ann.user.first_name = "Annabel"  # type: ignore[union-attr]
    ann.user.save()  # type: ignore[union-attr]
    body = management_client.get(copy_url(mixed, ann)).json()
    assert (body["subject"], "Dear Ann," in body["html"], "Annabel" in body["html"]) == (
        "Hangar day for Ann",
        True,
        False,
    )


def test_a_copy_carries_who_it_went_to_and_its_result(
    management_client: APIClient, mixed: BulkEmail
) -> None:
    """The answer names the person, the result, and both bodies."""
    bea = row_of(mixed, "bea@example.test")
    body = management_client.get(copy_url(mixed, bea)).json()
    assert (
        body["id"],
        body["name"],
        body["email"],
        body["status"],
        "Dear Bea," in body["text"],
    ) == (
        bea.pk,
        "Bea Bell",
        "bea@example.test",
        "failed",
        True,
    )


def test_a_copy_never_tried_is_refused(management_client: APIClient, mixed: BulkEmail) -> None:
    """Gil was skipped: there is no copy to show."""
    response = management_client.get(copy_url(mixed, row_of(mixed, "gil@example.test")))
    assert (response.status_code, response.json()) == (409, {"detail": delivery.NOT_TRIED_MESSAGE})


def test_a_copy_of_another_email_is_not_found(
    management_client: APIClient, mixed: BulkEmail, management: User
) -> None:
    """A row id from another email's batch is a 404 here."""
    other = BulkEmailFactory(sender=management)
    response = management_client.get(copy_url(other, row_of(mixed, "ann@example.test")))
    assert response.status_code == 404


# --------------------------------------------------------------------------
# The email log links each copy to its bulk email
# --------------------------------------------------------------------------
def test_the_email_log_links_a_bulk_copy_to_its_bulk_email(
    system_admin_client: APIClient, mixed: BulkEmail
) -> None:
    """A copy's row on Sent Emails leads to the bulk email's Sent page."""
    rows = system_admin_client.get("/api/v1/system/emails").json()["results"]
    assert {row["to_email"]: row["link"] for row in rows} == {
        "ann@example.test": f"/bulk-email/sent/{mixed.pk}",
        "bea@example.test": "",
    }


def test_the_email_log_links_no_other_message(system_admin_client: APIClient) -> None:
    """A message that belongs to no record has no link."""
    EmailLogFactory()
    rows = system_admin_client.get("/api/v1/system/emails").json()["results"]
    assert [row["link"] for row in rows] == [""]


# --------------------------------------------------------------------------
# Who may
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("role", "allowed"), role_matrix(MANAGEMENT, SYSTEM_ADMIN))
def test_only_management_retries(
    api_client: APIClient,
    all_role_users: dict[str, User],
    mixed: BulkEmail,
    role: str,
    allowed: bool,
) -> None:
    """**Retry failed** is CalDART management's."""
    api_client.force_login(all_role_users[role])
    response = api_client.post(f"/api/v1/bulk-email/{mixed.pk}/retry")
    assert response.status_code == (200 if allowed else 403)


@pytest.mark.parametrize(("role", "allowed"), role_matrix(MANAGEMENT, SYSTEM_ADMIN))
def test_only_management_reads_a_copy(
    api_client: APIClient,
    all_role_users: dict[str, User],
    mixed: BulkEmail,
    role: str,
    allowed: bool,
) -> None:
    """A recipient's copy is CalDART management's to read."""
    api_client.force_login(all_role_users[role])
    response = api_client.get(copy_url(mixed, row_of(mixed, "ann@example.test")))
    assert response.status_code == (200 if allowed else 403)


@pytest.mark.parametrize("path", ["/{id}/retry", "/{id}/recipients/{rid}/copy"])
def test_an_anonymous_caller_reaches_no_delivery_endpoint(
    api_client: APIClient, mixed: BulkEmail, path: str
) -> None:
    """No session is a 401."""
    url = "/api/v1/bulk-email" + path.format(id=mixed.pk, rid=row_of(mixed, "ann@example.test").pk)
    response = api_client.post(url) if path.endswith("retry") else api_client.get(url)
    assert response.status_code == 401
