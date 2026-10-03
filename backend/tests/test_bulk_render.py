"""Each recipient's copy of an HTML bulk email: filling in, checking, and previewing.

``apps.bulk_email.render`` builds a copy from the sanitized message and one person's
field values, and refuses a message whose tokens cannot be filled in; the sender stores
the values on each row as the copy goes, so a copy is rebuilt as it went.  ``POST
/bulk-email/{id}/preview`` shows one person's copy at a time, and a save, a preview,
and a send each refuse a token that cannot be filled in.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from django.core import mail
from django.core.mail import EmailMultiAlternatives
from rest_framework.test import APIClient

from apps.accounts.roles import MANAGEMENT, SYSTEM_ADMIN
from apps.bulk_email import job
from apps.bulk_email.fields import unknown_token_message
from apps.bulk_email.models import BulkEmail, BulkEmailRecipient, BulkEmailStatus
from apps.bulk_email.preview import NOT_IN_BATCH_MESSAGE
from apps.bulk_email.render import (
    check_message,
    render_copy,
    render_message,
    retype_message,
)
from tests.conftest import role_matrix
from tests.factories import BulkEmailFactory, DartFactory, add_to_batch, make_person

if TYPE_CHECKING:
    from apps.accounts.models import User

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 4, 6, 17, 0, tzinfo=UTC)

#: A message that fills in two fields, one of them with a fallback.
GREETING = "<p>Dear {first_name|friend},</p><p>Your DART is <strong>{dart_name}</strong>.</p>"


def detail_url(bulk: BulkEmail, action: str = "") -> str:
    """``/bulk-email/{id}`` for ``bulk``, with ``/<action>`` when given."""
    suffix = f"/{action}" if action != "" else ""
    return f"/api/v1/bulk-email/{bulk.pk}{suffix}"


@pytest.fixture(autouse=True)
def _no_pacing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Let the sender send without pausing between copies."""
    monkeypatch.setattr(job, "sleep", lambda seconds: None)


@pytest.fixture
def ann() -> User:
    """Ann Able, of the Marin DART."""
    return make_person("ann@example.test", "Ann", "Able", dart=DartFactory(name="Marin"))


@pytest.fixture
def bea() -> User:
    """Bea Bell, of the Napa DART."""
    return make_person("bea@example.test", "Bea", "Bell", dart=DartFactory(name="Napa"))


@pytest.fixture
def greeting(management: User, ann: User, bea: User) -> BulkEmail:
    """A draft greeting Ann and Bea by name and DART, from CalDART management."""
    bulk = BulkEmailFactory(sender=management, subject="Hello {first_name}", body=GREETING)
    add_to_batch(bulk, ann, bea)
    return bulk


def send_now(bulk: BulkEmail) -> None:
    """Queue ``bulk`` to start at :data:`NOW` and run the sender once."""
    BulkEmail.objects.filter(pk=bulk.pk).update(status=BulkEmailStatus.QUEUED, start_at=NOW)
    job.run_sender(now=NOW)


def html_of(message: object) -> str:
    """The HTML body of a sent ``message``."""
    assert isinstance(message, EmailMultiAlternatives)
    return str(message.alternatives[0][0])


# --------------------------------------------------------------------------
# Building a copy
# --------------------------------------------------------------------------
def test_a_copy_fills_each_value_into_the_subject() -> None:
    """The subject takes the value as it is."""
    copy = render_message("Hi {first_name}", "<p>x</p>", {"first_name": "Pat & Co"})
    assert copy.subject == "Hi Pat & Co"


def test_a_copy_fills_each_value_into_the_html_escaped() -> None:
    """The HTML body takes each value escaped, so markup in a name is text."""
    copy = render_message("x", "<p>Hi {first_name}</p>", {"first_name": "<b>Pat</b>"})
    assert "<p>Hi &lt;b&gt;Pat&lt;/b&gt;</p>" in copy.html


