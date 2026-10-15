"""Account services: creation, the edit guard, roles, and the account emails.

The API layer validates; everything that changes state lives here so the
management commands, the Django admin and the tests can reuse it.  A rule the
caller breaks is refused with a ``DomainError``, never an HTTP exception.

Two emails carry a password link: the reset a member asks for, and the
invitation an administrator-created account receives.  Both render a pair of
templates from the same context, so the link, the organization name and the
expiry wording can never drift apart.

A third email proves an address: every new account is mailed a signed link to
``/portal/verify-email``, and the account counts as verified once the link comes back.
A password link proves the address too, so following one marks an unverified account
verified.  A change of address is proved the same way before it takes effect, by the
link ``apps.accounts.email_change`` mails to the new address.
"""

from __future__ import annotations

import hashlib
from typing import TypedDict

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import password_changed, validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core import signing
from django.db import connection, transaction
from django.http import HttpRequest
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from apps.accounts.history import record_account_change
from apps.accounts.models import PERSON_KINDS, AccountChangeKind, AccountKind, User
from apps.accounts.roles import (
    GUARDED_ROLES,
    MEMBER,
    ROLE_LABELS,
    ROLE_SLUGS,
    SYSTEM_ADMIN,
    VERIFIER,
    WEBSITE_ADMIN,
)
from caldart import audit, events
from caldart.exceptions import DomainPermissionError, DomainValidationError
from caldart.mail import contact_email, org_name, send_templated

#: Where the SPA serves the reset form (``routes/auth.tsx``).
RESET_PATH = "/portal/reset-password"

#: Where the SPA serves the page that posts a verification link back.
VERIFY_PATH = "/portal/verify-email"

#: The ``django.core.signing`` salt of a verification token, so no value signed for
#: another purpose passes for one.
EMAIL_VERIFICATION_SALT = "accounts.email-verification"

#: What every unusable verification link is told, so a caller cannot tell an
#: expired link from a forged one or from one for an address since replaced.
EMAIL_VERIFICATION_INVALID = "That verification link is invalid or has expired."
#: The complaint, against ``password``, when a donor's link is followed without one.
DONOR_UPGRADE_PROMPT = "Choose a password to finish opening your account."

#: The name the password emails use before a website administrator has filled
#: in the organization name in Wagtail's site settings.
DEFAULT_ORG_NAME = "CalDART"

#: Seconds in a day, for turning ``PASSWORD_RESET_TIMEOUT`` into whole days.
SECONDS_PER_DAY = 86_400

#: The fields an administrator may change on another account only while holding
#: every role that account holds.  The email address is a takeover route: it is the
#: login and the target of a reset link.  The active flag is guarded the same way,
#: but it is not an edit: see ``apps.accounts.status``.
PROTECTED_ACCOUNT_FIELDS: tuple[str, ...] = ("email",)

#: The account columns :func:`update_account` writes, in the order it writes them.
#: Anything else in the changes it is handed is ignored, the address included: a change
#: of address waits for its new owner (``apps.accounts.email_change``).
ACCOUNT_FIELDS: tuple[str, ...] = ("first_name", "last_name")

EMAIL_CHANGE_REFUSED = (
    "You cannot change the email address of an account that holds roles you do not hold."
)
ROLE_CHANGE_REFUSED = (
    "Only a system administrator can grant or take away the System administrator role."
)
#: The refusal of a role write that moves guarded roles the actor does not hold;
#: ``{roles}`` is their labels, comma separated, in privilege order.
ROLE_NOT_HELD_REFUSED = "You cannot give or take away a role you do not hold yourself: {roles}."
OWN_ROLES_REFUSED = "You cannot change your own roles. Ask another administrator."
DONOR_KIND_REFUSED = "A donor becomes a member or a friend only by registering."

#: What one account column carries in an edit: an address or a name.
type AccountFieldValue = str


class EmailVerificationError(DomainValidationError):
    """A verification token that proves nothing, reported against the ``token`` field."""

    def __init__(self, message: str) -> None:
        """Store ``message`` as the complaint about the ``token`` field."""
        super().__init__("token", message)


class DonorPasswordRequiredError(DomainValidationError):
    """A donor's upgrade link followed without the password the account will sign in with.

    Reported against the ``password`` field with :data:`DONOR_UPGRADE_PROMPT`.  Nothing
    is written: the person following the link is asked for a password and posts again.
    """

    def __init__(self) -> None:
        """Store :data:`DONOR_UPGRADE_PROMPT` as the complaint about ``password``."""
        super().__init__("password", DONOR_UPGRADE_PROMPT)


class AuditFields(TypedDict, total=False):
    """The extra fields an account audit line carries.  Every key is optional.

    ``fields`` names the account columns a save really altered; ``added`` and
    ``removed`` the role slugs a role write really moved.
    """

    fields: list[str]
    added: list[str]
    removed: list[str]


class AccountChanges(TypedDict, total=False):
    """What :func:`update_account` may be asked to change.  Every key is optional.

    ``roles`` is the complete list the account should end up holding, in any
    order; ``kind`` the kind of person the account should belong to; the names are
    account columns, written as given.  ``email`` is the address an administrator's
    edit asks for: :func:`update_account` ignores it, and the member record hands it to
    ``apps.accounts.email_change.request_email_change``.
    """

    email: str
    first_name: str
    last_name: str
    roles: list[str]
    kind: AccountKind


