"""Account services: creation, the edit guard, roles, and the account emails.

The API layer validates; everything that changes state lives here so the
management commands, the Django admin and the tests can reuse it.  A rule the
caller breaks is refused with a ``DomainError``, never an HTTP exception.

Two emails carry a password link: the reset a member asks for, and the
invitation an administrator-created account receives.  Both render a pair of
templates from the same context, so the link, the organization name and the
expiry wording can never drift apart.

A third email proves an address: every new account and every change of address
is mailed a signed link to ``/portal/verify-email``, and the account counts as
verified once the link comes back.  A password link proves the address too, so
following one marks an unverified account verified.
"""

from __future__ import annotations

from typing import TypedDict

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core import signing
from django.db import transaction
from django.http import HttpRequest
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from apps.accounts.models import User
from apps.accounts.roles import MEMBER, ROLE_SLUGS, SYSTEM_ADMIN, WEBSITE_ADMIN
from caldart import audit
from caldart.exceptions import DomainValidationError
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

#: The name the password emails use before a website administrator has filled
#: in the organization name in Wagtail's site settings.
DEFAULT_ORG_NAME = "CalDART"

#: Seconds in a day, for turning ``PASSWORD_RESET_TIMEOUT`` into whole days.
SECONDS_PER_DAY = 86_400

#: The fields an administrator may change on another account only while holding
#: every role that account holds.  Both are takeover routes: the email address is
#: the login and the target of a reset link, and ``is_active`` locks the account.
#: The order is the order in which a refusal reports them.
PROTECTED_ACCOUNT_FIELDS: tuple[str, ...] = ("email", "is_active")

#: The account columns :func:`update_account` writes, in the order it writes them.
#: Anything else in the changes it is handed is ignored.
ACCOUNT_FIELDS: tuple[str, ...] = ("email", "first_name", "last_name", "is_active")

SELF_DEACTIVATION_REFUSED = "You cannot deactivate your own account."
EMAIL_CHANGE_REFUSED = (
    "You cannot change the email address of an account that holds roles you do not hold."
)
STATUS_CHANGE_REFUSED = (
    "You cannot activate or deactivate an account that holds roles you do not hold."
)
ROLE_CHANGE_REFUSED = "Only a system administrator can grant or revoke the system_admin role."

#: What one account column carries in an edit: an address or a name, or the active flag.
type AccountFieldValue = str | bool


