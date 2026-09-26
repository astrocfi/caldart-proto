"""Scheduled charges: the standing authority, the scanner, and its emails.

Somebody who asks CalDART to charge them on a schedule gives it a *mandate*: a
payment method saved with their provider, together with what it pays for.  A
mandate comes in two kinds, and a person holds at most one of each: an
**automatic renewal** names a plan and renews the membership once a year, with a
contribution beside the dues if they chose one, and a **recurring donation** names
no plan and gives a contribution alone, monthly, quarterly or yearly.  Nothing
about the schedule lives at the provider -- no Stripe subscription, no PayPal
billing plan -- so the plan, the price, the term, the cadence and the reminder
logic all stay here, in one place.

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

import calendar
import logging
import smtplib
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from django.conf import settings
from django.db import IntegrityError, models, transaction
from django.db.models import Model
from django.utils import timezone

from apps.accounts.models import AccountKind, User
from apps.members.models import Membership, MembershipPlan, MembershipStatusChoices
from apps.members.services import account_kind, become_friend, check_can_become_friend
from apps.payments.models import (
    MandateCadence,
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
from caldart.exceptions import DomainError, DomainValidationError
from caldart.mail import Attachment, contact_email, org_name, send_templated
from caldart.reports import PDF_MEDIA_TYPE, money_label
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

#: The field an input refusal about automatic renewal is keyed by.
AUTO_RENEW_FIELD = "auto_renew"

#: What a member is told when they ask to be charged on a day that has gone.
PAST_CHARGE_DATE_MESSAGE = "The next charge cannot be in the past."

#: The key on a pending mandate's ``raw`` that records that the member named the
#: charge date themselves, so the checkout that activates it leaves the date alone.
CHOSEN_DATE_KEY = "next_charge_on_chosen"

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


class MandateKind(models.TextChoices):
    """What a standing authority charges for, which is what every email says.

    ``renewal`` renews a membership term and nothing else, ``both`` renews the
    term and takes a contribution alongside it, and ``contribution`` is a
    recurring donation: a contribution alone, on its own schedule, which is the only
    kind a life member or a friend holds, since neither has dues to renew.
    """

    RENEWAL = "renewal", "Automatic renewal"
    BOTH = "both", "Automatic renewal and contribution"
    CONTRIBUTION = "contribution", "Recurring donation"


#: The words every email and screen uses for each kind, in running prose.
KIND_LABELS: dict[str, str] = {
    MandateKind.RENEWAL: "automatic renewal",
    MandateKind.BOTH: "automatic renewal and contribution",
    MandateKind.CONTRIBUTION: "recurring donation",
}

#: How often each cadence charges, in running prose: "we will charge $25.00 each
#: month".
CADENCE_PHRASES: dict[str, str] = {
    MandateCadence.MONTHLY: "each month",
    MandateCadence.QUARTERLY: "each quarter",
    MandateCadence.YEARLY: "each year",
}

#: How many months each cadence moves the next charge on by.
CADENCE_MONTHS: dict[str, int] = {
    MandateCadence.MONTHLY: 1,
    MandateCadence.QUARTERLY: 3,
    MandateCadence.YEARLY: 12,
}

#: Subject lines, in the house voice: plain, specific, no exclamation marks.
#: Keyed by template and then by the mandate's kind, because a recurring donation
#: renews nothing and must never say it does.
SUBJECTS: dict[str, dict[str, str]] = {
    "renewal_enabled": {
        MandateKind.RENEWAL: "{org}: automatic renewal is on",
        MandateKind.BOTH: "{org}: automatic renewal is on",
        MandateKind.CONTRIBUTION: "{org}: your recurring donation is on",
    },
    "renewal_notice": {
        MandateKind.RENEWAL: "{org}: we will renew your membership on {charge_on}",
        MandateKind.BOTH: (
            "{org}: we will renew your membership and take your contribution on {charge_on}"
        ),
        MandateKind.CONTRIBUTION: "{org}: we will take your recurring donation on {charge_on}",
    },
    "renewal_card_expiring": {
        MandateKind.RENEWAL: "{org}: the card we renew your membership with expires soon",
        MandateKind.BOTH: "{org}: the card we renew your membership with expires soon",
        MandateKind.CONTRIBUTION: (
            "{org}: the card we take your recurring donation with expires soon"
        ),
    },
    "renewal_charged": {
        MandateKind.RENEWAL: "{org}: your membership has been renewed",
        MandateKind.BOTH: "{org}: your membership has been renewed",
        MandateKind.CONTRIBUTION: "{org}: thank you for your recurring donation",
    },
    "renewal_failed": {
        MandateKind.RENEWAL: "{org}: we could not renew your membership",
        MandateKind.BOTH: "{org}: we could not renew your membership",
        MandateKind.CONTRIBUTION: "{org}: we could not take your recurring donation",
    },
    "renewal_canceled": {
        MandateKind.RENEWAL: "{org}: automatic renewal is off",
        MandateKind.BOTH: "{org}: automatic renewal is off",
        MandateKind.CONTRIBUTION: "{org}: your recurring donation is off",
    },
}

#: What a life member is told when they ask for a plan to renew.
LIFE_MEMBER_PLAN_MESSAGE = (
    "A life member's membership does not renew; choose a contribution instead."
)

#: What somebody is told when they ask for a recurring donation of nothing.
DONATION_AMOUNT_MESSAGE = "A recurring donation needs an amount to give."

#: What somebody is told when they ask for an automatic renewal with no plan.
RENEWAL_PLAN_MESSAGE = "Automatic renewal needs a membership plan to renew."

#: What somebody is told when they ask for a renewal on any cadence but yearly.
YEARLY_ONLY_MESSAGE = "Automatic renewal is charged once a year."

#: What a member holding a recurring donation is told when they ask for a
#: contribution on their renewal as well: a contribution lives in one place.
HAS_DONATION_MESSAGE = "You already have a recurring donation. Change it on the Donate screen."

#: The field the refusal above is keyed by.
CONTRIBUTION_FIELD = "contribution_cents"

#: What a member whose renewal already takes a contribution is told when they ask
#: for a recurring donation, with the amount filled in.
RENEWAL_CONTRIBUTION_MESSAGE = (
    "Your automatic renewal already includes a contribution of {amount} a year. Set up a "
    "recurring donation and that contribution comes off the renewal; your dues still "
    "renew automatically."
)

#: The ``code`` the refusal above carries, which the portal answers with a
#: **Continue** button that resends the request with the renewal's contribution
#: removed.
RENEWAL_CONTRIBUTION_CODE = "renewal_contribution"


class RenewalContributionError(DomainError):
    """A recurring donation asked for while the member's renewal takes a contribution.

    ``contribution_cents`` is what the renewal takes each year.  The API renders
    this as ``400 {"detail": <message>, "code": "renewal_contribution"}``.
    """

    def __init__(self, contribution_cents: int) -> None:
        """Build the refusal for a renewal that takes ``contribution_cents`` a year."""
        super().__init__(
            RENEWAL_CONTRIBUTION_MESSAGE.format(amount=money_label(contribution_cents))
        )
        self.contribution_cents = contribution_cents


# --------------------------------------------------------------------------
# Dates
# --------------------------------------------------------------------------
def payments_url() -> str:
    """Absolute link to the portal's payments screen, which every email carries."""
    return f"{settings.SITE_URL.rstrip('/')}/portal/payments"


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
    """The words for ``kind`` in running prose: ``recurring donation`` and so on.

    Raises ``KeyError`` for anything outside :class:`MandateKind`.
    """
    return KIND_LABELS[kind]


