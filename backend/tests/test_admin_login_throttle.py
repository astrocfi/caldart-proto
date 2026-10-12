"""The Wagtail and Django admin login forms share the portal's sign-in rate limit.

Every login form counts against the ``auth_login`` budget by client address, so a
caller cannot guess passwords at the admin forms once the portal's ``/auth/login``
has refused them, nor the other way round.  Only posts are counted: opening the
form is free.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from django.core.cache import cache
from django.test import Client
from pytest_django.fixtures import Settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from tests.conftest import LOGIN_URL

pytestmark = pytest.mark.django_db

WAGTAIL_LOGIN_URL = "/admin/login/"
DJANGO_ADMIN_LOGIN_URL = "/django-admin/login/"
ADMIN_LOGIN_URLS = [WAGTAIL_LOGIN_URL, DJANGO_ADMIN_LOGIN_URL]
WRONG_PASSWORD = "not-the-password"  # noqa: S105 - a guess the form refuses
TOO_MANY = "Too many sign-in attempts. Wait a minute and try again."


@pytest.fixture(autouse=True)
def login_twice_a_minute(settings: Settings) -> None:
    """Two sign-in attempts a minute per client address, on every login form."""
    settings.AUTH_THROTTLE_RATES = {"auth_login": "2/min"}


@pytest.fixture(autouse=True)
def empty_throttle_cache() -> Generator[None]:
    """Start and end each test with no counted attempts."""
    cache.clear()
    yield
    cache.clear()


def guess(client: Client, url: str, member: User) -> int:
    """Post a wrong password for ``member`` to the login form at ``url``; the status."""
    response = client.post(url, {"username": member.email, "password": WRONG_PASSWORD})
    return response.status_code


@pytest.mark.parametrize("url", ADMIN_LOGIN_URLS)
def test_an_admin_login_form_refuses_the_third_guess_in_a_minute(url: str, member: User) -> None:
    """The budget's two attempts are answered by the form; the third is a 429."""
    client = Client()
    assert [guess(client, url, member) for _ in range(3)] == [200, 200, 429]


@pytest.mark.parametrize("url", ADMIN_LOGIN_URLS)
def test_the_refusal_says_to_wait(url: str, member: User) -> None:
    """The 429 carries a plain sentence for the person at the form."""
    client = Client()
    for _ in range(2):
        guess(client, url, member)
    response = client.post(url, {"username": member.email, "password": WRONG_PASSWORD})
    assert response.content.decode() == TOO_MANY


@pytest.mark.parametrize("url", ADMIN_LOGIN_URLS)
def test_the_refusal_says_when_to_try_again(url: str, member: User) -> None:
    """The 429 names the seconds to wait in ``Retry-After``."""
    client = Client()
    for _ in range(2):
        guess(client, url, member)
    response = client.post(url, {"username": member.email, "password": WRONG_PASSWORD})
    assert int(response["Retry-After"]) == 60


@pytest.mark.parametrize("url", ADMIN_LOGIN_URLS)
def test_attempts_at_the_portal_count_against_an_admin_form(
    url: str, api_client: APIClient, member: User
) -> None:
    """Guesses at ``/auth/login`` spend the same budget the admin forms draw on."""
    for _ in range(2):
        api_client.post(
            LOGIN_URL, {"email": member.email, "password": WRONG_PASSWORD}, format="json"
        )
    assert guess(Client(), url, member) == 429


@pytest.mark.parametrize("url", ADMIN_LOGIN_URLS)
def test_attempts_at_an_admin_form_count_against_the_portal(
    url: str, api_client: APIClient, member: User
) -> None:
    """Guesses at an admin form spend the budget ``/auth/login`` draws on too."""
    client = Client()
    for _ in range(2):
        guess(client, url, member)
    response = api_client.post(
        LOGIN_URL, {"email": member.email, "password": WRONG_PASSWORD}, format="json"
    )
    assert response.status_code == 429


@pytest.mark.parametrize("url", ADMIN_LOGIN_URLS)
def test_opening_an_admin_login_form_is_not_counted(url: str, member: User) -> None:
    """Showing the form spends nothing: only posted attempts count."""
    client = Client()
    for _ in range(3):
        client.get(url)
    assert guess(client, url, member) == 200


def test_a_switched_off_throttle_leaves_the_admin_forms_alone(
    settings: Settings, member: User
) -> None:
    """With the ``auth_login`` scope off, the admin forms are not limited either."""
    settings.AUTH_THROTTLE_RATES = {}
    client = Client()
    assert {guess(client, WAGTAIL_LOGIN_URL, member) for _ in range(4)} == {200}
