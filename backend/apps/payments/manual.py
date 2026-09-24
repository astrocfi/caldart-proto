"""Payments taken by hand: a check in the mail, cash at a meeting, a transfer.

Money that never passes through Stripe or PayPal still buys a membership term
and still earns a receipt, so a payment recorded here goes through exactly the
same service a card checkout does.  It differs in only three ways: the provider
is ``manual``, the fee is nothing so the net equals the amount, and the ledger
date is the day the money was received rather than the moment it was keyed in.
"""

from __future__ import annotations

import datetime as dt

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.payments.models import Payment, PaymentProvider, PaymentWallet
from apps.payments.services import create_checkout, mark_succeeded
from caldart.exceptions import DomainValidationError

#: How a payment recorded by hand can have been presented.  Every other wallet
#: describes something a provider told us, which nobody can say of a check.
MANUAL_METHODS = (
    PaymentWallet.CHECK,
    PaymentWallet.CASH,
    PaymentWallet.BANK_TRANSFER,
    PaymentWallet.OTHER,
)

#: The same four, as the choices a serializer field takes.
MANUAL_METHOD_CHOICES = [(method.value, method.label) for method in MANUAL_METHODS]


@transaction.atomic
def record_manual_payment(
    *,
    user: User,
    plan_slug: str | None,
    contribution_cents: int,
    method: str,
    reference: str,
    received_on: dt.date,
    note: str,
    actor: User,
) -> Payment:
    """Record money taken by hand and activate whatever term it bought.

    ``plan_slug`` names an active membership plan, a lifetime plan included, or is
    empty for a pure contribution.  ``method`` is one of :data:`MANUAL_METHODS`,
    ``reference`` is the check number or transfer reference and may be empty,
    ``received_on`` is the day the money arrived, and ``note`` is the treasurer's
    own line about it.  ``actor`` is the administrator doing the recording and is
    kept on the payment as ``recorded_by``.

    The payment is created already succeeded, with a zero fee and a net equal to
    the amount, and the term is activated through the same service a card
    checkout uses, which also emails the receipt.  Returns the payment as saved.

    Raises ``DomainValidationError`` keyed by ``method`` for a method outside
    :data:`MANUAL_METHODS`, by ``received_on`` for a day in the future, by
    ``reference`` for a reference another recorded payment already carries --
    including one recorded between this call's check and its insert -- by
    ``plan`` for a plan that is not active, by ``contribution_cents`` for a
    negative contribution and by ``amount_cents`` when the plan and the
    contribution come to nothing.  Nothing is written when it raises.
    """
    if method not in MANUAL_METHODS:
        raise DomainValidationError("method", f"Unknown payment method '{method}'.")
    if received_on > timezone.localdate():
        raise DomainValidationError("received_on", "The money cannot have arrived in the future.")
    if reference and _reference_taken(reference):
        raise DomainValidationError("reference", _taken_message(reference))

    payment = create_checkout(user, plan_slug, contribution_cents, PaymentProvider.MANUAL)
    payment.wallet = method
    payment.provider_ref = reference
    payment.received_on = received_on
    payment.note = note
    payment.recorded_by = actor
    payment.fee_cents = 0
    payment.net_cents = payment.amount_cents
    # The check above is a read, so two treasurers entering the same check at
    # once can both pass it; the unique constraint on (provider, provider_ref)
    # catches the loser, and it deserves the same message as the winner's
    # duplicate would have got.
    try:
        with transaction.atomic():
            payment.save(
                update_fields=[
                    "wallet",
                    "provider_ref",
                    "received_on",
                    "note",
                    "recorded_by",
                    "fee_cents",
                    "net_cents",
                    "updated_at",
                ]
            )
    except IntegrityError as exc:
        raise DomainValidationError("reference", _taken_message(reference)) from exc
    return mark_succeeded(payment, wallet=method, provider_ref=reference)


def _taken_message(reference: str) -> str:
    """What a treasurer is told when a check number is already in the books."""
    return f"Another recorded payment already carries the reference '{reference}'."


def _reference_taken(reference: str) -> bool:
    """Whether a payment recorded by hand already carries ``reference``."""
    return Payment.objects.filter(provider=PaymentProvider.MANUAL, provider_ref=reference).exists()
