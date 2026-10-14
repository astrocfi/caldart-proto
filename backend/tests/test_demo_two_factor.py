"""The seeded demo accounts and two-factor sign-in.

``seed_demo`` marks the accounts in ``apps.accounts.seed.DEMO_ACCOUNTS`` as demo
accounts (``User.is_demo``).  While ``DEMO_ACCOUNTS_SKIP_TWO_FACTOR`` is on, no role
makes a demo account set up two-factor sign-in; one that sets it up anyway is still
asked for a code.  ``docs/developer/two-factor.rst`` describes the rule and
``docs/developer/configuration.rst`` the setting.
"""

from __future__ import annotations

from collections.abc import Callable
from io import StringIO
from typing import TYPE_CHECKING

import pytest
from django.core.management import call_command
from pytest_django import Settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import MEMBER, SYSTEM_ADMIN
from apps.accounts.seed import DEMO_ACCOUNTS
from tests.conftest import LOGIN_URL, ME_URL, change_and_confirm, without_second_factor
from tests.factories import DEFAULT_PASSWORD, UserFactory, confirmed_device

if TYPE_CHECKING:
    from rest_framework.response import _MonkeyPatchedResponse as ApiResponse

pytestmark = pytest.mark.django_db

MFA_STATUS_URL = "/api/v1/auth/mfa"
ADMIN_USERS_URL = "/api/v1/admin/users"
PROFILE_URL = "/api/v1/me/profile"
DEMO_ADMIN_EMAIL = "demo.sysadmin@example.test"


@pytest.fixture
def skip_on(settings: Settings) -> None:
    """Turn the demo accounts' exemption from two-factor sign-in on."""
    settings.DEMO_ACCOUNTS_SKIP_TWO_FACTOR = True


@pytest.fixture
def skip_off(settings: Settings) -> None:
    """Turn the demo accounts' exemption from two-factor sign-in off."""
    settings.DEMO_ACCOUNTS_SKIP_TWO_FACTOR = False


@pytest.fixture
def demo_admin() -> User:
    """A demo-marked system administrator and Django superuser, as the seed writes one."""
    return UserFactory(
        email=DEMO_ADMIN_EMAIL,
        roles=[MEMBER, SYSTEM_ADMIN],
        is_superuser=True,
        is_staff=True,
        is_demo=True,
    )


def password_step(client: APIClient, user: User) -> ApiResponse:
    """Post ``user``'s address and the factory password to the sign-in."""
    return client.post(
        LOGIN_URL, {"email": user.email, "password": DEFAULT_PASSWORD}, format="json"
    )


def _seed() -> None:
    """Run the ``seed_demo`` management command, discarding its stdout."""
    call_command("seed_demo", stdout=StringIO())


# --------------------------------------------------------------------------
# The rule
# --------------------------------------------------------------------------
@pytest.mark.usefixtures("skip_on")
def test_a_demo_administrator_signs_in_with_the_password_alone(
    api_client: APIClient, demo_admin: User
) -> None:
    """With the setting on, the password step answers the user payload."""
    assert password_step(api_client, demo_admin).json()["email"] == DEMO_ADMIN_EMAIL


@pytest.mark.usefixtures("skip_on")
def test_a_demo_administrator_signed_in_with_the_password_stays_signed_in(
    api_client: APIClient, demo_admin: User
) -> None:
    """The session the password step starts is one the next request keeps."""
    password_step(api_client, demo_admin)
    assert api_client.get(ME_URL).status_code == 200


@pytest.mark.usefixtures("skip_on")
def test_the_middleware_keeps_a_demo_administrator_session_without_the_mark(
    api_client: APIClient, demo_admin: User
) -> None:
    """A session that never passed a second factor is not ended."""
    api_client.force_login(demo_admin)
    without_second_factor(api_client)
    assert api_client.get(ME_URL).status_code == 200


@pytest.mark.usefixtures("skip_on")
def test_a_demo_administrator_is_not_required_to_use_two_factor(
    api_client: APIClient, demo_admin: User
) -> None:
    """The two-factor status says no role requires it, so it may be turned off."""
    api_client.force_login(demo_admin)
    assert api_client.get(MFA_STATUS_URL).json()["required_by_role"] is False


