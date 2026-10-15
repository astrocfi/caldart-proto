"""The bounce check: read the bounce mailbox, mark what bounced, and flag the address.

``apps.mail.bounces.check_bounces`` reads every unseen message from the mailbox
``BOUNCE_IMAP_URL`` names, through a fake IMAP server here, matches each report to the
email log row its signed bounce address names, and marks the row and its account.  A
report not addressed to a valid signed address marks nothing.  See
``docs/developer/email.rst``, "Bounces".
"""

from __future__ import annotations

import imaplib
import ssl
from collections.abc import Iterator
from datetime import date, timedelta
from typing import Any

import pytest
from django.db import DataError, connection
from django.utils import timezone
from freezegun import freeze_time
from pytest_django import Settings

from apps.accounts.models import User
from apps.mail.bounces import (
    DISABLED_MESSAGE,
    MAX_MESSAGE_BYTES,
    REPORT_MAX_AGE,
    BounceCheckError,
    BounceRun,
    check_bounces,
)
from apps.mail.models import EmailLog, EmailStatus
from caldart.mail import signed_bounce_address
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


def _signed(row: EmailLog) -> str:
    """The signed bounce address ``row``'s message went out from."""
    return signed_bounce_address(row.pk, row.message_id)


@pytest.fixture
def signed(sent: EmailLog, fake_mailbox: FakeMailbox) -> str:
    """The signed bounce address ``sent`` went out from."""
    return _signed(sent)


