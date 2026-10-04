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
message carries a ``Message-ID`` stored on that row, and goes out with
``BOUNCE_ADDRESS`` as its envelope sender when that is set, which is how the
bounce check (``apps.mail.bounces``) matches a returned report to its row.  A
``List-Unsubscribe`` header a caller passes is written as itself, never as encoded
words, so mail programs can read its links.

A send raises :class:`MailRefusedError` when the mail server refuses the message or
cannot be reached.  A caller that must answer whatever the server does -- a request
whose answer must not depend on the mail, or a change already committed -- sends
through :func:`send_logging_refusal` or :func:`send_on_commit`, which log the refusal
on this module's logger instead of raising it.  Production routes that logger to the
error mail ``ADMIN_EMAILS`` receives.
"""

from __future__ import annotations

import email.policy
import logging
import smtplib
from collections.abc import Callable, Mapping, Sequence
from email.headerregistry import BaseHeader, HeaderRegistry, UnstructuredHeader
from email.policy import EmailPolicy, Policy
from email.utils import make_msgid, parseaddr

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.utils import DNS_NAME
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

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
    ``BOUNCE_ADDRESS`` is set, when that address is the envelope sender instead and a
    receiving server returns an undeliverable message there.  The message carries a
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
    envelope_sender = settings.BOUNCE_ADDRESS or settings.DEFAULT_FROM_EMAIL
    if settings.BOUNCE_ADDRESS:
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


def new_message_id() -> str:
    """A fresh ``Message-ID``, in angle brackets, on ``DEFAULT_FROM_EMAIL``'s domain.

    It is what :func:`send_templated` gives a message when the caller names none.
    """
    return make_msgid(domain=_message_id_domain())


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
) -> None:
    """Write one email log row.  A blank ``error`` records a send that went out.

    ``message_id`` is the ``Message-ID`` header the message carried.

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
