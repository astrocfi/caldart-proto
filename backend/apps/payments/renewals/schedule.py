"""What a mandate is and when it charges.

:class:`MandateKind` and the words for each kind, the amount a mandate charges, the
membership term it renews, and the dates it charges on.  Every other module in the
package reads these; this one reads none of them.
"""

from __future__ import annotations

import calendar
from datetime import date

from django.db import models
from django.utils import timezone

from apps.accounts.models import User
from apps.members.models import Membership, MembershipStatusChoices
from apps.payments.models import MandateCadence, MandateStatus, RenewalMandate, RenewalOutcome


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

#: How many months each cadence moves the next charge on by.
CADENCE_MONTHS: dict[str, int] = {
    MandateCadence.MONTHLY: 1,
    MandateCadence.QUARTERLY: 3,
    MandateCadence.YEARLY: 12,
}


# --------------------------------------------------------------------------
# Dates
# --------------------------------------------------------------------------
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
