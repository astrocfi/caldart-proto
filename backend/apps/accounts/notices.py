"""Notices to an account's owner: what was done to the account, or asked of its address.

Two messages that carry no link anybody can use to change the account: the notice that
a password was changed, so its owner can act if the change was not theirs, and the
answer to somebody registering with an address that already has an account, which
tells the address's owner how to sign in instead.  Each renders a pair of templates
under ``templates/emails/`` through :func:`caldart.mail.send_templated`.
"""

from __future__ import annotations

from urllib.parse import urlencode

from django.conf import settings
from django.utils import timezone

from apps.accounts.email_change import UNDO_PATH, make_undo_token, recovery_address
from apps.accounts.models import User
from apps.accounts.services import is_donor, normalized_email
from caldart.mail import contact_email, org_name, send_templated

#: Where the SPA serves the sign-in form.
SIGN_IN_PATH = "/portal/login"

#: Where the SPA serves the form that mails a password reset link.
FORGOT_PASSWORD_PATH = "/portal/forgot-password"  # noqa: S105 - a URL path, not a secret

#: What :func:`send_account_exists_notice` says the account is: one that signs in, one
#: its owner may bring back, or one a user administrator has closed.
ACTIVE = "active"
DEACTIVATED = "deactivated"
CLOSED = "closed"
RESERVED = "reserved"


def send_password_changed_notice(user: User) -> None:
    """Tell ``user``'s address that the account's password has just been changed.

    The subject is ``"<organization name>: your password was changed"`` and the bodies
    are ``emails/password_changed.{txt,html}``, which say when and point to the
    forgot-password page (``/portal/forgot-password``) for an owner who did not make the
    change.  The context carries ``first_name``, ``email``, ``changed_at`` (now),
    ``forgot_url``, ``undo_url`` (``""`` here), ``site_url``, ``org_name`` and
    ``contact_email``.  A donor, who holds no password, is sent nothing.

    While the account keeps a recovery address after a change of address
    (``apps.accounts.email_change``), the same notice goes to that address too, carrying
    an ``undo_url`` that undoes the change: whoever moved the account may be whoever just
    changed its password.
    """
    if is_donor(user):
        return
    name = org_name()
    context: dict[str, object] = {
        **_letterhead(name),
        "first_name": user.first_name or user.display_name,
        "email": user.email,
        "changed_at": timezone.localtime(),
        "forgot_url": f"{_site_url()}{FORGOT_PASSWORD_PATH}",
        "undo_url": "",
    }
    subject = f"{name}: your password was changed"
    send_templated(
        to=user.email,
        subject=subject,
        template="password_changed",
        context=context,
        user_id=user.pk,
    )
    recovery = recovery_address(user)
    if recovery:
        token = make_undo_token(user, previous_email=recovery, new_email=user.email)
        send_templated(
            to=recovery,
            subject=subject,
            template="password_changed",
            context={**context, "undo_url": f"{_site_url()}{UNDO_PATH}?token={token}"},
            user_id=user.pk,
        )


def account_state(user: User) -> str:
    """Which notice an existing account's address is sent: :data:`ACTIVE`, and so on.

    :data:`CLOSED` for an account a user administrator has blocked from reactivating,
    :data:`DEACTIVATED` for any other inactive account, and :data:`ACTIVE` otherwise.
    """
    if user.reactivation_blocked:
        return CLOSED
    if not user.is_active:
        return DEACTIVATED
    return ACTIVE


def send_account_exists_notice(user: User, *, to: str | None = None) -> None:
    """Tell ``user``'s address that somebody tried to open an account with it.

    The subject is ``"<organization name>: you already have an account"`` and the bodies
    are ``emails/account_exists.{txt,html}``, worded by :func:`account_state`: an active
    account is pointed to the sign-in page and the forgot-password page (and told that
    signing in offers a fresh verification link while the address is unverified); a
    deactivated one is told that signing in, or resetting the password, brings it back;
    a closed one is told to contact the organization.  The context carries
    ``first_name``, ``email``, ``state``, ``sign_in_url`` (the sign-in page with the
    address filled in), ``forgot_url``, ``site_url``, ``org_name`` and ``contact_email``.
    Nothing about the account changes.  The notice goes to ``to`` when given, the
    address somebody registered; to the account's own address otherwise.  When that is
    not the address the account signs in with -- it is one the account keeps as its
    recovery address after a change of address -- the state is :data:`RESERVED`
    instead, and the message points to the undo link sent about the change and to the
    office rather than to signing in, since that address signs nothing in.
    """
    name = org_name()
    address = to or user.email
    send_templated(
        to=address,
        subject=f"{name}: you already have an account",
        template="account_exists",
        context={
            **_letterhead(name),
            "first_name": user.first_name or user.display_name,
            "email": address,
            "state": (
                account_state(user)
                if normalized_email(address) == normalized_email(user.email)
                else RESERVED
            ),
            "sign_in_url": f"{_site_url()}{SIGN_IN_PATH}?{urlencode({'email': address})}",
            "forgot_url": f"{_site_url()}{FORGOT_PASSWORD_PATH}",
        },
        user_id=user.pk,
    )


def _letterhead(name: str) -> dict[str, object]:
    """The context every notice shares: the site, the organization, and its address."""
    return {"site_url": _site_url(), "org_name": name, "contact_email": contact_email()}


def _site_url() -> str:
    """``SITE_URL`` without a trailing slash."""
    return str(settings.SITE_URL).rstrip("/")
