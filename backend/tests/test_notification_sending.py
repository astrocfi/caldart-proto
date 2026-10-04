"""Sending an event: one email per address that may hear about it, once it commits.

``caldart.events.emit`` hands the event to the notifications dispatcher, which builds
the email at once and sends it when the raising transaction commits.  Each active
subscription that lists the event, and whose recipient may receive it, is sent one
email; a sign-up also goes to the contacts checked to receive the chosen DART's
roster.  Every send is recorded in the email log under ``notification_<slug>``, and a
refused send never stops the next one or fails the request that raised the event.
"""

from __future__ import annotations

import logging

import pytest
from django.core.mail import EmailMessage, EmailMultiAlternatives
from pytest_django.fixtures import DjangoCaptureOnCommitCallbacks

from apps.accounts.models import User
from apps.accounts.roles import ACCOUNT_ADMIN, MEMBER, TREASURER
from apps.darts.models import Dart
from apps.mail.models import EmailLog, EmailStatus
from apps.mail.purposes import PURPOSE_LABELS
from apps.notifications import dispatch
from apps.notifications.events import EVENTS
from apps.notifications.models import NotificationSubscription
from caldart.events import EVENT_SLUGS, emit
from tests.factories import DartContactFactory, DartFactory, UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def pat() -> User:
    """A member named Pat Quill, who signs up."""
    return UserFactory(email="pat@example.test", first_name="Pat", last_name="Quill")


@pytest.fixture
def north() -> Dart:
    """The DART Pat chose, with no roster contact yet."""
    return DartFactory(name="North Bay DART")


def subscribe(email: str, events: list[str], **fields: object) -> NotificationSubscription:
    """A saved subscription of ``email`` to ``events``, with any other ``fields``."""
    return NotificationSubscription.objects.create(recipient_email=email, events=events, **fields)


def sign_up(capture: DjangoCaptureOnCommitCallbacks, user: User, dart: Dart | None = None) -> None:
    """Raise ``signed_up`` for ``user`` and ``dart``, running what waits on the commit."""
    with capture(execute=True):
        emit("signed_up", user=user, dart=dart)


def recipients(outbox: list[EmailMessage]) -> list[str]:
    """The single address of each email sent, in the order they went."""
    return [address for message in outbox for address in message.to]


# -- the purposes ----------------------------------------------------------------
@pytest.mark.parametrize("slug", EVENT_SLUGS)
def test_each_event_has_an_email_log_label(slug: str) -> None:
    """The email log reads ``notification_<slug>`` as ``Notification: <label>``."""
    assert PURPOSE_LABELS[f"notification_{slug}"] == f"Notification: {EVENTS[slug].label}"


def test_the_notification_purposes_follow_the_dart_roster_in_catalog_order() -> None:
    """The purpose filter offers the notifications last, in the catalog's order."""
    purposes = list(PURPOSE_LABELS)
    start = purposes.index("dart_roster") + 1

    assert purposes[start:] == [f"notification_{slug}" for slug in EVENT_SLUGS]


