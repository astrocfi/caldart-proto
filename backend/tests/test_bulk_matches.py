"""The search on the compose screen: who the filters choose, before anybody is added.

``GET /bulk-email/{id}/batch/matches`` runs the member list's filters as an add would,
pages the people they choose, and says whether each would receive a copy.  It stores
nothing.  A DART leader's email is held to the leader's DART, and the ``dart`` filter
takes several DARTs as a list of ids.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import AccountKind
from apps.bulk_email.models import BatchAdd, BulkEmail
from apps.bulk_email.senders import NOT_YOUR_DART_MESSAGE
from tests.factories import (
    BulkEmailFactory,
    DartFactory,
    add_to_batch,
    make_dart_leader,
    make_person,
)

if TYPE_CHECKING:
    from apps.accounts.models import User
    from apps.darts.models import Dart

pytestmark = pytest.mark.django_db

#: Everybody the fixtures make lives here, and nobody else does.
SONOMA = "Sonoma"


def matches_url(bulk: BulkEmail) -> str:
    """``/api/v1/bulk-email/{id}/batch/matches`` for ``bulk``."""
    return f"/api/v1/bulk-email/{bulk.pk}/batch/matches"


def addresses(body: dict[str, list[dict[str, str]]]) -> list[str]:
    """The addresses of one page of matches, in order."""
    return [row["email"] for row in body["results"]]


@pytest.fixture
def marin() -> Dart:
    """The Marin DART."""
    return DartFactory(name="Marin DART")


@pytest.fixture
def napa() -> Dart:
    """The Napa DART."""
    return DartFactory(name="Napa DART")


@pytest.fixture
def solano() -> Dart:
    """The Solano DART."""
    return DartFactory(name="Solano DART")


@pytest.fixture
def people(marin: Dart, napa: Dart, solano: Dart) -> dict[str, User]:
    """One person in each DART, all in Sonoma, by first name."""
    return {
        "ann": make_person("ann@example.test", "Ann", "Able", county=SONOMA, dart=marin),
        "nat": make_person("nat@example.test", "Nat", "Neal", county=SONOMA, dart=napa),
        "sol": make_person("sol@example.test", "Sol", "Stone", county=SONOMA, dart=solano),
    }


@pytest.fixture
def bulk(management: User) -> BulkEmail:
    """A draft from CalDART management with an empty batch."""
    return BulkEmailFactory(sender=management)


def test_the_matches_are_the_people_the_filters_choose_in_surname_order(
    management_client: APIClient, bulk: BulkEmail, people: dict[str, User]
) -> None:
    """Every person in the county comes back, by surname."""
    body = management_client.get(matches_url(bulk), {"county": SONOMA}).json()
    assert addresses(body) == ["ann@example.test", "nat@example.test", "sol@example.test"]


def test_the_matches_carry_a_count_of_everybody_across_pages(
    management_client: APIClient, bulk: BulkEmail, people: dict[str, User]
) -> None:
    """A page of two still counts all three."""
    body = management_client.get(matches_url(bulk), {"county": SONOMA, "page_size": "2"}).json()
    assert (body["count"], len(body["results"])) == (3, 2)


def test_a_match_carries_what_a_batch_row_says(
    management_client: APIClient, bulk: BulkEmail, people: dict[str, User]
) -> None:
    """Name, address, kind, DART, and whether a copy would go."""
    body = management_client.get(matches_url(bulk), {"search": "ann@example.test"}).json()
    assert body["results"] == [
        {
            "user_id": people["ann"].pk,
            "name": "Ann Able",
            "email": "ann@example.test",
            "kind": "member",
            "dart_name": "Marin DART",
            "will_receive": True,
            "reason": "",
        }
    ]


def test_a_match_who_would_be_skipped_says_why(
    management_client: APIClient, bulk: BulkEmail, people: dict[str, User]
) -> None:
    """A deactivated account matches, as on an add, and would be sent no copy."""
    people["nat"].is_active = False
    people["nat"].save()
    body = management_client.get(matches_url(bulk), {"search": "nat@example.test"}).json()
    assert [(row["will_receive"], row["reason"]) for row in body["results"]] == [
        (False, "Account deactivated")
    ]


def test_searching_stores_nothing(
    management_client: APIClient, bulk: BulkEmail, people: dict[str, User]
) -> None:
    """No add is recorded and the batch stays empty."""
    management_client.get(matches_url(bulk), {"county": SONOMA})
    assert (BatchAdd.objects.filter(bulk_email=bulk).count(), bulk.recipients.count()) == (0, 0)


def test_people_in_the_batch_already_still_match(
    management_client: APIClient, bulk: BulkEmail, people: dict[str, User]
) -> None:
    """The search shows who the filters choose, whoever is in the batch."""
    add_to_batch(bulk, people["ann"])
    body = management_client.get(matches_url(bulk), {"search": "ann@example.test"}).json()
    assert body["count"] == 1


def test_a_filter_the_member_list_does_not_have_is_refused(
    management_client: APIClient, bulk: BulkEmail
) -> None:
    """400 keyed ``filters`` then the filter."""
    response = management_client.get(matches_url(bulk), {"color": "red"})
    assert response.status_code == 400
    assert list(response.json()["filters"]) == ["color"]


def test_a_value_the_member_list_refuses_is_refused(
    management_client: APIClient, bulk: BulkEmail
) -> None:
    """A county the list does not know is a 400 keyed ``filters`` then ``county``."""
    response = management_client.get(matches_url(bulk), {"county": "Atlantis"})
    assert response.status_code == 400
    assert list(response.json()["filters"]) == ["county"]


def test_a_member_cannot_search(api_client: APIClient, member: User, bulk: BulkEmail) -> None:
    """The endpoint is a bulk sender's."""
    api_client.force_login(member)
    assert api_client.get(matches_url(bulk)).status_code == 403


