"""The member list's kind selector, deactivated accounts, and donors.

``GET /admin/members`` takes ``?kind=member`` or ``?kind=friend`` (absent means both),
hides deactivated accounts unless ``?include_inactive=true``, and never lists a donor.
The members report, the DART rosters, and the DART leader's member check never
include a deactivated account or a donor, whatever the caller asks for.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import AccountKind, User
from apps.accounts.roles import MEMBER
from apps.aircraft.services import aircraft_pilots, search_members
from apps.members.filters import EXPORT_FILTER_PARAMS, applied_filters
from apps.members.models import MembershipPlan
from tests.conftest import read_csv
from tests.factories import (
    AircraftFactory,
    MemberProfileFactory,
    MembershipFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db

LIST_URL = "/api/v1/admin/members"
CSV_URL = "/api/v1/reports/members/export.csv"
SEARCH_URL = "/api/v1/leader/search"


@pytest.fixture
def people(annual_plan: MembershipPlan) -> dict[str, User]:
    """A current member, a friend, a pending friend, a deactivated member, and a donor.

    Every one of them has the surname Quill and flies N55LF, so one search and one
    aircraft find them all.
    """
    today = timezone.localdate()
    plane = AircraftFactory(n_number="N55LF")
    specs = {
        "member": {"email": "member@lf.test", "first_name": "Mia"},
        "friend": {"email": "friend@lf.test", "first_name": "Fay", "kind": AccountKind.FRIEND},
        "pending": {
            "email": "pending@lf.test",
            "first_name": "Pat",
            "friend_on": today + timedelta(days=30),
        },
        "inactive": {"email": "inactive@lf.test", "first_name": "Ian", "is_active": False},
        "donor": {"email": "donor@lf.test", "first_name": "Dee", "kind": AccountKind.DONOR},
    }
    users: dict[str, User] = {}
    for key, fields in specs.items():
        roles = [] if key == "donor" else [MEMBER]
        user = UserFactory(last_name="Quill", roles=roles, **fields)
        MemberProfileFactory(user=user).aircraft.add(plane)
        if key != "friend":
            MembershipFactory(user=user, plan=annual_plan, starts_on=today - timedelta(days=10))
        users[key] = user
    return users


def listed(client: APIClient, **params: str) -> set[str]:
    """The emails ``GET /admin/members`` answers with for ``params``, from one page."""
    response = client.get(LIST_URL, {"search": "Quill", **params, "page_size": "100"})
    assert response.status_code == 200, response.content
    return {row["email"] for row in response.json()["results"]}


def reported(client: APIClient, **params: str) -> set[str]:
    """The emails the members CSV lists for ``params``."""
    response = client.get(CSV_URL, {"search": "Quill", "columns": "email", **params})
    assert response.status_code == 200, response.content
    return {row[0] for row in read_csv(response)[1:]}


# -- the kind selector ----------------------------------------------------------
def test_no_kind_lists_members_and_friends(
    account_admin_client: APIClient, people: dict[str, User]
) -> None:
    """With no ``kind``, the list holds every active member and friend."""
    assert listed(account_admin_client) == {"member@lf.test", "friend@lf.test", "pending@lf.test"}


def test_kind_member_lists_members_only(
    account_admin_client: APIClient, people: dict[str, User]
) -> None:
    """``?kind=member`` keeps the members, a member with a pending change among them."""
    assert listed(account_admin_client, kind="member") == {"member@lf.test", "pending@lf.test"}


def test_kind_friend_lists_friends_only(
    account_admin_client: APIClient, people: dict[str, User]
) -> None:
    """``?kind=friend`` keeps the friends."""
    assert listed(account_admin_client, kind="friend") == {"friend@lf.test"}


def test_kind_friend_includes_a_member_whose_change_has_come(
    account_admin_client: APIClient, people: dict[str, User]
) -> None:
    """A member whose ``friend_on`` has arrived is a friend to the selector."""
    pending = people["pending"]
    pending.friend_on = timezone.localdate()
    pending.save(update_fields=["friend_on"])
    assert listed(account_admin_client, kind="friend") == {"friend@lf.test", "pending@lf.test"}


def test_a_blank_kind_narrows_nothing(
    account_admin_client: APIClient, people: dict[str, User]
) -> None:
    """``?kind=`` with no value is the same as no ``kind`` at all."""
    assert listed(account_admin_client, kind="") == listed(account_admin_client)


@pytest.mark.parametrize("kind", ["donor", "pilot"])
def test_any_other_kind_is_refused(
    account_admin_client: APIClient, people: dict[str, User], kind: str
) -> None:
    """A kind other than ``member`` or ``friend`` is a 400 naming the refused choice."""
    response = account_admin_client.get(LIST_URL, {"kind": kind})
    assert response.status_code == 400
    assert response.json() == {
        "kind": [f"Select a valid choice. {kind} is not one of the available choices."]
    }


def test_each_row_carries_its_kind(
    account_admin_client: APIClient, people: dict[str, User]
) -> None:
    """Every row names its stored kind."""
    response = account_admin_client.get(LIST_URL, {"search": "Quill"})
    kinds = {row["email"]: row["kind"] for row in response.json()["results"]}
    assert kinds == {"member@lf.test": "member", "friend@lf.test": "friend", "pending@lf.test": "member"}


# -- deactivated accounts and donors on the list ----------------------------------
def test_the_list_hides_a_deactivated_account(
    account_admin_client: APIClient, people: dict[str, User]
) -> None:
    """A deactivated account is left out unless the caller asks for it."""
    assert "inactive@lf.test" not in listed(account_admin_client)


def test_include_inactive_brings_a_deactivated_account_back(
    account_admin_client: APIClient, people: dict[str, User]
) -> None:
    """``?include_inactive=true`` lists the deactivated account beside the active ones."""
    assert listed(account_admin_client, include_inactive="true") == {
        "member@lf.test",
        "friend@lf.test",
        "pending@lf.test",
        "inactive@lf.test",
    }


def test_include_inactive_false_hides_a_deactivated_account(
    account_admin_client: APIClient, people: dict[str, User]
) -> None:
    """``?include_inactive=false`` reads the same as leaving it out."""
    assert "inactive@lf.test" not in listed(account_admin_client, include_inactive="false")


def test_the_list_never_lists_a_donor(
    account_admin_client: APIClient, people: dict[str, User]
) -> None:
    """A donor is left out whatever the filters, deactivated accounts included."""
    assert "donor@lf.test" not in listed(account_admin_client, include_inactive="true")


def test_a_donor_has_no_member_record(
    account_admin_client: APIClient, people: dict[str, User]
) -> None:
    """``GET /admin/members/{id}`` is a 404 for a donor."""
    response = account_admin_client.get(f"{LIST_URL}/{people['donor'].pk}")
    assert response.status_code == 404


def test_a_deactivated_account_keeps_its_member_record(
    account_admin_client: APIClient, people: dict[str, User]
) -> None:
    """The member record of a deactivated account still opens, to reactivate it."""
    response = account_admin_client.get(f"{LIST_URL}/{people['inactive'].pk}")
    assert response.status_code == 200


def test_is_active_is_no_longer_a_filter(
    account_admin_client: APIClient, people: dict[str, User]
) -> None:
    """``?is_active=false`` narrows nothing: ``include_inactive`` is the one switch."""
    assert "inactive@lf.test" not in listed(account_admin_client, is_active="false")


# -- the report ------------------------------------------------------------------
def test_the_report_leaves_out_deactivated_accounts_and_donors(
    account_admin_client: APIClient, people: dict[str, User]
) -> None:
    """The members report lists every active member and friend, and nobody else."""
    assert reported(account_admin_client) == {
        "member@lf.test",
        "friend@lf.test",
        "pending@lf.test",
    }


def test_the_report_ignores_include_inactive(
    account_admin_client: APIClient, people: dict[str, User]
) -> None:
    """``include_inactive`` does not bring a deactivated account into the report."""
    assert "inactive@lf.test" not in reported(account_admin_client, include_inactive="true")


def test_the_report_reads_the_kind_selector(
    account_admin_client: APIClient, people: dict[str, User]
) -> None:
    """``?kind=friend`` narrows the report as it narrows the list."""
    assert reported(account_admin_client, kind="friend") == {"friend@lf.test"}


def test_the_kind_is_a_named_report_filter() -> None:
    """``kind`` is one of the parameters the report names in its PDF subtitle."""
    assert "kind" in EXPORT_FILTER_PARAMS


def test_include_inactive_is_not_a_named_report_filter() -> None:
    """The report never includes a deactivated account, so its subtitle never says so."""
    assert applied_filters({"include_inactive": "true", "kind": "friend"}) == {"kind": "friend"}


# -- the leader's member check ---------------------------------------------------
def test_the_member_search_leaves_out_deactivated_accounts_and_donors(
    people: dict[str, User],
) -> None:
    """``search_members`` finds only active members and friends."""
    assert {user.email for user in search_members("Quill")} == {
        "member@lf.test",
        "friend@lf.test",
        "pending@lf.test",
    }


def test_the_leader_search_endpoint_leaves_them_out_too(
    api_client: APIClient, dart_leader: User, people: dict[str, User]
) -> None:
    """``GET /leader/search`` never answers with a deactivated account or a donor."""
    api_client.force_login(dart_leader)
    rows = api_client.get(SEARCH_URL, {"q": "Quill"}).json()
    assert {row["email"] for row in rows} == {
        "member@lf.test",
        "friend@lf.test",
        "pending@lf.test",
    }


@pytest.mark.parametrize("key", ["inactive", "donor"])
def test_the_status_card_is_a_404_for_them(
    api_client: APIClient, dart_leader: User, people: dict[str, User], key: str
) -> None:
    """The status card of a deactivated account or a donor is a 404."""
    api_client.force_login(dart_leader)
    response = api_client.get(f"/api/v1/leader/members/{people[key].pk}/status")
    assert response.status_code == 404


def test_the_pilots_of_an_aircraft_leave_them_out(people: dict[str, User]) -> None:
    """``aircraft_pilots`` lists only the active members and friends who fly it."""
    plane = people["member"].profile.aircraft.get()
    assert {row["email"] for row in aircraft_pilots(plane)} == {
        "member@lf.test",
        "friend@lf.test",
        "pending@lf.test",
    }
