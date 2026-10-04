"""``/docs/`` for a visitor who is not signed in: the pages ``signed-out.json`` names.

The pages Help opens before anyone can sign in (signing in, a forgotten or reset
password, joining, and email verification) are served without sign-in, with every link
to another page of the guide taken out, and so are the ``_static/`` files they load.
Every other request from a signed-out visitor is sent to the portal's login page.  The
tests build a stand-in guide under ``tmp_path``, so they run whether or not the real
guide has been built.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest
from django.http import HttpResponseBase, StreamingHttpResponse
from django.test import Client
from pytest_django.fixtures import Settings

from apps.accounts.models import User
from apps.accounts.roles import SYSTEM_ADMIN
from caldart.views import GUIDE_INDEX, GUIDE_ROLES, GUIDE_SIGNED_OUT

pytestmark = pytest.mark.django_db

STYLESHEET = "body { color: black; }"

#: A link from the sign-in page to a page that needs sign-in.
PROFILE_LINK = '<a href="../profile/">My profile</a>'

#: A link from the sign-in page to another signed-out page.
FORGOT_LINK = '<a href="../forgot-password/">Forgot your password</a>'

#: A link from the sign-in page to the search page Sphinx writes.
SEARCH_LINK = '<a href="../../search/">Search</a>'

#: The sidebar's entry for the member screens' group page, which needs sign-in.
GROUP_LINK = '<a href="../">Your screens</a>'

#: The sidebar's search box, which submits to the search page.
SEARCH_FORM = '<form action="../../search/" method="get" role="search"></form>'

#: The links Sphinx puts in a page's head to the general index and the search page.
HEAD_INDEX_LINK = '<link href="../../genindex/" rel="index" title="Index"/>'
HEAD_SEARCH_LINK = '<link href="../../search/" rel="search" title="Search"/>'

#: The stand-in sign-in page: head links to the index and the search page; a sidebar
#: with the search box, a gated top-level entry, and the member group holding the page
#: itself, a signed-out page, and a gated one; then a sentence linking a gated page, a
#: signed-out one, and the search page.
SIGN_IN_HTML = (
    f"<html><head>{HEAD_INDEX_LINK}{HEAD_SEARCH_LINK}</head><body>"
    f"{SEARCH_FORM}"
    '<div class="sidebar-tree">'
    '<ul><li><a href="../../overview/">Overview</a></li></ul>'
    f"<ul><li>{GROUP_LINK}<ul>"
    '<li><a href="#">Sign in</a></li>'
    f"<li>{FORGOT_LINK}</li>"
    f"<li>{PROFILE_LINK}</li>"
    "</ul></li></ul>"
    "</div>"
    f"<p>See {PROFILE_LINK}, {FORGOT_LINK}, and {SEARCH_LINK}.</p>"
    "</body></html>"
)

FORGOT_HTML = "<h1>Forgot your password</h1>"
PROFILE_HTML = "<h1>My profile</h1>"
INDEX_HTML = "<h1>User guide</h1>"

#: The signed-out pages and every page of the stand-in, as the extension writes them.
SIGNED_OUT = {
    "signed_out": ["member/forgot-password", "member/sign-in"],
    "pages": [
        "index",
        "member/forgot-password",
        "member/index",
        "member/profile",
        "member/sign-in",
        "overview",
    ],
}


def _rewrite(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` and move its modification time on, like a rebuild."""
    path.write_text(text)
    later = path.stat().st_mtime + 10
    os.utime(path, (later, later))


def _write(root: Path, path: str, text: str) -> None:
    """Write ``text`` to the guide file ``path`` under ``root``, making its directory."""
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)


@pytest.fixture
def guide(tmp_path: Path, settings: Settings) -> Path:
    """A stand-in guide with two signed-out pages, a gated page, and the build's files."""
    root = tmp_path / "guide"
    _write(root, GUIDE_INDEX, INDEX_HTML)
    _write(root, f"member/{GUIDE_INDEX}", "<h1>Member screens</h1>")
    _write(root, f"member/sign-in/{GUIDE_INDEX}", SIGN_IN_HTML)
    _write(root, f"member/forgot-password/{GUIDE_INDEX}", FORGOT_HTML)
    _write(root, f"member/profile/{GUIDE_INDEX}", PROFILE_HTML)
    _write(root, f"search/{GUIDE_INDEX}", "<h1>Search</h1>")
    _write(root, "_static/styles.css", STYLESHEET)
    _write(root, "_images/diagram.svg", "<svg/>")
    _write(root, "searchindex.js", "Search.setIndex({})")
    _write(root, "objects.inv", "inventory")
    _write(root, GUIDE_ROLES, json.dumps({}))
    _write(root, GUIDE_SIGNED_OUT, json.dumps(SIGNED_OUT))
    settings.USER_GUIDE_ROOT = root
    return root


