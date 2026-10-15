"""One way to send a templated email.

Every email CalDART sends -- a reminder, a receipt, a refund, a renewal notice
-- is a pair of templates under ``backend/templates/emails/``: the ``.txt`` body
is the message proper, and the ``.html`` one an alternative, so a client that
renders no markup still reads the whole thing.  :func:`send_templated` renders
both and sends them, and :func:`org_name` and :func:`contact_email` answer the
two pieces of the letterhead almost every template asks for.

Because every email goes through :func:`send_templated`, it is also the one
place that records what went out: each send writes an ``apps.mail.EmailLog``
row, successful or refused, which is what the email log screen reads.  Each
message carries a ``Message-ID`` stored on that row and, when ``BOUNCE_ADDRESS`` is
set, goes out with an envelope sender tagged with the row's id and signed over the id
and the ``Message-ID`` (:func:`signed_bounce_address`), which is how the bounce check
(``apps.mail.bounces``) ties a returned report to its row and tells a genuine report
from one anybody could write (:func:`bounce_tag`, :func:`bounce_tag_matches`).  A
``List-Unsubscribe`` header a caller passes is written as itself, never as encoded
words, so mail programs can read its links.

A send raises :class:`MailRefusedError` when the mail server refuses the message or
cannot be reached.  A caller that must answer whatever the server does -- a request
whose answer must not depend on the mail, or a change already committed -- sends
through :func:`send_logging_refusal` or :func:`send_on_commit`, which log the refusal
on this module's logger instead of raising it.  A request whose answer must not even
take longer when a message goes out sends through :func:`send_after_response`, after
the client has its answer.  Production routes that logger to the error mail
``ADMIN_EMAILS`` receives.
"""

from __future__ import annotations

import email.policy
import hmac
import logging
import re
import smtplib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from email.headerregistry import BaseHeader, HeaderRegistry, UnstructuredHeader
from email.policy import EmailPolicy, Policy
from email.utils import make_msgid, parseaddr

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.utils import DNS_NAME
from django.db import DatabaseError, connection, transaction
from django.http import HttpResponseBase
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.crypto import salted_hmac

from caldart.org import org_details

log = logging.getLogger(__name__)

#: One attachment: its filename, its bytes, and its media type.
type Attachment = tuple[str, bytes, str]

#: What the transport raises when the mail server refuses the message or cannot be
#: reached.  ``smtplib.SMTPException`` covers a refusal the server states (credentials
#: it will not accept, a sender or recipient it will not take), and ``OSError`` a
#: connection refused, a host that does not resolve, a TLS failure, or a timeout.  The
#: first is a subclass of the second and is named for the reader.  Only an error raised
#: while the message is handed over counts, so a template that does not render is never
#: taken for a refusal.
_TRANSPORT_ERRORS: tuple[type[Exception], ...] = (smtplib.SMTPException, OSError)

#: The ``salted_hmac`` purpose a signed bounce address is keyed with, so its signature
#: can never stand for any other value the site signs.
BOUNCE_SIGNATURE_SALT = "caldart.mail.bounce-address"

#: How many hex digits of the signature a signed bounce address keeps: 64 bits, far
#: beyond guessing, in 16 characters, so the tag (``+``, the id, ``.``, the signature)
#: leaves room in a local part's 64 for the bounce address's own.
BOUNCE_SIGNATURE_LENGTH = 16

#: The most digits an email log id in a signed bounce address may have, so the id
#: always fits the table's ``bigint`` key.
BOUNCE_ID_MAX_DIGITS = 18

#: The longest local part ``BOUNCE_ADDRESS`` may have: an address's local part holds 64
#: characters, and the tag (``+``, the id, ``.``, the signature) takes up to 36 of them.
BOUNCE_LOCAL_PART_MAX_LENGTH = 64 - (1 + BOUNCE_ID_MAX_DIGITS + 1 + BOUNCE_SIGNATURE_LENGTH)

#: The plus tag of a signed bounce address: an email log id and its signature.
_SIGNED_TAG = re.compile(
    rf"(?P<id>[1-9][0-9]{{0,{BOUNCE_ID_MAX_DIGITS - 1}}})"
    rf"\.(?P<signature>[0-9a-f]{{{BOUNCE_SIGNATURE_LENGTH}}})"
)


@dataclass(frozen=True)
class BounceTag:
    """The plus tag of a signed bounce address, read but not yet verified.

    ``log_id`` is the email log id the tag names and ``signature`` the hex digits
    signed with it; :func:`bounce_tag_matches` says whether the signature is the one
    the site gave that row.
    """

    log_id: int
    signature: str