# --------------------------------------------------------------------------
# Creating an account
# --------------------------------------------------------------------------
@transaction.atomic
def create_account(
    *,
    email: str,
    password: str = "",
    first_name: str = "",
    last_name: str = "",
    kind: AccountKind = AccountKind.MEMBER,
) -> User:
    """Create an account of ``kind``, and return it.

    A member or a friend holds the ``member`` role, which is what lets them into the
    portal; a donor holds no role at all.  Without a password the account holds an
    unusable one and can only be opened by following an invitation or reset link --
    which a donor is never sent.  The names are stored stripped.
    """
    user = User.objects.create_user(
        email=email,
        password=password or None,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        kind=kind,
    )
    if kind != AccountKind.DONOR:
        user.add_role(MEMBER)
    return user


def is_donor(user: User) -> bool:
    """True when ``user`` is a donor, who cannot sign in or hold a password."""
    return user.kind == AccountKind.DONOR


def set_kind(user: User, kind: AccountKind, *, actor: User | str = audit.COMMAND_ACTOR) -> bool:
    """Make ``user`` a ``kind`` at once, clearing any pending ``friend_on`` date.

    Saves the two columns and records ``account.kind`` with ``to=<kind>`` in the audit
    log under ``actor`` (``command`` by default).  Returns True when the stored kind
    really changed; a user already of that kind with nothing pending is left alone,
    records nothing, and returns False.
    """
    if user.kind == kind and user.friend_on is None:
        return False
    is_new_kind = user.kind != kind
    user.kind = kind
    user.friend_on = None
    user.save(update_fields=["kind", "friend_on", "updated_at"])
    if is_new_kind:
        audit.record(audit.ACCOUNT_KIND, actor=actor, target=user, to=kind.value)
    return is_new_kind


# --------------------------------------------------------------------------
# Roles
# --------------------------------------------------------------------------
def effective_roles(user: User | str) -> set[str]:
    """The role slugs ``user`` counts as holding.

    These are the user's own role groups, plus ``system_admin`` when the account is a
    Django superuser.  ``createsuperuser`` sets the flag without adding the role, and
    such an account has every power a system administrator has, so the guards treat
    the two the same way in both directions: as the actor making a change and as the
    target of one.  The command actor (``audit.COMMAND_ACTOR``) counts as holding
    every role, since a management command runs with the operator's own privilege,
    not a portal account's.
    """
    if isinstance(user, str):
        return set(ROLE_SLUGS)
    held = set(user.roles)
    if user.is_superuser:
        held.add(SYSTEM_ADMIN)
    return held


def sync_django_flags(user: User) -> None:
    """Keep ``is_superuser``/``is_staff`` in step with the roles.

    ``system_admin`` means "Django superuser"; ``website_admin`` keeps the
    staff flag so the Wagtail admin stays reachable after a role edit.  Call
    this after ``set_roles``; it does not save.
    """
    held = set(user.roles)
    user.is_superuser = SYSTEM_ADMIN in held
    user.is_staff = user.is_superuser or WEBSITE_ADMIN in held


# --------------------------------------------------------------------------
# Account edits
# --------------------------------------------------------------------------
@transaction.atomic
def update_account(actor: User | str, target: User, changes: AccountChanges) -> User:
    """Apply ``changes`` to ``target`` on ``actor``'s behalf, save it and return it.

    This is the only way an account is edited, so every rule is enforced once,
    whichever endpoint, command, or admin screen asked.  ``actor`` is ordinarily the
    signed-in account making the edit; a management command passes
    ``audit.COMMAND_ACTOR`` instead, which counts as holding every role (see
    :func:`effective_roles`) and so may grant or revoke any role: the own-account rule
    never applies to the command actor, which names no account.  The rules run in this
    order, and the first refusal raises, leaving the account untouched:

    #. nobody changes their own roles, a system administrator included
       (``DomainPermissionError``);
    #. only a system administrator may grant or revoke ``system_admin``, and only a
       system administrator or a holder of the role may grant or revoke a role in
       ``GUARDED_ROLES`` (``DomainValidationError`` against ``roles``; see
       :func:`_checked_roles` and :func:`assignable_roles`);
    #. a donor's kind is never changed by hand ("A donor becomes a member or a
       friend only by registering.", against ``kind``).

    The active flag is not an edit: ``apps.accounts.status`` deactivates and
    reactivates an account, and a change the caller hands in under ``is_active`` is
    ignored like any other key that is not an account column.  Nor is the address,
    which changes only once its new owner follows a link
    (``apps.accounts.email_change.request_email_change``): ``email`` is ignored here.

    A value that would not really alter the account is not a change.  A role list
    the account already holds is not written
    at all: rebuilding the Django flags from it would strip a ``createsuperuser``
    account of its access on a save that meant to correct a name.  Roles are
    stored in privilege order however they arrive.

    Everything the save really writes is recorded in the audit log, by field name
    and role slug: an edit that alters nothing records nothing.  The save writes only
    the columns the edit carries (plus the verification and bounce columns a new
    address clears, the Django flags a role write rebuilds, and ``updated_at``), so an
    edit made from a copy of the account read before another change committed -- a
    password cleared or roles granted meanwhile -- never writes the stale values back.

    A ``kind`` other than the stored one goes through :func:`set_kind`: the account
    becomes that kind at once, any pending ``friend_on`` date is cleared, and the
    change is recorded as ``account.kind`` under the actor.  A ``kind`` equal to the
    stored one is no change: a pending ``friend_on`` stays as it is.

    Each change the save really makes raises its notification event through
    :func:`caldart.events.emit`, after the save and inside the transaction:
    ``became_friend`` or ``became_member`` with ``how="administrator"`` for a new
    kind, and ``roles_changed`` with the slugs ``added`` and ``removed`` (in
    privilege order) and ``actor``, the command actor's string included.  An edit that
    alters nothing raises nothing.
    """
    fields = _account_fields(changes)
    roles = changes.get("roles")

    if roles is not None:
        roles = _checked_roles(actor, target, roles)
    kind = changes.get("kind")
    if kind is not None and is_donor(target):
        audit.refuse(audit.ACCOUNT_KIND, actor=actor, target=target, reason=audit.REASON_DONOR_KIND)
        raise DomainValidationError("kind", DONOR_KIND_REFUSED)

    records = _change_records(target, fields, roles)
    written = [field for field in ACCOUNT_FIELDS if field in fields]
    for field in written:
        setattr(target, field, fields[field])
    if roles is not None and _writes_roles(target, set(roles)):
        target.set_roles(roles)
        sync_django_flags(target)
        written += ["is_superuser", "is_staff"]
    target.save(update_fields=[*written, "updated_at"])
    if kind is not None and kind != target.kind and set_kind(target, kind, actor=actor):
        became = "became_friend" if kind == AccountKind.FRIEND else "became_member"
        events.emit(became, user=target, how="administrator")

    for action, logged in records:
        audit.record(action, actor=actor, target=target, **logged)
        if action == audit.ACCOUNT_ROLES:
            record_account_change(
                AccountChangeKind.ROLES,
                actor=actor,
                target=target,
                added=logged.get("added", []),
                removed=logged.get("removed", []),
            )
        _raise_edit_event(action, logged, actor=actor, target=target)
    return target


