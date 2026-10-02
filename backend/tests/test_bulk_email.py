"""Bulk email: who a filter reaches, who is skipped and why, and what a send records.

The recipients are the member list's own filters applied to every member and friend;
deactivated accounts and blank or invalid addresses are skipped with a reason, and
addresses are de-duplicated without regard to case.  A send writes one
``BulkEmailRecipient`` per person and keeps going past a mail server that refuses one
of them.
"""

from __future__ import annotations

import smtplib
from collections.abc import Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest
from django.core import mail
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.core.mail.backends.locmem import EmailBackend
from freezegun import freeze_time
from pytest_django import Settings

from apps.accounts.models import AccountKind
from apps.accounts.roles import MEMBER, TREASURER
from apps.accounts.services import clear_email_bounce
from apps.bulk_email.models import BulkEmail, BulkEmailRecipient, RecipientStatus
from apps.bulk_email.services import (
    SKIP_BOUNCED,
    SKIP_DEACTIVATED,
    SKIP_DUPLICATE,
    SKIP_INVALID,
    SKIP_NO_ADDRESS,
    Recipient,
    build_recipients,
    send_bulk_email,
)
from apps.mail.models import EmailLog
from apps.members.models import MedicalType, MembershipPlan, PilotCertificateType
from tests.conftest import audit_messages
from tests.factories import (
    DartFactory,
    MemberProfileFactory,
    UserFactory,
    expire_membership,
    grant_membership,
)

if TYPE_CHECKING:
    from apps.accounts.models import User

pytestmark = pytest.mark.django_db

SUBJECT = "Spring safety seminar"
BODY = "Join us at Livermore on Saturday.\n\nBring your logbook."


def person(email: str, first: str = "Pat", last: str = "Doe", **user: Any) -> User:
    """A member with the member role and a profile on its own DART, Santa Clara County."""
    account = UserFactory(email=email, first_name=first, last_name=last, roles=[MEMBER], **user)
    MemberProfileFactory(user=account)
    return account


def addresses(recipients: list[Recipient]) -> list[str]:
    """The address of each recipient, in order."""
    return [recipient.email for recipient in recipients]


# --------------------------------------------------------------------------
# Recipients: each filter family
# --------------------------------------------------------------------------
def test_with_no_filters_everyone_listed_is_a_recipient_by_surname() -> None:
    """No filter reaches every member and friend, ordered by last name then first."""
    person("zed@example.test", "Zed", "Young")
    person("amy@example.test", "Amy", "Abbott")
    person("friend@example.test", "Fay", "Moss", kind=AccountKind.FRIEND)
    assert addresses(build_recipients({}).recipients) == [
        "amy@example.test",
        "friend@example.test",
        "zed@example.test",
    ]


def test_a_donor_is_never_a_recipient() -> None:
    """A donor is in no member list, so no filter reaches one."""
    person("member@example.test")
    UserFactory(email="donor@example.test", kind=AccountKind.DONOR)
    assert addresses(build_recipients({}).recipients) == ["member@example.test"]


def test_the_kind_filter_reaches_friends_alone(annual_plan: MembershipPlan) -> None:
    """``kind=friend`` lists the friends and leaves the paid-up members out."""
    grant_membership(person("member@example.test"), annual_plan)
    person("friend@example.test", kind=AccountKind.FRIEND)
    assert addresses(build_recipients({"kind": "friend"}).recipients) == ["friend@example.test"]


def test_the_status_filter_reaches_the_expired_members_alone(annual_plan: MembershipPlan) -> None:
    """``status=expired`` lists the members whose membership has lapsed."""
    grant_membership(person("current@example.test"), annual_plan)
    expire_membership(person("lapsed@example.test"), annual_plan)
    assert addresses(build_recipients({"status": "expired"}).recipients) == ["lapsed@example.test"]


def test_the_dart_filter_reaches_one_team() -> None:
    """``dart=<id>`` lists the members of that DART."""
    team = DartFactory(name="Bay Area DART")
    MemberProfileFactory(user=UserFactory(email="team@example.test", roles=[MEMBER]), dart=team)
    person("other@example.test")
    assert addresses(build_recipients({"dart": str(team.pk)}).recipients) == ["team@example.test"]


def test_the_county_filter_reaches_several_counties() -> None:
    """``county`` takes several counties, separated by commas."""
    for email, county in [
        ("marin@example.test", "Marin"),
        ("napa@example.test", "Napa"),
        ("fresno@example.test", "Fresno"),
    ]:
        MemberProfileFactory(user=UserFactory(email=email, roles=[MEMBER]), county=county)
    found = addresses(build_recipients({"county": "Marin,Napa"}).recipients)
    assert sorted(found) == ["marin@example.test", "napa@example.test"]


