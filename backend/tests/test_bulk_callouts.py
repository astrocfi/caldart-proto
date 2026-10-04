"""Mission callouts: the compose switch, the answer buttons, and the answer page.

A callout is a bulk email whose copies carry three answer buttons, each a link signed for
its recipient.  The page the link opens records nothing until **Send answer** posts it,
and records nothing at all once the callout has closed.  Every copy a sender sees carries
the buttons inert.  Each new or changed answer raises the ``callout_answer`` event.  See
``docs/developer/bulk-email.rst`` and ``docs/developer/api-bulk-email.rst``.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from django.conf import settings
from django.core import mail, signing
from django.core.mail import EmailMessage
from django.test import Client
from django.utils import timezone
from freezegun import freeze_time
from pytest_django import DjangoCaptureOnCommitCallbacks, Settings
from rest_framework.test import APIClient

from apps.accounts.roles import MANAGEMENT, MEMBER
from apps.bulk_email import job
from apps.bulk_email.callout_links import (
    ANSWER_SALT,
    STAND_IN,
    answer_url,
    make_token,
    read_token,
)
from apps.bulk_email.callouts import (
    CLOSED_MESSAGE,
    INACTIVE_MESSAGE,
    default_closes_at,
    record_answer,
)
from apps.bulk_email.models import (
    BulkEmail,
    Callout,
    CalloutAnswer,
    CalloutAnswerKind,
)
from apps.darts.models import Dart
from apps.mail.models import EmailType
from apps.mail.unsubscribe import make_token as unsubscribe_token
from apps.notifications.models import NotificationSubscription
from caldart.exceptions import DomainError
from tests.conftest import RecordedEvents, audit_messages
from tests.factories import (
    BulkEmailFactory,
    DartFactory,
    UserFactory,
    add_to_batch,
    make_dart_leader,
    make_person,
    sent_callout,
)

if TYPE_CHECKING:
    from apps.accounts.models import User

pytestmark = pytest.mark.django_db

API = "/api/v1/bulk-email"
PAST = datetime(2026, 1, 1, tzinfo=UTC)

#: An answer link in a copy, its token, and the answer it chooses.
LINK_RE = re.compile(r"/mail/callout/([^\s\"?<]+)\?answer=(available|limited|unavailable)")


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


def mission() -> EmailType:
    """The Mission type, which every test database starts with."""
    return EmailType.objects.get(slug="mission")


def message_to(address: str) -> EmailMessage:
    """The one email in the outbox to ``address``."""
    found = [message for message in mail.outbox if address in message.to]
    assert len(found) == 1
    return found[0]


def html_of(message: EmailMessage) -> str:
    """The HTML part of ``message``."""
    alternatives = getattr(message, "alternatives", [])
    return str(alternatives[0][0])


def tokens_in(text: str) -> set[str]:
    """Every token the answer links in ``text`` carry."""
    return {match.group(1) for match in LINK_RE.finditer(text)}


def token_for(bulk: BulkEmail, user: User) -> str:
    """The token ``user``'s copy of the callout ``bulk`` carries."""
    return make_token(bulk.callout, user)


def page_url(token: str) -> str:
    """The answer page's path for ``token``."""
    return f"/mail/callout/{token}"


# --------------------------------------------------------------------------
# The compose screen
# --------------------------------------------------------------------------
def test_switching_a_draft_to_a_callout_makes_its_callout_and_chooses_mission(
    management_client: APIClient, management: User
) -> None:
    """The switch makes the callout row and picks Mission, which management may send."""
    bulk = BulkEmailFactory(sender=management)
    with freeze_time("2026-04-07T15:10:00Z"):
        body = management_client.patch(
            f"{API}/{bulk.pk}", {"is_callout": True}, format="json"
        ).json()
    assert (body["is_callout"], body["email_type_name"], body["closes_at"]) == (
        True,
        "Mission",
        "2026-04-09T08:30:00-07:00",
    )


