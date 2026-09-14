"""Template context shared by every server-rendered page.

``nav`` is a plain list of dicts so ``templates/base.html`` never has to know
how the menu is assembled: the live top-level pages flagged *show in menus*,
then the two portal actions every visitor needs.
"""

from __future__ import annotations

from django.http import HttpRequest
from wagtail.models import Page, Site

from apps.accounts.roles import SYSTEM_ADMIN, WEBSITE_ADMIN


def site_chrome(request: HttpRequest) -> dict:
    from apps.cms.models import DEFAULT_THEME, get_site_settings

    settings_obj = get_site_settings(request)

    return {
        "site_settings": settings_obj,
        "theme": (settings_obj.theme if settings_obj else DEFAULT_THEME) or DEFAULT_THEME,
        "nav": build_nav(request),
        "can_preview_theme": can_preview_theme(getattr(request, "user", None)),
    }


def can_preview_theme(user) -> bool:
    """Website and system administrators may preview a theme with ``?theme=``."""
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    has_any_role = getattr(user, "has_any_role", None)
    return bool(has_any_role and has_any_role(WEBSITE_ADMIN, SYSTEM_ADMIN))


def menu_pages(request: HttpRequest):
    """Live top-level pages flagged *show in menus*, in tree order."""
    site = Site.find_for_request(request)
    root = site.root_page if site else None
    if root is None:
        return Page.objects.none()
    return Page.objects.child_of(root).live().public().in_menu().order_by("path")


def build_nav(request: HttpRequest) -> list[dict]:
    """Top navigation entries.

    Wagtail pages come first as ``kind="page"``; the portal links follow as
    ``kind="portal"`` so the template can set them apart as actions.
    """
    entries: list[dict] = [
        {"title": page.title, "url": page.url, "active": False, "kind": "page"}
        for page in menu_pages(request)
    ]

    entries.append({"title": "Join", "url": "/portal/join", "active": False, "kind": "portal"})
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        entries.append({"title": "Members", "url": "/portal/", "active": False, "kind": "portal"})
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
