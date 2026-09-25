"""CalDART's own receipt for a payment, and a member's annual statement.

Whoever took the money -- Stripe, PayPal or a treasurer writing down a check --
the member gets one receipt, and it is this one: the organization's letterhead,
the receipt number, what the payment bought, and the 501(c)(3) sentence under a
contribution.  A calendar year of contributions is gathered the same way into a
statement a donor files with their tax return.

This module gathers the facts from the payment rows and hands them to the pure
builders in :mod:`caldart.receipts`, which render the PDFs.  Sending is
deliberately forgiving: a mail server that refuses a receipt is logged and
leaves ``receipt_sent_at`` null, so the treasurer's "resend" is the retry.
"""

from __future__ import annotations

import logging
from datetime import date
from io import BytesIO

from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify

from apps.accounts.models import User
from apps.members.models import Membership
from apps.payments.models import Payment, PaymentProvider, PaymentStatus, RefundStatus
from caldart.mail import send_templated
from caldart.org import org_details
from caldart.receipts import (
    ReceiptData,
    ReceiptLine,
    StatementData,
    StatementLine,
    build_receipt_pdf,
    build_statement_pdf,
)
from caldart.reports import PDF_MEDIA_TYPE, money_label

log = logging.getLogger(__name__)

#: The subject of the receipt email, in the house voice.
RECEIPT_SUBJECT = "{org}: your receipt for {amount}"

#: What the contribution line is called.
CONTRIBUTION_LABEL = "Contribution"

#: The statuses whose money counts towards a receipt or a statement: a payment
#: refunded in part still bought something, and its receipt still stands.
SETTLED_STATUSES = (
    PaymentStatus.SUCCEEDED,
    PaymentStatus.PARTIALLY_REFUNDED,
    PaymentStatus.REFUNDED,
)


def payments_url() -> str:
    """Absolute link to the portal's payments screen, which every receipt carries."""
    return f"{settings.SITE_URL.rstrip('/')}/portal/payments"


def provider_label(payment: Payment) -> str:
    """How the money arrived, as the receipt prints it.

    The provider's display name, and for a payment recorded by hand the wallet
    as well -- "Recorded by hand (Check)" -- because that is the part the payer
    recognizes.
    """
    label = str(PaymentProvider(payment.provider).label)
    if payment.provider == PaymentProvider.MANUAL:
        return f"{label} ({payment.get_wallet_display()})"
    return label


def receipt_lines(payment: Payment) -> list[ReceiptLine]:
    """One line per thing ``payment`` bought, dues first.

    The membership line names the plan and, when the payment activated a term,
    that term's dates.  The contribution line is marked deductible, which is
    what brings the 501(c)(3) sentence onto the page.  A payment with neither a
    plan nor a contribution -- which checkout refuses to create -- yields no
    lines, and its receipt totals zero.
    """
    lines: list[ReceiptLine] = []
    if payment.plan is not None:
        lines.append(
            ReceiptLine(
                label=payment.plan.name,
                detail=term_detail(payment),
                amount_cents=payment.plan_amount_cents,
            )
        )
    if payment.contribution_cents > 0:
        lines.append(
            ReceiptLine(
                label=CONTRIBUTION_LABEL,
                amount_cents=payment.contribution_cents,
                deductible=True,
            )
        )
    return lines


def term_detail(payment: Payment) -> str:
    """The membership term this payment bought, as ``2026-03-01 to 2027-02-28``.

    A lifetime term reads ``from <start>``, and a payment with no term behind it
    -- one still settling, or one whose term was canceled -- gives ``""``.
    """
    term = Membership.objects.filter(payment=payment).first()
    if term is None:
        return ""
    if term.ends_on is None:
        return f"from {term.starts_on.isoformat()}"
    return f"{term.starts_on.isoformat()} to {term.ends_on.isoformat()}"


def receipt_data(payment: Payment) -> ReceiptData:
    """Everything the receipt for ``payment`` prints.

    The issue date is the payment's ledger date -- the day a check was received,
    or the day the provider settled -- and falls back to today for a payment
    that has not completed.
    """
    return ReceiptData(
        org=org_details(),
        receipt_number=payment.receipt_number,
        issued_on=payment.paid_on or timezone.localdate(),
        payer_name=payment.user.display_name,
        payer_email=payment.user.email,
        lines=receipt_lines(payment),
        provider_label=provider_label(payment),
        provider_ref=payment.provider_ref,
    )


def render_receipt_pdf(payment: Payment) -> bytes:
    """The receipt for ``payment`` as PDF bytes."""
    buffer = BytesIO()
    build_receipt_pdf(buffer, receipt_data(payment))
    return buffer.getvalue()


def receipt_filename(payment: Payment) -> str:
    """The name the receipt downloads under: ``caldart-receipt-CALDART-000123.pdf``."""
    return f"caldart-receipt-{payment.receipt_number}.pdf"