def advance_by_cadence(day: date, cadence: str) -> date:
    """``day`` moved on by one ``cadence``: one month, three months, or twelve.

    The day of the month is kept where the later month has it, and clamped to that
    month's last day where it does not: 31 January 2026 monthly gives 28 February
    2026, and 29 February 2028 yearly gives 28 February 2029.  Raises ``KeyError``
    for anything outside :class:`~apps.payments.models.MandateCadence`.
    """
    months = day.month - 1 + CADENCE_MONTHS[cadence]
    year = day.year + months // 12
    month = months % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def default_charge_date(user: User, today: date) -> date:
    """The day a renewal for ``user`` is charged on when they name none themselves.

    The ``ends_on`` of their current dated term, so a renewal falls on the day the
    membership runs out and the coverage carries straight on, and ``today`` for a
    member who holds none, since there is no later day to wait for.
    """
    term = term_to_renew(user, today)
    if term is not None and term.ends_on is not None:
        return term.ends_on
    return today


def charge_date(mandate: RenewalMandate, today: date | None = None) -> date | None:
    """The day ``mandate`` will next be charged, as the portal shows it.

    ``None`` for a mandate that is not ``active``, and a date for every mandate
    that is: the earliest ``scheduled`` attempt's own date when one is waiting, and
    otherwise the stored ``next_charge_on``, or ``today`` when that has already
    gone by -- because the next scan is what takes a charge the scanner missed.

    ``today`` defaults to the current local date.  The attempts are walked in
    Python, so a caller that has prefetched ``attempts`` costs no query per
    mandate.
    """
    if mandate.status != MandateStatus.ACTIVE:
        return None
    if today is None:
        today = timezone.localdate()
    scheduled = [
        attempt.scheduled_on
        for attempt in mandate.attempts.all()
        if attempt.outcome == RenewalOutcome.SCHEDULED
    ]
    if len(scheduled) > 0:
        return min(scheduled)
    return max(mandate.next_charge_on, today)


