"""The members admin ``expiring_within`` filter clamps its window.

A window past ``MAX_EXPIRING_WINDOW_DAYS`` or below zero must never reach
``date + timedelta(days=...)`` unclamped: Python's ``date`` overflows past the
year 9999 and turns an oversized query into a 500.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model

from apps.members.api.admin_filters import MAX_EXPIRING_WINDOW_DAYS
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db

User = get_user_model()

LIST_URL = "/api/v1/admin/members"


@pytest.fixture
def admin_client(api_client, account_admin):
    api_client.force_login(account_admin)
    return api_client


@pytest.fixture
def expiring_member(annual_plan, today):
    """A current member whose coverage ends 30 days out."""
    day = timedelta(days=1)
    membership = MembershipFactory(
        plan=annual_plan,
        starts_on=today - (annual_plan.duration_days - 30) * day,
        ends_on=today + 30 * day,
    )
    return membership.user


def emails(response) -> set[str]:
    return {row["email"] for row in response.json()["results"]}


@pytest.mark.parametrize("window", ["999999999", "1e11", "-5"])
def test_expiring_within_survives_an_absurd_window(
    admin_client, expiring_member, window: str
) -> None:
    """An overflowing timedelta would be a 500, not a filter."""
    response = admin_client.get(LIST_URL, {"expiring_within": window})
    assert response.status_code == 200


def test_expiring_within_huge_value_is_clamped_to_the_limit(admin_client, expiring_member) -> None:
    huge = emails(admin_client.get(LIST_URL, {"expiring_within": "3000000"}))
    limit = emails(admin_client.get(LIST_URL, {"expiring_within": MAX_EXPIRING_WINDOW_DAYS}))
    assert huge == limit
    assert expiring_member.email in huge


def test_expiring_within_negative_value_is_clamped_to_zero(admin_client, expiring_member) -> None:
    negative = emails(admin_client.get(LIST_URL, {"expiring_within": "-5"}))
    zero = emails(admin_client.get(LIST_URL, {"expiring_within": "0"}))
    assert negative == zero
    assert expiring_member.email not in negative


def test_expiring_within_fraction_truncates_towards_zero(admin_client, expiring_member) -> None:
    """A fractional day narrows the window the same way ``int()`` would."""
    fraction = admin_client.get(LIST_URL, {"expiring_within": "29.9"})
    assert expiring_member.email not in emails(fraction)
    whole = admin_client.get(LIST_URL, {"expiring_within": "30"})
    assert expiring_member.email in emails(whole)


def test_expiring_within_at_the_limit_still_finds_a_match(admin_client, expiring_member) -> None:
    response = admin_client.get(LIST_URL, {"expiring_within": MAX_EXPIRING_WINDOW_DAYS})
    assert response.status_code == 200
    assert expiring_member.email in emails(response)
