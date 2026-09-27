"""The passage between member and friend, and the daily catch-up that follows it.

A member becomes a friend when they choose to, when an administrator changes their
kind, or when their membership simply runs out; a friend or a lapsed member becomes
a member again by paying or by an administrator's grant.  This module holds the
member-initiated switch (:func:`become_friend`, :func:`undo_become_friend`) and the
two daily scans that keep the stored kind honest (:func:`convert_due_friends`,
:func:`expire_lapsed_memberships`).  ``apps.members.services`` holds everything else:
:func:`~apps.members.services.account_kind` is the single source of truth for what
kind an account counts as right now, which this module reads but never restates.
"""

from __future__ import annotations

from datetime import date, timedelta

from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

from apps.accounts.models import AccountKind, User
from apps.accounts.services import DONOR_KIND_REFUSED, is_donor
from apps.members.models import Membership, MembershipState, MembershipStatusChoices
from apps.members.services import account_kind, membership_status
from caldart import audit, events
from caldart.exceptions import DomainError

#: Refusals :func:`check_can_become_friend` and :func:`undo_become_friend` raise.
LIFETIME_STAYS_MEMBER = "A lifetime member stays a member."
ALREADY_FRIEND = "You are already a friend of CalDART."
NO_PENDING_CHANGE = "You have no pending change."


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
    as ``account.kind`` with ``to=friend`` and ``on=<friend_on>`` under ``command``,
    and raised as the ``became_friend`` event with ``how="lapsed"``.
    The daily reminder run calls this, so the stored kind catches up with the one
    :func:`~apps.members.services.account_kind` already reports.  A date still ahead
    is left alone.

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
        user.kind, user.friend_on = AccountKind.FRIEND, None
        events.emit("became_friend", user=user, how="lapsed")
    return converted


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
    ``member`` until then.  Anybody else is stored as a friend at once, which raises
    the ``became_friend`` event with ``how="chose"``; a change that waits raises it
    from :func:`convert_due_friends` on the day.  One
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
    if user.kind == AccountKind.FRIEND:
        events.emit("became_friend", user=user, how="chose")
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


@transaction.atomic
def expire_lapsed_memberships(on_date: date | None = None) -> int:
    """Flip active terms whose ``ends_on`` is before ``on_date`` to ``expired``.

    ``on_date`` defaults to the local date.  Returns how many terms were flipped.
    Used by the reminder scanner and by the seed to keep data honest.

    Each account whose terms were flipped and that is no longer current on
    ``on_date`` raises one ``membership_expired`` event, with the account and the
    flipped term that ended last.  An account a later term still covers, such as a
    renewal bought early, has not lost its membership and raises nothing.
    """
    on_date = on_date or timezone.localdate()
    lapsed = list(
        Membership.objects.select_for_update()
        .select_related("user")
        .filter(status=MembershipStatusChoices.ACTIVE, ends_on__isnull=False, ends_on__lt=on_date)
        .order_by("user_id", "ends_on", "id")
    )
    flipped = Membership.objects.filter(pk__in=[term.pk for term in lapsed]).update(
        status=MembershipStatusChoices.EXPIRED, updated_at=timezone.now()
    )
    # Later terms overwrite earlier ones, so each account keeps the one that ended last.
    last_terms = {term.user_id: term for term in lapsed}
    for term in last_terms.values():
        term.status = MembershipStatusChoices.EXPIRED
        if membership_status(term.user, on_date)["status"] != MembershipState.CURRENT:
            events.emit("membership_expired", user=term.user, term=term)
    return flipped
