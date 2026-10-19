"""Domain errors, and the DRF exception handling that renders them.

The API layer validates input; the services own the rules and refuse work by
raising a ``DomainError``.  A service is therefore callable from a management
command, the Django admin or a test without dragging HTTP along, and the
translation happens in one place: :func:`caldart_exception_handler` renders a
``DomainValidationError`` as a 400 keyed by the field it names and a
``DomainPermissionError`` as a 403 carrying ``detail``.

Session authentication doesn't have a ``WWW-Authenticate`` challenge, so DRF turns an
unauthenticated request into 403.  The API contract promises 401,
which is also what the SPA's ``client.ts`` keys "log in again" off.

A 404 that carries only Django's or DRF's stock sentence ("No User matches the given
query.", "Not found.") is answered with :data:`NOT_FOUND_MESSAGE`, because the portal
shows ``detail`` to the person; a 404 a view raised with its own sentence keeps it.

A 429 says *Too many tries. Try again in N seconds.* in place of DRF's stock *Request was
throttled. Expected available in N seconds.*; a ``Throttled`` raised with a sentence of
its own keeps that sentence and gains the same *Try again in N seconds.*
"""

from __future__ import annotations

import math
import re
from typing import Any

from django.http import Http404
from rest_framework.exceptions import (
    NotAuthenticated,
    NotFound,
    PermissionDenied,
    Throttled,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

#: The 404 ``detail`` a person reads in place of Django's or DRF's stock sentence.
NOT_FOUND_MESSAGE = "That isn't here. It may have been deleted."

#: What a 429 says in place of DRF's stock *Request was throttled.*
THROTTLED_MESSAGE = "Too many tries."

#: The sentences Django's ``get_object_or_404`` and DRF's ``NotFound`` put in a 404.
_STOCK_NOT_FOUND = re.compile(r"No .+ matches the given query\.|Not found\.")


class DomainError(Exception):
    """A rule a service refused to break.

    ``message`` is the sentence the caller is shown, and is also the exception's
    string form, so a command or a log line reads the same text the API returns.
    """

    def __init__(self, message: str) -> None:
        """Store ``message`` as both ``self.message`` and the exception's string form."""
        super().__init__(message)
        self.message = message


class DomainValidationError(DomainError):
    """Input a service refused, named by the request field it belongs to.

    ``field`` is the field the complaint is shown against, so an API caller can
    put it beside the input it came from.
    """

    def __init__(self, field: str, message: str) -> None:
        """Store ``field`` and pass ``message`` to :class:`DomainError`."""
        super().__init__(message)
        self.field = field


class DomainPermissionError(DomainError):
    """An action the actor is not allowed to take on the target.

    The input was well formed and the rule is about who is asking, so the answer
    carries one sentence rather than a field.
    """


def caldart_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """Render ``exc`` as an API response, or ``None`` to leave it to Django.

    A ``DomainValidationError`` becomes 400 ``{field: [message]}`` and a
    ``DomainPermissionError`` 403 ``{"detail": message}``, the shapes DRF's own
    validation and permission errors produce.  Everything else is DRF's answer,
    except that ``NotAuthenticated`` is rewritten from 403 to 401 and a 404 without a
    sentence of its own reads :data:`NOT_FOUND_MESSAGE`.  An exception
    the API does not describe -- a bug -- still returns ``None`` and reaches
    Django's 500 handling.
    """
    if isinstance(exc, DomainValidationError):
        exc = ValidationError({exc.field: [exc.message]})
    elif isinstance(exc, DomainPermissionError):
        exc = PermissionDenied(exc.message)

    response = drf_exception_handler(exc, context)
    if response is not None and isinstance(exc, NotAuthenticated):
        response.status_code = 401
    if response is not None and isinstance(exc, Http404 | NotFound):
        detail = str(response.data.get("detail", ""))
        if detail == "" or _STOCK_NOT_FOUND.fullmatch(detail) is not None:
            response.data = {"detail": NOT_FOUND_MESSAGE}
    if response is not None and isinstance(exc, Throttled):
        response.data = {"detail": throttled_message(exc)}
    return response


def throttled_message(exc: Throttled) -> str:
    """What a 429 for ``exc`` says: its sentence, then when to try again.

    The sentence is :data:`THROTTLED_MESSAGE` when ``exc`` carries DRF's stock one, and
    ``exc``'s own otherwise, with DRF's *Expected available in N seconds.* taken off.  It
    is followed by *Try again in N seconds.* (*1 second* for one), or by *Try again
    later.* when ``exc`` doesn't carry a wait.
    """
    detail = str(exc.detail)
    # djangorestframework-stubs leaves out the ``wait`` that ``Throttled.__init__`` sets.
    wait_seconds: float | None = exc.wait  # type: ignore[attr-defined]
    if wait_seconds is None:
        sentence = detail
        retry = "Try again later."
    else:
        wait = math.ceil(wait_seconds)
        extra = exc.extra_detail_singular if wait == 1 else exc.extra_detail_plural
        sentence = detail.removesuffix(" " + str(extra).format(wait=wait))
        retry = f"Try again in {wait} second{'' if wait == 1 else 's'}."
    if sentence == str(exc.default_detail):
        sentence = THROTTLED_MESSAGE
    return f"{sentence} {retry}"
