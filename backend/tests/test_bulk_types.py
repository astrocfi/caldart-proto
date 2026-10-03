"""A bulk email's type: chosen on the draft, needed to send, and what each copy carries.

The behavior is documented in ``docs/developer/bulk-email.rst`` and
``docs/developer/email.rst``.
"""

from __future__ import annotations

import email.policy
import logging
from datetime import UTC, datetime, timedelta

import pytest
from django.core import mail
from django.core.mail import EmailMultiAlternatives
from freezegun import freeze_time
from pytest_django import Settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import DART_LEADER, MANAGEMENT, MEMBER
from apps.bulk_email import batch, drafts, job
from apps.bulk_email.models import BulkEmail, BulkEmailStatus, RecipientStatus
from apps.bulk_email.render import render_copy
from apps.mail.models import EmailType
from apps.mail.unsubscribe import read_token
from caldart.exceptions import DomainValidationError
from tests.conftest import audit_messages, read_csv
from tests.factories import (
    BulkEmailFactory,
    EmailOptOutFactory,
    EmailTypeFactory,
    UserFactory,
    add_to_batch,
    make_person,
    make_site_settings,
)

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 4, 6, 17, 0, tzinfo=UTC)


def detail_url(bulk: BulkEmail) -> str:
    """``/bulk-email/{id}`` for ``bulk``."""
    return f"/api/v1/bulk-email/{bulk.pk}"


@pytest.fixture
def no_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    """Let the sender pace itself without waiting."""
    monkeypatch.setattr(job, "sleep", lambda seconds: None)


@pytest.fixture
def site(settings: Settings) -> None:
    """Serve the site at ``https://caldart.example.org`` with a contact address set."""
    settings.SITE_URL = "https://caldart.example.org"
    make_site_settings(org_name="CalDART", contact_email="contact@caldart.example.org")


@pytest.fixture
def mission() -> EmailType:
    """Mission email, which a person may turn off; management sends it."""
    return EmailTypeFactory(name="Mission Calls", sender_roles=[MANAGEMENT])


@pytest.fixture
def notices() -> EmailType:
    """An email type nobody may turn off."""
    return EmailTypeFactory(name="Notices", allow_opt_out=False, sender_roles=[MANAGEMENT])


def sent_copy() -> EmailMultiAlternatives:
    """The one copy the sender sent."""
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert isinstance(message, EmailMultiAlternatives)
    return message


def html_of(message: EmailMultiAlternatives) -> str:
    """The HTML alternative of ``message``."""
    content = message.alternatives[0][0]
    assert isinstance(content, str)
    return content


# -- the skip reason -----------------------------------------------------------
def test_an_opted_out_person_is_skipped_in_the_batch(management: User, mission: EmailType) -> None:
    """The batch names the type a person turned off as the reason they are skipped."""
    ann = make_person("ann@example.test", "Ann", "Able")
    EmailOptOutFactory(user=ann, email_type=mission)
    bulk = BulkEmailFactory(sender=management, email_type=mission)
    add_to_batch(bulk, ann)

    assert [row.reason for row in batch.batch_rows(bulk)] == ["Opted out of Mission Calls"]


def test_an_opt_out_of_another_type_does_not_skip(management: User, mission: EmailType) -> None:
    """Turning one type off leaves every other arriving."""
    ann = make_person("ann@example.test", "Ann", "Able")
    EmailOptOutFactory(user=ann, email_type=EmailTypeFactory(name="Board"))
    bulk = BulkEmailFactory(sender=management, email_type=mission)
    add_to_batch(bulk, ann)

    assert [row.reason for row in batch.batch_rows(bulk)] == [""]


def test_an_opt_out_of_a_type_that_no_longer_allows_one_does_not_skip(
    management: User, notices: EmailType
) -> None:
    """An opt-out kept from before the type stopped allowing one does not apply."""
    ann = make_person("ann@example.test", "Ann", "Able")
    EmailOptOutFactory(user=ann, email_type=notices)
    bulk = BulkEmailFactory(sender=management, email_type=notices)
    add_to_batch(bulk, ann)

    assert [row.reason for row in batch.batch_rows(bulk)] == [""]


