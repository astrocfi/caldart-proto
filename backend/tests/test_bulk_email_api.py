"""The bulk email endpoints: preview, send, history, and the recipient lists as CSV.

Every endpoint is CalDART management's and the system administrator's alone.  A
preview validates the message and lists who would receive it, sending nothing; a
send rebuilds that list, sends, and answers with the stored result.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from django.core import mail
from freezegun import freeze_time
from rest_framework.test import APIClient

from apps.accounts.models import AccountKind
from apps.accounts.roles import MANAGEMENT, MEMBER, SYSTEM_ADMIN
from apps.bulk_email.models import BulkEmail, BulkEmailRecipient, RecipientStatus
from apps.bulk_email.services import SKIP_BOUNCED, SKIP_DEACTIVATED
from apps.mail.purposes import purpose_label
from tests.conftest import read_csv, role_matrix
from tests.factories import MemberProfileFactory, UserFactory

if TYPE_CHECKING:
    from apps.accounts.models import User

pytestmark = pytest.mark.django_db

LIST_URL = "/api/v1/bulk-email"
PREVIEW_URL = "/api/v1/bulk-email/preview"
PREVIEW_CSV_URL = "/api/v1/bulk-email/preview.csv"
SEND_URL = "/api/v1/bulk-email/send"

SUBJECT = "Spring safety seminar"
BODY = "Join us at Livermore on Saturday.\n\nBring your logbook."

#: The filters every test below sends: friends in Marin County, where nobody but the
#: people a test makes lives, so the role fixtures, who have no profile, stay out.
FRIENDS = {"kind": "friend", "county": "Marin"}


def message(**overrides: object) -> dict[str, object]:
    """A valid preview or send body aimed at the friends, with ``overrides`` applied."""
    return {"subject": SUBJECT, "body": BODY, "filters": FRIENDS, **overrides}


def friend_of(email: str, first: str = "Fay", last: str = "Moss", **user: object) -> User:
    """A friend of CalDART holding the member role, living in Marin County."""
    account = UserFactory(
        email=email,
        first_name=first,
        last_name=last,
        kind=AccountKind.FRIEND,
        roles=[MEMBER],
        **user,
    )
    MemberProfileFactory(user=account, county="Marin")
    return account


def detail_url(bulk: BulkEmail) -> str:
    """``/bulk-email/{id}`` for ``bulk``."""
    return f"{LIST_URL}/{bulk.pk}"


def csv_url(bulk: BulkEmail) -> str:
    """``/bulk-email/{id}/recipients.csv`` for ``bulk``."""
    return f"{LIST_URL}/{bulk.pk}/recipients.csv"


@pytest.fixture
def management_client(api_client: APIClient, management: User) -> APIClient:
    """A DRF client signed in as CalDART management."""
    api_client.force_login(management)
    return api_client


@pytest.fixture
def sent(management_client: APIClient) -> BulkEmail:
    """One bulk email already sent, to one friend, with one deactivated friend skipped."""
    friend_of("ann@example.test", "Ann", "Able")
    friend_of("gil@example.test", "Gil", "Gone", is_active=False)
    response = management_client.post(SEND_URL, message(), format="json")
    return BulkEmail.objects.get(pk=response.json()["id"])


# --------------------------------------------------------------------------
# Who may call what
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("role", "allowed"), role_matrix(MANAGEMENT, SYSTEM_ADMIN))
def test_only_management_previews(
    api_client: APIClient, all_role_users: dict[str, User], role: str, allowed: bool
) -> None:
    """``POST /bulk-email/preview`` is for CalDART management and system admins."""
    api_client.force_login(all_role_users[role])
    response = api_client.post(PREVIEW_URL, message(), format="json")
    assert response.status_code == (200 if allowed else 403)


@pytest.mark.parametrize(("role", "allowed"), role_matrix(MANAGEMENT, SYSTEM_ADMIN))
def test_only_management_sends(
    api_client: APIClient, all_role_users: dict[str, User], role: str, allowed: bool
) -> None:
    """``POST /bulk-email/send`` is for CalDART management and system administrators."""
    friend_of("ann@example.test")
    api_client.force_login(all_role_users[role])
    response = api_client.post(SEND_URL, message(), format="json")
    assert response.status_code == (201 if allowed else 403)


@pytest.mark.parametrize(("role", "allowed"), role_matrix(MANAGEMENT, SYSTEM_ADMIN))
@pytest.mark.parametrize("path", ["", "/{id}", "/{id}/recipients.csv", "/preview.csv"])
def test_only_management_reads_the_history_and_the_lists(
    api_client: APIClient,
    all_role_users: dict[str, User],
    sent: BulkEmail,
    role: str,
    allowed: bool,
    path: str,
) -> None:
    """The history, one send, and both CSVs answer CalDART management alone."""
    api_client.force_login(all_role_users[role])
    response = api_client.get(LIST_URL + path.format(id=sent.pk))
    assert response.status_code == (200 if allowed else 403)


@pytest.mark.parametrize(
    ("method", "url"),
    [("get", LIST_URL), ("post", PREVIEW_URL), ("post", SEND_URL), ("get", PREVIEW_CSV_URL)],
)
def test_an_anonymous_caller_is_turned_away(
    csrf_client: APIClient,
    csrf_headers: Callable[[APIClient], dict[str, str]],
    method: str,
    url: str,
) -> None:
    """Nobody signed in reaches any bulk email endpoint, even with a CSRF token."""
    response = getattr(csrf_client, method)(url, **csrf_headers(csrf_client))
    assert response.status_code == 401


# --------------------------------------------------------------------------
# Preview
# --------------------------------------------------------------------------
def test_a_preview_lists_the_recipients_and_the_skips(management_client: APIClient) -> None:
    """The answer names who would receive it, who is skipped and why, and counts both."""
    ann = friend_of("ann@example.test", "Ann", "Able")
    gil = friend_of("gil@example.test", "Gil", "Gone", is_active=False)
    response = management_client.post(PREVIEW_URL, message(), format="json")
    assert response.json() == {
        "count": 1,
        "skipped_count": 1,
        "recipients": [
            {"user_id": ann.pk, "name": "Ann Able", "email": "ann@example.test", "reason": ""}
        ],
        "skipped": [
            {
                "user_id": gil.pk,
                "name": "Gil Gone",
                "email": "gil@example.test",
                "reason": SKIP_DEACTIVATED,
            }
        ],
    }


def test_a_preview_sends_nothing(management_client: APIClient) -> None:
    """A preview writes no email."""
    friend_of("ann@example.test")
    management_client.post(PREVIEW_URL, message(), format="json")
    assert mail.outbox == []


def test_a_preview_stores_nothing(management_client: APIClient) -> None:
    """A preview leaves no bulk email behind."""
    friend_of("ann@example.test")
    management_client.post(PREVIEW_URL, message(), format="json")
    assert BulkEmail.objects.count() == 0


@pytest.mark.parametrize(
    ("overrides", "errors"),
    [
        ({"subject": ""}, {"subject": ["Write a subject."]}),
        ({"body": "   "}, {"body": ["Write the message."]}),
        ({"subject": "One\nTwo"}, {"subject": ["A subject is one line."]}),
        (
            {"subject": "x" * 201},
            {"subject": ["Ensure this field has no more than 200 characters."]},
        ),
        (
            {"filters": {"wingspan": "red"}},
            {"filters": {"wingspan": ["Not a filter of the member list."]}},
        ),
        (
            {"filters": {"ordering": "name"}},
            {"filters": {"ordering": ["Not a filter of the member list."]}},
        ),
        (
            {"filters": {"kind": "donor"}},
            {
                "filters": {
                    "kind": ["Select a valid choice. donor is not one of the available choices."]
                }
            },
        ),
    ],
    ids=[
        "no-subject",
        "blank-body",
        "two-line-subject",
        "long-subject",
        "unknown-filter",
        "ordering",
        "bad-kind",
    ],
)
def test_a_preview_refuses_a_message_it_cannot_send(
    management_client: APIClient, overrides: dict[str, object], errors: dict[str, object]
) -> None:
    """A missing, malformed, or mis-aimed message is a 400 naming the field and rule."""
    response = management_client.post(PREVIEW_URL, message(**overrides), format="json")
    assert (response.status_code, response.json()) == (400, errors)


# --------------------------------------------------------------------------
# Send
# --------------------------------------------------------------------------
def test_a_send_answers_with_the_stored_result(
    management_client: APIClient, management: User
) -> None:
    """201 with the send, its counts, and each person's result."""
    ann = friend_of("ann@example.test", "Ann", "Able")
    gil = friend_of("gil@example.test", "Gil", "Gone", is_active=False)
    with freeze_time("2026-10-02 17:00:00"):
        response = management_client.post(SEND_URL, message(), format="json")
    body = response.json()
    assert body == {
        "id": body["id"],
        "subject": SUBJECT,
        "body": BODY,
        "filters": FRIENDS,
        "sender": "Hollis Grant",
        "created_at": "2026-10-02T10:00:00-07:00",
        "sent_at": "2026-10-02T10:00:00-07:00",
        "sent_count": 1,
        "failed_count": 0,
        "skipped_count": 1,
        "recipients": [
            {
                "user_id": ann.pk,
                "name": "Ann Able",
                "email": "ann@example.test",
                "status": "sent",
                "reason": "",
            },
            {
                "user_id": gil.pk,
                "name": "Gil Gone",
                "email": "gil@example.test",
                "status": "skipped",
                "reason": SKIP_DEACTIVATED,
            },
        ],
    }


