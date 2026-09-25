"""The renewal reminder scanner.

One entry point, :func:`send_renewal_reminders`, which the management command,
``POST /system/reminders/run`` and the systemd timer all call.  It is
deliberately idempotent: every email it sends is recorded in a ``ReminderLog``
row, and the unique constraint on ``(user, membership, kind)`` means a second
run sends nothing.  That constraint is also what lets each kind be a stage --
a span of expiry dates rather than one date -- and what a losing run in a race
hits; neither ends the scan, and neither does a mail server that refuses one
address.
"""

from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Model, QuerySet
from django.template.defaultfilters import pluralize
from django.utils import timezone

from apps.accounts.models import User
from apps.members.models import Membership, MembershipState, MembershipStatusChoices
from apps.members.services import expire_lapsed_memberships, membership_status
from apps.payments.models import MandateStatus, RenewalMandate, RenewalOutcome
from apps.reminders.models import REMINDER_OFFSETS, ReminderKind, ReminderLog
from caldart import audit
from caldart.mail import contact_email, org_name, send_templated
from caldart.runs import RunAction, action_lines

log = logging.getLogger(__name__)

#: Subject lines, in the house voice: plain, specific, no exclamation marks.
#: ``{org}`` is the organization name from Wagtail's site settings, ``{days}``
#: the real distance in days between the scan date and the expiry date -- any
#: day inside the stage's span -- and ``{plural}`` the "s" that a count of one
#: drops.
SUBJECTS: dict[str, str] = {
    ReminderKind.T60: "{org}: your membership expires in {days} day{plural}",
    ReminderKind.T30: "{org}: your membership expires in {days} day{plural}",
    ReminderKind.T7: "{org}: your membership expires in {days} day{plural}",
    ReminderKind.EXPIRED: "{org}: your membership expires today",
    ReminderKind.POST30: "{org}: your membership lapsed {days} day{plural} ago",
}

#: The ``expired`` subject for a term that ran out earlier in the stage's span.
#: "expires today" is only true on the expiry day itself, and the span covers
#: the six days after it.
EXPIRED_SUBJECT_DAYS_AGO: str = "{org}: your membership expired {days} day{plural} ago"

#: The order kinds are scanned and reported in.
KIND_ORDER: tuple[str, ...] = (
    ReminderKind.T60,
    ReminderKind.T30,
    ReminderKind.T7,
    ReminderKind.EXPIRED,
    ReminderKind.POST30,
)

#: Why a candidate membership did not produce an email.
SKIP_REASONS: tuple[str, ...] = (
    "already_sent",
    "inactive_user",
    "no_email",
    "lifetime",
    "auto_renew",
    "renewed",
)

#: How many days of expiry dates each stage at or after expiry reaches back
#: from its own date.  ``expired`` keeps to the week in which a term that has
#: just run out is still recent news, and ``post30`` covers the month from
#: thirty to sixty days after expiry, after which membership says nothing more.
#: The stages before expiry need no entry: each reaches back to the day after
#: the stage nearer expiry, so those spans meet without touching.
POST_EXPIRY_REACH_DAYS: dict[str, int] = {
    ReminderKind.EXPIRED: 6,
    ReminderKind.POST30: 30,
}


