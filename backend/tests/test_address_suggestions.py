"""Address suggestions: ``GET /addresses/suggest?q=`` and the Geoapify client behind it.

The endpoint forwards a signed-in member's partial street address to Geoapify's
autocomplete endpoint, limited to the United States and biased toward California, and
answers ``[{label, address_line1, city, state, postal_code, county}]``.  A blank
``GEOAPIFY_API_KEY`` turns the feature off, and any failure to reach Geoapify answers an
empty list rather than an error.  Geoapify is mocked with ``respx`` throughout.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import httpx
import pytest
import respx
from django.core.cache import cache
from pytest_django import Settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.members.addresses import (
    GEOAPIFY_TIMEOUT_SECONDS,
    california_county,
    suggest_addresses,
)
from apps.members.throttling import ADDRESS_SUGGEST_SCOPE, AddressSuggestThrottle

pytestmark = pytest.mark.django_db

SUGGEST_URL = "/api/v1/addresses/suggest"
GEOAPIFY_URL = "https://geoapify.test/v1/geocode/autocomplete"
API_KEY = "test-geoapify-key"  # a stand-in; nothing is sent anywhere

#: Geoapify's answer to ``text=1600 Amph``, trimmed to the fields the client reads plus a
#: few it ignores.  The second result is outside California, and the third is a city
#: with no street, which cannot fill an address line.
GEOAPIFY_RESPONSE: dict[str, Any] = {
    "results": [
        {
            "country_code": "us",
            "housenumber": "1600",
            "street": "Amphitheatre Parkway",
            "country": "United States",
            "county": "Santa Clara County",
            "postcode": "94043",
            "state": "California",
            "state_code": "CA",
            "city": "Mountain View",
            "lon": -122.0842,
            "lat": 37.4224,
            "result_type": "building",
            "formatted": (
                "1600 Amphitheatre Parkway, Mountain View, CA 94043, United States of America"
            ),
            "address_line1": "1600 Amphitheatre Parkway",
            "address_line2": "Mountain View, CA 94043, United States of America",
        },
        {
            "country_code": "us",
            "housenumber": "1600",
            "street": "Amphitheater Drive",
            "country": "United States",
            "county": "Clark County",
            "postcode": "89109-1234",
            "state": "Nevada",
            "state_code": "NV",
            "city": "Las Vegas",
            "result_type": "building",
            "formatted": "1600 Amphitheater Drive, Las Vegas, NV 89109, United States of America",
            "address_line1": "1600 Amphitheater Drive",
        },
        {
            "country_code": "us",
            "country": "United States",
            "county": "Santa Clara County",
            "state": "California",
            "state_code": "CA",
            "city": "Amphitown",
            "result_type": "city",
            "formatted": "Amphitown, CA, United States of America",
            "address_line1": "Amphitown",
        },
    ],
    "query": {"text": "1600 Amph"},
}

#: What the endpoint makes of ``GEOAPIFY_RESPONSE``.
EXPECTED_SUGGESTIONS = [
    {
        "label": "1600 Amphitheatre Parkway, Mountain View, CA 94043",
        "address_line1": "1600 Amphitheatre Parkway",
        "city": "Mountain View",
        "state": "CA",
        "postal_code": "94043",
        "county": "Santa Clara",
    },
    {
        "label": "1600 Amphitheater Drive, Las Vegas, NV 89109",
        "address_line1": "1600 Amphitheater Drive",
        "city": "Las Vegas",
        "state": "NV",
        "postal_code": "89109",
        "county": "",
    },
]


@pytest.fixture
def geoapify(settings: Settings) -> Iterator[respx.Router]:
    """A configured key and a mocked Geoapify that answers ``GEOAPIFY_RESPONSE``."""
    settings.GEOAPIFY_API_KEY = API_KEY
    settings.GEOAPIFY_URL = GEOAPIFY_URL
    with respx.mock(assert_all_mocked=True, assert_all_called=False) as router:
        router.get(GEOAPIFY_URL).mock(return_value=httpx.Response(200, json=GEOAPIFY_RESPONSE))
        yield router


@pytest.fixture
def member_client(api_client: APIClient, member: User) -> APIClient:
    """The API client signed in as a plain member."""
    api_client.force_login(member)
    return api_client


@pytest.fixture
def empty_throttle_cache() -> Iterator[None]:
    """The throttle counters are shared state; no test may inherit them."""
    cache.clear()
    yield
    cache.clear()


def geoapify_params(router: respx.Router) -> dict[str, str]:
    """The query parameters of the one call the router saw."""
    return dict(router.calls.last.request.url.params)


# -- the endpoint ------------------------------------------------------------------


def test_a_signed_in_member_gets_the_mapped_suggestions(
    member_client: APIClient, geoapify: respx.Router
) -> None:
    """Each Geoapify result with a street becomes one suggestion, in Geoapify's order."""
    response = member_client.get(SUGGEST_URL, {"q": "1600 Amph"})

    assert response.status_code == 200
    assert response.json() == EXPECTED_SUGGESTIONS


