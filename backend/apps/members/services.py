"""Membership services.

``membership_status`` is the single source of truth for "is this person a
current member"; ``activate_term`` is the single way a term is created.

The same rule is stated twice, because a list has to filter, order and
paginate on it in the database.  ``membership_status`` works one user out in
Python; :func:`membership_annotations` expresses the identical rule as
correlated subqueries, :func:`with_membership` hangs them on any ``User``
queryset, and :func:`membership_payload` reads them back in the shape
``membership_status`` returns.  :func:`membership_of` picks whichever of the
two the caller has paid for.

The translation, term by term:

``covers_today``
    An active term has started and has not run out -- ``_current_term``.
``coverage_end``
    ``_coverage`` walks forward from the covering term through terms that start
    no later than the day after the previous one ends.  The end of that walk is
    the earliest *boundary*: an active term ending on or after today that no
    other active term continues.  Anything ending earlier inside the chain has
    a follower by definition, and anything in a later chain ends after the gap,
    so "earliest boundary" and "end of the walk" are the same date.  NULL means
    the chain reaches a lifetime term (or that nothing covers today).
``past_end`` / ``past_plan``
    The most recent non-canceled term that has started, which
    ``membership_status`` reports for an expired member.

``tests/test_members_admin_status.py`` checks the two implementations agree
over a deliberately awkward set of histories, including early renewals, gaps
and canceled terms.
"""

from __future__ import annotations

from datetime import date, timedelta

from django.db import transaction
from django.db.models import (
    CharField,
    DateField,
    Exists,
    F,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
)
from django.utils import timezone

from apps.members.models import (
    Membership,
    MembershipPlan,
    MembershipSource,
    MembershipState,
    MembershipStatusChoices,
)

#: Shape returned by :func:`membership_status`.
MembershipStatusDict = dict


def _no_membership() -> MembershipStatusDict:
    """The status of an account nothing has ever covered.

    A fresh dictionary each call, so a caller that adds its own keys -- the
    ``/me/membership`` payload hangs the term history off it -- cannot reach
    the next caller's answer.
    """
    return {
        "status": MembershipState.NONE,
        "expires_on": None,
        "plan": None,
        "is_lifetime": False,
    }


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
    """Summarize a user's membership.

    Returns ``{"status", "expires_on", "plan", "is_lifetime"}`` where status is
    ``current`` (a term covers ``on_date``), ``expired`` (a term has started and
    run out) or ``none`` (nothing has started yet).

    ``expires_on`` is the end of the member's unbroken coverage, so a renewal
    bought today shows next year's date immediately.
    """
    on_date = on_date or timezone.localdate()

    if user is None or not getattr(user, "is_authenticated", False):
        return _no_membership()

    covering = _coverage(user, on_date)
    if covering is not None:
        return {
            "status": MembershipState.CURRENT,
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
        return _no_membership()
    return {
        "status": MembershipState.EXPIRED,
        "expires_on": past.ends_on,
        "plan": past.plan.name,
        "is_lifetime": False,
    }


def membership_annotations(today: date | None = None) -> dict:
    """Annotations restating :func:`membership_status` as correlated subqueries.

    ``today`` defaults to the current local date, which is read when this is
    called, so a queryset built per request always answers for the day of the
    request.  Splat the result into ``QuerySet.annotate`` on a ``User``
    queryset, or use :func:`with_membership`.
    """
    today = today or timezone.localdate()
    active = Membership.objects.filter(status=MembershipStatusChoices.ACTIVE)

    # A later term that continues the one being examined: it starts no later
    # than the day after this one ends, and reaches further into the future.
    follower = active.filter(
        user=OuterRef("user"),
        starts_on__lte=OuterRef("ends_on") + timedelta(days=1),
    ).filter(Q(ends_on__isnull=True) | Q(ends_on__gt=OuterRef("ends_on")))

    boundaries = (
        active.filter(user=OuterRef("pk"), ends_on__isnull=False, ends_on__gte=today)
        .filter(~Exists(follower))
        .order_by("ends_on")
    )

    lifetime = active.filter(user=OuterRef("pk"), ends_on__isnull=True).order_by("starts_on")

    started = Membership.objects.exclude(status=MembershipStatusChoices.CANCELED).filter(
        user=OuterRef("pk"), starts_on__lte=today
    )
    past = started.order_by(F("ends_on").desc(nulls_first=True), "-starts_on")

    return {
        "covers_today": Exists(
            active.filter(user=OuterRef("pk"), starts_on__lte=today).filter(
                Q(ends_on__isnull=True) | Q(ends_on__gte=today)
            )
        ),
        "has_started_term": Exists(started),
        "coverage_end": Subquery(boundaries.values("ends_on")[:1], output_field=DateField()),
        "coverage_plan": Subquery(boundaries.values("plan__name")[:1], output_field=CharField()),
        "lifetime_plan": Subquery(lifetime.values("plan__name")[:1], output_field=CharField()),
        "past_end": Subquery(past.values("ends_on")[:1], output_field=DateField()),
        "past_plan": Subquery(past.values("plan__name")[:1], output_field=CharField()),
        "joined_on": Subquery(
            Membership.objects.filter(user=OuterRef("pk"))
            .order_by("starts_on")
            .values("starts_on")[:1],
            output_field=DateField(),
        ),
    }


def with_membership(queryset: QuerySet, *, today: date | None = None) -> QuerySet:
    """``queryset`` of users, carrying the membership annotations.

    Every row then answers ``membership_status`` without a further query, which
    :func:`membership_payload` and :func:`membership_of` read back.  The status
    is worked out for ``today``, defaulting to the current local date.
    """
    return queryset.annotate(**membership_annotations(today))


def membership_payload(user) -> MembershipStatusDict:
    """Read the annotated status back in ``membership_status`` shape.

    ``user`` must have come from :func:`with_membership`; reach for
    :func:`membership_of` when that is not guaranteed.
    """
    if user.covers_today:
        lifetime = user.coverage_end is None
        return {
            "status": MembershipState.CURRENT,
            "expires_on": user.coverage_end,
            "plan": user.lifetime_plan if lifetime else user.coverage_plan,
            "is_lifetime": lifetime,
        }
    if user.has_started_term:
        return {
            "status": MembershipState.EXPIRED,
            "expires_on": user.past_end,
            "plan": user.past_plan,
            "is_lifetime": False,
        }
    return _no_membership()


def membership_of(user) -> MembershipStatusDict:
    """The membership summary for ``user``, however the row was fetched.

    A user that came through :func:`with_membership` is answered from its
    annotations, at no extra cost; any other user falls back to
    :func:`membership_status`, which spends a query or two working it out in
    Python.  Both answers are identical.
    """
    if hasattr(user, "covers_today"):
        return membership_payload(user)
    return membership_status(user)


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
