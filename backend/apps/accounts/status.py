"""Account status: deactivating and reactivating an account, and blocking reactivation.

An account is deactivated two ways: by its owner, from their profile
(:func:`deactivate_own_account`), and by an administrator
(:func:`deactivate_account`).  It is reactivated by its owner, signing in or
completing a password reset (:func:`reactivate_own_account`), or by an administrator
(:func:`reactivate_account`).  These functions write the account's flag, its audit
line, and its notification event; the membership terms and the standing payment
mandates that go with a change of status are the caller's, in
``apps.accounts.api.account_actions`` and ``apps.accounts.api.views``.

A user administrator may also block an account from reactivating
(:func:`set_reactivation_blocked`).  A blocked account stays deactivated: its owner is
told it has been closed whenever they try to bring it back, and no administrator
reactivates it until the block is lifted.
"""

from __future__ import annotations

from django.contrib.auth import SESSION_KEY
from django.contrib.sessions.models import Session
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.roles import SYSTEM_ADMIN
from apps.accounts.services import (
    effective_roles,
    is_donor,
    may_edit_protected_fields,
    send_email_verification,
)
from caldart import audit, events
from caldart.exceptions import DomainError
from caldart.mail import org_name, send_on_commit

SELF_DEACTIVATION_REFUSED = "You cannot deactivate your own account."
STATUS_CHANGE_REFUSED = (
    "You cannot activate or deactivate an account that holds roles you do not hold."
)
SYSTEM_ADMIN_SELF_DEACTIVATION_REFUSED = (
    "A system administrator cannot deactivate their own account."
)
DONOR_SELF_DEACTIVATION_REFUSED = "A donor has no portal account to deactivate."
DONOR_REACTIVATION_REFUSED = "A donor has no portal account to reactivate."
ALREADY_DEACTIVATED = "That account is already deactivated."
ALREADY_ACTIVE = "That account is already active."
REACTIVATION_BLOCKED_REFUSED = (
    "A user administrator has blocked this account from reactivating. "
    "Allow reactivation on its user record first."
)
SELF_BLOCK_REFUSED = "You cannot block your own account."
BLOCK_REFUSED = "You cannot block or unblock an account that holds roles you do not hold."
DONOR_BLOCK_REFUSED = "A donor has no portal account to block."


def closed_account_message() -> str:
    """What the owner of a blocked account is told when they try to bring it back.

    ``"This account has been closed. Contact <organization name> to reopen it."``,
    the name read from the site settings (``CalDART`` before anyone has set one).
    """
    return f"This account has been closed. Contact {org_name()} to reopen it."


# --------------------------------------------------------------------------
# The owner's own deactivation and reactivation
# --------------------------------------------------------------------------
def deactivate_own_account(user: User) -> None:
    """Clear ``user``'s active flag at their own request.

    A system administrator -- the role, or a Django superuser -- is refused with
    ``DomainError("A system administrator cannot deactivate their own account.")``, so
    the site is never left without one by accident, and a donor, who has no portal
    account, with ``DomainError("A donor has no portal account to deactivate.")``; each
    refusal is recorded at WARNING as ``account.deactivate`` with the reason
    ``system_admin_target`` or ``donor_account``.  Otherwise the account is saved
    inactive and the change is recorded as ``account.deactivate`` with
    ``self_service=true`` and raised as the ``account_deactivated`` event with
    ``actor=None``.  The kind, the roles and every record are kept.  The caller cancels
    the mandates, suspends the membership, and ends the session.
    """
    if is_donor(user):
        audit.refuse(
            audit.ACCOUNT_DEACTIVATE, actor=user, target=user, reason=audit.REASON_DONOR_ACCOUNT
        )
        raise DomainError(DONOR_SELF_DEACTIVATION_REFUSED)
    if SYSTEM_ADMIN in effective_roles(user):
        audit.refuse(
            audit.ACCOUNT_DEACTIVATE,
            actor=user,
            target=user,
            reason=audit.REASON_SYSTEM_ADMIN_TARGET,
        )
        raise DomainError(SYSTEM_ADMIN_SELF_DEACTIVATION_REFUSED)
    user.is_active = False
    user.save(update_fields=["is_active", "updated_at"])
    audit.record(audit.ACCOUNT_DEACTIVATE, actor=user, target=user, self_service=True)
    events.emit("account_deactivated", user=user, actor=None)


def deactivated_account(email: str, password: str) -> User | None:
    """The deactivated account ``email`` names, when ``password`` is its password.

    The address is compared case-insensitively.  ``None`` for an unknown address, an
    active account, a donor's account, and a wrong password alike, so a caller can
    say nothing that tells them apart.  A blocked account is returned like any other
    deactivated one; the caller reads ``reactivation_blocked`` to tell its owner it is
    closed.
    """
    user = User.objects.filter(email__iexact=email.strip(), is_active=False).first()
    if user is None or is_donor(user) or not user.check_password(password):
        return None
    return user


