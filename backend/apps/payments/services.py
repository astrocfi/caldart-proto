"""Payment services.

The server never trusts a client-supplied amount: totals are recomputed from
the plan price plus the contribution.  Input the server will not act on is
refused with a ``DomainValidationError`` naming the field it came from.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.members.models import MembershipPlan, MembershipSource
from apps.members.services import activate_term
from apps.payments.models import Payment, PaymentProvider, PaymentStatus, PaymentWallet
from caldart.exceptions import DomainValidationError


@transaction.atomic
def create_checkout(
    user,
    plan_slug: str | None,
    contribution_cents: int = 0,
    provider: str = PaymentProvider.MOCK,
) -> Payment:
    """Create a ``pending`` payment for ``plan_slug`` plus an optional donation."""
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
    raw: dict | None = None,
    provider_ref: str | None = None,
) -> Payment:
    """Mark a payment succeeded and activate the membership term.

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

    if payment.plan_id:
        activate_term(
            payment.user,
            payment.plan,
            source=MembershipSource.PAYMENT,
            payment=payment,
        )
    return payment


@transaction.atomic
def mark_failed(payment: Payment, raw: dict | None = None) -> Payment:
    """Mark a pending payment failed.  A succeeded payment is never downgraded."""
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    if payment.status == PaymentStatus.SUCCEEDED:
        return payment
    payment.status = PaymentStatus.FAILED
    if raw is not None:
        payment.raw = raw
    payment.save(update_fields=["status", "raw", "updated_at"])
    return payment


@transaction.atomic
def record_provider_event(payment: Payment, payload: dict) -> Payment:
    """File a provider notification against a payment without changing its state.

    Used by the PayPal webhook, which is a recorder rather than an authority:
    the capture call is what activates a membership.
    """
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    raw = dict(payment.raw or {})
    raw["last_webhook"] = payload
    payment.raw = raw
    payment.save(update_fields=["raw", "updated_at"])
    return payment