def test_the_default_close_time_is_two_days_ahead_rounded_up_to_the_half_hour() -> None:
    """48 hours from 08:10 is 08:10 two days later, rounded up to 08:30."""
    assert default_closes_at(datetime(2026, 4, 7, 15, 10, tzinfo=UTC)) == datetime(
        2026, 4, 9, 15, 30, tzinfo=UTC
    )


def test_the_switch_keeps_the_type_of_a_sender_who_may_not_send_mission(
    api_client: APIClient,
) -> None:
    """A leader whose role Mission does not name keeps the type they chose."""
    only_management = mission()
    only_management.sender_roles = [MANAGEMENT]
    only_management.save()
    leader = make_dart_leader("lane@example.test", DartFactory(name="Marin DART"))
    bulk = BulkEmailFactory(sender=leader)
    api_client.force_login(leader)
    body = api_client.patch(f"{API}/{bulk.pk}", {"is_callout": True}, format="json").json()
    assert (body["is_callout"], body["email_type_name"]) == (True, "Operational")


def test_a_close_time_can_be_chosen(management_client: APIClient, management: User) -> None:
    """``closes_at`` without an offset is read in the site's time zone."""
    bulk = BulkEmailFactory(sender=management)
    management_client.patch(f"{API}/{bulk.pk}", {"is_callout": True}, format="json")
    body = management_client.patch(
        f"{API}/{bulk.pk}", {"closes_at": "2099-05-01T18:00"}, format="json"
    ).json()
    assert body["closes_at"] == "2099-05-01T18:00:00-07:00"


def test_a_close_time_in_the_past_is_refused(
    management_client: APIClient, management: User
) -> None:
    """Answers cannot close before now."""
    bulk = BulkEmailFactory(sender=management)
    management_client.patch(f"{API}/{bulk.pk}", {"is_callout": True}, format="json")
    response = management_client.patch(
        f"{API}/{bulk.pk}", {"closes_at": "2020-05-01T18:00"}, format="json"
    )
    assert (response.status_code, response.json()) == (
        400,
        {"closes_at": ["Choose a time in the future."]},
    )


def test_switching_back_makes_an_ordinary_email(
    management_client: APIClient, management: User
) -> None:
    """Turning the switch off deletes the callout row, and the email has no close time."""
    bulk = BulkEmailFactory(sender=management)
    management_client.patch(f"{API}/{bulk.pk}", {"is_callout": True}, format="json")
    body = management_client.patch(f"{API}/{bulk.pk}", {"is_callout": False}, format="json").json()
    assert (body["is_callout"], body["closes_at"], Callout.objects.count()) == (False, None, 0)


