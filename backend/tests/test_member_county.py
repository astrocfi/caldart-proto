"""The county filter on the member list and the members report, and the County column.

``?county=`` takes one or more of the California counties a profile stores, separated
by commas, and matches each exactly; the members report reads the same filter, names
the counties in its PDF subtitle, and can carry the county as a column of its own.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.members.filters import EXPORT_FILTER_PARAMS, applied_filters
from apps.members.reports import MEMBER_REPORT_COLUMNS
from tests.conftest import PdfText, read_csv
from tests.factories import MemberProfileFactory, UserFactory

pytestmark = pytest.mark.django_db

LIST_URL = "/api/v1/admin/members"
CSV_URL = "/api/v1/reports/members/export.csv"
PDF_URL = "/api/v1/reports/members/export.pdf"
COOK_REFUSED = {"county": ["Select a valid choice. Cook is not one of the available choices."]}


@pytest.fixture
def county_members() -> dict[str, User]:
    """Four members: two in Napa County, one in Santa Clara, and one with no county."""
    people = {
        "napa": ("napa@example.test", "Napa"),
        "napa_too": ("napa2@example.test", "Napa"),
        "santa_clara": ("sc@example.test", "Santa Clara"),
        "unknown": ("none@example.test", ""),
    }
    users: dict[str, User] = {}
    for key, (email, county) in people.items():
        user = UserFactory(email=email)
        MemberProfileFactory(user=user, county=county)
        users[key] = user
    return users


def listed_emails(client: APIClient, **params: str) -> set[str]:
    """The emails ``GET /admin/members`` answers with for ``params``, on one page."""
    response = client.get(LIST_URL, {**params, "page_size": "100"})
    assert response.status_code == 200
    return {row["email"] for row in response.json()["results"]}


def test_the_list_keeps_the_members_of_one_county(
    account_admin_client: APIClient, county_members: dict[str, User]
) -> None:
    """``?county=Napa`` lists the members whose profile names Napa County, only."""
    assert listed_emails(account_admin_client, county="Napa") == {
        "napa@example.test",
        "napa2@example.test",
    }


def test_the_county_must_match_exactly(
    account_admin_client: APIClient, county_members: dict[str, User]
) -> None:
    """``Santa Clara`` finds Santa Clara County, never a county whose name contains it."""
    MemberProfileFactory(user=UserFactory(email="sb@example.test"), county="Santa Barbara")
    assert listed_emails(account_admin_client, county="Santa Clara") == {"sc@example.test"}


def test_a_county_outside_california_is_refused(
    account_admin_client: APIClient, county_members: dict[str, User]
) -> None:
    """A county that is not one of California's is a 400 naming the refused choice."""
    response = account_admin_client.get(LIST_URL, {"county": "Cook"})
    assert response.status_code == 400
    assert response.json() == COOK_REFUSED


def test_a_blank_county_narrows_nothing(
    account_admin_client: APIClient, county_members: dict[str, User]
) -> None:
    """``?county=`` with no value lists every member, the one with no county included."""
    assert "none@example.test" in listed_emails(account_admin_client, county="")


def test_the_report_keeps_the_members_of_one_county(
    account_admin_client: APIClient, county_members: dict[str, User]
) -> None:
    """The members CSV reads ``?county=`` the way the list does."""
    table = read_csv(account_admin_client.get(CSV_URL, {"county": "Napa", "columns": "email"}))
    assert sorted(row[0] for row in table[1:]) == ["napa2@example.test", "napa@example.test"]


def test_the_report_refuses_a_county_outside_california(
    account_admin_client: APIClient, county_members: dict[str, User]
) -> None:
    """A county the list refuses is refused by the export too, with the same 400 body."""
    response = account_admin_client.get(CSV_URL, {"county": "Cook"})
    assert response.status_code == 400
    assert response.json() == COOK_REFUSED


def test_the_county_is_a_named_report_filter() -> None:
    """``county`` is one of the parameters the report names in its PDF subtitle."""
    assert "county" in EXPORT_FILTER_PARAMS


def test_the_subtitle_names_the_county() -> None:
    """The applied filters carry the county the caller chose."""
    assert applied_filters({"county": "Napa", "dart": ""}) == {"county": "Napa"}


def test_the_county_column_follows_the_state() -> None:
    """``county`` is the column after ``state`` in the report's registry."""
    keys = [column.key for column in MEMBER_REPORT_COLUMNS]
    assert keys.index("county") == keys.index("state") + 1


def test_the_county_column_is_off_by_default() -> None:
    """The County column is offered but not in the default report."""
    column = next(column for column in MEMBER_REPORT_COLUMNS if column.key == "county")
    assert (column.label, column.default, column.width) == ("County", False, 1.8)


def test_the_county_column_prints_the_profile_county(
    account_admin_client: APIClient, county_members: dict[str, User]
) -> None:
    """A member's County cell is the county on their profile, blank when there is none."""
    table = read_csv(account_admin_client.get(CSV_URL, {"columns": "email,county"}))
    counties = dict(table[1:])
    assert counties["sc@example.test"] == "Santa Clara"
    assert counties["none@example.test"] == ""


# -- several counties ----------------------------------------------------------
def test_the_list_keeps_the_members_of_several_counties(
    account_admin_client: APIClient, county_members: dict[str, User]
) -> None:
    """``?county=Napa,Santa Clara`` lists the members of either county."""
    assert listed_emails(account_admin_client, county="Napa,Santa Clara") == {
        "napa@example.test",
        "napa2@example.test",
        "sc@example.test",
    }


def test_one_refused_county_refuses_the_list(
    account_admin_client: APIClient, county_members: dict[str, User]
) -> None:
    """A list naming one county outside California is a 400 naming that county."""
    response = account_admin_client.get(LIST_URL, {"county": "Napa,Cook"})
    assert response.status_code == 400
    assert response.json() == COOK_REFUSED


def test_the_report_keeps_the_members_of_several_counties(
    account_admin_client: APIClient, county_members: dict[str, User]
) -> None:
    """The members CSV reads several counties the way the list does."""
    params = {"county": "Napa,Santa Clara", "columns": "email"}
    table = read_csv(account_admin_client.get(CSV_URL, params))
    assert sorted(row[0] for row in table[1:]) == [
        "napa2@example.test",
        "napa@example.test",
        "sc@example.test",
    ]


def test_the_subtitle_joins_several_counties_with_commas() -> None:
    """The applied filters name each county, separated by a comma and a space."""
    assert applied_filters({"county": "Alameda,Marin"}) == {"county": "Alameda, Marin"}


def test_the_pdf_subtitle_lists_both_counties(
    account_admin_client: APIClient, county_members: dict[str, User], pdf_text: PdfText
) -> None:
    """The PDF prints both counties under its title."""
    body = account_admin_client.get(PDF_URL, {"county": "Alameda,Marin"}).content
    assert pdf_text(body)[0][:2] == ["CalDART membership report", "county: Alameda, Marin"]
