"""Bounce detection: read the bounce mailbox and mark what came back.

Every message ``caldart.mail.send_templated`` sends carries a ``Message-ID`` stored on
its :class:`~apps.mail.models.EmailLog` row, and, when ``BOUNCE_ADDRESS`` is set, that
address as its envelope sender, so a server that later refuses the message returns its
report there.  :func:`check_bounces` reads the unseen messages in that mailbox over IMAP
(``BOUNCE_IMAP_URL``), reads each as an RFC 3464 delivery-status report
(:func:`parse_report`), and for every permanent failure marks the email log row
**bounced** and flags the account whose current address it was.

The run is the shared scheduled-run shape: counts (``bounced``, ``unmatched``,
``ignored``) and one :class:`~caldart.runs.RunAction` per failure, and a dry run that
reports exactly what a live one would do while changing nothing, on the server or in
the mailbox.  ``manage.py check_bounces`` runs it hourly, and ``POST
/system/bounces/run`` runs it from the Scheduled tasks page.
"""

from __future__ import annotations

import email
import email.errors
import email.policy
import imaplib
import logging
import re
import ssl
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from email.message import Message
from email.parser import HeaderParser
from typing import Any
from urllib.parse import unquote, urlsplit

from django.conf import settings
from django.db import DatabaseError, transaction
from django.db.models import Model
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from apps.accounts.models import User
from apps.mail.models import EmailLog, EmailStatus
from caldart import audit
from caldart.runs import RunAction

log = logging.getLogger(__name__)

#: The scheme ``BOUNCE_IMAP_URL`` must use: IMAP over TLS from the first byte.
IMAP_SCHEME = "imaps"

#: The port an ``imaps://`` URL that names none connects to.
IMAP_DEFAULT_PORT = 993

#: The mailbox a URL with no path reads.
IMAP_DEFAULT_MAILBOX = "INBOX"

#: How long one conversation with the IMAP server may wait, in seconds.
IMAP_TIMEOUT_SECONDS = 30

#: What a malformed ``BOUNCE_IMAP_URL`` is told; it never repeats the URL itself,
#: which carries the mailbox password.
IMAP_URL_FORM = "BOUNCE_IMAP_URL must be imaps://user:password@host[:port]/MAILBOX"

#: The largest message the check fetches, in bytes.  A delivery report is a few
#: kilobytes even with the original's headers; anything bigger is left unread.
MAX_MESSAGE_BYTES = 1_048_576

#: Every control character, NUL included, which no header value the check stores may
#: carry: Postgres refuses a NUL in text outright.
CONTROL_CHARACTERS = re.compile(r"[\x00-\x1f\x7f]")

#: How far back a report with no usable ``Message-ID`` is matched by its recipient.
FALLBACK_WINDOW = timedelta(days=7)

#: The longest ``bounce_detail`` stored, the width of both columns that hold it.
DETAIL_MAX_LENGTH = 255

#: The content types a delivery-status part is sent as (RFC 3464, and RFC 6533's
#: internationalized form).
DELIVERY_STATUS_TYPES = frozenset({"message/delivery-status", "message/global-delivery-status"})

#: The content types a report returns the original message's headers as.
ORIGINAL_HEADER_TYPES = frozenset({"text/rfc822-headers", "text/global-headers"})

#: The content types a report returns the whole original message as.
ORIGINAL_MESSAGE_TYPES = frozenset({"message/rfc822", "message/global"})

#: The action kinds a run records: a matched permanent failure, and one no sent
#: message could be found for.
BOUNCED_KIND = "bounced"
UNMATCHED_KIND = "unmatched"

#: What a run with no mailbox configured says, on the command line and the screen.
DISABLED_MESSAGE = "Bounce checking is off: BOUNCE_IMAP_URL is not set."


class BounceCheckError(Exception):
    """The bounce mailbox could not be read, or ``BOUNCE_IMAP_URL`` is malformed.

    The message is a sentence an operator can act on and never carries the password.
    """


@dataclass(frozen=True)
class ImapAddress:
    """Where the bounce mailbox is: server, port, account, password and mailbox.

    The password is left out of the dataclass's ``repr``, so a traceback or a log line
    that prints the address never carries it.
    """

    host: str
    port: int
    user: str
    password: str = field(repr=False)
    mailbox: str


