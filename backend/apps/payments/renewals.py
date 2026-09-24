"""Automatic renewal: the standing authority, the scanner, and its emails.

A member who turns automatic renewal on gives CalDART a *mandate*: a payment
method saved with their provider, together with the plan and the contribution
it renews.  Nothing about the schedule lives at the provider -- no Stripe
subscription, no PayPal billing plan -- so the plan, the price, the term and
the reminder logic all stay here, in one place.

:func:`run_auto_renewals` is the one entry point the management command, ``POST
/system/renewals/run`` and the systemd timer all call.  It does three things,
in this order, for every mandate that is ``active``:

1. **Notice.**  A term running out within :data:`NOTICE_DAYS` of its charge date
   gets a :class:`~apps.payments.models.RenewalAttempt` scheduled
   :data:`CHARGE_LEAD_DAYS` before it expires, and the member is emailed the
   amount, the date and how to turn it off.
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

import calendar
import logging
import smtplib
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from django.conf import settings
from django.db import models, transaction
from django.db.models import Model
from django.utils import timezone

from apps.accounts.models import User
from apps.members.models import Membership, MembershipPlan, MembershipStatusChoices
from apps.payments.models import (
    MandateProvider,
    MandateStatus,
    Payment,
    PaymentStatus,
    RenewalAttempt,
    RenewalMandate,
    RenewalOutcome,
)
from apps.payments.providers.base import (
    MandateMethod,
    PaymentError,
    ProviderNotConfiguredError,
    ProviderUnavailableError,
    get_provider,
)
from apps.payments.receipts import receipt_filename, render_receipt_pdf
from apps.payments.services import create_checkout, mark_failed
from caldart import audit
from caldart.exceptions import DomainValidationError
from caldart.mail import Attachment, contact_email, org_name, send_templated
from caldart.reports import PDF_MEDIA_TYPE, money_label
from caldart.runs import CHARGE_KIND, RunAction, action_lines

log = logging.getLogger(__name__)

#: How many days before a term's ``ends_on`` the renewal is charged.  One: a
#: member is never charged for the coming year while a whole year of coverage
#: still remains.  A decline is therefore retried after the term has run out,
#: and the term the late charge buys starts on the day the money arrives.
CHARGE_LEAD_DAYS = 1

#: How many days before the charge the advance warning goes out.
NOTICE_DAYS = 14

#: Days after a failed charge that each retry is scheduled for, in order.  When
#: they are exhausted the mandate is paused.
RETRY_OFFSETS: tuple[int, ...] = (1, 3, 7)

#: How close to a card's expiry the member is warned that it will not last.
CARD_EXPIRY_WARNING_DAYS = 30

#: How long after a term ran out a scan may still renew it.  A scanner that was
#: down over a charge date catches up inside this window; past it the lapse is
#: too long for an unannounced charge to be the right thing to do, and the
#: mandate is paused instead.
CATCH_UP_DAYS = 30

#: What the member is told when their membership had lapsed too long to renew.
LAPSED_TOO_LONG_MESSAGE = (
    "your membership had lapsed for more than a month, so we did not take the renewal"
)

#: The field an input refusal about automatic renewal is keyed by.
AUTO_RENEW_FIELD = "auto_renew"

#: Why a mandate produced no charge on a given scan.
SKIP_REASONS: tuple[str, ...] = (
    "lifetime",
    "no_term",
    "not_active",
    "already_renewed",
    "no_plan",
    "in_flight",
    "provider_down",
)


class MandateKind(models.TextChoices):
    """What a standing authority charges for, which is what every email says.

    ``renewal`` renews a membership term and nothing else, ``both`` renews the
    term and takes a contribution alongside it, and ``contribution`` takes a
    contribution alone -- the only kind a life member can hold, since their
    membership never runs out.
    """

    RENEWAL = "renewal", "Renewal"
    BOTH = "both", "Renewal and contribution"
    CONTRIBUTION = "contribution", "Contribution"


#: The words every email and screen uses for each kind, in running prose.
KIND_LABELS: dict[str, str] = {
    MandateKind.RENEWAL: "renewal",
    MandateKind.BOTH: "renewal and contribution",
    MandateKind.CONTRIBUTION: "contribution",
}

#: Subject lines, in the house voice: plain, specific, no exclamation marks.
#: Keyed by template and then by the mandate's kind, because a contribution-only
#: mandate renews nothing and must never say it does.
SUBJECTS: dict[str, dict[str, str]] = {
    "renewal_enabled": {
        MandateKind.RENEWAL: "{org}: automatic renewal is on",
        MandateKind.BOTH: "{org}: automatic renewal is on",
        MandateKind.CONTRIBUTION: "{org}: automatic contribution is on",
    },
    "renewal_notice": {
        MandateKind.RENEWAL: "{org}: we will renew your membership on {charge_on}",
        MandateKind.BOTH: (
            "{org}: we will renew your membership and take your contribution on {charge_on}"
        ),
        MandateKind.CONTRIBUTION: "{org}: we will take your contribution on {charge_on}",
    },
    "renewal_card_expiring": {
        MandateKind.RENEWAL: "{org}: the card we renew your membership with expires soon",
        MandateKind.BOTH: "{org}: the card we renew your membership with expires soon",
        MandateKind.CONTRIBUTION: "{org}: the card we take your contribution with expires soon",
    },
    "renewal_charged": {
        MandateKind.RENEWAL: "{org}: your membership has been renewed",
        MandateKind.BOTH: "{org}: your membership has been renewed",
        MandateKind.CONTRIBUTION: "{org}: thank you for your contribution",
    },
    "renewal_failed": {
        MandateKind.RENEWAL: "{org}: we could not renew your membership",
        MandateKind.BOTH: "{org}: we could not renew your membership",
        MandateKind.CONTRIBUTION: "{org}: we could not take your contribution",
    },
    "renewal_canceled": {
        MandateKind.RENEWAL: "{org}: automatic renewal is off",
        MandateKind.BOTH: "{org}: automatic renewal is off",
        MandateKind.CONTRIBUTION: "{org}: automatic contribution is off",
    },
}

#: What a life member is told when they ask for a plan to renew.
LIFE_MEMBER_PLAN_MESSAGE = (
    "A life member's membership does not renew; choose a contribution instead."
)

#: What a life member is told when they ask for a standing authority over nothing.
LIFE_MEMBER_CONTRIBUTION_MESSAGE = "A contribution to charge each year is needed."


# --------------------------------------------------------------------------
# Dates
# --------------------------------------------------------------------------
def payments_url() -> str:
    """Absolute link to the portal's payments screen, which every email carries."""
    return f"{settings.SITE_URL.rstrip('/')}/portal/payments"


