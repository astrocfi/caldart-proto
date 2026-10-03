"""A mandate's life cycle, from the request that begins it to the one that ends it.

Beginning a mandate, saving the method that activates it, canceling it, switching a
member to friend, and moving its charge day when coverage arrives from elsewhere --
with the refusals each of those can answer, including the rule that a contribution
lives in one place.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Literal, TypedDict

from django.db import transaction
from django.db.models import Model
from django.utils import timezone

from apps.accounts.models import User
from apps.members.lifecycle import become_friend, check_can_become_friend
from apps.members.models import MembershipPlan
from apps.payments.models import (
    MandateCadence,
    MandateProvider,
    MandateStatus,
    Payment,
    RenewalMandate,
    RenewalOutcome,
)
from apps.payments.providers.base import MandateMethod, get_provider
from apps.payments.renewals.emails import send_mandate_email
from apps.payments.renewals.schedule import (
    advance_by_cadence,
    charge_date,
    default_charge_date,
    lifetime_term,
    term_to_renew,
)
from caldart import audit, events
from caldart.exceptions import DomainError, DomainValidationError
from caldart.reports import money_label

log = logging.getLogger(__name__)

#: The field an input refusal about automatic renewal is keyed by.
AUTO_RENEW_FIELD = "auto_renew"

#: What a member is told when they ask to be charged on a day that has gone.
PAST_CHARGE_DATE_MESSAGE = "The next charge cannot be in the past."

#: The key on a pending mandate's ``raw`` that records that the member named the
#: charge date themselves, so the checkout that activates it leaves the date alone.
CHOSEN_DATE_KEY = "next_charge_on_chosen"

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
    so a rollback tells nobody anything.  A mandate that was not active already
    raises the ``auto_renewal_on`` event; a new card on an active one raises nothing.
    """
    was_active = mandate.status == MandateStatus.ACTIVE
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
    if not was_active:
        events.emit("auto_renewal_on", mandate=mandate)
    return mandate


#: How an automatic payment was turned off, as the ``auto_renewal_off`` event names it.
type OffHow = Literal["member", "administrator", "lapsed", "deactivated", "deleted"]


class _CancelReason(TypedDict, total=False):
    """The optional ``reason`` field a ``renewal.cancel`` audit line ends with."""

    reason: str


@transaction.atomic
def cancel_mandate(
    mandate: RenewalMandate,
    *,
    actor: User | None,
    how: OffHow | None = None,
    reason: str | None = None,
) -> RenewalMandate:
    """Turn automatic renewal off, whoever asked, and tell the member.

    ``actor`` is the member themselves or the administrator who turned it off,
    and is recorded as ``canceled_by`` and in the audit record's
    ``self_service`` flag; it is ``None`` for a cancellation nobody signed for.
    Every scheduled attempt still waiting is marked ``skipped``, so the next scan
    charges nothing.  Writes one ``renewal.cancel`` audit record, ending in
    ``reason=<reason>`` when ``reason`` is given (``member.delete`` when the member's
    account is being deleted), and emails the member after the transaction commits.
    Calling it on a mandate that is already canceled changes nothing and sends nothing.

    Canceling a mandate that was active raises the ``auto_renewal_off`` event with
    the mandate and ``how``: the caller's word when given (``deactivated`` when the
    member left, ``deleted`` when their account is being deleted), otherwise
    ``member`` when ``actor`` is the mandate's own member and ``administrator`` for
    anybody else.  A paused mandate was off already, and
    raised its event when it paused, so canceling it raises nothing.
    """
    if mandate.status == MandateStatus.CANCELED:
        return mandate
    was_active = mandate.status == MandateStatus.ACTIVE
    mandate.status = MandateStatus.CANCELED
    mandate.canceled_at = timezone.now()
    mandate.canceled_by = actor
    mandate.save(update_fields=["status", "canceled_at", "canceled_by", "updated_at"])
    mandate.attempts.filter(outcome=RenewalOutcome.SCHEDULED).update(outcome=RenewalOutcome.SKIPPED)
    extra: _CancelReason = {} if reason is None else {"reason": reason}
    audit.record(
        audit.RENEWAL_CANCEL,
        actor=actor or audit.COMMAND_ACTOR,
        target=mandate.user,
        provider=mandate.provider,
        self_service=actor is not None and actor.pk == mandate.user_id,
        **extra,
    )
    transaction.on_commit(lambda: send_mandate_email(mandate, "renewal_canceled"))
    if was_active:
        if how is None:
            how = "member" if actor is not None and actor.pk == mandate.user_id else "administrator"
        events.emit("auto_renewal_off", mandate=mandate, how=how)
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