def test_a_copy_fills_each_value_into_the_text_as_it_is() -> None:
    """The plain-text body is derived from the HTML and takes each value unescaped."""
    copy = render_message("x", "<p>Hi <em>{first_name}</em></p>", {"first_name": "<b>Pat</b>"})
    assert copy.text.startswith("Hi <b>Pat</b>\n")


def test_a_copy_sanitizes_the_message() -> None:
    """A script in the stored message never reaches a copy."""
    copy = render_message("x", "<p>Hi</p><script>alert(1)</script>", {})
    assert "alert" not in copy.html


def test_a_subject_value_never_breaks_the_line() -> None:
    """A line break inside a value reads as a space in the subject."""
    copy = render_message("For {first_name}", "<p>x</p>", {"first_name": "Pat\nLee"})
    assert copy.subject == "For Pat Lee"


def test_template_syntax_arrives_literally_in_the_html() -> None:
    """``{{ }}`` and ``{% %}`` in the message are never evaluated in the HTML body."""
    copy = render_message("x", "<p>{{ first_name }} {% now Y %}</p>", {"first_name": "Pat"})
    assert "<p>{{ first_name }} {% now Y %}</p>" in copy.html


def test_template_syntax_arrives_literally_in_the_text() -> None:
    """``{{ }}`` and ``{% %}`` in the message are never evaluated in the text body."""
    copy = render_message("x", "<p>{{ first_name }} {% now Y %}</p>", {"first_name": "Pat"})
    assert copy.text.startswith("{{ first_name }} {% now Y %}\n")


def test_without_values_the_tokens_stay_as_written() -> None:
    """The history's rendering leaves every token in place."""
    copy = render_message("Hi {first_name}", "<p>Dear {first_name|friend}</p>", None)
    assert (copy.subject, "<p>Dear {first_name|friend}</p>" in copy.html) == (
        "Hi {first_name}",
        True,
    )


# --------------------------------------------------------------------------
# Values stored at send time
# --------------------------------------------------------------------------
def test_each_copy_is_filled_in_for_its_recipient(greeting: BulkEmail) -> None:
    """Ann's copy greets Ann with her DART, and Bea's greets Bea with hers."""
    send_now(greeting)
    by_address = {message.to[0]: message for message in mail.outbox}
    assert [
        by_address["ann@example.test"].subject,
        "Dear Ann," in html_of(by_address["ann@example.test"]),
        "<strong>Napa</strong>" in html_of(by_address["bea@example.test"]),
    ] == ["Hello Ann", True, True]


def test_each_recipients_values_are_stored_at_send_time(greeting: BulkEmail) -> None:
    """Each row keeps the values of the fields the message uses, and no others."""
    send_now(greeting)
    row = greeting.recipients.get(email="ann@example.test")
    assert row.values == {"first_name": "Ann", "dart_name": "Marin"}


def test_a_rebuilt_copy_reads_as_sent_after_the_profile_changed(
    greeting: BulkEmail, ann: User
) -> None:
    """Rebuilding a sent copy uses the stored values, not the account as it is now."""
    send_now(greeting)
    ann.first_name = "Annie"
    ann.save()
    row = greeting.recipients.get(email="ann@example.test")
    assert render_copy(greeting, row).subject == "Hello Ann"


def test_a_message_without_fields_stores_no_values(management: User, ann: User) -> None:
    """A copy that fills in nothing stores an empty object."""
    bulk = BulkEmailFactory(sender=management)
    add_to_batch(bulk, ann)
    send_now(bulk)
    assert bulk.recipients.get().values == {}


def test_a_copy_for_a_deleted_account_takes_the_fallback(management: User) -> None:
    """A row whose account is gone fills every field in empty: the fallback stands."""
    bulk = BulkEmailFactory(sender=management, body=GREETING)
    row = BulkEmailRecipient(bulk_email=bulk, user=None, values={})
    assert "Dear friend," in render_copy(bulk, row).html


