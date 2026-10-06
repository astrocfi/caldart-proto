"""Plain-language messages for the serializer fields a person fills in.

DRF answers a box left empty with its own stock sentences ("This field may not be
blank.", "This field is required.").  A form field a person types into names what to
put there instead, and these helpers build the ``error_messages`` dictionary that does.
The module also holds the sentences that refuse a field an endpoint does not change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django_stubs_ext import StrPromise

#: What DRF's ``error_messages`` takes: each key's message, plain or lazily translated.
type ErrorMessages = dict[str, str | StrPromise]

#: The answer to an email address that does not parse as one.
INVALID_EMAIL_MESSAGE = "Enter an email address, such as name@example.org."

#: The answer to a name or an email address sent to the user record, which changes
#: roles only.
USER_RECORD_ROLES_ONLY = (
    "The user record changes roles only. A name or an email address is changed on the "
    "member record, or by the person themselves."
)


def when_missing(message: str) -> ErrorMessages:
    """Return ``error_messages`` that answer an empty value with ``message``.

    The keys are DRF's ``blank``, ``required``, and ``null``, so whichever way the box
    arrives empty, the person reads the same sentence.
    """
    return {"blank": message, "required": message, "null": message}


def email_messages(missing: str) -> ErrorMessages:
    """Return ``error_messages`` for an email field: ``missing`` when it is empty.

    A value that is not an email address is answered with
    :data:`INVALID_EMAIL_MESSAGE`.
    """
    return {**when_missing(missing), "invalid": INVALID_EMAIL_MESSAGE}
