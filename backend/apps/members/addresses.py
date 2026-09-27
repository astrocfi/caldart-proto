"""Street-address suggestions from Geoapify, shaped to fill the profile's address fields.

The profile form offers matching US addresses as a member types the street line.  The
browser never talks to Geoapify: ``GET /addresses/suggest`` calls
:func:`suggest_addresses`, which forwards the text to Geoapify's autocomplete endpoint
with the key from ``GEOAPIFY_API_KEY``.  Results are limited to the United States and
biased toward California so in-state matches sort first.

Each Geoapify result that names a street becomes one :class:`AddressSuggestion`: the
street line, city, two-letter state, five-digit ZIP code, and the California county
when the result lies in one of the fifty-eight the profile stores.  Suggestions are a
convenience, so every failure -- no key, a short query, a slow or refusing provider, an
unreadable answer -- yields an empty list rather than an error.
"""

from __future__ import annotations

import logging
import re
from typing import Any, TypedDict

import httpx
from django.conf import settings

from apps.members.models import CALIFORNIA_COUNTIES, US_STATE_CHOICES

log = logging.getLogger(__name__)

#: The shortest query worth sending: fewer characters narrow nothing and spend quota.
MIN_QUERY_LENGTH = 3

#: How long to wait on Geoapify, in seconds, before giving up on this keystroke.
GEOAPIFY_TIMEOUT_SECONDS = 3.0

#: The most suggestions asked for, which is as many as fit under the street field.
SUGGESTION_LIMIT = 5

#: California's bounding box as ``lon1,lat1,lon2,lat2``, so in-state matches rank first.
CALIFORNIA_BIAS = "rect:-124.48,32.53,-114.13,42.01"

#: The postcode prefix the ZIP code field keeps: five digits, any ZIP+4 dropped.
ZIP_CODE = re.compile(r"^(\d{5})(?:-\d{4})?$")

#: The country Geoapify appends to every formatted address, which a US-only list omits.
COUNTRY_SUFFIXES = (", United States of America", ", United States")

#: Geoapify's names for the place a street lies in, most specific first.  A small
#: place has no ``city`` but a ``town`` or ``village``.
LOCALITY_KEYS = ("city", "town", "village", "hamlet")

_STATE_CODES = {code for code, _ in US_STATE_CHOICES}
_STATE_CODES_BY_NAME = {name.casefold(): code for code, name in US_STATE_CHOICES}
_COUNTIES_BY_NAME = {name.casefold(): name for name in CALIFORNIA_COUNTIES}


class AddressSuggestion(TypedDict):
    """One address the profile form can fill in at a pick.

    ``label`` is the whole address on one line, for the list under the street field.
    The other five are the profile fields a pick fills; any Geoapify could not supply
    in the profile's own terms is an empty string.
    """

    label: str
    address_line1: str
    city: str
    state: str
    postal_code: str
    county: str


def suggest_addresses(query: str) -> list[AddressSuggestion]:
    """Up to five US addresses matching ``query``, California first, in Geoapify's order.

    ``query`` is stripped first.  Nothing is sent, and ``[]`` comes back, when
    ``GEOAPIFY_API_KEY`` is blank or the stripped query is shorter than
    ``MIN_QUERY_LENGTH``.  A call that times out after ``GEOAPIFY_TIMEOUT_SECONDS``,
    fails to connect, answers an error status, or answers anything but a JSON object
    with a ``results`` list also yields ``[]``, logged as a warning without the query.
    Results without a street are skipped, and two results that would fill the same
    five fields are offered once.
    """
    text = query.strip()
    api_key: str = settings.GEOAPIFY_API_KEY
    if len(api_key) == 0 or len(text) < MIN_QUERY_LENGTH:
        return []
    results = _fetch_results(text, api_key)
    suggestions: list[AddressSuggestion] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for result in results:
        suggestion = _suggestion(result)
        if suggestion is None:
            continue
        key = (
            suggestion["address_line1"],
            suggestion["city"],
            suggestion["state"],
            suggestion["postal_code"],
            suggestion["county"],
        )
        if key in seen:
            continue
        seen.add(key)
        suggestions.append(suggestion)
    return suggestions