def charge_date_for(ends_on: date) -> date:
    """The day a renewal is charged: :data:`CHARGE_LEAD_DAYS` before ``ends_on``."""
    return ends_on - timedelta(days=CHARGE_LEAD_DAYS)


def card_expires_on(mandate: RenewalMandate) -> date | None:
    """The last day the mandate's card works, or ``None`` when it has no expiry.

    A card expires at the end of its printed month, so an expiry of 03/2028 gives
    31 March 2028.  A mandate on a method that is not a card -- a PayPal balance,
    say -- has no expiry month or year and gives ``None``.
    """
    if mandate.method_exp_year is None or mandate.method_exp_month is None:
        return None
    last_day = calendar.monthrange(mandate.method_exp_year, mandate.method_exp_month)[1]
    return date(mandate.method_exp_year, mandate.method_exp_month, last_day)


def term_to_renew(user: User, today: date) -> Membership | None:
    """The active term whose expiry a mandate for ``user`` would renew.

    That is the active term that runs furthest into the future and has not run
    out on ``today``.  ``None`` when the member holds no such term, and ``None``
    as well when any active term is a lifetime one: a lifetime membership never
    needs renewing.

    The member's terms are walked in Python rather than filtered in the database,
    so a caller that has prefetched ``memberships`` -- the finance list does --
    costs no query per member.
    """
    active = [m for m in user.memberships.all() if m.status == MembershipStatusChoices.ACTIVE]
    if any(term.ends_on is None for term in active):
        return None
    dated = [term for term in active if term.ends_on is not None and term.ends_on >= today]
    if len(dated) == 0:
        return None
    return max(dated, key=lambda term: (term.ends_on, term.id))


