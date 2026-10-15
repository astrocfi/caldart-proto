"""Reading a PayPal order and its captures, and checking them against our row.

The provider in :mod:`apps.payments.providers.paypal` reads every order and
capture through these: the captures that completed and what they came to, the fee
PayPal kept, the capture a refund is issued against, and :func:`verify_capture`,
which every path that settles a payment from a capture -- the capture call, the
capture notification, the renewal charge -- passes through.
"""

from __future__ import annotations

import logging
from typing import Any

from apps.payments.models import Payment
from apps.payments.providers.base import PaymentVerificationError, ProviderFees
from apps.payments.providers.paypal_api import cents

log = logging.getLogger(__name__)


#: Where a payment settled by a ``PAYMENT.CAPTURE.COMPLETED`` notification keeps
#: the capture it names, beside the order :meth:`PayPalProvider.start` stored, so a
#: later refund knows which capture to give the money back from.
WEBHOOK_CAPTURE_KEY = "capture"


def completed_captures(order: dict[str, Any]) -> list[dict[str, Any]]:
    """Every ``COMPLETED`` capture in a capture response.

    Reads ``purchase_units[].payments.captures[]`` and skips a capture in any other
    state.  An order without purchase units gives an empty list.
    """
    return captures_with_status(order, "COMPLETED")


def captures_with_status(order: dict[str, Any], status: str) -> list[dict[str, Any]]:
    """Every capture in ``purchase_units[].payments.captures[]`` that is in ``status``.

    An order without purchase units gives an empty list.
    """
    captures: list[dict[str, Any]] = []
    for unit in order.get("purchase_units") or []:
        captures.extend(
            capture
            for capture in (unit.get("payments") or {}).get("captures") or []
            if capture.get("status") == status
        )
    return captures


def captured_cents(order: dict[str, Any]) -> int:
    """The total of every ``COMPLETED`` capture in ``order``, in cents.

    An order without a completed capture totals zero.
    """
    return sum(cents((c.get("amount") or {}).get("value", 0)) for c in completed_captures(order))


def fees_from_capture(capture: dict[str, Any]) -> ProviderFees | None:
    """What PayPal kept and paid across, from one capture's seller breakdown.

    Reads ``seller_receivable_breakdown.paypal_fee.value`` and
    ``.net_amount.value``, the decimal strings PayPal reports, and converts both
    to cents.  Answers ``None`` when the capture doesn't carry a breakdown, which is
    what an order that has not settled looks like, and when either figure cannot
    be read as a number.
    """
    breakdown = capture.get("seller_receivable_breakdown")
    if not isinstance(breakdown, dict):
        return None
    fee = (breakdown.get("paypal_fee") or {}).get("value")
    net = (breakdown.get("net_amount") or {}).get("value")
    if fee is None or net is None:
        return None
    try:
        return ProviderFees(fee_cents=cents(fee), net_cents=cents(net))
    except ValueError:
        log.warning("PayPal reported a fee that is not a number: %r", fee)
        return None


def fees_from_order(order: dict[str, Any]) -> ProviderFees | None:
    """The same, from a whole order: the breakdown of its first completed capture.

    Answers ``None`` for an order without a completed capture, and for one whose
    capture doesn't carry a breakdown yet.
    """
    captures = completed_captures(order)
    if not captures:
        return None
    return fees_from_capture(captures[0])


def capture_id(payment: Payment) -> str:
    """The id of the capture that took ``payment``'s money, read from its stored order.

    A refund is issued against the capture rather than the order, so this is what
    the refund call needs.  The first completed capture of the stored order is
    used, and failing that the completed capture a ``PAYMENT.CAPTURE.COMPLETED``
    notification filed under :data:`WEBHOOK_CAPTURE_KEY` when it settled the
    payment.  Raises :class:`PaymentVerificationError` when neither holds one,
    which is what a payment that was never captured looks like.
    """
    raw = payment.raw or {}
    captures = completed_captures(raw)
    filed = raw.get(WEBHOOK_CAPTURE_KEY) or {}
    if not captures and filed.get("status") == "COMPLETED":
        captures = [filed]
    found = captures[0].get("id") if captures else None
    if not found:
        raise PaymentVerificationError(
            "That payment doesn't have a completed PayPal capture to refund against."
        )
    return str(found)


def log_capture_mismatch(payment: Payment, captured: int, reason: str) -> None:
    """Record at ERROR a capture that took money we cannot match to our row.

    PayPal has the money by this point, so the refusal needs a human to
    reconcile it.  ``captured`` is what PayPal took, in cents, and ``reason`` names
    the field that disagreed.  The record carries the payment id and both amounts,
    and leaves out personal data.
    """
    log.error(
        "PayPal capture mismatch (%s) for payment %s: captured %s cents, expected %s cents",
        reason,
        payment.pk,
        captured,
        payment.amount_cents,
    )


def verify_capture(
    payment: Payment, capture: dict[str, Any], *, captured: int, order_id: str
) -> None:
    """Everything about a completed capture that must match our own row.

    ``capture`` is one completed capture, ``captured`` the total PayPal took for the
    order in cents, and ``order_id`` the id of the order the capture belongs to.  The
    capture call and the ``PAYMENT.CAPTURE.COMPLETED`` notification both check here.

    Returns ``None`` when ``captured`` equals the payment's ``amount_cents``, the
    capture's ``amount.currency_code`` is the payment's currency in any case, the
    capture's ``custom_id``, when it carries one, is the payment's id, and
    ``order_id`` is the payment's own ``provider_ref``.  Otherwise records the
    mismatch through :func:`log_capture_mismatch`, since PayPal holds the money, and
    raises :class:`PaymentVerificationError` naming the first check that failed.
    """
    if captured != payment.amount_cents:
        log_capture_mismatch(payment, captured, "amount")
        raise PaymentVerificationError(
            f"PayPal captured ${captured / 100:,.2f}, not ${payment.amount_cents / 100:,.2f}."
        )

    currency = str((capture.get("amount") or {}).get("currency_code") or "")
    if currency.lower() != payment.currency.lower():
        log_capture_mismatch(payment, captured, "currency")
        raise PaymentVerificationError("PayPal captured a different currency.")

    custom_id = capture.get("custom_id")
    if custom_id and str(custom_id) != str(payment.pk):
        log_capture_mismatch(payment, captured, "custom_id")
        raise PaymentVerificationError("The PayPal capture belongs to another payment.")

    if not order_id or order_id != payment.provider_ref:
        log_capture_mismatch(payment, captured, "order")
        raise PaymentVerificationError("The PayPal capture belongs to another order.")


def belongs_to_payment_order(payment: Payment, capture: dict[str, Any]) -> bool:
    """Whether a capture notification's resource is a capture of ``payment``'s order.

    True only when the payment holds an order and the resource's related order id
    is that order, so a ``custom_id`` naming the payment is never enough on its own.
    """
    return bool(payment.provider_ref) and related_order_id(capture) == payment.provider_ref


def same_currency(payment: Payment, resource: dict[str, Any]) -> bool:
    """Whether the resource's ``amount.currency_code`` is the payment's currency."""
    currency = str((resource.get("amount") or {}).get("currency_code") or "")
    return currency.lower() == payment.currency.lower()


def related_order_id(capture: dict[str, Any]) -> str:
    """The id of the order a capture notification's resource belongs to.

    Read from ``supplementary_data.related_ids.order_id``, where PayPal puts it on a
    capture; an empty string when the resource doesn't carry one.
    """
    related = (capture.get("supplementary_data") or {}).get("related_ids") or {}
    return str(related.get("order_id") or "")