def body(response: HttpResponseBase) -> str:
    """The whole body of a streamed guide file, decoded."""
    assert isinstance(response, StreamingHttpResponse)
    # A synchronous StreamingHttpResponse yields bytes; the async branch of the
    # declared union cannot occur here.
    return b"".join(cast(Iterator[bytes], response.streaming_content)).decode()


@pytest.mark.parametrize(
    ("path", "expected"),
    [("member/sign-in/", "Forgot your password"), ("member/forgot-password/", FORGOT_HTML)],
    ids=["sign-in", "forgot-password"],
)
def test_a_signed_out_page_is_served_without_sign_in(
    client: Client, guide: Path, path: str, expected: str
) -> None:
    """A page ``signed-out.json`` names is served to a visitor who is not signed in."""
    response = client.get(f"/docs/{path}")
    assert response.status_code == 200
    assert expected in body(response)


def test_a_signed_out_page_named_by_its_file_is_served(client: Client, guide: Path) -> None:
    """``member/sign-in/index.html`` is the same page as ``member/sign-in/``."""
    response = client.get("/docs/member/sign-in/index.html")
    assert response.status_code == 200
    assert "Forgot your password" in body(response)


def test_a_signed_out_page_without_its_slash_redirects_to_the_slashed_form(
    client: Client, guide: Path
) -> None:
    """A signed-out page named without its trailing slash redirects, as when signed in."""
    response = client.get("/docs/member/sign-in")
    assert response.status_code == 302
    assert response.headers["Location"] == "/docs/member/sign-in/"


def test_a_signed_out_page_loses_its_links_to_gated_pages(client: Client, guide: Path) -> None:
    """Each link to a page that needs sign-in leaves the sidebar and the prose."""
    page = body(client.get("/docs/member/sign-in/"))
    assert 'href="../profile/"' not in page


def test_a_signed_out_page_loses_its_link_to_the_search_page(client: Client, guide: Path) -> None:
    """The search page needs sign-in, so the link to it goes too."""
    page = body(client.get("/docs/member/sign-in/"))
    assert 'href="../../search/"' not in page


@pytest.mark.parametrize(
    "link", ['href="../../genindex/"', 'rel="search"'], ids=["index", "search"]
)
def test_a_signed_out_page_loses_its_head_links_to_gated_pages(
    client: Client, guide: Path, link: str
) -> None:
    """The head's links to the general index and the search page, both gated, go."""
    page = body(client.get("/docs/member/sign-in/"))
    assert link not in page


@pytest.mark.parametrize("link", [HEAD_INDEX_LINK, HEAD_SEARCH_LINK], ids=["index", "search"])
def test_a_signed_in_reader_keeps_the_head_links(
    client: Client, member: User, guide: Path, link: str
) -> None:
    """A signed-in reader's copy keeps the head's links to the index and search."""
    client.force_login(member)
    page = body(client.get("/docs/member/sign-in/"))
    assert link in page


def test_a_signed_out_page_keeps_its_links_to_other_signed_out_pages(
    client: Client, guide: Path
) -> None:
    """The sidebar entry for another signed-out page stays."""
    page = body(client.get("/docs/member/sign-in/"))
    assert f"<li>{FORGOT_LINK}</li>" in page


def test_a_signed_out_page_loses_the_sidebar_entries_of_gated_pages(
    client: Client, guide: Path
) -> None:
    """A gated page with nothing signed out under it leaves the sidebar whole."""
    page = body(client.get("/docs/member/sign-in/"))
    assert "Overview" not in page


def test_a_signed_out_page_keeps_a_group_holding_signed_out_pages_as_text(
    client: Client, guide: Path
) -> None:
    """The gated group page above the signed-out pages stays as a label, not a link."""
    page = body(client.get("/docs/member/sign-in/"))
    assert "<li>Your screens<ul>" in page


def test_a_signed_out_page_loses_its_search_box(client: Client, guide: Path) -> None:
    """The search page needs sign-in, so the sidebar's search box goes."""
    page = body(client.get("/docs/member/sign-in/"))
    assert 'role="search"' not in page


