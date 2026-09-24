"""Seed ~24 months of succeeded payments and the terms they bought.

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
from apps.members.models import MembershipPlan, MembershipSource
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

#: What each provider charges, as the rate in thousandths and the fixed part in
#: cents: Stripe 2.9% + 30 cents, PayPal 3.49% + 49 cents.  A provider nobody
#: lists here takes nothing, which is what a payment recorded by hand costs.
PROVIDER_FEES: dict[str, tuple[int, int]] = {
    PaymentProvider.STRIPE: (29, 30),
    PaymentProvider.PAYPAL: (35, 49),
}


def _fee_cents(provider: str, amount_cents: int) -> int:
    """The fee ``provider`` would have charged on ``amount_cents``.

    The percentage is rounded half up to the cent, as a processor rounds it.
    A provider with no published rate -- a check, say -- costs nothing.
    """
    if provider not in PROVIDER_FEES:
        return 0
    rate, fixed = PROVIDER_FEES[provider]
    return (amount_cents * rate + 500) // 1_000 + fixed


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

    fee = _fee_cents(provider, amount)
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

    ctx["payment_count"] = payments
    if stdout is not None:
        stdout.write(
            f"  payments: {payments} succeeded payments, {terms} terms, "
            f"{expired} lapsed terms marked expired"
        )
    return ctx