@dataclass(frozen=True)
class FailedRecipient:
    """One recipient a delivery-status report says was permanently refused.

    ``address`` is the report's ``Final-Recipient``, ``status`` its three-part status
    code (``5.1.1``), and ``diagnostic`` the remote server's own words, with the
    ``smtp;`` type prefix and the line folding removed; it is ``""`` when the report
    gives none.
    """

    address: str
    status: str
    diagnostic: str

    @property
    def detail(self) -> str:
        """``"<status> <diagnostic>"``, cut to :data:`DETAIL_MAX_LENGTH` characters."""
        return f"{self.status} {self.diagnostic}".strip()[:DETAIL_MAX_LENGTH]


@dataclass(frozen=True)
class DeliveryReport:
    """What one delivery-status report says.

    ``message_id`` is the returned original's ``Message-ID``, angle brackets included,
    or ``""`` when the report carries no copy of its headers.  ``failures`` holds every
    permanent failure it reports, in report order, and is empty for a report of a
    delay, a transient failure, or a delivery.
    """

    message_id: str
    failures: tuple[FailedRecipient, ...]


@sensitive_variables()
def parse_imap_url(url: str) -> ImapAddress:
    """Read ``url``, of the form ``imaps://user:password@host[:port]/MAILBOX``.

    The user name, the password and the mailbox are percent-decoded, so an address as
    the user name is written with ``%40`` for its ``@``.  The port defaults to
    :data:`IMAP_DEFAULT_PORT` and an empty mailbox to ``INBOX``.  Any other scheme, a
    missing user name, password or host, or a port that is not a number raises
    :class:`BounceCheckError` with :data:`IMAP_URL_FORM`.
    """
    parts = urlsplit(url)
    try:
        port = parts.port or IMAP_DEFAULT_PORT
    except ValueError as exc:
        raise BounceCheckError(IMAP_URL_FORM) from exc
    if (
        parts.scheme != IMAP_SCHEME
        or not parts.hostname
        or not parts.username
        or parts.password is None
    ):
        raise BounceCheckError(IMAP_URL_FORM)
    return ImapAddress(
        host=parts.hostname,
        port=port,
        user=unquote(parts.username),
        password=unquote(parts.password),
        mailbox=unquote(parts.path.lstrip("/")) or IMAP_DEFAULT_MAILBOX,
    )


def parse_report(raw: bytes) -> DeliveryReport | None:
    """Read ``raw`` as an RFC 3464 delivery-status report, or answer ``None``.

    A message is a report when one of its parts is ``message/delivery-status``; an
    auto-reply, a challenge, or anything else that reached the mailbox is not, and
    neither is something that cannot be read as mail at all.  Only a recipient block
    with ``Action: failed`` and a ``5.x.x`` status is a failure: a delay, a ``4.x.x``
    transient failure and a delivery notice are reports with no failure.  The
    original's ``Message-ID`` is read from a returned ``text/rfc822-headers`` part or a
    returned ``message/rfc822`` message, whichever the report carries.
    """
    try:
        message = email.message_from_bytes(raw, policy=email.policy.compat32)
        parts = list(message.walk())
        status_parts = [part for part in parts if part.get_content_type() in DELIVERY_STATUS_TYPES]
        if len(status_parts) == 0:
            return None
        failures = tuple(
            failure
            for part in status_parts
            for block in _status_blocks(part)
            if (failure := _permanent_failure(block)) is not None
        )
        return DeliveryReport(message_id=_original_message_id(parts), failures=failures)
    except (email.errors.MessageError, LookupError, ValueError, TypeError) as exc:
        log.warning("Could not read a message in the bounce mailbox: %s", exc)
        return None


def _status_blocks(part: Message) -> list[Message]:
    """The header blocks of a delivery-status part: the message's, then each recipient's.

    The standard library splits ``message/delivery-status`` into blocks itself; the
    internationalized form arrives as text, which is split on its blank lines here.
    """
    payload = part.get_payload()
    if isinstance(payload, list):
        return [block for block in payload if isinstance(block, Message)]
    text = part.get_payload(decode=True)
    if not isinstance(text, bytes):
        return []
    decoded = text.decode("utf-8", errors="replace").replace("\r\n", "\n")
    return [HeaderParser().parsestr(chunk) for chunk in decoded.split("\n\n") if chunk.strip()]


def _permanent_failure(block: Message) -> FailedRecipient | None:
    """The failure one recipient block reports, or ``None`` when it is not permanent."""
    action = _unfolded(block.get("Action", "")).lower()
    status = _unfolded(block.get("Status", "")).split(" ", 1)[0]
    recipient = _address_field(block.get("Final-Recipient", ""))
    if action != "failed" or not status.startswith("5.") or not recipient:
        return None
    return FailedRecipient(
        address=recipient,
        status=status,
        diagnostic=_address_field(block.get("Diagnostic-Code", "")),
    )


