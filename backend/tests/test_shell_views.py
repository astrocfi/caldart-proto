"""The server-rendered shells: home page and the portal SPA mount.

These run whether or not the frontend has been built — ``conftest.py`` stubs
the Vite manifest when there is no real build, and the two tests that assert on
the actual bundle skip unless ``frontend_is_built``.
"""

from __future__ import annotations

import json

import pytest

from tests.conftest import VITE_MANIFEST

pytestmark = pytest.mark.django_db


def manifest_entry(source: str) -> dict:
    return json.loads(VITE_MANIFEST.read_text())[source]


def test_portal_shell_renders(client, site_settings):
    response = client.get("/portal/")
    assert response.status_code == 200
    body = response.content.decode()
    assert 'id="portal-root"' in body
    assert 'data-theme="sierra"' in body


@pytest.mark.parametrize(
    "path", ["/portal/", "/portal/login", "/portal/admin/members/42", "/portal/anything/deep"]
)
def test_portal_catch_all(client, site_settings, path):
    """Every client-side route must serve the same shell."""
    assert client.get(path).status_code == 200


def test_portal_theme_follows_site_settings(client, site_settings):
    site_settings.theme = "night"
    site_settings.save(update_fields=["theme"])
    assert 'data-theme="night"' in client.get("/portal/").content.decode()


def test_portal_shell_includes_the_portal_bundle(client, site_settings, frontend_is_built):
    if not frontend_is_built:
        pytest.skip("frontend/dist not built (run `make build`)")
    body = client.get("/portal/").content.decode()
    entry = manifest_entry("src/portal/main.tsx")
    assert entry["file"] in body
    assert '<script type="module"' in body
    for css in entry.get("css", []):
        assert css in body


def test_home_page_renders(client, home_page, site_settings):
    response = client.get("/")
    assert response.status_code == 200
    body = response.content.decode()
    assert "CalDART" in body
    assert 'class="skip-link"' in body
    assert "data-site-nav" in body


def test_home_page_nav_comes_from_the_context_processor(client, home_page, site_settings):
    body = client.get("/").content.decode()
    assert 'href="/portal/join"' in body
    assert 'href="/portal/login"' in body


def test_home_page_includes_the_site_bundle(client, home_page, site_settings, frontend_is_built):
    if not frontend_is_built:
        pytest.skip("frontend/dist not built (run `make build`)")
    body = client.get("/").content.decode()
    assert manifest_entry("src/site/main.ts")["file"] in body


def test_wagtail_admin_login_page(client):
    response = client.get("/admin/login/")
    assert response.status_code == 200


def test_django_admin_login_page(client):
    response = client.get("/django-admin/login/")
    assert response.status_code == 200


def test_apple_pay_association_is_404_when_unconfigured(client, settings):
    settings.STRIPE_APPLE_PAY_DOMAIN_ASSOCIATION = ""
    assert (
        client.get("/.well-known/apple-developer-merchantid-domain-association").status_code == 404
    )


def test_apple_pay_association_serves_the_file(client, settings, tmp_path):
    path = tmp_path / "association.txt"
    path.write_text("7B227073...")
    settings.STRIPE_APPLE_PAY_DOMAIN_ASSOCIATION = str(path)
    response = client.get("/.well-known/apple-developer-merchantid-domain-association")
    assert response.status_code == 200
    assert response.content.decode() == "7B227073..."