def set_verifier(actor: User, target: User, *, wanted: bool) -> User:
    """Give ``target`` the verifier role when ``wanted``, or take it away, and return it.

    The target's role list is rebuilt with ``verifier`` added or removed and written
    through :func:`update_account` under ``actor``, so the change is audited as
    ``account.roles`` and raised as ``roles_changed``, and every other role the target
    holds is kept.  A list that changes nothing writes, records and raises nothing.
    :func:`update_account`'s rules apply, so a change to the actor's own roles is
    refused with ``DomainPermissionError`` (:data:`OWN_ROLES_REFUSED`).  Who may call
    this is the endpoint's rule, not this function's.
    """
    held = [slug for slug in target.roles if slug != VERIFIER]
    roles = [*held, VERIFIER] if wanted else held
    return update_account(actor, target, {"roles": roles})


def _raise_edit_event(action: str, logged: AuditFields, *, actor: User | str, target: User) -> None:
    """Raise the notification event behind one audit record :func:`update_account` wrote.

    ``account.roles`` raises ``roles_changed`` with the slugs ``added`` and ``removed``
    and ``actor``.  ``account.update`` raises nothing here: the address has its own
    event and a name belongs to the profile.
    """
    if action == audit.ACCOUNT_ROLES:
        events.emit(
            "roles_changed",
            user=target,
            added=logged.get("added", []),
            removed=logged.get("removed", []),
            actor=actor,
        )


def _account_fields(changes: AccountChanges) -> dict[str, AccountFieldValue]:
    """The account columns ``changes`` carries, in ``ACCOUNT_FIELDS`` order.

    The role list is left out, and so is any key that is not an account column, the
    address included: only the two names are ever written.  A key ``changes`` does not
    carry is absent from the result rather than present as ``None``.
    """
    fields: dict[str, AccountFieldValue] = {}
    if "first_name" in changes:
        fields["first_name"] = changes["first_name"]
    if "last_name" in changes:
        fields["last_name"] = changes["last_name"]
    return fields


def _change_records(
    target: User, fields: dict[str, AccountFieldValue], roles: list[str] | None
) -> list[tuple[str, AuditFields]]:
    """The audit records this edit will produce, measured before it is written.

    One ``account.update`` for the columns whose stored value the save really
    alters, named but never valued -- a form that resends a column unchanged is
    not an edit of it; and one ``account.roles`` carrying the slugs added and
    removed when the role list really changes.
    """
    records: list[tuple[str, AuditFields]] = []
    written = _altered_fields(target, fields, ACCOUNT_FIELDS)
    if len(written) > 0:
        records.append((audit.ACCOUNT_UPDATE, {"fields": written}))
    if roles is not None and _writes_roles(target, set(roles)):
        held = set(target.roles)
        wanted = set(roles)
        added = [slug for slug in ROLE_SLUGS if slug in wanted - held]
        removed = [slug for slug in ROLE_SLUGS if slug in held - wanted]
        records.append((audit.ACCOUNT_ROLES, {"added": added, "removed": removed}))
    return records


