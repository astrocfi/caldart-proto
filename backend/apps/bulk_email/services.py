"""Bulk email: the list a filter selects, and one email to each person on it.

The recipients are chosen by the member list's own filters
(``apps.members.filters.MemberAdminFilterSet``), so a filter that works on the
member list chooses the same people here, friends included through ``kind``.
:func:`build_recipients` walks those accounts in surname order and sets aside
anybody who cannot be sent a copy, with the reason: a deactivated account, a blank
address, an invalid one, and an address already on the list in another case.  A
preview is that list and nothing else.

:func:`send_bulk_email` rebuilds the list at the moment it sends, sends each
person their own copy through ``caldart.mail.send_templated`` under the purpose
``bulk_email``, and records every person's result on a :class:`BulkEmail`.  A mail
server that refuses one copy fails that copy alone.
"""

from __future__ import annotations

import logging
import smtplib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.db.models import QuerySet
from django.utils import timezone

from apps.accounts.models import User
from apps.bulk_email.models import BulkEmail, BulkEmailRecipient, RecipientStatus
from apps.members.filters import EXPORT_FILTER_PARAMS, MemberAdminFilterSet, member_admin_queryset
from caldart import audit
from caldart.exceptions import DomainValidationError
from caldart.mail import contact_email, org_name, send_templated
from caldart.reports import (
    CSV_DOCUMENT_TYPE,
    ReportDocument,
    apply_filterset,
    csv_rows,
    given_params,
)

log = logging.getLogger(__name__)

#: The member list's filters a bulk email may be aimed with, in the order the list
#: names them.  The list's own **Include deactivated** switch is not one: a
#: deactivated account is always listed among the skips.
FILTER_KEYS: tuple[str, ...] = EXPORT_FILTER_PARAMS

#: The email template pair, ``emails/bulk_email.{txt,html}``, and the email log's
#: purpose for every copy.
TEMPLATE = "bulk_email"
PURPOSE = "bulk_email"

#: Why a person the filters selected is sent no copy.
SKIP_DEACTIVATED = "Account deactivated"
SKIP_NO_ADDRESS = "No email address"
SKIP_INVALID = "Invalid email address"
SKIP_DUPLICATE = "Duplicate address"

#: Why a copy the mail server would not take failed.
FAILED_REASON = "Refused by the mail server"

#: What a mail server that refuses a copy raises.
SEND_ERRORS: tuple[type[Exception], ...] = (smtplib.SMTPException, OSError)

#: What the refusal of a send with nobody to receive it says.
NOBODY_MESSAGE = "Nobody matches these filters."

#: The columns of both recipient CSVs.
CSV_HEADER: tuple[str, ...] = ("Name", "Email", "Result", "Reason")

#: The result a preview's CSV gives a person who will be sent a copy.
TO_SEND_LABEL = "To send"


@dataclass(frozen=True)
class Recipient:
    """One person the filters selected.

    ``user_id`` is the account's id, ``name`` its display name, and ``email`` its
    address as stored.  ``reason`` says why the person is skipped, and is blank for
    one who will be sent a copy.
    """

    user_id: int
    name: str
    email: str
    reason: str = ""


@dataclass(frozen=True)
class RecipientList:
    """Everybody the filters selected: who is sent a copy, and who is skipped."""

    recipients: list[Recipient]
    skipped: list[Recipient]


def unknown_filters(filters: Mapping[str, str]) -> list[str]:
    """The keys of ``filters`` that are not filters of the member list, in order."""
    return [key for key in filters if key not in FILTER_KEYS]


def given_filters(filters: Mapping[str, str]) -> dict[str, str]:
    """The filters of ``filters`` that carry a value, in :data:`FILTER_KEYS` order.

    A blank value narrows nothing, and a key that is not a member list filter is
    dropped.
    """
    return given_params(filters, FILTER_KEYS)


def selected_accounts(filters: Mapping[str, str]) -> QuerySet[User]:
    """Every member and friend ``filters`` select, deactivated ones included.

    The filters narrow the member list's queryset exactly as on the member list,
    with **Include deactivated** on.  A donor is never there.  The accounts come in
    surname order, then first name, then address.  A filter value the member list
    refuses raises DRF's ``ValidationError`` keyed by that filter.
    """
    params = {**given_filters(filters), "include_inactive": "true"}
    accounts = apply_filterset(MemberAdminFilterSet, params, member_admin_queryset())
    return accounts.order_by("last_name", "first_name", "email", "pk")


def build_recipients(filters: Mapping[str, str]) -> RecipientList:
    """Who a bulk email aimed with ``filters`` reaches, and who it skips and why.

    Each account the filters select is one entry, in surname order.  It is skipped
    with :data:`SKIP_DEACTIVATED` when the account is deactivated,
    :data:`SKIP_NO_ADDRESS` when its address is blank, :data:`SKIP_INVALID` when
    the address is not one a mail server could take, and :data:`SKIP_DUPLICATE`
    when an earlier entry is already sent to the same address in any case.
    Everybody else is a recipient.  Nothing is sent or stored.
    """
    recipients: list[Recipient] = []
    skipped: list[Recipient] = []
    seen: set[str] = set()
    for account in selected_accounts(filters):
        reason = _skip_reason(account, seen)
        entry = Recipient(
            user_id=account.pk, name=account.display_name, email=account.email, reason=reason
        )
        if reason == "":
            seen.add(account.email.strip().casefold())
            recipients.append(entry)
        else:
            skipped.append(entry)
    return RecipientList(recipients=recipients, skipped=skipped)


