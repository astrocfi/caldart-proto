"""The renewal reminder scanner.

One entry point, :func:`send_renewal_reminders`, which the management command,
``POST /system/reminders/run`` and the systemd timer all call.  It is
deliberately idempotent: every email it sends is recorded in a ``ReminderLog``
row, and the unique constraint on ``(user, membership, kind)`` means a second
run sends nothing.  That constraint is also what makes the catch-up window
safe, and what a losing run in a race hits; neither ends the scan, and neither
does a mail server that refuses one address.
"""

from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass, field
from datetime import date, timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import IntegrityError, transaction
from django.template.loader import render_to_string
from django.utils import timezone

from apps.members.models import Membership, MembershipStatusChoices
from apps.members.services import expire_lapsed_memberships, membership_status
from apps.reminders.models import REMINDER_OFFSETS, ReminderKind, ReminderLog

log = logging.getLogger(__name__)

#: Subject lines, in the house voice: plain, specific, no exclamation marks.
#: ``{org}`` is the organization name from Wagtail's site settings, and
#: ``{days}`` the real distance in days between the scan date and the expiry
#: date, which is the kind's nominal offset only when the run is on time.
SUBJECTS: dict[str, str] = {
    ReminderKind.T60: "{org}: your membership expires in {days} days",
    ReminderKind.T30: "{org}: your membership expires in {days} days",
    ReminderKind.T7: "{org}: your membership expires in {days} days",
    ReminderKind.EXPIRED: "{org}: your membership expires today",
    ReminderKind.POST30: "{org}: your membership lapsed {days} days ago",
}

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
    "renewed",
)

#: How many days of expiry dates one scan covers, counting back from a kind's
#: own date, so that a run the timer missed still catches its cohorts.  It is
#: shorter than the seven days between ``t7`` and ``expired``, so no two kinds
#: ever claim the same membership on the same day.
WINDOW_DAYS: int = 3

#: Kinds that only ever go out on their own date.  "Your membership expires
#: today" is untrue the morning after, so a missed ``expired`` is dropped
#: rather than sent late.
EXACT_DAY_KINDS: frozenset[str] = frozenset({ReminderKind.EXPIRED})


@dataclass
class ReminderRun:
    """Structured summary of one scan.

    Printed by ``manage.py send_renewal_reminders`` and reduced to
    ``{sent, skipped}`` by ``POST /system/reminders/run``.
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

    def record_sent(self, kind: str) -> None:
        self.sent += 1
        self.sent_by_kind[kind] = self.sent_by_kind.get(kind, 0) + 1

    def record_skipped(self, reason: str) -> None:
        self.skipped += 1
        self.skipped_by_reason[reason] = self.skipped_by_reason.get(reason, 0) + 1

    def record_failed(self, kind: str) -> None:
        self.failed += 1
        self.failed_by_kind[kind] = self.failed_by_kind.get(kind, 0) + 1

    def as_dict(self) -> dict:
        """The ``{sent, skipped}`` payload of ``POST /system/reminders/run``.

        Failures are deliberately not in it: the panel reports what went out,
        and the operator reads the count and the log lines from the command.
        """
        return {"sent": self.sent, "skipped": self.skipped}

    def as_lines(self) -> list[str]:
        """Human-readable summary, one fact per line."""
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
        return lines


def renew_url() -> str:
    """Absolute link to the portal's renew screen."""
    return f"{settings.SITE_URL.rstrip('/')}/portal/renew"


def _site_settings():
    from apps.cms.models import get_site_settings

    return get_site_settings()


def _org_name() -> str:
    """The organization name from Wagtail site settings, or the default."""
    site_settings = _site_settings()
    return (getattr(site_settings, "org_name", "") if site_settings else "") or "CalDART"


def _contact_email() -> str:
    site_settings = _site_settings()
    return (getattr(site_settings, "contact_email", "") if site_settings else "") or ""


def build_email(user, membership: Membership, kind: str, today: date) -> EmailMultiAlternatives:
    """Render ``emails/reminder_<kind>.{txt,html}`` for one member.

    ``days`` is counted from the dates rather than taken from the kind's offset,
    so a reminder the catch-up window picked up two days behind says 28 days
    rather than claiming 30.
    """
    org = _org_name()
    days = abs((membership.ends_on - today).days)
    context = {
        "user": user,
        "first_name": user.first_name or user.display_name,
        "org_name": org,
        "contact_email": _contact_email(),
        "plan_name": membership.plan.name,
        "expires_on": membership.ends_on,
        "days": days,
        "today": today,
        "renew_url": renew_url(),
        "site_url": settings.SITE_URL.rstrip("/"),
    }
    message = EmailMultiAlternatives(
        subject=SUBJECTS[kind].format(org=org, days=days),
        body=render_to_string(f"emails/reminder_{kind}.txt", context),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    html = render_to_string(f"emails/reminder_{kind}.html", context)
    message.attach_alternative(html, "text/html")
    return message


def _skip_reason(user, membership: Membership, kind: str, today: date) -> str | None:
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

    if kind == ReminderKind.POST30:
        # Nothing to nag about once they are covered again.
        return "renewed" if status["status"] == "current" else None

    # For the pre-expiry kinds the member must still be running out on exactly
    # this term: an early renewal pushes unbroken coverage further out.
    if status["expires_on"] != membership.ends_on:
        return "renewed"
    return None


def _candidates(kind: str, today: date):
    """Memberships due this kind of reminder on ``today``, or overdue one.

    ``REMINDER_OFFSETS`` counts days from expiry, negative before it, so the
    ``t60`` cohort is the one ending 60 days from now.  A kind in
    ``EXACT_DAY_KINDS`` matches that date alone; every other kind also matches
    the ``WINDOW_DAYS - 1`` days before it, which is how a run that the daily
    timer missed still reaches the members it stepped over.  The ``ReminderLog``
    constraint keeps the overlap between consecutive runs from sending twice.
    Lifetime terms have no ``ends_on`` and so never appear here.
    """
    target = today - timedelta(days=REMINDER_OFFSETS[kind])
    earliest = target
    if kind not in EXACT_DAY_KINDS:
        earliest = target - timedelta(days=WINDOW_DAYS - 1)
    return (
        Membership.objects.select_related("user", "plan")
        .filter(ends_on__gte=earliest, ends_on__lte=target)
        .exclude(status=MembershipStatusChoices.CANCELED)
        .order_by("user_id", "id")
    )


def send_renewal_reminders(*, today: date | None = None, dry_run: bool = False) -> ReminderRun:
    """Scan for due reminders and send them.

    Flips memberships whose ``ends_on`` has passed to ``expired`` first, so the
    ``post30`` cohort is honestly labeled, then walks the five kinds in order.
    A dry run writes nothing at all: no email, no log rows, no status flips.

    One member's problem never stops the scan.  A send the mail server refuses
    is logged at ERROR, counted in ``failed`` and ``failed_by_kind``, and leaves
    no log row, so the next run inside the window tries again.  A log row
    another run wrote first counts as ``already_sent``.  The run summary is
    returned either way; nothing is raised.
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
                run.record_sent(kind)
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
                run.record_sent(kind)

    return run


@transaction.atomic
def _send_one(user, membership: Membership, kind: str, today: date) -> None:
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
    build_email(user, membership, kind, today).send(fail_silently=False)
