"""The sender: report subscriptions and DART rosters, by email.

One entry point, :func:`run_scheduled_reports`, which the management command,
``POST /system/reports/run`` and the systemd timer all call.  It sends every active
subscription that is due, then every DART roster that is due, and reports what it did
as a :class:`ReportRun`.  :func:`send_subscription_now` and :func:`send_rosters_now`
are the two **Send now** buttons: the same sends, whatever the date.

Every file attached is built by :func:`caldart.reports.build_report`, exactly as the
report's download builds it, and every email goes through
:func:`caldart.mail.send_templated`, so the email log records each one.  One
recipient's problem never stops a run: a send the mail server refuses is counted in
``failed`` and left due, so the next daily run tries again.
"""

from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Any

from django.db.models import Model, Q, QuerySet
from django.utils import dateformat, timezone
from rest_framework.exceptions import ValidationError

from apps.darts.models import Dart, DartContact
from apps.members.filters import MemberAdminFilterSet, member_admin_queryset
from apps.members.reports import MEMBER_REPORT
from apps.reports.models import ReportFormats, ReportSubscription
from apps.reports.permissions import can_read_report
from apps.reports.registry import REPORTS
from apps.reports.schedule import next_due_after, schedule_label
from caldart import audit
from caldart.mail import Attachment, contact_email, org_name, send_templated
from caldart.reports import (
    Params,
    Report,
    ReportDocument,
    ReportFormat,
    apply_filterset,
    build_report,
    filter_summary,
    given_params,
)
from caldart.runs import RunAction, action_lines

log = logging.getLogger(__name__)

#: The action kind a subscription's email is recorded under.
REPORT_KIND = "report"

#: The action kind a DART roster's email is recorded under.
ROSTER_KIND = "roster"

#: Why a subscription or a roster did not produce an email, in the order a
#: summary lists them.  ``not_permitted``: the subscription's account may no
#: longer read the report, so it was paused.  ``no_recipients``: a DART with no
#: ticked person who has an address.  ``no_email``: one ticked person without an
#: address, on a DART whose roster went to others.
SKIP_REASONS: tuple[str, ...] = ("not_permitted", "no_recipients", "no_email")

#: The columns of a DART's roster, in the order it prints them.
ROSTER_COLUMNS: tuple[str, ...] = (
    "name",
    "phone",
    "email",
    "certificate",
    "medical_type",
    "medical_expiration",
    "aircraft",
    "expires_on",
)

#: The files each ``formats`` value attaches, in attachment order.
FORMAT_FILES: dict[str, tuple[ReportFormat, ...]] = {
    ReportFormats.CSV: ("csv",),
    ReportFormats.PDF: ("pdf",),
    ReportFormats.BOTH: ("csv", "pdf"),
}

#: The formats in words, as an action's detail and an email body name them.
FORMAT_LABELS: dict[str, str] = {
    ReportFormats.CSV: "CSV",
    ReportFormats.PDF: "PDF",
    ReportFormats.BOTH: "CSV and PDF",
}

#: What a refused send raises: the mail server's refusal, or a dropped connection.
SEND_ERRORS: tuple[type[Exception], ...] = (smtplib.SMTPException, OSError)

#: The prose date format of every email: ``October 1, 2026``.
PROSE_DATE = "F j, Y"


@dataclass
class ReportRun:
    """What one run of the sender did, or would do.

    Printed by ``manage.py send_scheduled_reports`` and answered by
    ``POST /system/reports/run``, ``POST /reports/subscriptions/{id}/send`` and
    ``POST /reports/rosters/send`` as ``{sent, skipped, failed, skipped_by_reason,
    actions}``.  ``actions`` holds one :class:`~caldart.runs.RunAction` per email: kind
    ``report`` naming the recipient and, in ``detail``, the report's title and
    formats; kind ``roster`` naming the person and, in ``detail``, the DART.  A dry
    run records exactly the emails a live run would send.
    """

    today: date
    dry_run: bool
    sent: int = 0
    skipped: int = 0
    failed: int = 0
    skipped_by_reason: dict[str, int] = field(default_factory=dict)
    actions: list[RunAction] = field(default_factory=list)

    def record_sent(self, action: RunAction) -> None:
        """Count one more email, and name who it went to."""
        self.sent += 1
        self.actions.append(action)

    def record_skipped(self, reason: str) -> None:
        """Count one more subscription or person passed over for ``reason``."""
        self.skipped += 1
        self.skipped_by_reason[reason] = self.skipped_by_reason.get(reason, 0) + 1

    def record_failed(self) -> None:
        """Count one more email refused by the mail server, or a report not built."""
        self.failed += 1

    def counts(self) -> tuple[int, int, int]:
        """``(sent, skipped, failed)`` so far."""
        return self.sent, self.skipped, self.failed

    def as_dict(self) -> dict[str, Any]:
        """The run as the endpoints answer it: the counts, the reasons, the emails.

        ``skipped_by_reason`` carries only the reasons that occurred.
        """
        return {
            "sent": self.sent,
            "skipped": self.skipped,
            "failed": self.failed,
            "skipped_by_reason": dict(self.skipped_by_reason),
            "actions": [action.as_dict() for action in self.actions],
        }

    def as_lines(self) -> list[str]:
        """Human-readable summary, one fact per line, then one line per email."""
        lines = [
            f"today            {self.today.isoformat()}",
            f"mode             {'dry run (nothing sent)' if self.dry_run else 'live'}",
            f"sent             {self.sent}",
            f"skipped          {self.skipped}",
        ]
        for reason in SKIP_REASONS:
            count = self.skipped_by_reason.get(reason, 0)
            if count:
                lines.append(f"  {reason:<14} {count}")
        lines.append(f"failed           {self.failed}")
        return lines + action_lines(self.actions, dry_run=self.dry_run)