def renewal_amount_cents(mandate: RenewalMandate) -> int:
    """What the next charge comes to: the plan's price plus the contribution.

    A recurring donation names no plan, so its next charge is the
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
    how each template tells a renewal from a recurring donation.  ``plan_name`` is
    an empty string for a recurring donation, which names no plan, and
    ``cadence_label`` says how often the mandate charges ("each month").
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
        "cadence": mandate.cadence,
        "cadence_label": CADENCE_PHRASES[mandate.cadence],
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
    receipt.  A member with no email address is not written to.  The send is
    recorded in the email log under the template's name.

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
            user_id=mandate.user_id,
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

    A ``plan`` of ``None`` asks for a recurring donation, which anybody may hold and
    which needs only a ``contribution_cents`` of more than nothing; ``None`` comes
    back.  A plan asks for an automatic renewal: it must have a duration, and the
    member must not already hold a lifetime term, which never needs renewing.  The
    plan comes back as given.

    Raises ``DomainValidationError`` keyed by :data:`AUTO_RENEW_FIELD` when the
    provider cannot charge again without the member -- which is every provider
    outside :class:`~apps.payments.models.MandateProvider` -- when a donation gives
    nothing, when a life member asks for a plan, and when the plan is a lifetime one.
    """
    if provider not in MandateProvider.values:
        raise DomainValidationError(
            AUTO_RENEW_FIELD, f"'{provider}' cannot charge a saved payment method."
        )
    if plan is None:
        if contribution_cents <= 0:
            raise DomainValidationError(AUTO_RENEW_FIELD, DONATION_AMOUNT_MESSAGE)
        return None
    if lifetime_term(user) is not None:
        raise DomainValidationError(AUTO_RENEW_FIELD, LIFE_MEMBER_PLAN_MESSAGE)
    if plan.duration_days is None:
        raise DomainValidationError(
            AUTO_RENEW_FIELD, "A lifetime membership never expires, so it cannot renew itself."
        )
    return plan


