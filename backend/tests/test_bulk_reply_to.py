"""Where replies to a bulk email go: the ``Reply-To`` address and its default.

A fresh draft starts with ``BULK_EMAIL_REPLY_TO``, or the sender's own address when that
setting is blank; ``PATCH`` changes it to any valid address, blank meaning the default.
Every copy carries it as its ``Reply-To`` header while ``From`` stays
``DEFAULT_FROM_EMAIL``, **Send** records the address the copies carry, and an address
that is not valid is refused on save and on send.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from django.core import mail
from pytest_django import Settings
from rest_framework.test import APIClient

from apps.bulk_email import drafts, job
from apps.bulk_email.checks import REPLY_TO, ChecksFailedError
from apps.bulk_email.models import BulkEmail, BulkEmailStatus
from apps.bulk_email.reply_to import (
    INVALID_MESSAGE,
    claimed_reply_to,
    default_reply_to,
    reply_to_for,
    reply_to_problem,
)
from tests.factories import BulkEmailFactory, add_to_batch, make_person

if TYPE_CHECKING:
    from apps.accounts.models import User

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 4, 6, 17, 0, tzinfo=UTC)

#: The shared mailbox an installation may send replies to.
OPERATIONS = "operations@caldart.example.org"


def detail_url(bulk: BulkEmail, action: str = "") -> str:
    """``/api/v1/bulk-email/{id}`` for ``bulk``, with ``/<action>`` when given."""
    suffix = f"/{action}" if action != "" else ""
    return f"/api/v1/bulk-email/{bulk.pk}{suffix}"


@pytest.fixture(autouse=True)
def _no_pacing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Let the sender send without pausing between copies."""
    monkeypatch.setattr(job, "sleep", lambda seconds: None)


@pytest.fixture
def own_address(settings: Settings) -> None:
    """No installation default: replies go to each sender's own address."""
    settings.BULK_EMAIL_REPLY_TO = ""


@pytest.fixture
def shared_mailbox(settings: Settings) -> None:
    """The installation sends replies to :data:`OPERATIONS` by default."""
    settings.BULK_EMAIL_REPLY_TO = OPERATIONS


def send_to_ann(bulk: BulkEmail) -> None:
    """Put Ann in ``bulk``'s batch, queue it to start at :data:`NOW`, and send it."""
    add_to_batch(bulk, make_person("ann@example.test", "Ann", "Able"))
    BulkEmail.objects.filter(pk=bulk.pk).update(status=BulkEmailStatus.QUEUED, start_at=NOW)
    job.run_sender(now=NOW)


# -- the default ------------------------------------------------------------------
@pytest.mark.usefixtures("shared_mailbox")
def test_the_default_is_the_setting(management: User) -> None:
    """With ``BULK_EMAIL_REPLY_TO`` set, the default is that address."""
    assert default_reply_to(management) == OPERATIONS


@pytest.mark.usefixtures("own_address")
def test_a_blank_setting_makes_the_default_the_sender_s_own_address(management: User) -> None:
    """With the setting blank, the default is the sender's own address."""
    assert default_reply_to(management) == management.email


@pytest.mark.usefixtures("own_address")
def test_a_deleted_sender_with_a_blank_setting_has_no_default() -> None:
    """Nobody to reply to is ``""``, which the checks then refuse."""
    assert default_reply_to(None) == ""


@pytest.mark.usefixtures("shared_mailbox")
def test_a_fresh_draft_starts_with_the_default(
    management_client: APIClient, management: User
) -> None:
    """``POST /bulk-email/drafts`` fills ``reply_to`` in, for the sender to change."""
    body = management_client.post("/api/v1/bulk-email/drafts").json()
    assert (body["reply_to"], body["default_reply_to"]) == (OPERATIONS, OPERATIONS)


@pytest.mark.usefixtures("own_address")
def test_the_email_answers_its_sender_s_default(
    management_client: APIClient, management: User
) -> None:
    """``default_reply_to`` is the sender's address while the setting is blank."""
    bulk = BulkEmailFactory(sender=management, reply_to="")
    body = management_client.get(detail_url(bulk)).json()
    assert (body["reply_to"], body["default_reply_to"]) == ("", management.email)


def test_a_chosen_address_wins_over_the_default(management: User) -> None:
    """``reply_to_for`` is the email's own address when it has one."""
    bulk = BulkEmailFactory(sender=management, reply_to="marin@example.test")
    assert reply_to_for(bulk) == "marin@example.test"


