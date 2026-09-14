"""Membership services.

``membership_status`` is the single source of truth for "is this person a
current member"; ``activate_term`` is the single way a term is created.
"""

from __future__ import annotations

from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from apps.members.models import (
    Membership,
    MembershipPlan,
    MembershipSource,
    MembershipStatusChoices,
)

#: Shape returned by :func:`membership_status`.
MembershipStatusDict = dict


def _current_term(user, on_date: date) -> Membership | None:
    """The active term covering ``on_date``, preferring lifetime then latest end."""
    terms = [
        m
        for m in user.memberships.select_related("plan").all()
        if m.status == MembershipStatusChoices.ACTIVE
        and m.starts_on <= on_date
        and (m.ends_on is None or m.ends_on >= on_date)
    ]
    if not terms:
        return None
    # Lifetime wins; otherwise the term that runs longest.
    terms.sort(key=lambda m: (m.ends_on is None, m.ends_on or date.min), reverse=True)
    return terms[0]


def _latest_expiry(user) -> date | None:
    """Latest ``ends_on`` across active terms, or ``None`` if any is lifetime."""
    ends: list[date] = []
    for m in user.memberships.all():
        if m.status != MembershipStatusChoices.ACTIVE:
            continue
        if m.ends_on is None:
            return None
        ends.append(m.ends_on)
    return max(ends) if ends else None


def _coverage(user, on_date: date) -> Membership | None:
    """The term the member's *unbroken* coverage from ``on_date`` ends with.

    Renewing early creates a term that starts the day after the current one
    ends.  The member is entitled to see the new expiry date straight away, so
    walk the chain of back-to-back active terms and return the last link.
    """
    current = _current_term(user, on_date)
    if current is None:
        return None

    active = [
        m
        for m in user.memberships.select_related("plan").all()
        if m.status == MembershipStatusChoices.ACTIVE
    ]
    last = current
    while last.ends_on is not None:
        following = [
            m
            for m in active
            if m.starts_on <= last.ends_on + timedelta(days=1)
            and (m.ends_on is None or m.ends_on > last.ends_on)
        ]
        if not following:
            break
        # A lifetime term wins; otherwise take the one that reaches furthest.
        following.sort(key=lambda m: (m.ends_on is None, m.ends_on or date.min), reverse=True)
        last = following[0]
    return last


def membership_status(user, on_date: date | None = None) -> MembershipStatusDict:
    """Summarise a user's membership.

    Returns ``{"status", "expires_on", "plan", "is_lifetime"}`` where status is
    ``current`` (a term covers ``on_date``), ``expired`` (a term has started and
    run out) or ``none`` (nothing has started yet).

    ``expires_on`` is the end of the member's unbroken coverage, so a renewal
    bought today shows next year's date immediately.
    """
    on_date = on_date or timezone.localdate()

    if user is None or not getattr(user, "is_authenticated", False):
        return {"status": "none", "expires_on": None, "plan": None, "is_lifetime": False}

    covering = _coverage(user, on_date)
    if covering is not None:
        return {
            "status": "current",
            "expires_on": covering.ends_on,
            "plan": covering.plan.name,
            "is_lifetime": covering.ends_on is None,
        }

    past = (
        user.memberships.select_related("plan")
        .exclude(status=MembershipStatusChoices.CANCELED)
        .filter(starts_on__lte=on_date)
        .order_by("-ends_on", "-starts_on")
        .first()
    )
    if past is None:
        return {"status": "none", "expires_on": None, "plan": None, "is_lifetime": False}
    return {
        "status": "expired",
        "expires_on": past.ends_on,
        "plan": past.plan.name,
        "is_lifetime": False,
    }


@transaction.atomic
def activate_term(
    user,
    plan: MembershipPlan,
    *,
    source: str = MembershipSource.PAYMENT,
    payment=None,
    granted_by=None,
    starts_on: date | None = None,
    note: str = "",
) -> Membership:
    """Create (or return) the membership term for ``plan``.

    A renewal starts the day after the current expiry when the member is
    already current; otherwise it starts today.  ``ends_on`` is
    ``starts_on + duration_days - 1``, or ``None`` for a lifetime plan.

    Idempotent on ``payment``: calling twice with the same payment returns the
    term created the first time.
    """
    if payment is not None:
        existing = Membership.objects.filter(payment=payment).first()
        if existing is not None:
            return existing

    today = timezone.localdate()

    if starts_on is None:
        expiry = _latest_expiry(user)
        has_active = user.memberships.filter(status=MembershipStatusChoices.ACTIVE).exists()
        if has_active and expiry is None:
            # Already a lifetime member: a new term simply starts today.
            starts_on = today
        elif expiry is not None and expiry >= today:
            starts_on = expiry + timedelta(days=1)
        else:
            starts_on = today

    if plan.duration_days is None:
        ends_on = None
    else:
        ends_on = starts_on + timedelta(days=plan.duration_days - 1)

    return Membership.objects.create(
        user=user,
        plan=plan,
        starts_on=starts_on,
        ends_on=ends_on,
        status=MembershipStatusChoices.ACTIVE,
        source=source,
        payment=payment,
        granted_by=granted_by,
        note=note,
    )


def expire_lapsed_memberships(on_date: date | None = None) -> int:
    """Flip active terms whose ``ends_on`` has passed to ``expired``.

    Used by the reminder scanner and by the seed to keep data honest.
    """
    on_date = on_date or timezone.localdate()
    return Membership.objects.filter(
        status=MembershipStatusChoices.ACTIVE,
        ends_on__isnull=False,
        ends_on__lt=on_date,
    ).update(status=MembershipStatusChoices.EXPIRED, updated_at=timezone.now())
