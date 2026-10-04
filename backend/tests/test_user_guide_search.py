"""``/docs/``: the user guide trimmed to the reader's roles, search index included.

The ``user_guide`` view serves ``searchindex.js`` and every page with the pages the
reader's roles do not reach taken out.  Most tests build a small stand-in guide under
``tmp_path`` in the shape Sphinx and furo write; the last group builds a real guide
with Sphinx, so a change in Sphinx's index format or furo's sidebar fails here.
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
from pytest_django import DjangoAssertNumQueries
from pytest_django.fixtures import Settings
from sphinx.cmd.build import build_main

from apps.accounts.models import User
from apps.accounts.roles import ACCOUNT_ADMIN, DART_LEADER, SYSTEM_ADMIN
from caldart.guide_search import SEARCH_INDEX
from caldart.views import GUIDE_INDEX, GUIDE_ROLES

pytestmark = pytest.mark.django_db

#: The repository's ``docs/``, whose ``conf.py`` and extension the real build uses.
DOCS_DIR = Path(__file__).resolve().parents[2] / "docs"

#: The stand-in guide's pages, in docname order, which is the order Sphinx numbers them.
DOCNAMES = ["admin/health-database", "admin/index", "admin/members", "index", "member/profile"]
TITLES = ["Health & Database", "Leader screens", "Members", "User guide", "My profile"]

#: The roles ``roles.json`` gives the stand-in's restricted pages.
ROLES = {
    "admin/health-database": [SYSTEM_ADMIN],
    "admin/index": [DART_LEADER, ACCOUNT_ADMIN, SYSTEM_ADMIN],
    "admin/members": [DART_LEADER, ACCOUNT_ADMIN],
}

#: The stand-in's index: ``vacuum`` is only on the system page, ``roster`` on the members
#: page and the profile, ``callsign`` on the profile alone.
SEARCH_DATA = {
    "alltitles": {
        "Health & Database": [[0, None]],
        "Members": [[2, None]],
        "Shared heading": [[2, "shared"], [4, "shared"]],
        "My profile": [[4, None]],
    },
    "docnames": DOCNAMES,
    "envversion": {"sphinx": 66},
    "filenames": [f"{docname}.rst" for docname in DOCNAMES],
    "indexentries": {"vacuum": [[0, "index-0", False]], "profile": [[4, "index-0", True]]},
    "objects": {"": [[0, 0, 1, "-", "vacuum"], [4, 0, 1, "-", "callsign"]]},
    "objnames": {"0": ["std", "label", "label"]},
    "objtypes": {"0": "std:label"},
    "terms": {"vacuum": 0, "roster": [2, 4], "callsign": 4, "screen": [0, 1, 2]},
    "titles": TITLES,
    "titleterms": {"health": 0, "member": 2, "profil": 4},
}

#: The stand-in's front page lists every page in a toctree; its next link is the
#: administrator index.
FRONT_PAGE = """<!doctype html>
<html><head><title>User guide</title>
<link rel="next" title="Leader screens" href="admin/">
</head><body>
<div class="sidebar-tree">
<p class="caption" role="heading"><span class="caption-text">Screens</span></p>
<ul>
<li class="toctree-l1"><a class="reference internal" href="member/profile/">My profile</a></li>
<li class="toctree-l1 has-children"><a class="reference internal" href="admin/">Leader screens</a>\
<input class="toctree-checkbox" id="toctree-checkbox-1" type="checkbox"/><ul>
<li class="toctree-l2"><a class="reference internal" href="admin/members/">Members</a></li>
<li class="toctree-l2"><a class="reference internal" href="admin/health-database/">\
Health &amp; Database</a></li>
</ul></li>
</ul>
<p class="caption" role="heading"><span class="caption-text">Administration</span></p>
<ul>
<li class="toctree-l1"><a class="reference internal" href="admin/health-database/">\
Health &amp; Database</a></li>
</ul>
</div>
<h1>User guide</h1>
<div class="toctree-wrapper compound">
<ul><li class="toctree-l1"><a class="reference internal" href="admin/members/">Members</a></li></ul>
</div>
<p>See <a href="https://example.org/admin/members/">the outside world</a>, the \
<a class="reference internal" href="admin/members/"><span class="doc">Members screen</span></a>, \
and <a class="reference internal" href="member/profile/">your profile</a>.</p>
<div class="related-pages">
<a class="next-page" href="admin/"><div class="title">Leader screens</div></a>
</div>
</body></html>
"""

#: A page that links nothing restricted, byte for byte as the build wrote it.
PROFILE_PAGE = """<!doctype html>
<html><head><title>My profile</title></head><body>
<div class="sidebar-tree"><ul>
<li class="toctree-l1"><a class="reference internal" href="../../">User guide</a></li>
<li class="toctree-l1 current"><a class="current reference internal" href="#">My profile</a></li>
</ul></div>
<p>Rock &amp; roll, a dash \u2014 here, <br>and a <b>bold</b>  spacing.</p>
</body></html>
"""

#: Every title a member must not see, as the stand-in's HTML spells it.
RESTRICTED_TITLES = ["Leader screens", ">Members<", "Health &amp; Database"]


def serialize_index(data: object) -> str:
    """``data`` written the way Sphinx writes ``searchindex.js``."""
    return f"Search.setIndex({json.dumps(data, separators=(',', ':'), sort_keys=True)})"


def body(response: HttpResponseBase) -> bytes:
    """The whole body of a streamed guide file, which also closes the file behind it."""
    assert isinstance(response, StreamingHttpResponse)
    # A synchronous StreamingHttpResponse yields bytes; the async branch of the
    # declared union cannot occur here.
    return b"".join(cast(Iterator[bytes], response.streaming_content))


def read_index(response: HttpResponseBase) -> dict[str, object]:
    """The JSON object a served ``searchindex.js`` passes to ``Search.setIndex``."""
    text = body(response).decode()
    assert text.startswith("Search.setIndex(")
    loaded: dict[str, object] = json.loads(text.removeprefix("Search.setIndex(").removesuffix(")"))
    return loaded


@pytest.fixture
def guide(tmp_path: Path, settings: Settings) -> Path:
    """A stand-in guide: a front page, a profile page, ``roles.json`` and an index."""
    root = tmp_path / "guide"
    for docname in ("member/profile", "admin/members", "admin/health-database"):
        (root / docname).mkdir(parents=True)
    (root / GUIDE_INDEX).write_text(FRONT_PAGE, encoding="utf-8")
    (root / "member" / "profile" / GUIDE_INDEX).write_text(PROFILE_PAGE, encoding="utf-8")
    (root / "admin" / GUIDE_INDEX).write_text("<h1>Leader screens</h1>")
    (root / GUIDE_ROLES).write_text(json.dumps(ROLES))
    (root / SEARCH_INDEX).write_text(serialize_index(SEARCH_DATA))
    settings.USER_GUIDE_ROOT = root
    return root


@pytest.fixture
def reader(client: Client, member: User) -> Client:
    """The test client signed in as a plain member."""
    client.force_login(member)
    return client


@pytest.fixture
def administrator(client: Client, system_admin: User) -> Client:
    """The test client signed in as a system administrator."""
    client.force_login(system_admin)
    return client


# ------------------------------------------------------------------ the index
def test_a_members_index_names_only_the_pages_they_may_open(reader: Client, guide: Path) -> None:
    """The restricted docnames are gone, and the open pages keep their order."""
    index = read_index(reader.get(f"/docs/{SEARCH_INDEX}"))
    assert index["docnames"] == ["index", "member/profile"]


def test_a_members_index_keeps_titles_beside_their_pages(reader: Client, guide: Path) -> None:
    """``titles`` loses the same entries as ``docnames``, so each still names its page."""
    index = read_index(reader.get(f"/docs/{SEARCH_INDEX}"))
    assert index["titles"] == ["User guide", "My profile"]


def test_a_members_index_keeps_filenames_beside_their_pages(reader: Client, guide: Path) -> None:
    """``filenames`` loses the same entries as ``docnames``."""
    index = read_index(reader.get(f"/docs/{SEARCH_INDEX}"))
    assert index["filenames"] == ["index.rst", "member/profile.rst"]


def test_a_members_index_renumbers_the_terms(reader: Client, guide: Path) -> None:
    """A word found only on restricted pages is gone; the rest point at the new numbers.

    ``roster`` was on the members page and the profile and keeps the profile alone,
    written as a single number the way Sphinx writes a word found on one page.
    """
    index = read_index(reader.get(f"/docs/{SEARCH_INDEX}"))
    assert index["terms"] == {"roster": 1, "callsign": 1}


def test_a_members_index_renumbers_the_title_terms(reader: Client, guide: Path) -> None:
    """``titleterms`` follows the same rule as ``terms``."""
    index = read_index(reader.get(f"/docs/{SEARCH_INDEX}"))
    assert index["titleterms"] == {"profil": 1}


def test_a_members_index_keeps_only_the_titles_of_open_pages(reader: Client, guide: Path) -> None:
    """A restricted page's headings leave ``alltitles``, and the rest are renumbered."""
    index = read_index(reader.get(f"/docs/{SEARCH_INDEX}"))
    assert index["alltitles"] == {"Shared heading": [[1, "shared"]], "My profile": [[1, None]]}


