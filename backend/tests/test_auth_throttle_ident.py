"""Which address the anonymous auth throttles count against.

Both shipped proxies pass a client's own ``X-Forwarded-For`` through and append
the address they saw, so only the **last** entry is trustworthy.  Production
tells DRF exactly that with ``NUM_PROXIES = 1``; without it DRF keys on the
whole header, and a client that varies its prefix is never throttled at all.
"""

from __future__ import annotations

from copy import deepcopy

import pytest
from django.conf import settings
from django.core.cache import cache
from django.test import override_settings

from tests.test_accounts_auth import LOGIN, REGISTER, RESET, register_payload

pytestmark = pytest.mark.django_db

#: The address the proxy itself wrote, and the only one a client cannot choose.
CLIENT = "203.0.113.9"
OTHER_CLIENT = "203.0.113.10"

#: What a client can put in front of it, differently on every request.
SPOOFED = ["198.51.100.7", "192.0.2.44", "198.51.100.200", "192.0.2.1"]

BEHIND_ONE_PROXY = deepcopy(settings.REST_FRAMEWORK) | {"NUM_PROXIES": 1}

LOGIN_TWICE = override_settings(
    REST_FRAMEWORK=BEHIND_ONE_PROXY, AUTH_THROTTLE_RATES={"auth_login": "2/min"}
)


@pytest.fixture(autouse=True)
def empty_throttle_cache():
    """The throttle counters are shared state; no test may inherit them."""
    cache.clear()
    yield
    cache.clear()


def forwarded_for(*addresses: str) -> dict[str, str]:
    """Request kwargs carrying an ``X-Forwarded-For`` chain, client first."""
    return {"HTTP_X_FORWARDED_FOR": ", ".join(addresses)}


def attempt_login(api_client, member, **extra):
    """One failed sign-in: a 400 while the throttle allows it, then a 429."""
    credentials = {"email": member.email, "password": "wrong"}
    return api_client.post(LOGIN, credentials, **extra).status_code


# ---------------------------------------------------------------- login scope
@LOGIN_TWICE
def test_a_rotating_forwarded_prefix_shares_one_budget(api_client, member) -> None:
    """Spoofing the header is what used to buy unlimited password guesses."""
    for spoofed in SPOOFED[:2]:
        assert attempt_login(api_client, member, **forwarded_for(spoofed, CLIENT)) == 400

    assert attempt_login(api_client, member, **forwarded_for(SPOOFED[2], CLIENT)) == 429


@LOGIN_TWICE
def test_two_real_clients_get_a_budget_each(api_client, member) -> None:
    for _ in range(2):
        attempt_login(api_client, member, **forwarded_for(SPOOFED[0], CLIENT))

    assert attempt_login(api_client, member, **forwarded_for(SPOOFED[1], OTHER_CLIENT)) == 400


@LOGIN_TWICE
def test_the_socket_address_counts_when_no_proxy_header_arrives(api_client, member) -> None:
    """A request straight to gunicorn still has to be counted against someone."""
    for _ in range(2):
        assert attempt_login(api_client, member) == 400

    assert attempt_login(api_client, member) == 429


# ----------------------------------------------------- register and reset
@override_settings(REST_FRAMEWORK=BEHIND_ONE_PROXY, AUTH_THROTTLE_RATES={"auth_register": "2/hour"})
def test_registration_counts_the_real_client_too(api_client) -> None:
    for index, spoofed in enumerate(SPOOFED[:2]):
        payload = register_payload(email=f"applicant{index}@example.test")
        response = api_client.post(REGISTER, payload, **forwarded_for(spoofed, CLIENT))
        assert response.status_code == 201

    payload = register_payload(email="applicant9@example.test")
    response = api_client.post(REGISTER, payload, **forwarded_for(SPOOFED[2], CLIENT))

    assert response.status_code == 429


@override_settings(
    REST_FRAMEWORK=BEHIND_ONE_PROXY, AUTH_THROTTLE_RATES={"auth_password_reset": "1/hour"}
)
def test_password_reset_counts_the_real_client_too(api_client, member) -> None:
    """Otherwise an inbox can be sprayed from one machine without limit."""
    first = api_client.post(RESET, {"email": member.email}, **forwarded_for(SPOOFED[0], CLIENT))
    assert first.status_code == 204

    second = api_client.post(RESET, {"email": member.email}, **forwarded_for(SPOOFED[1], CLIENT))

    assert second.status_code == 429
