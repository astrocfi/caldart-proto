"""The bounce check: read the bounce mailbox, mark what bounced, and flag the address.

``apps.mail.bounces.check_bounces`` reads every unseen message from the mailbox
``BOUNCE_IMAP_URL`` names, through a fake IMAP server here, matches each permanent
failure to the email log row it reports on, and marks the row and its account.  See
``docs/developer/email.rst``, "Bounces".
"""

from __future__ import annotations

import imaplib
from collections.abc import Iterator
from datetime import date, timedelta

import pytest
from django.utils import timezone
from freezegun import freeze_time
from pytest_django import Settings

from apps.accounts.models import User
from apps.mail.bounces import (
    DISABLED_MESSAGE,
    BounceCheckError,
    check_bounces,
)
from apps.mail.models import EmailLog, EmailStatus
from caldart.runs import RunAction
from tests.conftest import BounceReport, FakeMailbox, audit_messages
from tests.factories import EmailLogFactory, UserFactory

pytestmark = pytest.mark.django_db

#: The detail the default hard bounce carries.
POSTFIX_DETAIL = (
    "5.1.1 550 5.1.1 <gone@example.com>: Recipient address rejected: "
    "User unknown in virtual mailbox table"
)

#: When every test sends and checks: the Postfix report's own day.
NOW = "2026-10-01T18:00:00Z"


@pytest.fixture(autouse=True)
def _frozen_clock() -> Iterator[None]:
    """Run every test at :data:`NOW`."""
    with freeze_time(NOW):
        yield


@pytest.fixture
def gone() -> User:
    """The account whose address bounces: Dana Doe, ``gone@example.com``."""
    return UserFactory(email="gone@example.com", first_name="Dana", last_name="Doe")


@pytest.fixture
def sent(gone: User) -> EmailLog:
    """A message sent to ``gone`` an hour ago, with the default report's Message-ID."""
    return EmailLogFactory(
        user=gone,
        message_id="<original.1@caldart.example.org>",
        sent_at=timezone.now() - timedelta(hours=1),
    )


