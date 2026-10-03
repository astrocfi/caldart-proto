"""The daily scan that announces and takes every scheduled charge.

:func:`run_auto_renewals` is the one entry point the management command, ``POST
/system/renewals/run`` and the systemd timer all call.  It does three things,
in this order, for every mandate that is ``active``:

1. **Notice.**  A yearly mandate whose stored ``next_charge_on`` falls within
   :data:`NOTICE_DAYS` gets a :class:`~apps.payments.models.RenewalAttempt`
   scheduled for that day, and the member is emailed the amount, the date and how
   to turn it off.  A monthly or quarterly donation is written its attempt on the
   day of the charge, and sends no notice: its charged email is the one message.
2. **Card expiry.**  A card that expires before that charge earns one warning.
3. **Charge.**  Every attempt due today or earlier is charged off-session.  A
   success activates the next term and emails the member; a decline records the
   provider's reason, emails it, and schedules the next retry from
   :data:`RETRY_OFFSETS` -- or, once those are exhausted, pauses the mandate and
   hands the member back to the ordinary renewal reminders.

Every email is keyed on a timestamp of the attempt it belongs to, so a scan run
twice in one day sends nothing twice.  A dry run changes no mandate, sends no
email and charges nobody; the run itself is still recorded in the audit log.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import Model
from django.utils import timezone

from apps.accounts.models import AccountKind
from apps.members.models import Membership
from apps.members.services import account_kind
from apps.payments.models import (
    MandateCadence,
    MandateStatus,
    Payment,
    PaymentStatus,
    RenewalAttempt,
    RenewalMandate,
    RenewalOutcome,
)
from apps.payments.providers.base import (
    PaymentError,
    ProviderNotConfiguredError,
    ProviderUnavailableError,
    get_provider,
)
from apps.payments.providers.mock import MockPaymentsDisabledError
from apps.payments.receipts import receipt_filename, render_receipt_pdf
from apps.payments.renewals.emails import send_mandate_email
from apps.payments.renewals.mandates import roll_charge_date_past
from apps.payments.renewals.schedule import (
    advance_by_cadence,
    card_expires_on,
    charge_date,
    lapsed_term_to_renew,
    lifetime_term,
    renewal_amount_cents,
    term_to_renew,
)
from apps.payments.services import create_checkout, mark_failed
from caldart import audit, events
from caldart.exceptions import DomainValidationError
from caldart.mail import Attachment
from caldart.reports import PDF_MEDIA_TYPE
from caldart.runs import CHARGE_KIND, RunAction, action_lines

log = logging.getLogger(__name__)

#: How many days before the charge the advance warning goes out.
NOTICE_DAYS = 14

#: Days after a failed charge that each retry is scheduled for, in order.  When
#: they are exhausted the mandate is paused.
RETRY_OFFSETS: tuple[int, ...] = (1, 3, 7)

#: How close to a card's expiry the member is warned that it will not last.
CARD_EXPIRY_WARNING_DAYS = 30

#: How long after the stored charge date a scan may still take it.  A scanner
#: that was down over a charge date catches up inside this window; past it the
#: lapse is too long for an unannounced charge to be the right thing to do, and
#: the mandate is paused instead.
CATCH_UP_DAYS = 30

#: What the member is told when their membership had lapsed too long to renew.
LAPSED_TOO_LONG_MESSAGE = (
    "your membership had lapsed for more than a month, so we did not take the renewal"
)

#: Why a mandate produced no charge on a given scan.
SKIP_REASONS: tuple[str, ...] = (
    "friend",
    "lifetime",
    "no_term",
    "not_active",
    "already_renewed",
    "no_plan",
    "in_flight",
    "provider_down",
)


# --------------------------------------------------------------------------
# The scan
# --------------------------------------------------------------------------
@dataclass
class RenewalRun:
    """Structured summary of one automatic-renewal scan.

    Printed by ``manage.py run_auto_renewals`` and answered verbatim by ``POST
    /system/renewals/run``.  ``noticed`` counts the advance warnings sent,
    ``charged`` the renewals taken, ``failed`` the charges the provider refused,
    ``paused`` the mandates whose retries ran out on this scan, and ``skipped``
    the mandates and attempts that needed nothing doing.

    ``actions`` names the people behind those counts: one
    :class:`~caldart.runs.RunAction` per email and per charge, in the order the
    scan reached them.  A live run records what it did; a dry run records what it
    would have done, taking a charge the provider has not been asked about yet as
    one that succeeds.
    """

    today: date
    dry_run: bool
    noticed: int = 0
    warned: int = 0
    charged: int = 0
    failed: int = 0
    paused: int = 0
    skipped: int = 0
    skipped_by_reason: dict[str, int] = field(default_factory=dict)
    actions: list[RunAction] = field(default_factory=list)

    def record_skipped(self, reason: str) -> None:
        """Count one more mandate or attempt skipped for ``reason``."""
        self.skipped += 1
        self.skipped_by_reason[reason] = self.skipped_by_reason.get(reason, 0) + 1

    def record_action(
        self,
        kind: str,
        mandate: RenewalMandate,
        *,
        on: date | None = None,
        amount_cents: int | None = None,
        detail: str = "",
    ) -> None:
        """Note that ``kind`` happened, or would happen, to ``mandate``'s member."""
        self.actions.append(
            RunAction(
                kind=kind,
                member=mandate.user.display_name,
                email=mandate.user.email,
                on=on,
                amount_cents=amount_cents,
                detail=detail,
            )
        )

    def as_dict(self) -> dict[str, Any]:
        """The counts and the actions ``POST /system/renewals/run`` answers with."""
        return {
            "noticed": self.noticed,
            "warned": self.warned,
            "charged": self.charged,
            "failed": self.failed,
            "paused": self.paused,
            "skipped": self.skipped,
            "actions": [action.as_dict() for action in self.actions],
        }

    def as_lines(self) -> list[str]:
        """Human-readable summary, one fact per line, then one line per action."""
        lines = [
            f"today            {self.today.isoformat()}",
            f"mode             {'dry run (nothing renewed)' if self.dry_run else 'live'}",
            f"noticed          {self.noticed}",
            f"card warnings    {self.warned}",
            f"charged          {self.charged}",
            f"failed           {self.failed}",
            f"paused           {self.paused}",
            f"skipped          {self.skipped}",
        ]
        lines += [
            f"  {reason:<14} {self.skipped_by_reason[reason]}"
            for reason in SKIP_REASONS
            if self.skipped_by_reason.get(reason)
        ]
        return lines + action_lines(self.actions, dry_run=self.dry_run)