class EmailVerificationError(DomainValidationError):
    """A verification token that proves nothing, reported against the ``token`` field."""

    def __init__(self, message: str) -> None:
        """Store ``message`` as the complaint about the ``token`` field."""
        super().__init__("token", message)


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
    order; the other keys are the account columns, written as given.
    """

    email: str
    first_name: str
    last_name: str
    is_active: bool
    roles: list[str]


# --------------------------------------------------------------------------
# Creating an account
# --------------------------------------------------------------------------
@transaction.atomic
def create_account(
    *, email: str, password: str = "", first_name: str = "", last_name: str = ""
) -> User:
    """Create an account holding the ``member`` role, and return it.

    Every account on the site is at least a member, so the role is not a
    parameter.  Without a password the account holds an unusable one and can
    only be opened by following an invitation or reset link.  The names are
    stored stripped.
    """
    user = User.objects.create_user(
        email=email,
        password=password or None,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
    )
    user.add_role(MEMBER)
    return user


# --------------------------------------------------------------------------
# Roles
# --------------------------------------------------------------------------
def effective_roles(user: User) -> set[str]:
    """The role slugs ``user`` counts as holding.

    These are the user's own role groups, plus ``system_admin`` when the account is a
    Django superuser.  ``createsuperuser`` sets the flag without adding the role, and
    such an account has every power a system administrator has, so the guards treat
    the two the same way in both directions: as the actor making a change and as the
    target of one.
    """
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
def update_account(actor: User, target: User, changes: AccountChanges) -> User:
    """Apply ``changes`` to ``target`` on ``actor``'s behalf, save it and return it.

    This is the only way an account is edited, so every rule is enforced once,
    whichever endpoint, command, or admin screen asked.  The rules run in this
    order, and the first refusal raises ``DomainValidationError`` naming the
    field it belongs on, leaving the account untouched:

    #. nobody may deactivate their own account;
    #. only a system administrator may grant or revoke ``system_admin``;
    #. an account holding roles the actor does not hold has an untouchable email
       address and active flag -- see :func:`check_account_edit`.

    A value that would not really alter the account is not a change and so is
    never a refusal; on a record whose protected fields the actor may not write
    it is dropped rather than saved, so an address resent in another case cannot
    rewrite the stored one.  A role list the account already holds is not written
    at all: rebuilding the Django flags from it would strip a ``createsuperuser``
    account of its access on a save that meant to correct a name.  Roles are
    stored in privilege order however they arrive.

    Everything the save really writes is recorded in the audit log, by field name
    and role slug: an edit that alters nothing records nothing.

    An edit that really alters the email address -- compared as the unique
    constraint compares it, so a change of case is not one -- clears
    ``email_verified_at`` and, once the transaction commits, mails the new address a
    verification link through :func:`send_email_verification`.
    """
    fields = _account_fields(changes)
    roles = changes.get("roles")

    _refuse_self_deactivation(actor, target, _protected_changes(target, fields))
    if roles is not None:
        roles = _checked_roles(actor, target, roles)
    check_account_edit(actor, target, fields)
    if not may_edit_protected_fields(actor, target):
        for field in PROTECTED_ACCOUNT_FIELDS:
            fields.pop(field, None)

    records = _change_records(target, fields, roles)
    is_new_address = len(_altered_fields(target, fields, ("email",))) > 0
    for field in ACCOUNT_FIELDS:
        if field in fields:
            setattr(target, field, fields[field])
    if is_new_address:
        target.email_verified_at = None
    if roles is not None and _writes_roles(target, set(roles)):
        target.set_roles(roles)
        sync_django_flags(target)
    target.save()
    if is_new_address:
        transaction.on_commit(lambda: send_email_verification(target))

    for action, logged in records:
        audit.record(action, actor=actor, target=target, **logged)
    return target


def _account_fields(changes: AccountChanges) -> dict[str, AccountFieldValue]:
    """The account columns ``changes`` carries, in ``ACCOUNT_FIELDS`` order.

    The role list is left out, and so is any key that is not an account column: only
    these four are ever written.  A key ``changes`` does not carry is absent from the
    result rather than present as ``None``.
    """
    fields: dict[str, AccountFieldValue] = {}
    if "email" in changes:
        fields["email"] = changes["email"]
    if "first_name" in changes:
        fields["first_name"] = changes["first_name"]
    if "last_name" in changes:
        fields["last_name"] = changes["last_name"]
    if "is_active" in changes:
        fields["is_active"] = changes["is_active"]
    return fields


def _change_records(
    target: User, fields: dict[str, AccountFieldValue], roles: list[str] | None
) -> list[tuple[str, AuditFields]]:
    """The audit records this edit will produce, measured before it is written.

    One ``account.update`` for the columns whose stored value the save really
    alters, named but never valued -- a form that resends a column unchanged is
    not an edit of it; one ``account.activate`` or ``account.deactivate`` when
    the active flag really turns over; and one ``account.roles`` carrying the
    slugs added and removed when the role list really changes.
    """
    records: list[tuple[str, AuditFields]] = []
    altered = _altered_fields(target, fields, ACCOUNT_FIELDS)
    written = [name for name in altered if name != "is_active"]
    if len(written) > 0:
        records.append((audit.ACCOUNT_UPDATE, {"fields": written}))
    if "is_active" in altered:
        activating = bool(fields["is_active"])
        records.append((audit.ACCOUNT_ACTIVATE if activating else audit.ACCOUNT_DEACTIVATE, {}))
    if roles is not None and _writes_roles(target, set(roles)):
        held = set(target.roles)
        wanted = set(roles)
        added = [slug for slug in ROLE_SLUGS if slug in wanted - held]
        removed = [slug for slug in ROLE_SLUGS if slug in held - wanted]
        records.append((audit.ACCOUNT_ROLES, {"added": added, "removed": removed}))
    return records


def _checked_roles(actor: User, target: User, wanted: list[str]) -> list[str]:
    """``wanted`` in privilege order, refused if ``actor`` may not move ``system_admin``.

    Writing a role list rebuilds the Django flags from that list alone, so the two
    directions are measured against different sets.  A write grants the role when it
    names ``system_admin`` on an account whose groups lack it, and revokes it when it
    leaves the role out of the list for an account that counts as a system
    administrator -- which a ``createsuperuser`` account does, on the superuser flag
    alone.  A list matching the groups the account already holds writes nothing and
    is never refused.
    """
    held = set(wanted)
    is_refused = (
        _writes_roles(target, held)
        and _moves_system_admin(target, held)
        and SYSTEM_ADMIN not in effective_roles(actor)
    )
    if is_refused:
        audit.refuse(
            audit.ACCOUNT_ROLES,
            actor=actor,
            target=target,
            reason=audit.REASON_SYSTEM_ADMIN_ROLE,
        )
        raise DomainValidationError("roles", ROLE_CHANGE_REFUSED)
    return [slug for slug in ROLE_SLUGS if slug in held]


def _writes_roles(target: User, wanted: set[str]) -> bool:
    """True when writing ``wanted`` would alter ``target``'s role groups."""
    return wanted != set(target.roles)


