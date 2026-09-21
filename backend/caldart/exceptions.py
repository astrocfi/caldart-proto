"""Domain errors, and the DRF exception handling that renders them.

The API layer validates input; the services own the rules and refuse work by
raising a ``DomainError``.  A service is therefore callable from a management
command, the Django admin or a test without dragging HTTP along, and the
translation happens in one place: :func:`caldart_exception_handler` renders a
``DomainValidationError`` as a 400 keyed by the field it names and a
``DomainPermissionError`` as a 403 carrying ``detail``.

Session authentication has no ``WWW-Authenticate`` challenge, so DRF turns an
unauthenticated request into 403.  The API contract promises 401,
which is also what the SPA's ``client.ts`` keys "log in again" off.
"""

from __future__ import annotations

from typing import Any

from rest_framework.exceptions import NotAuthenticated, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


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
    except that ``NotAuthenticated`` is rewritten from 403 to 401.  An exception
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
    return response