def assignable_roles(actor: User | str, target: User) -> list[str]:
    """The role slugs ``actor`` may grant or take away on ``target``, in privilege order.

    None on the actor's own account: nobody changes their own roles.  Every role for a
    system administrator, a Django superuser and the command actor included
    (:func:`effective_roles`).  For anybody else, every role outside ``GUARDED_ROLES``
    and each guarded role the actor holds, which never includes ``system_admin``.  Who
    may write roles at all is the endpoint's rule, not this function's.
    """
    if isinstance(actor, User) and actor.pk == target.pk:
        return []
    held = effective_roles(actor)
    if SYSTEM_ADMIN in held:
        return list(ROLE_SLUGS)
    return [slug for slug in ROLE_SLUGS if slug not in GUARDED_ROLES or slug in held]


def _checked_roles(actor: User | str, target: User, wanted: list[str]) -> list[str]:
    """``wanted`` in privilege order, refused when ``actor`` may not make the change.

    A list matching the groups the account already holds writes nothing and is never
    refused.  Any other list is refused, and the refusal audited under
    ``account.roles``, in this order:

    #. on the actor's own account, whoever the actor is: ``DomainPermissionError``
       with :data:`OWN_ROLES_REFUSED`, reason ``own_account``;
    #. when it moves ``system_admin`` and the actor is not a system administrator:
       ``DomainValidationError`` on ``roles`` with :data:`ROLE_CHANGE_REFUSED`, reason
       ``system_admin_role``;
    #. when it grants or takes away a role :func:`assignable_roles` leaves out:
       ``DomainValidationError`` on ``roles`` with :data:`ROLE_NOT_HELD_REFUSED` naming
       those roles, reason ``roles_not_held``.

    Writing a role list rebuilds the Django flags from that list alone, so the two
    directions of ``system_admin`` are measured against different sets.  A write grants
    the role when it names ``system_admin`` on an account whose groups lack it, and
    revokes it when it leaves the role out of the list for an account that counts as a
    system administrator -- which a ``createsuperuser`` account does, on the superuser
    flag alone.
    """
    held = set(wanted)
    if not _writes_roles(target, held):
        return [slug for slug in ROLE_SLUGS if slug in held]
    if isinstance(actor, User) and actor.pk == target.pk:
        _refuse_roles(actor, target, audit.REASON_OWN_ACCOUNT)
        raise DomainPermissionError(OWN_ROLES_REFUSED)
    if _moves_system_admin(target, held) and SYSTEM_ADMIN not in effective_roles(actor):
        _refuse_roles(actor, target, audit.REASON_SYSTEM_ADMIN_ROLE)
        raise DomainValidationError("roles", ROLE_CHANGE_REFUSED)
    allowed = set(assignable_roles(actor, target))
    moved = held.symmetric_difference(target.roles)
    not_held = [slug for slug in ROLE_SLUGS if slug in moved and slug not in allowed]
    if len(not_held) > 0:
        _refuse_roles(actor, target, audit.REASON_ROLES_NOT_HELD)
        labels = ", ".join(ROLE_LABELS[slug] for slug in not_held)
        raise DomainValidationError("roles", ROLE_NOT_HELD_REFUSED.format(roles=labels))
    return [slug for slug in ROLE_SLUGS if slug in held]


def _refuse_roles(actor: User | str, target: User, reason: str) -> None:
    """Audit a refused role write on ``target`` by ``actor`` under ``reason``."""
    audit.refuse(audit.ACCOUNT_ROLES, actor=actor, target=target, reason=reason)


def _writes_roles(target: User, wanted: set[str]) -> bool:
    """True when writing ``wanted`` would alter ``target``'s role groups."""
    return wanted != set(target.roles)


def _moves_system_admin(target: User, wanted: set[str]) -> bool:
    """True when writing ``wanted`` to ``target`` would move the ``system_admin`` role."""
    if SYSTEM_ADMIN in wanted:
        return SYSTEM_ADMIN not in target.roles
    return SYSTEM_ADMIN in effective_roles(target)


def may_edit_protected_fields(actor: User | str, target: User) -> bool:
    """True when ``actor`` may write ``target``'s protected fields at all.

    The actor must hold every role the target holds; a system administrator, including
    a Django superuser without the role group or the command actor, holds them all.
    This judges the pair of accounts, not a particular edit: a caller who may not write
    these fields may still change names and profile fields.  The same rule guards
    deactivating, reactivating, and blocking an account (``apps.accounts.status``).
    """
    actor_roles = effective_roles(actor)
    if SYSTEM_ADMIN in actor_roles:
        return True
    return len(effective_roles(target) - actor_roles) == 0


def check_account_edit(
    actor: User | str, target: User, changes: dict[str, AccountFieldValue]
) -> None:
    """Refuse an edit of ``target``'s protected fields that ``actor`` may not make.

    ``changes`` is the incoming data; only the keys in ``PROTECTED_ACCOUNT_FIELDS``
    are examined, and only where they would really alter the account.  An email
    address is compared case-insensitively after stripping, so an administration form
    that resends every field is not treated as a change to the address.  Names are
    never protected.

    A protected change is refused unless the actor holds every role the target holds;
    a system administrator, including a Django superuser without the role, holds them
    all.  Raises ``DomainValidationError`` against ``email``, and returns ``None`` when
    the edit is allowed.  Every refusal is recorded in the audit log at WARNING with
    the two account ids, the field names and a reason, and no personal data.
    """
    changed = _protected_changes(target, changes)
    if len(changed) == 0 or may_edit_protected_fields(actor, target):
        return
    audit.refuse(
        audit.ACCOUNT_UPDATE,
        actor=actor,
        target=target,
        fields=changed,
        reason=audit.REASON_ROLES_NOT_HELD,
    )
    raise DomainValidationError(changed[0], EMAIL_CHANGE_REFUSED)