class MailRefusedError(OSError):
    """The mail server refused a message, or could not be reached, as it was handed over.

    ``error`` is the class name of what the transport raised, such as
    ``SMTPAuthenticationError``, and ``code`` the SMTP reply code when the server gave
    one, else ``None``.  The message is those two alone, ``"SMTPRecipientsRefused
    (550)"``, because the transport's own message can carry an email address.  It is an
    ``OSError``, so a job that catches the transport's own errors catches it unchanged.
    """

    def __init__(self, error: str, code: int | None = None) -> None:
        """Store ``error`` and ``code``; the message is ``error``, then the code."""
        super().__init__(error if code is None else f"{error} ({code})")
        self.error = error
        self.code = code

    @classmethod
    def from_transport(cls, exc: BaseException) -> MailRefusedError:
        """The refusal ``exc``, one of the transport's errors, stands for.

        ``code`` is the reply code of an ``smtplib.SMTPResponseException``, or the first
        recipient's code of an ``smtplib.SMTPRecipientsRefused``, and ``None`` for
        anything else, such as a connection that was never made.
        """
        code: int | None = None
        if isinstance(exc, smtplib.SMTPResponseException):
            code = exc.smtp_code
        elif isinstance(exc, smtplib.SMTPRecipientsRefused):
            code = next((reply for reply, _text in exc.recipients.values()), None)
        return cls(type(exc).__name__, code)


class _AddressListHeader(UnstructuredHeader, BaseHeader):
    """A header that is a comma-separated list of angle-bracketed URIs.

    ``List-Unsubscribe`` is one (RFC 2369).  The standard folding writes a word longer
    than a mail line, such as a long signed link, as RFC 2047 encoded words, which hides
    the URIs from the mail programs that read them; this header is instead written
    as itself, one URI to a line.
    """

    def fold(self, *, policy: Policy) -> str:
        """``Name: <uri>,`` then each further URI on a folded line of its own."""
        uris = [uri.strip() for uri in str(self).split(",")]
        return f"{self.name}: " + f",{policy.linesep} ".join(uris) + policy.linesep


def _header_registry() -> HeaderRegistry:
    """The standard header classes, with ``List-Unsubscribe`` as a URI list."""
    registry = HeaderRegistry()
    registry.map_to_type("list-unsubscribe", _AddressListHeader)
    return registry


class _Message(EmailMultiAlternatives):
    """A message whose ``List-Unsubscribe`` stays readable however long its links are.

    Whatever policy a mail backend writes the message with (the SMTP backend names
    ``email.policy.SMTP``, the others the default), it is used with
    :class:`_AddressListHeader` for that header.
    """

    def message(self, *, policy: Policy | None = None) -> email.message.EmailMessage:
        """The message as the mail library builds it, under ``policy`` or the default.

        A policy of the modern API (every one Django names) is used with
        :class:`_AddressListHeader` for ``List-Unsubscribe``; any other is used as given.
        """
        chosen = policy if policy is not None else email.policy.default
        if isinstance(chosen, EmailPolicy):
            chosen = chosen.clone(header_factory=_header_registry())
        return super().message(policy=chosen)


def org_name() -> str:
    """The organization's name, or ``CalDART`` before anyone has set one."""
    return org_details().name


def contact_email() -> str:
    """The address members write to, or ``""``.

    It is empty when the site settings are missing or their ``contact_email`` is
    blank; a template then omits the contact line rather than printing a blank
    one.
    """
    return org_details().contact_email


