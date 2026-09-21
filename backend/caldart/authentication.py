"""The project's DRF authentication class.

Session authentication is the only credential the API accepts; the portal and
the API are same-origin, so the browser's session cookie is enough.  What this
module adds is the CSRF check for callers who have no session yet.
"""

from __future__ import annotations

from typing import Any

from rest_framework.authentication import SessionAuthentication
from rest_framework.request import Request


class CsrfEnforcingSessionAuthentication(SessionAuthentication):
    """Session authentication that checks CSRF for anonymous callers too.

    DRF wraps every API view in ``csrf_exempt`` and runs its own CSRF check
    only after it has found a signed-in user, so without this class an
    anonymous unsafe method -- login, registration, logout, the two
    password-reset endpoints, and any future ``AllowAny`` endpoint -- would be
    accepted from a cross-site form with no token at all.  That is login CSRF:
    a visitor silently signed into an attacker's account, or an account created
    from a victim's browser.

    Enforcing the check here rather than decorating each view keeps the answer
    a DRF ``403`` with a ``detail`` that starts ``CSRF Failed``, and covers
    endpoints that do not exist yet.  Safe methods are untouched, because the
    check delegates to Django's ``CsrfViewMiddleware``, which exempts ``GET``,
    ``HEAD``, ``OPTIONS`` and ``TRACE``.  A view that authenticates by
    signature instead -- the payment webhooks -- sets
    ``authentication_classes = []`` and so never reaches this class.
    """

    def authenticate(self, request: Request) -> tuple[Any, Any] | None:
        """Return the signed-in user, or ``None`` once CSRF has been checked.

        Raises DRF's ``PermissionDenied`` when an unsafe method arrives without
        a usable CSRF token, whether or not the caller holds a session.
        """
        user_and_auth = super().authenticate(request)
        if user_and_auth is None:
            self.enforce_csrf(request)
        return user_and_auth
