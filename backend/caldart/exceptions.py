"""DRF exception handling.

Session authentication has no ``WWW-Authenticate`` challenge, so DRF turns an
unauthenticated request into 403.  The API contract (PLAN §6.1) promises 401,
which is also what the SPA's ``client.ts`` keys "log in again" off.
"""

from __future__ import annotations

from rest_framework.exceptions import NotAuthenticated
from rest_framework.views import exception_handler as drf_exception_handler


def caldart_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is not None and isinstance(exc, NotAuthenticated):
        response.status_code = 401
    return response
