"""Reading delivery-status reports, and the bounce mailbox's address.

``apps.mail.bounces.parse_report`` turns one message from the bounce mailbox into the
permanent failures it reports and the addresses it was delivered to, read from
real-shaped Postfix, Gmail and Exchange reports under ``backend/tests/bounce_reports/``;
``parse_imap_url`` reads ``BOUNCE_IMAP_URL``.  See ``docs/developer/email.rst``,
"Bounces".
"""

from __future__ import annotations

import pytest

from apps.mail.bounces import (
    BounceCheckError,
    FailedRecipient,
    ImapAddress,
    parse_imap_url,
    parse_report,
)
from tests.conftest import BounceReport

#: The diagnostic the Postfix report carries, its folded line unfolded.
POSTFIX_DIAGNOSTIC = (
    "550 5.1.1 <gone@example.com>: Recipient address rejected: "
    "User unknown in virtual mailbox table"
)


def test_a_hard_bounce_reports_its_recipient_status_and_diagnostic(
    bounce_report: BounceReport,
) -> None:
    """A Postfix hard bounce names the address, ``5.1.1``, and the server's words."""
    report = parse_report(bounce_report("hard_bounce"))

    assert report is not None
    assert report.failures == (FailedRecipient("gone@example.com", "5.1.1", POSTFIX_DIAGNOSTIC),)


def test_a_report_names_the_addresses_it_was_delivered_to(bounce_report: BounceReport) -> None:
    """``Delivered-To``, ``X-Original-To`` and ``To`` are read in that order."""
    report = parse_report(
        bounce_report(
            "hard_bounce",
            delivered_to="first@caldart.test",
            original_to="second@caldart.test",
            to="third@caldart.test",
        )
    )

    assert report is not None
    assert report.addressed_to == (
        "first@caldart.test",
        "second@caldart.test",
        "third@caldart.test",
    )


def test_an_address_named_twice_is_listed_once(bounce_report: BounceReport) -> None:
    """The same address in every header is one address."""
    report = parse_report(bounce_report("hard_bounce", envelope="bounces+7.ab@caldart.test"))

    assert report is not None
    assert report.addressed_to == ("bounces+7.ab@caldart.test",)


def test_an_address_header_with_a_display_name_reads_as_its_address(
    bounce_report: BounceReport,
) -> None:
    """``To: CalDART <bounces@...>`` names the address alone."""
    report = parse_report(
        bounce_report("no_original", to="CalDART <bounces+7.ab@caldart.test>", delivered_to="")
    )

    assert report is not None
    assert report.addressed_to == ("bounces+7.ab@caldart.test",)


def test_a_gmail_hard_bounce_reports_its_failure(bounce_report: BounceReport) -> None:
    """A report nesting its explanation in ``multipart/related`` yields its failure."""
    report = parse_report(bounce_report("attached_original", recipient="nobody@example.net"))

    assert report is not None
    assert report.failures == (
        FailedRecipient(
            "nobody@example.net",
            "5.1.1",
            "The email account that you tried to reach does not exist.",
        ),
    )


def test_a_report_without_the_original_still_reports_its_failure(
    bounce_report: BounceReport,
) -> None:
    """A report carrying no copy of the original message reads all the same."""
    report = parse_report(bounce_report("no_original", status="5.1.10"))

    assert report is not None
    assert report.failures == (
        FailedRecipient(
            "gone@example.com",
            "5.1.10",
            "550 5.1.10 RESOLVER.ADR.RecipientNotFound; Recipient not found by SMTP address lookup",
        ),
    )


def test_a_delay_reports_no_failure(bounce_report: BounceReport) -> None:
    """``Action: delayed`` with ``4.4.1`` is a warning, so the report lists no failure."""
    report = parse_report(bounce_report("delay"))

    assert report is not None
    assert report.failures == ()