def active_mandates() -> list[RenewalMandate]:
    """Every ``active`` mandate, with its member and plan loaded, oldest first."""
    return list(
        RenewalMandate.objects.filter(status=MandateStatus.ACTIVE)
        .select_related("user", "plan")
        .order_by("pk")
    )


def run_auto_renewals(
    *,
    today: date | None = None,
    dry_run: bool = False,
    actor: Model | str = audit.COMMAND_ACTOR,
) -> RenewalRun:
    """Scan every mandate, send the notices due, and charge the renewals due.

    ``today`` defaults to the current local date and is what every comparison is
    made against, so a rehearsal can be run as of any date.  A dry run changes no
    mandate, charges nobody and sends no email; it reports the counts the same
    scan would produce, and is itself recorded in the audit log.

    Nothing one member's mandate does stops the scan: a provider that declines,
    a provider that cannot be reached, is not configured, or is switched off, and
    a mail server that refuses a message are each recorded against that member's
    attempt and the walk carries on; a charge the provider was never asked to take
    is put off for the next scan rather than counted as refused.
    Every run ends with one ``renewals.run`` audit record carrying the mode and
    the counts, and returns them as a :class:`RenewalRun`, whose ``actions`` name
    every member the run emailed or charged -- or, in a rehearsal, would have.

    A charge whose date has already come round is scheduled and taken by the same
    scan.  A rehearsal writes no attempt for the charge step to find, so the
    notice step hands it the attempts it would have written and the rehearsal
    reports that charge too.
    """
    if today is None:
        today = timezone.localdate()
    run = RenewalRun(today=today, dry_run=dry_run)

    rehearsed: list[RenewalAttempt] = []
    for mandate in active_mandates():
        rehearsed += _notice(mandate, today, run, dry_run=dry_run)
        _warn_about_card(mandate, today, run, dry_run=dry_run)

    for attempt in [*_due_attempts(today), *rehearsed]:
        _charge(attempt, today, run, dry_run=dry_run)

    audit.record(
        audit.RENEWALS_RUN,
        actor=actor,
        dry_run=dry_run,
        noticed=run.noticed,
        charged=run.charged,
        failed=run.failed,
        paused=run.paused,
        skipped=run.skipped,
    )
    return run