def send_templated(
    *,
    to: str,
    subject: str,
    template: str,
    context: dict[str, object] | None = None,
    attachments: Sequence[Attachment] = (),
    purpose: str | None = None,
    user_id: int | None = None,
    to_name: str = "",
    mailer: BaseEmailBackend | None = None,
    headers: Mapping[str, str] | None = None,
    reply_to: str = "",
    message_id: str = "",
) -> EmailMultiAlternatives:
    """Render ``emails/<template>.{txt,html}`` and send them to one address.

    ``subject`` is sent as given: the house prefix and the organization's name
    belong to the caller, which knows what the email is about.  ``context``
    renders both bodies.  Each entry of ``attachments`` is attached by filename,
    bytes and media type, which is how a receipt PDF rides along.  The message's
    ``From`` is ``DEFAULT_FROM_EMAIL``, and so is its envelope sender unless
    ``BOUNCE_ADDRESS`` is set.  Then the envelope sender is that address tagged with the
    id of the email log row the send writes and signed over the id and the message's
    ``Message-ID`` (:func:`signed_bounce_address`), the id taken from the table's
    sequence before the hand-over, and a receiving server returns an undeliverable
    message there.  The message carries a
    fresh ``Message-ID`` on the domain of ``DEFAULT_FROM_EMAIL``, recorded on its email
    log row; ``message_id``, when given, is used instead, which is how a caller that
    must record the ``Message-ID`` before the hand-over (one from :func:`new_message_id`)
    can find the message in the email log afterward.

    Every send is recorded in the email log: ``purpose`` names what the message
    was for and defaults to ``template``, which is the right answer wherever one
    template is one kind of message; ``user_id`` is the primary key of the account
    the email concerned, and is left null for an address with no account behind it.
    ``to_name`` is the recipient's name at send time, such as a DART contact's
    name; a caller that leaves it blank while naming ``user_id`` has the account's
    own ``display_name`` recorded instead, so an account-linked row always carries
    the name it had when the email went.

    ``mailer`` is a mail connection to send through (one from
    ``django.core.mail.mailers``), so a caller sending many messages opens one
    connection for all of them; left out, the default mailer sends this message on
    a connection of its own.

    ``headers`` are extra headers the message carries, such as a bulk email's
    ``List-Unsubscribe``; they cannot replace the ``Message-ID`` or the ``From`` this
    function sets.  ``reply_to``, when given, is the message's ``Reply-To`` address.

    The sent message is returned, so a caller can record what went out.  A mail
    server that refuses the message, or cannot be reached, while it is handed over is
    logged as a failed send carrying the exception class, and raises
    :class:`MailRefusedError` from the transport's exception; a caller that must
    survive a refusal catches that and says so in its own log, or sends through
    :func:`send_logging_refusal`.  Anything else the hand-over raises is logged as a
    failed send too and raises unchanged, and an error rendering the templates raises
    before anything is sent or logged.
    """
    rendered = context or {}
    message_id = message_id or new_message_id()
    message_headers = {**(headers or {}), "Message-ID": message_id}
    log_id = _reserve_log_id() if settings.BOUNCE_ADDRESS else None
    envelope_sender = (
        settings.DEFAULT_FROM_EMAIL if log_id is None else signed_bounce_address(log_id, message_id)
    )
    if log_id is not None:
        # Django sends the envelope from ``from_email`` and writes the header from a
        # ``From`` given in ``headers``, which is how the two addresses differ.
        message_headers["From"] = settings.DEFAULT_FROM_EMAIL
    else:
        message_headers.pop("From", None)
    message = _Message(
        subject=subject,
        body=render_to_string(f"emails/{template}.txt", rendered),
        from_email=envelope_sender,
        to=[to],
        headers=message_headers,
        reply_to=[reply_to] if reply_to else None,
    )
    message.attach_alternative(render_to_string(f"emails/{template}.html", rendered), "text/html")
    for filename, content, mimetype in attachments:
        message.attach(filename, content, mimetype)
    filenames = ", ".join(filename for filename, _content, _mimetype in attachments)
    try:
        if mailer is None:
            message.send()
        else:
            mailer.send_messages([message])
    except Exception as exc:
        # Every failure is recorded before it travels on, whatever it is: the log
        # exists to answer "did this member hear from us?", and a refusal nobody
        # wrote down is exactly the case that leaves that unanswerable.
        _record(
            to=to,
            subject=subject,
            purpose=purpose or template,
            user_id=user_id,
            attachments=filenames,
            error=type(exc).__name__,
            to_name=to_name,
            message_id=message_id,
            log_id=log_id,
        )
        if isinstance(exc, _TRANSPORT_ERRORS):
            raise MailRefusedError.from_transport(exc) from exc
        raise
    _record(
        to=to,
        subject=subject,
        purpose=purpose or template,
        user_id=user_id,
        attachments=filenames,
        error="",
        to_name=to_name,
        message_id=message_id,
        log_id=log_id,
    )
    return message


def error_name(exc: BaseException) -> str:
    """The class name a log line gives for ``exc``.

    For a :class:`MailRefusedError` it is the class of what the transport raised, such
    as ``SMTPAuthenticationError``, as the email log records it; for anything else, the
    class of ``exc`` itself.
    """
    if isinstance(exc, MailRefusedError):
        return exc.error
    return type(exc).__name__


def log_refusal(what: str, refusal: MailRefusedError) -> None:
    """Log ``refusal`` at ERROR on the ``caldart.mail`` logger, naming ``what``.

    The record carries the exception class and the SMTP code, if any, and neither the
    transport's message nor a traceback, since either can carry an email address.
    ``what`` names the message and the account by id, such as ``"the password reset
    for account 12"``, never an address.
    """
    log.error(
        "Could not send %s: the mail server refused it or could not be reached (%s)",
        what,
        refusal,
    )