# --------------------------------------------------------------------------
# Subscriptions
# --------------------------------------------------------------------------
def recipient_may_read(subscription: ReportSubscription, spec: Report) -> bool:
    """Whether ``subscription`` may still go where it goes.

    A subscription bound to an account needs that account to be active and to hold a
    role that may read ``spec``; one sent to a bare address was confirmed when it was
    set up and always may.
    """
    user = subscription.recipient_user
    if user is None:
        return True
    return user.is_active and can_read_report(user, spec)


def subscription_params(subscription: ReportSubscription) -> Params:
    """The params ``subscription`` builds its report with: its filters and its columns.

    An empty column list leaves ``columns`` out, which is the report's defaults.
    """
    params: dict[str, str] = dict(subscription.filters)
    if subscription.columns:
        params["columns"] = ",".join(subscription.columns)
    return params


def subscription_action(subscription: ReportSubscription, spec: Report) -> RunAction:
    """The run action one email of ``subscription`` is recorded as."""
    user = subscription.recipient_user
    return RunAction(
        kind=REPORT_KIND,
        member=user.display_name if user is not None else subscription.recipient_email,
        email=subscription.recipient_email,
        detail=f"{spec.title}, {FORMAT_LABELS[subscription.formats]}",
    )


def subscription_documents(
    subscription: ReportSubscription, spec: Report, today: date
) -> list[ReportDocument]:
    """The files ``subscription`` attaches, built for ``today``; two for ``both``."""
    params = subscription_params(subscription)
    return [
        build_report(spec, params, fmt=fmt, today=today)
        for fmt in FORMAT_FILES[subscription.formats]
    ]


def send_subscription_email(subscription: ReportSubscription, spec: Report, today: date) -> None:
    """Build ``subscription``'s files for ``today`` and email them to its recipient.

    The subject reads ``CalDART report: <title> (<Month D, YYYY>)``, and the body
    (``emails/scheduled_report.{txt,html}``) names the report, its filters, the
    schedule and who set it up.  The email log records the send under the purpose
    ``scheduled_report``, with the recipient's account when there is one.  A report
    the stored params no longer build raises DRF's ``ValidationError``, and a refusing
    mail server raises as :func:`~caldart.mail.send_templated` does.
    """
    documents = subscription_documents(subscription, spec, today)
    attachments: list[Attachment] = [
        (document.filename, document.content, document.media_type) for document in documents
    ]
    user = subscription.recipient_user
    creator = subscription.created_by
    context: dict[str, object] = {
        "org_name": org_name(),
        "contact_email": contact_email(),
        "first_name": (user.first_name or user.display_name) if user is not None else "",
        "report_title": spec.title,
        "report_date": today,
        "filters": filter_summary(given_params(subscription.filters)),
        "schedule": schedule_label(subscription.cadence, subscription.weekday),
        "formats": FORMAT_LABELS[subscription.formats],
        "created_by": creator.display_name if creator is not None else "",
        "filenames": [document.filename for document in documents],
    }
    send_templated(
        to=subscription.recipient_email,
        subject=f"CalDART report: {spec.title} ({dateformat.format(today, PROSE_DATE)})",
        template="scheduled_report",
        context=context,
        attachments=attachments,
        purpose="scheduled_report",
        user_id=user.pk if user is not None else None,
    )


