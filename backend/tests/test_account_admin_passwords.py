"""The Django admin's accounts pages set nobody's password.

A superuser can list and edit accounts at ``/django-admin/accounts/user/``, but the add
form, the change-password page, and the password on the change form are closed: an
account is added on New member, which invites the person to choose their own password.
"""

from __future__ import annotations

import pytest
from django.test import Client

from apps.accounts.models import User
from tests.conftest import GOOD_PASSWORD
from tests.factories import DEFAULT_PASSWORD, UserFactory

pytestmark = pytest.mark.django_db

USERS_URL = "/django-admin/accounts/user/"


@pytest.fixture
def superuser_browser(superuser: User) -> Client:
    """A browser signed in to the Django admin as a superuser."""
    client = Client()
    client.force_login(superuser)
    return client


@pytest.fixture
def target(db: None) -> User:
    """An ordinary account the superuser looks at."""
    return UserFactory(email="target@example.test")


def test_the_change_form_opens(superuser_browser: Client, target: User) -> None:
    """The account's change form is still there for its other fields."""
    assert superuser_browser.get(f"{USERS_URL}{target.pk}/change/").status_code == 200


def test_the_change_form_links_to_no_password_page(superuser_browser: Client, target: User) -> None:
    """The form carries no password field, so no link to set one either."""
    response = superuser_browser.get(f"{USERS_URL}{target.pk}/change/")
    assert f"{target.pk}/password/" not in response.content.decode()


def test_the_add_form_is_closed(superuser_browser: Client) -> None:
    """Accounts are added on New member, never here."""
    assert superuser_browser.get(f"{USERS_URL}add/").status_code == 403


def test_the_change_password_page_is_closed(superuser_browser: Client, target: User) -> None:
    """Opening the page that would set another account's password is a 403."""
    assert superuser_browser.get(f"{USERS_URL}{target.pk}/password/").status_code == 403


def test_posting_a_password_there_changes_nothing(superuser_browser: Client, target: User) -> None:
    """A posted password is refused, and the account keeps the one its owner chose."""
    superuser_browser.post(
        f"{USERS_URL}{target.pk}/password/",
        {"password1": GOOD_PASSWORD, "password2": GOOD_PASSWORD},
    )
    target.refresh_from_db()
    assert target.check_password(DEFAULT_PASSWORD) is True
