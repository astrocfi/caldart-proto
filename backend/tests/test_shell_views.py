"""The server-rendered shells: home page and the portal SPA mount.

These run whether or not the frontend has been built -- ``conftest.py`` stubs
the Vite manifest when there is no real build, and the two tests that assert on
the actual bundle carry ``needs_frontend_build`` and skip unless one is present.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from django.conf import settings as django_settings
from django.test import Client
from django_vite.core.asset_loader import DjangoViteAssetLoader
from pytest_django.fixtures import Settings

from apps.cms.models import HomePage, SiteSettings

pytestmark = pytest.mark.django_db


def manifest_entry(source: str) -> dict[str, Any]:
    """The Vite manifest entry for ``source`` (a build entry point).

    Reads whichever manifest ``DJANGO_VITE`` is configured with, real or the
    ``needs_frontend_build`` skip guard would not have let the test reach here.
    """
    manifest_path = Path(django_settings.DJANGO_VITE["default"]["manifest_path"])
    manifest: dict[str, dict[str, Any]] = json.loads(manifest_path.read_text())
    return manifest[source]


@pytest.fixture
def vite_dev_mode(settings: Settings) -> Iterator[None]:
    """Render the shells the way they render against the Vite dev server.

    django-vite builds its asset loader once, from ``DJANGO_VITE``, and caches it on the
    class, so the cached loader is discarded on the way in for the override to take
    effect and on the way out so it cannot leak into later tests.
    """
    config = copy.deepcopy(settings.DJANGO_VITE)
    config["default"]["dev_mode"] = True
    settings.DJANGO_VITE = config
    DjangoViteAssetLoader._instance = None
    yield
    DjangoViteAssetLoader._instance = None


def test_portal_shell_renders(client: Client, site_settings: SiteSettings) -> None:
    """The portal shell renders its root mount and the site's theme attribute."""
    response = client.get("/portal/")
    assert response.status_code == 200
    body = response.content.decode()
    assert 'id="portal-root"' in body
    assert 'data-theme="sierra"' in body


@pytest.mark.parametrize(
    "path", ["/portal/", "/portal/login", "/portal/admin/members/42", "/portal/anything/deep"]
)
def test_portal_catch_all(client: Client, site_settings: SiteSettings, path: str) -> None:
    """Every client-side route must serve the same shell."""
    assert client.get(path).status_code == 200


def test_portal_theme_follows_site_settings(client: Client, site_settings: SiteSettings) -> None:
    """The portal shell's ``data-theme`` attribute follows a changed site setting."""
    site_settings.theme = "night"
    site_settings.save(update_fields=["theme"])
    assert 'data-theme="night"' in client.get("/portal/").content.decode()


@pytest.mark.needs_frontend_build
def test_portal_shell_includes_the_portal_bundle(
    client: Client, site_settings: SiteSettings
) -> None:
    """The built shell references the portal bundle's script and stylesheet files."""
    body = client.get("/portal/").content.decode()
    entry = manifest_entry("src/portal/main.tsx")
    assert entry["file"] in body
    assert '<script type="module"' in body
    for css in entry.get("css", []):
        assert css in body


def test_portal_shell_installs_the_react_refresh_preamble(
    client: Client, site_settings: SiteSettings, vite_dev_mode: None
) -> None:
    """Against the dev server the preamble must run before any module that uses it."""
    body = client.get("/portal/").content.decode()
    assert "window.$RefreshReg$" in body
    assert body.index("RefreshRuntime") < body.index("@vite/client")
    assert body.index("@vite/client") < body.index("src/portal/main.tsx")


def test_portal_shell_has_no_react_refresh_preamble_in_production(
    client: Client, site_settings: SiteSettings
) -> None:
    """The built bundle needs no refresh runtime, so the tag renders nothing."""
    assert "RefreshRuntime" not in client.get("/portal/").content.decode()


def test_home_page_renders(
    client: Client, home_page: HomePage, site_settings: SiteSettings
) -> None:
    """The home page renders CalDART's name, skip link and site navigation."""
    response = client.get("/")
    assert response.status_code == 200
    body = response.content.decode()
    assert "CalDART" in body
    assert 'class="skip-link"' in body
    assert "data-site-nav" in body


def test_home_page_nav_comes_from_the_context_processor(
    client: Client, home_page: HomePage, site_settings: SiteSettings
) -> None:
    """The home page's nav links to the join and log-in portal routes."""
    body = client.get("/").content.decode()
    assert 'href="/portal/join"' in body
    assert 'href="/portal/login"' in body


@pytest.mark.needs_frontend_build
def test_home_page_includes_the_site_bundle(
    client: Client, home_page: HomePage, site_settings: SiteSettings
) -> None:
    """The built home page references the site bundle's script file."""
    body = client.get("/").content.decode()
    assert manifest_entry("src/site/main.ts")["file"] in body


def test_wagtail_admin_login_page(client: Client) -> None:
    """The Wagtail admin login page answers 200."""
    response = client.get("/admin/login/")
    assert response.status_code == 200


def test_django_admin_login_page(client: Client) -> None:
    """The Django admin login page answers 200."""
    response = client.get("/django-admin/login/")
    assert response.status_code == 200


def test_apple_pay_association_is_404_when_unconfigured(client: Client, settings: Settings) -> None:
    """The Apple Pay domain association file answers 404 when unconfigured."""
    settings.STRIPE_APPLE_PAY_DOMAIN_ASSOCIATION = ""
    assert (
        client.get("/.well-known/apple-developer-merchantid-domain-association").status_code == 404
    )


def test_apple_pay_association_serves_the_file(
    client: Client, settings: Settings, tmp_path: Path
) -> None:
    """The Apple Pay domain association route serves the configured file's bytes."""
    path = tmp_path / "association.txt"
    path.write_text("7B227073...")
    settings.STRIPE_APPLE_PAY_DOMAIN_ASSOCIATION = str(path)
    response = client.get("/.well-known/apple-developer-merchantid-domain-association")
    assert response.status_code == 200
    assert response.content.decode() == "7B227073..."