def california_county(state: str, county: str) -> str:
    """The profile's name for ``county`` when it is a California county, else ``""``.

    ``state`` is a two-letter code, and anything but ``CA`` yields ``""``.  ``county``
    is Geoapify's name for it, matched without regard to case or surrounding space and
    with a trailing ``County`` or a leading ``City and County of`` removed, so
    ``Santa Clara County`` gives ``Santa Clara`` and ``City and County of San
    Francisco`` gives ``San Francisco``.  A name that is not one of the fifty-eight
    yields ``""``.
    """
    if state != "CA":
        return ""
    name = county.strip().casefold()
    name = name.removeprefix("city and county of ").removesuffix(" county").strip()
    return _COUNTIES_BY_NAME.get(name, "")


def _fetch_results(text: str, api_key: str) -> list[dict[str, Any]]:
    """Geoapify's result objects for ``text``, or ``[]`` when the call goes wrong."""
    params = {
        "text": text,
        "apiKey": api_key,
        "filter": "countrycode:us",
        "bias": CALIFORNIA_BIAS,
        "format": "json",
        "limit": str(SUGGESTION_LIMIT),
        "lang": "en",
    }
    try:
        response = httpx.get(settings.GEOAPIFY_URL, params=params, timeout=GEOAPIFY_TIMEOUT_SECONDS)
    except httpx.HTTPError as exc:
        # The query is a member's home address, so only the failure is logged.
        log.warning("Geoapify autocomplete did not complete: %s", type(exc).__name__)
        return []
    if response.status_code != 200:
        log.warning("Geoapify autocomplete answered HTTP %s", response.status_code)
        return []
    try:
        body = response.json()
    except ValueError:
        log.warning("Geoapify autocomplete answered a body that is not JSON")
        return []
    results = body.get("results") if isinstance(body, dict) else None
    if not isinstance(results, list):
        log.warning("Geoapify autocomplete answered without a results list")
        return []
    return [result for result in results if isinstance(result, dict)]


def _suggestion(result: dict[str, Any]) -> AddressSuggestion | None:
    """``result`` in the profile's terms, or ``None`` when it names no street."""
    street = _text(result, "street")
    if len(street) == 0:
        return None
    address_line1 = f"{_text(result, 'housenumber')} {street}".strip()
    city = next((_text(result, key) for key in LOCALITY_KEYS if _text(result, key)), "")
    state = _state_code(result)
    postal_code = _zip_code(_text(result, "postcode"))
    return AddressSuggestion(
        label=_label(result, address_line1, city, state, postal_code),
        address_line1=address_line1,
        city=city,
        state=state,
        postal_code=postal_code,
        county=california_county(state, _text(result, "county")),
    )


def _text(result: dict[str, Any], key: str) -> str:
    """``result[key]`` stripped when it is a string, else ``""``."""
    value = result.get(key)
    return value.strip() if isinstance(value, str) else ""


def _state_code(result: dict[str, Any]) -> str:
    """The two-letter state from ``state_code`` or the state's name, else ``""``."""
    code = _text(result, "state_code").upper()
    if code in _STATE_CODES:
        return code
    return _STATE_CODES_BY_NAME.get(_text(result, "state").casefold(), "")


def _zip_code(postcode: str) -> str:
    """The five-digit ZIP code in ``postcode``, or ``""`` when it holds none."""
    match = ZIP_CODE.match(postcode)
    return match.group(1) if match is not None else ""


def _label(
    result: dict[str, Any], address_line1: str, city: str, state: str, postal_code: str
) -> str:
    """The one-line address for the list: Geoapify's own, without the country.

    A result with no ``formatted`` address is labeled from its parts instead.
    """
    formatted = _text(result, "formatted")
    for suffix in COUNTRY_SUFFIXES:
        formatted = formatted.removesuffix(suffix)
    if len(formatted) > 0:
        return formatted
    place = " ".join(part for part in (state, postal_code) if part)
    return ", ".join(part for part in (address_line1, city, place) if part)
