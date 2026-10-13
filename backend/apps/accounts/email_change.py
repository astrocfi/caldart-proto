"""Changing an account's sign-in address: the request, the link that completes it, undo.

The address is the login and where a password reset link goes, so a change never takes
effect on the word of whoever asked.  :func:`request_email_change` records the new
address as the account's ``pending_email`` and mails it a link; the account keeps
signing in with the address it has until somebody follows that link
(:func:`complete_email_change`), which proves the new mailbox and makes the change.  A
later request replaces the pending address, and a new password drops it, so an older
link no longer matches and does nothing: the link is signed over the password the
account had when it was made, as a password reset link is.

The address the account had is told twice, when the change is asked for and when it
completes, and each notice carries a link that undoes it (:func:`undo_email_change`).
Only an address its owner had verified is told, since an unproved address may belong to
somebody else entirely, who must not be handed a link that takes the account.

A completed change keeps the verified address it moved away from as the account's
**recovery address** for :data:`EMAIL_CHANGE_UNDO_TIMEOUT` seconds, as long as the undo
links last.  Meanwhile the address is reserved for the account (nobody else may
register it, give from it, or move to it), the account's own address cannot change
again by self-service, an administrator's change is announced to the recovery address,
and only an undo link mailed to the recovery address counts: whoever moved the account
can never mint an undo link of their own that outranks its owner's.  An undo link
works once: following one spends every undo link made before it.

A donor cannot sign in, so a donor's address is only where receipts go: it changes at
once, with nothing mailed.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TypedDict

from django.conf import settings
from django.core import signing
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from apps.accounts.history import record_account_change
from apps.accounts.models import AccountChangeKind, User
from apps.accounts.services import (
    EMAIL_VERIFICATION_INVALID,
    VERIFY_PATH,
    EmailVerificationError,
    address_taken,
    check_account_edit,
    is_donor,
    normalized_email,
    send_password_reset_email,
    verify_email,
)
from apps.accounts.status import end_sessions
from caldart import audit, events
from caldart.dates import format_display_date
from caldart.exceptions import DomainValidationError
from caldart.mail import contact_email, org_name, send_on_commit, send_templated

#: Where the SPA serves the page that posts an undo link back.
UNDO_PATH = "/portal/undo-email-change"

#: The ``django.core.signing`` salt of the link that completes a change of address, so
#: no other signed value passes for one, a plain verification link included.
EMAIL_CHANGE_SALT = "accounts.email-change"

#: The salt of the link that undoes a change of address.
EMAIL_CHANGE_UNDO_SALT = "accounts.email-change-undo"

#: The key salt of the password fingerprint a change link carries.
PASSWORD_FINGERPRINT_SALT = "accounts.email-change.password"  # noqa: S105 - a salt name

#: How long an undo link stays good, and a recovery address is kept, in seconds: seven
#: days.
EMAIL_CHANGE_UNDO_TIMEOUT = int(timedelta(days=7).total_seconds())

#: What every unusable undo link is told, so a forged link reads as a spent one.
UNDO_INVALID = "That link is invalid, has expired, or has been used."

#: The complaint when the address a change asks for, or completes to, is taken.
ADDRESS_TAKEN = "Another account already uses that email address."


def recent_change_refused(until: datetime) -> str:
    """What a self-service change is told while the account keeps a recovery address.

    ``"Your sign-in address changed in the last seven days, so it cannot change again
    until MM/DD/YYYY."``, the date the recovery address stops being kept.
    """
    return (
        "Your sign-in address changed in the last seven days, so it cannot change again "
        f"until {format_display_date(timezone.localtime(until).date())}."
    )


class EmailChangeUndoError(DomainValidationError):
    """An undo link that proves nothing or cannot apply, reported against ``token``."""

    def __init__(self, message: str = UNDO_INVALID) -> None:
        """Store ``message`` as the complaint about the ``token`` field."""
        super().__init__("token", message)


class FollowedLink(TypedDict):
    """What following a link mailed to an address did.

    ``email`` is the address the link proved, which the account now signs in with, and
    ``changed`` is true when following it moved the account to that address.
    """

    email: str
    changed: bool


class UndoneChange(TypedDict):
    """What following an undo link did.

    ``user`` is the account; ``taken`` is true when the address the link was mailed to
    could not be put back because another account holds it, so the account was only
    secured.
    """

    user: User
    taken: bool


# --------------------------------------------------------------------------
# The recovery address
# --------------------------------------------------------------------------
def recovery_address(user: User) -> str:
    """The recovery address ``user`` keeps now, or ``""`` when it keeps none."""
    if user.recovery_email == "" or user.recovery_until is None:
        return ""
    return user.recovery_email if user.recovery_until > timezone.now() else ""


def _notice_address(user: User) -> str:
    """Where a notice about a change of ``user``'s address goes, or ``""`` for nowhere.

    The recovery address while one is kept, otherwise the account's own address when
    it is verified, otherwise nowhere.
    """
    recovery = recovery_address(user)
    if recovery:
        return recovery
    return user.email if user.email_verified else ""


# --------------------------------------------------------------------------
# Asking for a change
# --------------------------------------------------------------------------
@transaction.atomic
def request_email_change(
    actor: User | str, target: User, email: str, *, quiet_if_taken: bool = False
) -> User:
    """Ask for ``target``'s sign-in address to become ``email`` on ``actor``'s behalf.

    ``email`` is stripped.  An address equal to the one the account holds, compared
    case-insensitively, is no change: nothing is written, nothing is mailed, and the
    account is returned as it was.  Otherwise, in this order:

    #. the account-edit guard (:func:`apps.accounts.services.check_account_edit`): an
       actor who does not hold every role ``target`` holds is refused with
       ``DomainValidationError`` against ``email``;
    #. the account's own change (``actor`` is ``target``) while it keeps a recovery
       address is refused against ``email`` with :func:`recent_change_refused`;
    #. an address another account holds, or keeps as its recovery address
       (:func:`apps.accounts.services.address_taken`), is refused against ``email``
       with :data:`ADDRESS_TAKEN` -- unless ``quiet_if_taken``, when nothing is
       written, nothing is mailed, and the account is returned as it was, so the
       caller can answer as for a free address.

    A refusal changes nothing.  A donor's address is then written at once, audited as
    ``account.update`` of ``email``, and nothing is mailed.  For anybody else the
    address is stored as ``pending_email``, replacing any earlier one, and the request
    is audited as ``account.email_change_request``; once the transaction commits the
    new address is mailed a link that completes the change
    (:func:`send_email_change_link`), and a notice with a link that undoes it goes to
    the recovery address while one is kept, or else to the account's address when its
    owner verified it (:func:`send_email_change_notice`).  A mail server that refuses
    either is logged and the request stands.  The account still signs in with its
    current address.
    """
    address = email.strip()
    if normalized_email(address) == normalized_email(target.email):
        return target
    check_account_edit(actor, target, {"email": address})
    recovery_until = target.recovery_until
    if actor == target and recovery_address(target) and recovery_until is not None:
        raise DomainValidationError("email", recent_change_refused(recovery_until))
    if address_taken(address, by_other_than=target):
        if quiet_if_taken:
            return target
        raise DomainValidationError("email", ADDRESS_TAKEN)
    if is_donor(target):
        target.email = address
        target.save(update_fields=["email", "updated_at"])
        audit.record(audit.ACCOUNT_UPDATE, actor=actor, target=target, fields=["email"])
        return target
    target.pending_email = address
    target.save(update_fields=["pending_email", "updated_at"])
    audit.record(audit.ACCOUNT_EMAIL_CHANGE_REQUEST, actor=actor, target=target)
    requester = actor.pk if isinstance(actor, User) else None
    send_on_commit(
        lambda: send_email_change_link(target, requested_by=requester),
        what=f"the email change link for account {target.pk}",
    )
    notice_to = _notice_address(target)
    if notice_to:
        send_on_commit(
            lambda: send_email_change_notice(
                target, previous_email=notice_to, new_email=address, completed=False
            ),
            what=f"the email change notice for account {target.pk}",
        )
    return target


# --------------------------------------------------------------------------
# The link to the new address
# --------------------------------------------------------------------------
def password_fingerprint(user: User) -> str:
    """A keyed fingerprint of ``user``'s stored password hash, safe to sign into a link.

    Any change of password, a reset or the password being made unusable, changes it,
    which spends every change link made before.
    """
    return salted_hmac(PASSWORD_FINGERPRINT_SALT, user.password, algorithm="sha256").hexdigest()[
        :32
    ]


def make_email_change_token(user: User, *, requested_by: int | None = None) -> str:
    """A signed token that moves ``user`` from its address to its ``pending_email``.

    It names the account, both addresses (normalized), ``requested_by`` (the id of the
    account that asked, or ``None`` for a management command), and
    :func:`password_fingerprint`.  It carries its own timestamp and is read with
    ``max_age=EMAIL_VERIFICATION_TIMEOUT``.
    """
    payload = {
        "user": user.pk,
        "email": normalized_email(user.email),
        "change_to": normalized_email(user.pending_email),
        "by": requested_by,
        "pw": password_fingerprint(user),
    }
    return signing.dumps(payload, salt=EMAIL_CHANGE_SALT)


def send_email_change_link(user: User, *, requested_by: int | None = None) -> None:
    """Mail ``user``'s ``pending_email`` the link that completes the change.

    The subject is ``"<organization name>: confirm your new email address"`` and the
    bodies are ``emails/email_change_confirm.{txt,html}``; the email log records the
    send under that template's name.  The context carries ``first_name``,
    ``new_email``, ``confirm_url`` (``/portal/verify-email?token=...``),
    ``expiry_days`` (``EMAIL_VERIFICATION_TIMEOUT`` in whole days, at least one),
    ``site_url``, ``org_name`` and ``contact_email``; the address the account signs in
    with now is not shown to the new address's holder.  An account with no pending
    address is sent nothing.
    """
    if user.pending_email == "":
        return
    token = make_email_change_token(user, requested_by=requested_by)
    name = org_name()
    send_templated(
        to=user.pending_email,
        subject=f"{name}: confirm your new email address",
        template="email_change_confirm",
        context={
            "first_name": user.first_name or user.display_name,
            "new_email": user.pending_email,
            "confirm_url": f"{_site_url()}{VERIFY_PATH}?token={token}",
            "expiry_days": _days(settings.EMAIL_VERIFICATION_TIMEOUT),
            "site_url": _site_url(),
            "org_name": name,
            "contact_email": contact_email(),
        },
        user_id=user.pk,
    )


def follow_verification_link(token: str, *, password: str = "") -> FollowedLink:
    """Follow a link mailed to prove an address, of either kind, and say what it did.

    A link that completes a change of address goes to :func:`complete_email_change`;
    any other goes to :func:`apps.accounts.services.verify_email` with ``password``.
    Raises what those raise: ``EmailVerificationError`` for a link that proves nothing.
    """
    try:
        payload = signing.loads(
            token, salt=EMAIL_CHANGE_SALT, max_age=settings.EMAIL_VERIFICATION_TIMEOUT
        )
    except signing.BadSignature:
        return {"email": verify_email(token, password=password).email, "changed": False}
    return complete_email_change(payload)


def complete_email_change(payload: object) -> FollowedLink:
    """Move the account a change link's ``payload`` names to the address it was sent to.

    The account's row is locked while it is read.  The link is good only while the
    account is active, still holds the address the link names, still waits for the
    address the link was sent to, and still has the password it had when the link was
    made: a later request, an undo, a new password, or a change of address made since
    all spend it.  Every other way a link is unusable raises ``EmailVerificationError``
    with the message every unusable verification link gets.  A link followed again
    once the account already holds its address answers as the first visit did and
    changes nothing.  When another account holds the address meanwhile, or keeps it as
    its recovery address, or takes it while this one is completing,
    ``EmailVerificationError`` says :data:`ADDRESS_TAKEN` and nothing changes.

    Completing the change writes the pending address as the account's ``email``, as it
    was typed, empties ``pending_email``, stamps the address verified now, and clears
    any bounce recorded against the old one.  An old address its owner had verified
    becomes the account's recovery address for :data:`EMAIL_CHANGE_UNDO_TIMEOUT`
    seconds; while one is kept already, it stays the recovery address and is kept that
    long from now.  The change is audited as ``account.update`` of ``email`` and
    ``account.email_verified`` with the account as actor, recorded in the account's
    history as ``email_changed`` under the account that asked for it, and raises the
    ``email_changed`` event with the ``old_email``.  Once it commits, the recovery
    address, if any, is mailed a notice with a link that undoes the change.
    """
    try:
        with transaction.atomic():
            return _complete(payload)
    except IntegrityError as exc:
        # Another account took the address between the check and the write.
        raise EmailVerificationError(ADDRESS_TAKEN) from exc


def _complete(payload: object) -> FollowedLink:
    """The body of :func:`complete_email_change`, inside its transaction."""
    claim = _change_claim(payload)
    if claim is None:
        raise EmailVerificationError(EMAIL_VERIFICATION_INVALID)
    user = User.objects.select_for_update().filter(pk=claim["user"], is_active=True).first()
    if user is None:
        raise EmailVerificationError(EMAIL_VERIFICATION_INVALID)
    if normalized_email(user.email) == claim["change_to"] and user.pending_email == "":
        return {"email": user.email, "changed": True}
    is_waiting = normalized_email(user.pending_email) == claim["change_to"]
    is_same_password = constant_time_compare(claim["pw"], password_fingerprint(user))
    if normalized_email(user.email) != claim["email"] or not is_waiting or not is_same_password:
        raise EmailVerificationError(EMAIL_VERIFICATION_INVALID)
    if address_taken(user.pending_email, by_other_than=user):
        raise EmailVerificationError(ADDRESS_TAKEN)

    old_email = user.email
    recovery = recovery_address(user) or (old_email if user.email_verified else "")
    now = timezone.now()
    user.email = user.pending_email
    user.pending_email = ""
    user.email_verified_at = now
    user.email_bounced_at = None
    user.email_bounce_detail = ""
    user.recovery_email = recovery
    user.recovery_until = now + timedelta(seconds=EMAIL_CHANGE_UNDO_TIMEOUT) if recovery else None
    user.save(
        update_fields=[
            "email",
            "pending_email",
            "email_verified_at",
            "email_bounced_at",
            "email_bounce_detail",
            "recovery_email",
            "recovery_until",
            "updated_at",
        ]
    )
    audit.record(audit.ACCOUNT_UPDATE, actor=user, target=user, fields=["email"])
    audit.record(audit.ACCOUNT_EMAIL_VERIFIED, actor=user, target=user)
    record_account_change(
        AccountChangeKind.EMAIL_CHANGED, actor=_requester(claim["by"], user), target=user
    )
    events.emit("email_changed", user=user, old_email=old_email)
    if recovery:
        new_email = user.email
        send_on_commit(
            lambda: send_email_change_notice(
                user, previous_email=recovery, new_email=new_email, completed=True
            ),
            what=f"the email change notice for account {user.pk}",
        )
    return {"email": user.email, "changed": True}


class _ChangeClaim(TypedDict):
    """A change link's payload, once its shape is checked."""

    user: int
    email: str
    change_to: str
    by: int | None
    pw: str