def _moves_system_admin(target: User, wanted: set[str]) -> bool:
    """True when writing ``wanted`` to ``target`` would move the ``system_admin`` role."""
    if SYSTEM_ADMIN in wanted:
        return SYSTEM_ADMIN not in target.roles
    return SYSTEM_ADMIN in effective_roles(target)


def may_edit_protected_fields(actor: User, target: User) -> bool:
    """True when ``actor`` may write ``target``'s protected fields at all.

    The actor must hold every role the target holds; a system administrator, including
    a Django superuser without the role group, holds them all.  This judges the pair of
    accounts, not a particular edit: self-deactivation is refused separately, and a
    caller who may not write these fields may still change names and profile fields.
    """
    actor_roles = effective_roles(actor)
    if SYSTEM_ADMIN in actor_roles:
        return True
    return len(effective_roles(target) - actor_roles) == 0


def check_account_edit(actor: User, target: User, changes: dict[str, AccountFieldValue]) -> None:
    """Refuse an edit of ``target``'s protected fields that ``actor`` may not make.

    ``changes`` is the incoming data; only the keys in ``PROTECTED_ACCOUNT_FIELDS``
    are examined, and only where they would really alter the account.  An email
    address is compared case-insensitively after stripping and ``is_active`` as a
    bool, so an administration form that resends every field is not treated as a
    change to the fields it left alone.  Names are never protected.

    Nobody may deactivate their own account.  Beyond that, a protected change is
    refused unless the actor holds every role the target holds; a system
    administrator, including a Django superuser without the role, holds them all.
    Raises ``DomainValidationError`` on the first refused field, email before status,
    and returns ``None`` when the edit is allowed.  Every refusal is recorded in the
    audit log at WARNING with the two account ids, the field names and a reason, and
    no personal data.
    """
    changed = _protected_changes(target, changes)
    if len(changed) == 0:
        return

    _refuse_self_deactivation(actor, target, changed)

    if may_edit_protected_fields(actor, target):
        return

    field = changed[0]
    message = EMAIL_CHANGE_REFUSED if field == "email" else STATUS_CHANGE_REFUSED
    _refuse(
        actor,
        target,
        changed,
        field=field,
        message=message,
        action=audit.ACCOUNT_UPDATE,
        reason=audit.REASON_ROLES_NOT_HELD,
    )


