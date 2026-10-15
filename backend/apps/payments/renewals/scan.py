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
   provider's reason, emails it, and schedules the next retry -- or, once those
   are exhausted, pauses the mandate and hands the member back to the ordinary
   renewal reminders.  :mod:`apps.payments.renewals.charge` takes each charge, and
   never takes one twice.

A live scan holds a database advisory lock while it runs, so the timer and a
**Run now** never charge at the same time; one that cannot take the lock raises
:class:`RenewalsBusyError` before it does anything.

Every email is keyed on a timestamp of the attempt it belongs to, so a scan run
twice in one day sends nothing twice.  A dry run changes no mandate, sends no
email and charges nobody; the run itself is still recorded in the audit log.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from django.db import connection
from django.db.models import Model
from django.utils import timezone

from apps.accounts.models import AccountKind
from apps.members.models import Membership
from apps.members.services import account_kind
from apps.payments.models import (
    MandateCadence,
    MandateStatus,
    RenewalAttempt,
    RenewalMandate,
    RenewalOutcome,
)
from apps.payments.renewals.charge import RETRY_OFFSETS as RETRY_OFFSETS
from apps.payments.renewals.charge import charge, due_attempts, schedule_attempt, stale_after
from apps.payments.renewals.emails import send_mandate_email
from apps.payments.renewals.schedule import (
    card_expires_on,
    charge_date,
    lapsed_term_to_renew,
    lifetime_term,
    term_to_renew,
)
from caldart import audit, events
from caldart.runs import RunAction, action_lines

log = logging.getLogger(__name__)

#: How many days before the charge the advance warning goes out.
NOTICE_DAYS = 14

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

#: Sets the live renewal scan's advisory lock apart from every other one on the
#: database.
SCAN_LOCK_KEY = 0x0C4A_26E5

#: What a live scan says when another one already holds the lock.
ALREADY_RUNNING_MESSAGE = "Another automatic renewal run is already under way."

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
    "pending",
    "in_doubt",
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
    #: The providers that answered nothing at all earlier in this run: the charge
    #: step sends them no more charges until the next run.
    unanswered: set[str] = field(default_factory=set)
    #: Where a charged email goes to be sent later, or ``None`` to send it at once.
    #: A treasurer settling a charge from the portal hands it to the response.
    defer: Callable[[Callable[[], None]], None] | None = None

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

    A live scan first checks ``RENEWAL_STALE_MINUTES`` (``stale_after``), raising
    ``ImproperlyConfigured`` when it is too small, then takes the renewal scan's
    advisory lock for as long as it runs.  When another live scan holds the lock
    it raises :class:`RenewalsBusyError` having done nothing at all.  A rehearsal
    changes nothing, so it takes no lock and runs beside a live scan.
    """
    if today is None:
        today = timezone.localdate()
    run = RenewalRun(today=today, dry_run=dry_run)
    if dry_run:
        _scan(run, today, dry_run=True)
    else:
        stale_after()
        with scan_lock() as is_held:
            if not is_held:
                raise RenewalsBusyError(ALREADY_RUNNING_MESSAGE)
            _scan(run, today, dry_run=False)

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


class RenewalsBusyError(RuntimeError):
    """Another live renewal scan holds the lock, so this one did nothing."""


@contextmanager
def scan_lock() -> Iterator[bool]:
    """Hold the renewal scan's advisory lock for the block; yield whether it was taken.

    The lock belongs to the database session, so it is released however the block
    ends, and also if the process dies.
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_try_advisory_lock(%s)", [SCAN_LOCK_KEY])
        row = cursor.fetchone()
    is_held = row is not None and bool(row[0])
    try:
        yield is_held
    finally:
        if is_held:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_unlock(%s)", [SCAN_LOCK_KEY])


def _scan(run: RenewalRun, today: date, *, dry_run: bool) -> None:
    """Send the notices and card warnings due, then take the charges due, into ``run``."""
    rehearsed: list[RenewalAttempt] = []
    for mandate in active_mandates():
        rehearsed += _notice(mandate, today, run, dry_run=dry_run)
        _warn_about_card(mandate, today, run, dry_run=dry_run)

    for attempt in [*due_attempts(today), *rehearsed]:
        charge(attempt, today, run, dry_run=dry_run)


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
        attempt = schedule_attempt(mandate, term, charge_on)
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
        schedule_attempt(mandate, None, charge_on)
        return []
    if (charge_on - today).days > NOTICE_DAYS:
        return []

    attempt = waiting
    if attempt is None and not dry_run:
        attempt = schedule_attempt(mandate, None, charge_on)
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
        attempt = schedule_attempt(mandate, term, charge_on)
        if attempt is None:
            return []
    run.noticed += 1
    run.record_action("renewal_notice", mandate, on=charge_on)
    if attempt is None:
        return _rehearsed_attempt(mandate, term, charge_on, today)
    _send_notice(mandate, attempt, charge_on, term.ends_on, today)
    return []


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