def test_a_members_index_keeps_only_the_index_entries_of_open_pages(
    reader: Client, guide: Path
) -> None:
    """``indexentries`` drops a restricted page's entries and renumbers the rest."""
    index = read_index(reader.get(f"/docs/{SEARCH_INDEX}"))
    assert index["indexentries"] == {"profile": [[1, "index-0", True]]}


def test_a_members_index_keeps_only_the_objects_of_open_pages(reader: Client, guide: Path) -> None:
    """``objects`` drops a restricted page's entries and renumbers the rest."""
    index = read_index(reader.get(f"/docs/{SEARCH_INDEX}"))
    assert index["objects"] == {"": [[1, 0, 1, "-", "callsign"]]}


def test_a_members_index_keeps_the_fields_that_name_no_page(reader: Client, guide: Path) -> None:
    """``envversion``, ``objnames`` and ``objtypes`` pass through unchanged."""
    index = read_index(reader.get(f"/docs/{SEARCH_INDEX}"))
    kept = {key: index[key] for key in ("envversion", "objnames", "objtypes")}
    assert kept == {key: SEARCH_DATA[key] for key in ("envversion", "objnames", "objtypes")}


def test_a_dart_leader_finds_the_pages_their_role_reaches(
    client: Client, dart_leader: User, guide: Path
) -> None:
    """A DART leader keeps the members page and its index but not the system page."""
    client.force_login(dart_leader)
    index = read_index(client.get(f"/docs/{SEARCH_INDEX}"))
    assert index["docnames"] == ["admin/index", "admin/members", "index", "member/profile"]