def test_a_hard_bounce_marks_the_row_it_reports_on(
    sent: EmailLog, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """The row the report's Message-ID names becomes ``bounced``."""
    fake_mailbox(bounce_report("hard_bounce"))

    check_bounces()

    sent.refresh_from_db()
    assert sent.status == EmailStatus.BOUNCED


def test_a_bounced_row_carries_when_and_why(
    sent: EmailLog, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """``bounced_at`` is the run's time; ``bounce_detail`` the status and diagnostic."""
    fake_mailbox(bounce_report("hard_bounce"))

    check_bounces()

    sent.refresh_from_db()
    assert (sent.bounced_at, sent.bounce_detail) == (timezone.now(), POSTFIX_DETAIL)


def test_a_hard_bounce_flags_the_account_at_that_address(
    sent: EmailLog, gone: User, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """The account whose current address bounced gets the time and the detail."""
    fake_mailbox(bounce_report("hard_bounce"))

    check_bounces()

    gone.refresh_from_db()
    assert (gone.email_bounced_at, gone.email_bounce_detail) == (timezone.now(), POSTFIX_DETAIL)


def test_the_message_id_wins_over_the_recipient(
    gone: User, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """A report whose Message-ID names an older row marks that row, not the latest one."""
    older = EmailLogFactory(
        user=gone,
        message_id="<older@caldart.example.org>",
        sent_at=timezone.now() - timedelta(days=2),
    )
    newer = EmailLogFactory(user=gone, sent_at=timezone.now() - timedelta(hours=1))
    fake_mailbox(bounce_report("hard_bounce", message_id="<older@caldart.example.org>"))

    check_bounces()

    statuses = dict(EmailLog.objects.values_list("pk", "status"))
    assert statuses == {older.pk: EmailStatus.BOUNCED, newer.pk: EmailStatus.SENT}


def test_a_message_id_match_needs_no_account_at_the_address(
    fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """A row sent to an address with no account behind it is marked all the same."""
    row = EmailLogFactory(
        user=None, to_email="contact@dart.example.org", message_id="<contact@caldart.example.org>"
    )
    fake_mailbox(
        bounce_report(
            "hard_bounce",
            recipient="contact@dart.example.org",
            message_id="<contact@caldart.example.org>",
        )
    )

    check_bounces()

    row.refresh_from_db()
    assert row.status == EmailStatus.BOUNCED


def test_without_a_message_id_the_latest_row_to_the_recipient_matches(
    gone: User, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """A report with no copy of the original matches the latest send to its recipient."""
    earlier = EmailLogFactory(user=gone, sent_at=timezone.now() - timedelta(days=3))
    latest = EmailLogFactory(user=gone, sent_at=timezone.now() - timedelta(days=1))
    fake_mailbox(bounce_report("no_original"))

    check_bounces()

    statuses = dict(EmailLog.objects.values_list("pk", "status"))
    assert statuses == {earlier.pk: EmailStatus.SENT, latest.pk: EmailStatus.BOUNCED}


def test_the_fallback_ignores_the_recipients_case(
    fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """``Gone@Example.com`` in the report matches a row sent to ``gone@example.com``."""
    row = EmailLogFactory(user=None, to_email="gone@example.com")
    fake_mailbox(bounce_report("no_original", recipient="Gone@Example.com"))

    check_bounces()

    row.refresh_from_db()
    assert row.status == EmailStatus.BOUNCED


def test_a_message_id_nobody_sent_falls_back_to_the_recipient(
    gone: User, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """A Message-ID no row carries is no match by itself; the recipient still matches."""
    row = EmailLogFactory(user=gone)
    fake_mailbox(bounce_report("hard_bounce", message_id="<someone-else@example.net>"))

    check_bounces()

    row.refresh_from_db()
    assert row.status == EmailStatus.BOUNCED


def test_the_fallback_reaches_back_seven_days(
    gone: User, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """A send seven days and a minute ago is too old to match by its recipient."""
    EmailLogFactory(user=gone, sent_at=timezone.now() - timedelta(days=7, minutes=1))
    fake_mailbox(bounce_report("no_original"))

    run = check_bounces()

    assert (run.bounced, run.unmatched) == (0, 1)


def test_the_fallback_never_matches_a_refused_send(
    gone: User, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """A row the mail server refused never went out, so it cannot have bounced."""
    EmailLogFactory(user=gone, status=EmailStatus.FAILED, error="SMTPException")
    fake_mailbox(bounce_report("no_original"))

    run = check_bounces()

    assert run.unmatched == 1


def test_an_unmatched_failure_flags_nobody(
    gone: User, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """With no sent message to pin it on, a report changes no account."""
    fake_mailbox(bounce_report("no_original"))

    check_bounces()

    gone.refresh_from_db()
    assert gone.email_bounced_at is None


def test_an_account_that_moved_address_is_not_flagged(
    sent: EmailLog, gone: User, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """The row's account has moved to another address, so the old one is not its own."""
    User.objects.filter(pk=gone.pk).update(email="dana@example.org")
    fake_mailbox(bounce_report("hard_bounce"))

    check_bounces()

    gone.refresh_from_db()
    assert gone.email_bounced_at is None


def test_the_account_at_the_address_is_flagged_even_from_a_row_without_one(
    gone: User, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """A row naming no account still flags the account whose address it was sent to."""
    EmailLogFactory(user=None, to_email="gone@example.com", message_id="<bare@caldart.test>")
    fake_mailbox(bounce_report("hard_bounce", message_id="<bare@caldart.test>"))

    check_bounces()

    gone.refresh_from_db()
    assert gone.email_bounce_detail == POSTFIX_DETAIL


@pytest.mark.parametrize(
    ("report", "fields"),
    [
        ("delay", {}),
        ("auto_reply", {}),
        ("hard_bounce", {"status": "4.2.2"}),
    ],
    ids=["delay", "auto-reply", "transient-failure"],
)
def test_a_message_reporting_no_permanent_failure_is_ignored(
    report: str,
    fields: dict[str, str],
    sent: EmailLog,
    fake_mailbox: FakeMailbox,
    bounce_report: BounceReport,
) -> None:
    """Delays, transient failures and auto-replies count as ignored and change nothing."""
    fake_mailbox(bounce_report(report, **fields))

    run = check_bounces()

    sent.refresh_from_db()
    assert (run.ignored, run.bounced, sent.status) == (1, 0, EmailStatus.SENT)


def test_every_processed_message_is_marked_seen(
    sent: EmailLog, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """A bounce, an unmatched failure and an ignored message are each marked seen."""
    fake = fake_mailbox(
        bounce_report("hard_bounce"),
        bounce_report("no_original", recipient="stranger@example.net"),
        bounce_report("auto_reply"),
    )

    check_bounces()

    assert fake.seen == {"1", "2", "3"}


def test_a_seen_message_is_not_read_again(
    sent: EmailLog, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """A second run finds nothing unseen, so it counts nothing."""
    fake_mailbox(bounce_report("hard_bounce"))
    check_bounces()

    run = check_bounces()

    assert (run.bounced, run.unmatched, run.ignored) == (0, 0, 0)


def test_the_run_counts_and_names_what_it_found(
    sent: EmailLog, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """A bounce, an unmatched failure and an ignored message, each counted and named."""
    fake_mailbox(
        bounce_report("hard_bounce"),
        bounce_report("no_original", recipient="stranger@example.net", status="5.1.10"),
        bounce_report("delay"),
    )

    run = check_bounces()

    assert (run.bounced, run.unmatched, run.ignored) == (1, 1, 1)
    assert run.actions == [
        RunAction(
            kind="bounced",
            member="Dana Doe",
            email="gone@example.com",
            on=date(2026, 10, 1),
            detail=POSTFIX_DETAIL,
        ),
        RunAction(
            kind="unmatched",
            member="",
            email="stranger@example.net",
            detail=(
                "5.1.10 550 5.1.10 RESOLVER.ADR.RecipientNotFound; Recipient not found by "
                "SMTP address lookup"
            ),
        ),
    ]


def test_the_run_signs_in_to_the_configured_mailbox(fake_mailbox: FakeMailbox) -> None:
    """The run opens the URL's host and port, signs in as its user, and opens its box."""
    fake = fake_mailbox()

    check_bounces()

    assert (fake.opened, fake.credentials, fake.mailbox, fake.logged_out) == (
        ("imap.example.org", 993),
        ("bounces@caldart.example.org", "s3cret"),
        "Bounces",
        True,
    )


def test_a_dry_run_changes_no_row_and_no_account(
    sent: EmailLog, gone: User, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """A rehearsal reads and matches, but the row stays sent and the account unflagged."""
    fake_mailbox(bounce_report("hard_bounce"))

    check_bounces(dry_run=True)

    sent.refresh_from_db()
    gone.refresh_from_db()
    assert (sent.status, sent.bounced_at, gone.email_bounced_at) == (EmailStatus.SENT, None, None)


def test_a_dry_run_marks_nothing_seen(
    sent: EmailLog, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """A rehearsal leaves every message unseen for the live run that follows."""
    fake = fake_mailbox(bounce_report("hard_bounce"), bounce_report("delay"))

    check_bounces(dry_run=True)

    assert fake.seen == set()


def test_a_dry_run_reports_what_a_live_run_would_do(
    sent: EmailLog, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """The rehearsal's counts and actions are the live run's."""
    fake_mailbox(bounce_report("hard_bounce"), bounce_report("delay"))
    rehearsal = check_bounces(dry_run=True).as_dict()

    live = check_bounces().as_dict()

    assert rehearsal == live


def test_with_no_mailbox_configured_checking_is_off(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An empty ``BOUNCE_IMAP_URL`` reads nothing and says checking is off."""
    settings.BOUNCE_IMAP_URL = ""

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("no connection may be opened")

    monkeypatch.setattr(imaplib, "IMAP4_SSL", refuse)

    run = check_bounces()

    assert (run.enabled, run.as_lines()) == (False, [DISABLED_MESSAGE])


def test_an_unreachable_mailbox_is_an_error_naming_the_host(fake_mailbox: FakeMailbox) -> None:
    """A server that cannot be reached raises, naming the host but not the password."""
    fake_mailbox(refuse=ConnectionRefusedError(111, "Connection refused"))

    with pytest.raises(
        BounceCheckError, match=r"^Could not reach the bounce mailbox at imap\.example\.org"
    ):
        check_bounces()


def test_a_mailbox_the_server_lacks_is_an_error_naming_it(fake_mailbox: FakeMailbox) -> None:
    """A mailbox that will not open raises, naming the mailbox and the host."""
    fake = fake_mailbox()
    fake.mailboxes = set()

    with pytest.raises(
        BounceCheckError, match=r"^Could not open the mailbox Bounces at imap\.example\.org$"
    ):
        check_bounces()


def test_a_malformed_url_is_an_error(settings: Settings) -> None:
    """A ``BOUNCE_IMAP_URL`` that is not ``imaps://`` raises before anything is opened."""
    settings.BOUNCE_IMAP_URL = "https://example.org/"

    with pytest.raises(BounceCheckError, match=r"^BOUNCE_IMAP_URL must be imaps://"):
        check_bounces()


def test_a_run_writes_one_audit_record(
    sent: EmailLog,
    fake_mailbox: FakeMailbox,
    bounce_report: BounceReport,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """``bounces.run`` carries the mode, whether checking is on, and the counts."""
    fake_mailbox(bounce_report("hard_bounce"), bounce_report("auto_reply"))

    check_bounces(dry_run=True)

    assert audit_messages(audit_log) == [
        "action=bounces.run actor=command target=- dry_run=true enabled=true "
        "bounced=1 unmatched=0 ignored=1"
    ]


def test_the_summary_names_each_bounce(
    sent: EmailLog, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """The printed summary ends with one line per bounce, in the run's tense."""
    fake_mailbox(bounce_report("hard_bounce"))

    lines = check_bounces(dry_run=True).as_lines()

    assert lines[-1] == (
        f"would mark bounced Dana Doe <gone@example.com> sent 2026-10-01 ({POSTFIX_DETAIL})"
    )
