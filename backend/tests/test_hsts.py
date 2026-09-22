"""One owner for ``Strict-Transport-Security`` and the other response headers.

Django is the only thing that sets HSTS, ``X-Content-Type-Options`` and
``Referrer-Policy`` on proxied responses: its values are configurable per
deployment and asserted here, while a header baked into a vhost is neither.
The exception is ``/media/``, which both proxies serve straight off disk
without Django ever seeing the request, so ``nosniff`` stays there.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from pytest_django import Settings

from tests.conftest import DEPLOY_DIR

if TYPE_CHECKING:
    from django.test import Client
    from django.test.client import _MonkeyPatchedWSGIResponse

    from apps.cms.models import SiteSettings

APACHE = DEPLOY_DIR / "apache" / "caldart.conf"
NGINX = DEPLOY_DIR / "nginx" / "caldart.conf"
PROXY_CONFIGS = {"apache": APACHE, "nginx": NGINX}

HSTS_HEADER = "Strict-Transport-Security"

#: What ``prod.py`` defaults to, and what a browser should therefore receive.
PRODUCTION_HSTS = {
    "SECURE_HSTS_SECONDS": 31536000,
    "SECURE_HSTS_INCLUDE_SUBDOMAINS": True,
    "SECURE_HSTS_PRELOAD": False,
}

pytestmark = pytest.mark.django_db


@pytest.fixture
def production_hsts(settings: Settings) -> None:
    """Apply the HSTS settings ``prod.py`` defaults to, for the length of one test."""
    for name, value in PRODUCTION_HSTS.items():
        setattr(settings, name, value)


def secure_response(client: Client) -> _MonkeyPatchedWSGIResponse:
    """Return the portal shell fetched over TLS, as a browser would fetch it."""
    return client.get("/portal/", secure=True)


def directives(config: Path) -> str:
    """Return a vhost's contents with comments stripped, matching only what it does."""
    lines = config.read_text().splitlines()
    return "\n".join(line for line in lines if not line.strip().startswith("#"))


def nginx_media_block() -> str:
    """Return the ``location /media/`` block, which Django never sees a request for."""
    config = NGINX.read_text()
    start = config.index("location /media/ {")
    return config[start : config.index("\n    }", start)]


# ------------------------------------------------------- what Django sends
def test_a_secure_request_carries_the_hsts_header(
    client: Client, site_settings: SiteSettings, production_hsts: None
) -> None:
    """A TLS request to the portal shell carries the configured HSTS header value."""
    assert secure_response(client)[HSTS_HEADER] == "max-age=31536000; includeSubDomains"


def test_the_hsts_header_is_sent_exactly_once(
    client: Client, site_settings: SiteSettings, production_hsts: None
) -> None:
    """Two copies is what a proxy adding its own would produce."""
    headers = secure_response(client).serialize_headers()

    assert headers.count(HSTS_HEADER.encode()) == 1


def test_the_hsts_header_does_not_consent_to_preloading(
    client: Client, site_settings: SiteSettings, production_hsts: None
) -> None:
    """Submitting the domain to the browser preload list is very hard to undo."""
    assert "preload" not in secure_response(client)[HSTS_HEADER]


def test_no_hsts_header_on_a_first_deploy(
    client: Client, site_settings: SiteSettings, settings: Settings
) -> None:
    """``SECURE_HSTS_SECONDS=0`` has to reach the browser, or it means nothing."""
    settings.SECURE_HSTS_SECONDS = 0
    assert HSTS_HEADER not in secure_response(client).headers


# ------------------------------------------------------- what the proxies set
@pytest.mark.parametrize("config", PROXY_CONFIGS.values(), ids=PROXY_CONFIGS)
def test_the_proxy_leaves_hsts_to_django(config: Path) -> None:
    """Neither vhost config sets the HSTS header itself."""
    assert HSTS_HEADER not in directives(config)


@pytest.mark.parametrize("config", PROXY_CONFIGS.values(), ids=PROXY_CONFIGS)
def test_the_proxy_leaves_the_referrer_policy_to_django(config: Path) -> None:
    """Neither vhost config sets the referrer policy header itself."""
    assert "Referrer-Policy" not in directives(config)


@pytest.mark.parametrize("config", PROXY_CONFIGS.values(), ids=PROXY_CONFIGS)
def test_the_proxy_sets_nosniff_only_where_django_cannot(config: Path) -> None:
    """The one remaining copy is the ``/media/`` block, checked below."""
    assert directives(config).count("X-Content-Type-Options") == 1


def test_apache_keeps_nosniff_on_media() -> None:
    """The Apache vhost sets ``nosniff`` for the ``/media/`` files it serves directly."""
    assert 'Header set X-Content-Type-Options "nosniff"' in APACHE.read_text()


def test_nginx_keeps_nosniff_on_media() -> None:
    """The nginx vhost sets ``nosniff`` for the ``/media/`` files it serves directly."""
    assert 'add_header X-Content-Type-Options "nosniff" always;' in nginx_media_block()