# --------------------------------------------------------------------------
# Several DARTs
# --------------------------------------------------------------------------
def test_the_dart_filter_takes_several_darts(
    management_client: APIClient,
    bulk: BulkEmail,
    people: dict[str, User],
    marin: Dart,
    solano: Dart,
) -> None:
    """A list of ids chooses the people of every DART on it."""
    body = management_client.get(matches_url(bulk), {"dart": f"{marin.pk},{solano.pk}"}).json()
    assert addresses(body) == ["ann@example.test", "sol@example.test"]


def test_an_add_takes_several_darts_and_names_them(
    management_client: APIClient,
    bulk: BulkEmail,
    people: dict[str, User],
    marin: Dart,
    napa: Dart,
) -> None:
    """The add's label names each DART."""
    management_client.post(
        f"/api/v1/bulk-email/{bulk.pk}/batch/add",
        {"filters": {"dart": f"{marin.pk},{napa.pk}"}},
        format="json",
    )
    adds = management_client.get(f"/api/v1/bulk-email/{bulk.pk}/batch").json()["adds"]
    assert [add["label"] for add in adds] == ["DART: Marin DART, Napa DART"]


def test_the_member_list_takes_several_darts(
    account_admin_client: APIClient, people: dict[str, User], marin: Dart, napa: Dart
) -> None:
    """The member list's own ``dart`` filter reads the same list of ids."""
    body = account_admin_client.get(
        "/api/v1/admin/members", {"dart": f"{marin.pk},{napa.pk}"}
    ).json()
    assert sorted(row["email"] for row in body["results"]) == [
        "ann@example.test",
        "nat@example.test",
    ]


def test_the_member_list_still_takes_part_of_a_dart_name(
    account_admin_client: APIClient, people: dict[str, User]
) -> None:
    """A value that is not a list of ids is part of one DART's name."""
    body = account_admin_client.get("/api/v1/admin/members", {"dart": "napa"}).json()
    assert [row["email"] for row in body["results"]] == ["nat@example.test"]


# --------------------------------------------------------------------------
# A DART leader's search
# --------------------------------------------------------------------------
@pytest.fixture
def leader(marin: Dart) -> User:
    """The Marin DART's leader, in another county than the people."""
    return make_dart_leader("lane@example.test", marin)


@pytest.fixture
def leader_client(api_client: APIClient, leader: User) -> APIClient:
    """An API client signed in as the Marin DART's leader."""
    api_client.force_login(leader)
    return api_client


@pytest.fixture
def leader_draft(leader: User, marin: Dart) -> BulkEmail:
    """The Marin leader's draft, with an empty batch."""
    return BulkEmailFactory(sender=leader, dart=marin)


def test_a_leaders_search_is_held_to_their_dart(
    leader_client: APIClient, leader_draft: BulkEmail, people: dict[str, User]
) -> None:
    """Of three people in the county, only the Marin one matches."""
    body = leader_client.get(matches_url(leader_draft), {"county": SONOMA}).json()
    assert addresses(body) == ["ann@example.test"]


def test_a_leaders_search_naming_other_darts_is_refused(
    leader_client: APIClient,
    leader_draft: BulkEmail,
    people: dict[str, User],
    marin: Dart,
    napa: Dart,
) -> None:
    """Several DARTs, their own among them, are still another DART: 400."""
    response = leader_client.get(matches_url(leader_draft), {"dart": f"{marin.pk},{napa.pk}"})
    assert response.status_code == 400
    assert response.json() == {"filters": {"dart": [NOT_YOUR_DART_MESSAGE]}}


def test_a_leader_with_no_dart_cannot_search(
    leader_client: APIClient, leader_draft: BulkEmail, leader: User
) -> None:
    """Their profile names no DART, so nobody matches: 409."""
    leader.profile.dart = None
    leader.profile.save()
    response = leader_client.get(matches_url(leader_draft))
    assert response.status_code == 409


def test_a_friend_matches_with_their_kind(
    management_client: APIClient, bulk: BulkEmail, marin: Dart
) -> None:
    """A friend is listed as a friend."""
    make_person(
        "fay@example.test", "Fay", "Fern", county=SONOMA, dart=marin, kind=AccountKind.FRIEND
    )
    body = management_client.get(matches_url(bulk), {"search": "fay@example.test"}).json()
    assert [row["kind"] for row in body["results"]] == ["friend"]