def _protected_changes(target: User, changes: dict[str, AccountFieldValue]) -> list[str]:
    """The protected fields ``changes`` would alter on ``target``, in field order."""
    return _altered_fields(target, changes, PROTECTED_ACCOUNT_FIELDS)


def _altered_fields(
    target: User, changes: dict[str, AccountFieldValue], fields: tuple[str, ...]
) -> list[str]:
    """Those of ``fields`` that ``changes`` would alter on ``target``, in that order.

    A field ``changes`` does not carry is not altered, and neither is one it carries at
    the value the account already holds.
    """
    return [
        field for field in fields if field in changes and _alters(target, field, changes[field])
    ]


def _alters(target: User, field: str, value: AccountFieldValue) -> bool:
    """True when writing ``value`` to ``target.<field>`` would change the account.

    An email address is compared normalized, so the stored address resent in another
    case does not alter the account; a name is compared exactly, so a change of case
    is a change.
    """
    if field == "email":
        return normalized_email(value) != normalized_email(target.email)
    return bool(value != getattr(target, field))


def normalized_email(value: AccountFieldValue | None) -> str:
    """``value`` as the case-insensitive unique constraint sees it.

    Stripped and lowercased; ``None`` and an empty address both give an empty string.
    """
    return str(value or "").strip().lower()


def address_holder(address: str) -> User | None:
    """The account ``address`` belongs to, or ``None`` when it is free.

    An address belongs to the account that signs in with it, compared
    case-insensitively, and also to the account keeping it as its ``recovery_email``
    until ``recovery_until``: a change of address reserves the address it moved away
    from for its owner's undo (``apps.accounts.email_change``), so nobody else may
    register it, give from it, or move to it meanwhile.
    """
    address = address.strip()
    holder = User.objects.filter(email__iexact=address).first()
    if holder is not None:
        return holder
    return User.objects.filter(
        recovery_email__iexact=address, recovery_until__gt=timezone.now()
    ).first()


def address_taken(address: str, *, by_other_than: User | None = None) -> bool:
    """True when ``address`` belongs to an account other than ``by_other_than``.

    Belonging is :func:`address_holder`'s: the address an account signs in with, or
    one an account keeps as its recovery address.
    """
    address = address.strip()
    others = User.objects.all()
    if by_other_than is not None:
        others = others.exclude(pk=by_other_than.pk)
    if others.filter(email__iexact=address).exists():
        return True
    return others.filter(recovery_email__iexact=address, recovery_until__gt=timezone.now()).exists()


#: What sets address locks apart from any other advisory lock taken on the database.
ADDRESS_LOCK_PERSON = b"caldart-address"


def lock_address(address: str) -> None:
    """Hold a transaction-scoped advisory lock on ``address``, whatever its case.

    ``User.email`` is unique only case-insensitively through a constraint, so two
    requests that each find an address free could both try to take it: one then fails
    on the constraint.  Taking this lock first makes the second wait until the first
    commits, and then find the account the first made.  The caller must be inside a
    transaction.
    """
    digest = hashlib.blake2b(
        address.strip().lower().encode(), digest_size=8, person=ADDRESS_LOCK_PERSON
    ).digest()
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(%s)", [int.from_bytes(digest, "big", signed=True)]
        )


# --------------------------------------------------------------------------
# Password reset
# --------------------------------------------------------------------------
def replace_password(user: User, raw_password: str) -> bool:
    """Make ``raw_password`` ``user``'s password unless the stored one moved meanwhile.

    The write is conditional on the stored hash still being the one ``user`` carries,
    the hash the caller checked the request against (the current password, or the
    reset link, which is signed over it).  When another change committed in between --
    ``create_admin`` clearing the password, or a second change or reset -- nothing is
    written and the return is False; the caller refuses the request.  Otherwise the new
    hash and ``updated_at`` are written, copied onto ``user``, the password validators'
    ``password_changed`` hooks run, and the return is True.  Any change of address
    waiting for its link is dropped with it (``pending_email`` emptied): a new password
    is the owner taking the account in hand, and the link was asked for under the old.
    For the same reason the demo mark is cleared (``is_demo``): the account no longer
    signs in with the published demo password, so a role that requires two-factor
    sign-in requires it again, and the session that changed the password is signed out
    at its next request unless it has passed a second factor.
    """
    new_hash = make_password(raw_password)
    now = timezone.now()
    written = User.objects.filter(pk=user.pk, password=user.password).update(
        password=new_hash, pending_email="", is_demo=False, updated_at=now
    )
    if written == 0:
        return False
    user.password = new_hash
    user.pending_email = ""
    user.is_demo = False
    user.updated_at = now
    password_changed(raw_password, user)
    return True


def make_reset_token(user: User) -> tuple[str, str]:
    """``(uid, token)`` for ``user``, using Django's default generator."""
    return urlsafe_base64_encode(force_bytes(user.pk)), default_token_generator.make_token(user)


