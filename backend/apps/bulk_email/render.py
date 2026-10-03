"""One recipient's copy of a bulk email: its subject, its two bodies, and its headers.

:func:`render_copy` is the one place a copy is built, for the background sender and for
anything that shows a copy as it went.  The bodies come from
``emails/bulk_email.{txt,html}``: the plain-text body is the message followed by the
house footer, and the HTML one makes each paragraph of the message a ``<p>``.  The
sender hands the finished bodies to ``caldart.mail.send_templated`` through the
pass-through pair ``emails/bulk_email_copy.{txt,html}`` (:data:`COPY_TEMPLATE`), so the
email log records the copy like any other message.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.template.loader import render_to_string

from apps.bulk_email.models import BulkEmail, BulkEmailRecipient
from caldart.mail import contact_email, org_name

#: The template pair a copy is built from.
TEMPLATE = "bulk_email"

#: The pass-through template pair a built copy is sent through: each renders the
#: ``text`` or ``html`` it is given, unchanged.
COPY_TEMPLATE = "bulk_email_copy"

#: The email log's purpose for every copy.
PURPOSE = "bulk_email"


@dataclass(frozen=True)
class RenderedCopy:
    """One recipient's copy of a bulk email.

    ``subject`` is the subject line, ``text`` and ``html`` the two bodies, and
    ``headers`` any extra headers the copy carries.
    """

    subject: str
    text: str
    html: str
    headers: dict[str, str] = field(default_factory=dict)


def render_copy(bulk: BulkEmail, recipient: BulkEmailRecipient) -> RenderedCopy:
    """``recipient``'s copy of ``bulk``, as the background sender sends it.

    The subject is the email's, as typed.  Both bodies render the message and the
    organization's name and contact address as they are now.  Every copy of one
    email reads the same, and carries no extra header.
    """
    context: dict[str, object] = {
        "org_name": org_name(),
        "contact_email": contact_email(),
        "subject": bulk.subject,
        "body": bulk.body,
    }
    return RenderedCopy(
        subject=bulk.subject,
        text=render_to_string(f"emails/{TEMPLATE}.txt", context),
        html=render_to_string(f"emails/{TEMPLATE}.html", context),
    )