def test_the_certificate_filter_reaches_the_students() -> None:
    """``certificate=student`` lists the student pilots."""
    MemberProfileFactory(
        user=UserFactory(email="student@example.test", roles=[MEMBER]),
        pilot_certificate_type=PilotCertificateType.STUDENT,
    )
    person("private@example.test")
    found = addresses(build_recipients({"certificate": "student"}).recipients)
    assert found == ["student@example.test"]


def test_the_medical_filter_reaches_basicmed() -> None:
    """``medical=basicmed`` lists the members flying under BasicMed."""
    MemberProfileFactory(
        user=UserFactory(email="basic@example.test", roles=[MEMBER]),
        medical_type=MedicalType.BASICMED,
    )
    person("third@example.test")
    assert addresses(build_recipients({"medical": "basicmed"}).recipients) == ["basic@example.test"]


def test_the_role_filter_reaches_the_holders_of_a_role() -> None:
    """``role=treasurer`` lists the treasurers."""
    UserFactory(email="treasurer@example.test", roles=[MEMBER, TREASURER])
    person("member@example.test")
    found = addresses(build_recipients({"role": TREASURER}).recipients)
    assert found == ["treasurer@example.test"]


def test_the_search_filter_reaches_a_name() -> None:
    """``search`` matches a name, as the member list's search does."""
    person("ada@example.test", "Ada", "Lovelace")
    person("bob@example.test", "Bob", "Smith")
    assert addresses(build_recipients({"search": "Lovelace"}).recipients) == ["ada@example.test"]


def test_the_expiring_within_filter_reaches_the_terms_ending_soon(
    annual_plan: MembershipPlan,
) -> None:
    """``expiring_within=30`` lists the members whose term ends within 30 days."""
    grant_membership(person("soon@example.test"), annual_plan, days_left=10)
    grant_membership(person("later@example.test"), annual_plan, days_left=200)
    found = addresses(build_recipients({"expiring_within": "30"}).recipients)
    assert found == ["soon@example.test"]


def test_a_blank_filter_is_no_filter() -> None:
    """A filter bar sends every key; a blank value narrows nothing."""
    person("one@example.test")
    person("two@example.test", kind=AccountKind.FRIEND)
    found = addresses(build_recipients({"kind": "", "county": ""}).recipients)
    assert sorted(found) == ["one@example.test", "two@example.test"]


# --------------------------------------------------------------------------
# Skips and de-duplication
# --------------------------------------------------------------------------
def test_a_deactivated_account_is_skipped_with_its_reason() -> None:
    """A deactivated account the filters match is listed as skipped, never sent."""
    person("gone@example.test", is_active=False)
    result = build_recipients({})
    assert [(r.email, r.reason) for r in result.skipped] == [
        ("gone@example.test", SKIP_DEACTIVATED)
    ]


def test_a_deactivated_account_is_not_a_recipient() -> None:
    """The deactivated account appears among the skips alone."""
    person("gone@example.test", is_active=False)
    assert build_recipients({}).recipients == []


def test_a_blank_address_is_skipped() -> None:
    """An account with no address on file has nowhere to send to."""
    account = person("blank@example.test")
    type(account).objects.filter(pk=account.pk).update(email="")
    assert [r.reason for r in build_recipients({}).skipped] == [SKIP_NO_ADDRESS]


def bounced(email: str, **user: Any) -> User:
    """A member whose address the bounce check has marked as bounced."""
    return person(
        email,
        email_bounced_at=datetime(2026, 9, 30, 12, 0, tzinfo=UTC),
        email_bounce_detail="5.1.1 user unknown",
        **user,
    )


def test_a_bounced_address_is_skipped_with_its_reason() -> None:
    """An address the bounce check marked is listed among the skips."""
    bounced("gone@example.test")
    assert [(r.email, r.reason) for r in build_recipients({}).skipped] == [
        ("gone@example.test", SKIP_BOUNCED)
    ]


def test_a_bounced_address_is_not_a_recipient() -> None:
    """Nobody is sent a copy at an address that bounced."""
    bounced("gone@example.test")
    assert build_recipients({}).recipients == []


def test_clearing_the_bounce_makes_the_address_a_recipient_again() -> None:
    """Once a user administrator clears the bounce, the address is sent a copy again."""
    account = bounced("back@example.test")
    clear_email_bounce(UserFactory(email="useradmin@example.test"), account)
    assert addresses(build_recipients({}).recipients) == [
        "back@example.test",
        "useradmin@example.test",
    ]


