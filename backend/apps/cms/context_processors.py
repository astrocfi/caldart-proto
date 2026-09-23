"""Template context shared by every server-rendered page.

``nav`` is a plain list of dicts so ``templates/base.html`` never has to know
how the menu is assembled: Home, the live top-level pages flagged *show in
menus* with their children, then the members-only pages and the portal link.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from django.contrib.auth.models import AnonymousUser
from django.db.models import QuerySet
from django.http import HttpRequest
from wagtail.models import Page, Site

from apps.accounts.models import User
from apps.accounts.roles import SYSTEM_ADMIN, WEBSITE_ADMIN

#: What the signed-in reader's portal link is called.  Not "Members": a site
#: whose members area is a content page would then carry that word twice.
PORTAL_TITLE = "Member portal"

if TYPE_CHECKING:
    from apps.cms.models import SiteSettings


class NavChild(TypedDict):
    """One entry of a menu page's drop-down."""

    title: str
    url: str


class NavEntry(TypedDict):
    """One entry of the top navigation."""

    title: str
    url: str
    active: bool
    kind: str
    children: list[NavChild]


class SiteChrome(TypedDict):
    """The template context every server-rendered page shares."""

    site_settings: SiteSettings | None
    theme: str
    nav: list[NavEntry]
    can_preview_theme: bool


def site_chrome(request: HttpRequest) -> SiteChrome:
    """The chrome context for ``request``.

    ``site_settings`` is the settings row, or ``None`` before ``migrate`` has
    created the site.  ``theme`` falls back to ``duty`` when the row is missing
    or its theme is blank.  ``nav`` is the same list ``build_nav`` returns, and
    ``can_preview_theme`` says whether the reader may override the theme with
    ``?theme=``.
    """
    from apps.cms.models import DEFAULT_THEME, get_site_settings

    settings_obj = get_site_settings(request)

    return {
        "site_settings": settings_obj,
        "theme": (settings_obj.theme if settings_obj else DEFAULT_THEME) or DEFAULT_THEME,
        "nav": build_nav(request),
        "can_preview_theme": can_preview_theme(getattr(request, "user", None)),
    }


def can_preview_theme(user: User | AnonymousUser | None) -> bool:
    """Website and system administrators may preview a theme with ``?theme=``.

    ``None`` and anonymous visitors are refused, as is a signed-in account holding
    neither role.  Superusers are always allowed.
    """
    if user is None or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.has_any_role(WEBSITE_ADMIN, SYSTEM_ADMIN)


def menu_pages(request: HttpRequest) -> QuerySet[Page]:
    """Live top-level pages flagged *show in menus*, in tree order.

    Only the children of the site's root page are listed, and only those that are
    live, public, and flagged for menus.  An empty queryset comes back when
    ``request`` matches no Wagtail site; every site has a root page.
    """
    site = Site.find_for_request(request)
    if site is None:
        empty: QuerySet[Page] = Page.objects.none()
        return empty
    pages: QuerySet[Page] = (
        Page.objects.child_of(site.root_page).live().public().in_menu().order_by("path")
    )
    return pages


def child_entries(page: Page) -> list[NavChild]:
    """The live, public, in-menu children of ``page``, in tree order."""
    return [
        {"title": child.title, "url": child.url or "#"}
        for child in page.get_children().live().public().in_menu().order_by("path")
    ]


def build_nav(request: HttpRequest) -> list[NavEntry]:
    """Top navigation entries.

    Home comes first, then the live top-level pages flagged *show in menus* as
    ``kind="page"``, each carrying its own in-menu children as ``children`` for a
    drop-down.  A page behind the members-only wall is moved to the end as
    ``kind="portal"``, beside the portal link itself, which is the member portal
    for a signed-in reader and Log in for everybody else.  An entry is ``active``
    when the request path starts with its URL, and the home entry only when the
    path is exactly ``/``.
    """
    pages: list[NavEntry] = []
    members_only: list[NavEntry] = []
    for page in menu_pages(request):
        entry: NavEntry = {
            "title": page.title,
            "url": page.url or "#",
            "active": False,
            "kind": "portal" if getattr(page.specific_deferred, "members_only", False) else "page",
            "children": child_entries(page),
        }
        (members_only if entry["kind"] == "portal" else pages).append(entry)

    home: NavEntry = {
        "title": "Home",
        "url": "/",
        "active": request.path == "/",
        "kind": "page",
        "children": [],
    }
    entries: list[NavEntry] = [home, *pages, *members_only]

    user = getattr(request, "user", None)
    signed_in = user is not None and user.is_authenticated
    entries.append(
        {
            "title": PORTAL_TITLE if signed_in else "Log in",
            "url": "/portal/" if signed_in else "/portal/login",
            "active": False,
            "kind": "portal",
            "children": [],
        }
    )

    path = request.path
    for entry in entries:
        url = entry["url"]
        if url and url != "/" and path.startswith(url):
            entry["active"] = True
    return entries