def user_from_uid(uid: str) -> User | None:
    """The user a reset ``uid`` points at, or ``None`` if it is unusable."""
    try:
        pk = force_str(urlsafe_base64_decode(uid))
    except (TypeError, ValueError, OverflowError, UnicodeDecodeError):
        return None
    return User.objects.filter(pk=pk).first() if pk.isdigit() else None


def build_reset_url(user: User) -> str:
    """The absolute link mailed to ``user``."""
    uid, token = make_reset_token(user)
    return f"{settings.SITE_URL.rstrip('/')}{RESET_PATH}?uid={uid}&token={token}"


def _password_link_context(user: User, *, request: HttpRequest | None) -> dict[str, object]:
    """The context both password emails render, carrying a fresh reset link.

    ``org_name`` and ``contact_email`` come from Wagtail's site settings for
    ``request``'s site, falling back to ``DEFAULT_ORG_NAME`` and an empty
    address before a website administrator has set them.  ``expiry_days`` is
    ``PASSWORD_RESET_TIMEOUT`` in whole days, never less than one.
    """
    # Inline: cms is the top layer and apps.cms.models reaches apps.accounts.roles
    # through apps.cms.forms, so a top-level import here would close the cycle.
    from apps.cms.models import get_site_settings

    site_settings = get_site_settings(request)
    return {
        "user": user,
        "display_name": user.display_name,
        "first_name": user.first_name or user.display_name,
        "reset_url": build_reset_url(user),
        "site_url": settings.SITE_URL.rstrip("/"),
        "org_name": site_settings.org_name if site_settings else DEFAULT_ORG_NAME,
        "contact_email": site_settings.contact_email if site_settings else "",
        "expiry_days": max(1, settings.PASSWORD_RESET_TIMEOUT // SECONDS_PER_DAY),
    }


def _send_password_link_email(
    user: User,
    *,
    template: str,
    subject: str,
    context: dict[str, object],
    to: str | None = None,
) -> None:
    """Mail ``user`` both bodies of ``emails/<template>.{txt,html}``, at ``to`` if given.

    The text body is the message proper and the HTML one an alternative, so a
    client that renders no markup still reads the whole thing.  The send goes
    through the shared mail funnel, so it is recorded in the email log under the
    template's name.  ``to`` defaults to the account's own address.
    """
    send_templated(
        to=to or user.email,
        subject=subject,
        template=template,
        context=context,
        user_id=user.pk,
    )


def send_password_reset_email(
    user: User,
    *,
    request: HttpRequest | None = None,
    required: bool = False,
    to: str | None = None,
) -> bool:
    """Mail ``user`` a reset link.  Returns False when there is nobody to mail.

    The link goes to ``to`` when given, and to the account's own address otherwise:
    an undone change of address whose old address could not be put back mails the
    link to that old address.

    The subject is ``"<organization name>: reset your password"`` and the two
    bodies are ``emails/password_reset.{txt,html}``.  With ``required`` -- the email
    a user administrator's **Require a new password** sends -- the subject is
    ``"<organization name>: choose a new password"`` and the bodies say instead that
    an administrator has required a new password, that the old one no longer works
    and every session was ended, and that the link is the way to sign in again.

    Donors -- who cannot sign in, so have no password to reset -- accounts without
    an address, and accounts a user administrator has blocked from reactivating are
    skipped silently: the caller answers 204 either way so the endpoint cannot be
    used to discover which addresses are registered.  A deactivated account that is
    not blocked is mailed the link like an active one, because completing a reset
    reactivates it.  An account that has never set a usable password is mailed the
    link like any other, so an invited member who asks for a reset before following
    their invitation still receives one.
    """
    if not user.email or is_donor(user) or user.reactivation_blocked:
        return False

    context = _password_link_context(user, request=request)
    context["required"] = required
    what = "choose a new password" if required else "reset your password"
    _send_password_link_email(
        user,
        template="password_reset",
        subject=f"{context['org_name']}: {what}",
        context=context,
        to=to,
    )
    return True


def send_password_invitation(
    user: User, *, request: HttpRequest | None = None, taken_back: bool = False
) -> None:
    """Mail ``user`` the link that sets the first password on their account.

    An administrator may create a member without a password; the account holds
    an unusable one until the invitation is followed.  The subject is
    ``"<organization name>: set your password"`` and the two bodies are
    ``emails/member_invitation.{txt,html}``.  The link is the ordinary reset
    link, so ``/auth/password/reset/confirm`` accepts it unchanged.  A donor, who
    cannot sign in, is sent nothing.

    With ``taken_back`` the bodies say instead that an administrator account was set
    up on the existing account at this address, that any earlier password was cleared
    and every session ended, and that nobody can sign in until the link is used; this
    is the email ``create_admin`` sends when it promotes an existing account.
    """
    if is_donor(user):
        return
    context = _password_link_context(user, request=request)
    context["taken_back"] = taken_back
    _send_password_link_email(
        user,
        template="member_invitation",
        subject=f"{context['org_name']}: set your password",
        context=context,
    )


# --------------------------------------------------------------------------
# Email verification
# --------------------------------------------------------------------------
class DonorUpgrade(TypedDict):
    """What a registration with a donor's address asks the donor's account to become.

    ``kind`` is ``member`` or ``friend``; the names are the ones the form gave,
    stripped.  It travels inside the verification link, so nothing is written to the
    donor's account until somebody proves the address is theirs by following the link.
    The registration's password does not travel with it: whoever follows the link
    chooses the password then (:func:`verify_email`).
    """

    first_name: str
    last_name: str
    kind: str


def make_email_verification_token(user: User, *, upgrade: DonorUpgrade | None = None) -> str:
    """A signed token naming ``user`` and the address they hold now.

    The address is signed stripped and lowercased, so a change of case keeps the
    token good while any real change of address makes it useless.  The token carries
    its own timestamp; :func:`verify_email` refuses it once
    ``EMAIL_VERIFICATION_TIMEOUT`` seconds have passed.  A donor's token also carries
    the ``upgrade`` its registration asked for, which :func:`verify_email` applies.
    """
    payload: dict[str, object] = {"user": user.pk, "email": normalized_email(user.email)}
    if upgrade is not None:
        payload["upgrade"] = dict(upgrade)
    return signing.dumps(payload, salt=EMAIL_VERIFICATION_SALT)


def build_email_verification_url(user: User, *, upgrade: DonorUpgrade | None = None) -> str:
    """The absolute ``/portal/verify-email?token=...`` link mailed to ``user``.

    Built on ``SITE_URL`` with any trailing slash dropped; ``upgrade`` is signed into
    the token as :func:`make_email_verification_token` describes.
    """
    token = make_email_verification_token(user, upgrade=upgrade)
    return f"{settings.SITE_URL.rstrip('/')}{VERIFY_PATH}?token={token}"


def send_email_verification(user: User, *, upgrade: DonorUpgrade | None = None) -> None:
    """Mail ``user`` a link that proves the address they hold now is theirs.

    The subject is ``"<organization name>: verify your email address"`` and the two
    bodies are ``emails/email_verification.{txt,html}``; the email log records the
    send under the purpose ``email_verification``.  The context carries ``user``,
    ``first_name`` (the display name when there is no first name), ``email``,
    ``verify_url``, ``expiry_days`` (``EMAIL_VERIFICATION_TIMEOUT`` in whole days,
    never less than one), ``site_url``, ``org_name``, ``contact_email`` and ``upgrade``
    (true when the link opens a donor's account).  A donor, who cannot sign in, is sent
    nothing -- unless ``upgrade`` is given, when the link carries the registration that
    asked for it (:func:`verify_email` applies it) and the message says that following it
    opens a portal account for the address, choosing its password on the way.
    """
    if is_donor(user) and upgrade is None:
        return
    name = org_name()
    context: dict[str, object] = {
        "user": user,
        "first_name": user.first_name or user.display_name,
        "email": user.email,
        "verify_url": build_email_verification_url(user, upgrade=upgrade),
        "expiry_days": max(1, settings.EMAIL_VERIFICATION_TIMEOUT // SECONDS_PER_DAY),
        "site_url": settings.SITE_URL.rstrip("/"),
        "org_name": name,
        "contact_email": contact_email(),
        "upgrade": upgrade is not None,
    }
    send_templated(
        to=user.email,
        subject=f"{name}: verify your email address",
        template="email_verification",
        context=context,
        user_id=user.pk,
    )


@transaction.atomic
def verify_email(token: str, *, password: str = "") -> User:
    """Mark the account ``token`` names as verified, and return it.

    Raises ``EmailVerificationError`` with ``EMAIL_VERIFICATION_INVALID`` when the
    token's signature does not match, when it is older than
    ``EMAIL_VERIFICATION_TIMEOUT`` seconds, when its account no longer exists or is
    deactivated, and when the account's address is no longer the one the token was
    sent to.  A token for an account that is already verified succeeds without
    changing it, so following the same link twice is harmless, including two clicks
    of the same link at once: the account row is locked while it is read
    (:func:`_verification_target`), so the second caller waits for the first to
    finish and then sees what it left, rather than upgrading a donor twice.

    A token for a donor completes the registration that mailed it, and the person
    following it chooses the password: with no ``password`` it raises
    :class:`DonorPasswordRequiredError` and changes nothing, and a ``password`` Django's
    validators reject raises ``django.core.exceptions.ValidationError`` and changes
    nothing.  An accepted ``password`` becomes the account's, the account takes the names
    and the kind the form gave and the ``member`` role (see :func:`upgrade_donor`), and it
    is verified, so it can sign in with that password.  The password typed when
    registering is never used, so the account opens only for whoever holds the mailbox.
    A donor's token that carries no upgrade is refused as invalid.  ``password`` is
    ignored for every other account.
    """
    try:
        payload = signing.loads(
            token, salt=EMAIL_VERIFICATION_SALT, max_age=settings.EMAIL_VERIFICATION_TIMEOUT
        )
    except signing.BadSignature as exc:
        raise EmailVerificationError(EMAIL_VERIFICATION_INVALID) from exc
    user = _verification_target(payload)
    if user is None:
        raise EmailVerificationError(EMAIL_VERIFICATION_INVALID)
    if is_donor(user):
        upgrade = _donor_upgrade(payload)
        if upgrade is None:
            raise EmailVerificationError(EMAIL_VERIFICATION_INVALID)
        if password == "":
            raise DonorPasswordRequiredError
        validate_password(password, user=user)
        user.set_password(password)
        user.save(update_fields=["password", "updated_at"])
        upgrade_donor(user, upgrade)
    if confirm_email_address(user):
        return user
    # Nothing was stamped: the account was verified already, or its address changed
    # after it was read above.  Read it again to tell the two apart.
    user = _verification_target(payload)
    if user is None:
        raise EmailVerificationError(EMAIL_VERIFICATION_INVALID)
    return user


def upgrade_donor(donor: User, upgrade: DonorUpgrade) -> None:
    """Turn ``donor`` into the member or friend ``upgrade`` names, keeping its gifts.

    The names are replaced by the upgrade's, the account gains the ``member`` role,
    and the kind is set through :func:`set_kind` with the account as its own actor,
    which records ``account.kind``.  The caller has proved the address and set the
    password chosen by whoever proved it.  The donor has not signed up yet:
    like anybody who registers, they do when the join wizard's profile step
    completes the profile, which raises ``signed_up``.
    """
    donor.first_name = upgrade["first_name"]
    donor.last_name = upgrade["last_name"]
    donor.save(update_fields=["first_name", "last_name", "updated_at"])
    donor.add_role(MEMBER)
    set_kind(donor, AccountKind(upgrade["kind"]), actor=donor)


def _donor_upgrade(payload: dict[str, object]) -> DonorUpgrade | None:
    """The ``upgrade`` a verified token's ``payload`` carries, or ``None``.

    ``None`` when there is none, or when it is not the shape
    :func:`make_email_verification_token` signs: two string names and a kind a
    person may choose.
    """
    upgrade = payload.get("upgrade")
    if not isinstance(upgrade, dict):
        return None
    first_name = upgrade.get("first_name")
    last_name = upgrade.get("last_name")
    kind = upgrade.get("kind")
    if not isinstance(first_name, str) or not isinstance(last_name, str):
        return None
    if kind not in {person_kind.value for person_kind in PERSON_KINDS}:
        return None
    return {"first_name": first_name, "last_name": last_name, "kind": str(kind)}


def _verification_target(payload: object) -> User | None:
    """The active account a verified token's ``payload`` names at its current address.

    ``None`` when the payload is not the ``{"user": <id>, "email": <address>}`` shape a
    token carries, when no active account has that id, or when that account's address,
    normalized, is no longer the one signed.  Locks the row with ``select_for_update``,
    so two clicks of the same link at once serialize here: the second waits for the
    first's transaction to commit, then reads the account as the first left it, rather
    than the donor or the unverified address both callers saw when they started.
    """
    if not isinstance(payload, dict):
        return None
    pk = payload.get("user")
    email = payload.get("email")
    if not isinstance(pk, int) or not isinstance(email, str):
        return None
    user = User.objects.select_for_update().filter(pk=pk, is_active=True).first()
    if user is None or normalized_email(user.email) != email:
        return None
    return user


def confirm_email_address(user: User, *, actor: User | str | None = None) -> bool:
    """Record that ``user``'s owner has proved the address, unless that is known already.

    Following a verification link and following a password link both prove it, for the
    address ``user`` held when the caller checked the link.  While the stored account
    still holds that address (ignoring case), any bounce recorded against it is cleared,
    verified or not, since mail to it has just arrived; ``email_bounced_at`` and
    ``email_bounce_detail`` are cleared on ``user`` too.  Then the account is stamped
    verified now, in one conditional update, only while it is unverified; the stamp is
    copied onto ``user``, recorded in the audit log as ``account.email_verified`` with
    the account as target and ``actor`` as actor (the account itself when ``actor`` is
    ``None``, as when its owner follows a link), and the return is True.  An account
    already verified, or moved to another address since ``user`` was read, is not
    stamped and the return is False.
    """
    now = timezone.now()
    same_address = User.objects.filter(pk=user.pk, email__iexact=user.email)
    if same_address.filter(email_bounced_at__isnull=False).update(
        email_bounced_at=None, email_bounce_detail="", updated_at=now
    ):
        user.email_bounced_at = None
        user.email_bounce_detail = ""
        user.updated_at = now
    stamped = same_address.filter(email_verified_at__isnull=True).update(
        email_verified_at=now, updated_at=now
    )
    if stamped == 0:
        return False
    user.email_verified_at = now
    user.updated_at = now
    audit.record(audit.ACCOUNT_EMAIL_VERIFIED, actor=user if actor is None else actor, target=user)
    return True


def clear_email_bounce(actor: User, target: User) -> User:
    """Clear the bounce recorded against ``target``'s address on ``actor``'s word.

    For a user administrator who has checked the address is good: ``email_bounced_at``
    and ``email_bounce_detail`` are emptied and the change is recorded as
    ``account.bounce_cleared`` under ``actor``.  An account with no bounce recorded is
    left alone and nothing is recorded.  Who may call this is the endpoint's rule, not
    this function's.  Returns the account.
    """
    if target.email_bounced_at is None:
        return target
    target.email_bounced_at = None
    target.email_bounce_detail = ""
    target.save(update_fields=["email_bounced_at", "email_bounce_detail", "updated_at"])
    audit.record(audit.ACCOUNT_BOUNCE_CLEARED, actor=actor, target=target)
    return target