def _original_message_id(parts: list[Message]) -> str:
    """The returned original's ``Message-ID``, or ``""`` when the report carries none."""
    for part in parts:
        content_type = part.get_content_type()
        if content_type in ORIGINAL_HEADER_TYPES:
            headers = part.get_payload(decode=True)
            if isinstance(headers, bytes):
                parsed = HeaderParser().parsestr(headers.decode("utf-8", errors="replace"))
                return _unfolded(parsed.get("Message-ID", ""))
        if content_type in ORIGINAL_MESSAGE_TYPES:
            payload = part.get_payload()
            if isinstance(payload, list) and len(payload) > 0 and isinstance(payload[0], Message):
                return _unfolded(payload[0].get("Message-ID", ""))
    return ""


def _address_field(value: str) -> str:
    """A typed field such as ``rfc822; gone@example.com`` without its type, unfolded.

    The value after the first ``;`` is kept, with any surrounding angle brackets taken
    off an address; a value with no ``;`` is kept whole.
    """
    kind, separator, rest = _unfolded(value).partition(";")
    text = rest.strip() if separator else kind.strip()
    if text.startswith("<") and text.endswith(">"):
        return text[1:-1]
    return text


def _unfolded(value: object) -> str:
    """A header value with control characters gone and whitespace collapsed to one space.

    Each control character, a NUL included, becomes a space before the runs of
    whitespace (the header's folding among them) collapse, so no value read from a
    report can carry one into the database.
    """
    return " ".join(CONTROL_CHARACTERS.sub(" ", str(value)).split())


@dataclass
class BounceRun:
    """Structured summary of one bounce check.

    Printed by ``manage.py check_bounces`` and answered by ``POST /system/bounces/run``
    as ``{enabled, bounced, unmatched, ignored, skipped, actions}``.  ``enabled`` is
    false when ``BOUNCE_IMAP_URL`` is empty and nothing was read.  ``bounced`` counts the
    permanent failures matched to a sent message, ``unmatched`` those no sent message
    could be found for, and ``ignored`` the messages read that reported no permanent
    failure (delays, transient failures, auto-replies, anything else) or that could not
    be recorded.  ``skipped`` counts the messages left unread in the mailbox: one the
    server would not hand over, and one larger than :data:`MAX_MESSAGE_BYTES`.
    ``actions`` holds one :class:`~caldart.runs.RunAction` per failure, ``bounced`` or
    ``unmatched``.
    """

    today: date
    dry_run: bool
    enabled: bool
    bounced: int = 0
    unmatched: int = 0
    ignored: int = 0
    skipped: int = 0
    actions: list[RunAction] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        """The counts and the actions ``POST /system/bounces/run`` answers with."""
        return {
            "enabled": self.enabled,
            "bounced": self.bounced,
            "unmatched": self.unmatched,
            "ignored": self.ignored,
            "skipped": self.skipped,
            "actions": [action.as_dict() for action in self.actions],
        }

    def as_lines(self) -> list[str]:
        """Human-readable summary, one fact per line, then one line per failure.

        With bounce checking off the summary is :data:`DISABLED_MESSAGE` alone.
        """
        if not self.enabled:
            return [DISABLED_MESSAGE]
        lines = [
            f"today            {self.today.isoformat()}",
            f"mode             {'dry run (nothing changed)' if self.dry_run else 'live'}",
            f"bounced          {self.bounced}",
            f"unmatched        {self.unmatched}",
            f"ignored          {self.ignored}",
            f"skipped          {self.skipped}",
        ]
        return lines + [self._action_line(action) for action in self.actions]

    def _action_line(self, action: RunAction) -> str:
        """One failure as a line: who it was, when the message went, and the detail."""
        if action.kind == UNMATCHED_KIND:
            return f"unmatched {action.email} ({action.detail})"
        verb = "would mark bounced" if self.dry_run else "marked bounced"
        sent = f" sent {action.on.isoformat()}" if action.on is not None else ""
        return f"{verb} {action.member} <{action.email}>{sent} ({action.detail})"


def bounce_checking_enabled() -> bool:
    """True when a bounce mailbox is configured, so the bounce check has one to read.

    That is ``BOUNCE_IMAP_URL`` set to anything; whether it can be read is only known
    once a run tries.
    """
    return bool(settings.BOUNCE_IMAP_URL)