def _rehearsed_attempt(
    mandate: RenewalMandate, term: Membership | None, charge_on: date, today: date
) -> list[RenewalAttempt]:
    """The unsaved attempt a rehearsal hands to its charge step, or nothing.

    A live run creates the attempt here and finds it again in the same run when
    its date has already come round.  A rehearsal writes nothing, so the attempt
    it would have written is carried forward instead -- and only when it is due
    today, since a charge still in the future is for a later run to take.
    """
    if charge_on > today:
        return []
    return [RenewalAttempt(mandate=mandate, membership=term, scheduled_on=charge_on)]


def _notice(
    mandate: RenewalMandate, today: date, run: RenewalRun, *, dry_run: bool
) -> list[RenewalAttempt]:
    """Schedule the charge for a term running out, and email the warning.

    A mandate carries one charge at a time, so an attempt still ``scheduled`` --
    against this term or against the one before it, which is what a member who
    renewed by hand leaves behind -- is the charge this run announces rather than a
    reason to write another.  Beyond that, only an attempt that has already
    ``succeeded`` against this very term stands in the way of a fresh one, so a
    mandate that was paused over a term and then turned back on is scheduled again
    rather than left to lapse quietly.  An attempt that is waiting but whose notice
    never went out -- a mail server that refused it -- is written to again here.

    Returns the attempts a rehearsal would have written and that are due today,
    for the charge step to rehearse as well; a live run returns nothing, because
    it has written them to the database the charge step reads.
    """
    if mandate.plan_id is None:
        return _notice_donation(mandate, today, run, dry_run=dry_run)
    if account_kind(mandate.user, today) == AccountKind.FRIEND:
        # A friend pays no dues, so a renewal they still hold renews nothing.
        run.record_skipped("friend")
        return []
    if lifetime_term(mandate.user) is not None:
        # The member has been granted a lifetime term since the mandate was made,
        # so there is no expiry left for it to renew.
        run.record_skipped("lifetime")
        return []
    term = term_to_renew(mandate.user, today)
    if term is None or term.ends_on is None:
        return _catch_up(mandate, today, run, dry_run=dry_run)
    waiting = (
        mandate.attempts.filter(outcome=RenewalOutcome.SCHEDULED)
        .order_by("scheduled_on", "pk")
        .first()
    )
    if waiting is None:
        if mandate.attempts.filter(membership=term, outcome=RenewalOutcome.SUCCEEDED).exists():
            return []
    elif waiting.noticed_at is not None:
        return []
    scheduled_on = charge_date(mandate, today)
    if scheduled_on is None:
        return []
    # A scan that was down over the charge date takes it today rather than
    # writing to the member about a date that has already gone by.
    charge_on = max(scheduled_on, today)
    if (charge_on - today).days > NOTICE_DAYS:
        return []

    attempt = waiting
    if attempt is None and not dry_run:
        attempt = _schedule(mandate, term, charge_on)
        if attempt is None:
            return []
    run.noticed += 1
    run.record_action("renewal_notice", mandate, on=charge_on)
    if attempt is None:
        # Only a rehearsal gets here with nothing written.
        return _rehearsed_attempt(mandate, term, charge_on, today)
    if dry_run:
        # An attempt already waiting is one the charge step finds by itself.
        return []
    _send_notice(mandate, attempt, charge_on, term.ends_on, today)
    return []


