"""DART leaders send bulk email to their own DART, and only to it.

A DART leader's DART is the one on their own member profile.  Every add to a leader's
email is forced to that DART, a person outside it is skipped, the background sender
checks it once more when the send starts, and a leader whose profile names no DART
cannot send.  A leader sees only their own emails; CalDART management sees everyone's,
with the sender and the DART.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from django.core import mail
from pytest_django import Settings
from rest_framework.test import APIClient

from apps.accounts.roles import DART_LEADER, MANAGEMENT, MEMBER, SYSTEM_ADMIN
from apps.bulk_email import job
from apps.bulk_email.models import BatchAdd, BulkEmail, BulkEmailStatus, RecipientStatus
from apps.bulk_email.senders import (
    NO_DART_MESSAGE,
    NOT_YOUR_DART_MESSAGE,
    SKIP_NOT_IN_DART,
    sender_context,
)
from apps.mail.models import EmailType
from caldart import audit
from tests.conftest import audit_messages, role_matrix
from tests.factories import (
    BulkEmailFactory,
    DartFactory,
    MemberProfileFactory,
    UserFactory,
    add_to_batch,
    make_person,
)

if TYPE_CHECKING:
    from apps.accounts.models import User
    from apps.darts.models import Dart

pytestmark = pytest.mark.django_db

API = "/api/v1/bulk-email"
NOW = datetime(2026, 4, 6, 17, 0, tzinfo=UTC)

#: Everybody in the Marin DART: Ann, Bea, and their leader, Lane.
MARIN_ADDRESSES = {"ann@example.test", "bea@example.test", "lane@example.test"}


def url(bulk: BulkEmail, action: str = "") -> str:
    """``/api/v1/bulk-email/{id}`` for ``bulk``, then ``/<action>`` when one is given."""
    base = f"{API}/{bulk.pk}"
    return f"{base}/{action}" if action else base


def make_leader(email: str, dart: Dart | None, first: str = "Lane", last: str = "Lead") -> User:
    """A DART leader whose profile names ``dart``, or names none when it is ``None``."""
    leader = UserFactory(email=email, first_name=first, last_name=last, roles=[MEMBER, DART_LEADER])
    MemberProfileFactory(user=leader, dart=dart)
    return leader


def batch_reasons(client: APIClient, bulk: BulkEmail) -> dict[str, str]:
    """Each address in ``bulk``'s batch with its reason, ``""`` for one receiving it."""
    rows = client.get(url(bulk, "batch")).json()["rows"]
    return {row["email"]: row["reason"] for row in rows}


@pytest.fixture
def marin(db: None) -> Dart:
    """The Marin DART."""
    return DartFactory(name="Marin DART", airport_identifiers="DVO")


@pytest.fixture
def napa(db: None) -> Dart:
    """The Napa DART."""
    return DartFactory(name="Napa DART", airport_identifiers="APC")


@pytest.fixture
def leader(marin: Dart) -> User:
    """A DART leader whose profile names the Marin DART."""
    return make_leader("lane@example.test", marin)


@pytest.fixture
def leader_client(api_client: APIClient, leader: User) -> APIClient:
    """An API client signed in as the Marin DART's leader."""
    api_client.force_login(leader)
    return api_client


@pytest.fixture
def people(marin: Dart, napa: Dart) -> dict[str, User]:
    """Two members of the Marin DART and one of the Napa DART, by first name."""
    return {
        "ann": make_person("ann@example.test", "Ann", "Able", dart=marin),
        "bea": make_person("bea@example.test", "Bea", "Bell", dart=marin),
        "nat": make_person("nat@example.test", "Nat", "Napa", dart=napa),
    }


@pytest.fixture
def leader_draft(leader: User, marin: Dart) -> BulkEmail:
    """The Marin leader's draft, with a subject and a message and an empty batch."""
    return BulkEmailFactory(sender=leader, dart=marin)


@pytest.fixture
def no_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    """Let the background sender go without pausing between copies."""
    monkeypatch.setattr(job, "sleep", lambda seconds: None)