def test_a_system_administrator_gets_the_index_as_built(administrator: Client, guide: Path) -> None:
    """Nothing is hidden from a system administrator, so the file is served as it is."""
    response = administrator.get(f"/docs/{SEARCH_INDEX}")
    assert body(response) == (guide / SEARCH_INDEX).read_bytes()


def test_the_trimmed_index_is_javascript(reader: Client, guide: Path) -> None:
    """The trimmed copy carries the type a browser needs to run it."""
    response = reader.get(f"/docs/{SEARCH_INDEX}")
    response.close()
    assert response.headers["Content-Type"] == "text/javascript"


def test_a_guide_without_a_roles_file_serves_the_index_as_built(
    reader: Client, guide: Path
) -> None:
    """With no ``roles.json`` nothing is restricted, so nothing is taken out."""
    (guide / GUIDE_ROLES).unlink()
    response = reader.get(f"/docs/{SEARCH_INDEX}")
    assert body(response) == (guide / SEARCH_INDEX).read_bytes()


def test_a_rebuilt_index_is_read_again(reader: Client, guide: Path) -> None:
    """An index rewritten with a newer modification time is trimmed afresh."""
    body(reader.get(f"/docs/{SEARCH_INDEX}"))
    index_file = guide / SEARCH_INDEX
    index_file.write_text(serialize_index({**SEARCH_DATA, "terms": {"aileron": [3, 4]}}))
    later = index_file.stat().st_mtime + 10
    os.utime(index_file, (later, later))
    index = read_index(reader.get(f"/docs/{SEARCH_INDEX}"))
    assert index["terms"] == {"aileron": [0, 1]}


@pytest.mark.parametrize(
    "text",
    ["not an index", "Search.setIndex({)", 'Search.setIndex({"docnames": 3})'],
    ids=["no-wrapper", "not-json", "wrong-shape"],
)
def test_an_index_that_cannot_be_trimmed_is_refused(reader: Client, guide: Path, text: str) -> None:
    """An index the view cannot read answers 404 rather than every page's words."""
    (guide / SEARCH_INDEX).write_text(text)
    response = reader.get(f"/docs/{SEARCH_INDEX}")
    assert response.status_code == 404


