"""Account services: registration, role syncing and password-reset email.

The API layer validates; everything that changes state lives here so the
management commands, the Django admin and the tests can reuse it.
"""

from __future__ import annotations

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

#: Where the SPA serves the reset form (PLAN §8, ``routes/auth.tsx``).
RESET_PATH = "/portal/reset-password"


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
def sync_django_flags(user: User) -> None:
    """Keep ``is_superuser``/``is_staff`` in step with the roles (PLAN §4.1).

    ``system_admin`` means "Django superuser"; ``website_admin`` keeps the
    staff flag so the Wagtail admin stays reachable after a role edit.  Call
    this after ``set_roles``; it does not save.
    """
    held = set(user.roles)
    user.is_superuser = SYSTEM_ADMIN in held
    user.is_staff = user.is_superuser or WEBSITE_ADMIN in held


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
    """The absolute link mailed to ``user`` (PLAN §6.1)."""
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

    subject = f"Reset your {context['org_name']} password"
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
