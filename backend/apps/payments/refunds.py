"""Refunds: giving money back against a payment, and recording the ones we did not.

A refund is a record in its own right.  :func:`issue_refund` writes it
``pending``, asks the provider for the money, and then either marks it
``succeeded`` -- moving the payment to ``partially_refunded`` or ``refunded``,
optionally canceling the membership term the payment bought, and emailing the
member -- or leaves it ``failed`` for a treasurer to look at.  The rule that a
payment's succeeded refunds never exceed what it took is kept here rather than
in the database, because it is a rule about the running total and not about one
row.

Somebody can also refund in Stripe's or PayPal's own dashboard, where CalDART
has no say.  :func:`record_dashboard_refund` is what the two webhooks call so
that the ledger is right anyway; it never cancels a term, because the treasurer
decides that on the payment's own screen.
"""

from __future__ import annotations

import logging
import smtplib
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.members import services as member_services
from apps.members.models import Membership
from apps.payments.models import (
    Payment,
    PaymentProvider,
    PaymentStatus,
    Refund,
    RefundReason,
    RefundStatus,
)
from apps.payments.providers.base import PaymentError, ProviderRefund, get_provider
from caldart import audit
from caldart.exceptions import DomainValidationError
from caldart.mail import contact_email, org_name, send_templated
from caldart.reports import money_label

log = logging.getLogger(__name__)

#: The note carried by a refund somebody issued in the provider's own dashboard,
#: which reached us as a webhook rather than as a request.
DASHBOARD_NOTE = "Issued in the provider's dashboard"

#: The subject of the email a member gets when money goes back to them.
REFUND_SUBJECT = "{org}: a refund of {amount}"

#: The statuses a payment whose money arrived can be in.  A refund is refused
#: from any other, and one from these is judged on what is left, so a payment
#: already given back in full is refused by amount rather than by status.
SETTLED_STATUSES = frozenset(
    {
        PaymentStatus.SUCCEEDED,
        PaymentStatus.PARTIALLY_REFUNDED,
        PaymentStatus.REFUNDED,
    }
)


def payments_url() -> str:
    """Absolute link to the portal's payments screen, which every refund email carries."""
    return f"{settings.SITE_URL.rstrip('/')}/portal/payments"


def remaining_cents(payment: Payment) -> int:
    """What is still refundable on ``payment``: its amount less its succeeded refunds.

    A payment nobody has refunded answers its whole ``amount_cents``, and one
    that has been given back in full answers ``0``.  Pending and failed refunds
    count for nothing, so a refund the provider refused does not lock money away.
    """
    return payment.amount_cents - payment.refunded_cents


def issue_refund(
    payment: Payment,
    *,
    amount_cents: int,
    reason: str,
    note: str = "",
    actor: User | None = None,
    cancel_term: bool = False,
) -> Refund:
    """Give ``amount_cents`` of ``payment`` back, and return the refund row.

    The row is written ``pending``, the payment's provider is asked for the money
    -- except for a payment recorded by hand, where the check was written by hand
    too and there is nobody to ask -- and the row is then ``succeeded``.  The
    payment becomes ``refunded`` when its succeeded refunds come to its whole
    amount and ``partially_refunded`` otherwise.  ``cancel_term`` cancels the
    membership term the payment bought, with a note naming this refund; a payment
    that bought no term ignores it.  The member is emailed, and the action is
    recorded in the audit log under ``payment.refund``.

    ``actor`` is the administrator issuing it, and is kept on the row as
    ``requested_by``.  ``reason`` is one of the ``RefundReason`` values and
    ``note`` a sentence at most 255 characters long.

    Raises ``DomainValidationError`` keyed by ``amount_cents`` when the amount is
    zero or less, when it exceeds :func:`remaining_cents`, and when the payment
    never succeeded, and keyed by ``reason`` for a reason outside the choices;
    nothing is written when it raises.  A provider that refuses or cannot be
    reached leaves the row ``failed``, emails nobody and re-raises the provider's
    own ``PaymentError``, so the caller can show the sentence it carries.
    """
    if reason not in RefundReason.values:
        raise DomainValidationError("reason", f"Unknown refund reason '{reason}'.")

    with transaction.atomic():
        locked = Payment.objects.select_for_update().get(pk=payment.pk)
        if locked.status not in SETTLED_STATUSES:
            raise DomainValidationError(
                "amount_cents", "That payment has not succeeded, so there is nothing to refund."
            )
        if amount_cents <= 0:
            raise DomainValidationError("amount_cents", "A refund must be for more than zero.")
        left = remaining_cents(locked)
        if amount_cents > left:
            raise DomainValidationError(
                "amount_cents",
                f"Only {money_label(left)} of this payment is left to refund.",
            )
        refund = Refund.objects.create(
            payment=locked,
            amount_cents=amount_cents,
            reason=reason,
            note=note,
            status=RefundStatus.PENDING,
            requested_by=actor,
        )

    result = _ask_the_provider(locked, refund)

    with transaction.atomic():
        refund.provider_ref = result["provider_ref"]
        refund.raw = result["raw"]
        refund.status = RefundStatus.SUCCEEDED
        refund.refunded_at = timezone.now()
        refund.save(update_fields=["provider_ref", "raw", "status", "refunded_at", "updated_at"])
        apply_refund_totals(locked)
        term = _canceled_term(refund, actor=actor) if cancel_term else None

    audit.record(
        audit.PAYMENT_REFUND,
        actor=actor if actor is not None else audit.COMMAND_ACTOR,
        target=locked,
        refund=refund.pk,
        amount_cents=amount_cents,
        reason=reason,
        term_canceled=term is not None,
    )
    send_refund_email(refund, term_canceled=term is not None)
    return refund


