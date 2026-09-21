"""The Content-Security-Policy header every response carries.

The policy is enforced, never report-only.  Every response outside the Wagtail
admin carries the site policy; the Wagtail admin's ``script-src`` is replaced
with ``'self' 'unsafe-inline'`` because Wagtail's admin templates inline
scripts, and its other directives are untouched.
"""

from __future__ import annotations

import importlib
import re
from collections.abc import Iterator
from types import ModuleType
from urllib.parse import urlparse

import pytest
from csp.middleware import CSPMiddleware
from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseBase
from django.test import Client, RequestFactory
from django.urls import set_script_prefix

from apps.accounts.models import User
from apps.cms.models import HomePage, SiteSettings
from caldart.middleware import WagtailAdminCspMiddleware

pytestmark = pytest.mark.django_db

#: Where ``make dev-frontend`` serves modules from, and its hot-reload socket.
VITE_DEV_SERVER = "http://localhost:5173"
VITE_HMR_SOCKET = "ws://localhost:5173"

#: The three hosts PayPal's own Content-Security-Policy page names for the
#: JavaScript SDK, which every one of the four resource directives repeats.
PAYPAL = ["https://*.paypal.com", "https://*.paypalobjects.com", "https://*.venmo.com"]

#: The policy every response outside the Wagtail admin carries, directive by
#: directive.  django-csp joins the directives in an unordered sweep, so the
#: tests compare the parsed mapping rather than one header string.
SITE_POLICY = {
    "default-src": ["'self'"],
    "script-src": [
        "'self'",
        "https://js.stripe.com",
        "https://*.js.stripe.com",
        *PAYPAL,
    ],
    "frame-src": [
        "'self'",
        "https://js.stripe.com",
        "https://*.js.stripe.com",
        "https://hooks.stripe.com",
        "https://link.com",
        "https://*.link.com",
        *PAYPAL,
    ],
    "connect-src": [
        "'self'",
        "https://api.stripe.com",
        "https://link.com",
        "https://*.link.com",
        *PAYPAL,
    ],
    "img-src": ["'self'", "data:", "https://*.link.com", *PAYPAL],
    "style-src": ["'self'", "'unsafe-inline'"],
}

#: The Wagtail admin's policy: the site policy with ``script-src`` replaced.
ADMIN_POLICY = {**SITE_POLICY, "script-src": ["'self'", "'unsafe-inline'"]}

#: The ``src`` of every ``<img>`` a rendered page draws.
IMG_SRC = re.compile(r"<img\b[^>]*?\bsrc=\"([^\"]*)\"", re.IGNORECASE)

#: What ``caldart.settings.dev`` adds so the Vite dev server can serve the
#: modules, the hot-reload client, its socket and React Fast Refresh's inline
#: preamble.
DEV_POLICY = {
    **SITE_POLICY,
    "default-src": [*SITE_POLICY["default-src"], VITE_DEV_SERVER],
    "script-src": [*SITE_POLICY["script-src"], VITE_DEV_SERVER, "'unsafe-inline'"],
    "connect-src": [*SITE_POLICY["connect-src"], VITE_DEV_SERVER, VITE_HMR_SOCKET],
    "img-src": [*SITE_POLICY["img-src"], VITE_DEV_SERVER],
}


@pytest.fixture(scope="module")
def dev_settings() -> ModuleType:
    """Import ``caldart.settings.dev`` as a module, without switching onto it.

    Importing it executes the module, so a policy edit that reached back into
    the base module's own dict would corrupt the settings this suite runs
    under -- which is what ``test_dev_settings_leave_the_running_policy_alone``
    watches for.
    """
    return importlib.import_module("caldart.settings.dev")


@pytest.fixture
def script_prefix() -> Iterator[None]:
    """Resolve URLs under ``/app/`` for one test, as a WSGI ``SCRIPT_NAME`` would.

    The prefix is process-wide thread-local state that no fixture manages, so
    it is put back afterwards.
    """
    set_script_prefix("/app/")
    try:
        yield
    finally:
        set_script_prefix("/")


def directives(response: HttpResponseBase) -> dict[str, list[str]]:
    """Parse a response's Content-Security-Policy header into directive -> sources.

    Raises ``KeyError`` when the response carries no enforced policy, which is
    itself the failure a caller wants to see.
    """
    header = response.headers["Content-Security-Policy"]
    parsed: dict[str, list[str]] = {}
    for part in header.split(";"):
        name, _, sources = part.strip().partition(" ")
        parsed[name] = sources.split()
    return parsed


def policy_for(request: HttpRequest) -> dict[str, list[str]]:
    """The policy the CSP middleware pair writes for one request, parsed by directive.

    Stacks ``caldart.middleware.WagtailAdminCspMiddleware`` under
    ``csp.middleware.CSPMiddleware`` the way ``MIDDLEWARE`` orders them, around
    a view that answers an empty 200.  Use it where the request has to carry a
    WSGI environment the test client cannot produce.
    """
    stack = CSPMiddleware(WagtailAdminCspMiddleware(lambda _request: HttpResponse()))
    response = stack(request)
    assert isinstance(response, HttpResponseBase)
    return directives(response)


