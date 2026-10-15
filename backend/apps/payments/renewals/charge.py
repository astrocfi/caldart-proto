"""The charge step of the renewal scan: each charge that is due, taken exactly once.

:func:`charge` takes one scheduled attempt.  A new charge is claimed, its payment is
written, and the provider is asked to take it off-session, keyed on the payment, so
asking again for the same payment never takes the money twice.  A charge whose
outcome the scan never learned -- an answer lost in transit, a charge the provider
is still settling, a scan that died after claiming it -- keeps its payment, and the
next scan asks the provider about that payment (``find_mandate_charge``) before
charging anything.  A charge the provider may have taken but cannot be asked about
is held *in doubt*: nothing more is charged for it until a treasurer settles it with
:func:`settle_in_doubt`.

Every way an attempt is closed is a conditional update on this scan's own claim, so
a scan that lost its claim to another changes nothing and emails nobody.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import IntegrityError, transaction
from django.db.models import Model, Q
from django.utils import timezone

from apps.accounts.models import AccountKind
from apps.members.models import Membership
from apps.members.services import account_kind
from apps.payments.models import (
    MandateStatus,
    Payment,
    PaymentProvider,
    PaymentStatus,
    RenewalAttempt,
    RenewalMandate,
    RenewalOutcome,
)
from apps.payments.providers.base import (
    PaymentError,
    PaymentInDoubtError,
    PaymentPendingError,
    PaymentUnansweredError,
    ProviderNotConfiguredError,
    ProviderUnavailableError,
    RequestNotSentError,
    get_provider,
)
from apps.payments.providers.mock import MockPaymentsDisabledError
from apps.payments.receipts import SETTLED_STATUSES, receipt_filename, render_receipt_pdf
from apps.payments.renewals.emails import send_mandate_email
from apps.payments.renewals.mandates import roll_charge_date_past
from apps.payments.renewals.schedule import (
    advance_by_cadence,
    charge_date,
    lifetime_term,
    renewal_amount_cents,
    term_to_renew,
)
from apps.payments.services import create_checkout, mark_failed
from caldart import audit, events
from caldart.exceptions import DomainValidationError
from caldart.mail import Attachment
from caldart.reports import PDF_MEDIA_TYPE
from caldart.runs import CHARGE_KIND

if TYPE_CHECKING:
    from apps.payments.renewals.scan import RenewalRun

log = logging.getLogger(__name__)

#: Days after a failed charge that each retry is scheduled for, in order.  When
#: they are exhausted the mandate is paused.
RETRY_OFFSETS: tuple[int, ...] = (1, 3, 7)

#: How long a charge may stay pending at the provider before a treasurer is told.
PENDING_ALERT_DAYS = 3

#: The least ``RENEWAL_STALE_MINUTES`` may be: the systemd unit lets one scan run
#: for 15 minutes, and a claim taken over sooner could still be charging.
MINIMUM_STALE_MINUTES = 15

#: Why a reference is refused for a charge that is not PayPal's.  Only PayPal holds
#: charges in doubt: a Stripe charge is always found by its payment's metadata.
ONLY_PAYPAL_MESSAGE = "Only a PayPal charge is settled by its reference."

#: What a treasurer may answer about a charge held in doubt.
SETTLE_PAID = "paid"
SETTLE_RELEASED = "released"
SETTLE_FAILED = "failed"
SETTLE_OUTCOMES: tuple[str, ...] = (SETTLE_PAID, SETTLE_RELEASED, SETTLE_FAILED)

#: The reason an attempt a treasurer closed as failed records.
CLOSED_BY_TREASURER_MESSAGE = "Closed by the treasurer after checking with the provider."

#: Why the treasurer is told again about a charge still in doubt.
LAPSED_IN_DOUBT_MESSAGE = "The membership has run out while this charge waits to be checked."

#: Why a charge is put off when its provider answered nothing earlier in the run.
BREAKER_MESSAGE = "The provider answered nothing earlier in this run."

#: Why a charge whose payment has already gone through is neither released nor closed.
ALREADY_PAID_MESSAGE = "This charge's payment has already gone through; record it as paid instead."

#: Why an attempt the treasurer is asked to settle is not in doubt.
NOT_IN_DOUBT_MESSAGE = "This charge is not waiting to be checked."


def stale_after() -> timedelta:
    """How old a claim or a portal scan must be before it is taken to have died.

    ``RENEWAL_STALE_MINUTES``, which must be at least :data:`MINIMUM_STALE_MINUTES`;
    a smaller value raises ``ImproperlyConfigured`` naming the setting, so no scan
    starts while one could take over another's charge mid-call.
    """
    minutes = int(settings.RENEWAL_STALE_MINUTES)
    if minutes < MINIMUM_STALE_MINUTES:
        raise ImproperlyConfigured(
            f"RENEWAL_STALE_MINUTES must be at least {MINIMUM_STALE_MINUTES}, not {minutes}."
        )
    return timedelta(minutes=minutes)


def charges_in_doubt() -> int:
    """How many scheduled charges are held in doubt, waiting for a treasurer."""
    return RenewalAttempt.objects.filter(outcome=RenewalOutcome.SCHEDULED, in_doubt=True).count()


def due_attempts(today: date) -> list[RenewalAttempt]:
    """Every scheduled attempt due on ``today`` or earlier, oldest first."""
    return list(
        RenewalAttempt.objects.filter(outcome=RenewalOutcome.SCHEDULED, scheduled_on__lte=today)
        .select_related("mandate", "mandate__user", "mandate__plan", "membership")
        .order_by("scheduled_on", "pk")
    )


def schedule_attempt(
    mandate: RenewalMandate,
    term: Membership | None,
    charge_on: date,
    *,
    retry_of: RenewalAttempt | None = None,
) -> RenewalAttempt | None:
    """Write the mandate's one scheduled charge, or ``None`` when another scan has.

    ``renewal_attempt_one_scheduled_per_mandate`` allows a mandate one charge
    waiting at a time.  Two scans running at once -- the timer and a system
    administrator pressing "Run now" -- can both find none waiting and both try to
    write one; the second write is refused, and that scan leaves the charge, its
    notice, and its taking to the scan that wrote it.  A charge held in doubt is
    also the one waiting, so nothing new is written beside it until a treasurer has
    settled it, and the refusal says so.  A retry carries the notice time of the
    attempt it retries.
    """
    try:
        with transaction.atomic():
            return RenewalAttempt.objects.create(
                mandate=mandate,
                membership=term,
                scheduled_on=charge_on,
                retry_of=retry_of,
                noticed_at=retry_of.noticed_at if retry_of is not None else None,
            )
    except IntegrityError:
        waiting = RenewalAttempt.objects.filter(mandate=mandate, outcome=RenewalOutcome.SCHEDULED)
        if waiting.filter(in_doubt=True).exists():
            log.warning(
                "mandate %s has a charge waiting to be checked; nothing new is scheduled",
                mandate.pk,
            )
        else:
            log.info("mandate %s already has a charge scheduled by another scan", mandate.pk)
        return None


def charge(attempt: RenewalAttempt, today: date, run: RenewalRun, *, dry_run: bool) -> None:
    """Take one scheduled renewal, and record what the provider said.

    An attempt held in doubt is skipped as ``in_doubt``: it waits for a treasurer
    (:func:`_wait_in_doubt`), unless its payment has succeeded in the meantime,
    when it is settled as any charge is.  An attempt that already carries a payment
    has been sent to the provider before without the outcome being recorded, and
    is settled by :func:`_resume` rather than charged afresh.
    """
    if attempt.in_doubt and not _paid_meanwhile(attempt, dry_run=dry_run):
        _wait_in_doubt(attempt, today, run, dry_run=dry_run)
        return
    mandate = attempt.mandate
    if attempt.payment_id is None or dry_run:
        skip = _skip_reason(attempt, today)
        if skip is not None:
            _skip(attempt, skip, run, dry_run=dry_run)
            return

    amount_cents = renewal_amount_cents(mandate)
    if dry_run:
        run.charged += 1
        run.record_action(CHARGE_KIND, mandate, on=attempt.scheduled_on, amount_cents=amount_cents)
        # A rehearsal cannot ask the provider whether the charge would be taken,
        # so it reports the message a charge that succeeds sends.  It carries no
        # date: the charge that has not happened is what sets the one after it.
        run.record_action("renewal_charged", mandate)
        return
    if not _claim(attempt):
        run.record_skipped("in_flight")
        return
    if attempt.in_doubt and not _paid_meanwhile(attempt, dry_run=False):
        # Another scan put it in doubt between this scan's read and its claim.
        _release(attempt)
        run.record_skipped("in_doubt")
        return
    if attempt.payment_id is not None:
        _resume(attempt, today, run)
        return

    run.record_action(CHARGE_KIND, mandate, on=attempt.scheduled_on, amount_cents=amount_cents)
    try:
        # The payment and the attempt that owns it are written together, so a scan
        # that dies here leaves either both or neither for the next scan to find.
        with transaction.atomic():
            payment = create_checkout(
                mandate.user,
                mandate.plan.slug if mandate.plan is not None else None,
                mandate.contribution_cents,
                mandate.provider,
            )
            attempt.payment = payment
            attempt.save(update_fields=["payment", "updated_at"])
    except DomainValidationError as exc:
        log.error("renewal for mandate %s could not be priced: %s", mandate.pk, exc)
        run.record_skipped("no_plan")
        _finish(attempt, RenewalOutcome.SKIPPED)
        return

    _take(attempt, payment, today, run, fresh=True)


def _paid_meanwhile(attempt: RenewalAttempt, *, dry_run: bool) -> bool:
    """Whether an attempt in doubt has had its payment succeed since, and is let go.

    A payment that succeeded -- recorded from the provider's own notification, or
    by a settle that stopped before it reached the attempt -- answers the doubt.
    In a live run the attempt's ``in_doubt`` is cleared, so it is settled as any
    charge is; a rehearsal changes nothing and keeps reading it as in doubt.
    """
    if dry_run or attempt.payment_id is None:
        return False
    if not Payment.objects.filter(pk=attempt.payment_id, status=PaymentStatus.SUCCEEDED).exists():
        return False
    RenewalAttempt.objects.filter(pk=attempt.pk).update(in_doubt=False)
    attempt.in_doubt = False
    return True


def _wait_in_doubt(attempt: RenewalAttempt, today: date, run: RenewalRun, *, dry_run: bool) -> None:
    """Skip an attempt held in doubt, telling the treasurer again once its term ran out.

    The charge waits for a treasurer whatever happens; a renewal whose member's
    term has ended since the treasurer was last told is flagged again, once, so
    the lapse is never silent.
    """
    run.record_skipped("in_doubt")
    if dry_run:
        return
    term = attempt.membership
    if term is None or term.ends_on is None or today <= term.ends_on:
        return
    flagged_at = attempt.flagged_at
    if flagged_at is not None and timezone.localdate(flagged_at) > term.ends_on:
        return
    payment = Payment.objects.get(renewal_attempts=attempt)
    _flag(attempt, payment, LAPSED_IN_DOUBT_MESSAGE, previous=flagged_at)


def settle_in_doubt(
    attempt_id: int,
    *,
    outcome: str,
    reference: str = "",
    actor: Model,
    defer: Callable[[Callable[[], None]], None] | None = None,
) -> RenewalAttempt:
    """Settle the attempt ``attempt_id`` held in doubt, as a treasurer checked it.

    The attempt and its payment are locked for the whole of it, so two treasurers
    settling at once settle it once.  A payment that has already gone through can
    only be recorded as paid: ``released`` and ``failed`` are refused for it.
    ``outcome`` is one of :data:`SETTLE_OUTCOMES`:

    * ``paid``: ``reference`` is the provider's id for the charge it took, such as a
      PayPal capture id.  The provider confirms it belongs to this payment and the
      payment succeeds from it (``record_charge_reference``); the attempt is then
      settled at once, as the scan settles one -- the term renewed and the member
      emailed.  ``defer``, when given, is handed that email to send later, so a slow
      mail server never holds the request up.
    * ``released``: the provider didn't take anything.  The hold is lifted and the next
      scan charges the same payment again, under the same ``invoice_id``.
    * ``failed``: neither is right.  The attempt is closed as failed without a
      charge, the payment is marked failed, and an active mandate is paused, raising
      ``auto_renewal_off`` with ``how="administrator"``, and the ordinary renewal
      reminders take over.  The member of a mandate paused this way is emailed
      ``renewal_failed`` with ``closed`` set (:func:`_closed_email`), once the
      transaction has committed: it goes to ``defer`` when given, as the ``paid``
      email does, and is otherwise queued with ``transaction.on_commit``.  A mandate
      that was not active is left as it is, and the member isn't emailed.

    Every outcome clears ``flagged_at``, so a charge held in doubt again later is
    flagged again, and writes one ``renewal.settle`` audit record naming ``actor``,
    with the attempt, the payment, the outcome, and any reference.  Returns the
    attempt as it stands afterwards.

    Raises ``DomainValidationError`` keyed by ``attempt`` when the attempt is not in
    doubt, keyed by ``outcome`` when ``released`` or ``failed`` is asked of a payment
    that has already gone through, and keyed by ``reference`` when a reference is
    given for a charge that is not PayPal's, and lets the provider's
    ``PaymentError`` propagate when it will not confirm ``reference``, leaving the
    attempt in doubt.
    """
    with transaction.atomic():
        attempt = (
            RenewalAttempt.objects.select_for_update(of=("self",))
            .select_related("mandate", "mandate__user", "mandate__plan", "membership")
            .get(pk=attempt_id)
        )
        if not attempt.in_doubt or attempt.outcome != RenewalOutcome.SCHEDULED:
            raise DomainValidationError("attempt", NOT_IN_DOUBT_MESSAGE)
        payment = Payment.objects.select_for_update(of=("self",)).get(renewal_attempts=attempt)
        if outcome != SETTLE_PAID and payment.status in SETTLED_STATUSES:
            raise DomainValidationError("outcome", ALREADY_PAID_MESSAGE)
        if outcome == SETTLE_PAID and payment.provider != PaymentProvider.PAYPAL:
            raise DomainValidationError("reference", ONLY_PAYPAL_MESSAGE)
        if outcome == SETTLE_PAID:
            get_provider(payment.provider).record_charge_reference(payment, reference)
        elif outcome == SETTLE_RELEASED:
            payment.charge_sent_at = None
            payment.save(update_fields=["charge_sent_at", "updated_at"])
        attempt.in_doubt = False
        attempt.flagged_at = None
        attempt.attempted_at = None
        attempt.error = CLOSED_BY_TREASURER_MESSAGE if outcome == SETTLE_FAILED else ""
        if outcome == SETTLE_FAILED:
            attempt.outcome = RenewalOutcome.FAILED
        attempt.save(
            update_fields=[
                "in_doubt",
                "flagged_at",
                "attempted_at",
                "error",
                "outcome",
                "updated_at",
            ]
        )
        if outcome == SETTLE_FAILED and _close_unpaid(attempt, payment):
            deliver = _closed_email(attempt)
            if defer is None:
                transaction.on_commit(deliver)
            else:
                defer(deliver)
        audit.record(
            audit.RENEWAL_SETTLE,
            actor=actor,
            target=attempt.mandate.user,
            attempt=attempt.pk,
            payment=payment.pk,
            outcome=outcome,
            reference=audit.safe_slug(reference) if reference else "",
        )
        if outcome == SETTLE_PAID:
            # Inline: the scan imports this module, and the run is the scan's own.
            from apps.payments.renewals.scan import RenewalRun

            today = timezone.localdate()
            charge(
                attempt, today, RenewalRun(today=today, dry_run=False, defer=defer), dry_run=False
            )
    attempt.refresh_from_db()
    return attempt


def _close_unpaid(attempt: RenewalAttempt, payment: Payment) -> bool:
    """Fail the payment of an attempt a treasurer closed, and say whether it paused one.

    The member isn't charged for the term automatically: an active mandate is paused
    and raises ``auto_renewal_off`` with ``how="administrator"``, and the member's
    renewal reminders take over.  Returns ``True`` when the mandate was paused here,
    and ``False`` for one that was not active, which is left as it is.
    """
    if payment.status != PaymentStatus.SUCCEEDED:
        mark_failed(payment, {"error": CLOSED_BY_TREASURER_MESSAGE})
    mandate = attempt.mandate
    if mandate.status != MandateStatus.ACTIVE:
        return False
    mandate.status = MandateStatus.PAUSED
    mandate.save(update_fields=["status", "updated_at"])
    events.emit("auto_renewal_off", mandate=mandate, how="administrator")
    return True


def _closed_email(attempt: RenewalAttempt) -> Callable[[], None]:
    """The email telling a member that a charge a treasurer closed paused their mandate.

    The returned function sends ``renewal_failed`` with ``closed`` set, worded by the
    mandate's kind like every renewal email: the charge couldn't be completed, the
    mandate is paused so the member isn't charged automatically, and where to pay by
    hand and turn it back on.  A renewal's email also names ``expires_on``, the day
    the term the charge was for ends, with ``has_ended`` true once that day has gone
    by; both are left out for a recurring donation and for a charge that doesn't name
    a term.  The
    send stamps the attempt's ``result_emailed_at``; a mail server that refuses it is
    logged by :func:`send_mandate_email`, and the settlement stands.
    """
    mandate = attempt.mandate
    term = attempt.membership
    expires_on = term.ends_on if term is not None and mandate.plan_id is not None else None
    has_ended = expires_on is not None and expires_on < timezone.localdate()

    def deliver() -> None:
        """Email the member that their mandate is paused, and stamp that it went."""
        if not send_mandate_email(
            mandate,
            "renewal_failed",
            closed=True,
            next_on=None,
            expires_on=expires_on,
            has_ended=has_ended,
        ):
            return
        RenewalAttempt.objects.filter(pk=attempt.pk).update(result_emailed_at=timezone.now())

    return deliver


def _take(
    attempt: RenewalAttempt, payment: Payment, today: date, run: RenewalRun, *, fresh: bool
) -> None:
    """Ask the payment's provider to charge ``payment``, and record what it said.

    The first time a payment is sent, the customer and the method it is sent for are
    stamped on it with the time (``charge_customer_ref``, ``charge_method_ref``,
    ``charge_sent_at``), so every later try and lookup uses those, whatever has
    happened to the mandate since.  ``fresh`` says the payment was written by this
    scan and has never been sent, so a provider that was never asked -- one not
    configured or switched off, or one the request certainly never reached -- leaves
    nothing behind worth keeping.  A provider that answered nothing earlier in the
    same run is not asked at all: the charge is put off before anything is stamped.
    """
    mandate = attempt.mandate
    if payment.provider in run.unanswered:
        # The provider answered nothing earlier in this run: sending more would only
        # leave more charges in doubt, so this one waits for the next run unsent.
        _postpone(attempt, payment, BREAKER_MESSAGE, run, discard=fresh)
        return
    stamped = payment.charge_sent_at is None
    if stamped:
        payment.charge_sent_at = timezone.now()
        payment.charge_customer_ref = payment.charge_customer_ref or mandate.customer_ref
        payment.charge_method_ref = payment.charge_method_ref or mandate.method_ref
        payment.save(
            update_fields=[
                "charge_sent_at",
                "charge_customer_ref",
                "charge_method_ref",
                "updated_at",
            ]
        )
    try:
        get_provider(payment.provider).charge_mandate(mandate, payment)
    except (ProviderNotConfiguredError, MockPaymentsDisabledError, RequestNotSentError) as exc:
        if stamped and not fresh:
            # Nothing reached the provider, so the payment was not sent after all.
            payment.charge_sent_at = None
            payment.save(update_fields=["charge_sent_at", "updated_at"])
        _postpone(attempt, payment, str(exc), run, discard=fresh)
        return
    except ProviderUnavailableError as exc:
        _postpone(attempt, payment, str(exc), run, discard=False)
        return
    except PaymentPendingError:
        _hold(attempt, payment, run)
        return
    except PaymentInDoubtError as exc:
        if isinstance(exc, PaymentUnansweredError):
            run.unanswered.add(payment.provider)
        _doubt(attempt, payment, str(exc), run)
        return
    except PaymentError as exc:
        _record_failure(attempt, payment, str(exc), today, run)
        return

    _record_success(attempt, run)


def _resume(attempt: RenewalAttempt, today: date, run: RenewalRun) -> None:
    """Settle a claimed attempt whose payment was sent to the provider before.

    That is a charge whose answer never arrived (a timeout), one the provider was
    still processing, and one a scan claimed and then died over.  The provider asked
    is the payment's own, whatever the mandate has been switched to since.  A payment
    the provider's webhook has already marked succeeded is recorded as the charge.
    Otherwise the provider is asked for the charge it made for this payment
    (``find_mandate_charge``), and what it found is recorded: a success, a decline, a
    charge still settling, or one in doubt.  Only when it doesn't hold a charge at all
    is the payment charged, under the same payment and so the same idempotency key --
    unless the attempt should no longer be charged, in which case the payment is
    thrown away and the attempt skipped.  This is reached whatever the mandate's
    status, so a charge taken just before the member turned renewal off is still
    recorded.
    """
    mandate = attempt.mandate
    payment = Payment.objects.get(renewal_attempts=attempt)
    attempt.payment = payment
    if payment.status != PaymentStatus.SUCCEEDED:
        try:
            found = get_provider(payment.provider).find_mandate_charge(mandate, payment)
        except (
            ProviderUnavailableError,
            ProviderNotConfiguredError,
            MockPaymentsDisabledError,
        ) as exc:
            _postpone(attempt, payment, str(exc), run, discard=False)
            return
        except PaymentPendingError:
            _hold(attempt, payment, run)
            return
        except PaymentInDoubtError as exc:
            _doubt(attempt, payment, str(exc), run)
            return
        except PaymentError as exc:
            _record_charge(attempt, payment, run)
            _record_failure(attempt, payment, str(exc), today, run)
            return
        if not found:
            skip = _skip_reason(attempt, today)
            if skip is not None:
                attempt.payment = None
                attempt.save(update_fields=["payment", "updated_at"])
                payment.delete()
                _skip(attempt, skip, run, dry_run=False)
                return
            _record_charge(attempt, payment, run)
            _take(attempt, payment, today, run, fresh=False)
            return
        payment.refresh_from_db()
    _record_charge(attempt, payment, run)
    _record_success(attempt, run)


def _record_charge(attempt: RenewalAttempt, payment: Payment, run: RenewalRun) -> None:
    """Name the charge a resumed attempt takes, or took, in the run's actions."""
    run.record_action(
        CHARGE_KIND, attempt.mandate, on=attempt.scheduled_on, amount_cents=payment.amount_cents
    )


