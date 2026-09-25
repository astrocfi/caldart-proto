"""Seed ~24 months of payments, the terms they bought, some refunds and the mandates.

Every term goes through :func:`apps.members.services.activate_term`, so the
seeded data exercises the same code path as a real checkout.

Each payment carries the fee its provider would have charged and the net that
would have reached CalDART, and is stamped as having had its receipt emailed,
so the finance screens and the exports have real figures to show from the first
run.

The demo books also hold money taken by hand -- a handful of checks -- and a
reconciliation history: every payment older than
:data:`RECONCILED_AFTER_DAYS` has been matched to a statement by the demo
treasurer, so the finance screens open on a realistic mix of matched and
outstanding rows.

A dozen members also have a standing automatic-renewal authority, one of them
paused after a charge and its retries were all refused, so every state the
renewals screens show is on screen with no clicking.
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
    MembershipStatusChoices,
)
from apps.members.services import activate_term, cancel_term, expire_lapsed_memberships
from apps.payments.models import (
    CONTRIBUTION_TIERS,
    MandateProvider,
    MandateStatus,
    Payment,
    PaymentProvider,
    PaymentStatus,
    PaymentWallet,
    Refund,
    RefundReason,
    RefundStatus,
    RenewalAttempt,
    RenewalMandate,
    RenewalOutcome,
)
from apps.payments.providers.mock import DECLINED_LAST4, DECLINED_MESSAGE
from apps.payments.refunds import apply_refund_totals
from apps.payments.renewals import (
    NOTICE_DAYS,
    RETRY_OFFSETS,
)

#: How far back the payment history runs.
HISTORY_MONTHS = 24

#: How many payments the demo treasurer has taken by check.
MANUAL_PAYMENT_COUNT = 8

#: The contribution amounts the seeded checks carry, in cents, cycled through
#: so the demo books hold a spread rather than eight identical rows.
MANUAL_AMOUNTS_CENTS = (2_500, 5_000, 10_000, 25_000)

#: A payment older than this many days has been matched to a bank statement.
#: Anything newer is still outstanding, which is what a treasurer works through.
RECONCILED_AFTER_DAYS = 60

#: How long after the money arrives the treasurer gets to the statement.
RECONCILED_LAG_DAYS = 5

#: How many members hold a standing automatic-renewal authority: ten active, one
#: paused after every retry was refused, and one the member turned off.  The
#: account administrator's contribution-only authority is seeded on top of these.
ACTIVE_MANDATES = 10
PAUSED_MANDATES = 1
CANCELED_MANDATES = 1

#: What the account administrator's standing contribution charges each year.
CONTRIBUTION_MANDATE_CENTS = 5_000

#: How far out that authority's next charge falls, so the walkthrough always has
#: a date a little way off to show.
CONTRIBUTION_MANDATE_DUE_DAYS = 30

#: The saved cards the seeded mandates carry, as a provider would describe them.
#: The saved method each seeded mandate carries, cycled through by index.  A
#: PayPal mandate vaults an account rather than a card, so it carries no card at
#: all: ``(brand, last4, expiry month, expiry year)`` or ``None``.
SEED_CARDS: tuple[tuple[str, tuple[str, str, int, int] | None], ...] = (
    (MandateProvider.STRIPE, ("visa", "4242", 3, 2028)),
    (MandateProvider.STRIPE, ("mastercard", "4444", 11, 2027)),
    (MandateProvider.STRIPE, ("amex", "0005", 7, 2029)),
    (MandateProvider.PAYPAL, None),
)

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


def _manual_payments(ctx: dict[str, Any]) -> int:
    """Record :data:`MANUAL_PAYMENT_COUNT` checks, and return how many there are.

    Each one is a pure contribution from a different seeded member, received on
    a day in the past two years, with the check number in the note.  Keyed on the
    provider reference, so a second seed run finds the rows it made before.
    """
    rng = ctx["rng"]
    today = ctx["today"]
    treasurer = ctx["demo_users"]["treasurer"]
    payers = rng.sample(ctx["users"], MANUAL_PAYMENT_COUNT)

    for index, payer in enumerate(payers):
        amount = MANUAL_AMOUNTS_CENTS[index % len(MANUAL_AMOUNTS_CENTS)]
        received_on = today - timedelta(days=rng.randint(10, HISTORY_MONTHS * 30))
        check_number = 1_000 + index
        payment, created = Payment.objects.get_or_create(
            provider=PaymentProvider.MANUAL,
            provider_ref=str(check_number),
            defaults={
                "user": payer,
                "plan": None,
                "amount_cents": amount,
                "plan_amount_cents": 0,
                "contribution_cents": amount,
                "currency": "usd",
                "wallet": PaymentWallet.CHECK,
                "status": PaymentStatus.SUCCEEDED,
                "received_on": received_on,
                "note": f"Check {check_number}",
                "recorded_by": treasurer,
                "fee_cents": 0,
                "net_cents": amount,
                "raw": {"seeded": True, "provider": PaymentProvider.MANUAL.value},
            },
        )
        if created:
            paid_at = timezone.make_aware(dt.datetime.combine(received_on, dt.time(hour=9)))
            Payment.objects.filter(pk=payment.pk).update(created_at=paid_at, completed_at=paid_at)
    return MANUAL_PAYMENT_COUNT


def _reconcile_settled_payments(ctx: dict[str, Any]) -> int:
    """Match every payment older than :data:`RECONCILED_AFTER_DAYS` to a statement.

    Returns how many rows the demo treasurer has matched.  A payment that is
    already matched is left alone, so a second seed run changes nothing.
    """
    today = ctx["today"]
    treasurer = ctx["demo_users"]["treasurer"]
    cutoff = today - timedelta(days=RECONCILED_AFTER_DAYS)

    matched = 0
    settled = Payment.objects.filter(
        status=PaymentStatus.SUCCEEDED, reconciled_on__isnull=True
    ).only("id", "provider", "completed_at", "received_on")
    for payment in settled:
        paid_on = payment.paid_on
        if paid_on is None or paid_on > cutoff:
            continue
        Payment.objects.filter(pk=payment.pk).update(
            reconciled_on=paid_on + timedelta(days=RECONCILED_LAG_DAYS),
            reconciled_by=treasurer,
        )
        matched += 1
    return matched


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
    manual = _manual_payments(ctx)
    reconciled = _reconcile_settled_payments(ctx)
    refunds = _seed_refunds(today, ctx["generated_users"])
    mandates = _seed_mandates(ctx)

    ctx["payment_count"] = payments + manual
    ctx["manual_payment_count"] = manual
    ctx["refund_count"] = refunds
    ctx["mandate_count"] = mandates
    if stdout is not None:
        stdout.write(
            f"  payments: {payments} succeeded payments, {terms} terms, "
            f"{expired} lapsed terms marked expired, {manual} recorded by hand, "
            f"{reconciled} reconciled, {refunds} refunds, "
            f"{mandates} renewal mandates"
        )
    return ctx


def _card(index: int) -> dict[str, Any]:
    """The saved method the mandate at ``index`` carries, as the provider gave it."""
    provider, card = SEED_CARDS[index % len(SEED_CARDS)]
    if card is None:
        return {
            "provider": provider,
            "method_ref": f"seed_vault_{index}",
            "method_brand": "",
            "method_last4": "",
            "method_exp_month": None,
            "method_exp_year": None,
            "method_label": "PayPal (m***@example.org)",
        }
    brand, last4, month, year = card
    return {
        "provider": provider,
        "customer_ref": f"seed_cus_{index}",
        "method_ref": f"seed_pm_{index}",
        "method_brand": brand,
        "method_last4": last4,
        "method_exp_month": month,
        "method_exp_year": year,
        "method_label": f"{brand.title()} ending {last4}, expires {month:02d}/{year}",
    }


def _mandate_candidates(users: list[User], today: dt.date) -> list[tuple[User, Membership]]:
    """Members with an active term that runs out, and the term a renewal would renew.

    Ordered by expiry, soonest first, so a caller taking an evenly spaced slice
    gets charge dates spread across the coming year.
    """
    found: list[tuple[User, Membership]] = []
    for user in users:
        term = (
            user.memberships.filter(
                status=MembershipStatusChoices.ACTIVE, ends_on__isnull=False, ends_on__gte=today
            )
            .order_by("-ends_on")
            .first()
        )
        if term is not None:
            found.append((user, term))
    return sorted(found, key=lambda pair: (pair[1].ends_on or today, pair[0].pk))


def _seed_mandates(ctx: dict[str, Any]) -> int:
    """Create the demo mandates and their attempts, and return how many there are.

    Ten members renew automatically, one is paused after a charge and all three
    of its retries were refused, and one turned automatic renewal off.  The
    account administrator, a life member, holds a contribution-only authority on
    top of those.  Each active mandate whose charge falls inside the notice
    window already carries a scheduled attempt with its warning sent, which is
    what the daily scan would have left behind.  Running it twice over the same
    database changes nothing.
    """
    rng: random.Random = ctx["rng"]
    today: dt.date = ctx["today"]
    annual: MembershipPlan = ctx["plans"]["annual"]

    wanted = ACTIVE_MANDATES + PAUSED_MANDATES + CANCELED_MANDATES
    eligible = _mandate_candidates(ctx["users"], today)
    # Evenly spaced through the expiry order, so the seeded charge dates spread
    # across the coming year instead of bunching in the next fortnight.
    step = max(len(eligible) // wanted, 1)
    candidates = eligible[::step][:wanted]

    for index, (user, term) in enumerate(candidates):
        contribution = _contribution(rng)
        fields = _card(index)
        if index == ACTIVE_MANDATES:
            fields |= {
                "provider": MandateProvider.MOCK,
                "customer_ref": "",
                "method_ref": "mock",
                "method_brand": "visa",
                "method_last4": DECLINED_LAST4,
                "method_exp_month": 12,
                "method_exp_year": 2030,
                "method_label": f"Test card ending {DECLINED_LAST4}, expires 12/2030",
                "status": MandateStatus.PAUSED,
                "failure_count": len(RETRY_OFFSETS) + 1,
            }
        elif index == ACTIVE_MANDATES + PAUSED_MANDATES:
            fields |= {
                "status": MandateStatus.CANCELED,
                "canceled_at": timezone.now() - timedelta(days=rng.randint(10, 90)),
                "canceled_by": user,
            }
        else:
            fields |= {"status": MandateStatus.ACTIVE}

        mandate, created = RenewalMandate.objects.get_or_create(
            user=user,
            defaults={
                "plan": annual,
                "contribution_cents": contribution,
                "next_charge_on": term.ends_on or today,
                **fields,
            },
        )
        if not created:
            continue
        if mandate.status == MandateStatus.PAUSED:
            _seed_failed_attempts(mandate, term, today)
        elif mandate.status == MandateStatus.ACTIVE:
            _seed_scheduled_attempt(mandate, term, today)

    return len(candidates) + _seed_contribution_mandate(ctx)


def _seed_contribution_mandate(ctx: dict[str, Any]) -> int:
    """Give the account administrator a standing contribution, and count it.

    They are a life member, so their membership never renews; their authority is
    over the contribution alone, and its next charge falls a month out so the
    walkthrough always has a date to show.  Answers ``1``, which is how many such
    authorities it leaves behind whether it created one or found one already there.
    """
    user = ctx["demo_users"]["accountadmin"]
    today: dt.date = ctx["today"]
    RenewalMandate.objects.get_or_create(
        user=user,
        defaults={
            "plan": None,
            "contribution_cents": CONTRIBUTION_MANDATE_CENTS,
            "next_charge_on": today + timedelta(days=CONTRIBUTION_MANDATE_DUE_DAYS),
            "status": MandateStatus.ACTIVE,
            "provider": MandateProvider.MOCK,
            "customer_ref": "",
            "method_ref": "mock",
            "method_brand": "visa",
            "method_last4": "4242",
            "method_exp_month": 12,
            "method_exp_year": 2030,
            "method_label": "Test card ending 4242, expires 12/2030",
        },
    )
    return 1


def _seed_scheduled_attempt(mandate: RenewalMandate, term: Membership, today: dt.date) -> None:
    """Leave a scheduled charge behind when the term is inside the notice window."""
    if term.ends_on is None:
        return
    charge_on = term.ends_on
    if (charge_on - today).days > NOTICE_DAYS:
        return
    RenewalAttempt.objects.create(
        mandate=mandate,
        membership=term,
        scheduled_on=charge_on,
        noticed_at=timezone.now(),
    )


def _seed_failed_attempts(mandate: RenewalMandate, term: Membership, today: dt.date) -> None:
    """The charge and the three retries that all failed, which paused this mandate."""
    if term.ends_on is None:
        return
    day = term.ends_on - timedelta(days=sum(RETRY_OFFSETS))
    previous: RenewalAttempt | None = None
    for offset in (0, *RETRY_OFFSETS):
        day = day + timedelta(days=offset)
        previous = RenewalAttempt.objects.create(
            mandate=mandate,
            membership=term,
            scheduled_on=day,
            retry_of=previous,
            outcome=RenewalOutcome.FAILED,
            error=DECLINED_MESSAGE,
            noticed_at=timezone.now(),
            attempted_at=timezone.now(),
            result_emailed_at=timezone.now(),
        )
