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
    The most recent term that has started and is neither canceled nor
    suspended, which ``membership_status`` reports for an expired member.

``effective_kind``
    :func:`kind_annotation`, the SQL statement of :func:`account_kind`.  A row
    whose effective kind is ``friend`` or ``donor`` reads as that before any term
    is looked at, exactly as ``membership_status`` answers it.

``tests/test_members_admin_status.py`` checks the two implementations agree
over a deliberately awkward set of histories, including early renewals, gaps,
canceled terms, and friends.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING, Any, NoReturn, TypedDict, cast

from django.contrib.auth.models import AnonymousUser
from django.db import transaction
from django.db.models import (
    Case,
    CharField,
    DateField,
    Exists,
    F,
    OuterRef,
    Q,
    QuerySet,
    Subquery,
    Value,
    When,
)
from django.db.models.deletion import ProtectedError
from django.http import HttpRequest
from django.utils import timezone

from apps.accounts.models import AccountKind, User
from apps.accounts.roles import SYSTEM_ADMIN
from apps.accounts.services import (
    DONOR_KIND_REFUSED,
    AccountChanges,
    DonorUpgrade,
    create_account,
    effective_roles,
    is_donor,
    send_email_verification,
    send_password_invitation,
    set_kind,
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
from caldart.exceptions import DomainError, DomainPermissionError

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
    coverage_end: date | None
    coverage_plan: str | None
    lifetime_plan: str | None
    past_end: date | None
    past_plan: str | None
    joined_on: date | None
    effective_kind: str


if TYPE_CHECKING:
    #: A user row that came through :func:`with_membership`, so the membership
    #: annotations can be read straight off it.
    type MemberRow = WithAnnotations[User, MembershipAnnotations]

#: The profile fields an administrator may set when creating or editing a member.
type ProfileChanges = dict[str, Any]

SELF_DELETE_REFUSED = "You cannot delete your own account."
SYSTEM_ADMIN_DELETE_REFUSED = "Only a system administrator can delete a system administrator."

#: Account columns whose edit counts as a profile write: a name or an email
#: is what a member record shows alongside the rest of the profile.
_PROFILE_TOUCHING_ACCOUNT_FIELDS = frozenset({"email", "first_name", "last_name"})


def touch_profile(profile: MemberProfile) -> None:
    """Stamp ``profile.profile_updated_at`` as now, and save that and ``updated_at``.

    Called after every write of profile information: the member's own
    ``PATCH /me/profile``, an administrator's edit to the profile or to the
    account's name or email, an aircraft attached or detached, and the
    profile's creation.  Never called for a payment, a membership grant or
    renewal, a reminder, or a role change.  ``updated_at`` is listed in
    ``update_fields`` alongside the stamp because Django skips an ``auto_now``
    field that is left out, and this is a genuine write to the row.
    """
    profile.profile_updated_at = timezone.now()
    profile.save(update_fields=["profile_updated_at", "updated_at"])


# --------------------------------------------------------------------------
# The member record: account plus profile
# --------------------------------------------------------------------------
@transaction.atomic
def register_member(
    *,
    email: str,
    password: str,
    first_name: str = "",
    last_name: str = "",
    kind: AccountKind = AccountKind.MEMBER,
) -> User:
    """Create the account ``POST /auth/register`` signs in, and return it.

    ``kind`` is a member or a friend.  The profile starts blank on purpose -- the
    join wizard fills it in -- but it must exist so ``/me/profile`` is a PATCH rather
    than a create.  Account and profile are written together, so a failure leaves no
    half-made member.  The profile's ``profile_updated_at`` is stamped as the moment
    it was written.  The account starts unverified, and once the transaction commits
    its address is mailed a verification link.

    An address that belongs to a donor is not a new account, and the donor is
    returned still a donor: only the password is written, which a donor cannot sign
    in with.  The verification link mailed to the donor's address carries the names
    and the kind, and following it upgrades the donor in place
    (:func:`apps.accounts.services.verify_email`), so the gifts already made stay on
    the account and nobody reaches them without proving the address.
    """
    donor = User.objects.filter(email__iexact=email.strip(), kind=AccountKind.DONOR).first()
    if donor is not None:
        donor.set_password(password)
        donor.save(update_fields=["password", "updated_at"])
        upgrade: DonorUpgrade = {
            "first_name": first_name.strip(),
            "last_name": last_name.strip(),
            "kind": kind.value,
        }
        MemberProfile.objects.get_or_create(user=donor)
        transaction.on_commit(lambda: send_email_verification(donor, upgrade=upgrade))
        return donor
    user = create_account(
        email=email,
        password=password,
        first_name=first_name,
        last_name=last_name,
        kind=kind,
    )
    profile, _ = MemberProfile.objects.get_or_create(user=user)
    touch_profile(profile)
    transaction.on_commit(lambda: send_email_verification(user))
    return user


@transaction.atomic
def create_member(
    actor: User,
    *,
    email: str,
    password: str = "",
    first_name: str = "",
    last_name: str = "",
    kind: AccountKind = AccountKind.MEMBER,
    profile: ProfileChanges | None = None,
    request: HttpRequest | None = None,
) -> User:
    """Create a member or a friend an administrator is entering, and return the account.

    ``kind`` is the kind of person, a member unless it says friend.  ``profile`` is
    the profile fields to record, which on the day somebody joins
    at an airshow may be none of them.  Without a password the account holds an
    unusable one and is mailed an invitation to set the first, whose link also
    proves the address; with one it is mailed a verification link instead.  Either
    mail is queued past the commit, so a create that rolls back mails nobody.
    ``request`` only tells the invitation which site's name and contact address to
    use.  The new
    profile's ``profile_updated_at`` is stamped as the moment it was created.
    """
    user = create_account(
        email=email, password=password, first_name=first_name, last_name=last_name, kind=kind
    )
    row = MemberProfile.objects.create(user=user, **(profile or {}))
    touch_profile(row)
    if password:
        transaction.on_commit(lambda: send_email_verification(user))
    else:
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
    every rule about who may change what, through :func:`apply_account_changes`, so
    an edit that makes a deactivated account active brings back its suspended terms.
    ``profile`` is written over the member's profile row, creating it if the account
    somehow has none.  Both halves are written together, so a refused account edit
    leaves the profile alone.

    :func:`touch_profile` stamps the profile whenever the request carries
    ``profile``, or an account ``email``, ``first_name`` or ``last_name`` --
    the fields a member record shows alongside the rest of the profile.  A
    request that only flips ``is_active`` leaves the stamp alone, and so does
    one for a target with no profile row to stamp.
    """
    apply_account_changes(actor, target, account or {})
    if profile is not None:
        row, _ = MemberProfile.objects.get_or_create(user=target)
        for field, value in profile.items():
            setattr(row, field, value)
        row.save()
        touch_profile(row)
        target.refresh_from_db()
    elif account is not None and _PROFILE_TOUCHING_ACCOUNT_FIELDS & account.keys():
        existing = MemberProfile.objects.filter(user=target).first()
        if existing is not None:
            touch_profile(existing)
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


# --------------------------------------------------------------------------
# The kind of account, in Python and in SQL
# --------------------------------------------------------------------------
#: The term states that make somebody a member once the term has started: a paid or
#: granted term, current or run out, and one a self-deactivation set aside.  A
#: canceled term, or one still to start, makes nobody a member.
MEMBER_MAKING_STATUSES = (
    MembershipStatusChoices.ACTIVE,
    MembershipStatusChoices.EXPIRED,
    MembershipStatusChoices.SUSPENDED,
)


def account_kind(user: User, today: date | None = None) -> AccountKind:
    """The kind ``user`` counts as on ``today``, which defaults to the local date.

    The stored kind is what the person asked for; this is what they are.  ``friend``
    for an account stored as a friend; for a member whose ``friend_on`` date is on or
    before ``today`` (the conversion has come, whether or not
    :func:`convert_due_friends` has written it down yet); and for a member who holds
    no term that started on or before ``today`` with the status ``active``,
    ``expired``, or ``suspended``, which is somebody who chose to be a member and has
    not yet paid, or whose only terms were canceled or are still to start.  A donor
    is ``donor``, and anybody else a ``member``.  :func:`kind_annotation` states the
    same rule in SQL.  The terms are read through ``user.memberships.all()``, so a
    prefetched set costs no query.
    """
    today = today or timezone.localdate()
    if user.kind != AccountKind.MEMBER:
        return AccountKind(user.kind)
    if user.friend_on is not None and user.friend_on <= today:
        return AccountKind.FRIEND
    has_term = any(
        term.status in MEMBER_MAKING_STATUSES and term.starts_on <= today
        for term in user.memberships.all()
    )
    return AccountKind.MEMBER if has_term else AccountKind.FRIEND


def kind_annotation(today: date | None = None) -> Case:
    """:func:`account_kind` as a ``Case`` expression over a ``User`` row.

    ``today`` defaults to the local date, read when this is called.  Annotate a
    ``User`` queryset with it to filter or order on the effective kind.
    """
    today = today or timezone.localdate()
    member_making = Membership.objects.filter(
        user=OuterRef("pk"), status__in=MEMBER_MAKING_STATUSES, starts_on__lte=today
    )
    return Case(
        When(~Q(kind=AccountKind.MEMBER), then=F("kind")),
        When(friend_on__lte=today, then=Value(AccountKind.FRIEND.value)),
        When(~Exists(member_making), then=Value(AccountKind.FRIEND.value)),
        default=Value(AccountKind.MEMBER.value),
        output_field=CharField(),
    )


def due_conversions(today: date) -> list[User]:
    """The accounts not stored as friends whose ``friend_on`` has come by ``today``."""
    return list(_due_conversions(today))


def _due_conversions(today: date) -> QuerySet[User]:
    """The accounts :func:`due_conversions` lists, as a queryset to filter or update."""
    return User.objects.filter(friend_on__isnull=False, friend_on__lte=today).exclude(
        kind=AccountKind.FRIEND
    )


def convert_due_friends(today: date | None = None) -> int:
    """Write down every conversion to friend whose day has come, and return how many.

    Each member whose ``friend_on`` is on or before ``today`` (the local date by
    default) is stored as a friend with no pending date, and the change is recorded
    as ``account.kind`` with ``to=friend`` and ``on=<friend_on>`` under ``command``.
    The daily reminder run calls this, so the stored kind catches up with the one
    :func:`account_kind` already reports.  A date still ahead is left alone.

    Each row is written only while it still qualifies, so an account that became a
    member again after the list was read -- a payment landing meanwhile clears its
    ``friend_on`` -- is left a member, counted out, and recorded nowhere.
    """
    today = today or timezone.localdate()
    converted = 0
    for user in due_conversions(today):
        written = (
            _due_conversions(today)
            .filter(pk=user.pk)
            .update(kind=AccountKind.FRIEND, friend_on=None, updated_at=timezone.now())
        )
        if written == 0:
            continue
        converted += 1
        audit.record(
            audit.ACCOUNT_KIND,
            actor=audit.COMMAND_ACTOR,
            target=user,
            to=AccountKind.FRIEND.value,
            on=str(user.friend_on),
        )
    return converted


LIFETIME_STAYS_MEMBER = "A lifetime member stays a member."
ALREADY_FRIEND = "You are already a friend of CalDART."
NO_PENDING_CHANGE = "You have no pending change."


def check_can_become_friend(user: User, today: date) -> None:
    """Refuse, with ``DomainError``, a request from ``user`` to become a friend.

    A donor is refused with :data:`DONOR_KIND_REFUSED`; an account stored as a friend,
    or whose ``friend_on`` is on or before ``today``, with :data:`ALREADY_FRIEND`; and a
    current lifetime member with :data:`LIFETIME_STAYS_MEMBER`.  A member whose change
    is pending may ask again, and so may a member who has not paid: they count as a
    friend already, but their stored kind still says ``member``.
    """
    if is_donor(user):
        raise DomainError(DONOR_KIND_REFUSED)
    if user.kind == AccountKind.FRIEND or (user.friend_on is not None and user.friend_on <= today):
        raise DomainError(ALREADY_FRIEND)
    if membership_status(user, today)["is_lifetime"]:
        raise DomainError(LIFETIME_STAYS_MEMBER)


def become_friend(user: User, today: date | None = None) -> User:
    """Make ``user`` a friend when their membership runs out, or at once, and return them.

    A membership current on ``today`` (the local date by default) is kept: ``friend_on``
    becomes the day after the unbroken coverage ends and the stored kind stays
    ``member`` until then.  Anybody else is stored as a friend at once.  One
    ``account.kind`` record, under the account itself, names ``to=friend`` and the day
    the change takes effect as ``on``.  Raises what :func:`check_can_become_friend`
    raises, before writing anything.  The automatic renewal is the caller's to end.
    """
    today = today or timezone.localdate()
    check_can_become_friend(user, today)
    status = membership_status(user, today)
    if status["status"] == MembershipState.CURRENT and status["expires_on"] is not None:
        user.friend_on = effective_on = status["expires_on"] + timedelta(days=1)
    else:
        user.kind, user.friend_on, effective_on = AccountKind.FRIEND, None, today
    user.save(update_fields=["kind", "friend_on", "updated_at"])
    audit.record(
        audit.ACCOUNT_KIND, actor=user, target=user, to=AccountKind.FRIEND, on=str(effective_on)
    )
    return user


def undo_become_friend(user: User, today: date | None = None) -> User:
    """Clear ``user``'s pending ``friend_on`` so they stay a member, and return them.

    Recorded as ``account.kind``, ``to=member`` and ``undo=true``; a canceled renewal
    stays canceled.  Raises ``DomainError`` with :data:`NO_PENDING_CHANGE` when nothing
    is pending on ``today`` (the local date by default).
    """
    today = today or timezone.localdate()
    if user.friend_on is None or account_kind(user, today) == AccountKind.FRIEND:
        raise DomainError(NO_PENDING_CHANGE)
    user.friend_on = None
    user.save(update_fields=["friend_on", "updated_at"])
    audit.record(audit.ACCOUNT_KIND, actor=user, target=user, to=AccountKind.MEMBER, undo=True)
    return user


#: The term states that never make anybody expired: a canceled term counts for
#: nothing, and a suspended one belongs to an account its holder deactivated.
NOT_PAST_STATUSES = (
    MembershipStatusChoices.CANCELED,
    MembershipStatusChoices.SUSPENDED,
)


def _friend_membership() -> MembershipStatusDict:
    """The status of a friend: ``friend``, with no expiry, no plan, and never lifetime.

    A fresh dictionary each call, so a caller that adds its own keys -- the
    ``/me/membership`` payload hangs the term history off it -- cannot reach
    the next caller's answer.
    """
    return {
        "status": MembershipState.FRIEND,
        "expires_on": None,
        "plan": None,
        "is_lifetime": False,
    }


def _donor_membership() -> MembershipStatusDict:
    """The status of a donor: ``donor``, with no expiry, no plan, and never lifetime."""
    return {
        "status": MembershipState.DONOR,
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


#: The term states :func:`_latest_expiry` chains a new term after: an active term
#: covers today or later, and a suspended one is coverage a self-deactivation set
#: aside rather than lost, restored by :func:`restore_terms` on reactivation.
COVERING_STATUSES = (MembershipStatusChoices.ACTIVE, MembershipStatusChoices.SUSPENDED)


def _latest_expiry(user: User) -> date | None:
    """Latest ``ends_on`` across active or suspended terms, ``None`` if any is lifetime.

    A checkout that settles while the account is deactivated buys a term
    :func:`activate_term` places by this same rule, so it chains after coverage a
    self-deactivation suspended rather than starting today and overlapping it.
    """
    ends: list[date] = []
    for m in user.memberships.all():
        if m.status not in COVERING_STATUSES:
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

    Returns ``{"status", "expires_on", "plan", "is_lifetime"}`` where status is one
    of four.  ``donor`` for a donor account and ``friend`` when the account's kind on
    ``on_date``, by :func:`account_kind`, is friend -- both decided before any term
    is looked at, so a friend's past or even live terms never make them current or
    expired, and ``expires_on`` and ``plan`` are ``None``.  Otherwise ``current``
    (a term covers ``on_date``) or ``expired`` (a paid or granted term has started
    and run out).  ``on_date`` defaults to the current local date.  An anonymous
    caller, or none at all, is answered with the friend shape, so a signed-out
    visitor is never mistaken for a lapsed member.

    ``expires_on`` is the end of the member's unbroken coverage, so a renewal
    bought today shows next year's date immediately, and is ``None`` for a
    lifetime term.  ``plan`` is the name of the plan behind the term reported.

    A canceled or a suspended term counts for nothing: it never covers a day and
    never makes anybody expired, so an account whose only terms are suspended reads
    as ``friend`` while it is deactivated.
    """
    on_date = on_date or timezone.localdate()

    if not isinstance(user, User):
        return _friend_membership()
    kind = account_kind(user, on_date)
    if kind == AccountKind.DONOR:
        return _donor_membership()
    if kind == AccountKind.FRIEND:
        return _friend_membership()

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
        .exclude(status__in=NOT_PAST_STATUSES)
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
    return _friend_membership()


def membership_annotations(today: date | None = None) -> dict[str, Exists | Subquery | Case]:
    """Annotations restating :func:`membership_status` as correlated subqueries.

    The keys are the names in ``MembershipAnnotations``, ``effective_kind`` among
    them (:func:`kind_annotation`).  ``today``
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

    started = Membership.objects.exclude(status__in=NOT_PAST_STATUSES).filter(
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
        "effective_kind": kind_annotation(today),
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
    if user.effective_kind == AccountKind.DONOR:
        return _donor_membership()
    if user.effective_kind == AccountKind.FRIEND:
        return _friend_membership()
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
    return _friend_membership()


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

    A renewal starts the day after the current expiry when the member is already
    current, counting a term a self-deactivation suspended as covering too, so a
    checkout that settles while the account is deactivated still chains after it
    rather than overlapping it; otherwise it starts today, and ``starts_on``
    overrides both.  ``ends_on`` is ``starts_on + duration_days - 1``, or ``None``
    for a lifetime plan.  ``source`` records how the term was come by,
    ``granted_by`` the administrator behind a manual grant, and ``note`` their
    reason.

    The member's ``member_since`` is stamped with this term's start the first
    time they hold one, and never moved afterwards: a renewal does not change
    it, and neither does a gap and a return, which is what the date means.

    Paying dues, or an administrator's grant, is what membership is: a friend who
    is given a term becomes a member (recorded as ``account.kind`` under the
    granting administrator, or ``command``), and a member with a pending
    ``friend_on`` date keeps being a member, the date cleared.  A donor's kind is
    left alone.

    A deactivated account's term is created ``SUSPENDED`` rather than ``ACTIVE``:
    a checkout a provider confirms after the payer deactivated in the meantime
    must not stand as coverage for an account that cannot sign in to use it.
    Reactivating restores it exactly as it restores a term suspended by
    deactivation itself, back-to-back with the coverage it chained after.

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
        has_covering_term = user.memberships.filter(status__in=COVERING_STATUSES).exists()
        if has_covering_term and expiry is None:
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

    status = MembershipStatusChoices.ACTIVE if user.is_active else MembershipStatusChoices.SUSPENDED
    term = Membership.objects.create(
        user=user,
        plan=plan,
        starts_on=starts_on,
        ends_on=ends_on,
        status=status,
        source=source,
        payment=payment,
        granted_by=granted_by,
        note=note,
    )
    stamp_member_since(user, starts_on)
    if not is_donor(user):
        set_kind(
            user,
            AccountKind.MEMBER,
            actor=granted_by if granted_by is not None else audit.COMMAND_ACTOR,
        )
    return term


#: The longest note a term can carry, which is the model field's own width.
MAX_TERM_NOTE = 255


def _joined_note(existing: str, addition: str) -> str:
    """``addition`` appended to ``existing``, within ``MAX_TERM_NOTE`` characters.

    The two are separated by a period and a space, and a period the old text
    already ended in is dropped rather than doubled.  ``addition`` is kept whole
    wherever it fits: the old text loses its front to make room, and disappears
    when there is no room for any of it.
    """
    addition = addition.strip()
    prefix = existing.rstrip(". ")
    if not prefix:
        return addition[:MAX_TERM_NOTE]
    room = MAX_TERM_NOTE - len(addition) - 2
    if room <= 0:
        return addition[:MAX_TERM_NOTE]
    kept = prefix[len(prefix) - room :] if len(prefix) > room else prefix
    return f"{kept}. {addition}"


@transaction.atomic
def cancel_term(term: Membership, *, actor: User | None = None, note: str = "") -> Membership:
    """Cancel ``term`` so it stops covering the member, and return the row as saved.

    A canceled term counts for nothing: ``membership_status`` skips it, so a
    member with no other active term reads as expired, or as never covered.

    ``note`` is why it was canceled -- a refund, an administrator's correction.
    It is appended to whatever the term already said, separated by a period and
    a space, with any period the old text ended in dropped so the join never
    reads ``..``.  The reason for the cancellation always survives: it is the
    older text that is trimmed, from its front, when the two together exceed
    ``MAX_TERM_NOTE`` characters, and a note that fills the field on its own
    replaces what was there.  ``actor`` is the administrator behind the
    cancellation, and is recorded in the audit log; a cancellation nobody
    initiated, such as one a provider's webhook caused, is recorded under
    ``command``.

    Canceling a term that is already canceled changes nothing but the note.
    """
    term.status = MembershipStatusChoices.CANCELED
    if note:
        term.note = _joined_note(term.note, note)
    term.save(update_fields=["status", "note", "updated_at"])
    audit.record(
        audit.MEMBERSHIP_CORRECT,
        actor=actor if actor is not None else audit.COMMAND_ACTOR,
        target=term,
        status=MembershipStatusChoices.CANCELED.value,
    )
    return term


@transaction.atomic
def suspend_terms(user: User, *, today: date | None = None) -> list[Membership]:
    """Suspend every active term of ``user``'s that has not yet run out, and return them.

    That is the term covering ``today`` (defaulting to the current local date), a
    lifetime term, and any renewal already paid for that starts later: everything the
    member would lose by leaving.  A term that has run out, and a canceled one, is
    left alone.  Each suspension is recorded as ``membership.correct`` with
    ``status=suspended``, the account itself as the actor.  Called when a person
    deactivates their own account; :func:`restore_terms` undoes it.
    """
    today = today or timezone.localdate()
    terms = list(
        user.memberships.filter(status=MembershipStatusChoices.ACTIVE)
        .filter(Q(ends_on__isnull=True) | Q(ends_on__gte=today))
        .order_by("starts_on", "id")
    )
    for held in terms:
        _set_term_status(held, MembershipStatusChoices.SUSPENDED, actor=user)
    return terms


@transaction.atomic
def restore_terms(
    user: User, *, actor: User | None = None, today: date | None = None
) -> list[Membership]:
    """Bring back every suspended term of ``user``'s, and return them.

    A term that is lifetime or ends on or after ``today`` (defaulting to the current
    local date) is ``active`` again, so a membership resumes through its old date; one
    that ran out while the account was deactivated is ``expired``.  Each change is
    recorded as ``membership.correct`` with the new status under ``actor``, the account
    itself when none is given.  Called whenever a deactivated account is active again:
    the person reactivating it, or an administrator ticking **Account is active**.
    """
    actor = actor or user
    today = today or timezone.localdate()
    terms = list(
        user.memberships.filter(status=MembershipStatusChoices.SUSPENDED).order_by(
            "starts_on", "id"
        )
    )
    for held in terms:
        running = held.ends_on is None or held.ends_on >= today
        status = MembershipStatusChoices.ACTIVE if running else MembershipStatusChoices.EXPIRED
        _set_term_status(held, status, actor=actor)
    return terms


@transaction.atomic
def apply_account_changes(actor: User, target: User, changes: AccountChanges) -> User:
    """Apply an administrator's account edit through ``update_account``, and return it.

    Every rule is ``update_account``'s.  An edit that makes a deactivated account
    active again also brings back its suspended membership through
    :func:`restore_terms` under ``actor``, as the person's own reactivation would, so
    a membership suspended when they deactivated is not lost for good.
    """
    was_active = target.is_active
    user = update_account(actor, target, changes)
    if not was_active and user.is_active:
        restore_terms(user, actor=actor)
    return user


def _set_term_status(term: Membership, status: MembershipStatusChoices, *, actor: User) -> None:
    """Save ``term`` with ``status``, recorded as ``membership.correct`` by ``actor``."""
    term.status = status
    term.save(update_fields=["status", "updated_at"])
    audit.record(audit.MEMBERSHIP_CORRECT, actor=actor, target=term, status=status.value)


def stamp_member_since(user: User, joined_on: date) -> None:
    """Record ``joined_on`` as the day ``user`` joined, if nothing has yet.

    Does nothing when the profile already carries a date, so the earliest one
    wins however the member's terms are created, and nothing at all when the
    account has no profile row.
    """
    profile = MemberProfile.objects.filter(user=user, member_since__isnull=True).first()
    if profile is None:
        return
    profile.member_since = joined_on
    profile.save(update_fields=["member_since"])


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
