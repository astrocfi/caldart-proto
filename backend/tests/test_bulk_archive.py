"""The Messages page: the bulk emails a person received, each as their own copy.

A person reads only the bulk emails sent to them, each filled in with the values stored
on their own recipient row when it went.  CalDART management can hide an email from
Messages without changing its history.  Every copy links to its page here, under the
site's own address.  See ``docs/developer/api-bulk-email.rst``.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from django.core import mail
from django.core.mail import EmailMultiAlternatives
from freezegun import freeze_time
from pytest_django import Settings
from rest_framework.test import APIClient

from apps.accounts.roles import MANAGEMENT, ROLE_SLUGS, SYSTEM_ADMIN
from apps.bulk_email import delivery, job
from apps.bulk_email.models import BulkEmail, BulkEmailStatus, RecipientStatus
from caldart.exceptions import DomainError
from tests.conftest import audit_messages, role_matrix
from tests.factories import BulkEmailFactory, EmailLogFactory, add_to_batch, make_person

if TYPE_CHECKING:
    from apps.accounts.models import User

pytestmark = pytest.mark.django_db

PAST = datetime(2026, 1, 1, tzinfo=UTC)
MESSAGES_URL = "/api/v1/messages"


@pytest.fixture(autouse=True)
def _no_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    """Take the pacing's pause out, so a run sends at once."""
    monkeypatch.setattr(job, "sleep", lambda seconds: None)


@pytest.fixture
def ann(db: None) -> User:
    """Ann Able, a member."""
    return make_person("ann@example.test", "Ann", "Able")


@pytest.fixture
def bea(db: None) -> User:
    """Bea Bell, a member."""
    return make_person("bea@example.test", "Bea", "Bell")


@pytest.fixture
def ann_client(api_client: APIClient, ann: User) -> APIClient:
    """An API client signed in as Ann."""
    api_client.force_login(ann)
    return api_client


def sent_to(*people: User, subject: str = "Hangar day for {first_name}") -> BulkEmail:
    """A bulk email sent to ``people``, filling in each one's first name."""
    bulk = BulkEmailFactory(
        subject=subject,
        body="<p>Dear {first_name|friend},</p><p>Bring gloves.</p>",
        status=BulkEmailStatus.QUEUED,
        start_at=PAST,
    )
    add_to_batch(bulk, *people)
    job.run_sender()
    bulk.refresh_from_db()
    return bulk


def message_url(bulk: BulkEmail) -> str:
    """The address of ``bulk`` among the caller's messages."""
    return f"{MESSAGES_URL}/{bulk.pk}"


# --------------------------------------------------------------------------
# Who sees what
# --------------------------------------------------------------------------
def test_a_recipient_finds_the_message_in_their_list(
    ann_client: APIClient, ann: User, bea: User
) -> None:
    """Ann's list holds the email, with her own subject, its type, and who sent it."""
    with freeze_time("2026-04-07T15:00:00Z"):
        bulk = sent_to(ann, bea)
    assert ann_client.get(MESSAGES_URL).json() == [
        {
            "id": bulk.pk,
            "subject": "Hangar day for Ann",
            "sent_at": "2026-04-07T08:00:00-07:00",
            "from_name": "Grace Holloway",
            "email_type_name": "Operational",
        }
    ]


def test_a_recipient_reads_their_own_copy(ann_client: APIClient, ann: User) -> None:
    """The message opens as Ann's copy, filled in for her."""
    body = ann_client.get(message_url(sent_to(ann))).json()
    assert (body["subject"], "Dear Ann," in body["html"], "Dear Ann," in body["text"]) == (
        "Hangar day for Ann",
        True,
        True,
    )


def test_someone_not_sent_the_email_does_not_see_it(ann_client: APIClient, bea: User) -> None:
    """Bea's email is not in Ann's list."""
    sent_to(bea)
    assert ann_client.get(MESSAGES_URL).json() == []


def test_someone_not_sent_the_email_cannot_open_it(ann_client: APIClient, bea: User) -> None:
    """Opening Bea's email by its id is a 404 for Ann."""
    assert ann_client.get(message_url(sent_to(bea))).status_code == 404


def test_the_sender_does_not_see_an_email_they_did_not_receive(
    management_client: APIClient, bea: User
) -> None:
    """Sending an email does not put it in the sender's own Messages."""
    sent_to(bea)
    assert management_client.get(MESSAGES_URL).json() == []


def test_transactional_mail_is_not_a_message(ann_client: APIClient, ann: User) -> None:
    """A receipt or a reminder sent to Ann is not listed."""
    EmailLogFactory(user=ann, purpose="receipt")
    EmailLogFactory(user=ann, purpose="reminder_second")
    assert ann_client.get(MESSAGES_URL).json() == []