def check_bounces(*, dry_run: bool = False, actor: Model | str = audit.COMMAND_ACTOR) -> BounceRun:
    """Read the unseen messages in the bounce mailbox and mark what bounced.

    With ``BOUNCE_IMAP_URL`` empty, nothing is read and the run answers ``enabled``
    false.  Otherwise the mailbox is opened over TLS with the server's certificate and
    host name verified, and every unseen message of at most :data:`MAX_MESSAGE_BYTES` is
    fetched without marking it, read by :func:`parse_report`, and each permanent failure
    is matched to an email log row: the row whose ``message_id`` is the original's
    ``Message-ID``, or, when the report carries none that matches, the latest row sent
    to the failed address (ignoring case) in the last seven days that the mail server
    did not refuse.  A message with a ``Message-ID`` match counts as one bounce whatever
    its failures say.

    A match marks the row ``bounced`` with ``bounced_at`` now and the failure's
    ``bounce_detail``, and flags the account whose current address is the one the row
    was sent to, ignoring case, by setting its ``email_bounced_at`` and
    ``email_bounce_detail``; an account that has moved to another address since is not
    flagged.  Each message's writes are one savepoint: one that fails in the database is
    rolled back, logged by its message number alone, and counted as ignored, and the run
    carries on.  Each message read, recorded or not, is then marked seen, so the next
    run skips it.  A message the server will not hand over, or one too large to be a
    report, is counted as skipped and left unseen.

    A dry run opens the mailbox read-only (IMAP ``EXAMINE``), fetches and matches
    exactly as a live one, and writes nothing and marks nothing seen.  Every run that
    finished reading the mailbox, and every run with checking off, ends with one
    ``bounces.run`` audit record carrying the mode and the counts.

    Raises :class:`BounceCheckError` when ``BOUNCE_IMAP_URL`` is malformed or the
    mailbox cannot be reached, signed in to, opened, or read.  The audit record is then
    not written, but rows a live run marked before the failure stay marked, and their
    messages stay seen.
    """
    run = BounceRun(today=timezone.localdate(), dry_run=dry_run, enabled=False)
    if bounce_checking_enabled():
        run.enabled = True
        _read_mailbox(parse_imap_url(settings.BOUNCE_IMAP_URL), run)
    audit.record(
        audit.BOUNCES_RUN,
        actor=actor,
        dry_run=dry_run,
        enabled=run.enabled,
        bounced=run.bounced,
        unmatched=run.unmatched,
        ignored=run.ignored,
        skipped=run.skipped,
    )
    return run


# The frames below this one hold the mailbox password (the address, and imaplib's
# own login frame), so an error report shows none of their variables.
@sensitive_variables()
def _read_mailbox(address: ImapAddress, run: BounceRun) -> None:
    """Process every unseen message at ``address`` into ``run``, then sign out."""
    try:
        connection = imaplib.IMAP4_SSL(
            address.host,
            address.port,
            ssl_context=ssl.create_default_context(),
            timeout=IMAP_TIMEOUT_SECONDS,
        )
    except (OSError, imaplib.IMAP4.error) as exc:
        raise BounceCheckError(
            f"Could not reach the bounce mailbox at {address.host}: {exc}"
        ) from exc
    try:
        connection.login(address.user, address.password)
        status, _count = connection.select(_quoted_mailbox(address.mailbox), readonly=run.dry_run)
        if status != "OK":
            raise BounceCheckError(
                f"Could not open the mailbox {address.mailbox} at {address.host}"
            )
        for number in _unseen(connection, f"SMALLER {MAX_MESSAGE_BYTES + 1}"):
            _process(connection, number, run)
        oversized = _unseen(connection, f"LARGER {MAX_MESSAGE_BYTES}")
        if len(oversized) > 0:
            log.warning(
                "Left %d message(s) larger than %d bytes unread in the bounce mailbox",
                len(oversized),
                MAX_MESSAGE_BYTES,
            )
        run.skipped += len(oversized)
    except (OSError, imaplib.IMAP4.error) as exc:
        raise BounceCheckError(
            f"Could not read the bounce mailbox at {address.host}: {exc}"
        ) from exc
    finally:
        _sign_out(connection)


def _unseen(connection: imaplib.IMAP4, size: str) -> list[str]:
    """The numbers of the unseen messages matching the IMAP ``size`` criterion."""
    _status, found = connection.search(None, "UNSEEN", size)
    return (found[0] or b"").decode("ascii").split()