def test_a_send_rebuilds_the_list_when_it_sends(management_client: APIClient) -> None:
    """Somebody who joined the filter after the preview is sent the email too."""
    friend_of("ann@example.test")
    management_client.post(PREVIEW_URL, message(), format="json")
    friend_of("bea@example.test")
    management_client.post(SEND_URL, message(), format="json")
    assert sorted(m.to[0] for m in mail.outbox) == ["ann@example.test", "bea@example.test"]


def test_a_send_to_nobody_is_refused(management_client: APIClient) -> None:
    """With nobody to receive it, the send is a 400 and nothing is stored."""
    response = management_client.post(SEND_URL, message(), format="json")
    assert (response.status_code, response.json(), BulkEmail.objects.count()) == (
        400,
        {"filters": ["Nobody matches these filters."]},
        0,
    )


def test_a_send_refuses_what_a_preview_refuses(management_client: APIClient) -> None:
    """The send validates the message exactly as the preview does."""
    friend_of("ann@example.test")
    response = management_client.post(SEND_URL, message(subject=""), format="json")
    assert (response.status_code, response.json()) == (400, {"subject": ["Write a subject."]})


def test_the_bulk_email_purpose_has_a_label() -> None:
    """The email log names the purpose in words."""
    assert purpose_label("bulk_email") == "Bulk email"