# --------------------------------------------------------------------------
# Who may send to whom
# --------------------------------------------------------------------------
def test_management_sends_to_everyone(management: User) -> None:
    """CalDART management's context has no DART and can send."""
    context = sender_context(management)
    assert (context.is_management, context.dart, context.can_send, context.reason) == (
        True,
        None,
        True,
        "",
    )


def test_a_system_administrator_sends_as_management(system_admin: User) -> None:
    """A system administrator passes for CalDART management."""
    assert sender_context(system_admin).is_management is True


def test_a_leader_sends_to_the_dart_on_their_profile(leader: User, marin: Dart) -> None:
    """A DART leader's context is their profile's DART."""
    context = sender_context(leader)
    assert (context.is_management, context.dart, context.can_send) == (False, marin, True)


@pytest.mark.parametrize("has_profile", [True, False], ids=["profile-no-dart", "no-profile"])
def test_a_leader_with_no_dart_cannot_send(dart_leader: User, has_profile: bool) -> None:
    """A leader whose profile names no DART, or who has none, has nobody to send to."""
    if has_profile:
        MemberProfileFactory(user=dart_leader, dart=None)
    context = sender_context(dart_leader)
    assert (context.can_send, context.reason) == (False, NO_DART_MESSAGE)


def test_the_sender_endpoint_answers_a_leader_s_dart(leader_client: APIClient, marin: Dart) -> None:
    """``GET /bulk-email/sender`` names the leader's DART."""
    assert leader_client.get(f"{API}/sender").json() == {
        "is_management": False,
        "can_send": True,
        "reason": "",
        "dart": marin.pk,
        "dart_name": "Marin DART",
    }


def test_the_sender_endpoint_says_why_a_leader_cannot_send(
    api_client: APIClient, dart_leader: User
) -> None:
    """A leader with no DART is told why there is nobody to send to."""
    api_client.force_login(dart_leader)
    assert api_client.get(f"{API}/sender").json() == {
        "is_management": False,
        "can_send": False,
        "reason": NO_DART_MESSAGE,
        "dart": None,
        "dart_name": "",
    }


def test_the_sender_endpoint_answers_management(management_client: APIClient) -> None:
    """CalDART management sends to everyone, with no DART of its own."""
    assert management_client.get(f"{API}/sender").json() == {
        "is_management": True,
        "can_send": True,
        "reason": "",
        "dart": None,
        "dart_name": "",
    }


# --------------------------------------------------------------------------
# Opening a draft
# --------------------------------------------------------------------------
def test_a_leader_s_draft_records_their_dart(leader_client: APIClient, marin: Dart) -> None:
    """A leader's fresh draft is limited to their DART, and says so."""
    response = leader_client.post(f"{API}/drafts")
    bulk = BulkEmail.objects.get(pk=response.json()["id"])
    assert (response.status_code, bulk.dart, response.json()["dart_name"]) == (
        201,
        marin,
        "Marin DART",
    )


def test_a_leader_with_no_dart_cannot_open_a_draft(
    api_client: APIClient, dart_leader: User
) -> None:
    """Compose refuses a leader with no DART with the reason, and makes no draft."""
    api_client.force_login(dart_leader)
    response = api_client.post(f"{API}/drafts")
    assert (response.status_code, response.json(), BulkEmail.objects.count()) == (
        403,
        {"detail": NO_DART_MESSAGE},
        0,
    )


def test_management_s_draft_has_no_dart(management_client: APIClient) -> None:
    """CalDART management's draft goes to anybody: no DART, a blank name."""
    response = management_client.post(f"{API}/drafts")
    bulk = BulkEmail.objects.get(pk=response.json()["id"])
    assert (bulk.dart, response.json()["dart_name"]) == (None, "")


# --------------------------------------------------------------------------
# The batch stays inside the DART
# --------------------------------------------------------------------------
def test_an_add_with_no_filters_adds_only_the_leader_s_dart(
    leader_client: APIClient, leader_draft: BulkEmail, people: dict[str, User], marin: Dart
) -> None:
    """Everybody, for a leader, is everybody in their DART, the leader included."""
    leader_client.post(url(leader_draft, "batch/add"), {"filters": {}}, format="json")
    emails = set(leader_draft.recipients.values_list("email", flat=True))
    assert emails == MARIN_ADDRESSES