def _skip_reason(account: User, seen: set[str]) -> str:
    """Why ``account`` is sent no copy, or ``""`` when it is sent one.

    ``seen`` holds the case-folded addresses already on the list.
    """
    if not account.is_active:
        return SKIP_DEACTIVATED
    address = account.email.strip()
    if address == "":
        return SKIP_NO_ADDRESS
    try:
        validate_email(address)
    except DjangoValidationError:
        return SKIP_INVALID
    if address.casefold() in seen:
        return SKIP_DUPLICATE
    return ""


def send_bulk_email(
    *, subject: str, body: str, filters: Mapping[str, str], sender: User
) -> BulkEmail:
    """Send ``subject`` and ``body`` to everybody ``filters`` select; return the record.

    The list is rebuilt now (:func:`build_recipients`), so it is whoever the filters
    select at the moment of sending.  Each recipient is sent a copy of their own,
    from ``emails/bulk_email.{txt,html}``, logged in the email log under the purpose
    ``bulk_email``.  A copy the mail server refuses is recorded as failed with
    :data:`FAILED_REASON`, and the rest still go.  The returned :class:`BulkEmail`
    stores the message, the given filters, ``sender``, a :class:`BulkEmailRecipient`
    for every recipient (sent or failed) and then for every skip, the three counts,
    and ``sent_at``.  One ``bulk_email.send`` audit line names ``sender``, the send,
    and the counts.

    Raises ``DomainValidationError`` on ``filters`` when the filters select nobody
    who can be sent a copy; nothing is stored then.
    """
    chosen = build_recipients(filters)
    if len(chosen.recipients) == 0:
        raise DomainValidationError("filters", NOBODY_MESSAGE)
    bulk = BulkEmail.objects.create(
        subject=subject, body=body, filters=given_filters(filters), sender=sender
    )
    context: dict[str, object] = {
        "org_name": org_name(),
        "contact_email": contact_email(),
        "subject": subject,
        "body": body,
    }
    for recipient in chosen.recipients:
        status, reason = _send_one(recipient, subject=subject, context=context, bulk=bulk)
        BulkEmailRecipient.objects.create(
            bulk_email=bulk,
            user_id=recipient.user_id,
            name=recipient.name,
            email=recipient.email,
            status=status,
            reason=reason,
        )
        if status == RecipientStatus.SENT:
            bulk.sent_count += 1
        else:
            bulk.failed_count += 1
    BulkEmailRecipient.objects.bulk_create(
        BulkEmailRecipient(
            bulk_email=bulk,
            user_id=skip.user_id,
            name=skip.name,
            email=skip.email,
            status=RecipientStatus.SKIPPED,
            reason=skip.reason,
        )
        for skip in chosen.skipped
    )
    bulk.skipped_count = len(chosen.skipped)
    bulk.sent_at = timezone.now()
    bulk.save(
        update_fields=["sent_count", "failed_count", "skipped_count", "sent_at", "updated_at"]
    )
    audit.record(
        audit.BULK_EMAIL_SEND,
        actor=sender,
        target=bulk,
        sent=bulk.sent_count,
        skipped=bulk.skipped_count,
        failed=bulk.failed_count,
    )
    return bulk


def _send_one(
    recipient: Recipient, *, subject: str, context: dict[str, object], bulk: BulkEmail
) -> tuple[RecipientStatus, str]:
    """Send ``recipient`` their copy, and say whether it went and, if not, why."""
    try:
        send_templated(
            to=recipient.email,
            subject=subject,
            template=TEMPLATE,
            context=context,
            purpose=PURPOSE,
            user_id=recipient.user_id,
            to_name=recipient.name,
        )
    except SEND_ERRORS as exc:
        log.error(
            "bulk email copy refused: bulk_email=%s user=%s error=%s",
            bulk.pk,
            recipient.user_id,
            type(exc).__name__,
        )
        return RecipientStatus.FAILED, FAILED_REASON
    return RecipientStatus.SENT, ""


def preview_document(chosen: RecipientList, *, today_iso: str) -> ReportDocument:
    """The preview's list as a CSV: who will be sent a copy, then who is skipped.

    Each row is the name, the address, ``To send`` or ``Skipped``, and the reason
    for a skip.  The file is named ``caldart-bulk-email-preview-<today_iso>.csv``.
    """
    rows = [
        *((r.name, r.email, TO_SEND_LABEL, "") for r in chosen.recipients),
        *((r.name, r.email, RecipientStatus.SKIPPED.label, r.reason) for r in chosen.skipped),
    ]
    return _csv_document(rows, f"caldart-bulk-email-preview-{today_iso}.csv")


def results_document(bulk: BulkEmail) -> ReportDocument:
    """A sent bulk email's results as a CSV, one row per person in the order stored.

    Each row is the name, the address, ``Sent``, ``Failed`` or ``Skipped``, and the
    reason.  The file is named ``caldart-bulk-email-<id>-recipients.csv``.
    """
    rows = [
        (row.name, row.email, RecipientStatus(row.status).label, row.reason)
        for row in bulk.recipients.all()
    ]
    return _csv_document(rows, f"caldart-bulk-email-{bulk.pk}-recipients.csv")


def _csv_document(rows: Iterable[tuple[str, str, str, str]], filename: str) -> ReportDocument:
    """``rows`` under :data:`CSV_HEADER` as a CSV document named ``filename``."""
    content = "".join(csv_rows(CSV_HEADER, rows)).encode()
    return ReportDocument(filename=filename, media_type=CSV_DOCUMENT_TYPE, content=content)
