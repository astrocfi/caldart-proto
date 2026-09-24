"""One spelling for a phone number, shared by every app that stores one.

A member's numbers, a DART contact's number and anything else typed into this
system are stored as ``XXX-XXX-XXXX``: one shape to read, to search on and to
print, rather than a dozen spellings to clean up afterwards.
"""

import re

#: A phone number as this system stores and prints it.
PHONE_RE = re.compile(r"^\d{3}-\d{3}-\d{4}$")

#: What a phone extension may be: digits, and not many of them.
PHONE_EXTENSION_RE = re.compile(r"^\d{1,6}$")

_PHONE_STRIP = re.compile(r"[^0-9]")


def normalize_phone(value: str | None) -> str:
    """Return ``value`` as ``XXX-XXX-XXXX``, or unchanged when it cannot be.

    Punctuation and spaces are dropped and a leading country code ``1`` is
    removed, so ``+1 (415) 555-0100``, ``415.555.0100`` and ``4155550100`` all
    come back ``415-555-0100``.  A blank value gives ``""``.  Anything that is
    not ten digits after that is returned stripped of nothing, for the caller to
    refuse: this function never invents a number.
    """
    if not value:
        return ""
    digits = _PHONE_STRIP.sub("", value)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        return value.strip()
    return f"{digits[:3]}-{digits[3:6]}-{digits[6:]}"