def _refuse_self_deactivation(actor: User, target: User, changed: list[str]) -> None:
    """Refuse the one protected change an actor can make to their own account.

    An authenticated actor is active, so the only move they can make on their own
    flag is to clear it.  ``changed`` is the protected fields the edit really alters.
    """
    if target.pk == actor.pk and "is_active" in changed:
        _refuse(
            actor,
            target,
            changed,
            field="is_active",
            message=SELF_DEACTIVATION_REFUSED,
            action=audit.ACCOUNT_DEACTIVATE,
            reason=audit.REASON_SELF_DEACTIVATION,
        )


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
    case does not alter the account; ``is_active`` is compared as a boolean; a name is
    compared exactly, so a change of case is a change.
    """
    if field == "email":
        return normalized_email(value) != normalized_email(target.email)
    if field == "is_active":
        return bool(value) != target.is_active
    return bool(value != getattr(target, field))


def normalized_email(value: AccountFieldValue | None) -> str:
    """``value`` as the case-insensitive unique constraint sees it.

    Stripped and lowercased; ``None`` and an empty address both give an empty string.
    """
    return str(value or "").strip().lower()


def _refuse(
    actor: User,
    target: User,
    changed: list[str],
    *,
    field: str,
    message: str,
    action: str,
    reason: str,
) -> None:
    """Record the refused edit and raise ``DomainValidationError`` for ``field``.

    ``changed`` is the protected fields the edit really alters, ``action`` the
    audit action the attempt belongs to and ``reason`` the slug saying which rule
    turned it away.
    """
    audit.refuse(action, actor=actor, target=target, fields=changed, reason=reason)
    raise DomainValidationError(field, message)


# --------------------------------------------------------------------------
# Password reset
# --------------------------------------------------------------------------
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
    user: User, *, template: str, subject: str, context: dict[str, object]
) -> None:
    """Mail ``user`` both bodies of ``emails/<template>.{txt,html}``.

    The text body is the message proper and the HTML one an alternative, so a
    client that renders no markup still reads the whole thing.  The send goes
    through the shared mail funnel, so it is recorded in the email log under the
    template's name.
    """
    send_templated(
        to=user.email,
        subject=subject,
        template=template,
        context=context,
        user_id=user.pk,
    )


def send_password_reset_email(user: User, *, request: HttpRequest | None = None) -> bool:
    """Mail ``user`` a reset link.  Returns False when there is nobody to mail.

    The subject is ``"<organization name>: reset your password"`` and the two
    bodies are ``emails/password_reset.{txt,html}``.

    Inactive accounts and accounts without an address are skipped silently: the
    caller answers 204 either way so the endpoint cannot be used to discover
    which addresses are registered.  An account that has never set a usable
    password is mailed the link like any other, so an invited member who asks
    for a reset before following their invitation still receives one.
    """
    if not user.is_active or not user.email:
        return False

    context = _password_link_context(user, request=request)
    _send_password_link_email(
        user,
        template="password_reset",
        subject=f"{context['org_name']}: reset your password",
        context=context,
    )
    return True


def send_password_invitation(user: User, *, request: HttpRequest | None = None) -> None:
    """Mail ``user`` the link that sets the first password on their account.

    An administrator may create a member without a password; the account holds
    an unusable one until the invitation is followed.  The subject is
    ``"<organization name>: set your password"`` and the two bodies are
    ``emails/member_invitation.{txt,html}``.  The link is the ordinary reset
    link, so ``/auth/password/reset/confirm`` accepts it unchanged.
    """
    context = _password_link_context(user, request=request)
    _send_password_link_email(
        user,
        template="member_invitation",
        subject=f"{context['org_name']}: set your password",
        context=context,
    )


# --------------------------------------------------------------------------
# Email verification
# --------------------------------------------------------------------------
def make_email_verification_token(user: User) -> str:
    """A signed token naming ``user`` and the address they hold now.

    The address is signed stripped and lowercased, so a change of case keeps the
    token good while any real change of address makes it useless.  The token carries
    its own timestamp; :func:`verify_email` refuses it once
    ``EMAIL_VERIFICATION_TIMEOUT`` seconds have passed.
    """
    payload = {"user": user.pk, "email": normalized_email(user.email)}
    return signing.dumps(payload, salt=EMAIL_VERIFICATION_SALT)


def build_email_verification_url(user: User) -> str:
    """The absolute ``/portal/verify-email?token=...`` link mailed to ``user``.

    Built on ``SITE_URL`` with any trailing slash dropped.
    """
    token = make_email_verification_token(user)
    return f"{settings.SITE_URL.rstrip('/')}{VERIFY_PATH}?token={token}"


def send_email_verification(user: User) -> None:
    """Mail ``user`` a link that proves the address they hold now is theirs.

    The subject is ``"<organization name>: verify your email address"`` and the two
    bodies are ``emails/email_verification.{txt,html}``; the email log records the
    send under the purpose ``email_verification``.  The context carries ``user``,
    ``first_name`` (the display name when there is no first name), ``email``,
    ``verify_url``, ``expiry_days`` (``EMAIL_VERIFICATION_TIMEOUT`` in whole days,
    never less than one), ``site_url``, ``org_name`` and ``contact_email``.
    """
    name = org_name()
    context: dict[str, object] = {
        "user": user,
        "first_name": user.first_name or user.display_name,
        "email": user.email,
        "verify_url": build_email_verification_url(user),
        "expiry_days": max(1, settings.EMAIL_VERIFICATION_TIMEOUT // SECONDS_PER_DAY),
        "site_url": settings.SITE_URL.rstrip("/"),
        "org_name": name,
        "contact_email": contact_email(),
    }
    send_templated(
        to=user.email,
        subject=f"{name}: verify your email address",
        template="email_verification",
        context=context,
        user_id=user.pk,
    )


def verify_email(token: str) -> User:
    """Mark the account ``token`` names as verified, and return it.

    Raises ``EmailVerificationError`` with ``EMAIL_VERIFICATION_INVALID`` when the
    token's signature does not match, when it is older than
    ``EMAIL_VERIFICATION_TIMEOUT`` seconds, when its account no longer exists or is
    deactivated, and when the account's address is no longer the one the token was
    sent to.  A token for an account that is already verified succeeds without
    changing it, so following the same link twice is harmless.
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
    if confirm_email_address(user):
        return user
    # Nothing was stamped: the account was verified already, or its address changed
    # after it was read above.  Read it again to tell the two apart.
    user = _verification_target(payload)
    if user is None:
        raise EmailVerificationError(EMAIL_VERIFICATION_INVALID)
    return user


