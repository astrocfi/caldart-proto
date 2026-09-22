"""Which address the anonymous auth throttles count against.

Both shipped proxies pass a client's own ``X-Forwarded-For`` through and append
the address they saw, so only the **last** entry is trustworthy.  Production
tells DRF exactly that with ``NUM_PROXIES = 1``; without it DRF keys on the
whole header, and a client that varies its prefix is never throttled at all.
"""

from __future__ import annotations

from collections.abc import Generator
from copy import deepcopy

import pytest
from django.conf import settings as django_settings
from django.core.cache import cache
from pytest_django import Settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from tests.conftest import LOGIN_URL, REGISTER_URL, RESET_URL, register_payload

pytestmark = pytest.mark.django_db

#: The address the proxy itself wrote, and the only one a client cannot choose.
CLIENT = "203.0.113.9"
OTHER_CLIENT = "203.0.113.10"

#: What a client can put in front of it, differently on every request.
SPOOFED = ["198.51.100.7", "192.0.2.44", "198.51.100.200", "192.0.2.1"]

BEHIND_ONE_PROXY = deepcopy(django_settings.REST_FRAMEWORK) | {"NUM_PROXIES": 1}


@pytest.fixture
def login_twice_a_minute(settings: Settings) -> None:
    """One proxy in front, and a login budget of two attempts a minute."""
    settings.REST_FRAMEWORK = BEHIND_ONE_PROXY
    settings.AUTH_THROTTLE_RATES = {"auth_login": "2/min"}


@pytest.fixture(autouse=True)
def empty_throttle_cache() -> Generator[None]:
    """The throttle counters are shared state; no test may inherit them."""
    cache.clear()
    yield
    cache.clear()


def forwarded_for(*addresses: str) -> str:
    """An ``X-Forwarded-For`` header value chaining ``addresses``, client first."""
    return ", ".join(addresses)


def attempt_login(api_client: APIClient, member: User, chain: str = "") -> int:
    """One failed sign-in: a 400 while the throttle allows it, then a 429.

    ``chain`` is the ``X-Forwarded-For`` value to send; the default sends no such
    header, so the request arrives as if straight off the socket.
    """
    credentials = {"email": member.email, "password": "wrong"}
    if len(chain) == 0:
        return api_client.post(LOGIN_URL, credentials).status_code
    return api_client.post(LOGIN_URL, credentials, HTTP_X_FORWARDED_FOR=chain).status_code


# ---------------------------------------------------------------- login scope
def test_a_rotating_forwarded_prefix_shares_one_budget(
    api_client: APIClient, member: User, login_twice_a_minute: None
) -> None:
    """A different spoofed prefix on every guess buys no extra attempts."""
    for spoofed in SPOOFED[:2]:
        assert attempt_login(api_client, member, forwarded_for(spoofed, CLIENT)) == 400

    assert attempt_login(api_client, member, forwarded_for(SPOOFED[2], CLIENT)) == 429


def test_two_real_clients_get_a_budget_each(
    api_client: APIClient, member: User, login_twice_a_minute: None
) -> None:
    """Two different real client addresses are throttled independently."""
    for _ in range(2):
        attempt_login(api_client, member, forwarded_for(SPOOFED[0], CLIENT))

    assert attempt_login(api_client, member, forwarded_for(SPOOFED[1], OTHER_CLIENT)) == 400


def test_the_socket_address_counts_when_no_proxy_header_arrives(
    api_client: APIClient, member: User, login_twice_a_minute: None
) -> None:
    """A request straight to gunicorn still has to be counted against someone."""
    for _ in range(2):
        assert attempt_login(api_client, member) == 400

    assert attempt_login(api_client, member) == 429


# ----------------------------------------------------- register and reset
def test_registration_counts_the_real_client_too(api_client: APIClient, settings: Settings) -> None:
    """A rotating spoofed prefix does not buy extra registration attempts either."""
    settings.REST_FRAMEWORK = BEHIND_ONE_PROXY
    settings.AUTH_THROTTLE_RATES = {"auth_register": "2/hour"}
    for index, spoofed in enumerate(SPOOFED[:2]):
        payload = register_payload(email=f"applicant{index}@example.test")
        response = api_client.post(
            REGISTER_URL, payload, HTTP_X_FORWARDED_FOR=forwarded_for(spoofed, CLIENT)
        )
        assert response.status_code == 201

    payload = register_payload(email="applicant9@example.test")
    response = api_client.post(
        REGISTER_URL, payload, HTTP_X_FORWARDED_FOR=forwarded_for(SPOOFED[2], CLIENT)
    )

    assert response.status_code == 429


def test_password_reset_counts_the_real_client_too(
    api_client: APIClient, member: User, settings: Settings
) -> None:
    """Otherwise an inbox can be sprayed from one machine without limit."""
    settings.REST_FRAMEWORK = BEHIND_ONE_PROXY
    settings.AUTH_THROTTLE_RATES = {"auth_password_reset": "1/hour"}
    first = api_client.post(
        RESET_URL,
        {"email": member.email},
        HTTP_X_FORWARDED_FOR=forwarded_for(SPOOFED[0], CLIENT),
    )
    assert first.status_code == 204

    second = api_client.post(
        RESET_URL,
        {"email": member.email},
        HTTP_X_FORWARDED_FOR=forwarded_for(SPOOFED[1], CLIENT),
    )

    assert second.status_code == 429
