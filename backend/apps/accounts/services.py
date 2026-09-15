"""Account services: registration, the account-edit guard, roles and reset email.

The API layer validates; everything that changes state lives here so the
management commands, the Django admin and the tests can reuse it.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from apps.accounts.roles import MEMBER, SYSTEM_ADMIN, WEBSITE_ADMIN

User = get_user_model()

log = logging.getLogger(__name__)

#: Where the SPA serves the reset form (``routes/auth.tsx``).
RESET_PATH = "/portal/reset-password"

#: The fields an administrator may change on another account only while holding
#: every role that account holds.  Both are takeover routes: the email address is
#: the login and the target of a reset link, and ``is_active`` locks the account.
#: The order is the order in which a refusal reports them.
PROTECTED_ACCOUNT_FIELDS: tuple[str, ...] = ("email", "is_active")

SELF_DEACTIVATION_REFUSED = "You cannot deactivate your own account."
EMAIL_CHANGE_REFUSED = (
    "You cannot change the email address of an account that holds roles you do not hold."
)
STATUS_CHANGE_REFUSED = (
    "You cannot activate or deactivate an account that holds roles you do not hold."
)


# --------------------------------------------------------------------------
# Registration
# --------------------------------------------------------------------------
@transaction.atomic
def register_user(*, email: str, password: str, first_name: str = "", last_name: str = "") -> User:
    """Create a member account: user + ``member`` role + empty profile.

    The profile starts blank on purpose — the join wizard fills it in — but it
    must exist so ``/me/profile`` is a PATCH rather than a create.
    """
    from apps.members.models import MemberProfile

    user = User.objects.create_user(
        email=email,
        password=password,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
    )
    user.add_role(MEMBER)
    MemberProfile.objects.get_or_create(user=user)
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
class AccountEditRefused(Exception):
    """An account edit the actor may not make.

    ``field`` is the request field the complaint belongs on, so an API caller can
    show it against the input it came from, and ``message`` is the text to show.
    """

    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message


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


def check_account_edit(actor: User, target: User, changes: dict) -> None:
    """Refuse an edit of ``target``'s protected fields that ``actor`` may not make.

    ``changes`` is the incoming data; only the keys in ``PROTECTED_ACCOUNT_FIELDS``
    are examined, and only where they would really alter the account.  An email
    address is compared case-insensitively after stripping and ``is_active`` as a
    bool, so an administration form that resends every field is not treated as a
    change to the fields it left alone.  Names are never protected.

    Nobody may deactivate their own account.  Beyond that, a protected change is
    refused unless the actor holds every role the target holds; a system
    administrator, including a Django superuser without the role, holds them all.
    Raises ``AccountEditRefused`` on the first refused field, email before status,
    and returns ``None`` when the edit is allowed.  Every refusal is logged at
    WARNING with the two account ids and the field names, and no personal data.
    """
    changed = _protected_changes(target, changes)
    if len(changed) == 0:
        return

    if target.pk == actor.pk and "is_active" in changed:
        # An authenticated actor is active, so the only change they can make to
        # their own flag is to clear it.
        _refuse(actor, target, changed, "is_active", SELF_DEACTIVATION_REFUSED)

    if may_edit_protected_fields(actor, target):
        return

    field = changed[0]
    message = EMAIL_CHANGE_REFUSED if field == "email" else STATUS_CHANGE_REFUSED
    _refuse(actor, target, changed, field, message)


def _protected_changes(target: User, changes: dict) -> list[str]:
    """The protected fields ``changes`` would really alter on ``target``, in field order."""
    return [
        field
        for field in PROTECTED_ACCOUNT_FIELDS
        if field in changes and _alters(target, field, changes[field])
    ]


def _alters(target: User, field: str, value: str | bool) -> bool:
    """True when writing ``value`` to ``target.<field>`` would change the account."""
    if field == "email":
        return _normalized_email(value) != _normalized_email(target.email)
    return bool(value) != bool(target.is_active)


def _normalized_email(value: str | None) -> str:
    """``value`` as the case-insensitive unique constraint sees it."""
    return (value or "").strip().lower()


def _refuse(actor: User, target: User, changed: list[str], field: str, message: str) -> None:
    """Log the refused edit and raise ``AccountEditRefused`` for ``field``."""
    log.warning(
        "Account edit refused: actor=%s target=%s fields=%s",
        actor.pk,
        target.pk,
        ",".join(changed),
    )
    raise AccountEditRefused(field, message)


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


def send_password_reset_email(user: User, *, request=None) -> bool:
    """Mail ``user`` a reset link.  Returns False when there is nobody to mail.

    Inactive accounts and accounts without a usable password are skipped
    silently: the caller answers 204 either way so the endpoint cannot be used
    to discover which addresses are registered.
    """
    from apps.cms.models import get_site_settings

    if not user.is_active or not user.email:
        return False

    site_settings = get_site_settings(request)
    context = {
        "user": user,
        "display_name": user.display_name,
        "reset_url": build_reset_url(user),
        "site_url": settings.SITE_URL.rstrip("/"),
        "org_name": site_settings.org_name if site_settings else "CalDART",
        "contact_email": site_settings.contact_email if site_settings else "",
        "expiry_days": max(1, settings.PASSWORD_RESET_TIMEOUT // 86_400),
    }

    subject = f"{context['org_name']}: reset your password"
    text_body = render_to_string("emails/password_reset.txt", context)
    html_body = render_to_string("emails/password_reset.html", context)

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    message.attach_alternative(html_body, "text/html")
    message.send()
    return True