def test_a_leader_s_add_records_the_dart_it_was_limited_to(
    leader_client: APIClient, leader_draft: BulkEmail, people: dict[str, User], marin: Dart
) -> None:
    """The add keeps the DART it was forced to, so its label names it."""
    leader_client.post(url(leader_draft, "batch/add"), {"filters": {}}, format="json")
    assert BatchAdd.objects.get(bulk_email=leader_draft).filters == {"dart": str(marin.pk)}


def test_a_leader_may_name_their_own_dart(
    leader_client: APIClient, leader_draft: BulkEmail, people: dict[str, User], marin: Dart
) -> None:
    """A filter naming the leader's own DART by id is taken."""
    response = leader_client.post(
        url(leader_draft, "batch/add"), {"filters": {"dart": str(marin.pk)}}, format="json"
    )
    assert response.json() == {"added": 3, "already_present": 0, "count": 3}


@pytest.mark.parametrize("value", ["other-id", "Napa", "Marin"], ids=["id", "name", "own-name"])
def test_a_crafted_dart_filter_is_refused(
    leader_client: APIClient,
    leader_draft: BulkEmail,
    people: dict[str, User],
    napa: Dart,
    value: str,
) -> None:
    """Another DART, by id or by name, is a 400 and adds nobody; only the id is taken."""
    dart = str(napa.pk) if value == "other-id" else value
    response = leader_client.post(
        url(leader_draft, "batch/add"), {"filters": {"dart": dart}}, format="json"
    )
    assert (response.status_code, response.json(), leader_draft.recipients.count()) == (
        400,
        {"filters": {"dart": [NOT_YOUR_DART_MESSAGE]}},
        0,
    )


def test_other_filters_narrow_inside_the_dart(
    leader_client: APIClient, leader_draft: BulkEmail, people: dict[str, User]
) -> None:
    """A search matching every address runs inside the DART: Nat of Napa is not added."""
    leader_client.post(
        url(leader_draft, "batch/add"), {"filters": {"search": "example.test"}}, format="json"
    )
    emails = set(leader_draft.recipients.values_list("email", flat=True))
    assert emails == MARIN_ADDRESSES


def test_management_adding_to_a_leader_s_email_stays_in_the_dart(
    management_client: APIClient, leader_draft: BulkEmail, people: dict[str, User]
) -> None:
    """The limit is the email's, whoever presses Add to batch."""
    management_client.post(url(leader_draft, "batch/add"), {"filters": {}}, format="json")
    emails = set(leader_draft.recipients.values_list("email", flat=True))
    assert emails == MARIN_ADDRESSES


def test_management_s_add_reaches_every_dart(
    management_client: APIClient, management: User, people: dict[str, User]
) -> None:
    """CalDART management's email has no limit: all three are added."""
    bulk = BulkEmailFactory(sender=management)
    management_client.post(url(bulk, "batch/add"), {"filters": {"county": "Marin"}}, format="json")
    assert bulk.recipients.count() == 3


def test_someone_outside_the_dart_in_the_batch_is_skipped(
    leader_client: APIClient, leader_draft: BulkEmail, people: dict[str, User]
) -> None:
    """A row that is not in the DART, however it got there, receives nothing."""
    add_to_batch(leader_draft, people["ann"], people["nat"])
    assert batch_reasons(leader_client, leader_draft) == {
        "ann@example.test": "",
        "nat@example.test": SKIP_NOT_IN_DART,
    }


def test_someone_who_left_the_dart_is_skipped(
    leader_client: APIClient, leader_draft: BulkEmail, people: dict[str, User], napa: Dart
) -> None:
    """A person who moves to another DART after being added is skipped at once."""
    add_to_batch(leader_draft, people["ann"])
    people["ann"].profile.dart = napa
    people["ann"].profile.save()
    assert batch_reasons(leader_client, leader_draft) == {"ann@example.test": SKIP_NOT_IN_DART}