def test_a_send_skips_a_bounced_address(sender: User) -> None:
    """A send records the bounced address as skipped and mails nobody there."""
    bounced("gone@example.test", kind=AccountKind.FRIEND)
    person("ok@example.test", kind=AccountKind.FRIEND)
    bulk = send_bulk_email(subject=SUBJECT, body=BODY, filters={"kind": "friend"}, sender=sender)
    rows = bulk.recipients.order_by("id")
    assert (
        [(r.email, r.status, r.reason) for r in rows],
        [message.to[0] for message in mail.outbox],
    ) == (
        [
            ("ok@example.test", RecipientStatus.SENT, ""),
            ("gone@example.test", RecipientStatus.SKIPPED, SKIP_BOUNCED),
        ],
        ["ok@example.test"],
    )


def test_an_invalid_address_is_skipped() -> None:
    """An address a mail server could never take is skipped as invalid."""
    person("not-an-address")
    assert [(r.email, r.reason) for r in build_recipients({}).skipped] == [
        ("not-an-address", SKIP_INVALID)
    ]


def test_addresses_are_de_duplicated_whatever_their_case() -> None:
    """Two accounts on one address, in different case and spacing, are sent one email.

    The account table refuses two addresses equal but for case, so the second one here
    differs by a leading space as well.
    """
    person("pat@example.test", "Pat", "Able")
    second = person("other@example.test", "Pat", "Baker")
    type(second).objects.filter(pk=second.pk).update(email=" PAT@Example.test")
    result = build_recipients({})
    assert (addresses(result.recipients), [(r.email, r.reason) for r in result.skipped]) == (
        ["pat@example.test"],
        [(" PAT@Example.test", SKIP_DUPLICATE)],
    )


def test_a_recipient_carries_the_account_and_the_name() -> None:
    """Each recipient names the account, the person, and the address."""
    account = person("ada@example.test", "Ada", "Lovelace")
    assert build_recipients({}).recipients == [
        Recipient(user_id=account.pk, name="Ada Lovelace", email="ada@example.test")
    ]


# --------------------------------------------------------------------------
# Sending
# --------------------------------------------------------------------------
@pytest.fixture
def sender(annual_plan: MembershipPlan) -> User:
    """The account that sends the bulk email: a paid-up member, so never a friend."""
    account = UserFactory(email="boss@example.test", first_name="Grace", last_name="Holloway")
    grant_membership(account, annual_plan)
    return account


def refuse_one(address: str) -> Callable[[EmailBackend, list[EmailMessage]], int]:
    """A ``send_messages`` that refuses ``address`` and sends everything else."""
    original = EmailBackend.send_messages

    def send(self: EmailBackend, messages: list[EmailMessage]) -> int:
        if any(address in message.to for message in messages):
            raise smtplib.SMTPRecipientsRefused({address: (550, b"No such user")})
        return original(self, messages)

    return send


def test_a_send_emails_every_recipient(sender: User) -> None:
    """One message per recipient, each to that recipient alone."""
    person("one@example.test")
    person("two@example.test")
    send_bulk_email(subject=SUBJECT, body=BODY, filters={}, sender=sender)
    assert sorted(message.to[0] for message in mail.outbox) == [
        "boss@example.test",
        "one@example.test",
        "two@example.test",
    ]


def test_a_send_goes_out_with_the_subject_as_typed(sender: User) -> None:
    """The subject is the one the sender wrote."""
    person("one@example.test", kind=AccountKind.FRIEND)
    send_bulk_email(subject=SUBJECT, body=BODY, filters={"kind": "friend"}, sender=sender)
    assert [message.subject for message in mail.outbox] == [SUBJECT]


def test_the_plain_text_body_carries_the_message(sender: User) -> None:
    """The text body opens with the message, paragraphs intact."""
    person("one@example.test", kind=AccountKind.FRIEND)
    send_bulk_email(subject=SUBJECT, body=BODY, filters={"kind": "friend"}, sender=sender)
    assert mail.outbox[0].body.startswith(BODY + "\n")


def test_the_html_body_makes_each_paragraph_a_paragraph(sender: User) -> None:
    """A blank line in the message starts a new paragraph in the HTML alternative."""
    person("one@example.test", kind=AccountKind.FRIEND)
    send_bulk_email(
        subject=SUBJECT,
        body="First <b>line</b>.\n\nSecond.",
        filters={"kind": "friend"},
        sender=sender,
    )
    message = mail.outbox[0]
    assert isinstance(message, EmailMultiAlternatives)
    html = str(message.alternatives[0][0])
    assert "<p>First &lt;b&gt;line&lt;/b&gt;.</p>\n\n<p>Second.</p>" in html