def _notice_donation(
    mandate: RenewalMandate, today: date, run: RenewalRun, *, dry_run: bool
) -> list[RenewalAttempt]:
    """Schedule, and for a yearly gift announce, the next charge of a recurring donation.

    The charge date is the mandate's own, and the attempt names no term: a donation
    accompanies no membership, so anybody's is charged whatever their membership.
    A yearly donation is scheduled and announced :data:`NOTICE_DAYS` ahead, exactly
    as a renewal is, and one whose notice the mail server refused is written to
    again here.  A monthly or quarterly donation sends no notice: its attempt is
    written on the day of the charge, for the charge step of the same run to take.

    Returns what :func:`_notice` returns, for the same reason.
    """
    waiting = (
        mandate.attempts.filter(outcome=RenewalOutcome.SCHEDULED).order_by("scheduled_on", "pk")
    ).first()
    is_yearly = mandate.cadence == MandateCadence.YEARLY
    if waiting is not None and (not is_yearly or waiting.noticed_at is not None):
        return []
    scheduled_on = charge_date(mandate, today)
    if scheduled_on is None:
        return []
    charge_on = max(scheduled_on, today)
    if not is_yearly:
        if charge_on > today:
            return []
        if dry_run:
            return _rehearsed_attempt(mandate, None, charge_on, today)
        _schedule(mandate, None, charge_on)
        return []
    if (charge_on - today).days > NOTICE_DAYS:
        return []

    attempt = waiting
    if attempt is None and not dry_run:
        attempt = _schedule(mandate, None, charge_on)
        if attempt is None:
            return []
    run.noticed += 1
    run.record_action("renewal_notice", mandate, on=charge_on)
    if attempt is None:
        return _rehearsed_attempt(mandate, None, charge_on, today)
    if dry_run:
        return []
    _send_notice(mandate, attempt, charge_on, None, today)
    return []


def _catch_up(
    mandate: RenewalMandate, today: date, run: RenewalRun, *, dry_run: bool
) -> list[RenewalAttempt]:
    """Renew a term that already ran out, or pause a mandate too far behind to.

    Reached for a mandate whose member holds no term left to renew.  While the
    ordinary reminders are skipped for an active mandate, this is the only thing
    that stops such a member lapsing unnoticed, so a charge date missed by no more
    than :data:`CATCH_UP_DAYS` is taken here: the attempt is dated today, the
    notice says the charge is happening today, and the charge step of the same run
    takes it.  A charge date missed by longer than that pauses the mandate and
    tells the member why, and the ordinary reminders resume for them.

    A charge date still further out than :data:`NOTICE_DAYS` is left for a later
    scan: a member who chose a day beyond their expiry lapses until it comes round.
    A term that already has an attempt against it is left alone: it is on the
    retry ladder, not behind the scanner.

    Returns what :func:`_notice` returns, for the same reason.
    """
    term = lapsed_term_to_renew(mandate.user, today)
    if term is None or term.ends_on is None:
        run.record_skipped("no_term")
        return []
    if mandate.attempts.filter(membership=term).exists():
        return []
    if (today - mandate.next_charge_on).days > CATCH_UP_DAYS:
        _abandon(mandate, run, dry_run=dry_run)
        return []
    charge_on = max(mandate.next_charge_on, today)
    if (charge_on - today).days > NOTICE_DAYS:
        return []

    attempt = None
    if not dry_run:
        attempt = _schedule(mandate, term, charge_on)
        if attempt is None:
            return []
    run.noticed += 1
    run.record_action("renewal_notice", mandate, on=charge_on)
    if attempt is None:
        return _rehearsed_attempt(mandate, term, charge_on, today)
    _send_notice(mandate, attempt, charge_on, term.ends_on, today)
    return []


