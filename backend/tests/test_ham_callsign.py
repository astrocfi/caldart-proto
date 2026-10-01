"""The amateur radio callsign on a member's profile.

Optional, US format only, stored upper case with spaces removed.  The member edits it on
their own profile, the account administrator on the member record, and the membership
report carries it as a column.  The docs pages are ``docs/user/member/profile.rst`` and
``docs/developer/api-profile.rst``.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.members.models import MemberProfile
from apps.members.reports import MEMBER_REPORT_COLUMNS

pytestmark = pytest.mark.django_db

PROFILE_URL = "/api/v1/me/profile"
CSV_URL = "/api/v1/reports/members/export.csv"

#: What every refused callsign is answered with.
CALLSIGN_MESSAGE = "Enter a US amateur radio callsign, such as W6ABC."


def admin_members_url(user: User) -> str:
    """The account-administrator detail endpoint for ``user``."""
    return f"/api/v1/admin/members/{user.id}"


@pytest.mark.parametrize(
    ("typed", "stored"),
    [
        ("W6ABC", "W6ABC"),
        ("w6abc", "W6ABC"),
        ("K6A", "K6A"),
        ("N0XYZ", "N0XYZ"),
        ("KD6AB", "KD6AB"),
        ("WA6ABC", "WA6ABC"),
        ("AA6A", "AA6A"),
        ("AL7XYZ", "AL7XYZ"),
        ("w6 abc", "W6ABC"),
        ("  kd6ab ", "KD6AB"),
        ("", ""),
    ],
    ids=[
        "one-letter-prefix",
        "lower-case-upper-cased",
        "one-letter-suffix",
        "digit-zero",
        "two-letter-k-prefix",
        "two-letter-w-prefix",
        "aa-prefix",
        "al-prefix",
        "inner-space-removed",
        "outer-spaces-removed",
        "blank-clears-it",
    ],
)
def test_patch_profile_stores_a_valid_callsign_upper_case(
    api_client: APIClient, member: User, profile: MemberProfile, typed: str, stored: str
) -> None:
    """A US callsign is accepted and stored upper case without spaces."""
    api_client.force_login(member)
    response = api_client.patch(PROFILE_URL, {"ham_callsign": typed}, format="json")
    assert response.status_code == 200, response.json()
    profile.refresh_from_db()
    assert profile.ham_callsign == stored


@pytest.mark.parametrize(
    "typed",
    ["X1ABC", "AM6ABC", "W6", "W6ABCD", "6ABC", "WAB6ABC", "W6A1", "VE3ABC", "W-6ABC"],
    ids=[
        "x-prefix-is-not-us",
        "am-prefix-is-not-us",
        "no-suffix",
        "four-letter-suffix",
        "no-prefix",
        "three-letter-prefix",
        "digit-in-suffix",
        "canadian",
        "punctuation",
    ],
)
def test_patch_profile_refuses_a_callsign_that_is_not_us_format(
    api_client: APIClient, member: User, profile: MemberProfile, typed: str
) -> None:
    """Anything but a US callsign is refused with the documented message."""
    api_client.force_login(member)
    response = api_client.patch(PROFILE_URL, {"ham_callsign": typed}, format="json")
    assert response.status_code == 400
    assert response.json() == {"ham_callsign": [CALLSIGN_MESSAGE]}


def test_get_profile_carries_the_callsign(
    api_client: APIClient, member: User, profile: MemberProfile
) -> None:
    """``GET /me/profile`` reads the stored callsign."""
    profile.ham_callsign = "W6ABC"
    profile.save()
    api_client.force_login(member)
    assert api_client.get(PROFILE_URL).json()["ham_callsign"] == "W6ABC"


def test_put_profile_without_a_callsign_clears_it(
    api_client: APIClient, member: User, profile: MemberProfile
) -> None:
    """The callsign is a profile field, so a full ``PUT`` that leaves it out clears it."""
    profile.ham_callsign = "W6ABC"
    profile.save()
    api_client.force_login(member)
    response = api_client.put(PROFILE_URL, {"phone": "415-555-0100", "state": "CA"}, format="json")
    assert response.status_code == 200, response.json()
    profile.refresh_from_db()
    assert profile.ham_callsign == ""


def test_saving_a_profile_upper_cases_the_callsign() -> None:
    """``MemberProfile.save()`` stores the callsign upper case with spaces removed."""
    profile = MemberProfile.objects.create(
        user=User.objects.create_user(email="ham@example.test"), ham_callsign="w6 abc"
    )
    profile.refresh_from_db()
    assert profile.ham_callsign == "W6ABC"


def test_admin_edits_the_callsign_on_the_member_record(
    account_admin_client: APIClient, member: User, profile: MemberProfile
) -> None:
    """An administrator's ``PATCH`` of the nested profile stores the callsign."""
    response = account_admin_client.patch(
        admin_members_url(member), {"profile": {"ham_callsign": "kd6ab"}}, format="json"
    )
    assert response.status_code == 200, response.json()
    assert response.json()["profile"]["ham_callsign"] == "KD6AB"


def test_admin_edit_refuses_a_callsign_that_is_not_us_format(
    account_admin_client: APIClient, member: User, profile: MemberProfile
) -> None:
    """The administrator's editor applies the same rule, keyed under the profile."""
    response = account_admin_client.patch(
        admin_members_url(member), {"profile": {"ham_callsign": "X1ABC"}}, format="json"
    )
    assert response.status_code == 400
    assert response.json() == {"profile": {"ham_callsign": [CALLSIGN_MESSAGE]}}


def test_the_membership_report_offers_a_callsign_column() -> None:
    """The column chooser and the exports offer Callsign, off by default."""
    column = next(column for column in MEMBER_REPORT_COLUMNS if column.key == "ham_callsign")
    assert (column.label, column.default) == ("Callsign", False)


def test_the_membership_export_carries_the_callsign(
    account_admin_client: APIClient, member: User, profile: MemberProfile
) -> None:
    """A CSV that asks for the column carries the member's callsign under Callsign."""
    profile.ham_callsign = "W6ABC"
    profile.save()
    response = account_admin_client.get(CSV_URL, {"columns": "name,ham_callsign"})
    assert response.status_code == 200
    rows = response.content.decode().splitlines()
    assert rows[0] == "Name,Callsign"
    assert f"{member.display_name},W6ABC" in rows[1:]
