"""Serving the site under a URL prefix such as ``/caldart-proto``.

``URL_PREFIX`` is read once, in ``caldart/settings/base.py``: it becomes
``FORCE_SCRIPT_NAME``, so ``reverse()``, ``static()`` and ``{% url %}`` carry it, and
the login and logout redirects are built from it.  The web server in front strips the
prefix before proxying, so Django routes on the path below it and puts the prefix
back on every URL it writes.  These tests cover the setting, the URLs Django builds,
the two HTML shells and their links, the example content ``seed_content`` writes, the
email links, and the production check that ``SITE_URL`` ends in the same prefix.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import re
import sys
from collections.abc import Iterator
from io import StringIO
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from django.apps import apps as django_apps
from django.conf import settings as django_settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.template.loader import get_template
from django.templatetags.static import static
from django.test import Client
from django.urls import reverse, set_script_prefix
from pytest_django.fixtures import Settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.cms import seed_content_data as content
from apps.cms.models import ContactPage, DonatePage, HomePage, SiteSettings
from apps.cms.seed import ensure_site_root
from apps.members.models import MembershipPlan
from apps.notifications.events import EVENTS
from apps.notifications.messages import build_message
from caldart.settings.base import normalize_url_prefix
from tests.factories import (
    AircraftFactory,
    DartFactory,
    MembershipFactory,
    PaymentFactory,
    RenewalMandateFactory,
    UserFactory,
    expire_membership,
    grant_membership,
    make_dart_index,
    make_standard_page,
)

pytestmark = pytest.mark.django_db

#: The prefix these tests serve the site under.  A test value only: production code
#: never names it.
PREFIX = "/caldart-proto"

#: The prefix the rest of the suite runs with, put back after a test changes it.
SUITE_URL_PREFIX: str = django_settings.URL_PREFIX

SETTINGS_DIR = Path(__file__).resolve().parents[1] / "caldart" / "settings"

#: A root-relative URL in an ``href``, ``src`` or ``action`` attribute, or in a
#: ``data-*-url`` attribute a script fetches or navigates to.
ROOT_RELATIVE_URL = re.compile(r'(?:href|src|action|data-[a-z-]*url)="(/[^"]*)"')

#: A production environment that satisfies every required variable of ``prod.py``.
PRODUCTION_ENV = {
    "SECRET_KEY": "prod-secret-not-a-real-key",
    "ALLOWED_HOSTS": "caldart.example.org",
    "EMAIL_URL": "smtp://localhost:25",
    "DATABASE_URL": "postgres://caldart:caldart@db.example.org:5432/caldart",
}

#: Variables that would otherwise leak from a developer's shell or ``.env`` into the
#: settings these tests execute afresh.
CLEARED_ENV = ["URL_PREFIX", "SITE_URL", "CSRF_TRUSTED_ORIGINS"]


def unprefixed_links(body: str) -> list[str]:
    """Each root-relative link or ``data-*-url`` in ``body`` that is off the prefix."""
    return [url for url in ROOT_RELATIVE_URL.findall(body) if not url.startswith(f"{PREFIX}/")]


def execute_base_settings() -> ModuleType:
    """Execute ``settings/base.py`` as a throwaway module and return it.

    The module is loaded under its own name, outside ``sys.modules``, so the settings
    the suite runs under are left alone.
    """
    spec = importlib.util.spec_from_file_location("caldart_prefix_probe", SETTINGS_DIR / "base.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def import_production_settings() -> ModuleType:
    """Import ``caldart.settings.prod`` over a freshly executed ``base``.

    ``base`` reads ``URL_PREFIX`` at import, so it has to run again for the variable a
    test sets to reach ``prod``.  The modules the suite runs under are put back.
    """
    saved = {
        name: sys.modules.get(name) for name in ("caldart.settings.base", "caldart.settings.prod")
    }
    for name in saved:
        sys.modules.pop(name, None)
    try:
        return importlib.import_module("caldart.settings.prod")
    finally:
        for name, module in saved.items():
            sys.modules.pop(name, None)
            if module is not None:
                sys.modules[name] = module


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """No prefix, site URL or trusted origin in the environment until a test sets one."""
    for name in CLEARED_ENV:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


@pytest.fixture
def production_env(clean_env: pytest.MonkeyPatch) -> pytest.MonkeyPatch:
    """A minimal production environment; each test sets the prefix and the site URL."""
    for name, value in PRODUCTION_ENV.items():
        clean_env.setenv(name, value)
    return clean_env


@pytest.fixture
def prefixed(settings: Settings) -> Iterator[str]:
    """Serve the site under ``PREFIX`` for one test, as a production process would.

    ``FORCE_SCRIPT_NAME`` is what WSGI uses; the thread's script prefix is what
    ``reverse()`` reads, and Django's test client never sets it, so it is set here and
    put back afterwards.  ``STATIC_URL`` and ``MEDIA_URL`` are assigned again because
    Django computes their prefixed form once and caches it.
    """
    set_script_prefix(f"{PREFIX}/")
    settings.URL_PREFIX = PREFIX
    settings.FORCE_SCRIPT_NAME = PREFIX
    settings.SITE_URL = f"https://caldart.example.org{PREFIX}"
    settings.STATIC_URL = django_settings.STATIC_URL
    settings.MEDIA_URL = django_settings.MEDIA_URL
    yield PREFIX
    set_script_prefix("/")


@pytest.fixture
def prefixed_content(prefixed: str, settings: Settings) -> Iterator[ModuleType]:
    """The example content module, re-read so its links carry ``PREFIX``.

    The module is read again afterwards with the suite's own prefix, so later tests see
    the links they expect.
    """
    importlib.reload(content)
    yield content
    settings.URL_PREFIX = SUITE_URL_PREFIX
    importlib.reload(content)


# --------------------------------------------------------------------- setting
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", ""),
        ("/", ""),
        ("  ", ""),
        ("caldart-proto", "/caldart-proto"),
        ("/caldart-proto", "/caldart-proto"),
        ("/caldart-proto/", "/caldart-proto"),
        ("caldart-proto/", "/caldart-proto"),
        ("/dart/caldart-proto", "/dart/caldart-proto"),
        (" /caldart-proto ", "/caldart-proto"),
    ],
    ids=["empty", "slash", "blank", "bare", "leading", "both", "trailing", "two", "spaces"],
)
def test_the_prefix_is_normalized_to_a_leading_slash_and_no_trailing_one(
    raw: str, expected: str
) -> None:
    """Any spelling of a prefix reads as ``/segment[/segment]``, or empty for none."""
    assert normalize_url_prefix(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["//x//", "/a//b", "/a/../b", "/./a", "/a b", "https://example.org/x", "/a?b", "/a#b"],
    ids=["doubled", "empty-segment", "dot-dot", "dot", "space", "url", "query", "fragment"],
)
def test_a_malformed_prefix_is_refused(raw: str) -> None:
    """An empty segment, a dot segment, or a character a path forbids is refused."""
    with pytest.raises(ImproperlyConfigured, match="URL_PREFIX"):
        normalize_url_prefix(raw)


def test_with_no_prefix_the_site_is_served_from_the_root(clean_env: pytest.MonkeyPatch) -> None:
    """Unset, the prefix is empty and Django takes the script name from the request."""
    base = execute_base_settings()

    assert (base.URL_PREFIX, base.FORCE_SCRIPT_NAME) == ("", None)


def test_the_prefix_becomes_the_script_name(clean_env: pytest.MonkeyPatch) -> None:
    """``URL_PREFIX`` sets ``FORCE_SCRIPT_NAME`` to its normalized form."""
    clean_env.setenv("URL_PREFIX", "caldart-proto/")

    base = execute_base_settings()

    assert (base.URL_PREFIX, base.FORCE_SCRIPT_NAME) == (PREFIX, PREFIX)


@pytest.mark.parametrize(
    ("prefix", "expected"),
    [
        ("", ("/portal/login", "/portal/", "/")),
        (PREFIX, (f"{PREFIX}/portal/login", f"{PREFIX}/portal/", f"{PREFIX}/")),
    ],
    ids=["root", "prefixed"],
)
def test_the_login_and_logout_redirects_carry_the_prefix(
    clean_env: pytest.MonkeyPatch, prefix: str, expected: tuple[str, str, str]
) -> None:
    """``LOGIN_URL``, ``LOGIN_REDIRECT_URL`` and ``LOGOUT_REDIRECT_URL`` start with it."""
    clean_env.setenv("URL_PREFIX", prefix)

    base = execute_base_settings()

    assert expected == (base.LOGIN_URL, base.LOGIN_REDIRECT_URL, base.LOGOUT_REDIRECT_URL)


def test_the_default_trusted_origin_is_the_site_urls_scheme_and_host(
    clean_env: pytest.MonkeyPatch,
) -> None:
    """A browser's ``Origin`` carries no path, so the default trusted origin drops it."""
    clean_env.setenv("URL_PREFIX", PREFIX)
    clean_env.setenv("SITE_URL", f"https://caldart.example.org{PREFIX}")

    assert execute_base_settings().CSRF_TRUSTED_ORIGINS == ["https://caldart.example.org"]