def _change_claim(payload: object) -> _ChangeClaim | None:
    """``payload`` as a :class:`_ChangeClaim`, or ``None`` when it is not that shape."""
    if not isinstance(payload, dict):
        return None
    pk = payload.get("user")
    email = payload.get("email")
    change_to = payload.get("change_to")
    by = payload.get("by")
    fingerprint = payload.get("pw")
    if not isinstance(pk, int) or not isinstance(email, str) or not isinstance(change_to, str):
        return None
    if (by is not None and not isinstance(by, int)) or not isinstance(fingerprint, str):
        return None
    return {"user": pk, "email": email, "change_to": change_to, "by": by, "pw": fingerprint}


def _requester(pk: int | None, user: User) -> User | str:
    """The account that asked for a change, for its history entry.

    The command actor when a management command asked, and ``user`` itself when the
    account that asked has since been deleted.
    """
    if pk is None:
        return audit.COMMAND_ACTOR
    return User.objects.filter(pk=pk).first() or user


# --------------------------------------------------------------------------
# The notice to the old address, and undo
# --------------------------------------------------------------------------
def make_undo_token(user: User, *, previous_email: str, new_email: str) -> str:
    """A signed token that undoes moving ``user`` away from ``previous_email``.

    The addresses are signed as given, so the one put back keeps its capitals.  The
    token also carries the moment it was made, which :func:`undo_email_change` compares
    with the account's ``email_change_undone_at``.
    """
    payload = {
        "user": user.pk,
        "from": previous_email,
        "to": new_email,
        "at": timezone.now().timestamp(),
    }
    return signing.dumps(payload, salt=EMAIL_CHANGE_UNDO_SALT)


