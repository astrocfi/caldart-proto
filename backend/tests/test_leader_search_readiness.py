"""Go/no-go on a leader's search results.

A leader on an activation reads the list and needs the answer there: the row
carries the same two go/no-go booleans the status card computes, so a leader
reads a verdict off the list and opens the card for the detail.  The card's
own rule is tested in ``test_leader_api.py``; these tests prove the list agrees
with it, case by case.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.members.models import MedicalType, MembershipPlan, MembershipStatusChoices
from tests.factories import MemberProfileFactory, MembershipFactory, UserFactory

pytestmark = pytest.mark.django_db

SEARCH_URL = "/api/v1/leader/search"
STATUS_URL = "/api/v1/leader/members/{pk}/status"

#: Every search below matches on this surname alone.
SURNAME = "Quillan"

ONE_DAY = timedelta(days=1)


def make_member(
    *,
    email: str,
    annual_plan: MembershipPlan,
    today: date,
    membership: bool,
    medical: str,
    expiration: date | None,
) -> User:
    """A member of the searched surname, with the membership and medical asked for.

    ``membership`` true gives a term covering today, false a term that ran out a
    month ago.  ``medical`` is the class on file and ``expiration`` its date.
    """
    user = UserFactory(email=email, first_name="Ada", last_name=SURNAME)
    MemberProfileFactory(user=user, medical_type=medical, medical_expiration=expiration)
    if membership:
        MembershipFactory(user=user, plan=annual_plan, starts_on=today - 30 * ONE_DAY)
    else:
        MembershipFactory(
            user=user,
            plan=annual_plan,
            starts_on=today - 400 * ONE_DAY,
            ends_on=today - 30 * ONE_DAY,
            status=MembershipStatusChoices.EXPIRED,
        )
    return user


def search_row(client: APIClient, user: User) -> dict[str, Any]:
    """The search result for ``user``, or raise when the search does not find them."""
    rows: list[dict[str, Any]] = client.get(SEARCH_URL, {"q": SURNAME}).json()
    for row in rows:
        if row["user_id"] == user.pk:
            return row
    raise AssertionError(f"{user.email} is not in the search results")


@pytest.fixture
def leader_client(api_client: APIClient, dart_leader: User) -> APIClient:
    """A client signed in as the DART leader who runs the check."""
    api_client.force_login(dart_leader)
    return api_client


@pytest.fixture
def go(leader_client: APIClient, annual_plan: MembershipPlan, today: date) -> User:
    """A member who may fly: a current term and a medical in date."""
    return make_member(
        email="go@example.test",
        annual_plan=annual_plan,
        today=today,
        membership=True,
        medical=MedicalType.THIRD,
        expiration=today + 120 * ONE_DAY,
    )


def test_a_ready_member_is_a_go_on_both_counts(leader_client: APIClient, go: User) -> None:
    """A current member with a current medical reads as a go in the list."""
    assert search_row(leader_client, go)["go_no_go"] == {
        "membership": True,
        "medical": True,
    }


def test_a_lapsed_membership_is_a_no_go_on_the_membership(
    leader_client: APIClient, annual_plan: MembershipPlan, today: date
) -> None:
    """A member whose term has run out reads as a no-go on the membership alone."""
    user = make_member(
        email="lapsed@example.test",
        annual_plan=annual_plan,
        today=today,
        membership=False,
        medical=MedicalType.THIRD,
        expiration=today + 120 * ONE_DAY,
    )
    assert search_row(leader_client, user)["go_no_go"] == {
        "membership": False,
        "medical": True,
    }


def test_a_lapsed_medical_is_a_no_go_on_the_medical(
    leader_client: APIClient, annual_plan: MembershipPlan, today: date
) -> None:
    """A member whose medical has expired reads as a no-go on the medical alone."""
    user = make_member(
        email="grounded@example.test",
        annual_plan=annual_plan,
        today=today,
        membership=True,
        medical=MedicalType.THIRD,
        expiration=today - ONE_DAY,
    )
    assert search_row(leader_client, user)["go_no_go"] == {
        "membership": True,
        "medical": False,
    }


def test_no_medical_on_file_is_a_no_go_on_the_medical(
    leader_client: APIClient, annual_plan: MembershipPlan, today: date
) -> None:
    """A member with no medical at all reads as a no-go on the medical."""
    user = make_member(
        email="nomedical@example.test",
        annual_plan=annual_plan,
        today=today,
        membership=True,
        medical=MedicalType.NONE,
        expiration=None,
    )
    assert search_row(leader_client, user)["go_no_go"] == {
        "membership": True,
        "medical": False,
    }


def test_a_medical_that_expires_today_is_still_current(
    leader_client: APIClient, annual_plan: MembershipPlan, today: date
) -> None:
    """A medical is current through its expiration date, not up to it."""
    user = make_member(
        email="lastday@example.test",
        annual_plan=annual_plan,
        today=today,
        membership=True,
        medical=MedicalType.BASICMED,
        expiration=today,
    )
    assert search_row(leader_client, user)["go_no_go"]["medical"] is True


def test_a_member_with_no_profile_is_a_no_go_on_both_counts(leader_client: APIClient) -> None:
    """That same account has no term either, so both booleans are false."""
    user = UserFactory(email="bare2@example.test", first_name="Cy", last_name=SURNAME)
    assert search_row(leader_client, user)["go_no_go"] == {
        "membership": False,
        "medical": False,
    }


def test_the_list_and_the_card_give_the_same_verdict(leader_client: APIClient, go: User) -> None:
    """The row's go/no-go is the card's go/no-go, so the two can never disagree."""
    card = leader_client.get(STATUS_URL.format(pk=go.pk)).json()
    assert search_row(leader_client, go)["go_no_go"] == card["go_no_go"]


def test_a_search_result_carries_exactly_these_fields(leader_client: APIClient, go: User) -> None:
    """The row holds the six fields the list draws and nothing else."""
    assert set(search_row(leader_client, go)) == {
        "user_id",
        "name",
        "email",
        "dart",
        "membership_status",
        "go_no_go",
    }