# ------------------------------------------------------------------ production
@pytest.mark.parametrize(
    ("prefix", "site_url"),
    [
        ("", "https://caldart.example.org"),
        ("", "https://caldart.example.org/"),
        (PREFIX, f"https://caldart.example.org{PREFIX}"),
        (PREFIX, f"https://caldart.example.org{PREFIX}/"),
    ],
    ids=["root", "root-slash", "prefixed", "prefixed-slash"],
)
def test_production_accepts_a_site_url_whose_path_is_the_prefix(
    production_env: pytest.MonkeyPatch, prefix: str, site_url: str
) -> None:
    """A ``SITE_URL`` ending in the prefix, with or without a slash, starts cleanly."""
    production_env.setenv("URL_PREFIX", prefix)
    production_env.setenv("SITE_URL", site_url)

    assert (prefix or None) == import_production_settings().FORCE_SCRIPT_NAME


@pytest.mark.parametrize(
    ("prefix", "site_url"),
    [
        (PREFIX, "https://caldart.example.org"),
        ("", f"https://caldart.example.org{PREFIX}"),
        (PREFIX, "https://caldart.example.org/elsewhere"),
    ],
    ids=["prefix-only", "site-url-only", "different"],
)
def test_production_refuses_a_site_url_that_disagrees_with_the_prefix(
    production_env: pytest.MonkeyPatch, prefix: str, site_url: str
) -> None:
    """A ``SITE_URL`` whose path is not the prefix is a start-up error naming both."""
    production_env.setenv("URL_PREFIX", prefix)
    production_env.setenv("SITE_URL", site_url)

    with pytest.raises(ImproperlyConfigured, match=r"SITE_URL.*URL_PREFIX"):
        import_production_settings()