def _skip_reason(attempt: RenewalAttempt, today: date) -> str | None:
    """Why an attempt should not be charged, or ``None``.

    ``not_active`` when its mandate is no longer active; otherwise whatever
    :func:`_renewal_skip_reason` says.
    """
    if attempt.mandate.status != MandateStatus.ACTIVE:
        return "not_active"
    return _renewal_skip_reason(attempt, today)


def _skip(attempt: RenewalAttempt, reason: str, run: RenewalRun, *, dry_run: bool) -> None:
    """Count an attempt skipped for ``reason`` and, in a live run, close it unpaid.

    An attempt skipped as ``already_renewed`` also moves the stored charge date
    past the coverage that arrived from somewhere else, rather than leaving it to
    wait a year where it is.
    """
    run.record_skipped(reason)
    if dry_run:
        return
    _finish(attempt, RenewalOutcome.SKIPPED)
    if reason == "already_renewed" and attempt.membership is not None:
        roll_charge_date_past(attempt.mandate.user, covered_until=attempt.membership.ends_on)


def _renewal_skip_reason(attempt: RenewalAttempt, today: date) -> str | None:
    """Why a renewal's attempt should not be charged after all, or ``None``.

    ``friend`` when the member has become a friend of CalDART, who pays no dues;
    ``lifetime`` when they have been granted a lifetime term since the attempt was
    written; ``already_renewed`` when their coverage has already moved past the
    term the charge was for.  A recurring donation is never skipped for any of
    these: it charges whatever the giver's membership.  It is skipped as
    ``already_charged`` when its next charge, read afresh, already lies beyond the
    day the attempt was for, which is what a second attempt for a day another scan
    has already charged looks like.  A retry is dated after that next charge, so it
    is never skipped this way.
    """
    mandate = attempt.mandate
    if mandate.plan_id is None:
        next_charge_on = (
            RenewalMandate.objects.filter(pk=mandate.pk)
            .values_list("next_charge_on", flat=True)
            .get()
        )
        if next_charge_on > attempt.scheduled_on:
            return "already_charged"
        return None
    if account_kind(mandate.user, today) == AccountKind.FRIEND:
        return "friend"
    if lifetime_term(mandate.user) is not None:
        return "lifetime"
    if _already_renewed(attempt, today):
        return "already_renewed"
    return None


