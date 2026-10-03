"""A test copy of a bulk email, sent to its sender alone before the real send.

:func:`send_test` mails the email as it is saved to the person who asks, filled in
with their own field values and built exactly as the background sender builds a copy
(``apps.bulk_email.render.render_for``): the same layout, the same two parts, the same
footer and headers, and the same ``Reply-To``.  Only the subject differs, starting
:data:`SUBJECT_PREFIX`.  A test is not part of the send: it adds nobody to the batch,
counts toward nothing, and is in the email log under its own purpose,
:data:`PURPOSE`, so Sent Emails shows it.  Every call sends one more copy.
"""

from __future__ import annotations

from apps.accounts.models import User
from apps.bulk_email.checks import refuse_on_errors
from apps.bulk_email.models import BulkEmail
from apps.bulk_email.render import COPY_TEMPLATE, fill_values, render_for
from apps.bulk_email.reply_to import reply_to_for
from caldart.mail import send_templated

#: What a test copy's subject starts with.
SUBJECT_PREFIX = "[Test] "

#: The email log's purpose for a test copy.
PURPOSE = "bulk_email_test"


def send_test(bulk: BulkEmail, *, actor: User) -> str:
    """Mail ``actor`` a test copy of ``bulk`` as it is saved; return the address used.

    The copy is ``actor``'s own: their field values, their footer and unsubscribe
    link, and the email's ``Reply-To``, under a subject that starts
    :data:`SUBJECT_PREFIX`.  It goes to ``actor.email`` and is logged under
    :data:`PURPOSE` for that account.  An email the checks find errors in raises
    ``apps.bulk_email.checks.ChecksFailedError`` and sends nothing, and a mail server
    that refuses the copy raises ``caldart.mail.MailRefusedError`` (the failed send is
    in the email log).
    """
    refuse_on_errors(bulk)
    copy = render_for(bulk, actor, fill_values(bulk, actor))
    send_templated(
        to=actor.email,
        subject=f"{SUBJECT_PREFIX}{copy.subject}",
        template=COPY_TEMPLATE,
        context={"text": copy.text, "html": copy.html},
        purpose=PURPOSE,
        user_id=actor.pk,
        headers=copy.headers,
        reply_to=reply_to_for(bulk),
    )
    return actor.email