# ------------------------------------------------------------------------ URLs
def test_a_portal_route_is_reversed_under_the_prefix(prefixed: str) -> None:
    """``reverse()`` of a portal route starts with the prefix."""
    assert reverse("portal", kwargs={"path": "join"}) == f"{PREFIX}/portal/join"


def test_an_api_route_is_reversed_under_the_prefix(prefixed: str) -> None:
    """``reverse()`` of an API route starts with the prefix."""
    assert reverse("api:accounts:csrf") == f"{PREFIX}/api/v1/auth/csrf"


def test_a_static_url_carries_the_prefix(prefixed: str) -> None:
    """``static()`` writes the static URL under the prefix."""
    assert static("img/caldart-logo.png") == f"{PREFIX}/static/img/caldart-logo.png"


def test_a_media_url_carries_the_prefix(prefixed: str) -> None:
    """``MEDIA_URL`` reads under the prefix."""
    assert f"{PREFIX}/media/" == django_settings.MEDIA_URL


def test_without_a_prefix_static_and_media_urls_stay_at_the_root() -> None:
    """With no prefix, the static and media URLs are ``/static/`` and ``/media/``."""
    assert (django_settings.STATIC_URL, django_settings.MEDIA_URL) == ("/static/", "/media/")


def test_a_request_under_the_prefix_reaches_the_portal(
    client: Client, site_settings: SiteSettings, prefixed: str
) -> None:
    """The proxy strips the prefix; the portal shell answers the path below it."""
    response = client.get("/portal/login", SCRIPT_NAME=PREFIX)

    assert response.status_code == 200


def test_a_request_under_the_prefix_reaches_the_api(api_client: APIClient, prefixed: str) -> None:
    """The API answers the path below the prefix."""
    response = api_client.get("/api/v1/auth/csrf", SCRIPT_NAME=PREFIX)

    assert response.status_code == 204