@pytest.mark.usefixtures("shared_mailbox")
def test_a_blank_address_means_the_default(management: User) -> None:
    """``reply_to_for`` falls back to the default when the email names none."""
    bulk = BulkEmailFactory(sender=management, reply_to="")
    assert reply_to_for(bulk) == OPERATIONS


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("pat@example.org", None),
        ("not an address", INVALID_MESSAGE.format(address="not an address")),
    ],
    ids=["valid", "invalid"],
)
def test_an_address_that_is_not_valid_is_a_problem(address: str, expected: str | None) -> None:
    """``reply_to_problem`` names an address Django's validator refuses."""
    assert reply_to_problem(address) == expected


# -- saving -----------------------------------------------------------------------
def test_patch_saves_a_chosen_address(management_client: APIClient, management: User) -> None:
    """Any valid address may be chosen, trimmed."""
    bulk = BulkEmailFactory(sender=management)
    response = management_client.patch(
        detail_url(bulk), {"reply_to": "  marin@example.test "}, format="json"
    )
    assert response.json()["reply_to"] == "marin@example.test"


def test_patch_saves_a_blank_address(management_client: APIClient, management: User) -> None:
    """A blank address is saved, and stands for the default."""
    bulk = BulkEmailFactory(sender=management, reply_to="marin@example.test")
    management_client.patch(detail_url(bulk), {"reply_to": ""}, format="json")
    bulk.refresh_from_db()
    assert bulk.reply_to == ""


def test_patch_refuses_an_address_that_is_not_valid(
    management_client: APIClient, management: User
) -> None:
    """400 keyed ``reply_to``, and the saved address stays."""
    bulk = BulkEmailFactory(sender=management, reply_to="marin@example.test")
    response = management_client.patch(detail_url(bulk), {"reply_to": "marin@"}, format="json")
    assert (response.status_code, response.json()) == (
        400,
        {"reply_to": ["Enter a valid email address."]},
    )


# -- sending ----------------------------------------------------------------------
@pytest.mark.usefixtures("shared_mailbox")
def test_a_copy_carries_the_default(management: User) -> None:
    """An email with no address of its own goes out with the installation's default."""
    send_to_ann(BulkEmailFactory(sender=management, reply_to=""))
    assert mail.outbox[0].reply_to == [OPERATIONS]


@pytest.mark.usefixtures("own_address")
def test_a_copy_carries_the_sender_s_own_address(management: User) -> None:
    """With no default set, replies go to the sender."""
    send_to_ann(BulkEmailFactory(sender=management, reply_to=""))
    assert mail.outbox[0].reply_to == [management.email]


@pytest.mark.usefixtures("shared_mailbox")
def test_a_copy_carries_a_chosen_address(management: User) -> None:
    """An address the sender chose wins over the default."""
    send_to_ann(BulkEmailFactory(sender=management, reply_to="marin@example.test"))
    assert mail.outbox[0].reply_to == ["marin@example.test"]


@pytest.mark.usefixtures("shared_mailbox")
def test_from_stays_the_site_s_address(settings: Settings, management: User) -> None:
    """``Reply-To`` never changes ``From``, so SPF, DKIM, and DMARC still align."""
    send_to_ann(BulkEmailFactory(sender=management, reply_to="marin@example.test"))
    assert mail.outbox[0].from_email == settings.DEFAULT_FROM_EMAIL


@pytest.mark.usefixtures("shared_mailbox")
def test_send_records_the_address_the_copies_carry(
    management_client: APIClient, management: User
) -> None:
    """**Send** stores the default on an email that named none, for the history."""
    bulk = BulkEmailFactory(sender=management, reply_to="")
    add_to_batch(bulk, make_person("ann@example.test"))
    body = management_client.post(detail_url(bulk, "send"), {}, format="json").json()
    assert body["reply_to"] == OPERATIONS


def test_the_sent_email_shows_its_address(
    management_client: APIClient, management: User, settings: Settings
) -> None:
    """Changing the default later does not change what a sent email went with."""
    settings.BULK_EMAIL_REPLY_TO = OPERATIONS
    bulk = BulkEmailFactory(sender=management, reply_to="")
    add_to_batch(bulk, make_person("ann@example.test"))
    drafts.queue(bulk, confirm_count=None, start_at=None, actor=management, now=NOW)
    job.run_sender(now=NOW + timedelta(hours=1))
    settings.BULK_EMAIL_REPLY_TO = "elsewhere@example.test"
    assert management_client.get(detail_url(bulk)).json()["reply_to"] == OPERATIONS


