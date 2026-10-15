"""PayPal's REST layer: the client-credentials token and one authenticated call.

The provider in :mod:`apps.payments.providers.paypal` speaks to PayPal only through
:func:`call`, which tells the two kinds of failure apart: a call PayPal never
answered, or answered with a status that doesn't say anything about the request (a
5xx, a 429 or a 408), raises
:class:`~apps.payments.providers.base.ProviderUnavailableError`, because PayPal may
have acted on it; a refusal PayPal gave about the request itself raises
:class:`PayPalRequestError` with PayPal's own issue codes.

The client-credentials token is held in Django's default cache until shortly
before it expires; the entry records the environment and client id, so changing
either (in tests, or by editing ``.env``) fetches a fresh one.
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict
from urllib.parse import quote

import httpx
from django.conf import settings
from django.core.cache import cache

from apps.payments.providers.base import (
    PaymentVerificationError,
    ProviderNotConfiguredError,
    ProviderUnavailableError,
    RequestNotSentError,
)

log = logging.getLogger(__name__)


LIVE_BASE = "https://api-m.paypal.com"

SANDBOX_BASE = "https://api-m.sandbox.paypal.com"

#: What a member is told when PayPal times out or answers with something we
#: cannot read.  It doesn't say anything about the money: a capture can fail in transit
#: after PayPal has already taken it.
UNAVAILABLE_MESSAGE = "PayPal didn't answer. Try again in a moment."

#: Seconds shaved off the advertised token lifetime, so we never present one
#: that expires mid-flight.
TOKEN_SKEW_SECONDS = 60

#: How long a token is kept when PayPal advertises a lifetime shorter than the
#: skew above.  Caching for a moment is still better than a fetch per call.
MINIMUM_TOKEN_SECONDS = 30

#: Where the client-credentials token sits in Django's default cache.
TOKEN_CACHE_KEY = "paypal:access_token"  # noqa: S105 - a cache key, not a secret

TIMEOUT_SECONDS = 20.0

#: HTTP statuses below 500 that don't say anything about the request: a request timeout
#: and a rate limit.  :func:`is_transient` adds every 5xx.
TRANSIENT_STATUSES = frozenset({408, 429})

#: HTTP statuses that refuse CalDART's own credentials or permissions.
AUTHORIZATION_STATUSES = frozenset({401, 403})


def api_base() -> str:
    """The PayPal API host: the live one when ``PAYPAL_ENV`` is ``live``, else sandbox."""
    return LIVE_BASE if settings.PAYPAL_ENV == "live" else SANDBOX_BASE


def unavailable(call_name: str, exc: Exception) -> ProviderUnavailableError:
    """Log a PayPal call that never completed, and build the error to raise.

    ``call_name`` is the method and path attempted.  Only the exception's class
    is recorded, because its message can quote request data.
    """
    log.warning("PayPal %s failed: %s", call_name, type(exc).__name__)
    return ProviderUnavailableError(UNAVAILABLE_MESSAGE)


def segment(value: str) -> str:
    """``value`` escaped as one URL path segment, for an id spliced into a PayPal path.

    Every character outside the unreserved set is percent-encoded, ``/`` included, so
    the id can never name another resource: ``"A/../B"`` becomes ``"A%2F..%2FB"``,
    and a ``?`` or a ``#`` cannot start a query or a fragment.
    """
    return quote(value, safe="")


def credentials() -> tuple[str, str]:
    """The configured client id and secret.

    Raises :class:`ProviderNotConfiguredError` when either is empty, so an
    unconfigured PayPal answers 400 rather than 500.
    """
    client_id = settings.PAYPAL_CLIENT_ID
    client_secret = settings.PAYPAL_CLIENT_SECRET
    if not client_id or not client_secret:
        raise ProviderNotConfiguredError(
            "PayPal is not configured (PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET are empty)."
        )
    return client_id, client_secret


def dollars(cents: int) -> str:
    """PayPal wants a decimal string, always with two places: 4500 -> ``"45.00"``."""
    return f"{cents / 100:.2f}"


def cents(value: str | float | int) -> int:
    """Inverse of :func:`dollars`, rounded to the nearest cent.

    Takes the decimal string PayPal sends, or a number.  Raises ``ValueError``
    for a string that is not a number.
    """
    return round(float(value) * 100)


class CachedToken(TypedDict):
    """The cached OAuth token and the API base and client id it was fetched for."""

    key: list[str]
    token: str


def access_token() -> str:
    """A valid client-credentials token, fetched at most once per lifetime.

    The token is held in Django's default cache under
    :data:`TOKEN_CACHE_KEY` for its remaining lifetime less
    ``TOKEN_SKEW_SECONDS``, so it is never presented after PayPal has dropped it.
    Whether that cache is shared between worker processes is the cache backend's
    business: a per-process backend simply costs one token fetch per process.
    The entry records the API base and client id it was fetched for, so changing
    either fetches a fresh token rather than presenting one PayPal will refuse.
    Emptying the cache forces the next call to fetch.

    Raises :class:`ProviderNotConfiguredError` without credentials,
    :class:`ProviderUnavailableError` when the token call does not complete or
    PayPal answers with a status :func:`is_transient` names, and
    :class:`PaymentVerificationError` when PayPal refuses the credentials or
    doesn't return a token.
    """
    client_id, client_secret = credentials()
    key = [api_base(), client_id]
    cached: CachedToken | None = cache.get(TOKEN_CACHE_KEY)
    if cached is not None and cached["key"] == key:
        return cached["token"]

    try:
        response = httpx.post(
            f"{api_base()}/v1/oauth2/token",
            auth=(client_id, client_secret),
            data={"grant_type": "client_credentials"},
            headers={"Accept": "application/json"},
            timeout=TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        raise unavailable("POST /v1/oauth2/token", exc) from exc
    if is_transient(response.status_code):
        raise unavailable_status("POST /v1/oauth2/token", response.status_code)
    if response.status_code != 200:
        raise PaymentVerificationError(
            f"PayPal refused our credentials (HTTP {response.status_code})."
        )
    try:
        body = response.json()
    except ValueError as exc:
        raise unavailable("POST /v1/oauth2/token", exc) from exc
    token: str = body.get("access_token") or ""
    if not token:
        raise PaymentVerificationError("PayPal didn't return an access token.")

    lifetime = max(int(body.get("expires_in", 0)) - TOKEN_SKEW_SECONDS, MINIMUM_TOKEN_SECONDS)
    cache.set(TOKEN_CACHE_KEY, CachedToken(key=key, token=token), timeout=lifetime)
    return token


def call(
    method: str, path: str, *, json_body: dict[str, Any] | None = None, request_id: str = ""
) -> dict[str, Any]:
    """One authenticated Orders v2 call, returning the decoded body.

    ``request_id`` is sent as ``PayPal-Request-Id``, which makes the call
    idempotent at PayPal: a create repeated under the same id answers with the
    resource the first call made rather than making a second one.

    Raises :class:`~apps.payments.providers.base.ProviderUnavailableError` when the
    call never completes (a timeout or a dropped connection) and when PayPal answers
    with a status :func:`is_transient` names -- a fault on PayPal's side, a rate
    limit, a request timeout -- none of which says whether PayPal acted.  Raises
    :class:`PayPalRequestError`, a
    :class:`~apps.payments.providers.base.PaymentVerificationError`, for any other
    error status: PayPal's answer about the request itself, carrying its HTTP
    status and issue codes.  A call that certainly never reached PayPal -- the
    token could not be fetched, or the connection was never made -- raises
    :class:`~apps.payments.providers.base.RequestNotSentError`, the outage error
    that also says that nothing was asked.  A body that is not JSON is read as an empty
    dict, so a successful call with an unreadable body returns ``{}``.
    """
    try:
        token = access_token()
    except ProviderUnavailableError as exc:
        raise RequestNotSentError(UNAVAILABLE_MESSAGE) from exc
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if request_id:
        headers["PayPal-Request-Id"] = request_id
    try:
        response = httpx.request(
            method,
            f"{api_base()}{path}",
            headers=headers,
            json=json_body,
            timeout=TIMEOUT_SECONDS,
        )
    except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
        unavailable(f"{method} {path}", exc)
        raise RequestNotSentError(UNAVAILABLE_MESSAGE) from exc
    except httpx.HTTPError as exc:
        raise unavailable(f"{method} {path}", exc) from exc
    try:
        body: dict[str, Any] = response.json()
    except ValueError:
        body = {}
    if is_transient(response.status_code):
        raise unavailable_status(f"{method} {path}", response.status_code)
    if response.status_code >= 400:
        detail = body.get("message") or body.get("name") or f"HTTP {response.status_code}"
        raise PayPalRequestError(
            f"PayPal rejected the request: {detail}",
            status=response.status_code,
            issues=issues(body),
        )
    return body


def is_transient(status: int) -> bool:
    """Whether an HTTP ``status`` from PayPal doesn't say anything about the request.

    A 5xx is a fault on PayPal's side, a 429 a rate limit and a 408 a request that
    timed out there: any of them may follow work PayPal has already done, so the
    caller is told PayPal did not answer rather than that it refused.
    """
    return status >= 500 or status in TRANSIENT_STATUSES


def unavailable_status(call_name: str, status: int) -> ProviderUnavailableError:
    """Log a PayPal call answered with a transient ``status``, and build the error."""
    log.warning("PayPal %s answered HTTP %s", call_name, status)
    return ProviderUnavailableError(UNAVAILABLE_MESSAGE)


def issues(body: dict[str, Any]) -> list[str]:
    """The ``details[].issue`` codes of a PayPal error body: ``DUPLICATE_INVOICE_ID``."""
    return [
        str(detail.get("issue"))
        for detail in body.get("details") or []
        if isinstance(detail, dict) and detail.get("issue")
    ]


class PayPalRequestError(PaymentVerificationError):
    """PayPal refused a request, saying why.

    ``status`` is the HTTP status, and ``issues`` holds the ``details[].issue`` codes
    PayPal gave, so a caller can tell one refusal from another without parsing the
    message.  :attr:`is_authorization` is true for a 401 or a 403: PayPal refusing
    CalDART's own credentials, which doesn't say anything about the payer.
    """

    def __init__(self, message: str, *, status: int, issues: list[str]) -> None:
        """Store ``status`` and ``issues`` beside the message."""
        super().__init__(message)
        self.status = status
        self.issues = issues

    @property
    def is_authorization(self) -> bool:
        """Whether PayPal refused CalDART's credentials (401) or permissions (403)."""
        return self.status in AUTHORIZATION_STATUSES