def test_the_login_redirect_goes_to_the_prefixed_portal(
    client: Client, prefixed: str, settings: Settings
) -> None:
    """An anonymous reader of the guide is sent to the portal's login under the prefix."""
    settings.LOGIN_URL = f"{PREFIX}/portal/login"

    response = client.get("/docs/", SCRIPT_NAME=PREFIX)

    assert response["Location"] == f"{PREFIX}/portal/login?next={PREFIX}/docs/"


def test_the_site_config_links_every_page_under_the_prefix(
    api_client: APIClient,
    home_page: HomePage,
    prefixed: str,
    member: User,
    annual_plan: MembershipPlan,
) -> None:
    """The portal's nav and members-only links arrive with the prefix already on them."""
    make_standard_page(home_page, "about", "About", show_in_menus=True)
    make_standard_page(home_page, "inside", "Inside", members_only=True)
    grant_membership(member, annual_plan)
    api_client.force_login(member)

    body = api_client.get("/api/v1/site/config", SCRIPT_NAME=PREFIX).json()
    urls = [entry["url"] for entry in [*body["nav"], *body["members_pages"]]]

    assert urls == [
        f"{PREFIX}/",
        f"{PREFIX}/about/",
        f"{PREFIX}/portal/",
        f"{PREFIX}/inside/",
    ]


@pytest.mark.needs_frontend_build
def test_whitenoise_serves_a_hashed_asset_under_the_prefix(
    client: Client, prefixed: str, settings: Settings
) -> None:
    """A built bundle file answers at the static path below the prefix."""
    settings.WHITENOISE_USE_FINDERS = True
    manifest_path = Path(django_settings.DJANGO_VITE["default"]["manifest_path"])
    manifest: dict[str, dict[str, Any]] = json.loads(manifest_path.read_text())
    bundle = manifest["src/portal/main.tsx"]["file"]

    response = client.get(f"/static/{bundle}", SCRIPT_NAME=PREFIX)
    response.close()

    assert response.status_code == 200


# ---------------------------------------------------------------------- shells
@pytest.mark.parametrize(("use_prefix", "expected"), [(False, ""), (True, PREFIX)])
def test_the_portal_shell_names_the_prefix(
    client: Client,
    site_settings: SiteSettings,
    request: pytest.FixtureRequest,
    use_prefix: bool,
    expected: str,
) -> None:
    """``portal.html`` carries the prefix, or an empty one, on ``<html>``."""
    if use_prefix:
        request.getfixturevalue("prefixed")

    body = client.get("/portal/").content.decode()

    assert f'<html lang="en" data-url-prefix="{expected}"' in body


@pytest.mark.parametrize(("use_prefix", "expected"), [(False, ""), (True, PREFIX)])
def test_the_public_shell_names_the_prefix(
    client: Client,
    home_page: HomePage,
    site_settings: SiteSettings,
    request: pytest.FixtureRequest,
    use_prefix: bool,
    expected: str,
) -> None:
    """``base.html`` carries the prefix, or an empty one, on ``<html>``."""
    if use_prefix:
        request.getfixturevalue("prefixed")

    body = client.get("/").content.decode()

    assert f'<html lang="en" data-url-prefix="{expected}"' in body


def test_the_portal_shell_writes_every_link_under_the_prefix(
    client: Client, site_settings: SiteSettings, prefixed: str
) -> None:
    """The portal shell's bundle and stylesheet URLs all start with the prefix."""
    assert unprefixed_links(client.get("/portal/").content.decode()) == []


def test_the_home_page_writes_every_link_under_the_prefix(
    client: Client,
    home_page: HomePage,
    site_settings: SiteSettings,
    prefixed: str,
    member: User,
) -> None:
    """The masthead, navigation, sidebar, footer and assets all start with the prefix."""
    # The home page the migrations publish was stored with the suite's own prefix.
    HomePage.objects.filter(pk=home_page.pk).update(
        urgent_cta_url=f"{PREFIX}/contact/",
        primary_cta_url=f"{PREFIX}/portal/join",
        secondary_cta_url=f"{PREFIX}/about/",
    )
    make_dart_index(home_page)
    DartFactory()
    client.force_login(member)

    body = client.get("/").content.decode()

    assert unprefixed_links(body) == []


