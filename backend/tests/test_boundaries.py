"""The edges of the API's numeric and textual limits.

Page sizes at 25 and 200, an ``expiring_within`` window far outside anything a
date can hold, a string one character over its column, and a name written
outside ASCII.  Each case pins the exact answer the boundary produces, so a
change in the clamp or the limit fails here rather than in production.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.aircraft.models import Aircraft, OwnerType
from apps.aircraft.services import MAX_EXPIRING_WINDOW_DAYS as MAX_AIRCRAFT_WINDOW_DAYS
from apps.members.api.admin_filters import MAX_EXPIRING_WINDOW_DAYS as MAX_MEMBER_WINDOW_DAYS
from apps.members.models import MembershipPlan
from caldart.pagination import StandardPagination
from tests.conftest import read_csv
from tests.factories import AircraftFactory, MemberProfileFactory, MembershipFactory, UserFactory

pytestmark = pytest.mark.django_db

AIRCRAFT_URL = "/api/v1/aircraft"
PROFILE_URL = "/api/v1/me/profile"
MEMBERS_URL = "/api/v1/admin/members"
MEMBERS_CSV_URL = "/api/v1/admin/members/export.csv"

#: One more row than a full page, so the second page holds exactly one.
OVER_A_PAGE = StandardPagination.page_size + 1

#: One more row than the largest page anyone may ask for.
OVER_THE_CAP = StandardPagination.max_page_size + 1

#: A window so wide that ``today + timedelta(days=...)`` would raise
#: ``OverflowError`` if the filter passed it through unclamped.
ABSURD_WINDOW = 10**12


def make_register(count: int, *, expires_in_days: int = 200) -> None:
    """Insert ``count`` aircraft whose cover runs out ``expires_in_days`` from today."""
    expiration = timezone.localdate() + timedelta(days=expires_in_days)
    Aircraft.objects.bulk_create(
        Aircraft(
            n_number=f"N{9000 + index}B",
            make="Cessna",
            model="172S",
            owner_type=OwnerType.INDIVIDUAL,
            seats=4,
            insurance_expiration=expiration,
            is_active=True,
        )
        for index in range(count)
    )


# --------------------------------------------------------------------------
# Page size: 25 by default, 200 at most
# --------------------------------------------------------------------------
def test_a_list_returns_twenty_five_rows_by_default(
    api_client: APIClient, member: User, aircraft: Aircraft
) -> None:
    """With more rows than fit, a page carries 25 of them and points at the next."""
    make_register(OVER_A_PAGE - 1)
    api_client.force_login(member)

    body = api_client.get(AIRCRAFT_URL).json()

    assert body["count"] == OVER_A_PAGE
    assert len(body["results"]) == 25
    assert body["next"] == "http://testserver/api/v1/aircraft?page=2"


def test_the_last_page_carries_the_remainder(
    api_client: APIClient, member: User, aircraft: Aircraft
) -> None:
    """The page after a full one holds the single row that did not fit."""
    make_register(OVER_A_PAGE - 1)
    api_client.force_login(member)

    body = api_client.get(AIRCRAFT_URL, {"page": 2}).json()

    assert len(body["results"]) == 1
    assert body["next"] is None


def test_page_size_two_hundred_is_served_in_full(api_client: APIClient, member: User) -> None:
    """``page_size=200`` is the largest page the API serves, and it serves all of it."""
    make_register(OVER_THE_CAP)
    api_client.force_login(member)

    body = api_client.get(AIRCRAFT_URL, {"page_size": 200}).json()

    assert body["count"] == OVER_THE_CAP
    assert len(body["results"]) == 200


def test_a_page_size_above_the_cap_is_clamped(api_client: APIClient, member: User) -> None:
    """A page size beyond 200 is answered with 200 rows rather than refused."""
    make_register(OVER_THE_CAP)
    api_client.force_login(member)

    body = api_client.get(AIRCRAFT_URL, {"page_size": 5000}).json()

    assert body["count"] == OVER_THE_CAP
    assert len(body["results"]) == 200


@pytest.mark.parametrize(
    "page_size", ["0", "-10", "many"], ids=["zero", "negative", "not-a-number"]
)
def test_an_unusable_page_size_falls_back_to_the_default(
    api_client: APIClient, member: User, aircraft: Aircraft, page_size: str
) -> None:
    """A page size of zero, a negative one or a word is answered with the default 25."""
    make_register(OVER_A_PAGE - 1)
    api_client.force_login(member)

    body = api_client.get(AIRCRAFT_URL, {"page_size": page_size}).json()

    assert len(body["results"]) == 25


def test_a_page_past_the_end_is_refused(
    api_client: APIClient, member: User, aircraft: Aircraft
) -> None:
    """Asking for a page that does not exist is a 404, not an empty list."""
    api_client.force_login(member)

    response = api_client.get(AIRCRAFT_URL, {"page": 99})

    assert response.status_code == 404
    assert response.json() == {"detail": "Invalid page."}


# --------------------------------------------------------------------------
# expiring_within: clamped to 0..3650 days
# --------------------------------------------------------------------------
def test_an_absurd_aircraft_window_is_clamped_to_ten_years(
    api_client: APIClient, member: User
) -> None:
    """A window wider than a date can hold lists cover inside 3650 days and no more."""
    AircraftFactory(
        n_number="N1INSIDE",
        insurance_expiration=timezone.localdate() + timedelta(days=MAX_AIRCRAFT_WINDOW_DAYS),
    )
    AircraftFactory(
        n_number="N2BEYOND",
        insurance_expiration=timezone.localdate() + timedelta(days=MAX_AIRCRAFT_WINDOW_DAYS + 1),
    )
    api_client.force_login(member)

    body = api_client.get(AIRCRAFT_URL, {"expiring_within": ABSURD_WINDOW}).json()

    assert [row["n_number"] for row in body["results"]] == ["N1INSIDE"]


def test_a_negative_aircraft_window_reaches_only_today(api_client: APIClient, member: User) -> None:
    """A negative window is clamped to zero: only cover that runs out today is listed."""
    AircraftFactory(n_number="N3TODAY", insurance_expiration=timezone.localdate())
    AircraftFactory(
        n_number="N4LATER",
        insurance_expiration=timezone.localdate() + timedelta(days=1),
    )
    api_client.force_login(member)

    body = api_client.get(AIRCRAFT_URL, {"expiring_within": -30}).json()

    assert [row["n_number"] for row in body["results"]] == ["N3TODAY"]


def test_an_absurd_membership_window_is_clamped_to_ten_years(
    api_client: APIClient, account_admin: User, annual_plan: MembershipPlan
) -> None:
    """The member list answers an impossible window with the members inside 3650 days."""
    yesterday = timezone.localdate() - timedelta(days=1)
    edge = UserFactory(email="edge@example.test", first_name="Edge", last_name="Case")
    MembershipFactory(
        user=edge,
        plan=annual_plan,
        starts_on=yesterday,
        ends_on=timezone.localdate() + timedelta(days=MAX_MEMBER_WINDOW_DAYS),
    )
    soon = UserFactory(email="soon@example.test", first_name="Soon", last_name="Lapsing")
    MembershipFactory(
        user=soon,
        plan=annual_plan,
        starts_on=yesterday,
        ends_on=timezone.localdate() + timedelta(days=10),
    )
    far = UserFactory(email="far@example.test", first_name="Far", last_name="Off")
    MembershipFactory(
        user=far,
        plan=annual_plan,
        starts_on=yesterday,
        ends_on=timezone.localdate() + timedelta(days=MAX_MEMBER_WINDOW_DAYS + 1),
    )
    api_client.force_login(account_admin)

    response = api_client.get(MEMBERS_URL, {"expiring_within": ABSURD_WINDOW})

    assert response.status_code == 200
    assert [row["email"] for row in response.json()["results"]] == [
        "edge@example.test",
        "soon@example.test",
    ]


# --------------------------------------------------------------------------
# Column limits
# --------------------------------------------------------------------------
def test_a_make_of_exactly_sixty_characters_is_stored(api_client: APIClient, member: User) -> None:
    """A make filling the column exactly is accepted and comes back unchanged."""
    api_client.force_login(member)
    make = "C" * 60

    response = api_client.post(
        AIRCRAFT_URL, {"n_number": "N60EX", "make": make, "model": "172S"}, format="json"
    )

    assert response.status_code == 201
    assert response.json()["make"] == make


def test_a_make_one_character_too_long_is_refused(api_client: APIClient, member: User) -> None:
    """A make past the column length is a 400 naming the field and the limit."""
    api_client.force_login(member)

    response = api_client.post(
        AIRCRAFT_URL, {"n_number": "N61L", "make": "C" * 61, "model": "172S"}, format="json"
    )

    assert response.status_code == 400
    assert response.json() == {"make": ["Ensure this field has no more than 60 characters."]}


def test_a_phone_of_more_than_ten_digits_is_refused(api_client: APIClient, member: User) -> None:
    """A number that is not ten digits is a 400 naming the field."""
    MemberProfileFactory(user=member)
    api_client.force_login(member)

    response = api_client.patch(PROFILE_URL, {"phone": "5" * 13}, format="json")

    assert response.status_code == 400
    assert response.json() == {"phone": ["Use a ten-digit number like 415-555-0100."]}


def test_a_phone_typed_any_way_is_stored_in_one_shape(api_client: APIClient, member: User) -> None:
    """Ten digits reach the column however they were punctuated."""
    MemberProfileFactory(user=member)
    api_client.force_login(member)

    response = api_client.patch(PROFILE_URL, {"phone": "+1 (415) 555.0100"}, format="json")

    assert response.status_code == 200
    assert response.json()["phone"] == "415-555-0100"


# --------------------------------------------------------------------------
# Names outside ASCII
# --------------------------------------------------------------------------
#: A name carrying diacritics and a non-Latin script, to catch a narrow encoding
#: anywhere between the database and the download.  Written as escapes because
#: every ``.py`` file in the backend stays ASCII.
NON_ASCII_FIRST_NAME = "Ana Sof\u00eda"

#: The surname, whose first five characters are the accented spelling the search
#: test looks the member up by.
NON_ASCII_LAST_NAME = "N\u00fa\u00f1ez-\u5c0f\u6797"

NON_ASCII_NAME = f"{NON_ASCII_FIRST_NAME} {NON_ASCII_LAST_NAME}"


@pytest.fixture
def non_ascii_member(annual_plan: MembershipPlan) -> User:
    """A current member whose name is written with diacritics and a non-Latin script."""
    user = UserFactory(
        email="sofia@example.test",
        first_name=NON_ASCII_FIRST_NAME,
        last_name=NON_ASCII_LAST_NAME,
    )
    MemberProfileFactory(user=user, phone="415-555-0100")
    MembershipFactory(
        user=user,
        plan=annual_plan,
        starts_on=timezone.localdate() - timedelta(days=10),
        ends_on=timezone.localdate() + timedelta(days=354),
    )
    return user


def test_a_non_ascii_name_is_served_unchanged(
    api_client: APIClient, account_admin: User, non_ascii_member: User
) -> None:
    """The member list returns a name outside ASCII exactly as it was stored."""
    api_client.force_login(account_admin)

    body = api_client.get(MEMBERS_URL, {"search": "sofia@example.test"}).json()

    assert body["results"][0]["name"] == NON_ASCII_NAME


def test_a_non_ascii_name_survives_the_csv_export(
    api_client: APIClient, account_admin: User, non_ascii_member: User
) -> None:
    """The export writes a name outside ASCII as UTF-8, character for character."""
    api_client.force_login(account_admin)

    rows = read_csv(api_client.get(MEMBERS_CSV_URL, {"search": "sofia@example.test"}))

    assert rows[1][0] == NON_ASCII_NAME


def test_a_non_ascii_name_is_found_by_its_accented_spelling(
    api_client: APIClient, account_admin: User, non_ascii_member: User
) -> None:
    """Searching the accented surname finds the member it belongs to."""
    api_client.force_login(account_admin)

    body = api_client.get(MEMBERS_URL, {"search": NON_ASCII_LAST_NAME[:5]}).json()

    assert [row["email"] for row in body["results"]] == ["sofia@example.test"]
