"""One way to send a templated email.

Every email CalDART sends -- a reminder, a receipt, a refund, a renewal notice
-- is a pair of templates under ``backend/templates/emails/``: the ``.txt`` body
is the message proper, and the ``.html`` one an alternative, so a client that
renders no markup still reads the whole thing.  :func:`send_templated` renders
both and sends them, and :func:`org_name` and :func:`contact_email` answer the
two pieces of the letterhead almost every template asks for.

Because every email goes through :func:`send_templated`, it is also the one
place that records what went out: each send writes an ``apps.mail.EmailLog``
row, successful or refused, which is what the email log screen reads.
"""

from __future__ import annotations

from collections.abc import Sequence

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from caldart.org import org_details

#: One attachment: its filename, its bytes, and its media type.
type Attachment = tuple[str, bytes, str]


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
) -> EmailMultiAlternatives:
    """Render ``emails/<template>.{txt,html}`` and send them to one address.

    ``subject`` is sent as given: the house prefix and the organization's name
    belong to the caller, which knows what the email is about.  ``context``
    renders both bodies.  Each entry of ``attachments`` is attached by filename,
    bytes and media type, which is how a receipt PDF rides along.  The message
    comes from ``DEFAULT_FROM_EMAIL``.

    Every send is recorded in the email log: ``purpose`` names what the message
    was for and defaults to ``template``, which is the right answer wherever one
    template is one kind of message; ``user_id`` is the primary key of the account
    the email concerned, and is left null for an address with no account behind it.
    ``to_name`` is the recipient's name at send time, such as a DART contact's
    name; a caller that leaves it blank while naming ``user_id`` has the account's
    own ``display_name`` recorded instead, so an account-linked row always carries
    the name it had when the email went.

    The sent message is returned, so a caller can record what went out.  A mail
    server that refuses the message is logged as a failed send, carrying the
    exception class, and the exception then raises as Django's ``send`` does; a
    caller that must survive a refusal catches it and says so in its own log.
    """
    rendered = context or {}
    message = EmailMultiAlternatives(
        subject=subject,
        body=render_to_string(f"emails/{template}.txt", rendered),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to],
    )
    message.attach_alternative(render_to_string(f"emails/{template}.html", rendered), "text/html")
    for filename, content, mimetype in attachments:
        message.attach(filename, content, mimetype)
    filenames = ", ".join(filename for filename, _content, _mimetype in attachments)
    try:
        message.send()
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
        )
        raise
    _record(
        to=to,
        subject=subject,
        purpose=purpose or template,
        user_id=user_id,
        attachments=filenames,
        error="",
        to_name=to_name,
    )
    return message


def _record(
    *,
    to: str,
    subject: str,
    purpose: str,
    user_id: int | None,
    attachments: str,
    error: str,
    to_name: str = "",
) -> None:
    """Write one email log row.  A blank ``error`` records a send that went out.

    A blank ``to_name`` with a ``user_id`` is filled in from that account's current
    ``display_name`` before the row is written, so the log keeps the name the
    recipient had at send time even after the account is later renamed.  Whatever
    name results is cut to fit ``EmailLog.to_name``: a first and last name can
    together run past that limit, and the row must still be written rather than
    raise past a mail server that already took the message.
    """
    # Inline: apps.mail sits above every project module, so importing it here is
    # what keeps reading caldart.mail from pulling an app in.
    from apps.mail.models import EmailLog, EmailStatus

    name = to_name
    if not name and user_id is not None:
        account = get_user_model().objects.filter(pk=user_id).first()
        if account is not None:
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
    )
