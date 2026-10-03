"""The Wagtail admin manages no accounts: the portal is the one place that does.

Wagtail's own screens for users and groups, its bulk actions on accounts, its
password reset, and its account page would each change an account outside the
portal's rules (roles, deactivation, the payment handover on delete, address
verification).  They answer 404, and the account page sends the reader to their
portal profile.  The settings menu offers neither Users nor Groups.
"""

from __future__ import annotations

import pytest
from django.test import Client

from apps.accounts.models import User
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

#: Every Wagtail screen that would list, create, edit, or delete an account or a role.
CLOSED_SCREENS = [
    "/admin/users/",
    "/admin/users/add/",
    "/admin/users/edit/{pk}/",
    "/admin/users/delete/{pk}/",
    "/admin/groups/",
    "/admin/groups/add/",
    "/admin/bulk/accounts/user/delete/?id={pk}",
    "/admin/bulk/accounts/user/set_active_state/?id={pk}",
    "/admin/password_reset/",
]


@pytest.fixture
def wagtail_client(client: Client, superuser: User) -> Client:
    """The Wagtail admin as a superuser, who could reach every screen Wagtail offers."""
    client.force_login(superuser)
    return client


@pytest.mark.parametrize("url", CLOSED_SCREENS)
def test_a_wagtail_account_screen_is_not_found(wagtail_client: Client, url: str) -> None:
    """Each of Wagtail's account and role screens answers 404, even to a superuser."""
    other = UserFactory()
    assert wagtail_client.get(url.format(pk=other.pk)).status_code == 404


def test_a_delete_posted_to_wagtail_deletes_nothing(wagtail_client: Client) -> None:
    """A delete posted to Wagtail's user delete view leaves the account in place."""
    other = UserFactory()
    wagtail_client.post(f"/admin/users/delete/{other.pk}/")
    assert User.objects.filter(pk=other.pk).exists()


def test_the_wagtail_account_page_sends_the_reader_to_their_portal_profile(
    wagtail_client: Client,
) -> None:
    """``/admin/account/`` redirects to ``/portal/profile``, where accounts are edited."""
    response = wagtail_client.get("/admin/account/")
    assert response.status_code == 302
    assert response["Location"] == "/portal/profile"


@pytest.mark.parametrize("label", ["Users", "Groups"])
def test_the_settings_menu_offers_no_account_screens(wagtail_client: Client, label: str) -> None:
    """The Wagtail dashboard's menu carries no Users or Groups entry."""
    page = wagtail_client.get("/admin/").content.decode()
    assert f'"label": "{label}"' not in page