def test_a_report_to_a_signed_address_marks_that_row_bounced(
    sent: EmailLog, signed: str, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """The row the report's signed address names becomes ``bounced``."""
    fake_mailbox(bounce_report("hard_bounce", envelope=signed))

    check_bounces()

    sent.refresh_from_db()
    assert sent.status == EmailStatus.BOUNCED


def test_a_bounced_row_carries_when_and_why(
    sent: EmailLog, signed: str, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """``bounced_at`` is the run's time; ``bounce_detail`` the status and diagnostic."""
    fake_mailbox(bounce_report("hard_bounce", envelope=signed))

    check_bounces()

    sent.refresh_from_db()
    assert (sent.bounced_at, sent.bounce_detail) == (timezone.now(), POSTFIX_DETAIL)


def test_a_hard_bounce_flags_the_account_at_that_address(
    signed: str, gone: User, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """The account whose current address bounced gets the time and the detail."""
    fake_mailbox(bounce_report("hard_bounce", envelope=signed))

    check_bounces()

    gone.refresh_from_db()
    assert (gone.email_bounced_at, gone.email_bounce_detail) == (timezone.now(), POSTFIX_DETAIL)


@pytest.mark.parametrize("header", ["to", "delivered_to", "original_to"])
def test_any_address_header_the_mailbox_shows_may_carry_the_signed_address(
    header: str,
    sent: EmailLog,
    signed: str,
    fake_mailbox: FakeMailbox,
    bounce_report: BounceReport,
) -> None:
    """``To``, ``Delivered-To``, or ``X-Original-To`` alone naming the row is enough."""
    fake_mailbox(bounce_report("hard_bounce", **{header: signed}))

    check_bounces()

    sent.refresh_from_db()
    assert sent.status == EmailStatus.BOUNCED


@pytest.mark.parametrize("report", ["attached_original", "no_original"])
def test_a_report_with_or_without_the_original_counts_by_its_address(
    report: str, sent: EmailLog, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """Gmail's and Exchange's reports count when delivered to the signed address."""
    fake_mailbox(bounce_report(report, envelope=_signed(sent)))

    check_bounces()

    sent.refresh_from_db()
    assert sent.status == EmailStatus.BOUNCED


def test_the_signed_address_wins_over_the_message_id(
    gone: User, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """A report signed for one row with another's Message-ID marks the signed row."""
    older = EmailLogFactory(user=gone, sent_at=timezone.now() - timedelta(days=2))
    newer = EmailLogFactory(
        user=gone, message_id="<newer@caldart.example.org>", sent_at=timezone.now()
    )
    fake_mailbox(
        bounce_report(
            "hard_bounce", envelope=_signed(older), message_id="<newer@caldart.example.org>"
        )
    )

    check_bounces()

    statuses = dict(EmailLog.objects.values_list("pk", "status"))
    assert statuses == {older.pk: EmailStatus.BOUNCED, newer.pk: EmailStatus.SENT}


def test_the_report_is_pinned_on_the_signed_rows_recipient(
    gone: User, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """A report naming another address still flags only the row's own recipient."""
    olga = UserFactory(email="olga@example.org")
    row = EmailLogFactory(user=olga)
    fake_mailbox(bounce_report("hard_bounce", envelope=_signed(row)))

    check_bounces()

    flagged = set(User.objects.filter(email_bounced_at__isnull=False).values_list("pk", flat=True))
    assert flagged == {olga.pk}


def test_a_signed_row_needs_no_account_at_the_address(
    fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """A row sent to an address with no account behind it is marked all the same."""
    row = EmailLogFactory(user=None, to_email="contact@dart.example.org")
    fake_mailbox(
        bounce_report("hard_bounce", recipient="contact@dart.example.org", envelope=_signed(row))
    )

    check_bounces()

    row.refresh_from_db()
    assert row.status == EmailStatus.BOUNCED


def _with_signature_changed(address: str) -> str:
    """``address`` with its signature replaced by digits the site never made."""
    signature = address.partition("@")[0].rpartition(".")[2]
    return address.replace(signature, "0123456789abcdef")


#: The forged reports about ``sent``: one to the bare bounce address naming its
#: recipient, one to the bare address carrying its Message-ID, one to its id under a
#: made-up signature, and one genuinely signed for an id no row has.
FORGERIES = ["bare-address", "message-id-alone", "bad-signature", "unknown-id"]


@pytest.fixture(params=FORGERIES)
def forged_run(
    request: pytest.FixtureRequest,
    sent: EmailLog,
    signed: str,
    fake_mailbox: FakeMailbox,
    bounce_report: BounceReport,
) -> BounceRun:
    """The run that reads one forged report about ``sent``."""
    reports = {
        "bare-address": lambda: bounce_report("no_original"),
        "message-id-alone": lambda: bounce_report("hard_bounce", message_id=sent.message_id),
        "bad-signature": lambda: bounce_report(
            "hard_bounce", envelope=_with_signature_changed(signed)
        ),
        "unknown-id": lambda: bounce_report(
            "hard_bounce", envelope=signed_bounce_address(sent.pk + 1000, sent.message_id)
        ),
    }
    fake_mailbox(reports[request.param]())
    return check_bounces()


def test_a_forged_report_leaves_the_row_sent(forged_run: BounceRun, sent: EmailLog) -> None:
    """A report anybody could write changes no row."""
    sent.refresh_from_db()
    assert sent.status == EmailStatus.SENT


def test_a_forged_report_flags_nobody(forged_run: BounceRun, gone: User) -> None:
    """A report anybody could write flags no account."""
    gone.refresh_from_db()
    assert gone.email_bounced_at is None


def test_a_forged_report_counts_no_bounce(forged_run: BounceRun) -> None:
    """A report anybody could write is not counted as bounced."""
    assert forged_run.bounced == 0


def test_a_forged_report_counts_as_unmatched(forged_run: BounceRun) -> None:
    """Its one failure is counted as unmatched, so an operator sees it came in."""
    assert forged_run.unmatched == 1


@pytest.fixture
def refused_run(
    gone: User, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> tuple[EmailLog, BounceRun]:
    """A row the mail server refused, and the run over a report to its signed address."""
    row = EmailLogFactory(user=gone, status=EmailStatus.FAILED, error="SMTPException")
    fake_mailbox(bounce_report("hard_bounce", envelope=_signed(row)))
    return row, check_bounces()


def test_a_report_of_a_refused_send_is_unmatched(refused_run: tuple[EmailLog, BounceRun]) -> None:
    """A row the mail server refused never went out, so it cannot have bounced."""
    _row, run = refused_run
    assert run.unmatched == 1


def test_a_report_of_a_refused_send_leaves_the_row_failed(
    refused_run: tuple[EmailLog, BounceRun],
) -> None:
    """The refused row keeps reading ``failed``."""
    row, _run = refused_run
    row.refresh_from_db()
    assert row.status == EmailStatus.FAILED


def test_a_report_of_a_refused_send_flags_nobody(
    refused_run: tuple[EmailLog, BounceRun], gone: User
) -> None:
    """The account at the refused row's address is not flagged."""
    gone.refresh_from_db()
    assert gone.email_bounced_at is None


@pytest.fixture
def reused(
    gone: User, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> tuple[EmailLog, User]:
    """An id a rewound sequence gave a second message, and a report about the first.

    The first message, to Dana, is signed and deleted; the table's sequence is set back,
    as restoring an older backup or resetting the database does, so the next message,
    to Olga, gets the same id.  The report is then delivered to the first message's
    signed address.  Answers Olga's row and account.
    """
    first = EmailLogFactory(user=gone)
    address = _signed(first)
    reused_id = first.pk
    first.delete()
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT setval(pg_get_serial_sequence(%s, 'id'), %s, false)",
            [EmailLog._meta.db_table, reused_id],
        )
    olga = UserFactory(email="olga@example.org")
    second = EmailLogFactory(user=olga)
    assert second.pk == reused_id
    fake_mailbox(bounce_report("hard_bounce", envelope=address))
    check_bounces()
    return second, olga


def test_a_report_to_a_reused_id_leaves_the_new_row_sent(reused: tuple[EmailLog, User]) -> None:
    """The signature was made over the first message's Message-ID, not the second's."""
    row, _olga = reused
    row.refresh_from_db()
    assert row.status == EmailStatus.SENT


def test_a_report_to_a_reused_id_flags_nobody(reused: tuple[EmailLog, User]) -> None:
    """The second message's recipient is not flagged by a report about the first."""
    _row, olga = reused
    olga.refresh_from_db()
    assert olga.email_bounced_at is None


@pytest.mark.parametrize(
    ("age", "status"),
    [
        (REPORT_MAX_AGE - timedelta(minutes=1), EmailStatus.BOUNCED),
        (REPORT_MAX_AGE + timedelta(minutes=1), EmailStatus.SENT),
    ],
    ids=["within-30-days", "older-than-30-days"],
)
def test_a_report_counts_only_for_a_send_of_the_last_30_days(
    age: timedelta,
    status: str,
    gone: User,
    fake_mailbox: FakeMailbox,
    bounce_report: BounceReport,
) -> None:
    """A genuine report of a message sent more than 30 days ago marks nothing."""
    row = EmailLogFactory(user=gone, sent_at=timezone.now() - age)
    fake_mailbox(bounce_report("hard_bounce", envelope=_signed(row)))

    check_bounces()

    row.refresh_from_db()
    assert row.status == status


@pytest.mark.parametrize(
    ("status", "flagged"),
    [
        ("5.1.1", True),
        ("5.1.10", True),
        ("5.2.1", True),
        ("5.2.2", False),
        ("5.3.4", False),
        ("5.6.0", False),
        ("5.7.1", False),
    ],
    ids=[
        "no-such-user",
        "recipient-not-found",
        "mailbox-disabled",
        "mailbox-full",
        "message-too-big",
        "bad-content",
        "policy-refusal",
    ],
)
def test_only_a_bad_address_flags_the_account(
    status: str,
    flagged: bool,
    signed: str,
    gone: User,
    fake_mailbox: FakeMailbox,
    bounce_report: BounceReport,
) -> None:
    """``5.1.x`` and ``5.2.1`` flag the address; content and policy refusals do not."""
    fake_mailbox(bounce_report("hard_bounce", envelope=signed, status=status))

    check_bounces()

    gone.refresh_from_db()
    assert (gone.email_bounced_at is not None) is flagged


@pytest.mark.parametrize("status", ["5.2.2", "5.3.4", "5.6.0", "5.7.1"])
def test_a_refusal_of_the_message_still_marks_its_row(
    status: str,
    sent: EmailLog,
    signed: str,
    fake_mailbox: FakeMailbox,
    bounce_report: BounceReport,
) -> None:
    """A content or policy refusal marks the row bounced, with its detail."""
    fake_mailbox(bounce_report("hard_bounce", envelope=signed, status=status))

    check_bounces()

    sent.refresh_from_db()
    assert sent.status == EmailStatus.BOUNCED


def test_an_unmatched_failure_flags_nobody(
    gone: User, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """With no sent message to pin it on, a report changes no account."""
    fake_mailbox(bounce_report("no_original"))

    check_bounces()

    gone.refresh_from_db()
    assert gone.email_bounced_at is None


def test_an_account_that_moved_address_is_not_flagged(
    signed: str, gone: User, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """The row's account has moved to another address, so the old one is not its own."""
    User.objects.filter(pk=gone.pk).update(email="dana@example.org")
    fake_mailbox(bounce_report("hard_bounce", envelope=signed))

    check_bounces()

    gone.refresh_from_db()
    assert gone.email_bounced_at is None


def test_the_account_at_the_address_is_flagged_even_from_a_row_without_one(
    gone: User, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """A row naming no account still flags the account whose address it was sent to."""
    row = EmailLogFactory(user=None, to_email="gone@example.com")
    fake_mailbox(bounce_report("hard_bounce", envelope=_signed(row)))

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
    fake_mailbox(bounce_report(report, envelope=_signed(sent), **fields))

    run = check_bounces()

    sent.refresh_from_db()
    assert (run.ignored, run.bounced, sent.status) == (1, 0, EmailStatus.SENT)


def test_every_processed_message_is_marked_seen(
    sent: EmailLog, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """A bounce, an unmatched failure and an ignored message are each marked seen."""
    fake = fake_mailbox(
        bounce_report("hard_bounce", envelope=_signed(sent)),
        bounce_report("no_original", recipient="stranger@example.net"),
        bounce_report("auto_reply"),
    )

    check_bounces()

    assert fake.seen == {"1", "2", "3"}


def test_a_seen_message_is_not_read_again(
    sent: EmailLog, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """A second run finds nothing unseen, so it counts nothing."""
    fake_mailbox(bounce_report("hard_bounce", envelope=_signed(sent)))
    check_bounces()

    run = check_bounces()

    assert (run.bounced, run.unmatched, run.ignored) == (0, 0, 0)


def test_the_run_counts_and_names_what_it_found(
    sent: EmailLog, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """A bounce, an unmatched failure and an ignored message, each counted and named."""
    fake_mailbox(
        bounce_report("hard_bounce", envelope=_signed(sent)),
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
    fake_mailbox(bounce_report("hard_bounce", envelope=_signed(sent)))

    check_bounces(dry_run=True)

    sent.refresh_from_db()
    gone.refresh_from_db()
    assert (sent.status, sent.bounced_at, gone.email_bounced_at) == (EmailStatus.SENT, None, None)


def test_a_dry_run_marks_nothing_seen(
    sent: EmailLog, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """A rehearsal leaves every message unseen for the live run that follows."""
    fake = fake_mailbox(
        bounce_report("hard_bounce", envelope=_signed(sent)), bounce_report("delay")
    )

    check_bounces(dry_run=True)

    assert fake.seen == set()


def test_a_dry_run_reports_what_a_live_run_would_do(
    sent: EmailLog, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """The rehearsal's counts and actions are the live run's."""
    fake_mailbox(bounce_report("hard_bounce", envelope=_signed(sent)), bounce_report("delay"))
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


def test_without_a_bounce_address_checking_is_off(
    fake_mailbox: FakeMailbox, settings: Settings
) -> None:
    """With ``BOUNCE_ADDRESS`` empty no report could be signed, so nothing is read."""
    fake = fake_mailbox()
    settings.BOUNCE_ADDRESS = ""

    run = check_bounces()

    assert run.enabled is False
    assert fake.opened is None


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
    settings.BOUNCE_ADDRESS = "bounces@caldart.example.org"

    with pytest.raises(BounceCheckError, match=r"^BOUNCE_IMAP_URL must be imaps://"):
        check_bounces()


def test_a_run_writes_one_audit_record(
    sent: EmailLog,
    fake_mailbox: FakeMailbox,
    bounce_report: BounceReport,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """``bounces.run`` carries the mode, whether checking is on, and the counts."""
    fake_mailbox(bounce_report("hard_bounce", envelope=_signed(sent)), bounce_report("auto_reply"))

    check_bounces(dry_run=True)

    assert audit_messages(audit_log) == [
        "action=bounces.run actor=command target=- dry_run=true enabled=true "
        "bounced=1 unmatched=0 ignored=1 skipped=0"
    ]


def test_the_summary_names_each_bounce(
    sent: EmailLog, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """The printed summary ends with one line per bounce, in the run's tense."""
    fake_mailbox(bounce_report("hard_bounce", envelope=_signed(sent)))

    lines = check_bounces(dry_run=True).as_lines()

    assert lines[-1] == (
        f"would mark bounced Dana Doe <gone@example.com> sent 2026-10-01 ({POSTFIX_DETAIL})"
    )


def test_the_mailbox_is_opened_with_the_certificate_verified(fake_mailbox: FakeMailbox) -> None:
    """The TLS context requires a valid certificate for the server's own host name."""
    fake = fake_mailbox()

    check_bounces()

    assert fake.ssl_context is not None
    assert (fake.ssl_context.verify_mode, fake.ssl_context.check_hostname) == (
        ssl.CERT_REQUIRED,
        True,
    )


@pytest.mark.parametrize(("dry_run", "readonly"), [(True, True), (False, False)])
def test_a_dry_run_opens_the_mailbox_read_only(
    dry_run: bool, readonly: bool, fake_mailbox: FakeMailbox
) -> None:
    """A rehearsal opens the mailbox with ``EXAMINE``; a live run with ``SELECT``."""
    fake = fake_mailbox()

    check_bounces(dry_run=dry_run)

    assert fake.readonly is readonly


def test_a_message_the_server_will_not_hand_over_is_skipped_and_left_unseen(
    sent: EmailLog, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """A ``NO`` to the fetch is counted as skipped and the message stays unread."""
    fake = fake_mailbox(
        bounce_report("hard_bounce", envelope=_signed(sent)), bounce_report("delay")
    )
    fake.unfetchable = {"1"}

    run = check_bounces()

    assert (run.skipped, run.ignored, fake.seen) == (1, 1, {"2"})


def test_a_message_too_large_to_be_a_report_is_skipped_unread(
    sent: EmailLog, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """A message over a megabyte is never fetched, counted as skipped, and left unseen."""
    huge = bounce_report("hard_bounce", envelope=_signed(sent)) + b"x" * (MAX_MESSAGE_BYTES + 1)
    fake = fake_mailbox(huge)

    run = check_bounces()

    sent.refresh_from_db()
    assert (run.skipped, fake.seen, sent.status) == (1, set(), EmailStatus.SENT)


def test_control_characters_never_reach_the_database(
    sent: EmailLog, fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """A NUL in the diagnostic is stored as a space, so the row is still marked."""
    raw = bounce_report("hard_bounce", envelope=_signed(sent)).replace(
        b"550 5.1.1 <gone", b"550\x005.1.1 <gone"
    )
    fake_mailbox(raw)

    check_bounces()

    sent.refresh_from_db()
    assert sent.bounce_detail == POSTFIX_DETAIL


def test_a_nul_in_the_recipient_is_no_error(
    fake_mailbox: FakeMailbox, bounce_report: BounceReport
) -> None:
    """A report naming an address with a NUL in it is read, left unmatched, and seen."""
    fake = fake_mailbox(bounce_report("no_original", recipient="gone\x00@example.com"))

    run = check_bounces()

    assert (run.unmatched, fake.seen) == (1, {"1"})


def test_a_report_the_database_refuses_is_ignored_and_the_run_carries_on(
    sent: EmailLog,
    fake_mailbox: FakeMailbox,
    bounce_report: BounceReport,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One failing write is rolled back and counted as ignored; the next one is read."""
    later = EmailLogFactory(user=None, to_email="later@example.com")
    calls: list[EmailLog] = []
    original_save = EmailLog.save

    def failing_once(self: EmailLog, *args: Any, **kwargs: Any) -> None:
        calls.append(self)
        if len(calls) == 1:
            raise DataError("invalid byte sequence")
        original_save(self, *args, **kwargs)

    monkeypatch.setattr(EmailLog, "save", failing_once)
    fake = fake_mailbox(
        bounce_report("hard_bounce", envelope=_signed(sent)),
        bounce_report("no_original", recipient="later@example.com", envelope=_signed(later)),
    )

    run = check_bounces()

    later.refresh_from_db()
    assert (run.ignored, run.bounced, later.status, fake.seen) == (
        1,
        1,
        EmailStatus.BOUNCED,
        {"1", "2"},
    )


class _RefusingManager:
    """A manager whose every update the database refuses."""

    def filter(self, **lookups: object) -> _RefusingManager:
        """Answer itself, so ``update`` is what refuses."""
        return self

    def update(self, **values: object) -> int:
        """Refuse, as Postgres refuses text it cannot store."""
        raise DataError("invalid byte sequence")


def test_a_refused_report_keeps_nothing_it_wrote(
    sent: EmailLog,
    fake_mailbox: FakeMailbox,
    bounce_report: BounceReport,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The flag's write fails, so the row's own write rolls back with it, uncounted."""
    monkeypatch.setattr(User, "objects", _RefusingManager())
    fake_mailbox(bounce_report("hard_bounce", envelope=_signed(sent)))

    run = check_bounces()

    sent.refresh_from_db()
    assert (run.bounced, run.ignored, run.actions, sent.status) == (
        0,
        1,
        [],
        EmailStatus.SENT,
    )