def offsite_image_sources(body: str) -> list[str]:
    """The ``src`` of every ``<img>`` in rendered HTML that ``img-src`` refuses.

    A source is allowed when it is a ``data:`` URI or carries neither a scheme
    nor a host, which is every path the site serves itself.  A protocol-relative
    ``//host/path`` carries a host, so it is reported.
    """
    offsite: list[str] = []
    for source in IMG_SRC.findall(body):
        if source.startswith("data:"):
            continue
        parsed = urlparse(source)
        if parsed.scheme != "" or parsed.netloc != "":
            offsite.append(source)
    return offsite


def test_public_page_carries_the_site_policy(
    client: Client, home_page: HomePage, site_settings: SiteSettings
) -> None:
    """The public home page carries the site policy, directive for directive."""
    response = client.get("/")
    assert response.status_code == 200
    assert directives(response) == SITE_POLICY


def test_portal_shell_carries_the_site_policy(client: Client) -> None:
    """The portal SPA mount carries the same site policy as the public site."""
    response = client.get("/portal/login")
    assert response.status_code == 200
    assert directives(response) == SITE_POLICY


def test_api_response_carries_the_site_policy(client: Client) -> None:
    """An API response carries the site policy too, not only the rendered shells."""
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 204
    assert directives(response) == SITE_POLICY


def test_wagtail_admin_replaces_script_src_with_unsafe_inline(
    client: Client, superuser: User, home_page: HomePage
) -> None:
    """The Wagtail admin's script-src is exactly ``'self' 'unsafe-inline'``."""
    client.force_login(superuser)
    response = client.get("/admin/")
    assert response.status_code == 200
    assert directives(response)["script-src"] == ["'self'", "'unsafe-inline'"]


def test_wagtail_admin_keeps_every_other_directive(
    client: Client, superuser: User, home_page: HomePage
) -> None:
    """Relaxing the admin's script-src leaves the rest of the policy alone."""
    client.force_login(superuser)
    response = client.get("/admin/")
    assert directives(response) == ADMIN_POLICY


def test_wagtail_admin_draws_images_only_from_allowed_sources(
    client: Client, superuser: User, home_page: HomePage
) -> None:
    """No image on an admin page comes from an origin ``img-src`` refuses."""
    client.force_login(superuser)
    response = client.get("/admin/")
    assert offsite_image_sources(response.content.decode()) == []


def test_wagtail_admin_avatar_comes_from_the_site_itself(
    client: Client, superuser: User, home_page: HomePage
) -> None:
    """The account avatar is CalDART's own static image, not a Gravatar one."""
    client.force_login(superuser)
    response = client.get("/admin/")
    sources = IMG_SRC.findall(response.content.decode())
    assert [src for src in sources if "default-user-avatar" in src] != []


def test_wagtail_admin_login_page_is_relaxed_too(client: Client) -> None:
    """The relaxation follows the path, so the signed-out admin login page has it."""
    response = client.get("/admin/login/")
    assert response.status_code == 200
    assert directives(response)["script-src"] == ["'self'", "'unsafe-inline'"]


def test_django_admin_keeps_the_site_script_src(client: Client, superuser: User) -> None:
    """The relaxation stops at the Wagtail admin: /django-admin/ keeps the site policy."""
    client.force_login(superuser)
    response = client.get("/django-admin/")
    assert response.status_code == 200
    assert directives(response) == SITE_POLICY


def test_wagtail_admin_is_relaxed_under_a_wsgi_script_prefix(
    rf: RequestFactory, script_prefix: None
) -> None:
    """A site mounted below the domain root keeps the admin's relaxed script-src.

    Serving CalDART under a WSGI ``SCRIPT_NAME`` of ``/app`` puts the Wagtail
    admin at ``/app/admin/``: the request's path carries that prefix while its
    path info does not, and the relaxation has to follow the prefixed path.
    """
    policy = policy_for(rf.get("/admin/", SCRIPT_NAME="/app"))
    assert policy["script-src"] == ["'self'", "'unsafe-inline'"]


def test_site_policy_holds_outside_the_admin_under_a_script_prefix(
    rf: RequestFactory, script_prefix: None
) -> None:
    """Under the same prefix, a page outside the admin still gets the site policy."""
    assert policy_for(rf.get("/portal/login", SCRIPT_NAME="/app")) == SITE_POLICY


def test_no_report_only_header_is_sent(client: Client) -> None:
    """The policy is enforced, so no report-only header accompanies it."""
    response = client.get("/portal/login")
    assert "Content-Security-Policy-Report-Only" not in response.headers


def test_dev_settings_allow_the_vite_dev_server(dev_settings: ModuleType) -> None:
    """Development adds the Vite origin, its socket and the Fast Refresh preamble."""
    assert dev_settings.CONTENT_SECURITY_POLICY["DIRECTIVES"] == DEV_POLICY


def test_dev_settings_leave_the_running_policy_alone(dev_settings: ModuleType) -> None:
    """The development additions are a copy: the policy in force is unchanged."""
    assert settings.CONTENT_SECURITY_POLICY["DIRECTIVES"] == SITE_POLICY