def test_the_audience_follows_the_leader_s_profile(
    leader_client: APIClient,
    leader: User,
    leader_draft: BulkEmail,
    people: dict[str, User],
    napa: Dart,
) -> None:
    """When the leader's DART changes, their email reaches the new DART from then on."""
    add_to_batch(leader_draft, people["ann"])
    leader.profile.dart = napa
    leader.profile.save()
    leader_client.post(url(leader_draft, "batch/add"), {"filters": {}}, format="json")
    leader_draft.refresh_from_db()
    assert (batch_reasons(leader_client, leader_draft), leader_draft.dart) == (
        {"ann@example.test": SKIP_NOT_IN_DART, "lane@example.test": "", "nat@example.test": ""},
        napa,
    )


def test_a_leader_who_loses_their_dart_cannot_add(
    leader_client: APIClient, leader: User, leader_draft: BulkEmail, people: dict[str, User]
) -> None:
    """An add to the email of a leader whose profile names no DART is a 409."""
    leader.profile.dart = None
    leader.profile.save()
    response = leader_client.post(url(leader_draft, "batch/add"), {"filters": {}}, format="json")
    assert (response.status_code, response.json()) == (409, {"detail": NO_DART_MESSAGE})


# --------------------------------------------------------------------------
# Sending
# --------------------------------------------------------------------------
def test_a_leader_who_loses_their_dart_cannot_send(
    leader_client: APIClient, leader: User, leader_draft: BulkEmail, people: dict[str, User]
) -> None:
    """Send refuses a leader with no DART with the reason, under ``batch``."""
    add_to_batch(leader_draft, people["ann"])
    leader.profile.dart = None
    leader.profile.save()
    response = leader_client.post(url(leader_draft, "send"), {}, format="json")
    assert (response.status_code, response.json()) == (400, {"batch": [NO_DART_MESSAGE]})


def test_a_batch_only_outside_the_dart_cannot_be_sent(
    leader_client: APIClient, leader_draft: BulkEmail, people: dict[str, User]
) -> None:
    """Nobody in the batch is in the DART, so nobody can receive it."""
    add_to_batch(leader_draft, people["nat"])
    response = leader_client.post(url(leader_draft, "send"), {}, format="json")
    assert response.json() == {
        "batch": ["Nobody in the batch can receive this email. Add people to the batch."]
    }


def test_a_leader_cannot_send_a_type_their_role_may_not(
    leader_client: APIClient, leader_draft: BulkEmail
) -> None:
    """Fundraising is not a DART leader's to send."""
    fundraising = EmailType.objects.get(slug="fundraising")
    response = leader_client.patch(url(leader_draft), {"email_type": fundraising.pk}, format="json")
    assert response.json() == {
        "email_type": ["You cannot send Fundraising email. Choose another type."]
    }


def test_a_leader_s_send_reaches_only_their_dart(
    leader_client: APIClient,
    leader_draft: BulkEmail,
    people: dict[str, User],
    settings: Settings,
    no_pause: None,
) -> None:
    """Sent through the API and the sender, the copies go to the DART alone."""
    settings.BULK_EMAIL_UNDO_SECONDS = 0
    add_to_batch(leader_draft, people["nat"])
    leader_client.post(url(leader_draft, "batch/add"), {"filters": {}}, format="json")
    leader_client.post(url(leader_draft, "send"), {}, format="json")
    job.run_sender()
    assert {message.to[0] for message in mail.outbox} == MARIN_ADDRESSES


def test_the_freeze_skips_someone_who_left_the_dart(
    leader: User, people: dict[str, User], napa: Dart, marin: Dart, no_pause: None
) -> None:
    """A person who left the DART between Send and the start is skipped and stored so."""
    bulk = BulkEmailFactory(sender=leader, status=BulkEmailStatus.QUEUED, start_at=NOW)
    add_to_batch(bulk, people["ann"], people["bea"])
    people["bea"].profile.dart = napa
    people["bea"].profile.save()
    job.run_sender(now=NOW)
    rows = {row.email: (row.status, row.reason) for row in bulk.recipients.all()}
    assert rows == {
        "ann@example.test": (RecipientStatus.SENT, ""),
        "bea@example.test": (RecipientStatus.SKIPPED, SKIP_NOT_IN_DART),
    }