def send_receipt(payment: Payment) -> bool:
    """Email CalDART's receipt for ``payment``, with the PDF attached.

    Stamps ``receipt_sent_at`` and returns ``True`` once the message has gone.
    A payment whose payer has no address on file, and one the mail server
    refuses, are logged and answer ``False`` with ``receipt_sent_at`` left as it
    was, so resending is the retry.  Nothing here raises: a receipt that cannot
    be sent must never undo the payment that earned it.  Either way the attempt
    is recorded in the email log under the purpose ``receipt``.
    """
    if not payment.user.email:
        log.warning("No address on file for the payer of payment %s; no receipt sent", payment.pk)
        return False

    org = org_details()
    context: dict[str, object] = {
        "org_name": org.name,
        "contact_email": org.contact_email,
        "first_name": payment.user.first_name or payment.user.display_name,
        "receipt_number": payment.receipt_number,
        "issued_on": payment.paid_on or timezone.localdate(),
        "amount": money_label(payment.amount_cents),
        "plan_name": payment.plan.name if payment.plan is not None else "",
        "plan_amount": money_label(payment.plan_amount_cents),
        "contribution_amount": money_label(payment.contribution_cents),
        "contribution_cents": payment.contribution_cents,
        "term_detail": term_detail(payment),
        "provider_label": provider_label(payment),
        "payments_url": payments_url(),
        "site_url": settings.SITE_URL.rstrip("/"),
    }
    try:
        send_templated(
            to=payment.user.email,
            subject=RECEIPT_SUBJECT.format(org=org.name, amount=money_label(payment.amount_cents)),
            template="receipt",
            context=context,
            attachments=[(receipt_filename(payment), render_receipt_pdf(payment), PDF_MEDIA_TYPE)],
            user_id=payment.user_id,
        )
    except OSError as exc:
        log.error("Receipt for payment %s could not be sent: %s", payment.pk, exc)
        return False

    payment.receipt_sent_at = timezone.now()
    payment.save(update_fields=["receipt_sent_at", "updated_at"])
    return True


def contribution_payments(user: User, year: int) -> list[Payment]:
    """``user``'s settled contributions in ``year``, oldest first.

    A payment counts when it carried a contribution and its money settled, and
    it falls in the year its ledger date falls in -- the day a check was
    received, or the day the provider settled.
    """
    rows = (
        Payment.objects.filter(
            user=user,
            status__in=SETTLED_STATUSES,
            contribution_cents__gt=0,
        )
        .prefetch_related("refunds")
        .order_by("created_at", "id")
    )
    dated = [(payment.paid_on, payment) for payment in rows]
    return [payment for paid_on, payment in dated if paid_on is not None and paid_on.year == year]


def statement_years(user: User) -> list[int]:
    """The calendar years ``user`` may download a contribution statement for.

    Newest first, and a year appears only when the member made at least one
    settled contribution in it.  An empty list means there is nothing to state.
    """
    rows = Payment.objects.filter(
        user=user, status__in=SETTLED_STATUSES, contribution_cents__gt=0
    ).only("provider", "received_on", "completed_at")
    years = {payment.paid_on.year for payment in rows if payment.paid_on is not None}
    return sorted(years, reverse=True)


def refunded_contribution_cents(payment: Payment) -> int:
    """How much of ``payment``'s contribution came back, in cents.

    A refund is applied to the contribution first: a member asking for part of
    a payment back is asking for the gift back, not for the membership they are
    still using.  The result never exceeds the contribution itself, so a refund
    that reaches into the dues as well stops there.
    """
    refunded = sum(
        refund.amount_cents
        for refund in payment.refunds.all()
        if refund.status == RefundStatus.SUCCEEDED
    )
    return min(payment.contribution_cents, refunded)


def statement_data(user: User, year: int) -> StatementData:
    """``user``'s contributions in ``year``, gathered for the statement PDF.

    One line per settled contribution, in the order they were paid, each netted
    against whatever of it was refunded.  A year the member gave nothing in
    yields a statement whose total is zero rather than no statement at all;
    :func:`statement_years` is what says which years are worth offering.
    """
    lines = [
        StatementLine(
            paid_on=payment.paid_on or date(year, 1, 1),
            receipt_number=payment.receipt_number,
            amount_cents=payment.contribution_cents,
            refunded_cents=refunded_contribution_cents(payment),
        )
        for payment in contribution_payments(user, year)
    ]
    return StatementData(
        org=org_details(),
        year=year,
        member_name=user.display_name,
        member_email=user.email,
        contributions=lines,
    )


def render_statement_pdf(user: User, year: int) -> bytes:
    """``user``'s contribution statement for ``year`` as PDF bytes."""
    buffer = BytesIO()
    build_statement_pdf(buffer, statement_data(user, year))
    return buffer.getvalue()


def statement_filename(member: User, year: int) -> str:
    """The statement's download name, e.g. ``caldart-contributions-2026-marta-reyes.pdf``.

    The member's display name is slugified, so a treasurer who downloads a dozen
    statements for one year can tell them apart in a folder.  A name that slugifies
    to nothing (an email address made only of symbols, say) falls back to the
    account id.
    """
    who = slugify(member.display_name) or str(member.pk)
    return f"caldart-contributions-{year}-{who}.pdf"