# --------------------------------------------------------------------------
# Checking a message
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("subject", "body", "expected"),
    [
        ("Hi {nickname}", "<p>x</p>", {"subject": unknown_token_message("nickname")}),
        ("x", "<p>{shoe_size}</p>", {"body": unknown_token_message("shoe_size")}),
        (
            "x",
            '<p><a href="https://example.org/{id}">x</a></p>',
            {"body": unknown_token_message("id")},
        ),
        (
            "x",
            "<p><strong>{first</strong>_name}</p>",
            {"body": retype_message("{first_name}")},
        ),
        (
            "x",
            "<p>{first_name|a&lt;b}</p>",
            {"body": retype_message("{first_name|a<b}")},
        ),
        ("{first_name}", GREETING, {}),
        ("x", '<p><a href="https://caldart.org/?d={dart_name}">site</a></p>', {}),
        ("x", '<img src="https://x.example/a.png" alt="{first_name}">', {}),
        ("x", "<p>{{ first_name }} and {{id}}</p>", {}),
    ],
    ids=[
        "unknown-in-subject",
        "unknown-in-body",
        "unknown-in-a-link",
        "split-by-formatting",
        "fallback-with-an-angle-bracket",
        "fields-that-fill-in",
        "field-in-a-link",
        "field-in-an-alt",
        "doubled-braces",
    ],
)
def test_check_message(subject: str, body: str, expected: dict[str, str]) -> None:
    """Each message is refused, by field, exactly when a token cannot be filled in."""
    assert check_message(subject, body) == expected


def test_saving_sanitizes_the_message(management_client: APIClient, greeting: BulkEmail) -> None:
    """``PATCH`` stores the message with scripts and styles taken out."""
    management_client.patch(
        detail_url(greeting),
        {"body": '<p style="color:red" onclick="x()">Hi</p><script>s()</script>'},
        format="json",
    )
    greeting.refresh_from_db()
    assert greeting.body == "<p>Hi</p>"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("subject", "Hi {nickname}", unknown_token_message("nickname")),
        ("body", "<p>{nickname}</p>", unknown_token_message("nickname")),
        ("body", "<p><em>{first</em>_name}</p>", retype_message("{first_name}")),
    ],
    ids=["subject", "body", "split"],
)
def test_saving_refuses_a_token_that_cannot_be_filled_in(
    management_client: APIClient, greeting: BulkEmail, field: str, value: str, message: str
) -> None:
    """``PATCH`` answers 400 naming the token, and keeps the words already saved."""
    response = management_client.patch(detail_url(greeting), {field: value}, format="json")
    assert (response.status_code, response.json()) == (400, {field: [message]})


def test_sending_refuses_a_token_that_cannot_be_filled_in(
    management_client: APIClient, greeting: BulkEmail
) -> None:
    """``POST .../send`` answers 400 naming an unknown token the message holds."""
    BulkEmail.objects.filter(pk=greeting.pk).update(body="<p>{nickname}</p>")
    response = management_client.post(detail_url(greeting, "send"), {}, format="json")
    assert (response.status_code, response.json()) == (
        400,
        {"body": [unknown_token_message("nickname")]},
    )


def test_sending_refuses_a_message_with_no_words(
    management_client: APIClient, greeting: BulkEmail
) -> None:
    """A message of empty paragraphs is no message at all."""
    BulkEmail.objects.filter(pk=greeting.pk).update(body="<p></p><p> </p>")
    response = management_client.post(detail_url(greeting, "send"), {}, format="json")
    assert (response.status_code, response.json()) == (400, {"body": ["Write the message."]})


def test_the_detail_shows_the_message_with_its_tokens(
    management_client: APIClient, greeting: BulkEmail
) -> None:
    """``message_html`` is the whole HTML email, its tokens as written."""
    body = management_client.get(detail_url(greeting)).json()
    assert "<p>Dear {first_name|friend},</p>" in body["message_html"]