def lapsed_term_to_renew(user: User, today: date) -> Membership | None:
    """The most recent dated term that has already run out, or ``None``.

    This is the term a scan that missed its charge date would be catching up to:
    the ``active`` or ``expired`` term with the latest ``ends_on`` before
    ``today``.  A canceled term bought nothing that can be renewed and is not
    considered.  ``None`` when the member holds no such term, and ``None`` as
    well when any term of theirs is a lifetime one, which never needs renewing.

    The member's terms are walked in Python, so a caller that has prefetched
    ``memberships`` costs no query per member.
    """
    renewable = (MembershipStatusChoices.ACTIVE, MembershipStatusChoices.EXPIRED)
    terms = [m for m in user.memberships.all() if m.status in renewable]
    if any(term.ends_on is None for term in terms):
        return None
    dated = [term for term in terms if term.ends_on is not None and term.ends_on < today]
    if len(dated) == 0:
        return None
    return max(dated, key=lambda term: (term.ends_on, term.id))


def lifetime_term(user: User) -> Membership | None:
    """The member's active lifetime term, or ``None`` when they hold none.

    A lifetime term is an ``active`` membership with no ``ends_on``.  The terms
    are walked in Python, so a caller that has prefetched ``memberships`` costs
    no query per member.
    """
    for term in user.memberships.all():
        if term.status == MembershipStatusChoices.ACTIVE and term.ends_on is None:
            return term
    return None


def mandate_kind(mandate: RenewalMandate) -> str:
    """Which of :class:`MandateKind` ``mandate`` is, read off its plan and amount.

    ``contribution`` when it names no plan, ``both`` when it names a plan and
    carries a contribution, and ``renewal`` when it names a plan alone.
    """
    if mandate.plan_id is None:
        return MandateKind.CONTRIBUTION
    if mandate.contribution_cents > 0:
        return MandateKind.BOTH
    return MandateKind.RENEWAL


def kind_label(kind: str) -> str:
    """The words for ``kind`` in running prose: ``renewal and contribution`` and so on.

    Raises ``KeyError`` for anything outside :class:`MandateKind`.
    """
    return KIND_LABELS[kind]


def next_anniversary(anchor: date) -> date:
    """One year after ``anchor``, with 29 February answered as 28 February.

    Every other date keeps its day and month, so 3 March 2026 gives 3 March 2027.
    """
    try:
        return anchor.replace(year=anchor.year + 1)
    except ValueError:
        return date(anchor.year + 1, 2, 28)


def contribution_charge_date(mandate: RenewalMandate, today: date) -> date:
    """The day a contribution-only mandate is next charged.

    One year after the local date of the last charge, or of the day the mandate
    was created when nothing has been charged yet.  An anniversary that has
    already gone by -- because the scanner was not running on it -- is answered
    as ``today``, since that is the day the next scan takes it.
    """
    charged = mandate.last_charged_at or mandate.created_at
    return max(next_anniversary(timezone.localtime(charged).date()), today)


def next_charge_on(mandate: RenewalMandate, today: date | None = None) -> date | None:
    """The day ``mandate`` will next be charged, as the portal shows it.

    ``None`` for a mandate that is not ``active``, and a date for every mandate
    that is: a scheduled attempt's own date when one is waiting; otherwise, for a
    contribution-only mandate, :func:`contribution_charge_date`; otherwise the
    charge date of the member's current dated term; and otherwise ``today``,
    because the term has run out and the next scan is what charges it.

    The attempts are walked in Python, so a caller that has prefetched
    ``attempts`` costs no query per mandate.
    """
    if mandate.status != MandateStatus.ACTIVE:
        return None
    today = today or timezone.localdate()
    scheduled = [
        attempt.scheduled_on
        for attempt in mandate.attempts.all()
        if attempt.outcome == RenewalOutcome.SCHEDULED
    ]
    if len(scheduled) > 0:
        return min(scheduled)
    if mandate.plan_id is None:
        return contribution_charge_date(mandate, today)
    term = term_to_renew(mandate.user, today)
    if term is None or term.ends_on is None:
        return today
    return charge_date_for(term.ends_on)


