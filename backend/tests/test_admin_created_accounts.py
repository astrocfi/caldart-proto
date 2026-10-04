"""Accounts an administrator creates, and the wording of the administration screens' API.

A person an account administrator creates on New member has joined already, as a
member or a friend: ``/auth/me`` says so with ``admin_created``, and the portal opens
for them without the join wizard.  The same module holds the administration API's
plain words: the role descriptions the user record lists, the refusal of a role change
only a system administrator may make, and the casing of an aircraft owner's name.  The
contracts are ``docs/developer/api-auth.rst`` and ``docs/developer/api-members.rst``.
"""

from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import MEMBER, ROLE_DESCRIPTIONS, SYSTEM_ADMIN
from apps.aircraft.models import Aircraft, OwnerType
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
    ("typed", "stored"),
    [
        ("SKYWAYS AVIATION LLC", "Skyways Aviation LLC"),
        ("bay area flying club", "Bay Area Flying Club"),
        ("SkyWest Aviation", "SkyWest Aviation"),
        ("  NORTH  BAY FBO ", "North Bay FBO"),
        ("", ""),
    ],
    ids=["registry-capitals", "lower-case", "mixed-case-kept", "spaces-and-fbo", "blank"],
)
def test_business_name(typed: str, stored: str) -> None:
    """A one-case business name is title-cased with its abbreviations kept upper case."""
    assert business_name(typed) == stored


def test_a_flying_clubs_name_from_the_registry_is_stored_title_cased() -> None:
    """An owner that is not a person, typed in capitals, is saved in title case."""
    aircraft = AircraftFactory(owner_type=OwnerType.CLUB, owner_name="DELTA FLYING CLUB INC")
    aircraft.refresh_from_db()
    assert aircraft.owner_name == "Delta Flying Club Inc"


def test_a_person_owner_is_still_cased_as_a_name() -> None:
    """An individual owner keeps the person-name rules: ``MCDONALD`` is ``McDonald``."""
    aircraft = AircraftFactory(owner_type=OwnerType.INDIVIDUAL, owner_name="ANN MCDONALD")
    assert aircraft.owner_name == "Ann McDonald"


def test_normalize_casing_title_cases_a_stored_business_owner() -> None:
    """``manage.py normalize_casing`` gives a club stored in capitals its saved casing."""
    aircraft = AircraftFactory(owner_type=OwnerType.CLUB, owner_name="x")
    Aircraft.objects.filter(pk=aircraft.pk).update(owner_name="BAY AREA FLYING CLUB LLC")
    call_command("normalize_casing", stdout=StringIO())
    aircraft.refresh_from_db()
    assert aircraft.owner_name == "Bay Area Flying Club LLC"
