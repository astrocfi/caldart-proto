"""Seed ~24 months of succeeded payments and the terms they bought.

Every term goes through :func:`apps.members.services.activate_term`, so the
seeded data exercises the same code path as a real checkout.
"""

from __future__ import annotations

import datetime as dt
from datetime import timedelta

from django.utils import timezone

from apps.members.models import MembershipSource
from apps.members.services import activate_term, expire_lapsed_memberships
from apps.payments.models import (
    CONTRIBUTION_TIERS,
    Payment,
    PaymentProvider,
    PaymentStatus,
    PaymentWallet,
)

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


def _pick(rng, mix: tuple[tuple[str, int], ...]) -> str:
    values = [v for v, _ in mix]
    weights = [w for _, w in mix]
    return rng.choices(values, weights=weights)[0]


def _contribution(rng) -> int:
    if rng.random() < 0.62:
        return 0
    tier = rng.choice([t for t in CONTRIBUTION_TIERS if t["cents"]])
    if rng.random() < 0.15:  # "other amount"
        return rng.randrange(500, 25_000, 500)
    return tier["cents"]


def _term_starts(rng, target: str, today: dt.date) -> list[dt.date]:
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


def _payment_for(user, plan, starts_on, index, rng, today) -> Payment:
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
            "raw": {"seeded": True, "provider": provider},
        },
    )
    if created:
        # ``created_at`` is auto_now_add, so backdate it with an UPDATE.
        Payment.objects.filter(pk=payment.pk).update(created_at=paid_at, completed_at=paid_at)
        payment.refresh_from_db()
    return payment


def run(ctx: dict, stdout=None) -> dict:
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

    ctx["payment_count"] = payments
    if stdout is not None:
        stdout.write(
            f"  payments: {payments} succeeded payments, {terms} terms, "
            f"{expired} lapsed terms marked expired"
        )
    return ctx
