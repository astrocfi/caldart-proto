"""Payment services.

The server never trusts a client-supplied amount: totals are recomputed from
the plan price plus the contribution.  Input the server will not act on is
refused with a ``DomainValidationError`` naming the field it came from.

Every payment that succeeds also carries what it cost -- the provider's fee and
the net that reached CalDART -- and earns the member a receipt, emailed from
here through :mod:`apps.payments.receipts`.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.members.models import MembershipPlan, MembershipSource
from apps.members.services import activate_term
from apps.payments.models import Payment, PaymentProvider, PaymentStatus, PaymentWallet
from apps.payments.receipts import send_receipt
from caldart.exceptions import DomainValidationError

#: The fee a provider that has not settled yet reports: none, because it does
#: not know.  A payment whose ``net_cents`` is still this while its amount is
#: not has a fee nobody has been told; :func:`backfill_fees` is what asks again.
UNKNOWN_NET_CENTS = 0


@transaction.atomic
def create_checkout(
    user: User,
    plan_slug: str | None,
    contribution_cents: int = 0,
    provider: str = PaymentProvider.MOCK,
) -> Payment:
    """Create a ``pending`` payment for ``plan_slug`` plus an optional donation.

    The amount is computed here and never taken from the client: it is the active
    plan's price plus ``contribution_cents``.  A falsy ``plan_slug`` makes the
    payment a pure donation, with no plan and a zero plan amount.

    Raises ``DomainValidationError`` keyed by ``provider`` for a slug outside
    :class:`PaymentProvider`, by ``contribution_cents`` for a negative
    contribution, by ``plan`` when no active plan has that slug, and by
    ``amount_cents`` when the total comes to zero.  Nothing is written when it
    raises.
    """
    if provider not in PaymentProvider.values:
        raise DomainValidationError("provider", f"Unknown payment provider '{provider}'.")

    contribution_cents = int(contribution_cents or 0)
    if contribution_cents < 0:
        raise DomainValidationError("contribution_cents", "Contribution cannot be negative.")

    plan = None
    plan_amount_cents = 0
    if plan_slug:
        plan = MembershipPlan.objects.filter(slug=plan_slug, is_active=True).first()
        if plan is None:
            raise DomainValidationError("plan", f"Unknown membership plan '{plan_slug}'.")
        plan_amount_cents = plan.price_cents

    amount_cents = plan_amount_cents + contribution_cents
    if amount_cents <= 0:
        raise DomainValidationError("amount_cents", "Nothing to charge.")

    return Payment.objects.create(
        user=user,
        plan=plan,
        amount_cents=amount_cents,
        plan_amount_cents=plan_amount_cents,
        contribution_cents=contribution_cents,
        currency="usd",
        provider=provider,
        status=PaymentStatus.PENDING,
    )


def settled_fees(payment: Payment, fee_cents: int | None, net_cents: int | None) -> tuple[int, int]:
    """The fee and net to store for a payment that has just succeeded.

    A provider that reported both is believed.  A provider that reported only a
    fee has its net computed as the amount less that fee.  A provider that
    reported neither leaves a figure already on the row alone, because the fee
    can reach us before the success does -- nothing orders a provider's
    callbacks.  A payment recorded by hand cost nothing, so its net is the whole
    amount.  Anything else -- a provider that has not settled yet -- is left
    unknown, as ``(0, 0)``, for :func:`backfill_fees` to ask about later.
    """
    if fee_cents is not None:
        return fee_cents, net_cents if net_cents is not None else payment.amount_cents - fee_cents
    if net_cents is not None:
        return payment.amount_cents - net_cents, net_cents
    if fees_are_known(payment):
        return payment.fee_cents, payment.net_cents
    if payment.provider == PaymentProvider.MANUAL:
        return 0, payment.amount_cents
    return 0, UNKNOWN_NET_CENTS


def fees_are_known(payment: Payment) -> bool:
    """Whether the provider has told us what ``payment`` cost.

    A settled payment always nets something, so a zero net against a non-zero
    amount is the mark of a fee nobody has reported yet.  A payment of nothing
    -- which checkout will not create -- reads as known.
    """
    return payment.amount_cents == 0 or payment.net_cents != UNKNOWN_NET_CENTS


def mark_succeeded(
    payment: Payment,
    *,
    wallet: str = PaymentWallet.UNKNOWN,
    raw: dict[str, Any] | None = None,
    provider_ref: str | None = None,
    fee_cents: int | None = None,
    net_cents: int | None = None,
) -> Payment:
    """Mark a payment succeeded, activate the term, and email the receipt.

    Stamps ``completed_at`` with the current time, stores ``wallet``,
    ``provider_ref``, and ``raw`` when each is given, records what the payment
    cost as :func:`settled_fees` works it out from ``fee_cents`` and
    ``net_cents``, and activates a term for the payment's plan when it has one.
    CalDART's own receipt is then emailed to the payer with its PDF attached,
    outside the transaction that moved the payment: a mail server that refuses
    it is logged and leaves ``receipt_sent_at`` null, never undoing the
    membership the money bought.  Returns the row as saved.

    A checkout that asked for automatic renewal leaves the payer a ``pending``
    :class:`~apps.payments.models.RenewalMandate`; this is where it becomes
    active, from the payment method the provider has just recorded against the
    charge.  A payment with no such mandate activates nothing.

    Idempotent: a second call is a no-op that returns the same payment and
    sends no second receipt, so webhook and client confirmation can race safely.
    """
    payment, transitioned = _complete(
        payment, wallet=wallet, raw=raw, provider_ref=provider_ref, fees=(fee_cents, net_cents)
    )
    if transitioned:
        send_receipt(payment)
    return payment


@transaction.atomic
def _complete(
    payment: Payment,
    *,
    wallet: str,
    raw: dict[str, Any] | None,
    provider_ref: str | None,
    fees: tuple[int | None, int | None],
) -> tuple[Payment, bool]:
    """Move ``payment`` to succeeded, activate its term and its mandate, under one lock.

    Returns the row as saved and whether this call is the one that moved it, so
    only the caller that did the work sends the receipt.
    """
    payment = Payment.objects.select_for_update().get(pk=payment.pk)

    if payment.status == PaymentStatus.SUCCEEDED:
        return payment, False

    payment.status = PaymentStatus.SUCCEEDED
    payment.completed_at = timezone.now()
    if wallet:
        payment.wallet = wallet
    if provider_ref:
        payment.provider_ref = provider_ref
    if raw is not None:
        payment.raw = raw
    payment.fee_cents, payment.net_cents = settled_fees(payment, *fees)
    payment.save(
        update_fields=[
            "status",
            "completed_at",
            "wallet",
            "provider_ref",
            "raw",
            "fee_cents",
            "net_cents",
            "updated_at",
        ]
    )

    if payment.plan is not None:
        activate_term(
            payment.user,
            payment.plan,
            source=MembershipSource.PAYMENT,
            payment=payment,
        )

    # Inline: renewals reads this module for create_checkout and mark_failed, so a
    # top-level import here would close the cycle.
    from apps.payments.renewals import activate_pending_mandate

    activate_pending_mandate(payment)
    return payment, True


@transaction.atomic
def record_fees(payment: Payment, *, fee_cents: int, net_cents: int) -> Payment:
    """Store what a payment cost, whenever the provider gets round to saying.

    Used by the provider callbacks that learn the fee after the money arrived.
    Nothing else about the payment changes, and the row comes back as saved.
    """
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    payment.fee_cents = fee_cents
    payment.net_cents = net_cents
    payment.save(update_fields=["fee_cents", "net_cents", "updated_at"])
    return payment


def backfill_fees(payment: Payment) -> Payment:
    """Ask the provider again what ``payment`` cost, and store what it says.

    The row is read afresh, so a caller holding a stale copy still gets the
    right answer.  Answers it unchanged when the payment was recorded by hand,
    when it has not succeeded, and when the provider still has no figure to
    give.  Whatever the provider raises -- it is unconfigured, or unreachable --
    propagates, so the caller can tell "no answer yet" from "could not ask".
    """
    payment = Payment.objects.get(pk=payment.pk)
    if payment.provider == PaymentProvider.MANUAL or not payment.is_succeeded:
        return payment
    # Inline: the provider registry imports this module, so a top-level import
    # would be a cycle.
    from apps.payments.providers import get_provider

    fees = get_provider(payment.provider).fetch_fees(payment)
    if fees is None:
        return payment
    return record_fees(payment, fee_cents=fees.fee_cents, net_cents=fees.net_cents)


@transaction.atomic
def mark_failed(payment: Payment, raw: dict[str, Any] | None = None) -> Payment:
    """Mark a pending payment failed.  A succeeded payment is never downgraded.

    Stores ``raw`` when it is given, leaves ``completed_at`` alone, and returns the
    row as saved.  Activates no term and expires none.
    """
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    if payment.status == PaymentStatus.SUCCEEDED:
        return payment
    payment.status = PaymentStatus.FAILED
    if raw is not None:
        payment.raw = raw
    payment.save(update_fields=["status", "raw", "updated_at"])
    return payment


@transaction.atomic
def record_provider_event(payment: Payment, payload: dict[str, Any]) -> Payment:
    """File a provider notification against a payment without changing its state.

    ``payload`` replaces ``raw["last_webhook"]``, so only the most recent
    notification is kept.  The status, the wallet and the term are untouched.

    Used by the PayPal webhook, which is a recorder rather than an authority:
    the capture call is what activates a membership.
    """
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    raw = dict(payment.raw or {})
    raw["last_webhook"] = payload
    payment.raw = raw
    payment.save(update_fields=["raw", "updated_at"])
    return payment
