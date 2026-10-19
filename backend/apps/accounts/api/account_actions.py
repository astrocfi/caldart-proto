"""What an administrator's account actions do beyond the account row.

``apps.accounts.status`` writes an account's active and blocked flags.  Deactivating
also withdraws every standing payment authority and sets the membership aside, and
reactivating brings the membership back, so the actions the member record and the
user record offer run here, where the payments and members apps may be reached.  So
does the user record's **Require a new password**, which shuts an account's password
out and ends its sessions.  Each locks the account's row for its transaction, so two
administrators acting on one account at once take turns.  A refusal raises the
``DomainError`` the status, lifecycle, or password rule raised, and nothing is written.
"""

from __future__ import annotations

from django.db import transaction

from apps.accounts import mfa
from apps.accounts.history import record_account_change
from apps.accounts.models import AccountChangeKind, User
from apps.accounts.services import is_donor, may_edit_protected_fields
from apps.accounts.status import (
    check_block,
    clear_password_and_end_sessions,
    deactivate_account,
    reactivate_account,
    set_reactivation_blocked,
)
from apps.members.services import refuse_tombstone_change, restore_terms, suspend_terms
from apps.payments.renewals.mandates import cancel_all_mandates, switch_to_friend
from caldart import audit
from caldart.exceptions import DomainError

#: Why :func:`require_new_password_for` refuses a donor, a tombstone included.
DONOR_CREDENTIAL_REFUSED = "A donor cannot sign in, so there isn't a password to replace."

#: Why it refuses the administrator's own account, which has its own page for this.
SELF_CREDENTIAL_REFUSED = (
    'You cannot require a new password for your own account. Use "Change password" instead.'
)

#: Why it refuses an account holding a role the administrator lacks.
CREDENTIAL_ROLES_REFUSED = (
    "You cannot require a new password for an account that holds "
    "administrative roles you do not hold."
)


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

    This is :func:`apps.payments.renewals.mandates.switch_to_friend` with ``actor``
    recorded on the canceled renewal and the ``account.kind`` audit line: a current
    membership is kept to its end and the account becomes a friend the day after, or at
    once, and ``keep_contribution`` answers whether a renewal's contribution carries on
    as a recurring donation.  Raises what that function raises.  Returns the account.
    """
    return switch_to_friend(target, keep_contribution=keep_contribution, actor=actor)


@transaction.atomic
def block_for(actor: User, target: User) -> User:
    """Block ``target`` from reactivating, deactivating it first when it is active.

    The block is refused first by :func:`apps.accounts.status.check_block`; an active
    account is then deactivated exactly as :func:`deactivate_for` does it, and the flag
    is set and recorded as ``account.block``.  Blocking an account already blocked
    doesn't change anything.  Returns the account as stored.
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
def require_new_password_for(actor: User, target: User) -> User:
    """Shut ``target``'s current password out on ``actor``'s behalf, ending its sessions.

    Refused with ``DomainError``, in this order and without changing anything: a
    donor, a tombstone among them (:data:`DONOR_CREDENTIAL_REFUSED`), the actor's own
    account (:data:`SELF_CREDENTIAL_REFUSED`), and an account holding roles the actor
    does not hold (:data:`CREDENTIAL_ROLES_REFUSED`).  Each is recorded at WARNING as
    ``account.new_password`` with the reason ``donor_account``,
    ``own_account``, or ``roles_not_held``.

    Otherwise :func:`apps.accounts.status.clear_password_and_end_sessions` makes the
    password unusable, so neither signing in nor ``/auth/reactivate`` accepts the old
    one and every reset link made for it is spent, and ends every session signed in to
    the account.  The change is recorded as ``account.new_password`` under ``actor``
    and as a ``new_password`` entry of the account's history.  The active flag and the
    reactivation block are left as they are.  Mailing the owner a link to choose a new
    password is the caller's.  Requiring it again repeats all of this.  Returns the
    account as stored.
    """
    user = _locked(target)
    action = audit.ACCOUNT_REQUIRE_RESET
    if is_donor(user):
        audit.refuse(action, actor=actor, target=user, reason=audit.REASON_DONOR_ACCOUNT)
        raise DomainError(DONOR_CREDENTIAL_REFUSED)
    if user.pk == actor.pk:
        audit.refuse(action, actor=actor, target=user, reason=audit.REASON_OWN_ACCOUNT)
        raise DomainError(SELF_CREDENTIAL_REFUSED)
    if not may_edit_protected_fields(actor, user):
        audit.refuse(action, actor=actor, target=user, reason=audit.REASON_ROLES_NOT_HELD)
        raise DomainError(CREDENTIAL_ROLES_REFUSED)
    clear_password_and_end_sessions(user)
    audit.record(action, actor=actor, target=user)
    record_account_change(AccountChangeKind.NEW_PASSWORD, actor=actor, target=user)
    return user


@transaction.atomic
def unblock_for(actor: User, target: User) -> User:
    """Lift ``target``'s block, leaving the account deactivated for its owner to reopen.

    Refused by :func:`apps.accounts.status.check_block`; recorded as
    ``account.unblock``.  Lifting a block that is not set doesn't change anything.
    Returns the account as stored.
    """
    user = _locked(target)
    set_reactivation_blocked(actor, user, blocked=False)
    return user


@transaction.atomic
def reset_two_factor_for(actor: User, target: User) -> User:
    """Reset ``target``'s two-factor sign-in on ``actor``'s behalf, for a lost phone.

    A tombstone is refused first, as every edit of one is
    (:func:`apps.members.services.refuse_tombstone_change`, audited as
    ``account.mfa_reset``); then :func:`apps.accounts.mfa.reset_two_factor` refuses or
    resets: the device and backup codes are deleted, every session signed in to the
    account is ended, and the person is mailed.  Returns the account as stored.
    """
    user = _locked(target)
    refuse_tombstone_change(actor, user, audit.ACCOUNT_MFA_RESET)
    mfa.reset_two_factor(actor, user)
    return user