@dataclass
class ReminderRun:
    """Structured summary of one scan.

    Printed by ``manage.py send_renewal_reminders`` and reduced to
    ``{sent, skipped, failed, skipped_by_reason, actions}`` by
    ``POST /system/reminders/run``.

    ``actions`` names the members behind the counts: one
    :class:`~caldart.runs.RunAction` per reminder, its ``kind`` the reminder kind
    and its ``on`` the day the term runs out.  A live run records what it sent; a
    dry run records what it would have sent.
    """

    today: date
    dry_run: bool
    sent: int = 0
    skipped: int = 0
    failed: int = 0
    expired_flipped: int = 0
    sent_by_kind: dict[str, int] = field(default_factory=dict)
    skipped_by_reason: dict[str, int] = field(default_factory=dict)
    failed_by_kind: dict[str, int] = field(default_factory=dict)
    actions: list[RunAction] = field(default_factory=list)

    def record_sent(self, kind: str, user: User, membership: Membership) -> None:
        """Count one more reminder of ``kind``, and name who it went to.

        Counted overall and per kind, and appended to ``actions`` with the
        member's name, their address and the day their term runs out.
        """
        self.sent += 1
        self.sent_by_kind[kind] = self.sent_by_kind.get(kind, 0) + 1
        self.actions.append(
            RunAction(
                kind=kind,
                member=user.display_name,
                email=user.email,
                on=membership.ends_on,
            )
        )

    def record_skipped(self, reason: str) -> None:
        """Count one more candidate skipped for ``reason``, overall, and per reason."""
        self.skipped += 1
        self.skipped_by_reason[reason] = self.skipped_by_reason.get(reason, 0) + 1

    def record_failed(self, kind: str) -> None:
        """Count one more failed send of ``kind``, overall, and per kind."""
        self.failed += 1
        self.failed_by_kind[kind] = self.failed_by_kind.get(kind, 0) + 1

    def as_dict(self) -> dict[str, Any]:
        """The payload of ``POST /system/reminders/run``.

        ``{sent, skipped, failed, skipped_by_reason, actions}``: the counts, why
        each candidate was passed over, and the member behind every reminder.
        ``skipped_by_reason`` carries only the reasons that occurred, so a run
        that sent little says why on the screen rather than only in the log.
        """
        return {
            "sent": self.sent,
            "skipped": self.skipped,
            "failed": self.failed,
            "skipped_by_reason": dict(self.skipped_by_reason),
            "actions": [action.as_dict() for action in self.actions],
        }

    def as_lines(self) -> list[str]:
        """Human-readable summary, one fact per line, then one line per reminder."""
        lines = [
            f"today            {self.today.isoformat()}",
            f"mode             {'dry run (nothing written)' if self.dry_run else 'live'}",
            f"expired flipped  {self.expired_flipped}",
            f"sent             {self.sent}",
        ]
        lines += [f"  {kind:<14} {self.sent_by_kind.get(kind, 0)}" for kind in KIND_ORDER]
        lines.append(f"skipped          {self.skipped}")
        for reason in SKIP_REASONS:
            count = self.skipped_by_reason.get(reason, 0)
            if count:
                lines.append(f"  {reason:<14} {count}")
        lines.append(f"failed           {self.failed}")
        for kind in KIND_ORDER:
            count = self.failed_by_kind.get(kind, 0)
            if count:
                lines.append(f"  {kind:<14} {count}")
        return lines + action_lines(self.actions, dry_run=self.dry_run)


def renew_url() -> str:
    """Absolute link to the portal's renew screen."""
    return f"{settings.SITE_URL.rstrip('/')}/portal/renew"


def send_reminder_email(user: User, membership: Membership, kind: str, today: date) -> None:
    """Render ``emails/reminder_<kind>.{txt,html}`` for one member and send them.

    ``days`` is counted from the dates rather than from the middle of the stage,
    so a ``t30`` email to a member whose term ends in 28 days says 28 days.
    ``days_ago`` counts the days since the term ran out, negative while it is
    still running, which is what lets the ``expired`` bodies say "today" on the
    expiry day and "N days ago" later in the stage.  The ``expired`` subject
    follows the same two forms.

    The send goes through the shared mail funnel, so the email is recorded in the
    email log under the purpose ``reminder_<kind>``.  A mail server that refuses
    the message raises, for the caller to count.
    """
    org = org_name()
    # Lifetime terms (no ends_on) never reach here: _candidates() filters on ends_on.
    assert membership.ends_on is not None  # noqa: S101 - mypy strict narrowing, not test code
    days = abs((membership.ends_on - today).days)
    days_ago = (today - membership.ends_on).days
    subject = SUBJECTS[kind]
    if kind == ReminderKind.EXPIRED and days_ago > 0:
        subject = EXPIRED_SUBJECT_DAYS_AGO
    context = {
        "user": user,
        "first_name": user.first_name or user.display_name,
        "org_name": org,
        "contact_email": contact_email(),
        "plan_name": membership.plan.name,
        "expires_on": membership.ends_on,
        "days": days,
        "days_ago": days_ago,
        "today": today,
        "renew_url": renew_url(),
        "site_url": settings.SITE_URL.rstrip("/"),
    }
    send_templated(
        to=user.email,
        subject=subject.format(org=org, days=days, plural=pluralize(days)),
        template=f"reminder_{kind}",
        context=context,
        user_id=user.pk,
    )


