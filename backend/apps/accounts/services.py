"""Account services: account creation, the edit guard, roles, and the password email.

The API layer validates; everything that changes state lives here so the
management commands, the Django admin and the tests can reuse it.  A rule the
caller breaks is refused with a ``DomainError``, never an HTTP exception.

Two emails carry a password link: the reset a member asks for, and the
invitation an administrator-created account receives.  Both render a pair of
templates from the same context, so the link, the organization name and the
expiry wording can never drift apart.
"""

from __future__ import annotations

from typing import TypedDict

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.http import HttpRequest
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from apps.accounts.models import User
from apps.accounts.roles import MEMBER, ROLE_SLUGS, SYSTEM_ADMIN, WEBSITE_ADMIN
from caldart import audit
from caldart.exceptions import DomainValidationError

#: Where the SPA serves the reset form (``routes/auth.tsx``).
RESET_PATH = "/portal/reset-password"

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
    for field in ACCOUNT_FIELDS:
        if field in fields:
            setattr(target, field, fields[field])
    if roles is not None and _writes_roles(target, set(roles)):
        target.set_roles(roles)
        sync_django_flags(target)
    target.save()

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
        return _normalized_email(value) != _normalized_email(target.email)
    if field == "is_active":
        return bool(value) != target.is_active
    return bool(value != getattr(target, field))


def _normalized_email(value: AccountFieldValue | None) -> str:
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
    client that renders no markup still reads the whole thing.
    """
    message = EmailMultiAlternatives(
        subject=subject,
        body=render_to_string(f"emails/{template}.txt", context),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    message.attach_alternative(render_to_string(f"emails/{template}.html", context), "text/html")
    message.send()


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