def renewal_amount_cents(mandate: RenewalMandate) -> int:
    """What the next charge comes to: the plan's price plus the contribution.

    A contribution-only mandate names no plan, so its next charge is the
    contribution alone.
    """
    plan_cents = mandate.plan.price_cents if mandate.plan is not None else 0
    return plan_cents + mandate.contribution_cents


# --------------------------------------------------------------------------
# Email
# --------------------------------------------------------------------------
def mandate_context(mandate: RenewalMandate, **extra: Any) -> dict[str, Any]:
    """The template context every renewal email shares, plus ``extra``.

    Carries the member's first name, the organization's name and contact
    address, the plan, the amount as the member reads it, the saved method's
    label and the link to the portal's payments screen.  ``kind`` is the
    mandate's :class:`MandateKind` and ``kind_label`` the words for it, which is
    how each template tells a renewal from a contribution.  ``plan_name`` is an
    empty string for a contribution-only mandate, which names no plan.
    """
    amount_cents = renewal_amount_cents(mandate)
    kind = mandate_kind(mandate)
    context: dict[str, Any] = {
        "first_name": mandate.user.first_name or mandate.user.display_name,
        "org_name": org_name(),
        "contact_email": contact_email(),
        "kind": kind,
        "kind_label": kind_label(kind),
        "plan_name": mandate.plan.name if mandate.plan is not None else "",
        "amount": money_label(amount_cents),
        "amount_cents": amount_cents,
        "contribution": money_label(mandate.contribution_cents),
        "contribution_cents": mandate.contribution_cents,
        "method_label": mandate.method_label,
        "payments_url": payments_url(),
        "site_url": settings.SITE_URL.rstrip("/"),
    }
    context.update(extra)
    return context


def send_mandate_email(
    mandate: RenewalMandate,
    template: str,
    *,
    attachments: Sequence[Attachment] = (),
    **extra: Any,
) -> bool:
    """Send one renewal email to the mandate's member, and say whether it went.

    The subject comes from :data:`SUBJECTS` with the organization's name filled
    in, and the body from ``emails/<template>.{txt,html}`` rendered over
    :func:`mandate_context`.  Each entry of ``attachments`` is a filename, its
    bytes and its media type, which is how the charge report carries the
    receipt.  A member with no email address is not written to.

    A mail server that refuses the message is logged at ERROR and answered
    ``False`` rather than raised: one member's mail problem never stops a scan,
    and the timestamp that would have recorded the send stays unset.  The advance
    notice and the card-expiry warning are sent again on the next run because of
    that; the message that reports a charge or a decline is not resent, since the
    attempt it belongs to is already closed.
    """
    if not mandate.user.email:
        return False
    context = mandate_context(mandate, **extra)
    subject = SUBJECTS[template][context["kind"]].format(org=context["org_name"], **extra)
    try:
        send_templated(
            to=mandate.user.email,
            subject=subject,
            template=template,
            context=context,
            attachments=attachments,
        )
    except (smtplib.SMTPException, OSError) as exc:
        log.error(
            "renewal email failed: template=%s mandate=%s error=%s",
            template,
            mandate.pk,
            type(exc).__name__,
        )
        return False
    return True


# --------------------------------------------------------------------------
# The mandate's life cycle
# --------------------------------------------------------------------------
def check_renewable(
    plan: MembershipPlan | None, provider: str, *, user: User, contribution_cents: int
) -> MembershipPlan | None:
    """Refuse a mandate that could never be charged again, and return its plan.

    A member who already holds an active lifetime term may hold a
    contribution-only mandate and nothing else: ``plan`` must be ``None`` and
    ``contribution_cents`` must be more than nothing, and ``None`` comes back.
    Every other member needs a plan with a duration, which comes back as given.

    Raises ``DomainValidationError`` keyed by :data:`AUTO_RENEW_FIELD` when the
    provider cannot charge again without the member -- which is every provider
    outside :class:`~apps.payments.models.MandateProvider` -- when a life member
    asks for a plan or for no contribution, when a member who is not a life
    member gives no plan, and when the plan is a lifetime one.
    """
    if provider not in MandateProvider.values:
        raise DomainValidationError(
            AUTO_RENEW_FIELD, f"'{provider}' cannot charge a saved payment method."
        )
    if lifetime_term(user) is not None:
        if plan is not None:
            raise DomainValidationError(AUTO_RENEW_FIELD, LIFE_MEMBER_PLAN_MESSAGE)
        if contribution_cents <= 0:
            raise DomainValidationError(AUTO_RENEW_FIELD, LIFE_MEMBER_CONTRIBUTION_MESSAGE)
        return None
    if plan is None:
        raise DomainValidationError(
            AUTO_RENEW_FIELD, "Automatic renewal needs a membership plan to renew."
        )
    if plan.duration_days is None:
        raise DomainValidationError(
            AUTO_RENEW_FIELD, "A lifetime membership never expires, so it cannot renew itself."
        )
    return plan