def send_email_change_notice(
    user: User, *, previous_email: str, new_email: str, completed: bool
) -> None:
    """Tell ``previous_email`` that ``user``'s address is moving, or has moved, elsewhere.

    The subject is ``"<organization name>: your email address is changing"``, or
    ``"...: your email address has changed"`` once ``completed``, and the bodies are
    ``emails/email_change_notice.{txt,html}``.  The context carries ``first_name``,
    ``previous_email``, ``new_email``, ``completed``, ``undo_url``
    (``/portal/undo-email-change?token=...``, made by :func:`make_undo_token`),
    ``undo_days`` (:data:`EMAIL_CHANGE_UNDO_TIMEOUT` in days), ``site_url``,
    ``org_name`` and ``contact_email``.
    """
    token = make_undo_token(user, previous_email=previous_email, new_email=new_email)
    name = org_name()
    verb = "has changed" if completed else "is changing"
    send_templated(
        to=previous_email,
        subject=f"{name}: your email address {verb}",
        template="email_change_notice",
        context={
            "first_name": user.first_name or user.display_name,
            "previous_email": previous_email,
            "new_email": new_email,
            "completed": completed,
            "undo_url": f"{_site_url()}{UNDO_PATH}?token={token}",
            "undo_days": _days(EMAIL_CHANGE_UNDO_TIMEOUT),
            "site_url": _site_url(),
            "org_name": name,
            "contact_email": contact_email(),
        },
        user_id=user.pk,
    )


