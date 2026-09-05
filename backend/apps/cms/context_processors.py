"""Template context shared by every server-rendered page.

``nav`` is a plain list of ``{"title", "url", "active"}`` dicts so
``templates/base.html`` never has to know how the menu is assembled;
``feat/cms-site`` replaces the source of that list with the Wagtail page tree.
"""

from __future__ import annotations

from django.http import HttpRequest
from wagtail.models import Page, Site


def site_chrome(request: HttpRequest) -> dict:
    from apps.cms.models import DEFAULT_THEME, get_site_settings

    settings_obj = get_site_settings(request)

    return {
        "site_settings": settings_obj,
        "theme": (settings_obj.theme if settings_obj else DEFAULT_THEME) or DEFAULT_THEME,
        "nav": build_nav(request),
    }


def build_nav(request: HttpRequest) -> list[dict]:
    """Top navigation entries.

    Wagtail pages flagged ``show_in_menus`` come first, then the portal links
    every visitor needs (PLAN §7).
    """
    entries: list[dict] = []

    site = Site.find_for_request(request)
    root = site.root_page if site else None
    if root is not None:
        pages = Page.objects.child_of(root).live().in_menu()
        entries.extend({"title": p.title, "url": p.url, "active": False} for p in pages)

    entries.append({"title": "Join", "url": "/portal/join", "active": False})
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        entries.append({"title": "Members", "url": "/portal/", "active": False})
    else:
        entries.append({"title": "Log in", "url": "/portal/login", "active": False})

    path = request.path
    for entry in entries:
        url = entry["url"]
        if url and url != "/" and path.startswith(url):
            entry["active"] = True
    return entries