def _verification_target(payload: object) -> User | None:
    """The active account a verified token's ``payload`` names at its current address.

    ``None`` when the payload is not the ``{"user": <id>, "email": <address>}`` shape a
    token carries, when no active account has that id, or when that account's address,
    normalized, is no longer the one signed.
    """
    if not isinstance(payload, dict):
        return None
    pk = payload.get("user")
    email = payload.get("email")
    if not isinstance(pk, int) or not isinstance(email, str):
        return None
    user = User.objects.filter(pk=pk, is_active=True).first()
    if user is None or normalized_email(user.email) != email:
        return None
    return user


def confirm_email_address(user: User) -> bool:
    """Record that ``user``'s owner has proved the address, unless that is known already.

    Following a verification link and following a password link both prove it, for the
    address ``user`` held when the caller checked the link.  The stored account is
    stamped verified now, in one conditional update, only while it is unverified and
    still holds that address (ignoring case); the stamp is copied onto ``user``,
    recorded in the audit log as ``account.email_verified`` with the account as actor
    and target, and the return is True.  An account already verified, or moved to
    another address since ``user`` was read, is left alone and the return is False.
    """
    now = timezone.now()
    stamped = User.objects.filter(
        pk=user.pk, email__iexact=user.email, email_verified_at__isnull=True
    ).update(email_verified_at=now, updated_at=now)
    if stamped == 0:
        return False
    user.email_verified_at = now
    user.updated_at = now
    audit.record(audit.ACCOUNT_EMAIL_VERIFIED, actor=user, target=user)
    return True


def change_own_email(user: User, *, email: str) -> User:
    """Change ``user``'s own address to ``email``, and return the account.

    This is :func:`update_account` with the account as both actor and target, so the
    change is audited as an ``account.update`` of ``email``, the address is marked
    unverified, and the new address is mailed a verification link on commit.  The
    caller has already checked the current password and that the address is free.
    """
    return update_account(user, user, {"email": email})