def test_an_anonymous_caller_is_refused(api_client: APIClient, geoapify: respx.Router) -> None:
    """Without a session the endpoint answers 401 and never calls Geoapify."""
    response = api_client.get(SUGGEST_URL, {"q": "1600 Amph"})

    assert response.status_code == 401
    assert geoapify.calls.call_count == 0


def test_the_query_goes_to_geoapify_limited_to_the_us_and_biased_to_california(
    member_client: APIClient, geoapify: respx.Router
) -> None:
    """The call carries the text, the key, the US filter, and the California bias."""
    member_client.get(SUGGEST_URL, {"q": "  1600 Amph  "})

    assert geoapify_params(geoapify) == {
        "text": "1600 Amph",
        "apiKey": API_KEY,
        "filter": "countrycode:us",
        "bias": "rect:-124.48,32.53,-114.13,42.01",
        "format": "json",
        "limit": "5",
        "lang": "en",
    }


def test_the_key_never_reaches_the_client(member_client: APIClient, geoapify: respx.Router) -> None:
    """The response body carries nothing of the Geoapify key."""
    response = member_client.get(SUGGEST_URL, {"q": "1600 Amph"})

    assert API_KEY not in response.content.decode()


@pytest.mark.parametrize("query", ["", "16", "  16  "], ids=["empty", "two", "two-padded"])
def test_a_query_shorter_than_three_characters_answers_nothing(
    member_client: APIClient, geoapify: respx.Router, query: str
) -> None:
    """A query too short to narrow anything answers ``[]`` without calling Geoapify."""
    response = member_client.get(SUGGEST_URL, {"q": query})

    assert response.json() == []
    assert geoapify.calls.call_count == 0


def test_a_missing_query_answers_nothing(member_client: APIClient, geoapify: respx.Router) -> None:
    """No ``q`` at all is the same as an empty one."""
    response = member_client.get(SUGGEST_URL)

    assert response.status_code == 200
    assert response.json() == []


def test_an_overlong_query_is_refused(member_client: APIClient, geoapify: respx.Router) -> None:
    """A ``q`` over 200 characters is a 400 naming the field, not a call to Geoapify."""
    response = member_client.get(SUGGEST_URL, {"q": "x" * 201})

    assert response.status_code == 400
    assert response.json() == {"q": ["Ensure this field has no more than 200 characters."]}


def test_a_blank_key_turns_the_feature_off(
    member_client: APIClient, geoapify: respx.Router, settings: Settings
) -> None:
    """With no key configured the endpoint answers ``200 []`` and calls nobody."""
    settings.GEOAPIFY_API_KEY = ""

    response = member_client.get(SUGGEST_URL, {"q": "1600 Amph"})

    assert response.status_code == 200
    assert response.json() == []
    assert geoapify.calls.call_count == 0