@transaction.atomic
def undo_email_change(token: str) -> UndoneChange:
    """Undo the change of address an undo link was mailed about, and say what it did.

    Raises :class:`EmailChangeUndoError` with :data:`UNDO_INVALID` when the token's
    signature does not match, when it is older than :data:`EMAIL_CHANGE_UNDO_TIMEOUT`
    seconds, when it names no account or a donor's, when an undo link has already been
    followed for the account since this one was made (each undo spends every link
    issued before it, this one included), and when the account keeps a recovery
    address other than the one the link was mailed to: only the recovery address's
    links count while it is kept.  The account's row is locked while it is read, so two
    clicks at once take turns and the second is refused.

    When the account no longer holds the address the link was mailed to, that address
    is put back, as signed, and stamped verified, since the link could only have
    reached its owner.  When another account holds it by then, the address stays as it
    is and ``taken`` is true, but the account is secured all the same.  Either way any
    change still waiting is dropped, the recovery address is forgotten, the account's
    password is made unusable, every session signed in to it is ended, the undo is
    audited as ``account.email_change_undo`` (with ``restored`` true when an address
    was put back) and recorded in the account's history as ``email_change_undone``,
    and once the transaction commits a password reset link is mailed to the address the
    undo link was mailed to (``send_password_reset_email``), which is how the owner
    signs in again.  The account's active flag is left alone: completing the reset
    reactivates a deactivated account, as any reset does.
    """
    try:
        payload = signing.loads(
            token, salt=EMAIL_CHANGE_UNDO_SALT, max_age=EMAIL_CHANGE_UNDO_TIMEOUT
        )
    except signing.BadSignature as exc:
        raise EmailChangeUndoError from exc
    claim = _undo_claim(payload)
    if claim is None:
        raise EmailChangeUndoError
    user = User.objects.select_for_update().filter(pk=claim["user"]).first()
    if user is None or is_donor(user) or _is_spent(user, claim["at"]):
        raise EmailChangeUndoError
    previous = claim["previous"]
    recovery = recovery_address(user)
    if recovery and normalized_email(recovery) != normalized_email(previous):
        raise EmailChangeUndoError

    now = timezone.now()
    moved = normalized_email(user.email) != normalized_email(previous)
    taken = moved and address_taken(previous, by_other_than=user)
    restored = moved and not taken
    if restored:
        user.email = previous
        user.email_verified_at = now
        user.email_bounced_at = None
        user.email_bounce_detail = ""
    user.pending_email = ""
    user.recovery_email = ""
    user.recovery_until = None
    user.email_change_undone_at = now
    user.set_unusable_password()
    user.save(
        update_fields=[
            "email",
            "email_verified_at",
            "email_bounced_at",
            "email_bounce_detail",
            "pending_email",
            "recovery_email",
            "recovery_until",
            "email_change_undone_at",
            "password",
            "updated_at",
        ]
    )
    end_sessions(user)
    audit.record(audit.ACCOUNT_EMAIL_CHANGE_UNDO, actor=user, target=user, restored=restored)
    record_account_change(AccountChangeKind.EMAIL_CHANGE_UNDONE, actor=user, target=user)
    send_on_commit(
        lambda: send_password_reset_email(user, to=previous),
        what=f"the password reset for account {user.pk}",
    )
    return {"user": user, "taken": taken}


class _UndoClaim(TypedDict):
    """An undo link's payload, once its shape is checked: ``previous`` is its ``from``."""

    user: int
    previous: str
    at: float


def _undo_claim(payload: object) -> _UndoClaim | None:
    """``payload`` as an :class:`_UndoClaim`, or ``None`` when it is not that shape."""
    if not isinstance(payload, dict):
        return None
    pk = payload.get("user")
    previous = payload.get("from")
    at = payload.get("at")
    if not isinstance(pk, int) or not isinstance(previous, str):
        return None
    if not isinstance(at, int | float) or isinstance(at, bool):
        return None
    return {"user": pk, "previous": previous, "at": float(at)}


def _is_spent(user: User, issued_at: float) -> bool:
    """True when an undo was followed for ``user`` at or after ``issued_at``."""
    undone = user.email_change_undone_at
    return undone is not None and issued_at <= undone.timestamp()


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def _site_url() -> str:
    """``SITE_URL`` without a trailing slash."""
    return str(settings.SITE_URL).rstrip("/")


def _days(seconds: int) -> int:
    """``seconds`` in whole days, never less than one."""
    return max(1, timedelta(seconds=seconds).days)