def record_dashboard_refund(
    payment: Payment,
    *,
    amount_cents: int,
    provider_ref: str,
    raw: dict[str, Any],
) -> Refund | None:
    """Record a refund somebody took in the provider's own dashboard.

    Writes a ``succeeded`` refund with no ``requested_by``, the reason ``other``
    and :data:`DASHBOARD_NOTE`, updates the payment's status, and emails the
    member.  No membership term is canceled: a webhook never decides that.

    Returns ``None`` and writes nothing when a refund already carries
    ``provider_ref`` against this payment, which is what makes a second delivery
    of the same notification -- and the notification for a refund CalDART itself
    issued -- a no-op.  Returns ``None`` too for a blank ``provider_ref``, since
    there would be nothing to recognize it by next time.
    """
    if not provider_ref:
        log.warning("Ignored a dashboard refund for payment %s with no reference", payment.pk)
        return None

    with transaction.atomic():
        locked = Payment.objects.select_for_update().get(pk=payment.pk)
        if locked.refunds.filter(provider_ref=provider_ref).exists():
            return None
        refund = Refund.objects.create(
            payment=locked,
            amount_cents=amount_cents,
            reason=RefundReason.OTHER,
            note=DASHBOARD_NOTE,
            status=RefundStatus.SUCCEEDED,
            provider_ref=provider_ref,
            refunded_at=timezone.now(),
            raw=raw,
        )
        apply_refund_totals(locked)

    audit.record(
        audit.PAYMENT_REFUND,
        actor=audit.COMMAND_ACTOR,
        target=locked,
        refund=refund.pk,
        amount_cents=amount_cents,
        reason=RefundReason.OTHER.value,
        term_canceled=False,
    )
    send_refund_email(refund, term_canceled=False)
    return refund


def apply_refund_totals(payment: Payment) -> Payment:
    """Move ``payment``'s status to match what its succeeded refunds come to.

    ``refunded`` once they total the whole amount, ``partially_refunded`` while
    they total less, and ``succeeded`` again if they come to nothing, which is
    what happens when the only refund of a payment failed.  A payment that never
    succeeded is left alone: a pending or failed attempt took no money and so
    has none to give back.  Returns the row as saved.
    """
    if payment.status in (PaymentStatus.PENDING, PaymentStatus.FAILED):
        return payment
    refunded = payment.refunded_cents
    if refunded >= payment.amount_cents:
        payment.status = PaymentStatus.REFUNDED
    elif refunded > 0:
        payment.status = PaymentStatus.PARTIALLY_REFUNDED
    else:
        payment.status = PaymentStatus.SUCCEEDED
    payment.save(update_fields=["status", "updated_at"])
    return payment


def send_refund_email(refund: Refund, *, term_canceled: bool) -> None:
    """Tell the member money is on its way back, and never raise if the mail fails.

    Renders ``emails/refund.{txt,html}`` with the amount, what the payment was
    for, and whether the membership term ended with it.  The money has already
    moved by the time this is called, so a mail server that refuses the message
    is logged at ERROR and nothing else: the treasurer can say so by hand.
    """
    payment = refund.payment
    user = payment.user
    if not user.email:
        return
    org = org_name()
    context: dict[str, object] = {
        "org_name": org,
        "contact_email": contact_email(),
        "first_name": user.first_name or user.display_name,
        "amount": money_label(refund.amount_cents),
        "payment_amount": money_label(payment.amount_cents),
        "description": payment.description,
        "receipt_number": payment.receipt_number,
        "reason": refund.get_reason_display(),
        "refunded_on": refund.refunded_at,
        "term_canceled": term_canceled,
        "payments_url": payments_url(),
        "site_url": settings.SITE_URL.rstrip("/"),
    }
    try:
        send_templated(
            to=user.email,
            subject=REFUND_SUBJECT.format(org=org, amount=money_label(refund.amount_cents)),
            template="refund",
            context=context,
        )
    except (smtplib.SMTPException, OSError):
        log.exception("Could not email the refund notice for refund %s", refund.pk)


def _ask_the_provider(payment: Payment, refund: Refund) -> ProviderRefund:
    """The provider's answer to the refund, marking the row failed if it refuses.

    A payment recorded by hand is answered without calling anything: the money
    goes back the way it came, by check or in cash, and no provider is involved.
    Any ``PaymentError`` the provider raises marks ``refund`` failed and travels
    on to the caller.
    """
    if payment.provider == PaymentProvider.MANUAL:
        return ProviderRefund(provider_ref="", raw={"provider": PaymentProvider.MANUAL.value})
    try:
        return get_provider(payment.provider).refund(payment, refund)
    except PaymentError as exc:
        refund.status = RefundStatus.FAILED
        refund.raw = {"error": str(exc)}
        refund.save(update_fields=["status", "raw", "updated_at"])
        log.warning("Refund %s for payment %s failed: %s", refund.pk, payment.pk, exc)
        raise


def _canceled_term(refund: Refund, *, actor: User | None) -> Membership | None:
    """Cancel the term ``refund``'s payment bought, or ``None`` when it bought none.

    The note names the refund, so an administrator reading the term later can
    find the money that ended it.
    """
    term = Membership.objects.filter(payment=refund.payment).first()
    if term is None:
        return None
    return member_services.cancel_term(term, actor=actor, note=f"Canceled by refund {refund.pk}")