@pytest.mark.usefixtures("skip_off")
def test_with_the_setting_off_a_demo_administrator_is_asked_to_enroll(
    api_client: APIClient, demo_admin: User
) -> None:
    """The demo mark alone exempts nobody."""
    assert password_step(api_client, demo_admin).json() == {"mfa": "enroll"}


@pytest.mark.usefixtures("skip_off")
def test_with_the_setting_off_the_middleware_ends_a_demo_session_without_the_mark(
    api_client: APIClient, demo_admin: User
) -> None:
    """The session is ended as for any account a role requires two-factor of."""
    api_client.force_login(demo_admin)
    without_second_factor(api_client)
    assert api_client.get(ME_URL).status_code == 401


@pytest.mark.usefixtures("skip_on")
def test_a_system_administrator_who_is_not_a_demo_account_is_asked_to_enroll(
    api_client: APIClient,
) -> None:
    """The setting exempts only the accounts the seed marked."""
    admin = UserFactory(roles=[MEMBER, SYSTEM_ADMIN], is_superuser=True, is_staff=True)
    assert password_step(api_client, admin).json() == {"mfa": "enroll"}


@pytest.mark.usefixtures("skip_on")
def test_a_demo_account_with_a_device_is_asked_for_a_code(
    api_client: APIClient, demo_admin: User
) -> None:
    """Two-factor sign-in set up voluntarily is still asked for."""
    confirmed_device(demo_admin)
    assert password_step(api_client, demo_admin).json() == {"mfa": "verify"}


# --------------------------------------------------------------------------
# The mark
# --------------------------------------------------------------------------
def test_seed_demo_marks_exactly_the_demo_accounts() -> None:
    """The named demo accounts are marked; the generated members are not."""
    _seed()
    marked = set(User.objects.filter(is_demo=True).values_list("email", flat=True))
    assert marked == {email for _, email, *_ in DEMO_ACCOUNTS}


def test_seed_demo_marks_a_demo_account_again_on_every_run() -> None:
    """A re-run restores a mark something cleared, as it restores the password."""
    _seed()
    User.objects.filter(email="sysadmin@example.org").update(is_demo=False)
    _seed()
    assert User.objects.get(email="sysadmin@example.org").is_demo is True


def test_create_admin_taking_an_account_back_clears_the_mark(demo_admin: User) -> None:
    """An account promoted to a real administrator is never a demo account."""
    call_command("create_admin", email=DEMO_ADMIN_EMAIL, stdout=StringIO(), stderr=StringIO())
    demo_admin.refresh_from_db()
    assert demo_admin.is_demo is False


@pytest.mark.usefixtures("run_on_commit")
def test_a_completed_change_of_address_clears_the_mark(
    vera: User, signed_in_client: Callable[[User], APIClient]
) -> None:
    """An account that moved off its seeded address is no longer the published login."""
    User.objects.filter(pk=vera.pk).update(is_demo=True)
    change_and_confirm(vera, signed_in_client(vera))
    vera.refresh_from_db()
    assert vera.is_demo is False


def test_the_mark_is_not_writable_through_the_user_record(
    api_client: APIClient, system_admin: User, demo_admin: User
) -> None:
    """``PATCH /admin/users/{id}`` ignores ``is_demo``."""
    api_client.force_login(system_admin)
    api_client.patch(
        f"{ADMIN_USERS_URL}/{demo_admin.pk}",
        {"is_demo": False, "first_name": "Rafael"},
        format="json",
    )
    demo_admin.refresh_from_db()
    assert demo_admin.is_demo is True


def test_the_mark_is_not_settable_through_the_user_record(
    api_client: APIClient, system_admin: User, member: User
) -> None:
    """Nobody makes an account a demo account from the user record."""
    api_client.force_login(system_admin)
    api_client.patch(
        f"{ADMIN_USERS_URL}/{member.pk}", {"is_demo": True, "first_name": "Robin"}, format="json"
    )
    member.refresh_from_db()
    assert member.is_demo is False


def test_the_mark_is_not_settable_through_the_profile(api_client: APIClient, member: User) -> None:
    """``PATCH /me/profile`` ignores ``is_demo``."""
    api_client.force_login(member)
    api_client.patch(PROFILE_URL, {"is_demo": True, "phone": "415-555-0111"}, format="json")
    member.refresh_from_db()
    assert member.is_demo is False