@transaction.atomic
def begin_mandate(
    user: User,
    *,
    plan: MembershipPlan | None,
    contribution_cents: int,
    provider: str,
) -> RenewalMandate:
    """Create or reset the member's ``pending`` mandate, before anything is saved.

    A member has at most one mandate, so turning automatic renewal on again --
    at a checkout, or from the portal -- replaces whatever authority was there
    with a pending one carrying the plan, the contribution and the provider now
    asked for, and no saved method.  It becomes ``active`` only when the method
    is confirmed, through :func:`save_method`.

    A life member's mandate carries no plan: it is a standing authority for the
    contribution alone.

    Raises ``DomainValidationError`` keyed by :data:`AUTO_RENEW_FIELD` for
    anything :func:`check_renewable` refuses, and writes nothing when it does.
    """
    renewable = check_renewable(plan, provider, user=user, contribution_cents=contribution_cents)
    mandate, _ = RenewalMandate.objects.update_or_create(
        user=user,
        defaults={
            "plan": renewable,
            "contribution_cents": contribution_cents,
            "provider": provider,
            "status": MandateStatus.PENDING,
            "customer_ref": "",
            "method_ref": "",
            "method_brand": "",
            "method_last4": "",
            "method_exp_month": None,
            "method_exp_year": None,
            "method_label": "",
            "failure_count": 0,
            "canceled_at": None,
            "canceled_by": None,
            "raw": {},
        },
    )
    return mandate


@transaction.atomic
def save_method(
    mandate: RenewalMandate, method: MandateMethod, *, actor: Model | str
) -> RenewalMandate:
    """Store the saved payment method on ``mandate`` and make it ``active``.

    Clears the failure count and any cancellation, writes one ``renewal.enable``
    audit record, and emails the member that automatic renewal is on, naming the
    plan, the amount, the method and the next charge date.  The email is sent
    after the transaction commits, so a rollback tells nobody anything.
    """
    mandate.customer_ref = method.customer_ref or mandate.customer_ref
    mandate.method_ref = method.method_ref
    mandate.method_brand = method.brand
    mandate.method_last4 = method.last4
    mandate.method_exp_month = method.exp_month
    mandate.method_exp_year = method.exp_year
    mandate.method_label = method.label
    mandate.status = MandateStatus.ACTIVE
    mandate.failure_count = 0
    mandate.canceled_at = None
    mandate.canceled_by = None
    mandate.raw = method.raw
    mandate.save()

    audit.record(
        audit.RENEWAL_ENABLE,
        actor=actor,
        target=mandate.user,
        provider=mandate.provider,
        plan=mandate.plan.slug if mandate.plan is not None else "",
    )
    charge_on = next_charge_on(mandate)
    transaction.on_commit(
        lambda: send_mandate_email(mandate, "renewal_enabled", next_charge_on=charge_on)
    )
    return mandate