def test_a_signed_in_reader_keeps_the_search_box(client: Client, member: User, guide: Path) -> None:
    """A signed-in reader's copy of the page keeps its search box."""
    client.force_login(member)
    page = body(client.get("/docs/member/sign-in/"))
    assert SEARCH_FORM in page


def test_a_signed_out_page_is_private_and_revalidated(client: Client, guide: Path) -> None:
    """A signed-out page is cached the way every guide page is."""
    response = client.get("/docs/member/sign-in/")
    response.close()
    assert response.headers["Cache-Control"] == "private, no-cache"


def test_a_stylesheet_is_served_without_sign_in(client: Client, guide: Path) -> None:
    """A file under ``_static/``, which a signed-out page loads, is served to anybody."""
    response = client.get("/docs/_static/styles.css")
    assert response.status_code == 200
    assert body(response) == STYLESHEET


@pytest.mark.parametrize(
    "path",
    [
        "",
        "member/",
        "member/profile/",
        "search/",
        "searchindex.js",
        GUIDE_SIGNED_OUT,
        GUIDE_ROLES,
        "objects.inv",
        "_images/diagram.svg",
        "_static/",
        "no-such-page/",
        "_static/../member/profile/",
    ],
    ids=[
        "front-page",
        "group-index",
        "gated-page",
        "search-page",
        "search-index",
        "signed-out-file",
        "roles-file",
        "inventory",
        "image",
        "static-directory",
        "missing-page",
        "detour-through-static",
    ],
)
def test_anything_else_sends_a_signed_out_visitor_to_sign_in(
    client: Client, guide: Path, path: str
) -> None:
    """Every other request redirects to the portal login, ``next`` set to the request."""
    response = client.get(f"/docs/{path}")
    assert response.status_code == 302
    assert response.headers["Location"] == f"/portal/login?next=/docs/{path}"


def test_a_guide_without_the_signed_out_file_serves_nothing_signed_out(
    client: Client, guide: Path
) -> None:
    """With no ``signed-out.json``, even the sign-in page needs sign-in."""
    (guide / GUIDE_SIGNED_OUT).unlink()
    response = client.get("/docs/member/sign-in/")
    assert response.status_code == 302


def test_a_guide_without_the_signed_out_file_serves_no_stylesheet_signed_out(
    client: Client, guide: Path
) -> None:
    """With no ``signed-out.json``, a ``_static/`` file needs sign-in as well."""
    (guide / GUIDE_SIGNED_OUT).unlink()
    response = client.get("/docs/_static/styles.css")
    assert response.status_code == 302


def test_an_unreadable_signed_out_file_serves_nothing_signed_out(
    client: Client, guide: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A ``signed-out.json`` that is not JSON is logged, and every page needs sign-in."""
    signed_out_file = guide / GUIDE_SIGNED_OUT
    _rewrite(signed_out_file, "not json")
    response = client.get("/docs/member/sign-in/")
    assert response.status_code == 302
    assert f"The user guide's {signed_out_file} is not valid JSON" in caplog.text


def test_a_signed_out_file_of_the_wrong_shape_serves_nothing_signed_out(
    client: Client, guide: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A ``signed-out.json`` not in the build's shape is logged and refused."""
    signed_out_file = guide / GUIDE_SIGNED_OUT
    _rewrite(signed_out_file, json.dumps(["member/sign-in"]))
    caplog.set_level(logging.ERROR, logger="caldart.views")
    response = client.get("/docs/member/sign-in/")
    assert response.status_code == 302
    assert "is not the shape the build writes" in caplog.text


def test_a_signed_in_reader_keeps_every_link(client: Client, member: User, guide: Path) -> None:
    """A signed-in member reads the sign-in page with its link to a gated page intact."""
    client.force_login(member)
    page = body(client.get("/docs/member/sign-in/"))
    assert 'href="../profile/"' in page


def test_a_signed_in_reader_is_still_held_to_a_pages_roles(
    client: Client, member: User, guide: Path
) -> None:
    """``roles.json`` still decides which pages a signed-in reader may open."""
    _rewrite(guide / GUIDE_ROLES, json.dumps({"member/profile": [SYSTEM_ADMIN]}))
    client.force_login(member)
    response = client.get("/docs/member/profile/")
    assert response.status_code == 302
    assert response.headers["Location"] == "/docs/"