def reactivate_own_account(user: User) -> None:
    """Set ``user``'s active flag again, the person having proved who they are.

    A blocked account is refused with ``DomainError`` carrying
    :func:`closed_account_message`, recorded at WARNING as ``account.activate`` with
    the reason ``reactivation_blocked``, and nothing changes.  Otherwise the kind and
    roles are exactly as they were.  The change is recorded as ``account.activate``
    with ``self_service=true`` and raised as the ``account_reactivated`` event with
    ``actor=None``, and an account whose address was never verified is mailed a
    verification link once the transaction commits.  The caller restores the
    membership and, where it signs the person in, does so.
    """
    if user.reactivation_blocked:
        audit.refuse(
            audit.ACCOUNT_ACTIVATE,
            actor=user,
            target=user,
            reason=audit.REASON_REACTIVATION_BLOCKED,
        )
        raise DomainError(closed_account_message())
    user.is_active = True
    user.save(update_fields=["is_active", "updated_at"])
    audit.record(audit.ACCOUNT_ACTIVATE, actor=user, target=user, self_service=True)
    events.emit("account_reactivated", user=user, actor=None)
    _verify_on_commit(user)


# --------------------------------------------------------------------------
# An administrator's deactivation and reactivation
# --------------------------------------------------------------------------
def deactivate_account(actor: User, target: User) -> None:
    """Clear ``target``'s active flag on ``actor``'s behalf, and end its sessions.

    Refused with ``DomainError``, in this order and changing nothing: a donor ("A
    donor has no portal account to deactivate."), the actor's own account ("You cannot
    deactivate your own account."), an account holding roles the actor does not hold
    ("You cannot activate or deactivate an account that holds roles you do not
    hold." -- which is how a system administrator's account is kept from anyone but
    another system administrator), and an account already deactivated ("That account
    is already deactivated.").  The first three are recorded at WARNING as
    ``account.deactivate`` with the reasons ``donor_account``, ``self_deactivation``,
    and ``roles_not_held``.

    Otherwise the account is saved inactive, recorded as ``account.deactivate`` under
    ``actor``, and raised as the ``account_deactivated`` event naming ``actor``, and
    every session signed in to it is ended (:func:`end_sessions`).  The kind, the roles
    and every record are kept.  The caller cancels the mandates and suspends the
    membership.
    """
    if is_donor(target):
        _refuse(audit.ACCOUNT_DEACTIVATE, actor, target, audit.REASON_DONOR_ACCOUNT)
        raise DomainError(DONOR_SELF_DEACTIVATION_REFUSED)
    if target.pk == actor.pk:
        _refuse(audit.ACCOUNT_DEACTIVATE, actor, target, audit.REASON_SELF_DEACTIVATION)
        raise DomainError(SELF_DEACTIVATION_REFUSED)
    if not may_edit_protected_fields(actor, target):
        _refuse(audit.ACCOUNT_DEACTIVATE, actor, target, audit.REASON_ROLES_NOT_HELD)
        raise DomainError(STATUS_CHANGE_REFUSED)
    if not target.is_active:
        raise DomainError(ALREADY_DEACTIVATED)
    target.is_active = False
    target.save(update_fields=["is_active", "updated_at"])
    audit.record(audit.ACCOUNT_DEACTIVATE, actor=actor, target=target)
    events.emit("account_deactivated", user=target, actor=actor)
    end_sessions(target)


