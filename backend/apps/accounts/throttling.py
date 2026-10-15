"""Rate limits for the endpoints that mail someone, guess at a secret, or write.

Login, registration, password-reset, and email-verification requests are where a
caller can burn server time, guess at a token, or spray an inbox, every endpoint that
takes a two-factor code is a place to guess one, and a gift on the public donation
page writes an account and a payment for a caller nobody signed in, so each gets its
own scope.  Every scope counts by client address, signed in or not.

Rates come from the ``AUTH_THROTTLE_RATES`` setting rather than DRF's
``DEFAULT_THROTTLE_RATES`` so they can be switched off (or turned up for one
test) with a plain ``override_settings``.  A scope makes its throttle inert
when it is mapped to ``None``, mapped to an empty string, or absent from the
mapping; ``settings/test.py`` maps every scope to ``None`` so no test races a
shared counter.
"""

from __future__ import annotations

from django.conf import settings
from rest_framework.request import Request
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

#: Scope names, also the keys of ``settings.AUTH_THROTTLE_RATES``.
LOGIN_SCOPE = "auth_login"
REGISTER_SCOPE = "auth_register"
PASSWORD_RESET_SCOPE = "auth_password_reset"  # noqa: S105 - a throttle scope name, not a secret
VERIFY_SCOPE = "auth_verify"
VERIFY_RESEND_SCOPE = "auth_verify_resend"
EMAIL_CHANGE_SCOPE = "auth_email_change"
DONATE_SCOPE = "donate"
DONATE_CONFIRM_SCOPE = "donate_confirm"
MFA_SCOPE = "auth_mfa"


class AuthScopedThrottle(AnonRateThrottle):
    """An anonymous throttle whose rate is read from settings per request."""

    scope = ""

    def get_rate(self) -> str | None:
        """The configured rate, or ``None`` when this scope is switched off.

        Off is spelled three ways -- ``None``, an empty string and a missing
        key -- because an operator who blanks the environment variable and a
        test that overrides the mapping mean the same thing, and DRF treats
        only ``None`` as unlimited.
        """
        return settings.AUTH_THROTTLE_RATES.get(self.scope) or None

    def get_cache_key(self, request: Request, view: APIView) -> str:
        """Always count by client address.

        ``AnonRateThrottle`` exempts anyone with a session, which would let a
        caller register once and then spray: registration logs the new account
        in, so every request after the first carries a session cookie.
        """
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class LoginThrottle(AuthScopedThrottle):
    """Throttles ``POST /auth/login`` under the ``auth_login`` rate."""

    scope = LOGIN_SCOPE


class RegisterThrottle(AuthScopedThrottle):
    """Throttles ``POST /auth/register`` under the ``auth_register`` rate."""

    scope = REGISTER_SCOPE


class PasswordResetThrottle(AuthScopedThrottle):
    """Throttles both password-reset endpoints under the ``auth_password_reset`` rate."""

    scope = PASSWORD_RESET_SCOPE


class EmailVerifyThrottle(AuthScopedThrottle):
    """Throttles ``POST /auth/email/verify`` under the ``auth_verify`` rate."""

    scope = VERIFY_SCOPE


class EmailVerifyResendThrottle(AuthScopedThrottle):
    """Throttles ``POST /auth/email/resend`` under the ``auth_verify_resend`` rate."""

    scope = VERIFY_RESEND_SCOPE


class EmailChangeThrottle(AuthScopedThrottle):
    """Throttles ``POST /auth/email/change`` under the ``auth_email_change`` rate."""

    scope = EMAIL_CHANGE_SCOPE


class DonateThrottle(AuthScopedThrottle):
    """Throttles ``POST /donations/checkout`` under the ``donate`` rate.

    Each gift on the public donation page can make a donor account and a pending
    payment for a caller nobody has signed in, so the start of one is counted by
    client address like the auth endpoints.
    """

    scope = DONATE_SCOPE


class DonateConfirmThrottle(AuthScopedThrottle):
    """Throttles the public Stripe confirm and PayPal capture under ``donate_confirm``.

    ``POST /donations/stripe/confirm`` and ``/donations/paypal/capture`` each ask the
    provider about a gift for a caller nobody has signed in, so they are counted by
    client address under one budget.
    """

    scope = DONATE_CONFIRM_SCOPE


class MfaThrottle(AuthScopedThrottle):
    """Throttles every endpoint that takes a two-factor code under the ``auth_mfa`` rate.

    The code steps of signing in and the signed-in two-factor endpoints share it, on
    top of the per-sign-in cap on wrong codes and the per-address lockout.
    """

    scope = MFA_SCOPE