def _claim(attempt: RenewalAttempt) -> bool:
    """Take an attempt for this run, and say whether this run got it.

    The claim is a single conditional update: the attempt is stamped
    ``attempted_at`` only while it is still ``scheduled`` and unstamped, so of two
    scans running at once -- the timer and a system administrator pressing "Run
    now" -- exactly one charges, and the other finds nothing to do.

    A stamp older than ``RENEWAL_STALE_MINUTES`` (:func:`stale_after`) is a claim
    whose scan died before it recorded anything, and is taken over by the same
    update, so the attempt is settled rather than left claimed for ever.  The
    attempt's payment and its doubt are read again with the claim, since the scan
    that died may have written them.
    """
    now = timezone.now()
    stale_before = now - stale_after()
    claimed = (
        RenewalAttempt.objects.filter(pk=attempt.pk, outcome=RenewalOutcome.SCHEDULED)
        .filter(Q(attempted_at__isnull=True) | Q(attempted_at__lt=stale_before))
        .update(attempted_at=now, updated_at=now)
    )
    if claimed == 0:
        return False
    if attempt.attempted_at is not None:
        log.warning(
            "renewal attempt %s was claimed at %s and never settled; taking it up",
            attempt.pk,
            attempt.attempted_at.isoformat(),
        )
    attempt.refresh_from_db(fields=["attempted_at", "payment", "in_doubt", "updated_at"])
    return True