@transaction.atomic
def cancel_mandate(mandate: RenewalMandate, *, actor: User | None) -> RenewalMandate:
    """Turn automatic renewal off, whoever asked, and tell the member.

    ``actor`` is the member themselves or the administrator who turned it off,
    and is recorded as ``canceled_by`` and in the audit record's
    ``self_service`` flag; it is ``None`` for a cancellation nobody signed for.
    Every scheduled attempt still waiting is marked ``skipped``, so the next scan
    charges nothing.  Writes one ``renewal.cancel`` audit record
    and emails the member after the transaction commits.  Calling it on a
    mandate that is already canceled changes nothing and sends nothing.
    """
    if mandate.status == MandateStatus.CANCELED:
        return mandate
    mandate.status = MandateStatus.CANCELED
    mandate.canceled_at = timezone.now()
    mandate.canceled_by = actor
    mandate.save(update_fields=["status", "canceled_at", "canceled_by", "updated_at"])
    mandate.attempts.filter(outcome=RenewalOutcome.SCHEDULED).update(outcome=RenewalOutcome.SKIPPED)
    audit.record(
        audit.RENEWAL_CANCEL,
        actor=actor or audit.COMMAND_ACTOR,
        target=mandate.user,
        provider=mandate.provider,
        self_service=actor is not None and actor.pk == mandate.user_id,
    )
    transaction.on_commit(lambda: send_mandate_email(mandate, "renewal_canceled"))
    return mandate


def pending_mandate_for(payment: Payment) -> RenewalMandate | None:
    """The ``pending`` mandate this payment would activate, or ``None``.

    A mandate only matches when it is the payer's own, is still pending, names
    the provider the payment is being taken with, and renews exactly what the
    payment buys -- the same plan and the same contribution.  A member who
    started a Stripe mandate and then paid with PayPal activates nothing, and
    neither does a checkout for some other plan that happens to follow an
    abandoned one: a mandate is the authority the payer asked for at *this*
    checkout, never one left over from another.
    """
    mandate = RenewalMandate.objects.filter(
        user_id=payment.user_id, status=MandateStatus.PENDING
    ).first()
    if mandate is None or mandate.provider != payment.provider:
        return None
    if mandate.plan_id != payment.plan_id:
        return None
    if mandate.contribution_cents != payment.contribution_cents:
        return None
    return mandate


def discard_pending_mandate(user: User) -> None:
    """Throw away the member's ``pending`` mandate, if they hold one.

    A pending mandate has no saved method, has charged nothing and has never been
    announced to anybody, so a checkout that declines automatic renewal deletes it
    outright rather than canceling it: there is no standing authority to withdraw
    and nothing to tell the member.  A mandate in any other state is left alone.
    """
    RenewalMandate.objects.filter(user=user, status=MandateStatus.PENDING).delete()