def test_send_refuses_a_default_that_is_not_valid(
    management_client: APIClient, management: User, settings: Settings
) -> None:
    """A default that is not an address is a 400 under ``checks``; nothing queues."""
    settings.BULK_EMAIL_REPLY_TO = "operations"
    bulk = BulkEmailFactory(sender=management, reply_to="")
    add_to_batch(bulk, make_person("ann@example.test"))
    response = management_client.post(detail_url(bulk, "send"), {}, format="json")
    assert (response.status_code, response.json()) == (
        400,
        {
            "checks": [
                {
                    "code": REPLY_TO,
                    "level": "error",
                    "message": INVALID_MESSAGE.format(address="operations"),
                }
            ]
        },
    )


def test_a_refused_address_leaves_the_email_a_draft(management: User, settings: Settings) -> None:
    """``drafts.queue`` raises the checks' errors and changes nothing."""
    settings.BULK_EMAIL_REPLY_TO = "operations"
    bulk = BulkEmailFactory(sender=management, reply_to="")
    add_to_batch(bulk, make_person("ann@example.test"))
    with pytest.raises(ChecksFailedError, match="operations, which is not a valid"):
        drafts.queue(bulk, confirm_count=None, start_at=None, actor=management, now=NOW)
    bulk.refresh_from_db()
    assert bulk.status == BulkEmailStatus.DRAFT


# -- at claim time ------------------------------------------------------------------
@pytest.mark.usefixtures("own_address")
def test_a_reply_to_blanked_after_send_is_resolved_as_the_send_starts(
    management_client: APIClient, management: User, settings: Settings
) -> None:
    """A queued email patched back to blank takes the default as it is at the claim."""
    bulk = BulkEmailFactory(sender=management, reply_to="")
    add_to_batch(bulk, make_person("ann@example.test"))
    drafts.queue(bulk, confirm_count=None, start_at=None, actor=management, now=NOW)
    management_client.patch(detail_url(bulk), {"reply_to": ""}, format="json")
    settings.BULK_EMAIL_REPLY_TO = OPERATIONS
    job.run_sender(now=NOW + timedelta(hours=1))
    bulk.refresh_from_db()
    assert (bulk.reply_to, mail.outbox[0].reply_to) == (OPERATIONS, [OPERATIONS])


@pytest.mark.usefixtures("own_address")
def test_a_deleted_sender_with_no_default_falls_back_to_the_site_s_address(
    settings: Settings,
) -> None:
    """``claimed_reply_to`` answers ``DEFAULT_FROM_EMAIL``'s address when nothing else."""
    settings.DEFAULT_FROM_EMAIL = "CalDART <noreply@caldart.example.org>"
    bulk = BulkEmailFactory(sender=None, reply_to="")
    assert claimed_reply_to(bulk) == "noreply@caldart.example.org"


@pytest.mark.usefixtures("own_address")
def test_with_no_address_to_resolve_copies_reply_to_the_site_s_address(
    management: User, settings: Settings
) -> None:
    """A sender with no address of their own and no default: the site's, recorded."""
    settings.DEFAULT_FROM_EMAIL = "CalDART <noreply@caldart.example.org>"
    type(management).objects.filter(pk=management.pk).update(email="")
    management.refresh_from_db()
    bulk = BulkEmailFactory(sender=management, reply_to="")
    send_to_ann(bulk)
    bulk.refresh_from_db()
    assert (bulk.reply_to, mail.outbox[0].reply_to) == (
        "noreply@caldart.example.org",
        ["noreply@caldart.example.org"],
    )


def test_an_invalid_default_at_claim_falls_back_and_is_logged(
    management: User, settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    """A default that is not an address when the send starts is replaced, and logged."""
    settings.DEFAULT_FROM_EMAIL = "CalDART <noreply@caldart.example.org>"
    settings.BULK_EMAIL_REPLY_TO = "operations"
    bulk = BulkEmailFactory(sender=management, reply_to="")
    with caplog.at_level("WARNING", logger="apps.bulk_email.reply_to"):
        send_to_ann(bulk)
    assert caplog.messages == [
        f"bulk email {bulk.pk} has no usable Reply-To; replies go to DEFAULT_FROM_EMAIL"
    ]