def _quoted_mailbox(mailbox: str) -> str:
    """``mailbox`` as an IMAP argument: quoted when it holds a space, as IMAP requires."""
    return f'"{mailbox}"' if " " in mailbox else mailbox


def _sign_out(connection: imaplib.IMAP4) -> None:
    """End the IMAP session, logging rather than raising when the server has gone."""
    try:
        connection.logout()
    except (OSError, imaplib.IMAP4.error) as exc:
        log.warning("Signing out of the bounce mailbox failed: %s", exc)


def _process(connection: imaplib.IMAP4, number: str, run: BounceRun) -> None:
    """Fetch message ``number``, record its report, and mark it seen unless rehearsing.

    A fetch the server refuses leaves the message unseen and counts it as skipped.  A
    report whose writes fail in the database is rolled back to its savepoint, counted
    as ignored, and still marked seen, so one bad message cannot stop every later run.
    """
    status, data = connection.fetch(number, "(BODY.PEEK[])")
    raw = next((item[1] for item in data if isinstance(item, tuple)), None)
    if status != "OK" or raw is None:
        log.warning("The bounce mailbox would not hand over message %s; left unread", number)
        run.skipped += 1
        return
    report = parse_report(raw)
    if report is None or len(report.failures) == 0:
        run.ignored += 1
    else:
        _record_isolated(report, number, run)
    if not run.dry_run:
        connection.store(number, "+FLAGS", "\\Seen")


def _record_isolated(report: DeliveryReport, number: str, run: BounceRun) -> None:
    """Record ``report`` in a savepoint, counting it as ignored when the database refuses.

    The run's counts and actions are put back as they were before the report, so a
    failed report adds nothing but its one ``ignored``.  The log line names the message
    number and the error class alone: the report carries addresses.
    """
    before = (run.bounced, run.unmatched, len(run.actions))
    try:
        with transaction.atomic():
            _record_report(report, run)
    except DatabaseError as exc:
        log.warning(
            "Could not record bounce report %s in the bounce mailbox: %s",
            number,
            type(exc).__name__,
        )
        run.bounced, run.unmatched = before[0], before[1]
        del run.actions[before[2] :]
        run.ignored += 1


def _record_report(report: DeliveryReport, run: BounceRun) -> None:
    """Match ``report``'s failures to email log rows, marking each unless rehearsing."""
    now = timezone.now()
    by_id = _row_by_message_id(report.message_id)
    if by_id is not None:
        failure = next(
            (f for f in report.failures if f.address.lower() == by_id.to_email.lower()),
            report.failures[0],
        )
        _mark(by_id, failure, now, run)
        return
    for failure in report.failures:
        row = _latest_row_to(failure.address, now)
        if row is None:
            run.unmatched += 1
            run.actions.append(
                RunAction(
                    kind=UNMATCHED_KIND, member="", email=failure.address, detail=failure.detail
                )
            )
        else:
            _mark(row, failure, now, run)


def _row_by_message_id(message_id: str) -> EmailLog | None:
    """The row sent with ``message_id``, or ``None`` for ``""`` or no such row."""
    if not message_id:
        return None
    return EmailLog.objects.select_related("user").filter(message_id=message_id).first()


def _latest_row_to(address: str, now: datetime) -> EmailLog | None:
    """The latest unrefused row sent to ``address`` within :data:`FALLBACK_WINDOW`."""
    return (
        EmailLog.objects.select_related("user")
        .filter(to_email__iexact=address, sent_at__gte=now - FALLBACK_WINDOW)
        .exclude(status=EmailStatus.FAILED)
        .order_by("-sent_at", "-id")
        .first()
    )


def _mark(row: EmailLog, failure: FailedRecipient, now: datetime, run: BounceRun) -> None:
    """Count ``row`` as bounced and, outside a rehearsal, mark it and flag its address."""
    run.bounced += 1
    run.actions.append(
        RunAction(
            kind=BOUNCED_KIND,
            member=row.recipient_name,
            email=row.to_email,
            on=timezone.localdate(row.sent_at),
            detail=failure.detail,
        )
    )
    if run.dry_run:
        return
    row.status = EmailStatus.BOUNCED
    row.bounced_at = now
    row.bounce_detail = failure.detail
    row.save(update_fields=["status", "bounced_at", "bounce_detail", "updated_at"])
    User.objects.filter(email__iexact=row.to_email).update(
        email_bounced_at=now, email_bounce_detail=failure.detail, updated_at=now
    )