@pytest.mark.parametrize(
    "status",
    [RecipientStatus.SKIPPED, RecipientStatus.FAILED, RecipientStatus.STOPPED],
    ids=["skipped", "failed", "stopped"],
)
def test_a_copy_that_never_reached_the_reader_is_not_a_message(
    ann_client: APIClient, ann: User, status: RecipientStatus
) -> None:
    """Only a copy that went counts as received."""
    bulk = sent_to(ann)
    bulk.recipients.update(status=status)
    assert ann_client.get(MESSAGES_URL).json() == []


def test_a_copy_that_bounced_is_still_a_message(ann_client: APIClient, ann: User) -> None:
    """The copy went; the reader may still read it here."""
    bulk = sent_to(ann)
    bulk.recipients.update(status=RecipientStatus.BOUNCED)
    assert [row["id"] for row in ann_client.get(MESSAGES_URL).json()] == [bulk.pk]


def test_the_newest_message_comes_first(ann_client: APIClient, ann: User) -> None:
    """The list is in the order the copies reached Ann, latest first."""
    with freeze_time("2026-03-01T17:00:00Z"):
        older = sent_to(ann, subject="March")
    with freeze_time("2026-04-01T17:00:00Z"):
        newer = sent_to(ann, subject="April")
    assert [row["id"] for row in ann_client.get(MESSAGES_URL).json()] == [newer.pk, older.pk]


def test_a_deleted_sender_reads_as_the_organization(ann_client: APIClient, ann: User) -> None:
    """With the sender's account gone, the message is from CalDART."""
    bulk = sent_to(ann)
    BulkEmail.objects.filter(pk=bulk.pk).update(sender=None)
    assert ann_client.get(MESSAGES_URL).json()[0]["from_name"] == "CalDART"


# --------------------------------------------------------------------------
# The values as sent
# --------------------------------------------------------------------------
def test_the_copy_keeps_the_values_it_went_out_with(ann_client: APIClient, ann: User) -> None:
    """Ann renamed herself after the send; her message still reads as it went."""
    bulk = sent_to(ann)
    ann.first_name = "Annabel"
    ann.save()
    body = ann_client.get(message_url(bulk)).json()
    assert (body["subject"], "Dear Ann," in body["html"], "Annabel" in body["html"]) == (
        "Hangar day for Ann",
        True,
        False,
    )


def test_a_reader_never_sees_another_recipient_s_values(
    api_client: APIClient, ann: User, bea: User
) -> None:
    """Bea's copy of an email both received is filled in for Bea alone."""
    bulk = sent_to(ann, bea)
    api_client.force_login(bea)
    body = api_client.get(message_url(bulk)).json()
    assert ("Dear Bea," in body["html"], "Ann" in body["html"], "Ann" in body["subject"]) == (
        True,
        False,
        False,
    )


def test_the_reader_s_own_copy_keeps_their_unsubscribe_link(
    ann_client: APIClient, ann: User
) -> None:
    """Ann's own copy on Messages carries her live unsubscribe link, as her email did."""
    body = ann_client.get(message_url(sent_to(ann))).json()
    assert "/mail/unsubscribe/" in body["html"]


# --------------------------------------------------------------------------
# Hiding
# --------------------------------------------------------------------------
def hide(client: APIClient, bulk: BulkEmail, *, hidden: bool = True) -> dict[str, object]:
    """Press **Hide from Messages** (or **Show in Messages**) on ``bulk``'s Sent page."""
    response = client.post(f"/api/v1/bulk-email/{bulk.pk}/hide", {"hidden": hidden}, format="json")
    assert response.status_code == 200
    body: dict[str, object] = response.json()
    return body


def test_a_hidden_message_is_gone_from_the_list(management_client: APIClient, ann: User) -> None:
    """Once hidden, Ann's list no longer holds it."""
    bulk = sent_to(ann)
    hide(management_client, bulk)
    management_client.force_login(ann)
    assert management_client.get(MESSAGES_URL).json() == []


def test_a_hidden_message_cannot_be_opened(management_client: APIClient, ann: User) -> None:
    """Its page is a 404, so View in browser no longer shows it either."""
    bulk = sent_to(ann)
    hide(management_client, bulk)
    management_client.force_login(ann)
    assert management_client.get(message_url(bulk)).status_code == 404


def test_hiding_keeps_the_history(management_client: APIClient, ann: User) -> None:
    """The Sent page still reads the send and every copy's result."""
    bulk = sent_to(ann)
    body = hide(management_client, bulk)
    rows = management_client.get(f"/api/v1/bulk-email/{bulk.pk}/batch").json()["rows"]
    assert (body["hidden_from_archive"], body["sent_count"], [row["status"] for row in rows]) == (
        True,
        1,
        ["sent"],
    )