def _schedule(
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
    notice and its taking to the scan that wrote it.  A retry carries the notice
    time of the attempt it retries.
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
        log.info("mandate %s already has a charge scheduled by another scan", mandate.pk)
        return None


def _send_notice(
    mandate: RenewalMandate,
    attempt: RenewalAttempt,
    charge_on: date,
    expires_on: date | None,
    today: date,
) -> None:
    """Send the advance notice for ``attempt``, and stamp it when the mail went.

    ``today`` reaches the template so a charge that is happening now is worded as
    happening now rather than as a date the member has to wait for.
    """
    if send_mandate_email(
        mandate, "renewal_notice", charge_on=charge_on, expires_on=expires_on, today=today
    ):
        attempt.noticed_at = timezone.now()
        attempt.save(update_fields=["noticed_at", "updated_at"])


def _abandon(mandate: RenewalMandate, run: RenewalRun, *, dry_run: bool) -> None:
    """Pause a mandate whose member lapsed too long ago to be charged unannounced.

    Nothing is charged and no attempt is written: there is no term the money
    would extend.  The member is told that automatic renewal is off, why, and
    where to renew by hand, and the ordinary reminders cover them from then on.
    The pause raises the ``auto_renewal_off`` event with ``how="lapsed"``.
    """
    run.paused += 1
    run.record_action("renewal_failed", mandate, detail=LAPSED_TOO_LONG_MESSAGE)
    if dry_run:
        return
    mandate.status = MandateStatus.PAUSED
    mandate.save(update_fields=["status", "updated_at"])
    events.emit("auto_renewal_off", mandate=mandate, how="lapsed")
    send_mandate_email(
        mandate, "renewal_failed", error=LAPSED_TOO_LONG_MESSAGE, next_on=None, lapsed=True
    )


def _warn_about_card(
    mandate: RenewalMandate, today: date, run: RenewalRun, *, dry_run: bool
) -> None:
    """Warn once that the card on file will not last until the next charge."""
    expires_on = card_expires_on(mandate)
    charge_on = charge_date(mandate, today)
    if expires_on is None or charge_on is None:
        return
    if expires_on >= charge_on:
        return
    if (expires_on - today).days > CARD_EXPIRY_WARNING_DAYS:
        return
    stamp = expires_on.isoformat()
    if (mandate.raw or {}).get("card_expiry_warned_for") == stamp:
        return

    run.warned += 1
    run.record_action("renewal_card_expiring", mandate, on=expires_on)
    if dry_run:
        return
    if send_mandate_email(
        mandate, "renewal_card_expiring", expires_on=expires_on, charge_on=charge_on
    ):
        raw = dict(mandate.raw or {})
        raw["card_expiry_warned_for"] = stamp
        mandate.raw = raw
        mandate.save(update_fields=["raw", "updated_at"])


def _due_attempts(today: date) -> list[RenewalAttempt]:
    """Every scheduled attempt due on ``today`` or earlier, oldest first."""
    return list(
        RenewalAttempt.objects.filter(outcome=RenewalOutcome.SCHEDULED, scheduled_on__lte=today)
        .select_related("mandate", "mandate__user", "mandate__plan", "membership")
        .order_by("scheduled_on", "pk")
    )


def _charge(attempt: RenewalAttempt, today: date, run: RenewalRun, *, dry_run: bool) -> None:
    """Take one scheduled renewal, and record what the provider said."""
    mandate = attempt.mandate
    if mandate.status != MandateStatus.ACTIVE:
        run.record_skipped("not_active")
        if not dry_run:
            _finish(attempt, RenewalOutcome.SKIPPED)
        return
    skip = _renewal_skip_reason(attempt, today)
    if skip is not None:
        run.record_skipped(skip)
        if not dry_run:
            _finish(attempt, RenewalOutcome.SKIPPED)
        if not dry_run and skip == "already_renewed" and attempt.membership is not None:
            # The coverage this charge was for arrived from somewhere else, so the
            # stored day follows it rather than waiting a year where it is.
            roll_charge_date_past(mandate.user, covered_until=attempt.membership.ends_on)
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

    run.record_action(CHARGE_KIND, mandate, on=attempt.scheduled_on, amount_cents=amount_cents)
    try:
        payment = create_checkout(
            mandate.user,
            mandate.plan.slug if mandate.plan is not None else None,
            mandate.contribution_cents,
            mandate.provider,
        )
    except DomainValidationError as exc:
        log.error("renewal for mandate %s could not be priced: %s", mandate.pk, exc)
        run.record_skipped("no_plan")
        _finish(attempt, RenewalOutcome.SKIPPED)
        return

    attempt.payment = payment
    attempt.save(update_fields=["payment", "updated_at"])

    try:
        get_provider(mandate.provider).charge_mandate(mandate, payment)
    except (ProviderUnavailableError, ProviderNotConfiguredError, MockPaymentsDisabledError) as exc:
        _postpone(attempt, payment, str(exc), run)
        return
    except PaymentError as exc:
        _record_failure(attempt, payment, str(exc), today, run)
        return

    _record_success(attempt, run)


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
    """
    claimed = RenewalAttempt.objects.filter(
        pk=attempt.pk,
        outcome=RenewalOutcome.SCHEDULED,
        attempted_at__isnull=True,
    ).update(attempted_at=timezone.now(), updated_at=timezone.now())
    if claimed == 0:
        return False
    attempt.refresh_from_db(fields=["attempted_at", "updated_at"])
    return True


def _postpone(attempt: RenewalAttempt, payment: Payment, reason: str, run: RenewalRun) -> None:
    """Put a charge back that the provider could not be asked to take.

    A provider that cannot be reached, that is not configured, or that is switched
    off -- the mock provider with ``PAYMENTS_MOCK_ENABLED`` off -- says nothing
    about the member's card, so it costs no rung of the retry ladder, sends no
    decline notice and does not pause the mandate.  The pending payment is thrown
    away and the attempt is released, still scheduled for the same day, so the
    next scan tries it again.
    """
    log.error(
        "renewal attempt %s could not charge through %s: %s", attempt.pk, payment.provider, reason
    )
    attempt.payment = None
    attempt.attempted_at = None
    attempt.save(update_fields=["payment", "attempted_at", "updated_at"])
    payment.delete()
    run.record_skipped("provider_down")


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

    The mandate's stored charge date moves on: to the ``ends_on`` of the term the
    charge bought for a renewal, and by the mandate's cadence from the day the
    charge was scheduled for a recurring donation, which renews no term.
    """
    mandate = attempt.mandate
    now = timezone.now()
    today = timezone.localdate()

    attempt.outcome = RenewalOutcome.SUCCEEDED
    attempt.save(update_fields=["outcome", "updated_at"])

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
    attachments: list[Attachment] = []
    if payment is not None:
        attachments.append((receipt_filename(payment), render_receipt_pdf(payment), PDF_MEDIA_TYPE))
    if send_mandate_email(
        mandate,
        "renewal_charged",
        expires_on=renewed.ends_on if renewed is not None and mandate.plan_id else None,
        next_charge_on=charge_on,
        receipt_number=payment.receipt_number if payment is not None else "",
        attachments=attachments,
    ):
        attempt.result_emailed_at = now
        if payment is not None:
            payment.receipt_sent_at = now
            payment.save(update_fields=["receipt_sent_at", "updated_at"])
    attempt.save(update_fields=["result_emailed_at", "updated_at"])
    run.record_action("renewal_charged", mandate, on=charge_on)
    run.charged += 1


def _record_failure(
    attempt: RenewalAttempt, payment: Payment, reason: str, today: date, run: RenewalRun
) -> None:
    """Record a declined charge, then retry it or pause the mandate.

    The provider's reason is kept on the attempt and quoted to the member.  A
    mandate with retries left gets the next one from :data:`RETRY_OFFSETS`; one
    whose retries are exhausted is paused, and the member is told that automatic
    renewal is off and the ordinary reminders resume.  Every decline raises the
    ``auto_renewal_declined`` event with the mandate, the ``reason``, and ``next_on``,
    the day of the retry or ``None`` once the mandate is paused.
    """
    mandate = attempt.mandate
    if payment.status != PaymentStatus.SUCCEEDED:
        mark_failed(payment, {"error": reason})

    mandate.failure_count += 1
    retries_left = mandate.failure_count <= len(RETRY_OFFSETS)
    next_on = (
        today + timedelta(days=RETRY_OFFSETS[mandate.failure_count - 1]) if retries_left else None
    )
    if not retries_left:
        mandate.status = MandateStatus.PAUSED
        run.paused += 1
    mandate.save(update_fields=["failure_count", "status", "updated_at"])

    attempt.outcome = RenewalOutcome.FAILED
    attempt.error = reason[:255]
    events.emit("auto_renewal_declined", mandate=mandate, reason=attempt.error, next_on=next_on)
    run.record_action("renewal_failed", mandate, on=next_on, detail=attempt.error)
    if send_mandate_email(mandate, "renewal_failed", error=attempt.error, next_on=next_on):
        attempt.result_emailed_at = timezone.now()
    attempt.save(update_fields=["outcome", "error", "result_emailed_at", "updated_at"])

    if next_on is not None:
        _schedule(mandate, attempt.membership, next_on, retry_of=attempt)
    run.failed += 1
