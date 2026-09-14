"""Rate limits for the unauthenticated auth endpoints.

Login, registration and password-reset requests are the three places where an
anonymous caller can burn server time or spray an inbox, so each gets its own
DRF ``AnonRateThrottle`` scope.

Rates come from the ``AUTH_THROTTLE_RATES`` setting rather than DRF's
``DEFAULT_THROTTLE_RATES`` so they can be switched off (or turned up for one
test) with a plain ``override_settings``: a scope mapped to ``None`` — or
missing entirely, which is how ``settings/test.py`` leaves it — makes the
throttle inert.
"""

from __future__ import annotations

from django.conf import settings
from rest_framework.throttling import AnonRateThrottle

#: Scope names, also the keys of ``settings.AUTH_THROTTLE_RATES``.
LOGIN_SCOPE = "auth_login"
REGISTER_SCOPE = "auth_register"
PASSWORD_RESET_SCOPE = "auth_password_reset"


class AuthScopedThrottle(AnonRateThrottle):
    """An anonymous throttle whose rate is read from settings per request."""

    scope = ""

    def get_rate(self) -> str | None:
        return getattr(settings, "AUTH_THROTTLE_RATES", {}).get(self.scope)

    def get_cache_key(self, request, view) -> str:
        """Always count by client address.

        ``AnonRateThrottle`` exempts anyone with a session, which would let a
        caller register once and then spray: registration logs the new account
        in, so every request after the first carries a session cookie.
        """
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class LoginThrottle(AuthScopedThrottle):
    scope = LOGIN_SCOPE


class RegisterThrottle(AuthScopedThrottle):
    scope = REGISTER_SCOPE


class PasswordResetThrottle(AuthScopedThrottle):
    scope = PASSWORD_RESET_SCOPE