def send_logging_refusal(send: Callable[[], object], *, what: str) -> bool:
    """Call ``send``; True once it returns, False when the mail server refused it.

    A refusal is a :class:`MailRefusedError`.  The failed send is already in the email
    log, written by :func:`send_templated`, and the refusal is logged by
    :func:`log_refusal` naming ``what`` rather than raised, so the caller answers as it
    would had the message gone out.  Anything else ``send`` raises propagates, a
    template that does not render included.
    """
    try:
        send()
    except MailRefusedError as refusal:
        log_refusal(what, refusal)
        return False
    return True


def send_on_commit(send: Callable[[], object], *, what: str) -> None:
    """Call ``send`` once the current transaction commits, logging a refusal.

    The send runs through :func:`send_logging_refusal`, so a mail server that refuses
    the message cannot fail the request or job whose change has already committed;
    outside a transaction the send runs at once.  A transaction that rolls back sends
    nothing.
    """
    transaction.on_commit(lambda: send_logging_refusal(send, what=what))


def send_after_response(
    response: HttpResponseBase, send: Callable[[], object], *, what: str
) -> None:
    """Call ``send`` once ``response`` has gone to the client, logging what goes wrong.

    The WSGI server closes a response after it has written the body, and Django runs
    the response's closers then; ``send`` is added to them.  An answer that must not
    depend on whether a message goes out, nor on how long rendering and sending it
    takes, can therefore be sent first: a client timing the request learns nothing from
    the mail.  The send runs through :func:`send_logging_refusal`, so a refusal is logged
    rather than raised; anything else it raises, a template that does not render
    included, is logged at ERROR on this module's logger with its traceback, since
    Django discards what a closer raises and no answer is left to carry it.  The
    request's transaction has ended by then, so ``send`` sees what it committed.  A
    response that is never closed, such as one a test builds by calling a view
    directly, sends nothing.
    """

    def closer() -> None:
        """Send, logging a refusal or any other failure rather than raising it."""
        try:
            send_logging_refusal(send, what=what)
        except Exception:
            log.exception("Could not send %s after the response", what)

    # Django keeps the closers it runs on close() in this list; it is how a file
    # response closes its file, and the only per-response hook the close offers.
    response._resource_closers.append(closer)  # type: ignore[attr-defined]  # not in django-stubs


def new_message_id() -> str:
    """A fresh ``Message-ID``, in angle brackets, on ``DEFAULT_FROM_EMAIL``'s domain.

    It is what :func:`send_templated` gives a message when the caller names none.
    """
    return make_msgid(domain=_message_id_domain())


def bounce_address() -> str:
    """``BOUNCE_ADDRESS`` as a bare address, without any display name, or ``""``.

    ``CalDART bounces <bounces@caldart.example.org>`` reads as
    ``bounces@caldart.example.org``; the system check ``mail.E001`` asks for the bare
    form in the first place.
    """
    return parseaddr(settings.BOUNCE_ADDRESS)[1]


def signed_bounce_address(log_id: int, message_id: str) -> str:
    """:func:`bounce_address` tagged with ``log_id``, signed over it and ``message_id``.

    The address is ``<local>+<log_id>.<signature>@<domain>``, from the bounce address's
    ``<local>@<domain>``, so a mailbox that accepts plus addresses delivers it to the
    bounce mailbox.  The signature is the first :data:`BOUNCE_SIGNATURE_LENGTH` hex
    digits of an HMAC-SHA256 over ``"<log_id>:<message_id>"``, keyed with ``SECRET_KEY``
    under :data:`BOUNCE_SIGNATURE_SALT`.  Only the site can make one, and because the
    ``Message-ID`` is drawn at random for each message, a signature stays the row's own
    even when a restored or reset database hands the same id to another row later.
    """
    local, at, domain = bounce_address().rpartition("@")
    signature = _bounce_signature(log_id, message_id, settings.SECRET_KEY)
    return f"{local}+{log_id}.{signature}{at}{domain}"