def _release(attempt: RenewalAttempt, **fields: object) -> bool:
    """Give up this scan's claim, writing ``fields`` with it, and say whether it held it.

    A conditional update on the claim's own stamp, so a scan whose claim another
    took over writes nothing.
    """
    now = timezone.now()
    released = RenewalAttempt.objects.filter(
        pk=attempt.pk, outcome=RenewalOutcome.SCHEDULED, attempted_at=attempt.attempted_at
    ).update(attempted_at=None, updated_at=now, **fields)
    if released == 0:
        log.warning("renewal attempt %s was taken over by another scan", attempt.pk)
        return False
    attempt.attempted_at = None
    for name, value in fields.items():
        setattr(attempt, name, value)
    return True


def _close(attempt: RenewalAttempt, outcome: str, *, error: str = "") -> bool:
    """Close a claimed attempt with ``outcome``, and say whether this scan did.

    A conditional update on the claim's own stamp: a scan whose claim another scan
    took over closes nothing, and its caller then changes no mandate and emails
    nobody, so a charge is never recorded twice.
    """
    closed = RenewalAttempt.objects.filter(
        pk=attempt.pk, outcome=RenewalOutcome.SCHEDULED, attempted_at=attempt.attempted_at
    ).update(outcome=outcome, error=error, updated_at=timezone.now())
    if closed == 0:
        log.warning("renewal attempt %s was settled by another scan", attempt.pk)
        return False
    attempt.outcome = outcome
    attempt.error = error
    return True