def test_an_index_that_cannot_be_trimmed_is_logged(
    reader: Client, guide: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The unreadable index is logged as an error naming the file."""
    (guide / SEARCH_INDEX).write_text("not an index")
    reader.get(f"/docs/{SEARCH_INDEX}")
    assert f"The user guide's {guide / SEARCH_INDEX} cannot be trimmed" in caplog.text


# ------------------------------------------------------------------ revalidation
def test_readers_with_different_reach_get_different_tags(
    reader: Client, guide: Path, system_admin: User
) -> None:
    """The ``ETag`` names what was taken out, so a change of roles is a change of tag."""
    member_tag = reader.get(f"/docs/{SEARCH_INDEX}").headers["ETag"]
    reader.force_login(system_admin)
    response = reader.get(f"/docs/{SEARCH_INDEX}")
    response.close()
    assert response.headers["ETag"] != member_tag


def test_a_reader_revalidating_their_own_copy_gets_304(reader: Client, guide: Path) -> None:
    """``If-None-Match`` with the tag the reader was given answers 304."""
    tag = reader.get(f"/docs/{SEARCH_INDEX}").headers["ETag"]
    response = reader.get(f"/docs/{SEARCH_INDEX}", HTTP_IF_NONE_MATCH=tag)
    assert response.status_code == 304


def test_a_copy_trimmed_for_other_roles_is_sent_again(
    reader: Client, guide: Path, system_admin: User
) -> None:
    """A reader whose roles changed since their copy gets the file again, not 304."""
    tag = reader.get(f"/docs/{GUIDE_INDEX}").headers["ETag"]
    reader.force_login(system_admin)
    response = reader.get("/docs/", HTTP_IF_NONE_MATCH=tag)
    response.close()
    assert response.status_code == 200


# ------------------------------------------------------------------ the pages
def test_a_members_sidebar_leaves_out_every_restricted_page(reader: Client, guide: Path) -> None:
    """No restricted page's title is left anywhere on the member's front page."""
    page = body(reader.get("/docs/")).decode()
    assert [title for title in RESTRICTED_TITLES if title in page] == []


def test_a_members_sidebar_keeps_the_pages_they_may_open(reader: Client, guide: Path) -> None:
    """The profile page's entry stays in the sidebar."""
    page = body(reader.get("/docs/")).decode()
    assert '<a class="reference internal" href="member/profile/">My profile</a>' in page


def test_a_caption_with_nothing_left_under_it_is_removed(reader: Client, guide: Path) -> None:
    """A sidebar caption whose every entry is restricted goes with its list."""
    page = body(reader.get("/docs/")).decode()
    assert "Administration" not in page


def test_a_caption_with_an_open_entry_stays(reader: Client, guide: Path) -> None:
    """A caption that still lists a page the reader may open keeps its place."""
    page = body(reader.get("/docs/")).decode()
    assert '<span class="caption-text">Screens</span>' in page


def test_an_emptied_table_of_contents_is_removed(reader: Client, guide: Path) -> None:
    """A table of contents whose entries are all restricted goes whole."""
    page = body(reader.get("/docs/")).decode()
    assert "toctree-wrapper" not in page


def test_a_next_link_to_a_restricted_page_is_removed(reader: Client, guide: Path) -> None:
    """The link at the bottom of the page to a restricted page goes."""
    page = body(reader.get("/docs/")).decode()
    assert "next-page" not in page


def test_a_head_link_to_a_restricted_page_is_removed(reader: Client, guide: Path) -> None:
    """The ``<link rel="next">`` in the page head, which carries its title, goes too."""
    page = body(reader.get("/docs/")).decode()
    assert 'rel="next"' not in page


def test_a_link_that_leaves_the_guide_is_kept(reader: Client, guide: Path) -> None:
    """A link elsewhere whose path looks like a restricted page is not the guide's."""
    page = body(reader.get("/docs/")).decode()
    assert "https://example.org/admin/members/" in page


def test_a_prose_link_to_a_restricted_page_keeps_only_its_text(reader: Client, guide: Path) -> None:
    """A link in the page body to a restricted page loses its anchor; its words stay."""
    page = body(reader.get("/docs/")).decode()
    assert 'the <span class="doc">Members screen</span>, and' in page


def test_a_prose_link_to_an_open_page_is_kept(reader: Client, guide: Path) -> None:
    """A link in the page body to a page the reader may open is left alone."""
    page = body(reader.get("/docs/")).decode()
    assert '<a class="reference internal" href="member/profile/">your profile</a>' in page


def test_a_page_with_nothing_to_remove_is_served_as_built(reader: Client, guide: Path) -> None:
    """A page that links no restricted page is served byte for byte."""
    response = reader.get("/docs/member/profile/")
    assert body(response) == PROFILE_PAGE.encode()


def test_a_system_administrator_gets_every_page_as_built(
    administrator: Client, guide: Path
) -> None:
    """The front page reaches a system administrator untouched."""
    assert body(administrator.get("/docs/")) == FRONT_PAGE.encode()


# ------------------------------------------------------------------ queries
def test_a_page_reads_the_readers_roles_once(
    reader: Client, guide: Path, django_assert_max_num_queries: DjangoAssertNumQueries
) -> None:
    """Serving a trimmed page costs the session, the user, and one read of the roles."""
    with django_assert_max_num_queries(3):
        body(reader.get("/docs/"))


def test_a_static_file_reads_no_roles(
    reader: Client, guide: Path, django_assert_max_num_queries: DjangoAssertNumQueries
) -> None:
    """A stylesheet is neither gated nor trimmed, so the reader's roles are not read."""
    (guide / "_static").mkdir()
    (guide / "_static" / "styles.css").write_text("body { color: black; }")
    with django_assert_max_num_queries(2):
        body(reader.get("/docs/_static/styles.css"))


# ------------------------------------------------------------------ build files
@pytest.mark.parametrize(
    "path",
    [GUIDE_ROLES, "objects.inv", ".buildinfo", ".doctrees/admin/members.doctree"],
    ids=["roles", "inventory", "buildinfo", "doctree"],
)
def test_a_build_file_that_names_restricted_pages_is_not_served(
    reader: Client, guide: Path, path: str
) -> None:
    """A file the build leaves beside the pages, which a reader never needs, is 404.

    ``roles.json`` names the restricted pages, the inventory their titles, and a
    doctree their whole text.
    """
    target = guide / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("{}")
    response = reader.get(f"/docs/{path}")
    assert response.status_code == 404


# ------------------------------------------------------------------ a real build
#: A small guide in the shape of ``docs/user``: an open group and a restricted one.
REAL_PAGES = {
    "index": "User guide\n==========\n\n.. toctree::\n   :caption: Screens\n\n"
    "   member/index\n   admin/index\n",
    "member/index": "Your screens\n============\n\n.. toctree::\n\n   profile\n",
    "member/profile": "My profile\n==========\n\nThe profile lists your roster.\n",
    "admin/index": "Quokka screens\n==============\n\n.. toctree::\n\n   wombat\n",
    "admin/wombat": ":roles: account_admin\n\nWombat ledger\n=============\n\n"
    "Reconcile the numbat roster here.\n",
}

#: Words only the restricted pages carry, each of which must vanish for a member.
REAL_SECRETS = ["Quokka", "quokka", "Wombat", "wombat", "numbat"]


@pytest.fixture(scope="module")
def real_guide(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A guide built by Sphinx with the site's configuration, as ``make guide`` does."""
    root = tmp_path_factory.mktemp("real")
    source = root / "source"
    for docname, text in REAL_PAGES.items():
        page = source / f"{docname}.rst"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(text, encoding="utf-8")
    out = root / "out"
    args = ["-q", "-W", "-b", "dirhtml", "-t", "guide", "-c", str(DOCS_DIR)]
    assert build_main([*args, str(source), str(out)]) == 0
    return out


@pytest.fixture
def real_settings(real_guide: Path, settings: Settings) -> Path:
    """Point ``USER_GUIDE_ROOT`` at the real build."""
    settings.USER_GUIDE_ROOT = real_guide
    return real_guide


@pytest.mark.slow
@pytest.mark.parametrize(
    "path", ["", "member/", "member/profile/", "search/", SEARCH_INDEX], ids=str
)
def test_a_member_finds_no_restricted_word_in_a_real_build(
    reader: Client, real_settings: Path, path: str
) -> None:
    """Every page and the index of a real build omit the secrets for a member."""
    text = body(reader.get(f"/docs/{path}")).decode()
    assert [word for word in REAL_SECRETS if word in text] == []


@pytest.mark.slow
def test_a_system_administrator_finds_the_restricted_page_in_a_real_build(
    administrator: Client, real_settings: Path
) -> None:
    """The control: the restricted page is in the real index, so the trim has work."""
    index = read_index(administrator.get(f"/docs/{SEARCH_INDEX}"))
    assert "admin/wombat" in cast(list[str], index["docnames"])


@pytest.mark.slow
def test_a_member_still_finds_open_words_in_a_real_build(
    reader: Client, real_settings: Path
) -> None:
    """``roster``, on an open and a restricted page, leads a member to the open one."""
    index = read_index(reader.get(f"/docs/{SEARCH_INDEX}"))
    docnames = cast(list[str], index["docnames"])
    terms = cast(dict[str, int | list[int]], index["terms"])
    assert docnames[cast(int, terms["roster"])] == "member/profile"


def test_the_trim_logs_nothing_for_a_well_formed_guide(
    reader: Client, guide: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Trimming a sound index and page logs nothing at warning level or above."""
    caplog.set_level(logging.WARNING, logger="caldart")
    body(reader.get(f"/docs/{SEARCH_INDEX}"))
    body(reader.get("/docs/"))
    assert caplog.records == []
