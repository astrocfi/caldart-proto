"""Accounts an administrator creates, and the wording of the administration screens' API.

A person an account administrator creates on New member has joined already, as a
member or a friend: ``/auth/me`` says so with ``admin_created``, and the portal opens
for them without the join wizard.  The same module holds the administration API's
plain words: the role descriptions the user record lists, the refusal of a role change
only a system administrator may make, and the casing of an aircraft owner's name.  The
contracts are ``docs/developer/api-auth.rst`` and ``docs/developer/api-members.rst``.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import MEMBER, ROLE_DESCRIPTIONS, SYSTEM_ADMIN
from apps.aircraft.models import OwnerType, RegistrantType
from apps.aircraft.registry import registrant_display_name
from caldart.casing import business_name
from tests.conftest import ME_URL, REGISTER_URL, register_payload
from tests.factories import AircraftFactory

pytestmark = pytest.mark.django_db

MEMBERS_URL = "/api/v1/admin/members"
USERS_URL = "/api/v1/admin/users"
PASSWORD = "a-long-enough-password-9"  # noqa: S105 - a throwaway test password


def created_on_new_member(client: APIClient, admin: User, **extra: str) -> User:
    """Create Pat Quinn on New member as ``admin``, and return the account."""
    client.force_login(admin)
    body = {"email": "pat.quinn@example.test", "first_name": "Pat", "last_name": "Quinn", **extra}
    response = client.post(MEMBERS_URL, body, format="json")
    assert response.status_code == 201, response.json()
    client.logout()
    return User.objects.get(email="pat.quinn@example.test")


# --------------------------------------------------------------------------
# admin_created
# --------------------------------------------------------------------------
def test_an_account_made_on_new_member_reads_admin_created(
    api_client: APIClient, account_admin: User
) -> None:
    """The person's own ``/auth/me`` says an administrator created the account."""
    user = created_on_new_member(api_client, account_admin, password=PASSWORD)
    api_client.force_login(user)
    assert api_client.get(ME_URL).json()["admin_created"] is True


def test_an_invited_account_reads_admin_created_too(
    api_client: APIClient, account_admin: User
) -> None:
    """An account made without a password, and so invited by email, is marked as well."""
    user = created_on_new_member(api_client, account_admin)
    assert user.admin_created is True


def test_a_registered_account_is_not_admin_created(api_client: APIClient) -> None:
    """Somebody who registers through the join wizard reads ``admin_created: false``."""
    response = api_client.post(REGISTER_URL, register_payload(), format="json")
    assert response.json()["admin_created"] is False


# --------------------------------------------------------------------------
# Plain words
# --------------------------------------------------------------------------
@pytest.mark.parametrize("term", ["Wagtail", "Django", "trigger", "reconcile"])
def test_no_role_description_uses_a_technical_term(term: str) -> None:
    """The user record's role descriptions avoid words a volunteer would not know."""
    assert not any(term in description for description in ROLE_DESCRIPTIONS.values())


def test_a_refused_system_administrator_grant_names_the_role_in_words(
    api_client: APIClient, user_admin: User, member: User
) -> None:
    """A user administrator who checks System administrator is told so in words."""
    api_client.force_login(user_admin)
    response = api_client.patch(
        f"{USERS_URL}/{member.pk}", {"roles": [MEMBER, SYSTEM_ADMIN]}, format="json"
    )
    assert response.json()["roles"] == [
        "Only a system administrator can grant or take away the System administrator role."
    ]


@pytest.mark.parametrize(
    ("registered", "shown"),
    [
        ("SKYWAYS AVIATION LLC", "Skyways Aviation LLC"),
        ("SKYWAYS AVIATION OF NAPA L.L.C.", "Skyways Aviation of Napa L.L.C."),
        ("  NORTH  BAY FBO ", "North Bay FBO"),
        ("SkyWest Aviation", "SkyWest Aviation"),
        ("KPAO FBO INC", "KPAO FBO Inc"),
        ("JB AVIATION", "JB Aviation"),
        ("BAY AREA FLYERS", "Bay Area Flyers"),
        ("KING AIR INC", "King Air Inc"),
        ("KIDS FLY LLC", "Kids Fly LLC"),
        ("KEYS AVIATION", "Keys Aviation"),
        ("FLYERS OF KPAO", "Flyers of Kpao"),
        ("ST LOUIS AVIATION", "St Louis Aviation"),
        ("MR SMITH AIR CTR", "Mr Smith Air Ctr"),
        ("TR FLYING", "Tr Flying"),
        ("", ""),
    ],
    ids=[
        "capitals",
        "small-word-and-periods",
        "spaces-and-fbo",
        "mixed-case-kept",
        "airport-identifier-kept",
        "initials-kept",
        "short-words-title-cased",
        "king-is-a-word",
        "kids-is-a-word",
        "keys-is-a-word",
        "identifier-only-first",
        "st-is-a-word",
        "mr-and-ctr-are-words",
        "tr-is-a-word",
        "blank",
    ],
)
def test_business_name(registered: str, shown: str) -> None:
    """A registry's capitals read in title case, the abbreviations kept upper case."""
    assert business_name(registered) == shown


@pytest.mark.parametrize(
    ("name", "registrant_type", "shown"),
    [
        ("SMITH JOHN A", RegistrantType.INDIVIDUAL, "Smith John A"),
        ("MCDONALD ANN", RegistrantType.CO_OWNED, "McDonald Ann"),
        ("FOX FLYERS LLC", RegistrantType.LLC, "Fox Flyers LLC"),
        ("DELTA FLYING CLUB INC", RegistrantType.CORPORATION, "Delta Flying Club Inc"),
    ],
    ids=["individual", "co-owned", "llc", "corporation"],
)
def test_a_registrant_is_shown_in_the_casing_the_register_stores(
    name: str, registrant_type: RegistrantType, shown: str
) -> None:
    """A person's name follows the person-name rule, and a business's the business one."""
    assert registrant_display_name(name, registrant_type) == shown


def test_a_business_owner_a_person_typed_is_kept_as_typed() -> None:
    """An FBO's name typed in capitals is saved exactly as typed: ``KPAO FBO`` stays."""
    aircraft = AircraftFactory(owner_type=OwnerType.FBO, owner_name="KPAO FBO")
    aircraft.refresh_from_db()
    assert aircraft.owner_name == "KPAO FBO"