def _postpone(
    attempt: RenewalAttempt, payment: Payment, reason: str, run: RenewalRun, *, discard: bool
) -> None:
    """Put a charge back whose outcome the provider did not tell us.

    A provider that cannot be reached, that is not configured, or that is switched
    off -- the mock provider with ``PAYMENTS_MOCK_ENABLED`` off -- says nothing
    about the member's card, so it costs no rung of the retry ladder, sends no
    decline notice and does not pause the mandate.  The attempt is released, still
    scheduled for the same day, so the next scan tries it again.

    A provider that could not be reached may still have made the charge, so the
    pending payment stays on the attempt: the next scan asks the provider about
    that payment before charging it, under the same idempotency key.  ``discard``
    throws the payment away instead, which is right only for one this scan wrote
    and no provider was ever asked to take.
    """
    log.error(
        "renewal attempt %s could not charge through %s: %s", attempt.pk, payment.provider, reason
    )
    if discard:
        if _release(attempt, payment=None):
            payment.delete()
    else:
        _release(attempt)
    run.record_skipped("provider_down")


def _hold(attempt: RenewalAttempt, payment: Payment, run: RenewalRun) -> None:
    """Release an attempt whose charge the provider is still settling.

    The charge is neither taken nor refused yet, so nothing is emailed and no rung
    of the retry ladder is spent.  The payment stays on the attempt, still pending,
    and the claim is released: the provider's webhook may settle the payment, and
    the next scan records the attempt from it, or asks the provider again.  A charge
    the provider has held for more than :data:`PENDING_ALERT_DAYS` is logged at
    ERROR and flagged to the treasurer once (:func:`_flag`).
    """
    log.info(
        "renewal attempt %s: %s is still settling payment %s",
        attempt.pk,
        payment.provider,
        payment.pk,
    )
    sent_at = payment.charge_sent_at
    if sent_at is not None and timezone.now() - sent_at > timedelta(days=PENDING_ALERT_DAYS):
        log.error(
            "renewal payment %s has been pending at %s for more than %s days",
            payment.pk,
            payment.provider,
            PENDING_ALERT_DAYS,
        )
        _flag(attempt, payment, f"Pending at the provider for more than {PENDING_ALERT_DAYS} days.")
    _release(attempt)
    run.record_skipped("pending")