def activate_pending_mandate(payment: Payment) -> RenewalMandate | None:
    """Activate the mandate a succeeded checkout was asked to save, if any.

    Called from :func:`apps.payments.services.mark_succeeded`, so a checkout that
    asked for automatic renewal needs no second round trip: the method the member
    just paid with is read back off the provider's own record of the charge.
    Returns the activated mandate, or ``None`` when the payment saved no method
    or there was no pending mandate to activate.
    """
    mandate = pending_mandate_for(payment)
    if mandate is None:
        return None
    method = get_provider(payment.provider).method_from_payment(payment)
    if method is None:
        log.warning(
            "payment %s was to start a mandate but %s saved no method",
            payment.pk,
            payment.provider,
        )
        return None
    return save_method(mandate, method, actor=payment.user)


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
    a provider that cannot be reached and a mail server that refuses a message
    are each recorded against that member's attempt and the walk carries on.
    Every run ends with one ``renewals.run`` audit record carrying the mode and
    the counts, and returns them as a :class:`RenewalRun`, whose ``actions`` name
    every member the run emailed or charged -- or, in a rehearsal, would have.
    """
    today = today or timezone.localdate()
    run = RenewalRun(today=today, dry_run=dry_run)

    for mandate in active_mandates():
        _notice(mandate, today, run, dry_run=dry_run)
        _warn_about_card(mandate, today, run, dry_run=dry_run)

    for attempt in _due_attempts(today):
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


def _notice(mandate: RenewalMandate, today: date, run: RenewalRun, *, dry_run: bool) -> None:
    """Schedule the charge for a term running out, and email the warning.

    Only an attempt that is still ``scheduled`` or has already ``succeeded``
    stands in the way of a fresh one, so a mandate that was paused over a term and
    then turned back on is scheduled again rather than left to lapse quietly.  An
    attempt that is waiting but whose notice never went out -- a mail server that
    refused it -- is written to again here.
    """
    if mandate.plan_id is None:
        _notice_contribution(mandate, today, run, dry_run=dry_run)
        return
    if lifetime_term(mandate.user) is not None:
        # The member has been granted a lifetime term since the mandate was made,
        # so there is no expiry left for it to renew.
        run.record_skipped("lifetime")
        return
    term = term_to_renew(mandate.user, today)
    if term is None or term.ends_on is None:
        _catch_up(mandate, today, run, dry_run=dry_run)
        return
    waiting = (
        mandate.attempts.filter(
            membership=term,
            outcome__in=(RenewalOutcome.SCHEDULED, RenewalOutcome.SUCCEEDED),
        )
        .order_by("-pk")
        .first()
    )
    if waiting is not None and (
        waiting.outcome != RenewalOutcome.SCHEDULED or waiting.noticed_at is not None
    ):
        return
    charge_on = waiting.scheduled_on if waiting is not None else charge_date_for(term.ends_on)
    # A scan that was down over the charge date takes it today rather than
    # writing to the member about a date that has already gone by.
    charge_on = max(charge_on, today)
    if (charge_on - today).days > NOTICE_DAYS:
        return

    run.noticed += 1
    run.record_action("renewal_notice", mandate, on=charge_on)
    if dry_run:
        return
    attempt = waiting or RenewalAttempt.objects.create(
        mandate=mandate, membership=term, scheduled_on=charge_on
    )
    _send_notice(mandate, attempt, charge_on, term.ends_on, today)


def _notice_contribution(
    mandate: RenewalMandate, today: date, run: RenewalRun, *, dry_run: bool
) -> None:
    """Schedule and announce the yearly charge of a contribution-only mandate.

    The charge date is :func:`contribution_charge_date`, and the attempt is
    written against the member's lifetime term, which is what their standing
    authority sits alongside.  A member who no longer holds one is skipped as
    ``no_term``: there is nothing for the contribution to accompany.  An attempt
    already waiting is reused, and one whose notice the mail server refused is
    written to again here.
    """
    term = lifetime_term(mandate.user)
    if term is None:
        run.record_skipped("no_term")
        return
    waiting = next(
        (
            attempt
            for attempt in mandate.attempts.filter(outcome=RenewalOutcome.SCHEDULED).order_by("pk")
        ),
        None,
    )
    if waiting is not None and waiting.noticed_at is not None:
        return
    charge_on = (
        waiting.scheduled_on if waiting is not None else contribution_charge_date(mandate, today)
    )
    charge_on = max(charge_on, today)
    if (charge_on - today).days > NOTICE_DAYS:
        return

    run.noticed += 1
    run.record_action("renewal_notice", mandate, on=charge_on)
    if dry_run:
        return
    attempt = waiting or RenewalAttempt.objects.create(
        mandate=mandate, membership=term, scheduled_on=charge_on
    )
    _send_notice(mandate, attempt, charge_on, None, today)


def _catch_up(mandate: RenewalMandate, today: date, run: RenewalRun, *, dry_run: bool) -> None:
    """Renew a term that already ran out, or pause a mandate too far behind to.

    Reached for a mandate whose member holds no term left to renew.  While the
    ordinary reminders are skipped for an active mandate, this is the only thing
    that stops such a member lapsing unnoticed, so a term that ran out within
    :data:`CATCH_UP_DAYS` is renewed here: the attempt is dated today, the notice
    says the charge is happening today, and the charge step of the same run takes
    it.  A term that ran out longer ago pauses the mandate and tells the member
    why, and the ordinary reminders resume for them.

    A term that already has an attempt against it is left alone: it is on the
    retry ladder, not behind the scanner.
    """
    term = lapsed_term_to_renew(mandate.user, today)
    if term is None or term.ends_on is None:
        run.record_skipped("no_term")
        return
    if mandate.attempts.filter(membership=term).exists():
        return
    if (today - term.ends_on).days > CATCH_UP_DAYS:
        _abandon(mandate, run, dry_run=dry_run)
        return

    run.noticed += 1
    run.record_action("renewal_notice", mandate, on=today)
    if dry_run:
        return
    attempt = RenewalAttempt.objects.create(mandate=mandate, membership=term, scheduled_on=today)
    _send_notice(mandate, attempt, today, term.ends_on, today)


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
    """
    run.paused += 1
    run.record_action("renewal_failed", mandate, detail=LAPSED_TOO_LONG_MESSAGE)
    if dry_run:
        return
    mandate.status = MandateStatus.PAUSED
    mandate.save(update_fields=["status", "updated_at"])
    send_mandate_email(
        mandate, "renewal_failed", error=LAPSED_TOO_LONG_MESSAGE, next_on=None, lapsed=True
    )