def test_the_donate_page_writes_every_link_under_the_prefix(
    client: Client, home_page: HomePage, site_settings: SiteSettings, prefixed: str
) -> None:
    """The donation form fetches its config, and returns the browser, under the prefix."""
    page = DonatePage(title="Donate", slug="donate", intro="<p>Every gift flies.</p>")
    home_page.add_child(instance=page)
    page.save_revision().publish()

    body = client.get("/donate/").content.decode()

    assert unprefixed_links(body) == []
    assert f'data-config-url="{PREFIX}/api/v1/donations/config"' in body


def test_the_home_pages_blank_buttons_fall_back_under_the_prefix(
    client: Client, home_page: HomePage, site_settings: SiteSettings, prefixed: str
) -> None:
    """A labeled button with no URL links the contact page, the join screen, or home."""
    HomePage.objects.filter(pk=home_page.pk).update(
        urgent_cta_label="Request air support",
        urgent_cta_url="",
        primary_cta_label="Join CalDART",
        primary_cta_url="",
        secondary_cta_label="About us",
        secondary_cta_url="",
    )

    body = client.get("/").content.decode()

    assert unprefixed_links(body) == []


def test_the_home_page_links_the_guide_and_the_portal_under_the_prefix(
    client: Client, home_page: HomePage, site_settings: SiteSettings, prefixed: str
) -> None:
    """The footer's user guide link and the sign-in link carry the prefix."""
    body = client.get("/").content.decode()

    assert f'href="{PREFIX}/docs/"' in body
    assert f'href="{PREFIX}/portal/login"' in body


def test_the_signed_in_greeting_follows_the_prefixed_portal_link(
    client: Client, home_page: HomePage, site_settings: SiteSettings, prefixed: str, member: User
) -> None:
    """Signed in, the portal entry greets the reader by name under a prefix too."""
    client.force_login(member)

    body = client.get("/").content.decode()

    assert f"Welcome, {member.first_name}" in body


def test_the_home_entry_is_current_on_the_prefixed_home_page(
    client: Client, home_page: HomePage, site_settings: SiteSettings, prefixed: str
) -> None:
    """The Home entry links the prefixed root and is marked as the current page there."""
    body = client.get("/").content.decode()

    assert f'<a href="{PREFIX}/" aria-current="page">Home</a>' in body


def test_the_not_found_page_writes_every_link_under_the_prefix(
    client: Client, home_page: HomePage, site_settings: SiteSettings, prefixed: str
) -> None:
    """The 404 page's home and portal buttons start with the prefix."""
    response = client.get("/no-such-page/")

    assert unprefixed_links(response.content.decode()) == []


def test_the_server_error_page_writes_every_link_under_the_prefix(prefixed: str) -> None:
    """The 500 page, rendered with no request at all, still links under the prefix."""
    body = get_template("500.html").render()

    assert unprefixed_links(body) == []


@pytest.mark.parametrize("state", ["anonymous", "friend"])
def test_the_members_only_wall_writes_every_link_under_the_prefix(
    client: Client,
    home_page: HomePage,
    site_settings: SiteSettings,
    prefixed: str,
    state: str,
) -> None:
    """The wall's sign-in, join, and portal buttons start with the prefix."""
    make_standard_page(home_page, "inside", "Inside", members_only=True)
    if state == "friend":
        client.force_login(UserFactory(kind="friend"))

    response = client.get("/inside/")

    assert unprefixed_links(response.content.decode()) == []


def test_the_members_only_wall_for_a_lapsed_member_links_under_the_prefix(
    client: Client,
    home_page: HomePage,
    site_settings: SiteSettings,
    prefixed: str,
    annual_plan: MembershipPlan,
) -> None:
    """A lapsed member's renew and portal buttons start with the prefix."""
    make_standard_page(home_page, "inside", "Inside", members_only=True)
    lapsed = UserFactory()
    expire_membership(lapsed, annual_plan)
    client.force_login(lapsed)

    response = client.get("/inside/")

    assert unprefixed_links(response.content.decode()) == []


