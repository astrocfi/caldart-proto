"""``GET /aircraft/registrations?q=``: the N-number typeahead's prefix search.

``docs/developer/api-aircraft.rst`` is the contract.  The tests read the registry
fixture, imported as the seed imports it.
"""

from __future__ import annotations

import pytest
from django.db import connection
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.aircraft.models import Registration, RegistryImport
from apps.aircraft.registry import FIXTURE_DIR, import_registry

pytestmark = pytest.mark.django_db

SEARCH_URL = "/api/v1/aircraft/registrations"

#: A prefix the fixture holds more than eight registrations under.
BROAD_PREFIX = "N1"

#: The fixture's registrations under ``N128S``: the Cessna 172S the lookup tests read.
NARROW_MATCHES = ["N128SC"]


@pytest.fixture
def registry() -> RegistryImport:
    """The fixture registry, imported as the seed imports it."""
    return import_registry(str(FIXTURE_DIR))


@pytest.fixture
def member_client(api_client: APIClient, member: User) -> APIClient:
    """A client signed in as a plain member."""
    api_client.force_login(member)
    return api_client


def _found(client: APIClient, query: str) -> list[str]:
    """The N-numbers ``GET /aircraft/registrations?q=<query>`` answers, in order."""
    return [row["n_number"] for row in client.get(SEARCH_URL, {"q": query}).json()]


def test_the_fixture_holds_more_than_eight_under_the_broad_prefix(
    registry: RegistryImport,
) -> None:
    """The cap test below needs a prefix with more matches than the cap."""
    assert Registration.objects.filter(n_number__startswith=BROAD_PREFIX).count() > 8


def test_a_search_answers_at_most_eight_in_n_number_order(
    registry: RegistryImport, member_client: APIClient
) -> None:
    """A broad prefix answers the first eight of its registrations by N-number."""
    every = sorted(
        Registration.objects.filter(n_number__startswith=BROAD_PREFIX).values_list(
            "n_number", flat=True
        )
    )
    assert _found(member_client, BROAD_PREFIX) == every[:8]


@pytest.mark.parametrize(
    "typed",
    ["N128S", "128S", "n128s", "128s", "n-128 s"],
    ids=["as-written", "no-leading-n", "lower-case", "lower-case-no-n", "punctuated"],
)
def test_the_query_is_normalized_like_an_n_number(
    registry: RegistryImport, member_client: APIClient, typed: str
) -> None:
    """The leading N is optional, and case and punctuation do not matter."""
    assert _found(member_client, typed) == NARROW_MATCHES


def test_each_match_is_shaped_like_the_exact_lookup(
    registry: RegistryImport, member_client: APIClient
) -> None:
    """A match carries the same fields ``GET /aircraft/registry/{n_number}`` answers."""
    match = member_client.get(SEARCH_URL, {"q": "N128S"}).json()[0]
    lookup = member_client.get("/api/v1/aircraft/registry/N128SC").json()
    assert match == lookup


@pytest.mark.parametrize("typed", ["", " ", "N", "n", "-"])
def test_a_query_shorter_than_two_characters_answers_an_empty_list(
    registry: RegistryImport, member_client: APIClient, typed: str
) -> None:
    """Fewer than two characters after normalizing answers ``200 []``, not an error."""
    response = member_client.get(SEARCH_URL, {"q": typed})
    assert (response.status_code, response.json()) == (200, [])


def test_a_missing_query_answers_an_empty_list(member_client: APIClient) -> None:
    """No ``q`` at all is a blank query."""
    response = member_client.get(SEARCH_URL)
    assert (response.status_code, response.json()) == (200, [])


def test_a_prefix_nothing_starts_with_answers_an_empty_list(
    registry: RegistryImport, member_client: APIClient
) -> None:
    """A prefix no registration starts with answers ``[]``."""
    assert _found(member_client, "N99999ZZ") == []


def test_searching_needs_a_signed_in_user(api_client: APIClient) -> None:
    """An anonymous caller is refused."""
    assert api_client.get(SEARCH_URL, {"q": "N1"}).status_code == 401


def test_a_pattern_ops_index_serves_the_registrations_n_number_prefix() -> None:
    """Django's ``_like`` index on the unique ``n_number`` uses ``varchar_pattern_ops``.

    A ``LIKE 'N17%'`` prefix match cannot use a plain B-tree under a non-C collation;
    the operator class compares character by character, so the typeahead's query can.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT indexdef FROM pg_indexes WHERE tablename = %s AND indexdef LIKE %s",
            [Registration._meta.db_table, "%(n_number varchar_pattern_ops)%"],
        )
        rows = cursor.fetchall()
    assert len(rows) == 1
