"""Reusing a message: saved templates, and duplicating an email as a fresh draft.

A template (``apps.bulk_email.models.EmailTemplate``) is a message saved under a name
and shared by everybody in CalDART management: a subject, a message, and optionally a
type and a Reply-To address.  **Start from a template** fills a draft with it
(:func:`apply_template`); the draft is a copy, so changing it leaves the template as
it was.

**Duplicate** (:func:`duplicate`) makes a fresh draft from any email the caller can
open, sent or not, with the same subject, message, type, and Reply-To, and, when
asked, the same people as a fresh batch whose skip reasons are worked out as they are
now; a DART leader's copy goes to their own DART alone.  The original is not touched.
"""

from __future__ import annotations

from django.db import transaction

from apps.accounts.models import User
from apps.bulk_email.batch import add_accounts, batch_queryset
from apps.bulk_email.drafts import update
from apps.bulk_email.models import BulkEmail, EmailTemplate
from apps.bulk_email.reply_to import default_reply_to
from apps.bulk_email.richtext import sanitize
from apps.bulk_email.senders import sender_context
from apps.mail.models import EmailType
from apps.mail.types import sendable_types
from apps.members.filters import member_admin_queryset
from caldart.exceptions import DomainPermissionError

#: How the add of a duplicate's copied people is named; ``{subject}`` is the original's.
COPIED_LABEL = 'Copied from "{subject}"'

#: What :data:`COPIED_LABEL` says for an original with no subject.
NO_SUBJECT = "(no subject)"


def apply_template(bulk: BulkEmail, template: EmailTemplate, *, actor: User) -> BulkEmail:
    """Fill the draft ``bulk`` with ``template``'s message; return the email as saved.

    The subject and the message are replaced by the template's, the message sanitized
    again, and the Reply-To by the template's, or by the sender's default
    (``apps.bulk_email.reply_to.default_reply_to``) when the template leaves it blank.
    The template's type replaces the email's when it has one that ``actor`` may
    send; otherwise the email keeps its own.  The batch is not touched.  The change goes
    through the edit rule (``apps.bulk_email.drafts.update``), so a queued email whose
    type the template changes goes back to a draft; it raises
    ``DomainError`` once the email has started sending, and ``DomainValidationError``
    keyed ``subject`` or ``body`` when the template would leave a queued email without
    one.
    """
    changes: dict[str, object] = {
        "subject": template.subject,
        "body": sanitize(template.body),
        "reply_to": template.reply_to or default_reply_to(bulk.sender),
    }
    email_type = _sendable(template.email_type, actor)
    if email_type is not None:
        changes["email_type"] = email_type
    return update(bulk, changes, actor=actor)


def duplicate(bulk: BulkEmail, *, actor: User, copy_recipients: bool) -> BulkEmail:
    """A fresh draft owned by ``actor`` with ``bulk``'s subject, message, and Reply-To.

    The type is copied when ``actor`` may send it, and left unchosen otherwise.  The
    draft records the DART ``actor`` may send to (``apps.bulk_email.senders``): none for
    CalDART management, a DART leader's own.  With ``copy_recipients`` every account in
    ``bulk``'s batch whose account still exists joins the draft's batch as one add named
    :data:`COPIED_LABEL`; each is a fresh ``batched`` row with the account's name,
    address, kind, and DART as they are now, so whether each receives a copy is worked
    out afresh, and a DART leader's copy skips everybody outside their DART as
    ``Not in your DART``.  Without it the batch is empty.  ``bulk`` itself is not
    changed.  Raises ``DomainPermissionError`` with the sender's reason when ``actor``
    may send to nobody, such as a DART leader whose profile names no DART.
    """
    context = sender_context(actor)
    if not context.can_send:
        raise DomainPermissionError(context.reason)
    with transaction.atomic():
        copy = BulkEmail.objects.create(
            sender=actor,
            dart=context.dart,
            subject=bulk.subject,
            body=bulk.body,
            reply_to=bulk.reply_to,
            email_type=_sendable(bulk.email_type, actor),
        )
        if copy_recipients:
            people = member_admin_queryset().filter(
                pk__in=batch_queryset(bulk).filter(user__isnull=False).values("user_id")
            )
            add_accounts(
                copy,
                people.order_by("last_name", "first_name", "email", "pk"),
                actor=actor,
                label=COPIED_LABEL.format(subject=bulk.subject or NO_SUBJECT),
            )
    return copy


def _sendable(email_type: EmailType | None, actor: User) -> EmailType | None:
    """``email_type`` when ``actor`` may send it; else ``None``."""
    if email_type is None or email_type not in sendable_types(actor):
        return None
    return email_type