def renewal_of(user: User) -> RenewalMandate | None:
    """``user``'s automatic renewal -- the mandate that names a plan -- or ``None``."""
    return RenewalMandate.objects.filter(user=user, plan__isnull=False).first()


def donation_of(user: User) -> RenewalMandate | None:
    """``user``'s recurring donation -- the mandate that names no plan -- or ``None``."""
    return RenewalMandate.objects.filter(user=user, plan__isnull=True).first()


def refuse_renewal_contribution(user: User, contribution_cents: int) -> None:
    """Refuse a contribution on a renewal while ``user`` holds a recurring donation.

    A contribution lives in one place: a member who already gives on a schedule
    changes that gift on the Donate screen rather than adding a second one to their
    renewal.  A canceled donation gives nothing and stands in nobody's way, and a
    renewal of the dues alone is always fine.  Raises ``DomainValidationError`` keyed
    by :data:`CONTRIBUTION_FIELD` carrying :data:`HAS_DONATION_MESSAGE`.
    """
    if contribution_cents <= 0:
        return
    held = donation_of(user)
    if held is not None and held.status != MandateStatus.CANCELED:
        raise DomainValidationError(CONTRIBUTION_FIELD, HAS_DONATION_MESSAGE)


def take_contribution_off_renewal(user: User, *, remove: bool, actor: Model | str) -> None:
    """Make room for a recurring donation by taking the renewal's contribution off it.

    A member whose renewal (anything but canceled) takes a contribution is refused
    a recurring donation with :class:`RenewalContributionError`, naming the amount,
    unless ``remove`` says they agreed to move it: then the renewal's contribution
    becomes nothing, its dues renew as before, and one ``renewal.change`` audit
    record names the amount taken off.  A member with no such renewal passes
    straight through.
    """
    renewal = renewal_of(user)
    if renewal is None or renewal.status == MandateStatus.CANCELED:
        return
    if renewal.contribution_cents <= 0:
        return
    if not remove:
        raise RenewalContributionError(renewal.contribution_cents)
    removed = renewal.contribution_cents
    renewal.contribution_cents = 0
    renewal.save(update_fields=["contribution_cents", "updated_at"])
    audit.record(
        audit.RENEWAL_CHANGE,
        actor=actor,
        target=user,
        contribution_cents=0,
        removed_cents=removed,
    )


@transaction.atomic
def begin_mandate(
    user: User,
    *,
    plan: MembershipPlan | None,
    contribution_cents: int,
    provider: str,
    next_charge_on: date | None = None,
    cadence: str = MandateCadence.YEARLY,
    remove_renewal_contribution: bool = False,
) -> RenewalMandate:
    """Create or reset ``user``'s ``pending`` mandate, before anything is saved.

    A person holds at most one renewal and one recurring donation, so asking for
    one again -- at a checkout, or from the portal -- replaces whatever authority of
    that kind was there with a pending one carrying the plan, the contribution, the
    cadence and the provider now asked for, and no saved method.  It becomes
    ``active`` only when the method is confirmed, through :func:`save_method`.
    ``plan`` of ``None`` asks for the recurring donation; any plan, for the renewal.

    ``next_charge_on`` is the day of the first charge.  Left out, a renewal takes
    :func:`default_charge_date` and a donation takes today.  A mandate begun at a
    checkout with no day of its own is dated again from the payment, in
    :func:`activate_pending_mandate`, which is what :data:`CHOSEN_DATE_KEY` records.
    ``cadence`` is what the caller checked: a renewal is always yearly.

    A contribution lives in one place.  A recurring donation for a member whose
    renewal takes a contribution raises :class:`RenewalContributionError` unless
    ``remove_renewal_contribution`` moves that contribution off the renewal first
    (:func:`take_contribution_off_renewal`), and a renewal that takes a contribution
    beside a recurring donation is refused by :func:`refuse_renewal_contribution`.

    Raises ``DomainValidationError`` keyed by :data:`AUTO_RENEW_FIELD` for
    anything :func:`check_renewable` refuses, and writes nothing when anything
    is refused.
    """
    renewable = check_renewable(plan, provider, user=user, contribution_cents=contribution_cents)
    if renewable is None:
        take_contribution_off_renewal(user, remove=remove_renewal_contribution, actor=user)
    else:
        refuse_renewal_contribution(user, contribution_cents)
    chosen = next_charge_on is not None
    today = timezone.localdate()
    if next_charge_on is not None:
        charge_on = next_charge_on
    elif renewable is None:
        charge_on = today
    else:
        charge_on = default_charge_date(user, today)
    mandate, _ = RenewalMandate.objects.update_or_create(
        user=user,
        plan__isnull=renewable is None,
        defaults={
            "plan": renewable,
            "contribution_cents": contribution_cents,
            "cadence": cadence,
            "next_charge_on": charge_on,
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
            "raw": {CHOSEN_DATE_KEY: True} if chosen else {},
        },
    )
    return mandate