# --------------------------------------------------------------------------
# History
# --------------------------------------------------------------------------
def test_the_history_lists_each_send_newest_first(management_client: APIClient) -> None:
    """``GET /bulk-email`` lists every send, most recent first, without its recipients."""
    friend_of("ann@example.test")
    first = management_client.post(SEND_URL, message(subject="First"), format="json").json()
    second = management_client.post(SEND_URL, message(subject="Second"), format="json").json()
    rows = management_client.get(LIST_URL).json()
    assert [(row["id"], row["subject"], "recipients" in row) for row in rows] == [
        (second["id"], "Second", False),
        (first["id"], "First", False),
    ]


def test_one_send_answers_with_its_results(management_client: APIClient, sent: BulkEmail) -> None:
    """``GET /bulk-email/{id}`` carries each person's result."""
    rows = management_client.get(detail_url(sent)).json()["recipients"]
    assert [(row["email"], row["status"]) for row in rows] == [
        ("ann@example.test", RecipientStatus.SENT),
        ("gil@example.test", RecipientStatus.SKIPPED),
    ]


def test_an_unknown_send_is_not_found(management_client: APIClient) -> None:
    """An id no send carries is a 404."""
    assert management_client.get(f"{LIST_URL}/999999").status_code == 404


def test_a_deleted_sender_reads_as_blank(management_client: APIClient, sent: BulkEmail) -> None:
    """A send whose sender's account is gone names nobody."""
    other = UserFactory(email="former@example.test")
    BulkEmail.objects.filter(pk=sent.pk).update(sender=other)
    other.delete()
    assert management_client.get(detail_url(sent)).json()["sender"] == ""


