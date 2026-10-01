"""What an administrator's account actions do beyond the account row.

``apps.accounts.status`` writes an account's active and blocked flags.  Deactivating
also withdraws every standing payment authority and sets the membership aside, and
reactivating brings the membership back, so the actions the member record and the
user record offer run here, where the payments and members apps may be reached.  Each
locks the account's row for its transaction, so two administrators acting on one
account at once take turns.  A refusal raises the ``DomainError`` the status or
lifecycle rule raised, and nothing is written.
"""

from __future__ import annotations

from django.db import transaction

from apps.accounts.models import User
from apps.accounts.status import (
    check_block,
    deactivate_account,
    reactivate_account,
    set_reactivation_blocked,
)
from apps.members.services import restore_terms, suspend_terms
from apps.payments.renewals import cancel_all_mandates, switch_to_friend


def _locked(target: User) -> User:
    """``target``'s row, locked until the transaction ends and read afresh."""
    return User.objects.select_for_update().get(pk=target.pk)


@transaction.atomic
def deactivate_for(actor: User, target: User) -> User:
    """Deactivate ``target`` on ``actor``'s behalf, as its owner's own deactivation would.

    The account is refused or deactivated by
    :func:`apps.accounts.status.deactivate_account` (which also ends every session
    signed in to it); then every automatic renewal and recurring donation is canceled
    under ``actor`` (a pending one is discarded) and every membership term with time
    left is suspended under ``actor``.  Returns the account as stored.
    """
    user = _locked(target)
    deactivate_account(actor, user)
    cancel_all_mandates(user, actor=actor)
    suspend_terms(user, actor=actor)
    return user


@transaction.atomic
def reactivate_for(actor: User, target: User) -> User:
    """Reactivate ``target`` on ``actor``'s behalf, as its owner's own reactivation would.

    The account is refused or reactivated by
    :func:`apps.accounts.status.reactivate_account`; then each suspended term is active
    again, or expired if it ran out meanwhile, under ``actor``.  Canceled mandates stay
    canceled.  Returns the account as stored.
    """
    user = _locked(target)
    reactivate_account(actor, user)
    restore_terms(user, actor=actor)
    return user


@transaction.atomic
def make_friend_for(actor: User, target: User, *, keep_contribution: bool | None) -> User:
    """Make ``target`` a friend on ``actor``'s behalf, as their own switch would.

    This is :func:`apps.payments.renewals.switch_to_friend` with ``actor`` recorded on
    the canceled renewal and the ``account.kind`` audit line: a current membership is
    kept to its end and the account becomes a friend the day after, or at once, and
    ``keep_contribution`` answers whether a renewal's contribution carries on as a
    recurring donation.  Raises what that function raises.  Returns the account.
    """
    return switch_to_friend(target, keep_contribution=keep_contribution, actor=actor)


@transaction.atomic
def block_for(actor: User, target: User) -> User:
    """Block ``target`` from reactivating, deactivating it first when it is active.

    The block is refused first by :func:`apps.accounts.status.check_block`; an active
    account is then deactivated exactly as :func:`deactivate_for` does it, and the flag
    is set and recorded as ``account.block``.  Blocking an account already blocked
    changes nothing.  Returns the account as stored.
    """
    user = _locked(target)
    check_block(actor, user, blocked=True)
    if user.is_active:
        deactivate_account(actor, user)
        cancel_all_mandates(user, actor=actor)
        suspend_terms(user, actor=actor)
    set_reactivation_blocked(actor, user, blocked=True)
    return user


@transaction.atomic
def unblock_for(actor: User, target: User) -> User:
    """Lift ``target``'s block, leaving the account deactivated for its owner to reopen.

    Refused by :func:`apps.accounts.status.check_block`; recorded as
    ``account.unblock``.  Lifting a block that is not set changes nothing.  Returns the
    account as stored.
    """
    user = _locked(target)
    set_reactivation_blocked(actor, user, blocked=False)
    return user