def reactivate_account(actor: User, target: User) -> None:
    """Set ``target``'s active flag again on ``actor``'s behalf.

    Refused with ``DomainError``, in this order and changing nothing: a donor ("A
    donor has no portal account to reactivate."), an account holding roles the actor
    does not hold ("You cannot activate or deactivate an account that holds roles you
    do not hold."), an account a user administrator has blocked from reactivating ("A
    user administrator has blocked this account from reactivating. Allow reactivation
    on its user record first."), and an account already active ("That account is
    already active.").  The first three are recorded at WARNING as
    ``account.activate`` with the reasons ``donor_account``, ``roles_not_held``, and
    ``reactivation_blocked``.

    Otherwise the account is saved active, recorded as ``account.activate`` under
    ``actor``, and raised as the ``account_reactivated`` event naming ``actor``, and an
    account whose address was never verified is mailed a verification link once the
    transaction commits, as the owner's own reactivation does.  The caller restores the
    membership.
    """
    if is_donor(target):
        _refuse(audit.ACCOUNT_ACTIVATE, actor, target, audit.REASON_DONOR_ACCOUNT)
        raise DomainError(DONOR_REACTIVATION_REFUSED)
    if not may_edit_protected_fields(actor, target):
        _refuse(audit.ACCOUNT_ACTIVATE, actor, target, audit.REASON_ROLES_NOT_HELD)
        raise DomainError(STATUS_CHANGE_REFUSED)
    if target.reactivation_blocked:
        _refuse(audit.ACCOUNT_ACTIVATE, actor, target, audit.REASON_REACTIVATION_BLOCKED)
        raise DomainError(REACTIVATION_BLOCKED_REFUSED)
    if target.is_active:
        raise DomainError(ALREADY_ACTIVE)
    target.is_active = True
    target.save(update_fields=["is_active", "updated_at"])
    audit.record(audit.ACCOUNT_ACTIVATE, actor=actor, target=target)
    events.emit("account_reactivated", user=target, actor=actor)
    _verify_on_commit(target)


# --------------------------------------------------------------------------
# Blocking reactivation
# --------------------------------------------------------------------------
def check_block(actor: User, target: User, *, blocked: bool) -> None:
    """Refuse ``actor`` setting (``blocked``) or clearing ``target``'s block.

    Raises ``DomainError``, in this order: a donor ("A donor has no portal account to
    block."), the actor's own account ("You cannot block your own account."), and an
    account holding roles the actor does not hold ("You cannot block or unblock an
    account that holds roles you do not hold.").  Each is recorded at WARNING as
    ``account.block`` or ``account.unblock`` with the reason ``donor_account``,
    ``self_deactivation``, or ``roles_not_held``.  Returns ``None`` when the change is
    allowed.  Who may call this at all is the endpoint's rule.
    """
    action = audit.ACCOUNT_BLOCK if blocked else audit.ACCOUNT_UNBLOCK
    if is_donor(target):
        _refuse(action, actor, target, audit.REASON_DONOR_ACCOUNT)
        raise DomainError(DONOR_BLOCK_REFUSED)
    if target.pk == actor.pk:
        _refuse(action, actor, target, audit.REASON_SELF_DEACTIVATION)
        raise DomainError(SELF_BLOCK_REFUSED)
    if not may_edit_protected_fields(actor, target):
        _refuse(action, actor, target, audit.REASON_ROLES_NOT_HELD)
        raise DomainError(BLOCK_REFUSED)


def set_reactivation_blocked(actor: User, target: User, *, blocked: bool) -> bool:
    """Set or clear ``target``'s ``reactivation_blocked`` flag, and say whether it moved.

    Raises what :func:`check_block` raises.  A flag already as asked is left alone,
    records nothing, and returns False.  Otherwise the flag is saved and recorded as
    ``account.block`` or ``account.unblock`` under ``actor``, and the return is True.
    Setting the flag does not deactivate the account: the caller deactivates an active
    account first.  Clearing it leaves the account deactivated, for its owner to bring
    back.
    """
    check_block(actor, target, blocked=blocked)
    if target.reactivation_blocked == blocked:
        return False
    target.reactivation_blocked = blocked
    target.save(update_fields=["reactivation_blocked", "updated_at"])
    audit.record(
        audit.ACCOUNT_BLOCK if blocked else audit.ACCOUNT_UNBLOCK, actor=actor, target=target
    )
    return True


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def end_sessions(user: User) -> int:
    """Delete every unexpired session signed in to ``user``, and return how many.

    The sessions live in the database (Django's default session engine), so each one
    is decoded and matched on the account id it carries.  Django already refuses a
    deactivated account on its next request; deleting the rows makes the end
    immediate and leaves nothing behind to come back to life.
    """
    signed_in = str(user.pk)
    ended = [
        session.pk
        for session in Session.objects.filter(expire_date__gt=timezone.now())
        if session.get_decoded().get(SESSION_KEY) == signed_in
    ]
    Session.objects.filter(pk__in=ended).delete()
    return len(ended)


def _refuse(action: str, actor: User, target: User, reason: str) -> None:
    """Record ``actor``'s refused ``action`` on ``target`` at WARNING with ``reason``."""
    audit.refuse(action, actor=actor, target=target, reason=reason)


def _verify_on_commit(user: User) -> None:
    """Mail ``user`` a verification link once the transaction commits, if unverified.

    A mail server that refuses it is logged (``caldart.mail.send_on_commit``), and the
    reactivation stands.
    """
    if user.email_verified_at is None:
        send_on_commit(
            lambda: send_email_verification(user),
            what=f"the email verification for account {user.pk}",
        )
