"""Payment services.

The server never trusts a client-supplied amount: totals are recomputed from
the plan price plus the contribution.  Input the server will not act on is
refused with a ``DomainValidationError`` naming the field it came from.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.members.models import MembershipPlan, MembershipSource
from apps.members.services import activate_term
from apps.payments.models import Payment, PaymentProvider, PaymentStatus, PaymentWallet
from caldart.exceptions import DomainValidationError


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


@transaction.atomic
def mark_succeeded(
    payment: Payment,
    *,
    wallet: str = PaymentWallet.UNKNOWN,
    raw: dict[str, Any] | None = None,
    provider_ref: str | None = None,
) -> Payment:
    """Mark a payment succeeded and activate the membership term.

    Stamps ``completed_at`` with the current time, stores ``wallet``
    , ``provider_ref``, and ``raw`` when each is given, and activates a term for the
    payment's plan when it has one.  Returns the row as saved.

    Idempotent: a second call is a no-op that returns the same payment, so
    webhook and client confirmation can race safely.
    """
    payment = Payment.objects.select_for_update().get(pk=payment.pk)

    if payment.status == PaymentStatus.SUCCEEDED:
        return payment

    payment.status = PaymentStatus.SUCCEEDED
    payment.completed_at = timezone.now()
    if wallet:
        payment.wallet = wallet
    if provider_ref:
        payment.provider_ref = provider_ref
    if raw is not None:
        payment.raw = raw
    payment.save(
        update_fields=["status", "completed_at", "wallet", "provider_ref", "raw", "updated_at"]
    )

    if payment.plan is not None:
        activate_term(
            payment.user,
            payment.plan,
            source=MembershipSource.PAYMENT,
            payment=payment,
        )
    return payment


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