def test_every_send_is_in_the_email_log_as_a_bulk_email(sender: User) -> None:
    """Each message is logged under the ``bulk_email`` purpose, naming the account."""
    account = person("one@example.test", kind=AccountKind.FRIEND)
    send_bulk_email(subject=SUBJECT, body=BODY, filters={"kind": "friend"}, sender=sender)
    assert list(EmailLog.objects.values_list("purpose", "user_id", "to_email")) == [
        ("bulk_email", account.pk, "one@example.test")
    ]


def test_a_send_stores_the_message_its_filters_and_its_counts(sender: User) -> None:
    """The stored send carries what was sent, to whom it was aimed, and how it went."""
    person("one@example.test", kind=AccountKind.FRIEND)
    person("gone@example.test", kind=AccountKind.FRIEND, is_active=False)
    bulk = send_bulk_email(
        subject=SUBJECT, body=BODY, filters={"kind": "friend", "county": ""}, sender=sender
    )
    stored = BulkEmail.objects.get(pk=bulk.pk)
    assert (
        stored.subject,
        stored.body,
        stored.filters,
        stored.sender_id,
        stored.sent_count,
        stored.failed_count,
        stored.skipped_count,
    ) == (SUBJECT, BODY, {"kind": "friend"}, sender.pk, 1, 0, 1)


def test_a_send_is_stamped_when_it_finishes(sender: User) -> None:
    """``sent_at`` is set once every message has been tried."""
    with freeze_time("2026-10-02 17:00:00"):
        bulk = send_bulk_email(subject=SUBJECT, body=BODY, filters={}, sender=sender)
    assert bulk.sent_at == datetime(2026, 10, 2, 17, 0, tzinfo=UTC)


def test_every_copy_goes_over_one_connection(sender: User, monkeypatch: pytest.MonkeyPatch) -> None:
    """The send opens one mail connection and sends every copy through it."""
    person("one@example.test", kind=AccountKind.FRIEND)
    person("two@example.test", kind=AccountKind.FRIEND)
    person("three@example.test", kind=AccountKind.FRIEND)
    original = EmailBackend.send_messages
    backends: list[int] = []

    def send(self: EmailBackend, messages: list[EmailMessage]) -> int:
        backends.append(id(self))
        return original(self, messages)

    monkeypatch.setattr(EmailBackend, "send_messages", send)
    send_bulk_email(subject=SUBJECT, body=BODY, filters={"kind": "friend"}, sender=sender)
    assert (len(backends), len(set(backends))) == (3, 1)


def test_a_long_name_is_kept_whole(sender: User) -> None:
    """A 150-character first name and a 150-character last name fit the recipient row."""
    account = person("long@example.test", "A" * 150, "B" * 150, kind=AccountKind.FRIEND)
    bulk = send_bulk_email(subject=SUBJECT, body=BODY, filters={"kind": "friend"}, sender=sender)
    stored = bulk.recipients.get().name
    assert (len(stored), stored) == (301, account.display_name)