def cancel_all_mandates(user: User, *, actor: User | None = None) -> None:
    """Withdraw every standing authority ``user`` has given CalDART to charge them.

    Each active or paused mandate is canceled through :func:`cancel_mandate` under
    ``actor``, the account itself when none is given (so it is recorded as a
    self-service ``renewal.cancel``), raised as ``auto_renewal_off`` with
    ``how="deactivated"`` when it was active, and the member is told; a pending one is
    thrown away by :func:`discard_pending_mandate`.  A mandate already canceled is left
    as it is.  Called whenever an account is deactivated, by its owner or by an
    administrator.
    """
    standing = RenewalMandate.objects.filter(user=user).exclude(
        status__in=(MandateStatus.CANCELED, MandateStatus.PENDING)
    )
    for mandate in standing:
        cancel_mandate(mandate, actor=actor or user, how="deactivated")
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

#: The same refusal, told to the administrator making somebody else a friend.
KEEP_CONTRIBUTION_DONATION_HELD_ADMIN = (
    "They already have a recurring donation, so the contribution cannot be kept as one."
)


@transaction.atomic
def switch_to_friend(
    user: User, *, keep_contribution: bool | None, actor: User | None = None
) -> User:
    """Make ``user`` a friend of CalDART, and return the account.

    ``actor`` is the administrator who asked on the person's behalf, or ``None`` (the
    default) when the person asked for themselves; it is recorded on the canceled
    renewal and on the ``account.kind`` audit line, and an administrator's change
    raises ``became_friend`` with ``how="administrator"``.  An administrator who asks to
    keep the contribution while a recurring donation is held is refused with
    :data:`KEEP_CONTRIBUTION_DONATION_HELD_ADMIN` instead.

    The account becomes a friend through :func:`apps.members.lifecycle.become_friend`:
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
    actor = actor or user
    check_can_become_friend(user, timezone.localdate())
    renewal = (
        RenewalMandate.objects.select_for_update().filter(user=user, plan__isnull=False).first()
    )
    if renewal is not None and renewal.status == MandateStatus.PENDING:
        renewal.delete()
    elif renewal is not None and renewal.status != MandateStatus.CANCELED:
        is_kept = _keeps_contribution(renewal, keep_contribution, is_own=actor.pk == user.pk)
        cancel_mandate(renewal, actor=actor)
        if is_kept:
            keep_renewal_contribution(renewal)
    return become_friend(user, actor=actor)


def _keeps_contribution(
    renewal: RenewalMandate, keep_contribution: bool | None, *, is_own: bool = True
) -> bool:
    """Whether switching to friend keeps ``renewal``'s contribution as a donation.

    Only an active renewal with a contribution offers one to keep; for it, a missing
    answer, or true while a recurring donation is already active or paused, raises
    ``DomainValidationError`` keyed by :data:`KEEP_CONTRIBUTION_FIELD`, the second in
    the member's own words when ``is_own`` and an administrator's otherwise.
    """
    if renewal.status != MandateStatus.ACTIVE or renewal.contribution_cents == 0:
        return False
    if keep_contribution is None:
        raise DomainValidationError(KEEP_CONTRIBUTION_FIELD, KEEP_CONTRIBUTION_REQUIRED)
    if not keep_contribution:
        return False
    held = donation_of(renewal.user)
    if held is not None and held.status in (MandateStatus.ACTIVE, MandateStatus.PAUSED):
        message = (
            KEEP_CONTRIBUTION_DONATION_HELD if is_own else KEEP_CONTRIBUTION_DONATION_HELD_ADMIN
        )
        raise DomainValidationError(KEEP_CONTRIBUTION_FIELD, message)
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