def _skip_reason(user: User, membership: Membership, kind: str, today: date) -> str | None:
    """Why this candidate should not be emailed, or ``None`` to send."""
    if not user.is_active:
        return "inactive_user"
    if not user.email:
        return "no_email"
    if ReminderLog.objects.filter(user=user, membership=membership, kind=kind).exists():
        return "already_sent"

    status = membership_status(user, on_date=today)
    if status["is_lifetime"]:
        return "lifetime"
    if _renews_itself(user):
        return "auto_renew"

    if kind == ReminderKind.POST30:
        # Nothing to nag about once they are covered again.
        return "renewed" if status["status"] == MembershipState.CURRENT else None

    # For the pre-expiry kinds the member must still be running out on exactly
    # this term: an early renewal pushes unbroken coverage further out.
    if status["expires_on"] != membership.ends_on:
        return "renewed"
    return None


def _renews_itself(user: User) -> bool:
    """Whether automatic renewal is covering this member, so a reminder would confuse.

    True for an active mandate, and for a pending one that already has a
    scheduled charge: in both cases the renewal emails tell the member what is
    happening to their membership.  A paused or canceled mandate covers nothing,
    so the ordinary reminders resume.
    """
    mandate = RenewalMandate.objects.filter(user=user).first()
    if mandate is None:
        return False
    if mandate.status == MandateStatus.ACTIVE:
        return True
    if mandate.status != MandateStatus.PENDING:
        return False
    return mandate.attempts.filter(outcome=RenewalOutcome.SCHEDULED).exists()


def stage_span(kind: str, today: date) -> tuple[date, date]:
    """The first and last expiry date in ``kind``'s stage for a scan on ``today``.

    Both ends are inclusive.  The latest date is the kind's own date,
    ``today - REMINDER_OFFSETS[kind]``.  How far back the stage reaches from
    there depends on which side of expiry it sits:

    A stage before expiry reaches back to the day after the date of the stage
    nearer expiry, so the three of them tile the two months before a term runs
    out without overlapping: for a scan on day D, ``t60`` covers terms ending
    D+31 to D+60, ``t30`` covers D+8 to D+30, and ``t7`` covers D+1 to D+7.  A
    member who joins the register 23 days out is therefore in ``t30`` that day,
    rather than falling between two exact dates and hearing nothing.

    A stage at or after expiry reaches back by its entry in
    :data:`POST_EXPIRY_REACH_DAYS`: ``expired`` covers terms that ran out on any
    of the last seven days up to and including D, and ``post30`` those that ran
    out between D-60 and D-30.  Nothing covers the three weeks between them, or
    anything older than sixty days.

    Spans never overlap, so one scan sends a member at most one reminder.
    """
    offset = REMINDER_OFFSETS[kind]
    latest = today - timedelta(days=offset)
    if kind in POST_EXPIRY_REACH_DAYS:
        reach = POST_EXPIRY_REACH_DAYS[kind]
    else:
        nearer = min(other for other in REMINDER_OFFSETS.values() if other > offset)
        reach = nearer - offset - 1
    return latest - timedelta(days=reach), latest


def _candidates(kind: str, today: date) -> QuerySet[Membership]:
    """Memberships inside this stage's span of expiry dates on ``today``.

    The span comes from :func:`stage_span`, so every term running out in that
    part of the calendar is a candidate rather than only the ones landing on an
    exact date.  The ``ReminderLog`` constraint keeps a member who sits in one
    stage for days from being written to twice.  Canceled terms are left out,
    and lifetime terms have no ``ends_on`` and so never appear here.
    """
    earliest, latest = stage_span(kind, today)
    return (
        Membership.objects.select_related("user", "plan")
        .filter(ends_on__gte=earliest, ends_on__lte=latest)
        .exclude(status=MembershipStatusChoices.CANCELED)
        .order_by("user_id", "id")
    )