def test_the_dart_finder_falls_back_to_the_prefixed_home_page(
    client: Client, home_page: HomePage, prefixed: str
) -> None:
    """With no DART directory published, the finder redirects to the prefixed root."""
    response = client.get("/find-dart/?dart=999", SCRIPT_NAME=PREFIX)

    assert response["Location"] == f"{PREFIX}/"


# --------------------------------------------------------------------- content
def test_a_new_home_page_links_the_join_screen_under_the_prefix(prefixed: str) -> None:
    """A home page made in the admin defaults its join button to the prefixed portal."""
    assert HomePage().primary_cta_url == f"{PREFIX}/portal/join"


def test_ensure_site_root_links_the_join_screen_under_the_prefix(prefixed: str) -> None:
    """A home page the seed has to create links its join button under the prefix."""
    HomePage.objects.all().delete()

    site = ensure_site_root()

    assert site.root_page.specific.primary_cta_url == f"{PREFIX}/portal/join"


def test_the_migrated_home_page_links_its_buttons_under_the_prefix(prefixed: str) -> None:
    """The home page ``migrate`` publishes links its two buttons under the prefix."""
    HomePage.objects.all().delete()
    site_root = importlib.import_module("apps.cms.migrations.0002_site_root")

    site_root.create_site_root(django_apps, None)

    home = HomePage.objects.get()
    assert (home.primary_cta_url, home.secondary_cta_url) == (
        f"{PREFIX}/portal/join",
        f"{PREFIX}/about/",
    )


@pytest.mark.slow
def test_seed_content_writes_its_links_under_the_prefix(prefixed_content: ModuleType) -> None:
    """The home page's buttons, a page's button, and the donate setting carry it."""
    call_command("seed_content", stdout=StringIO())

    home = HomePage.objects.get()
    contact = ContactPage.objects.get()
    stored = {
        "join button": home.primary_cta_url,
        "find your DART button": home.secondary_cta_url,
        "contact page buttons": [
            block.value["url"] for block in contact.body if block.block_type == "cta"
        ],
        "donate setting": SiteSettings.objects.get().donate_url,
    }

    assert stored == {
        "join button": f"{PREFIX}/portal/join",
        "find your DART button": f"{PREFIX}/about/darts/",
        "contact page buttons": [f"{PREFIX}/portal/"],
        "donate setting": f"{PREFIX}/donate/",
    }


@pytest.mark.slow
def test_seed_content_stores_rich_text_links_under_the_prefix(
    prefixed_content: ModuleType,
) -> None:
    """The donation page's rich text links the portal's Donate screen under the prefix."""
    call_command("seed_content", stdout=StringIO())

    assert f'href="{PREFIX}/portal/donate"' in DonatePage.objects.get().intro


# ---------------------------------------------------------------------- emails
def every_event_payload() -> dict[str, object]:
    """One payload holding every key any notification event reads."""
    user = UserFactory(first_name="Pat", last_name="Quill")
    actor = UserFactory(first_name="Lee", last_name="Boss")
    payment = PaymentFactory(user=user)
    return {
        "user": user,
        "actor": actor,
        "dart": DartFactory(),
        "how": "administrator",
        "payment": payment,
        "term": MembershipFactory(user=user, plan=payment.plan),
        "mandate": RenewalMandateFactory(user=user),
        "reason": "Card declined",
        "refund_cents": 4500,
        "added": [],
        "removed": [],
        "old_email": "old@example.test",
        "fields": [],
        "verified": [],
        "cleared": [],
        "aircraft": AircraftFactory(),
        "n_number": "N12345",
        "owner": user,
    }


def test_every_notification_link_starts_with_the_prefixed_site_url(prefixed: str) -> None:
    """Every event's email links under ``SITE_URL``, which carries the prefix."""
    payload = every_event_payload()
    links = {slug: build_message(slug, payload).link for slug in EVENTS}

    assert {
        slug: link
        for slug, link in links.items()
        if link != "" and not link.startswith(f"{django_settings.SITE_URL}/")
    } == {}


def test_notification_links_are_built_under_the_prefix(prefixed: str) -> None:
    """At least one event links into the prefixed portal, so the check above bites."""
    payload = every_event_payload()

    assert build_message("signed_up", payload).link.startswith(
        f"https://caldart.example.org{PREFIX}/portal/"
    )