def _doubt(attempt: RenewalAttempt, payment: Payment, reason: str, run: RenewalRun) -> None:
    """Hold an attempt in doubt: the provider may have taken it and cannot say.

    Charging again could take the money twice, so the attempt is released with
    ``in_doubt`` set and ``reason`` kept as its ``error``; every later scan skips it
    as ``in_doubt`` until a treasurer settles it (:func:`settle_in_doubt`).  The
    payment stays pending.  Logged at ERROR, and flagged to the treasurer once.
    Nothing is emailed to the member.
    """
    log.error(
        "renewal attempt %s (payment %s at %s) is in doubt and waits for a treasurer: %s",
        attempt.pk,
        payment.pk,
        payment.provider,
        reason,
    )
    if _release(attempt, in_doubt=True, error=reason[:255]):
        _flag(attempt, payment, reason)
    run.record_skipped("in_doubt")


def _flag(
    attempt: RenewalAttempt, payment: Payment, reason: str, *, previous: datetime | None = None
) -> None:
    """Tell the treasurer, once, that ``attempt``'s charge needs checking.

    Raises the ``renewal_needs_checking`` event with the attempt, its payment and
    ``reason``, and stamps ``flagged_at``.  It flags only while ``flagged_at`` is
    still ``previous`` -- unset, unless the caller is flagging again on purpose --
    so of two scans only one tells the treasurer.
    """
    still = Q(flagged_at__isnull=True) if previous is None else Q(flagged_at=previous)
    now = timezone.now()
    flagged = RenewalAttempt.objects.filter(still, pk=attempt.pk).update(flagged_at=now)
    if flagged == 0:
        return
    attempt.flagged_at = now
    events.emit("renewal_needs_checking", attempt=attempt, payment=payment, reason=reason)


