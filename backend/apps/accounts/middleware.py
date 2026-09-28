"""The email-verification gate on the API.

A session whose account has not verified its address may use only what the portal's
"Check your email" screen needs; every other ``/api/v1/`` request is refused with a
403 the portal can recognize by its ``code``.  The check lives on the server, so the
screen is not the only thing holding an unverified account back.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from django.http import HttpRequest, HttpResponseBase, JsonResponse

from apps.accounts.models import User

#: The namespace every ``/api/v1/`` route resolves under (``caldart.api_urls``).
API_NAMESPACE = "api"

#: The ``code`` the refusal carries, which the portal keys its redirect off.
EMAIL_UNVERIFIED_CODE = "email_unverified"

#: The sentence the refusal carries as ``detail``.
EMAIL_UNVERIFIED_DETAIL = "Verify your email address to continue."

#: The routes an unverified session may still call, by their resolved view names: who
#: is signed in, signing out or in again, the CSRF token every write needs, following
#: the link, asking for another one, correcting the address, and the site chrome.
UNVERIFIED_ALLOWED_VIEWS: frozenset[str] = frozenset(
    {
        "api:accounts:me",
        "api:accounts:logout",
        "api:accounts:login",
        "api:accounts:csrf",
        "api:accounts:email-verify",
        "api:accounts:email-resend",
        "api:accounts:email-change",
        "api:cms:site-config",
    }
)


class EmailVerificationGateMiddleware:
    """Refuse the API to a signed-in account whose email address is not verified.

    For a request that resolves under the ``api`` namespace, made by an authenticated
    ``User`` whose ``email_verified`` is false, to a view not named in
    ``UNVERIFIED_ALLOWED_VIEWS``, the view is not called: the answer is 403 with
    ``{"detail": "Verify your email address to continue.", "code":
    "email_unverified"}``.  Anonymous requests, verified accounts, and every path
    outside the API (the user guide, the portal's HTML, the public site) pass through
    untouched.  It reads ``request.user``, so it must sit below
    ``AuthenticationMiddleware`` in ``MIDDLEWARE``.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponseBase]) -> None:
        """Store the next handler in the chain."""
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponseBase:
        """Pass the request on; the gate itself runs in :meth:`process_view`."""
        return self.get_response(request)

    def process_view(
        self,
        request: HttpRequest,
        view_func: Callable[..., HttpResponseBase],
        view_args: tuple[Any, ...],
        view_kwargs: dict[str, Any],
    ) -> HttpResponseBase | None:
        """Answer the gate's 403 for a gated request, or ``None`` to run the view."""
        match = request.resolver_match
        if match is None or API_NAMESPACE not in match.namespaces:
            return None
        user = request.user
        if not isinstance(user, User) or user.email_verified:
            return None
        if match.view_name in UNVERIFIED_ALLOWED_VIEWS:
            return None
        return JsonResponse(
            {"detail": EMAIL_UNVERIFIED_DETAIL, "code": EMAIL_UNVERIFIED_CODE}, status=403
        )
