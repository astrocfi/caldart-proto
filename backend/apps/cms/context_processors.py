"""Template context shared by every server-rendered page.

``nav`` is a plain list of dicts so ``templates/base.html`` never has to know
how the menu is assembled: the live top-level pages flagged *show in menus*,
then the two portal actions every visitor needs.
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


class NavEntry(TypedDict):
    """One entry of the top navigation."""

    title: str
    url: str
    active: bool
    kind: str


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


def build_nav(request: HttpRequest) -> list[NavEntry]:
    """Top navigation entries.

    Wagtail pages come first as ``kind="page"``; the portal links follow as
    ``kind="portal"`` so the template can set them apart as actions.  Join is
    always offered; the second portal link is ``PORTAL_TITLE`` for a signed-in
    reader and Log in for everybody else.  An entry is ``active`` when the request path
    starts with its URL, which never marks the home page's own ``/``.
    """
    entries: list[NavEntry] = [
        {"title": page.title, "url": page.url, "active": False, "kind": "page"}
        for page in menu_pages(request)
    ]

    entries.append({"title": "Join", "url": "/portal/join", "active": False, "kind": "portal"})
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        entries.append(
            {"title": PORTAL_TITLE, "url": "/portal/", "active": False, "kind": "portal"}
        )
    else:
        entries.append(
            {"title": "Log in", "url": "/portal/login", "active": False, "kind": "portal"}
        )

    path = request.path
    for entry in entries:
        url = entry["url"]
        if url and url != "/" and path.startswith(url):
            entry["active"] = True
    return entries