def bounce_tag(address: str) -> BounceTag | None:
    """The tag ``address`` carries when it is shaped as a signed bounce address.

    It is one only on :func:`bounce_address`'s own local part and domain, ignoring case,
    with a plus tag of an id of at most :data:`BOUNCE_ID_MAX_DIGITS` digits, a dot, and
    :data:`BOUNCE_SIGNATURE_LENGTH` hex digits.  The bare bounce address, another
    address, an unsigned tag, and any address at all while ``BOUNCE_ADDRESS`` is empty
    answer ``None``.  Nothing is verified here: :func:`bounce_tag_matches` checks the
    signature against the row the id names.
    """
    configured = bounce_address().lower()
    if not configured:
        return None
    local, _at, domain = configured.rpartition("@")
    candidate_local, _at, candidate_domain = address.lower().rpartition("@")
    prefix = f"{local}+"
    if candidate_domain != domain or not candidate_local.startswith(prefix):
        return None
    tag = _SIGNED_TAG.fullmatch(candidate_local.removeprefix(prefix))
    if tag is None:
        return None
    return BounceTag(log_id=int(tag["id"]), signature=tag["signature"])


def bounce_tag_matches(tag: BounceTag, message_id: str) -> bool:
    """Whether ``tag`` is signed for its id and ``message_id``, the row's ``Message-ID``.

    The signature is compared in constant time against the one made under
    ``SECRET_KEY`` and under each of ``SECRET_KEY_FALLBACKS``, so mail sent before the
    key was rotated still reads while the old key is a fallback.
    """
    keys = [settings.SECRET_KEY, *settings.SECRET_KEY_FALLBACKS]
    matched = [
        hmac.compare_digest(tag.signature, _bounce_signature(tag.log_id, message_id, key))
        for key in keys
    ]
    return any(matched)


def _bounce_signature(log_id: int, message_id: str, key: str) -> str:
    """The signature :func:`signed_bounce_address` gives the row under ``key``."""
    signature = salted_hmac(
        BOUNCE_SIGNATURE_SALT, f"{log_id}:{message_id}", secret=key, algorithm="sha256"
    )
    return signature.hexdigest()[:BOUNCE_SIGNATURE_LENGTH]


def _reserve_log_id() -> int:
    """Take the next email log id from the table's sequence, for the row a send writes.

    The row is written after the hand-over, as the transport answers, but the envelope
    sender must name it before; taking the id from the sequence first lets it.  A
    sequence never gives the same value twice, rolled back or not, so an id taken by a
    send that never wrote its row is never another row's.
    """
    # Inline, as in ``_record``: apps.mail sits above every project module.
    from apps.mail.models import EmailLog

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT nextval(pg_get_serial_sequence(%s, 'id'))", [EmailLog._meta.db_table]
        )
        row = cursor.fetchone()
    if row is None:
        raise DatabaseError("nextval answered no row")
    return int(row[0])


def _message_id_domain() -> str:
    """The domain of ``DEFAULT_FROM_EMAIL``'s address, or the host's name without one."""
    _name, address = parseaddr(settings.DEFAULT_FROM_EMAIL)
    domain = address.rpartition("@")[2]
    return domain or str(DNS_NAME)


def _record(
    *,
    to: str,
    subject: str,
    purpose: str,
    user_id: int | None,
    attachments: str,
    error: str,
    to_name: str = "",
    message_id: str = "",
    log_id: int | None = None,
) -> None:
    """Write one email log row.  A blank ``error`` records a send that went out.

    ``message_id`` is the ``Message-ID`` header the message carried, and ``log_id`` the
    id :func:`_reserve_log_id` took for the row, or ``None`` to let the table choose.

    A blank ``to_name`` with a ``user_id`` is filled in from that account's current
    ``display_name`` before the row is written, so the log keeps the name the
    recipient had at send time even after the account is later renamed.  A ``user_id``
    whose account no longer exists is recorded as no account at all.  Whatever
    name results is cut to fit ``EmailLog.to_name``: a first and last name can
    together run past that limit, and the row must still be written rather than
    raise past a mail server that already took the message.
    """
    # Inline: apps.mail sits above every project module, so importing it here is
    # what keeps reading caldart.mail from pulling an app in.
    from apps.mail.models import EmailLog, EmailStatus

    name = to_name
    if user_id is not None:
        account = get_user_model().objects.filter(pk=user_id).first()
        if account is None:
            # The account was deleted before the message went, as a deleted member's
            # "automatic renewal is off" email is: keep the row, naming no account.
            user_id = None
        elif not name:
            name = account.display_name

    max_length = EmailLog._meta.get_field("to_name").max_length
    if max_length is not None:
        name = name[:max_length]

    EmailLog.objects.create(
        id=log_id,
        to_email=to,
        to_name=name,
        user_id=user_id,
        purpose=purpose,
        subject=subject,
        sent_at=timezone.now(),
        status=EmailStatus.FAILED if error else EmailStatus.SENT,
        error=error,
        attachments=attachments,
        message_id=message_id,
    )