def test_send_refuses_a_callout_whose_answers_close_before_it_goes(
    management_client: APIClient, management: User, ann: User
) -> None:
    """A schedule after the close time would collect no answers."""
    bulk = BulkEmailFactory(sender=management, email_type=mission(), is_callout=True)
    Callout.objects.create(bulk_email=bulk, closes_at=timezone.now() + timedelta(hours=2))
    add_to_batch(bulk, ann)
    start = timezone.localtime(timezone.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M")
    response = management_client.post(f"{API}/{bulk.pk}/send", {"start_at": start}, format="json")
    assert (response.status_code, response.json()) == (
        400,
        {
            "closes_at": [
                "Answers would close before the email goes out. Choose a later time under "
                "Answers close."
            ]
        },
    )


def test_a_duplicated_callout_is_a_fresh_callout(
    management_client: APIClient, management: User, ann: User
) -> None:
    """**Duplicate** of a callout is a callout again, open two days, with no answers."""
    bulk = sent_callout(management, ann)
    record_answer(bulk.callout, ann, answer="available", note="")
    with freeze_time("2026-08-01T15:10:00Z"):
        copy = management_client.post(f"{API}/{bulk.pk}/duplicate", {}, format="json").json()
    fresh = Callout.objects.get(bulk_email_id=copy["id"])
    assert (copy["is_callout"], copy["closes_at"], fresh.answers.count()) == (
        True,
        "2026-08-03T08:30:00-07:00",
        0,
    )


# --------------------------------------------------------------------------
# The copies
# --------------------------------------------------------------------------
def test_each_copy_carries_three_buttons_signed_for_its_recipient(
    management: User, ann: User, bea: User
) -> None:
    """Ann's copy's buttons carry her token, in both parts, one for each answer."""
    bulk = sent_callout(management, ann, bea)
    copy = message_to("ann@example.test")
    answers = {match.group(2) for match in LINK_RE.finditer(html_of(copy))}
    assert (answers, tokens_in(str(copy.body)), tokens_in(html_of(copy))) == (
        {"available", "limited", "unavailable"},
        {token_for(bulk, ann)},
        {token_for(bulk, ann)},
    )


def test_a_copy_token_reads_back_as_its_callout_and_recipient(management: User, ann: User) -> None:
    """The token names the callout and the person it was sent to."""
    bulk = sent_callout(management, ann)
    (token,) = tokens_in(str(message_to("ann@example.test").body))
    assert read_token(token) == (bulk.callout, ann)


def test_a_copy_links_its_answer_page_to_read_it_in_the_browser(
    management: User, ann: User
) -> None:
    """A callout's View in browser line opens the answer page, not Messages."""
    # The token carries the second it was minted, so the copy and the expected link
    # must be signed at the same instant.
    with freeze_time("2026-08-01T15:10:00Z"):
        bulk = sent_callout(management, ann)
        body = str(message_to("ann@example.test").body)
        expected = answer_url(token_for(bulk, ann))
    assert f"View this email in your browser: {expected}" in body


def test_a_copy_on_the_delivery_report_carries_inert_buttons(
    management_client: APIClient, management: User, ann: User
) -> None:
    """The copy a sender reads answers for nobody: every link carries the stand-in."""
    bulk = sent_callout(management, ann)
    row = bulk.recipients.get()
    body = management_client.get(f"{API}/{bulk.pk}/recipients/{row.pk}/copy").json()
    assert (tokens_in(body["html"]), tokens_in(body["text"])) == ({STAND_IN}, {STAND_IN})


def test_the_preview_carries_inert_buttons(
    management_client: APIClient, management: User, ann: User
) -> None:
    """The preview of a callout's copy carries the stand-in in every link."""
    bulk = BulkEmailFactory(sender=management, email_type=mission(), is_callout=True)
    Callout.objects.create(bulk_email=bulk, closes_at=timezone.now() + timedelta(days=1))
    add_to_batch(bulk, ann)
    body = management_client.post(f"{API}/{bulk.pk}/preview", {}, format="json").json()
    assert tokens_in(body["html"]) == {STAND_IN}


def test_a_test_copy_carries_inert_buttons(management_client: APIClient, management: User) -> None:
    """A test goes to the sender, who is not answering the callout: no signed token."""
    bulk = BulkEmailFactory(sender=management, email_type=mission(), is_callout=True)
    Callout.objects.create(bulk_email=bulk, closes_at=timezone.now() + timedelta(days=1))
    management_client.post(f"{API}/{bulk.pk}/test")
    assert tokens_in(html_of(message_to(management.email))) == {STAND_IN}


def test_the_message_on_the_sent_page_carries_inert_buttons(
    management_client: APIClient, management: User, ann: User
) -> None:
    """``message_html`` shows the buttons with the stand-in."""
    bulk = sent_callout(management, ann)
    body = management_client.get(f"{API}/{bulk.pk}").json()
    assert tokens_in(body["message_html"]) == {STAND_IN}


def test_messages_leads_a_callout_to_the_readers_own_answer_page(
    api_client: APIClient, management: User, ann: User, bea: User
) -> None:
    """Ann's Messages entry for a callout links her own answer page."""
    bulk = sent_callout(management, ann, bea)
    api_client.force_login(ann)
    (entry,) = api_client.get("/api/v1/messages").json()
    assert entry["answer_url"] == answer_url(token_for(bulk, ann))


def test_the_readers_own_copy_under_messages_carries_live_buttons(
    api_client: APIClient, management: User, ann: User
) -> None:
    """Ann reading her copy again gets her own working buttons."""
    bulk = sent_callout(management, ann)
    api_client.force_login(ann)
    body = api_client.get(f"/api/v1/messages/{bulk.pk}").json()
    assert tokens_in(body["html"]) == {token_for(bulk, ann)}


# --------------------------------------------------------------------------
# The answer page
# --------------------------------------------------------------------------
def test_following_a_button_shows_its_answer_chosen_and_records_nothing(
    client: Client, management: User, ann: User
) -> None:
    """A GET, such as a link scanner's, shows the form and records no answer."""
    bulk = sent_callout(management, ann)
    response = client.get(f"{page_url(token_for(bulk, ann))}?answer=limited")
    assert (response.status_code, CalloutAnswer.objects.count()) == (200, 0)


def test_the_page_checks_the_answer_the_button_chose(
    client: Client, management: User, ann: User
) -> None:
    """The button's answer is the one checked."""
    bulk = sent_callout(management, ann)
    page = client.get(f"{page_url(token_for(bulk, ann))}?answer=limited").content.decode()
    checked = re.findall(r'value="(\w+)" checked', page)
    assert checked == ["limited"]


def test_the_page_shows_the_message_as_the_persons_copy_had_it(
    client: Client, management: User, ann: User
) -> None:
    """The subject and message are filled in with Ann's values."""
    bulk = sent_callout(management, ann)
    page = client.get(page_url(token_for(bulk, ann))).content.decode()
    assert ("Fire near Paradise for Ann" in page, "Dear Ann," in page) == (True, True)


def test_the_page_names_the_address_it_answers_for(
    client: Client, management: User, ann: User
) -> None:
    """The form says whose answer it records."""
    bulk = sent_callout(management, ann)
    page = client.get(page_url(token_for(bulk, ann))).content.decode()
    assert f"You are answering for <strong>{ann.email}</strong>." in page


def test_sending_an_answer_records_it_with_the_note(
    client: Client, management: User, ann: User
) -> None:
    """**Send answer** records Ann's answer and her note."""
    bulk = sent_callout(management, ann)
    response = client.post(
        page_url(token_for(bulk, ann)), {"answer": "limited", "note": " Saturday only "}
    )
    saved = CalloutAnswer.objects.get()
    assert (response.status_code, saved.user, saved.answer, saved.note) == (
        200,
        ann,
        CalloutAnswerKind.LIMITED,
        "Saturday only",
    )


def test_an_answer_can_be_changed(client: Client, management: User, ann: User) -> None:
    """A second answer replaces the first; Ann has one answer."""
    bulk = sent_callout(management, ann)
    url = page_url(token_for(bulk, ann))
    client.post(url, {"answer": "available"})
    client.post(url, {"answer": "unavailable", "note": "Plane in annual"})
    assert list(CalloutAnswer.objects.values_list("answer", "note")) == [
        ("unavailable", "Plane in annual")
    ]


def test_the_page_preselects_the_answer_already_given(
    client: Client, management: User, ann: User
) -> None:
    """Opened without a button's choice, the page checks Ann's own answer."""
    bulk = sent_callout(management, ann)
    url = page_url(token_for(bulk, ann))
    client.post(url, {"answer": "unavailable"})
    page = client.get(url).content.decode()
    assert re.findall(r'value="(\w+)" checked', page) == ["unavailable"]


def test_sending_no_answer_is_refused(client: Client, management: User, ann: User) -> None:
    """**Send answer** with nothing chosen asks for a choice and records nothing."""
    bulk = sent_callout(management, ann)
    response = client.post(page_url(token_for(bulk, ann)), {"answer": "maybe"})
    assert (
        response.status_code,
        "Choose one of the three answers." in response.content.decode(),
        CalloutAnswer.objects.count(),
    ) == (400, True, 0)


@pytest.mark.parametrize("method", ["get", "post"])
def test_a_tampered_token_is_refused(
    client: Client, management: User, ann: User, method: str
) -> None:
    """A token changed by one character is a 400 page, and nothing is recorded."""
    bulk = sent_callout(management, ann)
    token = token_for(bulk, ann)
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    response = getattr(client, method)(page_url(tampered), {"answer": "available"})
    assert (
        response.status_code,
        "This link does not work" in response.content.decode(),
        CalloutAnswer.objects.count(),
    ) == (400, True, 0)


def test_a_token_signed_for_another_purpose_is_refused(
    client: Client, management: User, ann: User
) -> None:
    """An unsubscribe token is not an answer token, though the site signed it."""
    sent_callout(management, ann)
    response = client.post(page_url(unsubscribe_token(ann, mission())), {"answer": "available"})
    assert (response.status_code, CalloutAnswer.objects.count()) == (400, 0)


def test_a_token_naming_a_deleted_account_is_refused(
    client: Client, management: User, ann: User
) -> None:
    """A link outlives nothing it names."""
    bulk = sent_callout(management, ann)
    token = token_for(bulk, ann)
    ann.delete()
    assert client.get(page_url(token)).status_code == 400


def test_the_token_carries_the_salt_of_its_purpose(management: User, ann: User) -> None:
    """The token reads back only under ``bulk_email.callout``."""
    bulk = sent_callout(management, ann)
    assert signing.loads(token_for(bulk, ann), salt=ANSWER_SALT) == {
        "c": bulk.callout.pk,
        "u": ann.pk,
    }


@pytest.mark.parametrize("method", ["get", "post"])
def test_an_expired_callout_records_nothing(
    client: Client, management: User, ann: User, method: str
) -> None:
    """After ``closes_at`` the page says the callout has closed and records nothing."""
    bulk = sent_callout(management, ann)
    Callout.objects.filter(pk=bulk.callout.pk).update(
        closes_at=timezone.now() - timedelta(minutes=1)
    )
    response = getattr(client, method)(page_url(token_for(bulk, ann)), {"answer": "available"})
    assert (
        response.status_code,
        "This callout has closed." in response.content.decode(),
        CalloutAnswer.objects.count(),
    ) == (200, True, 0)


def test_a_callout_closed_by_hand_records_nothing(
    client: Client, management: User, ann: User
) -> None:
    """After **Close now** a posted answer is not recorded."""
    bulk = sent_callout(management, ann)
    Callout.objects.filter(pk=bulk.callout.pk).update(closed_at=timezone.now())
    client.post(page_url(token_for(bulk, ann)), {"answer": "available"})
    assert CalloutAnswer.objects.count() == 0


def test_record_answer_refuses_a_closed_callout(management: User, ann: User) -> None:
    """The service itself refuses, whoever calls it."""
    bulk = sent_callout(management, ann)
    Callout.objects.filter(pk=bulk.callout.pk).update(closed_at=timezone.now())
    with pytest.raises(DomainError, match=re.escape(CLOSED_MESSAGE)):
        record_answer(Callout.objects.get(), ann, answer="available", note="")


def test_an_answer_link_is_built_on_the_site_address(management: User, ann: User) -> None:
    """The button's link is built on ``SITE_URL``, which carries any path prefix."""
    bulk = sent_callout(management, ann)
    assert answer_url(token_for(bulk, ann)).startswith(f"{settings.SITE_URL}/mail/callout/")


# --------------------------------------------------------------------------
# The event and its notification
# --------------------------------------------------------------------------
def test_an_answer_raises_the_callout_answer_event(
    management: User, ann: User, recorded_events: RecordedEvents
) -> None:
    """A new answer raises ``callout_answer`` with plain values: who, what, and where."""
    bulk = sent_callout(management, ann)
    record_answer(bulk.callout, ann, answer="available", note="KSQL")
    ((slug, payload),) = recorded_events
    assert (slug, {key: value for key, value in payload.items() if key != "audience"}) == (
        "callout_answer",
        {
            "user": ann,
            "answer": "Available",
            "note": "KSQL",
            "subject": "Fire near Paradise for Hollis",
            "callout_id": bulk.pk,
        },
    )


def test_the_events_audience_is_who_may_open_the_callout(
    management: User, ann: User, recorded_events: RecordedEvents
) -> None:
    """The payload's ``audience`` admits management and turns away a member."""
    bulk = sent_callout(management, ann)
    record_answer(bulk.callout, ann, answer="available", note="")
    audience = recorded_events[0][1]["audience"]
    assert callable(audience)
    assert (audience(management), audience(ann)) == (True, False)


def test_the_same_answer_again_raises_nothing(
    management: User, ann: User, recorded_events: RecordedEvents
) -> None:
    """Sending the same answer and note twice is no change."""
    bulk = sent_callout(management, ann)
    record_answer(bulk.callout, ann, answer="available", note="")
    record_answer(bulk.callout, ann, answer="available", note="")
    assert [slug for slug, _payload in recorded_events] == ["callout_answer"]


def test_a_changed_answer_raises_the_event_again(
    management: User, ann: User, recorded_events: RecordedEvents
) -> None:
    """Each change of the answer is an event of its own."""
    bulk = sent_callout(management, ann)
    record_answer(bulk.callout, ann, answer="available", note="")
    record_answer(bulk.callout, ann, answer="unavailable", note="")
    assert [payload["answer"] for _slug, payload in recorded_events] == [
        "Available",
        "Not available",
    ]


def test_an_answer_is_audited(
    management: User, ann: User, audit_log: pytest.LogCaptureFixture
) -> None:
    """One ``callout.answer`` line names the person and the answer, not the note."""
    bulk = sent_callout(management, ann)
    record_answer(bulk.callout, ann, answer="limited", note="private words")
    assert [line for line in audit_messages(audit_log) if "callout.answer" in line] == [
        f"action=callout.answer actor={ann.pk} target={bulk.pk} answer=limited"
    ]


def subscribed(user: User) -> None:
    """Subscribe ``user``'s address to callout answers."""
    NotificationSubscription.objects.create(
        recipient_user=user, recipient_email=user.email, events=["callout_answer"]
    )


def notified(capture: DjangoCaptureOnCommitCallbacks, bulk: BulkEmail, person: User) -> list[str]:
    """Who is emailed about ``person``'s answer to ``bulk``, once it commits."""
    mail.outbox.clear()
    with capture(execute=True):
        record_answer(bulk.callout, person, answer="available", note="")
    return sorted(address for message in mail.outbox for address in message.to)


def test_the_notification_reaches_management_and_the_leader_of_the_callouts_dart(
    management: User,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """A leader hears of answers to a callout they may open, not of another DART's."""
    marin = DartFactory(name="Marin DART")
    napa = DartFactory(name="Napa DART")
    lane = make_dart_leader("lane@example.test", marin)
    nell = make_dart_leader("nell@example.test", napa)
    pat = make_person("pat@example.test", "Pat", "Pilot", dart=marin)
    for user in (management, lane, nell):
        subscribed(user)
    bulk = sent_callout(lane, pat)
    assert notified(django_capture_on_commit_callbacks, bulk, pat) == [
        "lane@example.test",
        management.email,
    ]


def test_the_notification_names_the_person_the_answer_and_the_callout(
    management: User,
    ann: User,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """The email's subject says who answered what."""
    subscribed(management)
    bulk = sent_callout(management, ann)
    mail.outbox.clear()
    with django_capture_on_commit_callbacks(execute=True):
        record_answer(bulk.callout, ann, answer="limited", note="Saturday only")
    assert mail.outbox[0].subject.endswith(
        "Ann Able answered Available with limits to a mission callout"
    )


def test_a_member_cannot_be_subscribed_to_callout_answers(
    account_admin: User, api_client: APIClient
) -> None:
    """The event is for the callout senders' roles alone."""
    member = UserFactory(email="plain@example.test", roles=[MEMBER])
    api_client.force_login(account_admin)
    response = api_client.post(
        "/api/v1/notifications/subscriptions",
        {"recipient_email": member.email, "events": ["callout_answer"]},
        format="json",
    )
    assert (response.status_code, list(response.json())) == (400, ["events"])


def test_a_leader_can_be_subscribed_to_callout_answers(
    account_admin: User, api_client: APIClient
) -> None:
    """A DART leader may hear of answers."""
    leader = make_dart_leader("lane@example.test", Dart.objects.create(name="Marin DART"))
    api_client.force_login(account_admin)
    response = api_client.post(
        "/api/v1/notifications/subscriptions",
        {"recipient_email": leader.email, "events": ["callout_answer"]},
        format="json",
    )
    assert response.status_code == 201


# --------------------------------------------------------------------------
# A deactivated account, a throttled link, and a note edited alone
# --------------------------------------------------------------------------
@pytest.mark.parametrize("method", ["get", "post"])
def test_a_deactivated_accounts_link_no_longer_works(
    client: Client, management: User, ann: User, method: str
) -> None:
    """Ann's account was deactivated: her link records nothing and says why."""
    bulk = sent_callout(management, ann)
    ann.is_active = False
    ann.save()
    response = getattr(client, method)(page_url(token_for(bulk, ann)), {"answer": "available"})
    assert (
        "This link no longer works" in response.content.decode(),
        CalloutAnswer.objects.count(),
    ) == (True, 0)


def test_record_answer_refuses_a_deactivated_account(management: User, ann: User) -> None:
    """The service refuses, whoever calls it."""
    bulk = sent_callout(management, ann)
    ann.is_active = False
    ann.save()
    with pytest.raises(DomainError, match=re.escape(INACTIVE_MESSAGE)):
        record_answer(bulk.callout, ann, answer="available", note="")


def test_a_deactivated_accounts_answer_is_not_listed(
    management_client: APIClient, management: User, ann: User, bea: User
) -> None:
    """Ann answered, then her account was deactivated: the detail drops her."""
    bulk = sent_callout(management, ann, bea)
    record_answer(bulk.callout, ann, answer="available", note="KSQL")
    ann.is_active = False
    ann.save()
    body = management_client.get(f"{API}/callouts/{bulk.pk}").json()
    assert ([row["name"] for row in body["recipients"]], body["counts"]["available"]) == (
        ["Bea Bell"],
        0,
    )


def test_a_link_past_its_limit_of_answers_records_nothing(
    client: Client, management: User, ann: User, settings: Settings
) -> None:
    """With two answers an hour, the third is refused and the second stands."""
    settings.CALLOUT_ANSWER_THROTTLE_RATE = "2/hour"
    bulk = sent_callout(management, ann)
    url = page_url(token_for(bulk, ann))
    client.post(url, {"answer": "available"})
    client.post(url, {"answer": "limited"})
    response = client.post(url, {"answer": "unavailable"})
    assert (response.status_code, CalloutAnswer.objects.get().answer) == (
        429,
        CalloutAnswerKind.LIMITED,
    )


def test_editing_only_the_note_raises_no_event(
    management: User, ann: User, recorded_events: RecordedEvents
) -> None:
    """A changed note is saved without a notification; a changed answer raises one."""
    bulk = sent_callout(management, ann)
    record_answer(bulk.callout, ann, answer="available", note="")
    record_answer(bulk.callout, ann, answer="available", note="Saturday only")
    saved = CalloutAnswer.objects.get()
    assert (saved.note, len(recorded_events)) == ("Saturday only", 1)