def send_subscription(
    run: ReportRun,
    subscription: ReportSubscription,
    *,
    today: date,
    dry_run: bool,
    advance: bool,
) -> None:
    """Send ``subscription`` once, recording the outcome on ``run``.

    A recipient who may no longer read the report (:func:`recipient_may_read`) is
    skipped as ``not_permitted`` and the subscription is paused.  Otherwise the email
    goes out, ``last_sent_at`` is stamped and, when ``advance`` is set, ``next_due_on``
    moves to the schedule's next day after ``today``.  A report that cannot be built
    from the stored params, or a send the mail server refuses, is counted in
    ``failed`` and changes nothing, so the subscription stays due.  A dry run records
    what would happen and writes nothing.
    """
    spec = REPORTS[subscription.report]
    if not recipient_may_read(subscription, spec):
        run.record_skipped("not_permitted")
        if not dry_run:
            subscription.is_active = False
            subscription.save(update_fields=["is_active", "updated_at"])
        return
    action = subscription_action(subscription, spec)
    if dry_run:
        run.record_sent(action)
        return
    try:
        send_subscription_email(subscription, spec, today)
    except (smtplib.SMTPException, OSError, ValidationError) as exc:
        # The id and the exception class only: the log is not a place to collect
        # addresses, and the email log already names the refused one.
        log.error(
            "report subscription send failed: subscription=%s error=%s",
            subscription.pk,
            type(exc).__name__,
        )
        run.record_failed()
        return
    subscription.last_sent_at = timezone.now()
    fields = ["last_sent_at", "updated_at"]
    if advance:
        subscription.next_due_on = next_due_after(subscription.cadence, subscription.weekday, today)
        fields.append("next_due_on")
    subscription.save(update_fields=fields)
    run.record_sent(action)


def due_subscriptions(today: date) -> QuerySet[ReportSubscription]:
    """Every active subscription whose ``next_due_on`` is ``today`` or earlier."""
    return ReportSubscription.objects.select_related("recipient_user", "created_by").filter(
        is_active=True, next_due_on__lte=today
    )


def send_subscription_now(
    subscription: ReportSubscription, *, actor: Model | str, today: date | None = None
) -> ReportRun:
    """Send ``subscription`` at once, whatever its date, and return the one-send run.

    It is sent as the daily run sends it, except that ``next_due_on`` stays where it
    is.  One ``report.send`` audit line names ``actor``, the subscription, and the
    counts.
    """
    day = timezone.localdate() if today is None else today
    run = ReportRun(today=day, dry_run=False)
    send_subscription(run, subscription, today=day, dry_run=False, advance=False)
    _record_send(run, actor=actor, target=subscription.pk, kind="subscription", since=(0, 0, 0))
    return run


# --------------------------------------------------------------------------
# DART rosters
# --------------------------------------------------------------------------
def roster_params(dart: Dart) -> Params:
    """The members report's params for ``dart``'s roster: its members, by name."""
    return {"dart": str(dart.pk), "ordering": "name", "columns": ",".join(ROSTER_COLUMNS)}


def month_start(today: date) -> datetime:
    """The first moment of ``today``'s month, in the local timezone."""
    return timezone.make_aware(datetime.combine(today.replace(day=1), time.min))


def due_rosters(today: date) -> QuerySet[Dart]:
    """Every active DART that has not been sent a roster in ``today``'s month."""
    return (
        Dart.objects.filter(is_active=True)
        .filter(Q(roster_sent_at__isnull=True) | Q(roster_sent_at__lt=month_start(today)))
        .prefetch_related("contacts")
        .order_by("name")
    )


def roster_member_count(dart: Dart) -> int:
    """How many members ``dart``'s roster lists, counted as the report selects them."""
    return apply_filterset(
        MemberAdminFilterSet, roster_params(dart), member_admin_queryset()
    ).count()


def send_roster_email(
    contact: DartContact, dart: Dart, document: ReportDocument, *, members: int, today: date
) -> None:
    """Email ``dart``'s roster, already built as ``document``, to one ticked person.

    The subject reads ``<DART name> roster (<Month D, YYYY>)`` and the body
    (``emails/dart_roster.{txt,html}``) says how many members the roster lists and
    that the DART's leaders may ask a CalDART account administrator to change who
    receives it.  The email log records it under the purpose ``dart_roster``.  A
    refusing mail server raises as :func:`~caldart.mail.send_templated` does.
    """
    context: dict[str, object] = {
        "org_name": org_name(),
        "contact_email": contact_email(),
        "name": contact.name,
        "dart_name": dart.name,
        "report_date": today,
        "members": members,
        "filename": document.filename,
    }
    send_templated(
        to=contact.email,
        subject=f"{dart.name} roster ({dateformat.format(today, PROSE_DATE)})",
        template="dart_roster",
        context=context,
        attachments=[(document.filename, document.content, document.media_type)],
        purpose="dart_roster",
    )


