"""The Apple Pay domain-association file.

Stripe fetches ``/.well-known/apple-developer-merchantid-domain-association``
over plain HTTP when the domain is registered; without it Apple Pay never
appears in the Payment Element.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from django.test import Client
from pytest_django.fixtures import Settings

URL = "/.well-known/apple-developer-merchantid-domain-association"

pytestmark = pytest.mark.django_db


@pytest.fixture
def association_file(tmp_path: Path, settings: Settings) -> Path:
    """Write a fake association file and point the setting at it."""
    path = tmp_path / "apple-developer-merchantid-domain-association"
    path.write_text("7B227073705F6964223A2244454144424545460A")
    settings.STRIPE_APPLE_PAY_DOMAIN_ASSOCIATION = str(path)
    return path


def test_the_file_is_served_as_plain_text(client: Client, association_file: Path) -> None:
    """The endpoint returns the file's bytes as ``text/plain`` to an anonymous client."""
    response = client.get(URL)
    assert response.status_code == 200
    assert response["Content-Type"] == "text/plain"
    assert response.content.decode() == association_file.read_text()


def test_the_response_is_cacheable(client: Client, association_file: Path) -> None:
    """Stripe re-fetches it periodically; let the proxy help."""
    cache_control = client.get(URL)["Cache-Control"]
    assert "max-age=3600" in cache_control
    assert "public" in cache_control


def test_it_is_404_when_unconfigured(client: Client, settings: Settings) -> None:
    """An empty setting means no file is configured, so the endpoint 404s."""
    settings.STRIPE_APPLE_PAY_DOMAIN_ASSOCIATION = ""
    assert client.get(URL).status_code == 404


def test_it_is_404_when_the_file_is_missing(
    client: Client, settings: Settings, tmp_path: Path
) -> None:
    """A configured path that does not exist on disk also 404s."""
    settings.STRIPE_APPLE_PAY_DOMAIN_ASSOCIATION = str(tmp_path / "nope.txt")
    assert client.get(URL).status_code == 404


def test_head_works_like_get(client: Client, association_file: Path) -> None:
    """A HEAD request succeeds, so a checker that only probes headers is answered."""
    assert client.head(URL).status_code == 200


def test_post_is_refused(client: Client, association_file: Path) -> None:
    """The endpoint is read-only: a POST is refused with a 405."""
    assert client.post(URL).status_code == 405
