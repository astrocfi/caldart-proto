"""Wagtail hooks for the public site and the Wagtail admin's menu.

The settings menu drops Wagtail's Users and Groups entries: accounts and roles are
managed in the portal alone, and ``caldart.urls`` closes those screens.

The members-only wall covers page rendering; this covers the files those pages
link to.  Wagtail runs every ``before_serve_document`` hook before it hands a
document over, so a download from the ``Members only`` collection -- or from any
collection beneath it -- is answered with the wall and HTTP 403 unless the reader
passes ``user_can_access_members_content``.  Documents in every other collection
stay public.

The guard only bites when document URLs point at Django, which is what
``WAGTAILDOCS_SERVE_METHOD = "serve_view"`` guarantees; the deployment configs in
``deploy/`` keep the files themselves unreachable under ``/media/documents/``.
"""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.template.response import TemplateResponse
from wagtail import hooks
from wagtail.admin.menu import MenuItem
from wagtail.documents.models import Document

from apps.cms.models import (
    collection_is_members_only,
    members_wall_context,
    user_can_access_members_content,
)


# Wagtail ships no type information, so its hook registry is untyped.
@hooks.register("before_serve_document")  # type: ignore[untyped-decorator]
def guard_members_only_documents(document: Document, request: HttpRequest) -> HttpResponse | None:
    """Answer a members-only download with the wall, or ``None`` to let it through.

    A document outside the ``Members only`` collection subtree is always let
    through, as is one requested by a reader with members-only access.  Everyone
    else gets ``cms/members_only_wall.html`` with HTTP 403 and the document's
    title; the file's bytes are never sent.
    """
    if not collection_is_members_only(document.collection):
        return None
    if user_can_access_members_content(request.user):
        return None

    # The wall template titles the response from ``page.title``; a document has
    # nothing else of a page, and its title is safe to show -- knowing a file
    # exists is not the secret, its contents are.
    context = {"page": {"title": document.title}, **members_wall_context(request.user)}
    return TemplateResponse(request, "cms/members_only_wall.html", context, status=403)


#: The settings-menu entries that would open Wagtail's account and role screens.
ACCOUNT_MENU_ITEMS: frozenset[str] = frozenset({"users", "groups"})


# Wagtail ships no type information, so its hook registry is untyped.
@hooks.register("construct_settings_menu")  # type: ignore[untyped-decorator]
def hide_account_menu_items(request: HttpRequest, menu_items: list[MenuItem]) -> None:
    """Remove the Users and Groups entries from the Wagtail settings menu, in place."""
    menu_items[:] = [item for item in menu_items if item.name not in ACCOUNT_MENU_ITEMS]
