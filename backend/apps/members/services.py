"""Member and membership services.

A member record is an account plus its profile, and the four functions at the
top of this module are the only ways one is created, edited, or removed.  Each
enforces its own rules and refuses with a ``DomainError``, so a management
command, the Django admin and the API all behave the same way.  The account
half of every rule belongs to ``accounts.services``.

``membership_status`` is the single source of truth for "is this person a
current member"; ``activate_term`` is the single way a term is created.

The same rule is stated twice, because a list has to filter, order, and
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
over a deliberately awkward set of histories, including early renewals, gaps,
and canceled terms.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING, Any, NoReturn, TypedDict, cast

from django.contrib.auth.models import AnonymousUser
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
from django.db.models.deletion import ProtectedError
from django.http import HttpRequest
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.roles import SYSTEM_ADMIN
from apps.accounts.services import (
    AccountChanges,
    create_account,
    effective_roles,
    send_password_invitation,
    update_account,
)
from apps.members.models import (
    MemberProfile,
    Membership,
    MembershipPlan,
    MembershipSource,
    MembershipState,
    MembershipStatusChoices,
)
from caldart import audit
from caldart.exceptions import DomainPermissionError

if TYPE_CHECKING:
    from django_stubs_ext import WithAnnotations

    # Inline: payments sits above members and apps.payments.services imports this
    # module, so a top-level import here would close the cycle.  This one is read
    # by the type checker alone and costs nothing at run time.
    from apps.payments.models import Payment


class MembershipStatusDict(TypedDict):
    """The summary :func:`membership_status` and :func:`membership_payload` return."""

    status: MembershipState
    expires_on: date | None
    plan: str | None
    is_lifetime: bool


class MembershipAnnotations(TypedDict):
    """The columns :func:`membership_annotations` adds to a user row."""

    covers_today: bool
    has_started_term: bool
    has_unpaid_term: bool
    unpaid_end: date | None
    unpaid_plan: str | None
    coverage_end: date | None
    coverage_plan: str | None
    lifetime_plan: str | None
    past_end: date | None
    past_plan: str | None
    joined_on: date | None


if TYPE_CHECKING:
    #: A user row that came through :func:`with_membership`, so the membership
    #: annotations can be read straight off it.
    type MemberRow = WithAnnotations[User, MembershipAnnotations]

#: The profile fields an administrator may set when creating or editing a member.
type ProfileChanges = dict[str, Any]

SELF_DELETE_REFUSED = "You cannot delete your own account."
SYSTEM_ADMIN_DELETE_REFUSED = "Only a system administrator can delete a system administrator."


# --------------------------------------------------------------------------
# The member record: account plus profile
# --------------------------------------------------------------------------
@transaction.atomic
def register_member(
    *, email: str, password: str, first_name: str = "", last_name: str = ""
) -> User:
    """Create the member account ``POST /auth/register`` signs in, and return it.

    The profile starts blank on purpose -- the join wizard fills it in -- but it
    must exist so ``/me/profile`` is a PATCH rather than a create.  Account and
    profile are written together, so a failure leaves no half-made member.
    """
    user = create_account(
        email=email, password=password, first_name=first_name, last_name=last_name
    )
    MemberProfile.objects.get_or_create(user=user)
    return user


@transaction.atomic
def create_member(
    actor: User,
    *,
    email: str,
    password: str = "",
    first_name: str = "",
    last_name: str = "",
    profile: ProfileChanges | None = None,
    request: HttpRequest | None = None,
) -> User:
    """Create a member an administrator is entering, and return the account.

    ``profile`` is the profile fields to record, which on the day somebody joins
    at an airshow may be none of them.  Without a password the account holds an
    unusable one and is mailed an invitation to set the first; the mail is queued
    past the commit, so a create that rolls back mails nobody.  ``request`` only
    tells that mail which site's name and contact address to use.
    """
    user = create_account(
        email=email, password=password, first_name=first_name, last_name=last_name
    )
    MemberProfile.objects.create(user=user, **(profile or {}))
    if not password:
        transaction.on_commit(lambda: send_password_invitation(user, request=request))
    audit.record(audit.MEMBER_CREATE, actor=actor, target=user, invited=not password)
    return user


@transaction.atomic
def update_member(
    actor: User,
    target: User,
    *,
    account: AccountChanges | None = None,
    profile: ProfileChanges | None = None,
) -> User:
    """Apply an administrator's edit to a member, and return the account.

    ``account`` goes to :func:`apps.accounts.services.update_account`, which owns
    every rule about who may change what, and ``profile`` is written over the
    member's profile row, creating it if the account somehow has none.  Both
    halves are written together, so a refused account edit leaves the profile
    alone.
    """
    update_account(actor, target, account or {})
    if profile is not None:
        row, _ = MemberProfile.objects.get_or_create(user=target)
        for field, value in profile.items():
            setattr(row, field, value)
        row.save()
        target.refresh_from_db()
    return target


@transaction.atomic
def delete_member(actor: User, target: User) -> None:
    """Delete ``target``'s account and everything hanging off it, refused three ways.

    Nobody may delete themselves; only a system administrator may delete one.
    Both of those tests are judged on effective roles, so a Django superuser
    counts as a system administrator whether or not the role group was ever
    added.  The third refusal protects the accounts: a member with any payment,
    whatever its status, cannot be deleted, because the payment is a financial
    record.  Deactivation is the alternative.

    Every refusal raises ``DomainPermissionError``, writes nothing and is recorded
    in the audit log at WARNING with a reason; the delete itself is recorded at
    INFO, which is the only trace the account leaves.
    """
    if target.pk == actor.pk:
        _refuse_delete(actor, target, audit.REASON_SELF_DELETE, SELF_DELETE_REFUSED)
    target_is_system_admin = SYSTEM_ADMIN in effective_roles(target)
    if target_is_system_admin and SYSTEM_ADMIN not in effective_roles(actor):
        _refuse_delete(actor, target, audit.REASON_SYSTEM_ADMIN_TARGET, SYSTEM_ADMIN_DELETE_REFUSED)
    # Inline: payments sits above members and apps.payments.services imports this
    # module, so a top-level import here would close the cycle.
    from apps.payments.models import payment_deletion_refusal

    refusal = payment_deletion_refusal(target)
    if refusal is not None:
        _refuse_delete(actor, target, audit.REASON_HAS_PAYMENTS, refusal)
    target_id = target.pk
    try:
        target.delete()
    except ProtectedError as exc:
        # ``Payment.user`` is the only protected reference to an account, so a row
        # created between the check above and the delete lands here, and the same
        # sentence is now there to quote.  Anything else protecting the row is a
        # bug, not a refusal, and travels on as the server error it is.
        late_refusal = payment_deletion_refusal(target)
        if late_refusal is None:
            raise
        audit.refuse(
            audit.MEMBER_DELETE, actor=actor, target=target, reason=audit.REASON_HAS_PAYMENTS
        )
        raise DomainPermissionError(late_refusal) from exc
    audit.record(audit.MEMBER_DELETE, actor=actor, target=target_id)


def _refuse_delete(actor: User, target: User, reason: str, message: str) -> NoReturn:
    """Log the refused delete and raise ``DomainPermissionError`` carrying ``message``."""
    audit.refuse(audit.MEMBER_DELETE, actor=actor, target=target, reason=reason)
    raise DomainPermissionError(message)


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


def _current_term(user: User, on_date: date) -> Membership | None:
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


def _latest_expiry(user: User) -> date | None:
    """Latest ``ends_on`` across active terms, or ``None`` if any is lifetime."""
    ends: list[date] = []
    for m in user.memberships.all():
        if m.status != MembershipStatusChoices.ACTIVE:
            continue
        if m.ends_on is None:
            return None
        ends.append(m.ends_on)
    return max(ends) if ends else None


def _coverage(user: User, on_date: date) -> Membership | None:
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


def membership_status(
    user: User | AnonymousUser | None, on_date: date | None = None
) -> MembershipStatusDict:
    """Summarize a user's membership, reading the terms out of the database.

    Returns ``{"status", "expires_on", "plan", "is_lifetime"}`` where status is
    ``current`` (a term covers ``on_date``), ``expired`` (a paid term has started
    and run out), ``new`` (the only term is unpaid, so the member joined but has
    never been covered) or ``none`` (nothing at all).  ``on_date`` defaults to the
    current local date.  An anonymous caller, or none at all, is answered
    ``none`` with no expiry, no plan and ``is_lifetime`` false, so a signed-out
    visitor is never mistaken for a lapsed member.

    ``expires_on`` is the end of the member's unbroken coverage, so a renewal
    bought today shows next year's date immediately, and is ``None`` for a
    lifetime term.  ``plan`` is the name of the plan behind the term reported.
    """
    on_date = on_date or timezone.localdate()

    if not isinstance(user, User):
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
        .exclude(status__in=(MembershipStatusChoices.CANCELED, MembershipStatusChoices.NEW))
        .filter(starts_on__lte=on_date)
        .order_by("-ends_on", "-starts_on")
        .first()
    )
    if past is not None:
        return {
            "status": MembershipState.EXPIRED,
            "expires_on": past.ends_on,
            "plan": past.plan.name,
            "is_lifetime": False,
        }

    unpaid = (
        user.memberships.select_related("plan")
        .filter(status=MembershipStatusChoices.NEW)
        .order_by("-starts_on")
        .first()
    )
    if unpaid is not None:
        return {
            "status": MembershipState.NEW,
            "expires_on": unpaid.ends_on,
            "plan": unpaid.plan.name,
            "is_lifetime": False,
        }
    return _no_membership()


def membership_annotations(today: date | None = None) -> dict[str, Exists | Subquery]:
    """Annotations restating :func:`membership_status` as correlated subqueries.

    The keys are the eight names in ``MembershipAnnotations``.  ``today``
    defaults to the current local date, which is read when this is called, so a
    queryset built per request always answers for the day of the request.  Splat
    the result into ``QuerySet.annotate`` on a ``User`` queryset, or use
    :func:`with_membership`.
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

    started = Membership.objects.exclude(
        status__in=(MembershipStatusChoices.CANCELED, MembershipStatusChoices.NEW)
    ).filter(user=OuterRef("pk"), starts_on__lte=today)
    past = started.order_by(F("ends_on").desc(nulls_first=True), "-starts_on")

    unpaid = Membership.objects.filter(
        user=OuterRef("pk"), status=MembershipStatusChoices.NEW
    ).order_by("-starts_on")

    return {
        "covers_today": Exists(
            active.filter(user=OuterRef("pk"), starts_on__lte=today).filter(
                Q(ends_on__isnull=True) | Q(ends_on__gte=today)
            )
        ),
        "has_started_term": Exists(started),
        "has_unpaid_term": Exists(unpaid),
        "unpaid_end": Subquery(unpaid.values("ends_on")[:1], output_field=DateField()),
        "unpaid_plan": Subquery(unpaid.values("plan__name")[:1], output_field=CharField()),
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


def with_membership(queryset: QuerySet[User], *, today: date | None = None) -> QuerySet[MemberRow]:
    """``queryset`` of users, carrying the membership annotations.

    Every row then answers ``membership_status`` without a further query, which
    :func:`membership_payload` and :func:`membership_of` read back.  The status
    is worked out for ``today``, defaulting to the current local date.
    """
    # django-stubs can only follow ``annotate`` when the annotations are spelled out
    # as keyword arguments, so the row type is stated here rather than inferred.
    return cast("QuerySet[MemberRow]", queryset.annotate(**membership_annotations(today)))


def membership_payload(user: MemberRow) -> MembershipStatusDict:
    """Read the annotated status back in ``membership_status`` shape.

    Answers exactly what :func:`membership_status` would for the same row, out
    of the annotations alone and with no further query.  ``user`` must have come
    from :func:`with_membership`, otherwise the annotations are missing and the
    read raises ``AttributeError``; reach for :func:`membership_of` when that is
    not guaranteed.
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
    if user.has_unpaid_term:
        return {
            "status": MembershipState.NEW,
            "expires_on": user.unpaid_end,
            "plan": user.unpaid_plan,
            "is_lifetime": False,
        }
    return _no_membership()


def membership_of(user: User) -> MembershipStatusDict:
    """The membership summary for ``user``, however the row was fetched.

    A user that came through :func:`with_membership` is answered from its
    annotations, at no extra cost; any other user falls back to
    :func:`membership_status`, which spends a query or two working it out in
    Python.  Both answers are identical.
    """
    if hasattr(user, "covers_today"):
        # django-stubs cannot tell an annotated row from a plain one, so the
        # test above is what proves the annotations are there to be read.
        return membership_payload(cast("MemberRow", user))
    return membership_status(user)


@transaction.atomic
def activate_term(
    user: User,
    plan: MembershipPlan,
    *,
    source: str = MembershipSource.PAYMENT,
    payment: Payment | None = None,
    granted_by: User | None = None,
    starts_on: date | None = None,
    note: str = "",
) -> Membership:
    """Create (or return) the membership term for ``plan``.

    A renewal starts the day after the current expiry when the member is
    already current; otherwise it starts today, and ``starts_on`` overrides both.
    ``ends_on`` is ``starts_on + duration_days - 1``, or ``None`` for a lifetime
    plan.  ``source`` records how the term was come by, ``granted_by`` the
    administrator behind a manual grant, and ``note`` their reason.

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