def test_a_hidden_message_can_be_shown_again(management_client: APIClient, ann: User) -> None:
    """**Show in Messages** puts it back in Ann's list."""
    bulk = sent_to(ann)
    hide(management_client, bulk)
    hide(management_client, bulk, hidden=False)
    management_client.force_login(ann)
    assert [row["id"] for row in management_client.get(MESSAGES_URL).json()] == [bulk.pk]


def test_hiding_is_audited(
    management_client: APIClient, management: User, ann: User, caplog: pytest.LogCaptureFixture
) -> None:
    """One ``bulk_email.hide`` line names who hid it."""
    caplog.set_level("INFO", logger="caldart.audit")
    bulk = sent_to(ann)
    hide(management_client, bulk)
    assert (
        f"action=bulk_email.hide actor={management.pk} target={bulk.pk} hidden=true"
        in audit_messages(caplog)
    )


def test_a_draft_cannot_be_hidden(management: User) -> None:
    """Nobody received a draft, so there is nothing to hide."""
    draft = BulkEmailFactory(sender=management)
    with pytest.raises(DomainError, match=re.escape(delivery.NOT_STARTED_MESSAGE)):
        delivery.set_hidden(draft, hidden=True, actor=management)


def test_the_hide_endpoint_needs_a_choice(management_client: APIClient, ann: User) -> None:
    """A body without ``hidden`` is a 400 keyed ``hidden``."""
    bulk = sent_to(ann)
    response = management_client.post(f"/api/v1/bulk-email/{bulk.pk}/hide", {}, format="json")
    assert (response.status_code, list(response.json())) == (400, ["hidden"])


# --------------------------------------------------------------------------
# View in browser
# --------------------------------------------------------------------------
def only_copy() -> EmailMultiAlternatives:
    """The one copy the sender sent."""
    (message,) = mail.outbox
    assert isinstance(message, EmailMultiAlternatives)
    return message


def test_every_copy_links_to_its_message(ann: User, settings: Settings) -> None:
    """The plain-text copy carries the link to the message's page."""
    settings.SITE_URL = "https://caldart.example.org"
    bulk = sent_to(ann)
    assert (
        f"View this email in your browser: https://caldart.example.org/portal/messages/{bulk.pk}"
        in str(only_copy().body)
    )


def test_the_html_copy_links_to_its_message(ann: User, settings: Settings) -> None:
    """The HTML copy's footer links to the message's page."""
    settings.SITE_URL = "https://caldart.example.org"
    bulk = sent_to(ann)
    html = str(only_copy().alternatives[0][0])
    assert f'href="https://caldart.example.org/portal/messages/{bulk.pk}"' in html


def test_the_link_carries_the_site_s_url_prefix(ann: User, settings: Settings) -> None:
    """Under a URL prefix, the link reaches the portal under that prefix, once."""
    settings.SITE_URL = "https://caldart.example.org/caldart/"
    settings.URL_PREFIX = "/caldart"
    bulk = sent_to(ann)
    assert f"https://caldart.example.org/caldart/portal/messages/{bulk.pk}\n" in str(
        only_copy().body
    )


# --------------------------------------------------------------------------
# Who may
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("role", "allowed"), role_matrix(*ROLE_SLUGS))
def test_every_signed_in_person_reads_their_messages(
    api_client: APIClient, all_role_users: dict[str, User], role: str, allowed: bool
) -> None:
    """Messages is every signed-in person's, whatever their roles."""
    api_client.force_login(all_role_users[role])
    assert api_client.get(MESSAGES_URL).status_code == (200 if allowed else 403)


@pytest.mark.parametrize(("role", "allowed"), role_matrix(*ROLE_SLUGS))
def test_every_signed_in_recipient_opens_their_message(
    api_client: APIClient, all_role_users: dict[str, User], role: str, allowed: bool
) -> None:
    """Whatever their roles, a recipient opens a message sent to them."""
    bulk = sent_to(all_role_users[role])
    api_client.force_login(all_role_users[role])
    assert api_client.get(message_url(bulk)).status_code == (200 if allowed else 403)


@pytest.mark.parametrize("path", ["", "/1"])
def test_an_anonymous_caller_reads_no_messages(api_client: APIClient, path: str) -> None:
    """No session is a 401."""
    assert api_client.get(MESSAGES_URL + path).status_code == 401


@pytest.mark.parametrize(("role", "allowed"), role_matrix(MANAGEMENT, SYSTEM_ADMIN))
def test_only_management_hides_a_message(
    api_client: APIClient,
    all_role_users: dict[str, User],
    ann: User,
    role: str,
    allowed: bool,
) -> None:
    """Hiding a message from everybody's Messages is CalDART management's."""
    bulk = sent_to(ann)
    api_client.force_login(all_role_users[role])
    response = api_client.post(
        f"/api/v1/bulk-email/{bulk.pk}/hide", {"hidden": True}, format="json"
    )
    assert response.status_code == (200 if allowed else 403)