def send_roster(run: ReportRun, dart: Dart, *, today: date, dry_run: bool) -> None:
    """Send ``dart``'s roster to each person ticked to receive it, recorded on ``run``.

    A DART with no ticked person who has an address is skipped once as
    ``no_recipients``; otherwise each ticked person without one is skipped as
    ``no_email`` and everyone else is sent one email.  The roster is the members
    report for the DART, by name, with :data:`ROSTER_COLUMNS`, as a PDF built once.
    ``roster_sent_at`` is stamped when every email went out; a refused one is counted
    in ``failed`` and leaves the DART due, so the next run sends it again.  A dry run
    records the emails and writes nothing.
    """
    reachable = dart.roster_recipients()
    if not reachable:
        run.record_skipped("no_recipients")
        return
    ticked = [contact for contact in dart.contacts.all() if contact.receives_roster]
    for _unreachable in range(len(ticked) - len(reachable)):
        run.record_skipped("no_email")
    actions = [
        RunAction(kind=ROSTER_KIND, member=contact.name, email=contact.email, detail=dart.name)
        for contact in reachable
    ]
    if dry_run:
        for action in actions:
            run.record_sent(action)
        return
    document = build_report(MEMBER_REPORT, roster_params(dart), fmt="pdf", today=today)
    members = roster_member_count(dart)
    every_one_sent = True
    for contact, action in zip(reachable, actions, strict=True):
        try:
            send_roster_email(contact, dart, document, members=members, today=today)
        except SEND_ERRORS as exc:
            log.error(
                "roster send failed: dart=%s contact=%s error=%s",
                dart.pk,
                contact.pk,
                type(exc).__name__,
            )
            run.record_failed()
            every_one_sent = False
        else:
            run.record_sent(action)
    if every_one_sent:
        dart.roster_sent_at = timezone.now()
        dart.save(update_fields=["roster_sent_at", "updated_at"])


def send_rosters_now(
    *, dry_run: bool = False, actor: Model | str, today: date | None = None
) -> ReportRun:
    """Send every active DART's roster now, whatever the date, and return the run.

    Each DART is sent as the daily run sends it.  A live send writes one
    ``report.send`` audit line per DART, naming ``actor``, the DART and its counts; a
    dry run writes nothing at all.
    """
    day = timezone.localdate() if today is None else today
    run = ReportRun(today=day, dry_run=dry_run)
    darts = Dart.objects.filter(is_active=True).prefetch_related("contacts").order_by("name")
    for dart in darts:
        before = run.counts()
        send_roster(run, dart, today=day, dry_run=dry_run)
        if not dry_run:
            _record_send(run, actor=actor, target=dart.pk, kind="roster", since=before)
    return run


# --------------------------------------------------------------------------
# The run
# --------------------------------------------------------------------------
def run_scheduled_reports(
    *,
    today: date | None = None,
    dry_run: bool = False,
    actor: Model | str = audit.COMMAND_ACTOR,
) -> ReportRun:
    """Send every subscription and every DART roster that is due, and say what happened.

    First each active subscription whose ``next_due_on`` is ``today`` or earlier
    (:func:`send_subscription`, moving each sent one on to its next day), then each
    active DART not yet sent a roster in ``today``'s month (:func:`send_roster`).
    Nothing raises for one recipient: refusals are counted and retried by the next
    run.  A dry run writes nothing but records every email it would send.

    Every run ends with one ``reports.run`` audit line carrying the mode and the
    three counts; ``actor`` is the account that asked for it, or ``command`` for the
    management command and the daily timer.
    """
    day = timezone.localdate() if today is None else today
    run = ReportRun(today=day, dry_run=dry_run)
    for subscription in due_subscriptions(day):
        send_subscription(run, subscription, today=day, dry_run=dry_run, advance=True)
    for dart in due_rosters(day):
        send_roster(run, dart, today=day, dry_run=dry_run)
    audit.record(
        audit.REPORTS_RUN,
        actor=actor,
        dry_run=dry_run,
        sent=run.sent,
        skipped=run.skipped,
        failed=run.failed,
    )
    return run


def _record_send(
    run: ReportRun,
    *,
    actor: Model | str,
    target: int,
    kind: str,
    since: tuple[int, int, int],
) -> None:
    """Write one ``report.send`` line for the sends ``run`` counted after ``since``."""
    sent, skipped, failed = (now - then for now, then in zip(run.counts(), since, strict=True))
    audit.record(
        audit.REPORT_SEND,
        actor=actor,
        target=target,
        kind=kind,
        dry_run=run.dry_run,
        sent=sent,
        skipped=skipped,
        failed=failed,
    )