def _already_renewed(attempt: RenewalAttempt, today: date) -> bool:
    """Whether the member's coverage already reaches past the term being renewed.

    True when another term has been bought or granted since the attempt was
    scheduled, which is what a member paying by hand in the meantime looks like.
    Always false for a recurring donation, which renews no term and so can never be
    overtaken by one.
    """
    if attempt.mandate.plan_id is None or attempt.membership is None:
        return False
    term = term_to_renew(attempt.mandate.user, today)
    if term is None or term.ends_on is None or attempt.membership.ends_on is None:
        return False
    return term.ends_on > attempt.membership.ends_on


def _finish(attempt: RenewalAttempt, outcome: str) -> None:
    """Close an attempt with ``outcome`` and no charge."""
    attempt.outcome = outcome
    attempt.save(update_fields=["outcome", "updated_at"])


def _record_success(attempt: RenewalAttempt, run: RenewalRun) -> None:
    """Mark the attempt succeeded, roll the charge date forward, and tell the member.

    The attempt is closed first, on this scan's claim (:func:`_close`); a scan that
    no longer holds the claim does nothing more.  The member's email goes out at
    once, or is handed to the run's ``defer`` to send later when the run has one.
    The mandate's stored charge date then moves on: to the ``ends_on`` of the term
    the charge bought for a renewal, and by the mandate's cadence from the day the
    charge was scheduled for a recurring donation, which renews no term.
    """
    if not _close(attempt, RenewalOutcome.SUCCEEDED):
        return
    mandate = attempt.mandate
    now = timezone.now()
    today = timezone.localdate()

    renewed = term_to_renew(mandate.user, today)
    mandate.failure_count = 0
    mandate.last_charged_at = now
    if mandate.plan_id is None:
        mandate.next_charge_on = advance_by_cadence(attempt.scheduled_on, mandate.cadence)
    elif renewed is not None and renewed.ends_on is not None:
        mandate.next_charge_on = renewed.ends_on
    mandate.save(update_fields=["failure_count", "last_charged_at", "next_charge_on", "updated_at"])

    charge_on = charge_date(mandate, today)
    payment = attempt.payment
    expires_on = renewed.ends_on if renewed is not None and mandate.plan_id else None

    def deliver() -> None:
        """Email the member the charge with its receipt, and stamp that it went."""
        attachments: list[Attachment] = []
        if payment is not None:
            receipt = (receipt_filename(payment), render_receipt_pdf(payment), PDF_MEDIA_TYPE)
            attachments.append(receipt)
        if not send_mandate_email(
            mandate,
            "renewal_charged",
            expires_on=expires_on,
            next_charge_on=charge_on,
            receipt_number=payment.receipt_number if payment is not None else "",
            attachments=attachments,
        ):
            return
        sent_at = timezone.now()
        RenewalAttempt.objects.filter(pk=attempt.pk).update(result_emailed_at=sent_at)
        attempt.result_emailed_at = sent_at
        if payment is not None:
            Payment.objects.filter(pk=payment.pk).update(receipt_sent_at=sent_at)
            payment.receipt_sent_at = sent_at

    if run.defer is None:
        deliver()
    else:
        run.defer(deliver)
    run.record_action("renewal_charged", mandate, on=charge_on)
    run.charged += 1