def test_the_send_records_the_dart_it_went_to(
    leader: User, people: dict[str, User], marin: Dart, no_pause: None
) -> None:
    """When the send starts, the email records its sender's DART."""
    bulk = BulkEmailFactory(sender=leader, status=BulkEmailStatus.QUEUED, start_at=NOW)
    add_to_batch(bulk, people["ann"])
    job.run_sender(now=NOW)
    bulk.refresh_from_db()
    assert bulk.dart == marin


def test_a_queued_email_of_a_leader_who_lost_their_dart_is_not_sent(
    leader: User,
    leader_draft: BulkEmail,
    people: dict[str, User],
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """The sender returns it to the drafts with the reason, and sends nothing."""
    BulkEmail.objects.filter(pk=leader_draft.pk).update(status=BulkEmailStatus.QUEUED, start_at=NOW)
    add_to_batch(leader_draft, people["ann"])
    leader.profile.dart = None
    leader.profile.save()
    job.run_sender(now=NOW)
    leader_draft.refresh_from_db()
    assert (leader_draft.status, leader_draft.not_sent_reason, len(mail.outbox)) == (
        BulkEmailStatus.DRAFT,
        job.NOT_SENT_NO_DART,
        0,
    )


def test_the_refusal_is_audited_as_no_dart(
    leader: User,
    leader_draft: BulkEmail,
    people: dict[str, User],
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """One ``bulk_email.refused`` line names the reason ``no_dart``."""
    BulkEmail.objects.filter(pk=leader_draft.pk).update(status=BulkEmailStatus.QUEUED, start_at=NOW)
    leader.profile.dart = None
    leader.profile.save()
    job.run_sender(now=NOW)
    refused = [line for line in audit_messages(audit_log) if audit.BULK_EMAIL_REFUSED in line]
    assert len(refused) == 1
    assert f"reason={audit.REASON_NO_DART}" in refused[0]


# --------------------------------------------------------------------------
# Whose emails each sender sees
# --------------------------------------------------------------------------
@pytest.fixture
def three_senders(leader: User, management: User, napa: Dart) -> dict[str, BulkEmail]:
    """A draft and a sent email each of the two leaders and of CalDART management."""
    other = make_leader("otto@example.test", napa, "Otto", "Other")
    emails: dict[str, BulkEmail] = {}
    for name, sender in (("lane", leader), ("otto", other), ("mgmt", management)):
        emails[f"{name}-draft"] = BulkEmailFactory(sender=sender, subject=f"{name} draft")
        emails[f"{name}-sent"] = BulkEmailFactory(
            sender=sender,
            subject=f"{name} sent",
            status=BulkEmailStatus.SENT,
            started_at=NOW,
            sent_at=NOW,
            dart=napa if name == "otto" else None,
        )
    return emails


@pytest.mark.parametrize(
    ("path", "subject"), [("drafts", "lane draft"), ("sent", "lane sent")], ids=["drafts", "sent"]
)
def test_a_leader_lists_only_their_own(
    leader_client: APIClient, three_senders: dict[str, BulkEmail], path: str, subject: str
) -> None:
    """Drafts & scheduled and Sent list a leader's own emails alone."""
    rows = leader_client.get(f"{API}/{path}").json()
    assert [row["subject"] for row in rows] == [subject]


@pytest.mark.parametrize("path", ["drafts", "sent"])
def test_management_lists_everyone_s(
    management_client: APIClient, three_senders: dict[str, BulkEmail], path: str
) -> None:
    """CalDART management lists every sender's emails."""
    rows = management_client.get(f"{API}/{path}").json()
    assert len(rows) == 3


def test_management_sees_each_send_s_sender_and_dart(
    management_client: APIClient, three_senders: dict[str, BulkEmail]
) -> None:
    """The Sent list names the sender and the DART each send went to."""
    rows = management_client.get(f"{API}/sent").json()
    assert sorted((row["sender"], row["dart_name"]) for row in rows) == [
        ("Hollis Grant", ""),
        ("Lane Lead", ""),
        ("Otto Other", "Napa DART"),
    ]


@pytest.mark.parametrize(
    ("method", "action"),
    [
        ("get", ""),
        ("patch", ""),
        ("delete", ""),
        ("post", "send"),
        ("post", "cancel"),
        ("post", "stop"),
        ("post", "resume"),
        ("post", "preview"),
        ("get", "batch"),
        ("get", "batch.csv"),
        ("post", "batch/add"),
        ("delete", "batch"),
        ("get", "recipients.csv"),
    ],
)
@pytest.mark.parametrize("owner", ["otto-draft", "mgmt-draft", "otto-sent", "mgmt-sent"])
def test_a_leader_cannot_reach_another_sender_s_email(
    leader_client: APIClient,
    three_senders: dict[str, BulkEmail],
    method: str,
    action: str,
    owner: str,
) -> None:
    """Every endpoint answers 404 for an email that is not the leader's own."""
    response = getattr(leader_client, method)(url(three_senders[owner], action), {}, format="json")
    assert response.status_code == 404


def test_a_leader_cannot_remove_a_row_of_another_sender_s_batch(
    leader_client: APIClient, three_senders: dict[str, BulkEmail], people: dict[str, User]
) -> None:
    """A crafted row id under another sender's email is a 404, and the row stays."""
    row = add_to_batch(three_senders["mgmt-draft"], people["nat"])[0]
    response = leader_client.delete(url(three_senders["mgmt-draft"], f"batch/{row.pk}"))
    assert (response.status_code, three_senders["mgmt-draft"].recipients.count()) == (404, 1)


def test_management_reaches_a_leader_s_email(
    management_client: APIClient, three_senders: dict[str, BulkEmail]
) -> None:
    """CalDART management opens any leader's email, with its DART."""
    response = management_client.get(url(three_senders["otto-sent"]))
    assert (response.status_code, response.json()["dart_name"]) == (200, "Napa DART")


# --------------------------------------------------------------------------
# Who may call what
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("role", "allowed"), role_matrix(DART_LEADER, MANAGEMENT, SYSTEM_ADMIN))
@pytest.mark.parametrize("path", ["sender", "drafts", "sent", "fields"])
def test_the_lists_answer_every_bulk_sender(
    api_client: APIClient, all_role_users: dict[str, User], role: str, allowed: bool, path: str
) -> None:
    """The sender context, both lists, and the field catalog answer each sender's role."""
    api_client.force_login(all_role_users[role])
    assert api_client.get(f"{API}/{path}").status_code == (200 if allowed else 403)


@pytest.mark.parametrize(("role", "allowed"), role_matrix(DART_LEADER, MANAGEMENT, SYSTEM_ADMIN))
@pytest.mark.parametrize(
    ("method", "action", "code"),
    [
        ("get", "", 200),
        ("patch", "", 200),
        ("post", "preview", 200),
        ("get", "batch", 200),
        ("get", "batch.csv", 200),
        ("post", "batch/add", 200),
        ("post", "send", 200),
        ("post", "cancel", 200),
        ("get", "recipients.csv", 200),
        ("delete", "batch", 200),
        ("delete", "", 204),
    ],
)
def test_every_bulk_sender_reaches_their_own_email(
    api_client: APIClient,
    all_role_users: dict[str, User],
    marin: Dart,
    role: str,
    allowed: bool,
    method: str,
    action: str,
    code: int,
) -> None:
    """Each endpoint of one email answers its own sender, if that sender's role sends."""
    user = all_role_users[role]
    MemberProfileFactory(user=user, dart=marin)
    bulk = BulkEmailFactory(sender=user)
    add_to_batch(bulk, make_person("ann@example.test", "Ann", "Able", dart=marin))
    api_client.force_login(user)
    response = getattr(api_client, method)(url(bulk, action), {}, format="json")
    assert response.status_code == (code if allowed else 403)