@pytest.mark.usefixtures("no_pause")
def test_an_opt_out_made_after_queuing_skips_the_copy_when_it_starts(
    management: User, mission: EmailType
) -> None:
    """The send freezes the batch with the opt-outs as they are when it starts."""
    ann = make_person("ann@example.test", "Ann", "Able")
    bea = make_person("bea@example.test", "Bea", "Bell")
    bulk = BulkEmailFactory(
        sender=management, email_type=mission, status=BulkEmailStatus.QUEUED, start_at=NOW
    )
    add_to_batch(bulk, ann, bea)
    EmailOptOutFactory(user=bea, email_type=mission)

    job.run_sender(now=NOW)

    assert [(row.email, row.status, row.reason) for row in bulk.recipients.order_by("email")] == [
        ("ann@example.test", RecipientStatus.SENT, ""),
        ("bea@example.test", RecipientStatus.SKIPPED, "Opted out of Mission Calls"),
    ]


# -- what a copy carries ---------------------------------------------------------
@pytest.mark.usefixtures("site", "no_pause")
def test_a_bulk_copy_carries_the_unsubscribe_headers(management: User, mission: EmailType) -> None:
    """A copy of a type recipients may turn off carries both headers, for that person."""
    ann = make_person("ann@example.test", "Ann", "Able")
    bulk = BulkEmailFactory(
        sender=management, email_type=mission, status=BulkEmailStatus.QUEUED, start_at=NOW
    )
    add_to_batch(bulk, ann)

    job.run_sender(now=NOW)

    message = sent_copy().message()
    assert message["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    link = str(message["List-Unsubscribe"]).split(">")[0].removeprefix("<")
    token = link.removeprefix("https://caldart.example.org/mail/unsubscribe/")
    assert read_token(token) == (ann, mission)


@pytest.mark.usefixtures("no_pause")
def test_the_unsubscribe_header_goes_out_as_plain_text(
    management: User, mission: EmailType, settings: Settings
) -> None:
    """A link longer than a mail line is written as itself, never as an encoded word.

    Mail programs read ``List-Unsubscribe`` as angle-bracketed addresses, which an
    RFC 2047 encoded word would hide from them.
    """
    settings.SITE_URL = "https://caldart.example.org/a-long-prefix-for-a-shared-host"
    make_site_settings(org_name="CalDART", contact_email="contact@caldart.example.org")
    ann = make_person("ann@example.test", "Ann", "Able")
    bulk = BulkEmailFactory(
        sender=management, email_type=mission, status=BulkEmailStatus.QUEUED, start_at=NOW
    )
    add_to_batch(bulk, ann)

    job.run_sender(now=NOW)

    raw = sent_copy().message(policy=email.policy.SMTP).as_bytes()
    prefix = b"List-Unsubscribe: <https://caldart.example.org/a-long-prefix-for-a-shared-host"
    assert prefix + b"/mail/unsubscribe/" in raw
    assert b"=?utf-8?" not in raw.split(b"\r\n\r\n")[0]


@pytest.mark.usefixtures("site", "no_pause")
def test_a_bulk_copy_footer_offers_the_link(management: User, mission: EmailType) -> None:
    """Both bodies end with the footer line and the recipient's unsubscribe link."""
    ann = make_person("ann@example.test", "Ann", "Able")
    bulk = BulkEmailFactory(
        sender=management, email_type=mission, status=BulkEmailStatus.QUEUED, start_at=NOW
    )
    add_to_batch(bulk, ann)

    job.run_sender(now=NOW)

    message = sent_copy()
    line = (
        "You receive Mission Calls email from CalDART because you have not turned it off. "
        "To stop it, unsubscribe here: https://caldart.example.org/mail/unsubscribe/"
    )
    assert line in str(message.body)
    assert "Unsubscribe from Mission Calls email</a>" in html_of(message)


@pytest.mark.usefixtures("site")
def test_a_type_that_cannot_be_turned_off_carries_no_headers(
    management: User, notices: EmailType
) -> None:
    """Its copy has no unsubscribe header, and its footer says why it was sent."""
    ann = make_person("ann@example.test", "Ann", "Able")
    bulk = BulkEmailFactory(sender=management, email_type=notices)
    (row,) = add_to_batch(bulk, ann)

    copy = render_copy(bulk, row)

    assert copy.headers == {}
    assert (
        "CalDART sends Notices email to everyone it writes to, so it cannot be turned off."
        in copy.text
    )


# -- choosing the type ------------------------------------------------------------
def test_the_type_is_stored_and_shown(management_client: APIClient, management: User) -> None:
    """``PATCH`` stores the type, and the email answers with its id and name."""
    mission = EmailTypeFactory(name="Mission Calls", sender_roles=[MANAGEMENT])
    bulk = BulkEmailFactory(sender=management, email_type=None)

    response = management_client.patch(detail_url(bulk), {"email_type": mission.pk}, format="json")

    assert (response.json()["email_type"], response.json()["email_type_name"]) == (
        mission.pk,
        "Mission Calls",
    )


def test_a_draft_starts_with_no_type(management_client: APIClient) -> None:
    """A fresh draft has no type until the sender chooses one."""
    response = management_client.post("/api/v1/bulk-email/drafts", format="json")

    assert (response.json()["email_type"], response.json()["email_type_name"]) == (None, "")


def test_the_lists_show_the_type(management_client: APIClient, management: User) -> None:
    """Drafts & scheduled name each email's type."""
    mission = EmailTypeFactory(name="Mission Calls", sender_roles=[MANAGEMENT])
    BulkEmailFactory(sender=management, email_type=mission)

    response = management_client.get("/api/v1/bulk-email/drafts")

    assert [row["email_type_name"] for row in response.json()] == ["Mission Calls"]


def test_a_type_the_sender_may_not_send_is_refused(
    management_client: APIClient, management: User
) -> None:
    """Only a type whose senders include the caller's role can be chosen."""
    leaders = EmailTypeFactory(name="Leaders only", sender_roles=[DART_LEADER])
    bulk = BulkEmailFactory(sender=management, email_type=None)

    response = management_client.patch(detail_url(bulk), {"email_type": leaders.pk}, format="json")

    assert response.status_code == 400
    assert response.json() == {
        "email_type": ["You cannot send Leaders only email. Choose another type."]
    }


def test_the_batch_csv_names_the_type(management_client: APIClient, management: User) -> None:
    """Each line of the batch CSV carries the email's type."""
    mission = EmailTypeFactory(name="Mission Calls", sender_roles=[MANAGEMENT])
    bulk = BulkEmailFactory(sender=management, email_type=mission)
    add_to_batch(bulk, make_person("ann@example.test", "Ann", "Able"))

    rows = read_csv(management_client.get(f"{detail_url(bulk)}/batch.csv"))

    assert [row[-1] for row in rows] == ["Email type", "Mission Calls"]


# -- sending -------------------------------------------------------------------------
def test_send_is_refused_without_a_type(management_client: APIClient, management: User) -> None:
    """**Send** asks for a type first, and nothing is queued."""
    bulk = BulkEmailFactory(sender=management, email_type=None)
    add_to_batch(bulk, make_person("ann@example.test"))

    response = management_client.post(f"{detail_url(bulk)}/send", {}, format="json")

    assert response.status_code == 400
    assert response.json() == {"email_type": ["Choose a type."]}
    bulk.refresh_from_db()
    assert bulk.status == BulkEmailStatus.DRAFT


def test_send_is_refused_for_a_type_the_actor_may_no_longer_send(
    management: User, mission: EmailType
) -> None:
    """A type whose senders changed after it was chosen cannot be sent by the old one."""
    bulk = BulkEmailFactory(sender=management, email_type=mission)
    add_to_batch(bulk, make_person("ann@example.test"))
    mission.sender_roles = [DART_LEADER]
    mission.save()

    with pytest.raises(DomainValidationError, match="You cannot send Mission Calls email"):
        drafts.queue(bulk, confirm_count=None, start_at=None, actor=management)


def test_a_system_administrator_sends_any_type(system_admin: User) -> None:
    """A type nobody is named for is still the system administrator's to send."""
    board = EmailTypeFactory(name="Board", sender_roles=[])
    bulk = BulkEmailFactory(sender=system_admin, email_type=board)
    add_to_batch(bulk, make_person("ann@example.test"))

    queued = drafts.queue(bulk, confirm_count=None, start_at=None, actor=system_admin)

    assert queued.status == BulkEmailStatus.QUEUED


@pytest.fixture
def colleague() -> User:
    """Another CalDART manager, who also leads a DART, and owns drafts of their own."""
    return UserFactory(email="colleague@example.test", roles=[MEMBER, MANAGEMENT, DART_LEADER])


def test_a_manager_types_and_sends_a_colleagues_draft(
    management_client: APIClient, colleague: User, mission: EmailType
) -> None:
    """The caller's own roles decide: a manager may type and send another's draft."""
    bulk = BulkEmailFactory(sender=colleague, email_type=None)
    add_to_batch(bulk, make_person("ann@example.test"))

    typed = management_client.patch(detail_url(bulk), {"email_type": mission.pk}, format="json")
    sent = management_client.post(f"{detail_url(bulk)}/send", {}, format="json")

    assert (typed.status_code, sent.json()["status"]) == (200, BulkEmailStatus.QUEUED)


def test_a_caller_without_the_types_role_cannot_choose_it_for_anothers_draft(
    management_client: APIClient, colleague: User
) -> None:
    """A type only DART leaders send is refused to a manager who leads no DART."""
    leaders = EmailTypeFactory(name="Leaders only", sender_roles=[DART_LEADER])
    bulk = BulkEmailFactory(sender=colleague, email_type=None)

    response = management_client.patch(detail_url(bulk), {"email_type": leaders.pk}, format="json")

    assert response.json() == {
        "email_type": ["You cannot send Leaders only email. Choose another type."]
    }


def test_a_caller_without_the_types_role_cannot_send_anothers_draft(
    management_client: APIClient, colleague: User
) -> None:
    """A leader chose the type; a manager who leads no DART may not send it."""
    leaders = EmailTypeFactory(name="Leaders only", sender_roles=[DART_LEADER])
    bulk = BulkEmailFactory(sender=colleague, email_type=leaders)
    add_to_batch(bulk, make_person("ann@example.test"))

    response = management_client.post(f"{detail_url(bulk)}/send", {}, format="json")

    assert response.status_code == 400
    assert response.json() == {
        "email_type": ["You cannot send Leaders only email. Choose another type."]
    }


# -- the sender checks the type again ----------------------------------------------
@pytest.mark.usefixtures("no_pause")
def test_an_opt_out_made_during_the_send_skips_the_copy(
    management: User, mission: EmailType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An opt-out recorded while the paced send is under way is honored for its copy."""
    ann = make_person("ann@example.test", "Ann", "Able")
    bea = make_person("bea@example.test", "Bea", "Bell")
    bulk = BulkEmailFactory(
        sender=management, email_type=mission, status=BulkEmailStatus.QUEUED, start_at=NOW
    )
    add_to_batch(bulk, ann, bea)

    # Bea turns Mission off during the pause before her copy.
    def opt_bea_out(seconds: float) -> None:
        """Record Bea's opt-out, as she might while the sender waits."""
        EmailOptOutFactory(user=bea, email_type=mission)

    monkeypatch.setattr(job, "sleep", opt_bea_out)
    job.run_sender(now=NOW)

    bulk.refresh_from_db()
    rows = [(row.email, row.status, row.reason) for row in bulk.recipients.order_by("email")]
    assert rows == [
        ("ann@example.test", RecipientStatus.SENT, ""),
        ("bea@example.test", RecipientStatus.SKIPPED, "Opted out of Mission Calls"),
    ]
    assert (bulk.sent_count, bulk.skipped_count, bulk.status) == (1, 1, BulkEmailStatus.SENT)


@pytest.mark.usefixtures("no_pause")
def test_an_opt_out_made_while_stopped_is_honored_by_send_the_rest(
    management: User, mission: EmailType
) -> None:
    """Copies queued again by **Send the rest** skip a person who opted out meanwhile."""
    ann = make_person("ann@example.test", "Ann", "Able")
    bulk = BulkEmailFactory(
        sender=management, email_type=mission, status=BulkEmailStatus.QUEUED, start_at=NOW
    )
    (row,) = add_to_batch(bulk, ann)
    bulk.status = BulkEmailStatus.STOPPED
    bulk.started_at = NOW
    bulk.save()
    row.status = RecipientStatus.STOPPED
    row.save()
    EmailOptOutFactory(user=ann, email_type=mission)

    drafts.resume(bulk, actor=management, now=NOW)
    job.run_sender(now=NOW)

    row.refresh_from_db()
    assert (row.status, row.reason) == (RecipientStatus.SKIPPED, "Opted out of Mission Calls")
    assert len(mail.outbox) == 0


@pytest.mark.usefixtures("no_pause")
def test_a_sender_who_lost_the_role_has_the_email_returned_to_draft(
    management: User, mission: EmailType, audit_log: pytest.LogCaptureFixture
) -> None:
    """At its start time, an email whose sender may no longer send its type goes back."""
    bulk = BulkEmailFactory(sender=management, email_type=mission)
    add_to_batch(bulk, make_person("ann@example.test"))
    with freeze_time(NOW):
        drafts.queue(bulk, confirm_count=None, start_at=None, actor=management)
    management.remove_role(MANAGEMENT)

    with freeze_time(NOW + timedelta(seconds=120)):
        job.run_sender()

    bulk.refresh_from_db()
    assert (bulk.status, bulk.start_at, len(mail.outbox)) == (BulkEmailStatus.DRAFT, None, 0)
    assert bulk.not_sent_reason == (
        "This email was not sent: you can no longer send Mission Calls email. Choose "
        "another type and send again."
    )
    assert audit_messages(audit_log, logging.WARNING) == [
        f"action=bulk_email.refused actor=command target={bulk.pk} reason=type_not_sendable"
    ]


@pytest.mark.usefixtures("no_pause")
def test_an_email_whose_sender_was_deleted_is_returned_to_draft(
    mission: EmailType, audit_log: pytest.LogCaptureFixture
) -> None:
    """An email whose sender's account is gone is not sent."""
    sender = UserFactory(email="gone@example.test", roles=[MEMBER, MANAGEMENT])
    bulk = BulkEmailFactory(sender=sender, email_type=mission)
    add_to_batch(bulk, make_person("ann@example.test"))
    drafts.queue(bulk, confirm_count=None, start_at=None, actor=sender, now=NOW)
    sender.delete()

    job.run_sender(now=NOW + timedelta(seconds=120))

    bulk.refresh_from_db()
    assert (bulk.status, len(mail.outbox)) == (BulkEmailStatus.DRAFT, 0)
    assert audit_messages(audit_log, logging.WARNING) == [
        f"action=bulk_email.refused actor=command target={bulk.pk} reason=sender_deleted"
    ]


@pytest.mark.usefixtures("no_pause")
def test_a_refused_email_does_not_hold_back_the_next(management: User, mission: EmailType) -> None:
    """The run moves on to the next due email after returning one to draft."""
    refused = BulkEmailFactory(
        sender=UserFactory(email="plain@example.test", roles=[MEMBER]),
        email_type=mission,
        status=BulkEmailStatus.QUEUED,
        start_at=NOW,
    )
    add_to_batch(refused, make_person("ann@example.test"))
    good = BulkEmailFactory(
        sender=management, email_type=mission, status=BulkEmailStatus.QUEUED, start_at=NOW
    )
    add_to_batch(good, make_person("bea@example.test", "Bea", "Bell"))

    job.run_sender(now=NOW)

    refused.refresh_from_db()
    good.refresh_from_db()
    assert (refused.status, good.status) == (BulkEmailStatus.DRAFT, BulkEmailStatus.SENT)


def test_sending_again_clears_the_not_sent_notice(management: User, mission: EmailType) -> None:
    """Once the sender queues it again, the email no longer says it was not sent."""
    bulk = BulkEmailFactory(
        sender=management, email_type=mission, not_sent_reason="This email was not sent."
    )
    add_to_batch(bulk, make_person("ann@example.test"))

    queued = drafts.queue(bulk, confirm_count=None, start_at=None, actor=management, now=NOW)

    assert queued.not_sent_reason == ""


def test_the_drafts_list_carries_the_not_sent_notice(
    management_client: APIClient, management: User, mission: EmailType
) -> None:
    """The notice reaches the Drafts & scheduled list."""
    BulkEmailFactory(sender=management, email_type=mission, not_sent_reason="Not sent.")

    response = management_client.get("/api/v1/bulk-email/drafts")

    assert [row["not_sent_reason"] for row in response.json()] == ["Not sent."]


@pytest.mark.usefixtures("no_pause")
def test_send_the_rest_by_a_sender_who_lost_the_role_stops_again(
    management: User, mission: EmailType
) -> None:
    """Copies queued again are not sent once the sender may no longer send the type."""
    bulk = BulkEmailFactory(
        sender=management,
        email_type=mission,
        status=BulkEmailStatus.STOPPED,
        started_at=NOW,
    )
    (row,) = add_to_batch(bulk, make_person("ann@example.test"))
    row.status = RecipientStatus.STOPPED
    row.save()
    drafts.resume(bulk, actor=management, now=NOW)
    management.remove_role(MANAGEMENT)

    job.run_sender(now=NOW)

    bulk.refresh_from_db()
    row.refresh_from_db()
    assert (bulk.status, row.status, len(mail.outbox)) == (
        BulkEmailStatus.STOPPED,
        RecipientStatus.STOPPED,
        0,
    )
