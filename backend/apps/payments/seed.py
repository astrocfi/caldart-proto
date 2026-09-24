"""Seed ~24 months of succeeded payments, the terms they bought and some refunds.

Every term goes through :func:`apps.members.services.activate_term`, so the
seeded data exercises the same code path as a real checkout.

Each payment carries the fee its provider would have charged and the net that
would have reached CalDART, and is stamped as having had its receipt emailed,
so the finance screens and the exports have real figures to show from the first
run.
"""

from __future__ import annotations

import datetime as dt
import random
from datetime import timedelta
from typing import Any

from django.core.management.base import OutputWrapper
from django.utils import timezone

from apps.accounts.models import User
from apps.members.models import (
    Membership,
    MembershipPlan,
    MembershipSource,
)
from apps.members.services import activate_term, cancel_term, expire_lapsed_memberships
from apps.payments.models import (
    CONTRIBUTION_TIERS,
    Payment,
    PaymentProvider,
    PaymentStatus,
    PaymentWallet,
    Refund,
    RefundReason,
    RefundStatus,
)
from apps.payments.refunds import apply_refund_totals

#: How far back the payment history runs.
HISTORY_MONTHS = 24

PROVIDER_MIX: tuple[tuple[str, int], ...] = (
    (PaymentProvider.STRIPE, 70),
    (PaymentProvider.PAYPAL, 30),
)

STRIPE_WALLETS: tuple[tuple[str, int], ...] = (
    (PaymentWallet.CARD, 60),
    (PaymentWallet.APPLE_PAY, 18),
    (PaymentWallet.GOOGLE_PAY, 12),
    (PaymentWallet.LINK, 10),
)

#: What each provider charges, as the rate in ten-thousandths and the fixed part
#: in cents: Stripe 2.9% + 30 cents, PayPal 3.49% + 49 cents.  PayPal's rate
#: needs the finer granularity: 3.49% is not a whole number of thousandths.  A
#: provider nobody lists here takes nothing, which is what a payment recorded by
#: hand costs.
PROVIDER_FEES: dict[str, tuple[int, int]] = {
    PaymentProvider.STRIPE: (290, 30),
    PaymentProvider.PAYPAL: (349, 49),
}


def provider_fee_cents(provider: str, amount_cents: int) -> int:
    """The fee ``provider`` would have charged on ``amount_cents``.

    The percentage is rounded half up to the cent, as a processor rounds it.
    A provider with no published rate -- a check, say -- costs nothing.
    """
    if provider not in PROVIDER_FEES:
        return 0
    rate, fixed = PROVIDER_FEES[provider]
    return (amount_cents * rate + 5_000) // 10_000 + fixed


#: How many payments the seed gives back in full, canceling the term each bought.
#: They are chosen from terms that have already ended, so the demo's current
#: members stay current.
FULL_REFUNDS = 2

#: How many contributions the seed gives back on their own, leaving the dues and
#: the membership term alone.
PARTIAL_REFUNDS = 4

#: The reason recorded against each seeded refund, in the order they are written.
REFUND_REASONS: tuple[str, ...] = (
    RefundReason.REQUESTED_BY_MEMBER,
    RefundReason.DUPLICATE,
    RefundReason.REQUESTED_BY_MEMBER,
    RefundReason.ERROR,
    RefundReason.REQUESTED_BY_MEMBER,
    RefundReason.OTHER,
)

#: How long after a payment a seeded refund was taken.
REFUND_DELAY_DAYS = 5


def _pick(rng: random.Random, mix: tuple[tuple[str, int], ...]) -> str:
    values = [v for v, _ in mix]
    weights = [w for _, w in mix]
    return rng.choices(values, weights=weights)[0]


def _contribution(rng: random.Random) -> int:
    if rng.random() < 0.62:
        return 0
    tier = rng.choice([t for t in CONTRIBUTION_TIERS if t["cents"]])
    if rng.random() < 0.15:  # "other amount"
        return rng.randrange(500, 25_000, 500)
    return tier["cents"]


def _term_starts(rng: random.Random, target: str, today: dt.date) -> list[dt.date]:
    """Start dates for a user's terms, oldest first, matching ``target``."""
    if target == "none":
        return []
    if target == "lifetime":
        return [today - timedelta(days=rng.randint(120, HISTORY_MONTHS * 30))]

    if target == "current":
        last_end = today + timedelta(days=rng.randint(31, 360))
    elif target == "expiring":
        last_end = today + timedelta(days=rng.randint(1, 30))
    else:  # expired
        last_end = today - timedelta(days=rng.randint(5, 420))

    last_start = last_end - timedelta(days=364)
    count = rng.choices([1, 2, 3], weights=[45, 35, 20])[0]
    return [last_start - timedelta(days=365 * i) for i in range(count - 1, -1, -1)]