def break_on_second_copy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the second copy raise what a killed worker would: the send stops there."""
    original = EmailBackend.send_messages
    calls: list[int] = []

    def send(self: EmailBackend, messages: list[EmailMessage]) -> int:
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("worker timeout")
        return original(self, messages)

    monkeypatch.setattr(EmailBackend, "send_messages", send)


@pytest.fixture
def interrupted(sender: User, monkeypatch: pytest.MonkeyPatch) -> BulkEmail:
    """A send that stopped on its second of three copies, with one friend skipped."""
    person("ann@example.test", "Ann", "Able", kind=AccountKind.FRIEND)
    person("bea@example.test", "Bea", "Bell", kind=AccountKind.FRIEND)
    person("cal@example.test", "Cal", "Cole", kind=AccountKind.FRIEND)
    person("gil@example.test", "Gil", "Gone", kind=AccountKind.FRIEND, is_active=False)
    break_on_second_copy(monkeypatch)
    with pytest.raises(RuntimeError, match="worker timeout"):
        send_bulk_email(subject=SUBJECT, body=BODY, filters={"kind": "friend"}, sender=sender)
    return BulkEmail.objects.get()


def test_an_interrupted_send_keeps_who_was_reached_and_who_was_not(
    interrupted: BulkEmail,
) -> None:
    """Every row is there: the copy that went, the copies never tried, and the skip."""
    rows = interrupted.recipients.order_by("id")
    assert [(r.email, r.status) for r in rows] == [
        ("ann@example.test", RecipientStatus.SENT),
        ("bea@example.test", RecipientStatus.PENDING),
        ("cal@example.test", RecipientStatus.PENDING),
        ("gil@example.test", RecipientStatus.SKIPPED),
    ]


def test_an_interrupted_send_keeps_its_counts_so_far(interrupted: BulkEmail) -> None:
    """The counts say one went and one was skipped, and the send never finished."""
    assert (
        interrupted.sent_count,
        interrupted.failed_count,
        interrupted.skipped_count,
        interrupted.sent_at,
    ) == (1, 0, 1, None)


def test_a_send_records_every_recipient_and_every_skip(sender: User) -> None:
    """One row per person: the sent ones and the skipped ones, with the reasons."""
    one = person("one@example.test", "Ann", "One", kind=AccountKind.FRIEND)
    gone = person("gone@example.test", "Gil", "Gone", kind=AccountKind.FRIEND, is_active=False)
    bulk = send_bulk_email(subject=SUBJECT, body=BODY, filters={"kind": "friend"}, sender=sender)
    rows = BulkEmailRecipient.objects.filter(bulk_email=bulk).order_by("id")
    assert [(r.user_id, r.name, r.email, r.status, r.reason) for r in rows] == [
        (one.pk, "Ann One", "one@example.test", RecipientStatus.SENT, ""),
        (gone.pk, "Gil Gone", "gone@example.test", RecipientStatus.SKIPPED, SKIP_DEACTIVATED),
    ]


def test_a_refused_message_is_recorded_and_the_rest_still_go(
    sender: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A mail server that refuses one address fails that one and sends the others."""
    person("bad@example.test", "Bea", "Bad", kind=AccountKind.FRIEND)
    person("good@example.test", "Gus", "Good", kind=AccountKind.FRIEND)
    monkeypatch.setattr(EmailBackend, "send_messages", refuse_one("bad@example.test"))
    bulk = send_bulk_email(subject=SUBJECT, body=BODY, filters={"kind": "friend"}, sender=sender)
    rows = BulkEmailRecipient.objects.filter(bulk_email=bulk).order_by("id")
    assert [(r.email, r.status, r.reason) for r in rows] == [
        ("bad@example.test", RecipientStatus.FAILED, "Refused by the mail server"),
        ("good@example.test", RecipientStatus.SENT, ""),
    ]


def test_a_refused_message_is_counted_as_failed(
    sender: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The stored counts say one went and one failed."""
    person("bad@example.test", kind=AccountKind.FRIEND)
    person("good@example.test", kind=AccountKind.FRIEND)
    monkeypatch.setattr(EmailBackend, "send_messages", refuse_one("bad@example.test"))
    bulk = send_bulk_email(subject=SUBJECT, body=BODY, filters={"kind": "friend"}, sender=sender)
    assert (bulk.sent_count, bulk.failed_count) == (1, 1)


def test_a_send_writes_one_audit_line(sender: User, audit_log: pytest.LogCaptureFixture) -> None:
    """The audit line names the sender, the send, and the three counts."""
    person("one@example.test", kind=AccountKind.FRIEND)
    bulk = send_bulk_email(subject=SUBJECT, body=BODY, filters={"kind": "friend"}, sender=sender)
    assert audit_messages(audit_log) == [
        f"action=bulk_email.send actor={sender.pk} target={bulk.pk} sent=1 skipped=0 failed=0"
    ]


def test_every_copy_carries_its_own_message_id_on_its_log_row(sender: User) -> None:
    """Each copy's ``Message-ID`` is the one its email log row records."""
    person("one@example.test", kind=AccountKind.FRIEND)
    person("two@example.test", kind=AccountKind.FRIEND)
    send_bulk_email(subject=SUBJECT, body=BODY, filters={"kind": "friend"}, sender=sender)
    sent_ids = sorted(message.message()["Message-ID"] for message in mail.outbox)
    logged_ids = sorted(EmailLog.objects.values_list("message_id", flat=True))
    assert (logged_ids, len(set(sent_ids))) == (sent_ids, 2)


def test_every_copy_goes_out_from_the_bounce_address(sender: User, settings: Settings) -> None:
    """With ``BOUNCE_ADDRESS`` set, each copy's envelope sender is that address."""
    settings.BOUNCE_ADDRESS = "bounces@caldart.example.org"
    person("one@example.test", kind=AccountKind.FRIEND)
    send_bulk_email(subject=SUBJECT, body=BODY, filters={"kind": "friend"}, sender=sender)
    assert [message.from_email for message in mail.outbox] == ["bounces@caldart.example.org"]
