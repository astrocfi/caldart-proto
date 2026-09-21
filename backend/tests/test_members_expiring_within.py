"""The members admin ``expiring_within`` filter clamps its window.

A window past ``MAX_EXPIRING_WINDOW_DAYS`` or below zero must never reach
``date + timedelta(days=...)`` unclamped: Python's ``date`` overflows past the
year 9999 and turns an oversized query into a 500.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.members.api.admin_filters import MAX_EXPIRING_WINDOW_DAYS
from apps.members.models import MembershipPlan
from tests.factories import MembershipFactory

if TYPE_CHECKING:
    # rest_framework.test.APIClient.get() is typed to return this class, but it
    # exists only in the stub: rest_framework monkey-patches Django's test response
    # at runtime rather than defining a real subclass.
    from rest_framework.response import _MonkeyPatchedResponse as ApiResponse

pytestmark = pytest.mark.django_db

LIST_URL = "/api/v1/admin/members"


@pytest.fixture
def admin_client(api_client: APIClient, account_admin: User) -> APIClient:
    """A DRF client logged in as an account admin, who may list members."""
    api_client.force_login(account_admin)
    return api_client


@pytest.fixture
def expiring_member(annual_plan: MembershipPlan, today: date) -> User:
    """A current member whose coverage ends 30 days out."""
    assert annual_plan.duration_days is not None
    day = timedelta(days=1)
    membership = MembershipFactory(
        plan=annual_plan,
        starts_on=today - (annual_plan.duration_days - 30) * day,
        ends_on=today + 30 * day,
    )
    return membership.user


@pytest.fixture
def last_day_member(annual_plan: MembershipPlan, today: date) -> User:
    """A current member whose coverage ends today, the one match a zero-day window has."""
    assert annual_plan.duration_days is not None
    day = timedelta(days=1)
    membership = MembershipFactory(
        plan=annual_plan,
        starts_on=today - (annual_plan.duration_days - 1) * day,
        ends_on=today,
    )
    return membership.user


def emails(response: ApiResponse) -> set[str]:
    """Return the set of ``email`` values in a paginated member list response."""
    return {row["email"] for row in response.json()["results"]}


@pytest.mark.parametrize("window", ["999999999", "1e11"])
def test_expiring_within_survives_an_absurd_window(
    admin_client: APIClient, expiring_member: User, window: str
) -> None:
    """An overflowing timedelta would be a 500, not a filter."""
    response = admin_client.get(LIST_URL, {"expiring_within": window})
    assert response.status_code == 200


def test_expiring_within_huge_value_is_clamped_to_the_limit(
    admin_client: APIClient, expiring_member: User
) -> None:
    """A window far past the limit returns the same results as the limit itself."""
    huge = emails(admin_client.get(LIST_URL, {"expiring_within": "3000000"}))
    limit = emails(admin_client.get(LIST_URL, {"expiring_within": MAX_EXPIRING_WINDOW_DAYS}))
    assert huge == limit
    assert expiring_member.email in huge


def test_expiring_within_negative_value_is_clamped_to_zero(
    admin_client: APIClient, expiring_member: User, last_day_member: User
) -> None:
    """A window of ``-5`` days keeps today's expiries, which a shifted cutoff drops."""
    negative = emails(admin_client.get(LIST_URL, {"expiring_within": "-5"}))
    zero = emails(admin_client.get(LIST_URL, {"expiring_within": "0"}))
    assert negative == zero
    assert last_day_member.email in negative
    assert expiring_member.email not in negative


def test_expiring_within_fraction_truncates_towards_zero(
    admin_client: APIClient, expiring_member: User
) -> None:
    """A fractional day narrows the window the same way ``int()`` would."""
    fraction = admin_client.get(LIST_URL, {"expiring_within": "29.9"})
    assert expiring_member.email not in emails(fraction)
    whole = admin_client.get(LIST_URL, {"expiring_within": "30"})
    assert expiring_member.email in emails(whole)


def test_expiring_within_at_the_limit_still_finds_a_match(
    admin_client: APIClient, expiring_member: User
) -> None:
    """A window equal to the limit still returns a member whose coverage ends there."""
    response = admin_client.get(LIST_URL, {"expiring_within": MAX_EXPIRING_WINDOW_DAYS})
    assert response.status_code == 200
    assert expiring_member.email in emails(response)
