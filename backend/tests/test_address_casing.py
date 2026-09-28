"""Title case for street addresses and city names.

Every write path that saves a ``MemberProfile`` -- the member's own profile, an
administrator's edit, and a settled public donation -- stores ``address_line1``,
``address_line2``, and ``city`` in title case, through
``caldart.casing.title_case_words``.  The docs page is
``docs/user/member/profile.rst``.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.members.models import MemberProfile
from caldart.casing import title_case_words
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

PROFILE_URL = "/api/v1/me/profile"
CHECKOUT_URL = "/api/v1/donations/checkout"
MOCK_COMPLETE_URL = "/api/v1/donations/mock/complete"


def admin_members_url(user: User) -> str:
    """The account-administrator detail endpoint for ``user``."""
    return f"/api/v1/admin/members/{user.id}"


@pytest.fixture(autouse=True)
def empty_donation_throttle_cache() -> Iterator[None]:
    """Clear the public donation throttle's counters: shared state no test may inherit."""
    cache.clear()
    yield
    cache.clear()


# --------------------------------------------------------------------------
# title_case_words
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("palo alto", "Palo Alto"),
        ("O'BRIEN-SMITH lane", "O'Brien-Smith Lane"),
        ("123 MAIN ST NE", "123 Main St Ne"),
        ("94301", "94301"),
        ("2nd street", "2nd Street"),
        ("apt 3B", "Apt 3B"),
        ("  san   carlos  ", "San Carlos"),
        ("", ""),
        ("KING'S rd", "King's Rd"),
        ("st. john's pl", "St. John's Pl"),
        ("d'angelo way", "D'Angelo Way"),
    ],
    ids=[
        "every-word-lowercase",
        "hyphen-and-apostrophe-each-capitalize",
        "every-word-including-directionals",
        "all-digits-left-alone",
        "a-leading-digit-word-left-alone",
        "a-digit-and-letter-word-left-alone",
        "whitespace-trimmed-and-collapsed",
        "blank-stays-blank",
        "a-possessive-stays-lower",
        "a-possessive-after-a-period-stays-lower",
        "a-one-letter-prefix-keeps-its-capital",
    ],
)
def test_title_case_words_matches_the_documented_examples(value: str, expected: str) -> None:
    """Every word capitalizes except one that carries a digit, which is left as typed."""
    assert title_case_words(value) == expected


# --------------------------------------------------------------------------
# The model's save method
# --------------------------------------------------------------------------
def test_saving_a_profile_title_cases_the_street_and_the_city() -> None:
    """``save()`` title-cases ``address_line1``, ``address_line2``, and ``city``."""
    profile = MemberProfile.objects.create(
        user=UserFactory(),
        phone="415-555-0100",
        address_line1="123 main st",
        address_line2="apt 3B",
        city="palo alto",
    )
    assert (profile.address_line1, profile.address_line2, profile.city) == (
        "123 Main St",
        "Apt 3B",
        "Palo Alto",
    )


def test_saving_a_profile_leaves_other_free_text_fields_uncased() -> None:
    """The emergency contact, outside ``TITLE_CASE_FIELDS``, is left exactly as typed."""
    profile = MemberProfile.objects.create(
        user=UserFactory(),
        phone="415-555-0100",
        emergency_contact_name="dana lee",
    )
    assert profile.emergency_contact_name == "dana lee"


# --------------------------------------------------------------------------
# The member's own profile
# --------------------------------------------------------------------------
def test_put_profile_title_cases_the_street_and_the_city(
    api_client: APIClient, member: User
) -> None:
    """A member's own ``PUT`` stores the street and the city it was sent in title case."""
    api_client.force_login(member)

    response = api_client.put(
        PROFILE_URL,
        {
            "phone": "415-555-0100",
            "state": "CA",
            "address_line1": "123 main st",
            "city": "palo alto",
        },
        format="json",
    )

    assert response.status_code == 200, response.json()
    data = response.json()
    assert (data["address_line1"], data["city"]) == ("123 Main St", "Palo Alto")


# --------------------------------------------------------------------------
# An administrator's edit
# --------------------------------------------------------------------------
def test_admin_patch_title_cases_the_nested_profile(
    account_admin_client: APIClient, member: User
) -> None:
    """An administrator's ``PATCH`` of the nested profile stores the same casing."""
    response = account_admin_client.patch(
        admin_members_url(member),
        {"profile": {"address_line1": "1 embarcadero", "city": "san carlos"}},
        format="json",
    )

    assert response.status_code == 200, response.json()
    profile = response.json()["profile"]
    assert (profile["address_line1"], profile["city"]) == ("1 Embarcadero", "San Carlos")


# --------------------------------------------------------------------------
# A settled public donation
# --------------------------------------------------------------------------
def test_a_settled_gift_title_cases_the_donors_street_and_city(api_client: APIClient) -> None:
    """A public gift's optional address lands on the donor's profile in title case."""
    checkout = api_client.post(
        CHECKOUT_URL,
        {
            "first_name": "Pat",
            "last_name": "Giver",
            "email": "pat.giver@example.test",
            "phone": "415-555-0100",
            "contribution_cents": 10_000,
            "provider": "mock",
            "address_line1": "1 embarcadero",
            "city": "san carlos",
        },
        format="json",
    )
    assert checkout.status_code == 201, checkout.json()
    body = checkout.json()

    complete = api_client.post(
        MOCK_COMPLETE_URL,
        {"payment_id": body["payment_id"], "token": body["token"]},
        format="json",
    )
    assert complete.status_code == 200, complete.json()

    donor = User.objects.get(email="pat.giver@example.test")
    assert (donor.profile.address_line1, donor.profile.city) == ("1 Embarcadero", "San Carlos")