@transaction.atomic
def save_method(
    mandate: RenewalMandate, method: MandateMethod, *, actor: Model | str
) -> RenewalMandate:
    """Store the saved payment method on ``mandate`` and make it ``active``.

    Clears the failure count and any cancellation, writes one ``renewal.enable``
    audit record, and emails the member that the authority is on, naming the amount,
    the method and the next charge date.  The plan is named where there is one; a
    recurring donation renews nothing, so it names none and the record's
    ``plan`` field renders ``-``.  The email is sent after the transaction commits,
    so a rollback tells nobody anything.
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
        # A recurring donation names no plan, and an empty list is how a
        # record says a field has no value: it renders as `-`.
        plan=[] if mandate.plan is None else [mandate.plan.slug],
    )
    charge_on = charge_date(mandate)
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
        user_id=payment.user_id,
        status=MandateStatus.PENDING,
        plan__isnull=payment.plan_id is None,
    ).first()
    if mandate is None or mandate.provider != payment.provider:
        return None
    if mandate.plan_id != payment.plan_id:
        return None
    if mandate.contribution_cents != payment.contribution_cents:
        return None
    return mandate


def discard_pending_mandate(user: User) -> None:
    """Throw away the member's ``pending`` mandates, of either kind, if they hold any.

    A pending mandate has no saved method, has charged nothing and has never been
    announced to anybody, so a checkout that declines automatic renewal deletes it
    outright rather than canceling it: there is no standing authority to withdraw
    and nothing to tell the member.  A mandate in any other state is left alone.
    """
    RenewalMandate.objects.filter(user=user, status=MandateStatus.PENDING).delete()


def cancel_all_mandates(user: User) -> None:
    """Withdraw every standing authority ``user`` has given CalDART to charge them.

    Each active or paused mandate is canceled through :func:`cancel_mandate` with the
    account itself as the actor, so it is recorded as a self-service
    ``renewal.cancel`` and the member is told; a pending one is thrown away by
    :func:`discard_pending_mandate`.  A mandate already canceled is left as it is.
    Called when a person deactivates their own account.
    """
    standing = RenewalMandate.objects.filter(user=user).exclude(
        status__in=(MandateStatus.CANCELED, MandateStatus.PENDING)
    )
    for mandate in standing:
        cancel_mandate(mandate, actor=user)
    discard_pending_mandate(user)


#: The field a member switching to friend answers whether to keep their contribution in.
KEEP_CONTRIBUTION_FIELD = "keep_contribution"

#: What a member is told when their renewal takes a contribution and they did not say
#: whether to keep it, in DRF's own words for a missing field.
KEEP_CONTRIBUTION_REQUIRED = "This field is required."


#: What a member is told when they ask to keep their renewal's contribution while a
#: recurring donation of theirs is already active or paused.
KEEP_CONTRIBUTION_DONATION_HELD = (
    "You already have a recurring donation. Change it on the Donate screen."
)


@transaction.atomic
def switch_to_friend(user: User, *, keep_contribution: bool | None) -> User:
    """Make ``user`` a friend of CalDART at their own request, and return the account.

    The account becomes a friend through :func:`apps.members.services.become_friend`:
    the day after a current membership runs out, or at once.  Their automatic renewal
    ends with it (a friend has no dues to renew): an active or paused one is canceled
    through :func:`cancel_mandate` under their own name, and a pending one is thrown
    away.  When an active renewal takes a contribution, ``keep_contribution`` must say
    what becomes of it: true keeps it as a yearly recurring donation through
    :func:`keep_renewal_contribution`, false lets it stop.  Left as ``None`` there,
    ``DomainValidationError`` is raised keyed by :data:`KEEP_CONTRIBUTION_FIELD`, and
    true is refused the same way with :data:`KEEP_CONTRIBUTION_DONATION_HELD` while a
    recurring donation of theirs is active or paused.  ``keep_contribution`` is ignored
    when there is nothing to keep: no contribution, or a paused renewal, whose method
    already failed or whose member was told it is off, so its contribution simply
    stops.  Every refusal of ``become_friend`` is raised too, and nothing is written
    when anything is refused.  The account and its renewal are locked for the
    transaction, so two overlapping requests take turns: the second sees the first's
    work.  The account returned is the freshly locked copy.
    """
    user = User.objects.select_for_update().get(pk=user.pk)
    check_can_become_friend(user, timezone.localdate())
    renewal = (
        RenewalMandate.objects.select_for_update().filter(user=user, plan__isnull=False).first()
    )
    if renewal is not None and renewal.status == MandateStatus.PENDING:
        renewal.delete()
    elif renewal is not None and renewal.status != MandateStatus.CANCELED:
        is_kept = _keeps_contribution(renewal, keep_contribution)
        cancel_mandate(renewal, actor=user)
        if is_kept:
            keep_renewal_contribution(renewal)
    return become_friend(user)


def _keeps_contribution(renewal: RenewalMandate, keep_contribution: bool | None) -> bool:
    """Whether switching to friend keeps ``renewal``'s contribution as a donation.

    Only an active renewal with a contribution offers one to keep; for it, a missing
    answer, or true while a recurring donation is already active or paused, raises
    ``DomainValidationError`` keyed by :data:`KEEP_CONTRIBUTION_FIELD`.
    """
    if renewal.status != MandateStatus.ACTIVE or renewal.contribution_cents == 0:
        return False
    if keep_contribution is None:
        raise DomainValidationError(KEEP_CONTRIBUTION_FIELD, KEEP_CONTRIBUTION_REQUIRED)
    if not keep_contribution:
        return False
    held = donation_of(renewal.user)
    if held is not None and held.status in (MandateStatus.ACTIVE, MandateStatus.PAUSED):
        raise DomainValidationError(KEEP_CONTRIBUTION_FIELD, KEEP_CONTRIBUTION_DONATION_HELD)
    return True


def keep_renewal_contribution(renewal: RenewalMandate) -> RenewalMandate:
    """Carry ``renewal``'s contribution on as a yearly recurring donation, and return it.

    The donation takes the renewal's contribution, provider, and saved method, and is
    first charged on the renewal's next charge day (today when that has gone by), so
    the member gives what they gave, on the day they gave it, with the card they gave
    it with.  It is begun through :func:`begin_mandate`, reusing a canceled donation
    row when there is one, and activated through :func:`save_method`, so it is audited
    as ``renewal.enable`` and announced like any other.  The renewal must already be
    canceled, and the member must hold no active or paused donation: a contribution
    lives in one place, so :func:`begin_mandate` refuses a donation beside a live
    renewal that takes one.
    """
    donation = begin_mandate(
        renewal.user,
        plan=None,
        contribution_cents=renewal.contribution_cents,
        provider=renewal.provider,
        next_charge_on=max(renewal.next_charge_on, timezone.localdate()),
        cadence=MandateCadence.YEARLY,
    )
    method = MandateMethod(
        method_ref=renewal.method_ref,
        label=renewal.method_label,
        customer_ref=renewal.customer_ref,
        brand=renewal.method_brand,
        last4=renewal.method_last4,
        exp_month=renewal.method_exp_month,
        exp_year=renewal.method_exp_year,
        raw=renewal.raw,
    )
    return save_method(donation, method, actor=renewal.user)


def activate_pending_mandate(payment: Payment) -> RenewalMandate | None:
    """Activate the mandate a succeeded checkout was asked to save, if any.

    Called from :func:`apps.payments.services.mark_succeeded`, so a checkout that
    asked for automatic renewal needs no second round trip: the method the member
    just paid with is read back off the provider's own record of the charge.
    Returns the activated mandate, or ``None`` when the payment saved no method
    or there was no pending mandate to activate.

    A renewal whose member named no charge date is dated from the term the payment
    has just bought, so the first automatic charge falls on the day that term runs
    out.  A recurring donation whose member named no later day has just taken its
    first gift, so its next charge falls one cadence after today.  A date the member
    did choose is left exactly as they gave it, except that a donation's chosen day
    that is not after today moves on by its cadence too: the payment is that day's
    gift, and it is never taken twice.
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
    today = timezone.localdate()
    chosen = mandate.raw.get(CHOSEN_DATE_KEY) is True
    if mandate.plan_id is None:
        if not chosen or mandate.next_charge_on <= today:
            mandate.next_charge_on = advance_by_cadence(today, mandate.cadence)
    elif not chosen:
        # The term the money just bought is what the charge follows, not the one
        # the member held when they started the checkout.
        mandate.next_charge_on = default_charge_date(payment.user, today)
    return save_method(mandate, method, actor=payment.user)