@pytest.mark.parametrize(
    "answer",
    [
        httpx.Response(500, json={"message": "boom"}),
        httpx.Response(401, json={"message": "Invalid apiKey"}),
        httpx.Response(200, text="not json"),
        httpx.Response(200, json={"unexpected": True}),
        httpx.Response(200, json=["not", "an", "object"]),
    ],
    ids=["server-error", "refused-key", "not-json", "no-results", "wrong-shape"],
)
def test_a_bad_answer_from_geoapify_degrades_to_no_suggestions(
    member_client: APIClient, geoapify: respx.Router, answer: httpx.Response
) -> None:
    """An error status or an unreadable body answers ``200 []``, never an error."""
    geoapify.get(GEOAPIFY_URL).mock(return_value=answer)

    response = member_client.get(SUGGEST_URL, {"q": "1600 Amph"})

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize(
    "error",
    [httpx.ConnectTimeout("slow"), httpx.ConnectError("refused")],
    ids=["timeout", "unreachable"],
)
def test_an_unreachable_geoapify_degrades_to_no_suggestions(
    member_client: APIClient, geoapify: respx.Router, error: httpx.HTTPError
) -> None:
    """A call that never completes answers ``200 []``."""
    geoapify.get(GEOAPIFY_URL).mock(side_effect=error)

    response = member_client.get(SUGGEST_URL, {"q": "1600 Amph"})

    assert response.status_code == 200
    assert response.json() == []


def test_the_call_carries_a_short_timeout(member_client: APIClient, geoapify: respx.Router) -> None:
    """The request to Geoapify gives up after ``GEOAPIFY_TIMEOUT_SECONDS``."""
    member_client.get(SUGGEST_URL, {"q": "1600 Amph"})

    timeout = geoapify.calls.last.request.extensions["timeout"]
    assert timeout == {
        "connect": GEOAPIFY_TIMEOUT_SECONDS,
        "read": GEOAPIFY_TIMEOUT_SECONDS,
        "write": GEOAPIFY_TIMEOUT_SECONDS,
        "pool": GEOAPIFY_TIMEOUT_SECONDS,
    }


# -- the throttle ------------------------------------------------------------------


@pytest.mark.usefixtures("empty_throttle_cache")
def test_the_throttle_answers_429_past_the_rate(
    member_client: APIClient, geoapify: respx.Router, settings: Settings
) -> None:
    """With a rate of two a minute, the third request in the minute is a 429."""
    settings.ADDRESS_SUGGEST_THROTTLE_RATE = "2/min"

    statuses = [member_client.get(SUGGEST_URL, {"q": "1600 Amph"}).status_code for _ in range(3)]

    assert statuses == [200, 200, 429]


@pytest.mark.usefixtures("empty_throttle_cache")
def test_the_throttle_counts_each_user_separately(
    api_client: APIClient,
    member: User,
    dart_leader: User,
    geoapify: respx.Router,
    settings: Settings,
) -> None:
    """One member spending the budget leaves another member's untouched."""
    settings.ADDRESS_SUGGEST_THROTTLE_RATE = "1/min"
    api_client.force_login(member)
    api_client.get(SUGGEST_URL, {"q": "1600 Amph"})
    api_client.force_login(dart_leader)

    response = api_client.get(SUGGEST_URL, {"q": "1600 Amph"})

    assert response.status_code == 200


@pytest.mark.parametrize("rate", [None, ""], ids=["none", "empty"])
def test_an_empty_rate_makes_the_throttle_inert(settings: Settings, rate: str | None) -> None:
    """``None`` or an empty string for the rate switches the throttle off."""
    settings.ADDRESS_SUGGEST_THROTTLE_RATE = rate

    assert AddressSuggestThrottle().get_rate() is None


def test_the_throttle_reads_its_rate_from_settings(settings: Settings) -> None:
    """The rate is ``ADDRESS_SUGGEST_THROTTLE_RATE``, scope ``address_suggest`` scope."""
    settings.ADDRESS_SUGGEST_THROTTLE_RATE = "7/min"

    throttle = AddressSuggestThrottle()

    assert throttle.scope == ADDRESS_SUGGEST_SCOPE
    assert throttle.get_rate() == "7/min"


# -- the county mapping and the client --------------------------------------------


