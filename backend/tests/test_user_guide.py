"""``/docs/``: the built user guide, served to signed-in users.

The guide is a directory of static files ``make guide`` writes; these tests
build a tiny stand-in under ``tmp_path`` and point ``USER_GUIDE_ROOT`` at it,
so they run whether or not the real guide has been built.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest
from django.conf import settings as django_settings
from django.http import HttpResponseBase, StreamingHttpResponse
from django.test import Client
from django.utils.http import http_date
from pytest_django.fixtures import Settings

from apps.accounts.models import User
from apps.cms.models import SiteSettings
from caldart.views import GUIDE_INDEX

pytestmark = pytest.mark.django_db

INDEX_HTML = "<h1>User guide</h1>"
MEMBER_HTML = "<h1>Member guide</h1>"
STYLESHEET = "body { color: black; }"


@pytest.fixture
def guide_root(tmp_path: Path, settings: Settings) -> Path:
    """A three-file guide -- an index, one page directory and a stylesheet."""
    root = tmp_path / "guide"
    (root / "member-guide").mkdir(parents=True)
    (root / "_static").mkdir()
    (root / GUIDE_INDEX).write_text(INDEX_HTML)
    (root / "member-guide" / GUIDE_INDEX).write_text(MEMBER_HTML)
    (root / "_static" / "styles.css").write_text(STYLESHEET)
    settings.USER_GUIDE_ROOT = root
    return root


def guide_body(response: HttpResponseBase) -> bytes:
    """The whole body of a streamed guide file, which also closes the file behind it."""
    assert isinstance(response, StreamingHttpResponse)
    # A synchronous StreamingHttpResponse yields bytes; the async branch of the
    # declared union cannot occur here.
    return b"".join(cast(Iterator[bytes], response.streaming_content))


@pytest.fixture
def reader(client: Client, member: User) -> Client:
    """The test client signed in as a plain member."""
    client.force_login(member)
    return client


def test_a_visitor_is_sent_to_sign_in_with_the_page_they_asked_for(
    client: Client, guide_root: Path
) -> None:
    """An anonymous request redirects to the portal login, ``next`` set to the page."""
    response = client.get("/docs/member-guide/")
    assert response.status_code == 302
    assert response.headers["Location"] == "/portal/login?next=/docs/member-guide/"


def test_the_root_serves_the_guide_index(reader: Client, guide_root: Path) -> None:
    """``/docs/`` is the guide's front page."""
    response = reader.get("/docs/")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "text/html"
    assert guide_body(response) == INDEX_HTML.encode()


def test_a_page_directory_serves_its_index(reader: Client, guide_root: Path) -> None:
    """A slashed page path serves that directory's ``index.html``."""
    response = reader.get("/docs/member-guide/")
    assert response.status_code == 200
    assert guide_body(response) == MEMBER_HTML.encode()


def test_a_page_without_its_slash_redirects_to_the_slashed_form(
    reader: Client, guide_root: Path
) -> None:
    """A page directory named without a trailing slash redirects rather than 404s."""
    response = reader.get("/docs/member-guide")
    assert response.status_code == 302
    assert response.headers["Location"] == "/docs/member-guide/"


def test_a_stylesheet_carries_its_own_content_type(reader: Client, guide_root: Path) -> None:
    """A static asset is served with the type its file name implies."""
    response = reader.get("/docs/_static/styles.css")
    assert response.headers["Content-Type"] == "text/css"
    assert guide_body(response) == STYLESHEET.encode()


def test_the_guide_is_private_and_revalidated(reader: Client, guide_root: Path) -> None:
    """A guide page is marked private and revalidated on every request."""
    response = reader.get("/docs/")
    response.close()
    assert response.headers["Cache-Control"] == "private, no-cache"
    assert "Last-Modified" in response.headers


def test_an_unchanged_page_answers_304(reader: Client, guide_root: Path) -> None:
    """``If-Modified-Since`` at or after the file's mtime gets 304 and no body."""
    modified = (guide_root / GUIDE_INDEX).stat().st_mtime
    response = reader.get("/docs/", HTTP_IF_MODIFIED_SINCE=http_date(modified))
    assert response.status_code == 304


def test_a_missing_page_is_404(reader: Client, guide_root: Path) -> None:
    """A path that names no file in the guide is 404."""
    response = reader.get("/docs/no-such-page/")
    assert response.status_code == 404


@pytest.mark.parametrize(
    "path",
    ["../conftest.py", "member-guide/../../secret.txt", "%2e%2e/secret.txt"],
    ids=["dotdot", "nested-dotdot", "encoded-dotdot"],
)
def test_a_path_that_leaves_the_root_is_404(
    reader: Client, guide_root: Path, tmp_path: Path, path: str
) -> None:
    """``..`` cannot reach a file beside the guide, however it is spelled."""
    (tmp_path / "secret.txt").write_text("not for members")
    response = reader.get(f"/docs/{path}")
    assert response.status_code == 404


def test_an_unbuilt_guide_is_404_and_logged(
    reader: Client, tmp_path: Path, settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    """With no index under ``USER_GUIDE_ROOT``, every page is 404, and it is logged."""
    settings.USER_GUIDE_ROOT = tmp_path / "nowhere"
    # The test settings quiet the root logger to ERROR; the warning is the point here.
    caplog.set_level(logging.WARNING, logger="caldart.views")
    response = reader.get("/docs/")
    assert response.status_code == 404
    assert "The user guide has not been built" in caplog.text


def test_the_default_root_is_the_guide_build_directory() -> None:
    """With ``USER_GUIDE_ROOT`` unset, the root is ``docs/_build/guide``."""
    root = Path(django_settings.USER_GUIDE_ROOT)
    assert root.parts[-3:] == ("docs", "_build", "guide")


# ------------------------------------------------------------------ assets
@pytest.mark.parametrize(
    ("path", "content_type"),
    [
        ("_static/figure-zoom.js", "text/javascript"),
        ("_static/figure-zoom.css", "text/css"),
        ("_images/x.svg", "image/svg+xml"),
    ],
    ids=["zoom-script", "zoom-stylesheet", "diagram"],
)
def test_a_figure_asset_carries_the_type_a_browser_needs(
    reader: Client, guide_root: Path, path: str, content_type: str
) -> None:
    """The lightbox's script and stylesheet, and a diagram's SVG, carry their own types.

    A browser refuses to run a script, apply a stylesheet or draw an ``object`` whose
    type is wrong, so each asset the diagram toolbar depends on is served with its type.
    """
    asset = guide_root / path
    asset.parent.mkdir(exist_ok=True)
    asset.write_text("x")
    response = reader.get(f"/docs/{path}")
    response.close()
    assert response.headers["Content-Type"] == content_type


# ------------------------------------------------------------------ footer
def test_the_public_footer_opens_the_guide_in_a_new_tab(
    client: Client, site_settings: SiteSettings
) -> None:
    """The public site's footer links the guide in a new tab, without an opener."""
    body = client.get("/").content.decode()

    assert '<a href="/docs/" target="_blank" rel="noopener">User guide</a>' in body