def send_renewal_reminders(
    *,
    today: date | None = None,
    dry_run: bool = False,
    actor: Model | str = audit.COMMAND_ACTOR,
) -> ReminderRun:
    """Scan for due reminders and send them.

    Flips memberships whose ``ends_on`` has passed to ``expired`` first, so the
    ``post30`` stage is honestly labeled, then walks the five stages in order,
    each covering the span of expiry dates :func:`stage_span` gives it.  A
    member is in at most one stage on any day, and gets each stage once.  A dry
    run writes nothing at all: no email, no log rows, no status flips.

    A member whose membership renews itself is skipped for every stage, because
    the automatic-renewal emails already tell them what is happening; a mandate
    that has been paused or canceled covers nothing, so the reminders resume.

    One member's problem never stops the scan.  A send the mail server refuses
    is logged at ERROR, counted in ``failed`` and ``failed_by_kind``, and leaves
    no log row, so any later run while the term is still in that stage tries
    again.  A log row another run wrote first counts as ``already_sent``.  The
    run summary is returned either way; nothing is raised.

    The run's ``actions`` name every member a reminder went to, or would have
    gone to, so a rehearsal answers who as well as how many.

    Every run ends with one audit record carrying the mode and the four counts.
    ``actor`` is the account that asked for it; the management command and the
    daily timer leave it at ``command``.
    """
    today = today or timezone.localdate()
    run = ReminderRun(today=today, dry_run=dry_run)

    lapsed = Membership.objects.filter(
        status=MembershipStatusChoices.ACTIVE,
        ends_on__isnull=False,
        ends_on__lt=today,
    )
    run.expired_flipped = lapsed.count() if dry_run else expire_lapsed_memberships(today)

    for kind in KIND_ORDER:
        for membership in _candidates(kind, today):
            user = membership.user
            reason = _skip_reason(user, membership, kind, today)
            if reason is not None:
                run.record_skipped(reason)
                continue
            if dry_run:
                run.record_sent(kind, user, membership)
                continue
            try:
                _send_one(user, membership, kind, today)
            except IntegrityError:
                # A concurrent run logged this reminder between the check above
                # and the insert; its email is the one that goes out.
                log.warning(
                    "reminder already logged by a concurrent run: kind=%s user=%s membership=%s",
                    kind,
                    user.pk,
                    membership.pk,
                )
                run.record_skipped("already_sent")
            except (smtplib.SMTPException, OSError) as exc:
                # Ids and the exception class only: the scan log is not a place
                # to accumulate members' email addresses.
                log.error(
                    "reminder send failed: kind=%s user=%s membership=%s error=%s",
                    kind,
                    user.pk,
                    membership.pk,
                    type(exc).__name__,
                )
                run.record_failed(kind)
            else:
                run.record_sent(kind, user, membership)

    audit.record(
        audit.REMINDERS_RUN,
        actor=actor,
        dry_run=dry_run,
        sent=run.sent,
        skipped=run.skipped,
        failed=run.failed,
        expired_flipped=run.expired_flipped,
    )
    return run


@transaction.atomic
def _send_one(user: User, membership: Membership, kind: str, today: date) -> None:
    """Log the reminder, then send it.

    The log row goes in first and inside the transaction, so a send that fails
    rolls the row back and the reminder stays due.  If two runs race, the
    unique constraint makes the loser raise ``IntegrityError`` rather than send
    a duplicate; whatever the mail backend raises propagates in the same way,
    for the caller to record.
    """
    ReminderLog.objects.create(
        user=user,
        membership=membership,
        kind=kind,
        sent_at=timezone.now(),
        to_email=user.email,
    )
    send_reminder_email(user, membership, kind, today)