def _record_failure(
    attempt: RenewalAttempt, payment: Payment, reason: str, today: date, run: RenewalRun
) -> None:
    """Record a declined charge, then retry it or pause the mandate.

    The attempt is closed first, on this scan's claim (:func:`_close`); a scan that
    no longer holds the claim does nothing more.  The provider's reason is kept on
    the attempt and quoted to the member.  A mandate with retries left gets the next
    one from :data:`RETRY_OFFSETS`; one whose retries are exhausted is paused, and
    the member is told that automatic renewal is off and the ordinary reminders
    resume.  Every decline raises the ``auto_renewal_declined`` event with the
    mandate, the ``reason``, and ``next_on``, the day of the retry or ``None`` once
    the mandate is paused.  A mandate that is no longer active -- turned off while
    its charge was in doubt -- is left as it is, and nobody is emailed.
    """
    if not _close(attempt, RenewalOutcome.FAILED, error=reason[:255]):
        return
    mandate = attempt.mandate
    if payment.status != PaymentStatus.SUCCEEDED:
        mark_failed(payment, {"error": reason})
    run.failed += 1
    if mandate.status != MandateStatus.ACTIVE:
        return

    mandate.failure_count += 1
    retries_left = mandate.failure_count <= len(RETRY_OFFSETS)
    next_on = (
        today + timedelta(days=RETRY_OFFSETS[mandate.failure_count - 1]) if retries_left else None
    )
    if not retries_left:
        mandate.status = MandateStatus.PAUSED
        run.paused += 1
    mandate.save(update_fields=["failure_count", "status", "updated_at"])

    events.emit("auto_renewal_declined", mandate=mandate, reason=attempt.error, next_on=next_on)
    run.record_action("renewal_failed", mandate, on=next_on, detail=attempt.error)
    if send_mandate_email(mandate, "renewal_failed", error=attempt.error, next_on=next_on):
        attempt.result_emailed_at = timezone.now()
        attempt.save(update_fields=["result_emailed_at", "updated_at"])

    if next_on is not None:
        schedule_attempt(mandate, attempt.membership, next_on, retry_of=attempt)