def _warn_about_card(
    mandate: RenewalMandate, today: date, run: RenewalRun, *, dry_run: bool
) -> None:
    """Warn once that the card on file will not last until the next charge."""
    expires_on = card_expires_on(mandate)
    charge_on = next_charge_on(mandate, today)
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
    if mandate.plan_id is not None and lifetime_term(mandate.user) is not None:
        run.record_skipped("lifetime")
        if not dry_run:
            _finish(attempt, RenewalOutcome.SKIPPED)
        return
    if _already_renewed(attempt, today):
        run.record_skipped("already_renewed")
        if not dry_run:
            _finish(attempt, RenewalOutcome.SKIPPED)
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
    except (ProviderUnavailableError, ProviderNotConfiguredError) as exc:
        _postpone(attempt, payment, str(exc), run)
        return
    except PaymentError as exc:
        _record_failure(attempt, payment, str(exc), today, run)
        return

    _record_success(attempt, run)


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

    A provider that cannot be reached, or that is not configured, says nothing
    about the member's card, so it costs no rung of the retry ladder, sends no
    decline notice and does not pause the mandate.  The pending payment is thrown
    away and the attempt is released, still scheduled for the same day, so the
    next scan tries it again.
    """
    log.error("renewal attempt %s could not reach %s: %s", attempt.pk, payment.provider, reason)
    attempt.payment = None
    attempt.attempted_at = None
    attempt.save(update_fields=["payment", "attempted_at", "updated_at"])
    payment.delete()
    run.record_skipped("provider_down")


def _already_renewed(attempt: RenewalAttempt, today: date) -> bool:
    """Whether the member's coverage already reaches past the term being renewed.

    True when another term has been bought or granted since the attempt was
    scheduled, which is what a member paying by hand in the meantime looks like.
    Always false for a contribution-only mandate, which renews no term and so can
    never be overtaken by one.
    """
    if attempt.mandate.plan_id is None:
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
    """Mark the attempt succeeded, clear the failures, and tell the member."""
    mandate = attempt.mandate
    now = timezone.now()
    mandate.failure_count = 0
    mandate.last_charged_at = now
    mandate.save(update_fields=["failure_count", "last_charged_at", "updated_at"])

    attempt.outcome = RenewalOutcome.SUCCEEDED
    attempt.save(update_fields=["outcome", "updated_at"])

    today = timezone.localdate()
    renewed = term_to_renew(mandate.user, today)
    charge_on = next_charge_on(mandate, today)
    payment = attempt.payment
    attachments: list[Attachment] = []
    if payment is not None:
        attachments.append((receipt_filename(payment), render_receipt_pdf(payment), PDF_MEDIA_TYPE))
    if send_mandate_email(
        mandate,
        "renewal_charged",
        expires_on=renewed.ends_on if renewed is not None else None,
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
    renewal is off and the ordinary reminders resume.
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
    run.record_action("renewal_failed", mandate, on=next_on, detail=attempt.error)
    if send_mandate_email(mandate, "renewal_failed", error=attempt.error, next_on=next_on):
        attempt.result_emailed_at = timezone.now()
    attempt.save(update_fields=["outcome", "error", "result_emailed_at", "updated_at"])

    if next_on is not None:
        RenewalAttempt.objects.create(
            mandate=mandate,
            membership=attempt.membership,
            scheduled_on=next_on,
            retry_of=attempt,
            noticed_at=attempt.noticed_at,
        )
    run.failed += 1