def test_a_recipient_whose_account_is_gone_keeps_their_row(
    management_client: APIClient, sent: BulkEmail
) -> None:
    """Deleting a recipient's account keeps the row, with its name and address."""
    BulkEmailRecipient.objects.get(email="ann@example.test").user.delete()  # type: ignore[union-attr]  # the fixture's row names an account
    rows = management_client.get(detail_url(sent)).json()["recipients"]
    assert rows[0] == {
        "user_id": None,
        "name": "Ann Able",
        "email": "ann@example.test",
        "status": "sent",
        "reason": "",
    }


# --------------------------------------------------------------------------
# The CSVs
# --------------------------------------------------------------------------
def test_a_send_s_recipients_download_as_a_csv(
    management_client: APIClient, sent: BulkEmail
) -> None:
    """One row per person: name, address, result, and reason."""
    assert read_csv(management_client.get(csv_url(sent))) == [
        ["Name", "Email", "Result", "Reason"],
        ["Ann Able", "ann@example.test", "Sent", ""],
        ["Gil Gone", "gil@example.test", "Skipped", SKIP_DEACTIVATED],
    ]


def test_a_send_s_csv_is_named_for_the_send(management_client: APIClient, sent: BulkEmail) -> None:
    """The download is named for the send's id."""
    response = management_client.get(csv_url(sent))
    assert response["Content-Disposition"] == (
        f'attachment; filename="caldart-bulk-email-{sent.pk}-recipients.csv"'
    )


def test_the_preview_list_downloads_as_a_csv(management_client: APIClient) -> None:
    """``GET /bulk-email/preview.csv`` takes the filters as its query and lists them."""
    friend_of("ann@example.test", "Ann", "Able")
    friend_of("gil@example.test", "Gil", "Gone", is_active=False)
    UserFactory(email="member@example.test", roles=[MEMBER])
    assert read_csv(management_client.get(PREVIEW_CSV_URL, FRIENDS)) == [
        ["Name", "Email", "Result", "Reason"],
        ["Ann Able", "ann@example.test", "To send", ""],
        ["Gil Gone", "gil@example.test", "Skipped", SKIP_DEACTIVATED],
    ]


def test_the_preview_csv_is_named_for_the_day(management_client: APIClient) -> None:
    """The preview download carries the day it was built."""
    with freeze_time("2026-10-02 17:00:00"):
        response = management_client.get(PREVIEW_CSV_URL, FRIENDS)
    assert response["Content-Disposition"] == (
        'attachment; filename="caldart-bulk-email-preview-2026-10-02.csv"'
    )


def test_the_preview_csv_refuses_an_unknown_filter(management_client: APIClient) -> None:
    """A filter the member list does not have is a 400."""
    response = management_client.get(PREVIEW_CSV_URL, {"wingspan": "red"})
    assert (response.status_code, response.json()) == (
        400,
        {"filters": {"wingspan": ["Not a filter of the member list."]}},
    )


#: Every character that breaks a line, and a sample of the other control characters.
SUBJECT_BREAKERS = {
    "carriage-return": ("\r", "A subject is one line."),
    "vertical-tab": ("\x0b", "A subject is one line."),
    "form-feed": ("\x0c", "A subject is one line."),
    "file-separator": ("\x1c", "A subject is one line."),
    "next-line": ("\x85", "A subject is one line."),
    "line-separator": ("\u2028", "A subject is one line."),
    "paragraph-separator": ("\u2029", "A subject is one line."),
    "tab": ("\t", "A subject cannot carry control characters such as tabs."),
    "escape": ("\x1b", "A subject cannot carry control characters such as tabs."),
    "bell": ("\x07", "A subject cannot carry control characters such as tabs."),
    "delete": ("\x7f", "A subject cannot carry control characters such as tabs."),
}


