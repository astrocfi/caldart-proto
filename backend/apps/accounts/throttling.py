"""Rate limits for the anonymous endpoints that mail someone, guess at a secret, or write.

Login, registration, password-reset, and email-verification requests are where a
caller can burn server time, guess at a token, or spray an inbox, and a gift on the
public donation page writes an account and a payment for a caller nobody signed in,
so each gets its own scope.  Every scope counts by client address, signed in or not.

Rates come from the ``AUTH_THROTTLE_RATES`` setting rather than DRF's
``DEFAULT_THROTTLE_RATES`` so they can be switched off (or turned up for one
test) with a plain ``override_settings``.  A scope makes its throttle inert
when it is mapped to ``None``, mapped to an empty string, or absent from the
mapping; ``settings/test.py`` maps every scope to ``None`` so no test races a
shared counter.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from functools import wraps
from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseBase
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

#: What a login form that is not the portal's answers once the ``auth_login`` budget
#: is spent, as plain text: the form's own page cannot show an API error.
LOGIN_FORM_THROTTLED = "Too many sign-in attempts. Wait a minute and try again."


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


def throttle_login_form(
    view: Callable[..., HttpResponseBase],
) -> Callable[..., HttpResponseBase]:
    """Wrap a login view that is not the portal's in the ``auth_login`` rate limit.

    The Wagtail admin and the Django admin each serve their own login form, which would
    otherwise take unlimited guesses.  Each ``POST`` to the wrapped view counts against
    the same ``auth_login`` budget, by client address, as ``POST /auth/login``; once it
    is spent the answer is a plain-text 429 carrying :data:`LOGIN_FORM_THROTTLED` and a
    ``Retry-After`` header in whole seconds, and the view is not called.  Other methods
    pass through uncounted, and a switched-off scope leaves the view alone.
    """

    @wraps(view)
    def throttled(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponseBase:
        """Refuse a ``POST`` past the budget, otherwise call the view."""
        if request.method != "POST":
            return view(request, *args, **kwargs)
        throttle = LoginThrottle()
        if throttle.allow_request(Request(request), APIView()):
            return view(request, *args, **kwargs)
        response = HttpResponse(
            LOGIN_FORM_THROTTLED, status=429, content_type="text/plain; charset=utf-8"
        )
        wait = throttle.wait()
        if wait is not None:
            response["Retry-After"] = str(math.ceil(wait))
        return response

    return throttled