@pytest.mark.parametrize(
    ("action", "status"),
    [("failed", "4.2.2"), ("delivered", "2.0.0"), ("relayed", "2.0.0"), ("delayed", "5.0.0")],
    ids=["transient-failure", "delivered", "relayed", "delayed-with-5xx"],
)
def test_only_a_failed_action_with_a_5xx_status_is_a_failure(
    action: str, status: str, bounce_report: BounceReport
) -> None:
    """A transient ``4.x.x`` failure, a success, and a delay are none permanent."""
    report = parse_report(bounce_report("hard_bounce", action=action, status=status))

    assert report is not None
    assert report.failures == ()


def test_a_status_with_a_comment_is_read_by_its_code(bounce_report: BounceReport) -> None:
    """``Status: 5.0.0 (permanent failure)`` is a failure with status ``5.0.0``."""
    report = parse_report(bounce_report("no_original", status="5.0.0 (permanent failure)"))

    assert report is not None
    assert [failure.status for failure in report.failures] == ["5.0.0"]


def test_control_characters_are_read_as_spaces(bounce_report: BounceReport) -> None:
    """A NUL or other control character in a field reads as a space, never as itself."""
    raw = bounce_report("no_original").replace(b"Recipient not", b"Recipient\x00\x07not")

    report = parse_report(raw)

    assert report is not None
    assert report.failures[0].diagnostic.startswith(
        "550 5.1.10 RESOLVER.ADR.RecipientNotFound; Recipient not found"
    )


def test_an_auto_reply_is_not_a_report(bounce_report: BounceReport) -> None:
    """An out-of-office answer carries no delivery-status part, so it is not a report."""
    assert parse_report(bounce_report("auto_reply")) is None


def test_bytes_that_are_not_mail_are_not_a_report() -> None:
    """Anything unreadable as a delivery report is answered ``None``, never an error."""
    assert parse_report(b"\x00\xff not an email at all") is None


def test_the_detail_joins_the_status_and_the_diagnostic() -> None:
    """``detail`` is the status code, a space, and the diagnostic text."""
    failure = FailedRecipient("gone@example.com", "5.1.1", "550 User unknown")

    assert failure.detail == "5.1.1 550 User unknown"


def test_the_detail_is_cut_to_255_characters() -> None:
    """A long diagnostic is trimmed so the detail fits the columns that store it."""
    failure = FailedRecipient("gone@example.com", "5.1.1", "x" * 400)

    assert len(failure.detail) == 255


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "imaps://bounces%40caldart.example.org:p%40ss@imap.example.org/Bounces",
            ImapAddress("imap.example.org", 993, "bounces@caldart.example.org", "p@ss", "Bounces"),
        ),
        (
            "imaps://bounces:secret@imap.example.org:1993/",
            ImapAddress("imap.example.org", 1993, "bounces", "secret", "INBOX"),
        ),
        (
            "imaps://bounces:secret@imap.example.org",
            ImapAddress("imap.example.org", 993, "bounces", "secret", "INBOX"),
        ),
        (
            "imaps://bounces:secret@imap.example.org/Bounce%20reports",
            ImapAddress("imap.example.org", 993, "bounces", "secret", "Bounce reports"),
        ),
    ],
    ids=["encoded-credentials", "port", "no-mailbox", "encoded-mailbox"],
)
def test_the_imap_url_names_the_server_the_account_and_the_mailbox(
    url: str, expected: ImapAddress
) -> None:
    """Credentials and mailbox are percent-decoded.

    The port defaults to 993 and the mailbox to INBOX.
    """
    assert parse_imap_url(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "imap://bounces:secret@imap.example.org/INBOX",
        "imaps://imap.example.org/INBOX",
        "imaps://bounces@imap.example.org/INBOX",
        "imaps://bounces:secret@/INBOX",
        "imaps://bounces:secret@imap.example.org:notaport/INBOX",
    ],
    ids=["plain-imap", "no-credentials", "no-password", "no-host", "bad-port"],
)
def test_a_malformed_imap_url_is_refused_without_its_password(url: str) -> None:
    """A URL not of the form ``imaps://user:password@host[:port]/MAILBOX`` is refused.

    The message names the expected form and never repeats the password.
    """
    with pytest.raises(
        BounceCheckError, match=r"^BOUNCE_IMAP_URL must be imaps://user:password@host"
    ) as raised:
        parse_imap_url(url)

    assert "secret" not in str(raised.value)
