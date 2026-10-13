"""Starting a session: the one way any endpoint signs an account in.

Every endpoint that has just proved who somebody is -- a password at ``/auth/login``
or ``/auth/reactivate`` -- hands the account to
:func:`start_session` rather than calling ``django.contrib.auth.login`` itself, so an
account that needs a second factor never gets a session without one.  The code steps
finish with :func:`finish_sign_in`.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth import login
from rest_framework.exceptions import Throttled
from rest_framework.request import Request
from rest_framework.response import Response

from apps.accounts import lockout, mfa
from apps.accounts.api.serializers import UserSerializer
from apps.accounts.models import User


def start_session(request: Request, user: User, *, reactivate: bool = False) -> Response:
    """Sign ``user`` in, or ask for the second factor first; the 200 to answer with.

    An account that needs a second factor (``apps.accounts.mfa.needs_second_factor``) is
    not signed in: a pending sign-in bound to it and its password is stored in the
    session, and the answer is ``{"mfa": "verify"}`` -- or ``{"mfa": "enroll"}`` when
    it has no device yet -- with nothing about the account.  ``reactivate`` marks a
    pending sign-in for a deactivated account, which the code step reactivates once
    the second factor is passed.  Any other account is signed in, its failed attempts
    are forgotten, and the answer is the ``user`` payload.
    """
    if mfa.needs_second_factor(user):
        step = mfa.begin_pending(request.session, user, reactivate=reactivate)
        return Response({"mfa": step.value})
    return Response(UserSerializer(finish_sign_in(request, user)).data)


def finish_sign_in(request: Request, user: User, *, passed_mfa: bool = False) -> User:
    """Call ``login`` for ``user``, and mark the session when a second factor was passed.

    Any pending sign-in is cleared and the address's failed attempts are forgotten.
    ``login`` keeps the session's data when it changes the key, so the mark is written
    after it.  The key is changed even when ``login`` keeps it (a session already signed
    in to the same account), so a signed-in session never goes on under a key that
    existed before the sign-in.  Returns ``user``.
    """
    login(request, user, backend=settings.AUTHENTICATION_BACKENDS[0])
    request.session.cycle_key()
    if passed_mfa:
        mfa.mark_session(request.session, user)
    mfa.clear_pending(request.session)
    lockout.clear_failures(user.email)
    return user


def refuse_if_locked_out(email: str) -> None:
    """Raise DRF's ``Throttled`` when ``email`` is locked out, with ``Retry-After``.

    The answer is 429 ``{"detail": "Too many failed sign-in attempts for this email
    address. Try again later. Expected available in <n> seconds."}``.
    """
    wait = lockout.lockout_wait(email)
    if wait is not None:
        raise Throttled(wait=wait, detail=lockout.LOCKED_OUT)