@pytest.mark.parametrize(
    ("state", "county", "expected"),
    [
        ("CA", "Santa Clara County", "Santa Clara"),
        ("CA", "santa clara county", "Santa Clara"),
        ("CA", "Santa Clara", "Santa Clara"),
        ("CA", "City and County of San Francisco", "San Francisco"),
        ("CA", "San Francisco", "San Francisco"),
        ("CA", "  Los Angeles County ", "Los Angeles"),
        ("CA", "Cook County", ""),
        ("CA", "", ""),
        ("NV", "Clark County", ""),
        ("NV", "Santa Clara County", ""),
        ("", "Santa Clara County", ""),
    ],
    ids=[
        "suffix",
        "lower-case",
        "bare",
        "city-and-county",
        "bare-san-francisco",
        "padded",
        "not-californian",
        "blank",
        "other-state",
        "californian-name-other-state",
        "no-state",
    ],
)
def test_the_county_maps_onto_the_california_choices(
    state: str, county: str, expected: str
) -> None:
    """Only a California result whose county is one of the fifty-eight keeps it."""
    assert california_county(state, county) == expected


def test_a_state_named_without_a_code_is_still_read(
    geoapify: respx.Router,
) -> None:
    """A result with a state name but no ``state_code`` takes the code from the name."""
    result = dict(GEOAPIFY_RESPONSE["results"][0])
    del result["state_code"]
    geoapify.get(GEOAPIFY_URL).mock(return_value=httpx.Response(200, json={"results": [result]}))

    suggestions = suggest_addresses("1600 Amph")

    assert [suggestion["state"] for suggestion in suggestions] == ["CA"]


def test_a_town_stands_in_for_a_missing_city(geoapify: respx.Router) -> None:
    """A result that names a town or village instead of a city fills the city with it."""
    result = dict(GEOAPIFY_RESPONSE["results"][0])
    del result["city"]
    result["town"] = "Los Altos Hills"
    geoapify.get(GEOAPIFY_URL).mock(return_value=httpx.Response(200, json={"results": [result]}))

    suggestions = suggest_addresses("1600 Amph")

    assert [suggestion["city"] for suggestion in suggestions] == ["Los Altos Hills"]


def test_a_street_without_a_house_number_fills_the_street_alone(geoapify: respx.Router) -> None:
    """A street-level result fills the address line with the street's name."""
    result = dict(GEOAPIFY_RESPONSE["results"][0])
    del result["housenumber"]
    geoapify.get(GEOAPIFY_URL).mock(return_value=httpx.Response(200, json={"results": [result]}))

    suggestions = suggest_addresses("Amphitheatre")

    assert [suggestion["address_line1"] for suggestion in suggestions] == ["Amphitheatre Parkway"]


def test_a_postal_code_that_is_not_five_digits_is_left_blank(geoapify: respx.Router) -> None:
    """A malformed postcode is dropped rather than half-copied into the ZIP code."""
    result = dict(GEOAPIFY_RESPONSE["results"][0])
    result["postcode"] = "9404"
    geoapify.get(GEOAPIFY_URL).mock(return_value=httpx.Response(200, json={"results": [result]}))

    suggestions = suggest_addresses("1600 Amph")

    assert [suggestion["postal_code"] for suggestion in suggestions] == [""]


def test_an_unknown_state_is_left_blank(geoapify: respx.Router) -> None:
    """A state the profile cannot store leaves the state, and so the county, blank."""
    result = dict(GEOAPIFY_RESPONSE["results"][0])
    result["state_code"] = "ZZ"
    result["state"] = "Nowhere"
    geoapify.get(GEOAPIFY_URL).mock(return_value=httpx.Response(200, json={"results": [result]}))

    suggestions = suggest_addresses("1600 Amph")

    assert [(s["state"], s["county"]) for s in suggestions] == [("", "")]


def test_duplicate_results_are_offered_once(geoapify: respx.Router) -> None:
    """Two results that would fill the same five fields collapse to the first."""
    first = GEOAPIFY_RESPONSE["results"][0]
    geoapify.get(GEOAPIFY_URL).mock(
        return_value=httpx.Response(200, json={"results": [first, dict(first)]})
    )

    suggestions = suggest_addresses("1600 Amph")

    assert len(suggestions) == 1