@pytest.mark.parametrize(
    ("character", "error"), list(SUBJECT_BREAKERS.values()), ids=list(SUBJECT_BREAKERS)
)
def test_a_subject_refuses_a_line_break_or_control_character(
    management_client: APIClient, character: str, error: str
) -> None:
    """A character the mail library would refuse in a header is a 400, never a 500."""
    friend_of("ann@example.test")
    response = management_client.post(
        SEND_URL, message(subject=f"Spring{character}seminar"), format="json"
    )
    assert (response.status_code, response.json(), BulkEmail.objects.count()) == (
        400,
        {"subject": [error]},
        0,
    )


def test_the_preview_csv_refuses_ordering(management_client: APIClient) -> None:
    """``ordering`` sorts the member list and chooses nobody, so it is no filter here."""
    response = management_client.get(PREVIEW_CSV_URL, {"ordering": "name"})
    assert (response.status_code, response.json()) == (
        400,
        {"filters": {"ordering": ["Not a filter of the member list."]}},
    )


def test_an_unfinished_send_lists_who_was_never_sent_a_copy(
    management_client: APIClient, sent: BulkEmail
) -> None:
    """A send that stopped part way reads its pending copies as never sent."""
    BulkEmail.objects.filter(pk=sent.pk).update(sent_at=None)
    BulkEmailRecipient.objects.filter(email="ann@example.test").update(status="pending")
    body = management_client.get(detail_url(sent)).json()
    assert (body["sent_at"], [(r["email"], r["status"]) for r in body["recipients"]]) == (
        None,
        [("ann@example.test", "pending"), ("gil@example.test", "skipped")],
    )


def test_an_unfinished_send_s_csv_reads_not_sent(
    management_client: APIClient, sent: BulkEmail
) -> None:
    """The results CSV names a copy never tried as Not sent."""
    BulkEmailRecipient.objects.filter(email="ann@example.test").update(status="pending")
    assert read_csv(management_client.get(csv_url(sent)))[1] == [
        "Ann Able",
        "ann@example.test",
        "Not sent",
        "",
    ]


def test_a_preview_skips_a_bounced_address(management_client: APIClient) -> None:
    """The preview lists a bounced address among the skips, with the reason."""
    friend_of(
        "gone@example.test",
        "Gus",
        "Gone",
        email_bounced_at=datetime(2026, 9, 30, 12, 0, tzinfo=UTC),
    )
    body = management_client.post(PREVIEW_URL, message(), format="json").json()
    assert [(r["email"], r["reason"]) for r in body["skipped"]] == [
        ("gone@example.test", SKIP_BOUNCED)
    ]


def test_the_preview_csv_marks_a_bounced_address_skipped(management_client: APIClient) -> None:
    """The preview's download gives the bounce as the reason."""
    friend_of(
        "gone@example.test",
        "Gus",
        "Gone",
        email_bounced_at=datetime(2026, 9, 30, 12, 0, tzinfo=UTC),
    )
    assert read_csv(management_client.get(PREVIEW_CSV_URL, FRIENDS))[1:] == [
        ["Gus Gone", "gone@example.test", "Skipped", SKIP_BOUNCED]
    ]


def test_a_send_s_csv_marks_a_bounced_address_skipped(management_client: APIClient) -> None:
    """A sent email's download gives the bounce as the reason for the skip."""
    friend_of("ann@example.test", "Ann", "Able")
    friend_of(
        "gone@example.test",
        "Gus",
        "Gone",
        email_bounced_at=datetime(2026, 9, 30, 12, 0, tzinfo=UTC),
    )
    bulk_id = management_client.post(SEND_URL, message(), format="json").json()["id"]
    assert read_csv(management_client.get(f"{LIST_URL}/{bulk_id}/recipients.csv"))[1:] == [
        ["Ann Able", "ann@example.test", "Sent", ""],
        ["Gus Gone", "gone@example.test", "Skipped", SKIP_BOUNCED],
    ]