def roll_charge_date_past(user: User, *, covered_until: date | None) -> RenewalMandate | None:
    """Move an active authority's stored charge day past coverage bought elsewhere.

    ``covered_until`` is the day the member's coverage ran to before the term they
    have just bought or been granted.  When their coverage now runs further than
    that, the stored charge day moves on by the same span, keeping the place the
    member gave it relative to their expiry: a day stored on the expiry itself
    becomes the new expiry, a day stored a fortnight early stays a fortnight early,
    and a day stored after the expiry stays as far after it.  A day already behind
    when the coverage moved has lost that place, so it becomes the new expiry
    itself.  Without this a member who renews by hand would be charged a second
    year on a day their coverage already reaches past.

    Does nothing, and answers ``None``, for a member with no active authority, for
    a recurring donation, which renews no term, when the coverage did not
    move, and when the stored day already falls on or after the day the coverage now
    runs to -- which is what makes it safe to call twice for one term.  Otherwise
    answers the mandate as saved.
    """
    mandate = RenewalMandate.objects.filter(
        user=user, status=MandateStatus.ACTIVE, plan__isnull=False
    ).first()
    if mandate is None:
        return None
    today = timezone.localdate()
    term = term_to_renew(user, today)
    if term is None or term.ends_on is None:
        return None
    if mandate.next_charge_on >= term.ends_on:
        return None
    previous = covered_until if covered_until is not None else mandate.next_charge_on
    if term.ends_on <= previous:
        return None
    rolled = term.ends_on - (previous - mandate.next_charge_on)
    mandate.next_charge_on = rolled if rolled >= today else term.ends_on
    mandate.save(update_fields=["next_charge_on", "updated_at"])
    return mandate


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
    except (ProviderUnavailableError, ProviderNotConfiguredError) as exc:
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
        _schedule(mandate, attempt.membership, next_on, retry_of=attempt)
    run.failed += 1
