"""One way to send a templated email.

Every email CalDART sends -- a reminder, a receipt, a refund, a renewal notice
-- is a pair of templates under ``backend/templates/emails/``: the ``.txt`` body
is the message proper, and the ``.html`` one an alternative, so a client that
renders no markup still reads the whole thing.  :func:`send_templated` renders
both and sends them, and :func:`org_name` and :func:`contact_email` answer the
two pieces of the letterhead almost every template asks for.
"""

from __future__ import annotations

from collections.abc import Sequence

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

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
) -> EmailMultiAlternatives:
    """Render ``emails/<template>.{txt,html}`` and send them to one address.

    ``subject`` is sent as given: the house prefix and the organization's name
    belong to the caller, which knows what the email is about.  ``context``
    renders both bodies.  Each entry of ``attachments`` is attached by filename,
    bytes and media type, which is how a receipt PDF rides along.  The message
    comes from ``DEFAULT_FROM_EMAIL``.

    The sent message is returned, so a caller can record what went out.  A mail
    server that refuses the message raises, as Django's ``send`` does; a caller
    that must survive a refusal catches it and says so in its own log.
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
    message.send()
    return message