# -- who is sent it --------------------------------------------------------------
def test_a_subscribed_address_is_sent_the_event(
    pat: User,
    north: Dart,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """An active subscription that lists the event is sent one email."""
    subscribe("outside@example.test", ["signed_up"])

    sign_up(django_capture_on_commit_callbacks, pat, north)

    assert recipients(mailoutbox) == ["outside@example.test"]


def test_nothing_is_sent_before_the_transaction_commits(
    pat: User,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """The send waits on the commit, so a rolled-back request sends nothing."""
    subscribe("outside@example.test", ["signed_up"])

    with django_capture_on_commit_callbacks(execute=False):
        emit("signed_up", user=pat, dart=None)

    assert mailoutbox == []


def test_the_email_carries_the_subject_the_headline_the_lines_and_the_link(
    pat: User,
    north: Dart,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """The plain-text body prints the headline, each labeled line, and the link."""
    subscribe("outside@example.test", ["signed_up"])

    sign_up(django_capture_on_commit_callbacks, pat, north)

    message = mailoutbox[0]
    assert message.subject == "CalDART: Pat Quill signed up as a member"
    assert "Pat Quill signed up as a member" in message.body
    assert "DART: North Bay DART" in message.body
    assert f"http://localhost:8000/portal/admin/members/{pat.pk}" in message.body


def test_the_html_body_carries_the_headline_and_the_link(
    pat: User,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """The HTML alternative carries the same headline and link."""
    subscribe("outside@example.test", ["signed_up"])

    sign_up(django_capture_on_commit_callbacks, pat)

    message = mailoutbox[0]
    assert isinstance(message, EmailMultiAlternatives)
    html, _mimetype = message.alternatives[0]
    assert isinstance(html, str)
    assert "Pat Quill signed up as a member" in html
    assert f'href="http://localhost:8000/portal/admin/members/{pat.pk}"' in html


def test_the_email_log_records_the_notification_purpose(
    pat: User,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """Each send is logged under ``notification_<slug>``."""
    subscribe("outside@example.test", ["signed_up"])

    sign_up(django_capture_on_commit_callbacks, pat)

    assert list(EmailLog.objects.values_list("purpose", flat=True)) == ["notification_signed_up"]


def test_a_bound_account_is_logged_with_its_account_and_name(
    pat: User,
    account_admin: User,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """A subscription bound to an account is logged against that account by name."""
    subscribe(account_admin.email, ["signed_up"], recipient_user=account_admin)

    sign_up(django_capture_on_commit_callbacks, pat)

    row = EmailLog.objects.get()
    assert (row.user_id, row.to_name) == (account_admin.pk, "Zoe Yeager")


def test_an_event_the_subscription_does_not_list_is_not_sent(
    pat: User,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """A subscription hears only about the events it lists."""
    subscribe("outside@example.test", ["became_member"])

    sign_up(django_capture_on_commit_callbacks, pat)

    assert mailoutbox == []


def test_a_paused_subscription_is_not_sent(
    pat: User,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """A subscription whose ``is_active`` is false is sent nothing."""
    subscribe("outside@example.test", ["signed_up"], is_active=False)

    sign_up(django_capture_on_commit_callbacks, pat)

    assert mailoutbox == []


def test_an_account_without_a_role_for_the_event_is_skipped_and_stays_active(
    pat: User,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """A bound account the event's roles do not admit is skipped; nothing is paused."""
    cashier = UserFactory(email="cashier@example.test", roles=[MEMBER, TREASURER])
    subscription = subscribe(cashier.email, ["signed_up"], recipient_user=cashier)

    sign_up(django_capture_on_commit_callbacks, pat)

    subscription.refresh_from_db()
    assert (recipients(mailoutbox), subscription.is_active) == ([], True)


def test_a_deactivated_account_is_skipped(
    pat: User,
    account_admin: User,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """An inactive account is sent nothing."""
    account_admin.is_active = False
    account_admin.save(update_fields=["is_active"])
    subscribe(account_admin.email, ["signed_up"], recipient_user=account_admin)

    sign_up(django_capture_on_commit_callbacks, pat)

    assert mailoutbox == []


def test_a_bare_address_an_account_has_taken_is_bound_to_it_at_send_time(
    pat: User,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """The account that took the address is bound, and its roles decide from then on."""
    subscription = subscribe("taken@example.test", ["signed_up"])
    taker = UserFactory(email="taken@example.test", roles=[MEMBER])

    sign_up(django_capture_on_commit_callbacks, pat)

    subscription.refresh_from_db()
    assert (recipients(mailoutbox), subscription.recipient_user) == ([], taker)


def test_a_bound_subscription_follows_its_account_to_a_changed_address(
    pat: User,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """The email goes to the account's current address, which the subscription stores."""
    staff = UserFactory(email="staff@example.test", roles=[MEMBER, ACCOUNT_ADMIN])
    subscription = subscribe(staff.email, ["signed_up"], recipient_user=staff)
    staff.email = "Moved@example.test"
    staff.save(update_fields=["email"])

    sign_up(django_capture_on_commit_callbacks, pat)

    subscription.refresh_from_db()
    assert (recipients(mailoutbox), subscription.recipient_email) == (
        ["moved@example.test"],
        "moved@example.test",
    )


def test_an_account_moved_to_an_address_with_its_own_subscription_is_sent_once(
    pat: User,
    caplog: pytest.LogCaptureFixture,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """One email goes out, the clash is logged, and the bare row takes the account."""
    staff = UserFactory(email="staff@example.test", roles=[MEMBER, ACCOUNT_ADMIN])
    bound = subscribe(staff.email, ["signed_up"], recipient_user=staff)
    bare = subscribe("moved@example.test", ["signed_up"])
    staff.email = "moved@example.test"
    staff.save(update_fields=["email"])

    with caplog.at_level(logging.WARNING, logger="apps.notifications.dispatch"):
        sign_up(django_capture_on_commit_callbacks, pat)

    bound.refresh_from_db()
    bare.refresh_from_db()
    assert recipients(mailoutbox) == ["moved@example.test"]
    assert f"notification subscription {bound.pk} shares its address" in caplog.text
    assert (bound.recipient_email, bare.recipient_user) == ("staff@example.test", staff)


def test_a_bound_account_that_may_receive_the_event_is_sent_it(
    pat: User,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """An account administrator may hear about a sign-up."""
    staff = UserFactory(email="staff@example.test", roles=[MEMBER, ACCOUNT_ADMIN])
    subscribe(staff.email, ["signed_up"], recipient_user=staff)

    sign_up(django_capture_on_commit_callbacks, pat)

    assert recipients(mailoutbox) == ["staff@example.test"]


def test_each_subscribed_address_is_sent_its_own_email(
    pat: User,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """Two subscriptions mean two emails, in address order."""
    subscribe("zed@example.test", ["signed_up"])
    subscribe("amy@example.test", ["signed_up", "became_member"])

    sign_up(django_capture_on_commit_callbacks, pat)

    assert recipients(mailoutbox) == ["amy@example.test", "zed@example.test"]


# -- the DART's roster contacts ----------------------------------------------------
def test_a_sign_up_goes_to_the_dart_roster_contacts_unsubscribed(
    pat: User,
    north: Dart,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """Every contact checked to receive the chosen DART's roster hears of the sign-up."""
    DartContactFactory(dart=north, email="lead@example.test", receives_roster=True)
    DartContactFactory(dart=north, email="quiet@example.test", receives_roster=False)

    sign_up(django_capture_on_commit_callbacks, pat, north)

    assert recipients(mailoutbox) == ["lead@example.test"]


def test_a_roster_contact_is_logged_by_name_with_the_notification_purpose(
    pat: User,
    north: Dart,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """The contact's name and the sign-up purpose are recorded, with no account."""
    DartContactFactory(dart=north, name="Lee Lead", email="lead@example.test", receives_roster=True)

    sign_up(django_capture_on_commit_callbacks, pat, north)

    row = EmailLog.objects.get()
    assert (row.purpose, row.to_name, row.user_id) == (
        "notification_signed_up",
        "Lee Lead",
        None,
    )


def test_an_address_both_subscribed_and_on_the_roster_is_sent_once(
    pat: User,
    north: Dart,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """One address hears of one sign-up once, whatever the case it is written in."""
    subscribe("lead@example.test", ["signed_up"])
    DartContactFactory(dart=north, email="Lead@Example.test", receives_roster=True)

    sign_up(django_capture_on_commit_callbacks, pat, north)

    assert recipients(mailoutbox) == ["lead@example.test"]


def test_only_a_sign_up_goes_to_the_roster_contacts(
    pat: User,
    north: Dart,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """Another event about a person on the DART reaches nobody unsubscribed."""
    DartContactFactory(dart=north, email="lead@example.test", receives_roster=True)

    with django_capture_on_commit_callbacks(execute=True):
        emit("became_member", user=pat, how="paid")

    assert mailoutbox == []


def test_the_roster_contact_is_told_why_they_hear_of_it(
    pat: User,
    north: Dart,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """The footer says the DART lists the contact to receive its roster."""
    DartContactFactory(dart=north, email="lead@example.test", receives_roster=True)

    sign_up(django_capture_on_commit_callbacks, pat, north)

    assert "the North Bay DART lists you to receive its roster" in mailoutbox[0].body


def test_a_subscriber_is_told_why_they_hear_of_it(
    pat: User,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """The footer names the notification the address is subscribed to."""
    subscribe("outside@example.test", ["signed_up"])

    sign_up(django_capture_on_commit_callbacks, pat)

    assert "subscribed to the Sign-up notification" in mailoutbox[0].body


# -- a refused send ----------------------------------------------------------------
@pytest.mark.usefixtures("refusing_mail_server")
def test_a_refused_send_is_logged_and_the_next_recipient_is_still_tried(
    pat: User,
    caplog: pytest.LogCaptureFixture,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """Every recipient is tried, each refusal is a failed log row, and none raises."""
    subscribe("amy@example.test", ["signed_up"])
    subscribe("zed@example.test", ["signed_up"])

    with caplog.at_level(logging.ERROR, logger="apps.notifications.dispatch"):
        sign_up(django_capture_on_commit_callbacks, pat)

    statuses = list(EmailLog.objects.order_by("to_email").values_list("to_email", "status"))
    assert statuses == [
        ("amy@example.test", EmailStatus.FAILED),
        ("zed@example.test", EmailStatus.FAILED),
    ]
    assert "notification send failed" in caplog.text


def test_an_unexpected_send_error_still_leaves_the_next_recipient_tried(
    pat: User,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """A send raising something besides a mail refusal is logged, and the loop goes on."""
    subscribe("amy@example.test", ["signed_up"])
    subscribe("zed@example.test", ["signed_up"])
    tried: list[str] = []

    def send(*, to: str, **kwargs: object) -> None:
        tried.append(to)
        if to == "amy@example.test":
            raise ValueError("Header values may not contain linefeed or carriage return")

    monkeypatch.setattr(dispatch, "send_templated", send)

    with caplog.at_level(logging.ERROR, logger="apps.notifications.dispatch"):
        sign_up(django_capture_on_commit_callbacks, pat)

    assert tried == ["amy@example.test", "zed@example.test"]
    assert "notification send failed: event=signed_up error=ValueError" in caplog.text


def test_an_event_whose_email_cannot_be_built_does_not_fail_the_caller(
    caplog: pytest.LogCaptureFixture,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """A payload missing its objects is logged and sends nothing; ``emit`` returns."""
    subscribe("outside@example.test", ["signed_up"])

    with (
        caplog.at_level(logging.ERROR, logger="apps.notifications.dispatch"),
        django_capture_on_commit_callbacks(execute=True),
    ):
        emit("signed_up", dart=None)

    assert mailoutbox == []
    assert "notification not built: event=signed_up" in caplog.text


# -- suspending the dispatcher, for seeding ---------------------------------------
def test_an_event_raised_while_suspended_sends_nothing(
    pat: User,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """Inside :func:`dispatch.suspended`, a subscribed address hears nothing."""
    subscribe("outside@example.test", ["signed_up"])

    with dispatch.suspended(), django_capture_on_commit_callbacks(execute=True):
        emit("signed_up", user=pat, dart=None)

    assert mailoutbox == []


def test_the_dispatcher_resumes_once_suspended_ends(
    pat: User,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """The dispatcher hears events again once the ``suspended`` block ends."""
    subscribe("outside@example.test", ["signed_up"])
    with dispatch.suspended():
        pass

    sign_up(django_capture_on_commit_callbacks, pat)

    assert recipients(mailoutbox) == ["outside@example.test"]


def test_suspended_resumes_the_dispatcher_even_when_the_block_raises(
    pat: User,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """A block that raises still leaves the dispatcher subscribed afterward."""
    subscribe("outside@example.test", ["signed_up"])
    with pytest.raises(ValueError, match="boom"), dispatch.suspended():
        raise ValueError("boom")

    sign_up(django_capture_on_commit_callbacks, pat)

    assert recipients(mailoutbox) == ["outside@example.test"]