# --------------------------------------------------------------------------
# The preview
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("role", "allowed"), role_matrix(MANAGEMENT, SYSTEM_ADMIN))
def test_only_management_previews(
    api_client: APIClient,
    all_role_users: dict[str, User],
    management: User,
    role: str,
    allowed: bool,
) -> None:
    """``POST /bulk-email/{id}/preview`` is for CalDART management and system admins."""
    bulk = BulkEmailFactory(sender=management)
    api_client.force_login(all_role_users[role])
    response = api_client.post(detail_url(bulk, "preview"), {}, format="json")
    assert response.status_code == (200 if allowed else 403)


def test_the_preview_starts_with_the_first_person(
    management_client: APIClient, greeting: BulkEmail
) -> None:
    """With no row named, the preview is the first person's copy, Ann's."""
    body = management_client.post(detail_url(greeting, "preview"), {}, format="json").json()
    bea_row = greeting.recipients.get(email="bea@example.test")
    assert {
        "subject": body["subject"],
        "recipient": body["recipient"]["name"],
        "position": body["position"],
        "count": body["count"],
        "previous_id": body["previous_id"],
        "next_id": body["next_id"],
        "greets": "Dear Ann," in body["html"],
        "text": body["text"].startswith("Dear Ann,\n\nYour DART is Marin."),
    } == {
        "subject": "Hello Ann",
        "recipient": "Ann Able",
        "position": 1,
        "count": 2,
        "previous_id": None,
        "next_id": bea_row.pk,
        "greets": True,
        "text": True,
    }


def test_the_preview_steps_to_the_chosen_person(
    management_client: APIClient, greeting: BulkEmail
) -> None:
    """Naming Bea's row previews her copy, with Ann's row before it and none after."""
    ann_row = greeting.recipients.get(email="ann@example.test")
    bea_row = greeting.recipients.get(email="bea@example.test")
    body = management_client.post(
        detail_url(greeting, "preview"), {"recipient_id": bea_row.pk}, format="json"
    ).json()
    assert (body["subject"], body["position"], body["previous_id"], body["next_id"]) == (
        "Hello Bea",
        2,
        ann_row.pk,
        None,
    )


def test_the_preview_of_an_empty_batch_is_the_senders_own(
    management_client: APIClient, management: User
) -> None:
    """With nobody in the batch, the preview fills in the sender's own values."""
    bulk = BulkEmailFactory(sender=management, subject="Hi {first_name}")
    body = management_client.post(detail_url(bulk, "preview"), {}, format="json").json()
    assert (body["subject"], body["recipient"]["id"], body["position"], body["count"]) == (
        f"Hi {management.first_name}",
        None,
        0,
        0,
    )


def test_the_preview_refuses_a_row_not_in_the_batch(
    management_client: APIClient, greeting: BulkEmail
) -> None:
    """A row of another email, or none, is a 400 under ``recipient_id``."""
    response = management_client.post(
        detail_url(greeting, "preview"), {"recipient_id": 999_999}, format="json"
    )
    assert (response.status_code, response.json()) == (
        400,
        {"recipient_id": [NOT_IN_BATCH_MESSAGE]},
    )


def test_the_preview_refuses_an_unknown_token(
    management_client: APIClient, greeting: BulkEmail
) -> None:
    """A message holding an unknown token is a 400 naming it, as a send would be."""
    BulkEmail.objects.filter(pk=greeting.pk).update(subject="Hi {nickname}")
    response = management_client.post(detail_url(greeting, "preview"), {}, format="json")
    assert (response.status_code, response.json()) == (
        400,
        {"subject": [unknown_token_message("nickname")]},
    )


def test_the_preview_of_a_sent_copy_reads_as_it_went(
    management_client: APIClient, greeting: BulkEmail, ann: User
) -> None:
    """Once a copy went, its preview uses the values stored with it."""
    send_now(greeting)
    ann.first_name = "Annie"
    ann.save()
    row = greeting.recipients.get(email="ann@example.test")
    body = management_client.post(
        detail_url(greeting, "preview"), {"recipient_id": row.pk}, format="json"
    ).json()
    assert body["subject"] == "Hello Ann"