def _payment_for(
    user: User,
    plan: MembershipPlan,
    starts_on: dt.date,
    index: int,
    rng: random.Random,
    today: dt.date,
) -> Payment:
    """The succeeded payment that bought ``user`` the term starting ``starts_on``.

    Keyed on ``provider`` and a reference built from ``user`` and ``index``, so a
    second ``seed_demo`` run finds the row it made before instead of a duplicate.
    A row it creates is backdated: ``created_at`` and ``completed_at`` both become
    a random daytime moment on ``starts_on``, or on ``today`` when the term starts
    in the future.
    """
    provider = _pick(rng, PROVIDER_MIX)
    wallet = (
        _pick(rng, STRIPE_WALLETS) if provider == PaymentProvider.STRIPE else PaymentWallet.PAYPAL
    )
    contribution = _contribution(rng)
    amount = plan.price_cents + contribution
    ref = f"seed_{provider}_{user.pk}_{index}"

    # Draw the timestamp unconditionally: the random stream must advance the
    # same way whether or not this payment already exists, or a second
    # ``seed_demo`` run would generate a different data set.
    paid_at = timezone.make_aware(
        dt.datetime.combine(
            min(starts_on, today),
            dt.time(hour=rng.randint(8, 20), minute=rng.randint(0, 59)),
        )
    )

    fee = provider_fee_cents(provider, amount)
    payment, created = Payment.objects.get_or_create(
        provider=provider,
        provider_ref=ref,
        defaults={
            "user": user,
            "plan": plan,
            "amount_cents": amount,
            "plan_amount_cents": plan.price_cents,
            "contribution_cents": contribution,
            "currency": "usd",
            "wallet": wallet,
            "status": PaymentStatus.SUCCEEDED,
            "fee_cents": fee,
            "net_cents": amount - fee,
            "raw": {"seeded": True, "provider": provider},
        },
    )
    if created:
        # ``created_at`` is auto_now_add, so backdate it with an UPDATE.  The
        # receipt is stamped as sent at the same moment: a seeded payment stands
        # for one that went through, and a real one always earns a receipt.
        Payment.objects.filter(pk=payment.pk).update(
            created_at=paid_at, completed_at=paid_at, receipt_sent_at=paid_at
        )
        payment.refresh_from_db()
    return payment


def _refund(payment: Payment, amount_cents: int, reason: str, note: str) -> bool:
    """Write one seeded refund against ``payment``, and say whether it was created.

    Keyed on the payment's own seeded reference, so a second ``seed_demo`` run
    finds the row it made before instead of writing a second refund.  The
    payment's status follows the running total.
    """
    refunded_at = (payment.completed_at or timezone.now()) + timedelta(days=REFUND_DELAY_DAYS)
    _, created = Refund.objects.get_or_create(
        payment=payment,
        provider_ref=f"seed_refund_{payment.pk}",
        defaults={
            "amount_cents": amount_cents,
            "reason": reason,
            "note": note,
            "status": RefundStatus.SUCCEEDED,
            "refunded_at": refunded_at,
            "raw": {"seeded": True},
        },
    )
    if created:
        apply_refund_totals(payment)
    return created


def _seed_refunds(today: dt.date, generated: list[User]) -> int:
    """Refund a few of ``generated``'s payments, and return how many were written.

    Two payments are given back in full and the terms they bought are canceled;
    four contributions are given back on their own, leaving the dues and the
    membership alone.  Both sets are chosen in id order from terms that have
    already ended and from payments that carry a contribution, so the choice
    depends on nothing a refund changes: running this twice writes nothing
    twice, and it never moves the shared random stream.

    Only the generated members are touched.  The named demo accounts are the
    fixed cast the guides and the end-to-end specs drive, and a canceled term
    would change the membership each of them is there to demonstrate.
    """
    member_ids = [user.pk for user in generated]
    terms = list(
        Membership.objects.filter(
            user_id__in=member_ids,
            payment__isnull=False,
            ends_on__isnull=False,
            ends_on__lt=today,
        )
        .select_related("payment")
        .order_by("payment_id")[:FULL_REFUNDS]
    )
    written = 0
    refunded_ids = []
    for index, term in enumerate(terms):
        payment = term.payment
        if payment is None:
            continue
        refunded_ids.append(payment.pk)
        if _refund(payment, payment.amount_cents, REFUND_REASONS[index], "Membership refunded"):
            cancel_term(term, note="Canceled with a full refund")
            written += 1

    contributions = (
        Payment.objects.filter(user_id__in=member_ids, contribution_cents__gt=0)
        .exclude(pk__in=refunded_ids)
        .order_by("pk")[:PARTIAL_REFUNDS]
    )
    for index, payment in enumerate(contributions):
        reason = REFUND_REASONS[FULL_REFUNDS + index]
        if _refund(payment, payment.contribution_cents, reason, "Contribution refunded"):
            written += 1
    return written


def run(ctx: dict[str, Any], stdout: OutputWrapper | None = None) -> dict[str, Any]:
    """Seed each user's payments and terms, and return the shared seed context.

    ``ctx`` carries the seed run's ``rng``, ``today``, ``plans``, and ``users``, plus
    the ``membership_targets`` that say which of ``none``, ``current``, ``expiring``
    , ``expired``, or ``lifetime`` each user should end up in.  One payment is created
    per term, every term is activated through the same service a real checkout uses,
    and lapsed terms are then marked expired.  ``ctx["payment_count"]`` is set to the
    number of payments, and a one-line summary is written to ``stdout`` when one is
    given.  Running it twice over the same database changes nothing.
    """
    rng = ctx["rng"]
    today = ctx["today"]
    plans = ctx["plans"]
    targets: dict[int, str] = ctx["membership_targets"]

    annual = plans["annual"]
    life = plans["life"]

    payments = 0
    terms = 0
    for user in ctx["users"]:
        target = targets.get(user.pk, "none")
        starts = _term_starts(rng, target, today)
        plan = life if target == "lifetime" else annual
        for index, starts_on in enumerate(starts):
            payment = _payment_for(user, plan, starts_on, index, rng, today)
            payments += 1
            activate_term(
                user,
                plan,
                source=MembershipSource.PAYMENT,
                payment=payment,
                starts_on=starts_on,
            )
            terms += 1

    expired = expire_lapsed_memberships(today)
    refunds = _seed_refunds(today, ctx["generated_users"])

    ctx["payment_count"] = payments
    ctx["refund_count"] = refunds
    if stdout is not None:
        stdout.write(
            f"  payments: {payments} succeeded payments, {terms} terms, "
            f"{expired} lapsed terms marked expired, {refunds} refunds"
        )
    return ctx
