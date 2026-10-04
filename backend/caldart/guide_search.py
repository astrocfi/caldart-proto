"""The user guide trimmed to one reader: the search index and the navigation.

The guide is built once for every reader, so every page's sidebar lists every page,
and ``searchindex.js`` holds every page's title and words.  The ``user_guide`` view
hands each reader a copy with the pages their roles do not reach taken out, using the
functions here.  A reader is described by ``hidden``, the frozen set of docnames
they may not open; both trims are cached per file, modification time and ``hidden``,
so readers with the same reach share one copy and a rebuilt guide is trimmed afresh.

A page's links are judged the way the view judges a request: the ``dirhtml`` build
writes the page ``admin/members`` at ``admin/members/`` and the group index
``admin/index`` at ``admin/``, so a link to a directory is looked up under both
docnames.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup, Tag

log = logging.getLogger(__name__)

#: The file Sphinx writes the search index into, beside the guide's front page.
SEARCH_INDEX = "searchindex.js"

#: The docname of the guide's front page, and the last part of every group's index page.
INDEX_DOCNAME = "index"

#: The file a directory of the built guide is served as.
INDEX_FILE = "index.html"

#: What Sphinx wraps the index's JSON in.
_INDEX_OPEN = "Search.setIndex("
_INDEX_CLOSE = ")"

#: The index's lists that hold one entry per page, in page-number order.
_PER_PAGE_LISTS = ("docnames", "filenames", "titles")

#: The index's maps from a word to the page number, or the list of them, it is found on.
_WORD_MAPS = ("terms", "titleterms")

#: The index's maps from a name to entries, each a list that opens with a page number.
_ENTRY_MAPS = ("alltitles", "indexentries", "objects")

#: A stand-in origin the guide's relative links are resolved against.
_GUIDE_ORIGIN = "https://guide.invalid/"

#: The navigation a page carries: the sidebar and every table of contents.
_TREES = ".sidebar-tree, .toctree-wrapper"

#: The search page Sphinx writes, which no source file makes.
SEARCH_DOCNAME = "search"

#: The search box in a page's sidebar, which submits to the search page.
_SEARCH_FORM = "form[role=search]"

#: The next and previous links at a page's foot, and their twins in the page head.
_RELATED = ".related-pages a, link[rel~=next], link[rel~=prev]"

type Json = bool | int | float | str | list[Json] | dict[str, Json] | None


class SearchIndexError(ValueError):
    """``searchindex.js`` is not the shape Sphinx writes, so it cannot be trimmed."""


def link_is_hidden(page_path: str, href: str, hidden: frozenset[str]) -> bool:
    """True when ``href``, a link on the guide file ``page_path``, leads to a hidden page.

    ``page_path`` is the file's path inside the guide, such as
    ``member/profile/index.html``; ``href`` is resolved against it the way a browser
    would.  A link that leaves the guide, or leads to a page not in ``hidden``, is not
    hidden; a fragment or query on the link is ignored.
    """
    base = urljoin(_GUIDE_ORIGIN, page_path)
    resolved = urlsplit(urljoin(base, href))
    if f"{resolved.scheme}://{resolved.netloc}/" != _GUIDE_ORIGIN:
        return False
    path = resolved.path.removeprefix("/").removesuffix(INDEX_FILE).removesuffix("/")
    if path == "":
        return INDEX_DOCNAME in hidden
    return path in hidden or f"{path}/{INDEX_DOCNAME}" in hidden


@lru_cache(maxsize=16)
def trimmed_search_index(index_file: Path, modified: int, hidden: frozenset[str]) -> bytes:
    """``searchindex.js`` with every page in ``hidden`` taken out, as JavaScript.

    The hidden pages leave the per-page lists (``docnames``, ``filenames`` and
    ``titles``), and the pages left are numbered afresh in the order they had.  Every
    word in ``terms`` and ``titleterms`` keeps only the pages left, written as one
    number when one page is left, as Sphinx writes it, and is dropped when none is;
    every entry in ``alltitles``, ``indexentries`` and ``objects`` on a hidden page is
    dropped, and a name with no entry left goes with it.  Every other field passes
    through unchanged.  ``modified`` is the file's modification time in nanoseconds,
    part of the cache key only.  Raises ``SearchIndexError`` when the file is not a
    ``Search.setIndex(...)`` call holding the fields above in Sphinx's shapes.
    """
    text = index_file.read_text(encoding="utf-8").strip()
    if not (text.startswith(_INDEX_OPEN) and text.endswith(_INDEX_CLOSE)):
        raise SearchIndexError(f"{index_file} is not a Search.setIndex call")
    try:
        index: Json = json.loads(text.removeprefix(_INDEX_OPEN).removesuffix(_INDEX_CLOSE))
    except json.JSONDecodeError as exc:
        raise SearchIndexError(f"{index_file} does not hold JSON") from exc
    trimmed = _trim_index(index, hidden)
    payload = json.dumps(trimmed, separators=(",", ":"), sort_keys=True)
    return f"{_INDEX_OPEN}{payload}{_INDEX_CLOSE}".encode()


def _trim_index(index: Json, hidden: frozenset[str]) -> dict[str, Json]:
    """The parsed index ``index`` with the pages in ``hidden`` taken out.

    See ``trimmed_search_index`` for the rule; raises ``SearchIndexError`` for a field
    of the wrong shape.
    """
    if not isinstance(index, dict):
        raise SearchIndexError("the index is not an object")
    docnames = index.get("docnames")
    if not isinstance(docnames, list) or not all(isinstance(name, str) for name in docnames):
        raise SearchIndexError("the index's docnames are not a list of names")
    renumber = {
        old: new
        for new, old in enumerate(
            number for number, name in enumerate(docnames) if name not in hidden
        )
    }
    trimmed = dict(index)
    for key in _PER_PAGE_LISTS:
        values = _field(index, key, list)
        trimmed[key] = [value for number, value in enumerate(values) if number in renumber]
    for key in _WORD_MAPS:
        words = _field(index, key, dict)
        trimmed[key] = {
            word: pages
            for word, found in words.items()
            if (pages := _renumber_pages(found, renumber)) is not None
        }
    for key in _ENTRY_MAPS:
        names = _field(index, key, dict)
        trimmed[key] = {
            name: entries
            for name, found in names.items()
            if len(entries := _renumber_entries(found, renumber)) > 0
        }
    return trimmed


def _field[T: (list[Json], dict[str, Json])](index: dict[str, Json], key: str, kind: type[T]) -> T:
    """The field ``key`` of ``index``, which must be a ``kind``; missing is empty."""
    value = index.get(key, kind())
    if not isinstance(value, kind):
        raise SearchIndexError(f"the index's {key} is not a {kind.__name__}")
    return value


def _renumber_pages(found: Json, renumber: dict[int, int]) -> Json:
    """``found``, a page number or a list of them, with only the pages left, renumbered.

    One page left is written as its number, several as a list, and none as ``None``.
    """
    numbers = found if isinstance(found, list) else [found]
    if not all(isinstance(number, int) for number in numbers):
        raise SearchIndexError("a word's pages are not page numbers")
    kept: list[Json] = [renumber[n] for n in numbers if isinstance(n, int) and n in renumber]
    if len(kept) == 0:
        return None
    return kept[0] if len(kept) == 1 else kept


def _renumber_entries(found: Json, renumber: dict[int, int]) -> list[Json]:
    """``found``, entries that each open with a page number, for the pages left."""
    if not isinstance(found, list):
        raise SearchIndexError("an index entry list is not a list")
    kept: list[Json] = []
    for entry in found:
        if not isinstance(entry, list) or len(entry) == 0 or not isinstance(entry[0], int):
            raise SearchIndexError("an index entry does not open with a page number")
        if entry[0] in renumber:
            kept.append([renumber[entry[0]], *entry[1:]])
    return kept


@lru_cache(maxsize=256)
def trimmed_page(page_file: Path, page_path: str, modified: int, hidden: frozenset[str]) -> bytes:
    """The guide page ``page_file`` without its navigation to the pages in ``hidden``.

    ``page_path`` is the file's path inside the guide, against which its links are
    resolved (``link_is_hidden``).  Taken out: every sidebar and table-of-contents
    entry whose link leads to a hidden page, with everything nested under it, unless an
    entry nested under it leads to a page left, when the entry stays and its link is
    taken out as below; the sidebar's search box, when the search page is hidden; every
    next or previous link at the foot of the page and in its head that leads to one;
    every other link to one, such as a link in the page's prose, which loses its
    anchor and keeps its text; and then every list in the navigation left with no
    entries, with the caption before it and a table of contents left with no list.
    A page that loses nothing is returned byte for byte as built.  ``modified`` is the
    file's modification time in nanoseconds, part of the cache key only.
    """
    raw = page_file.read_bytes()
    soup = BeautifulSoup(raw, "html.parser")
    removed = False
    for anchor in soup.select(f":is({_TREES}) li > a"):
        entry = anchor.parent
        if anchor.decomposed or entry is None:
            continue
        if _leads_to_hidden(anchor, page_path, hidden) and not _holds_open_entry(
            entry, anchor, page_path, hidden
        ):
            entry.decompose()
            removed = True
    if SEARCH_DOCNAME in hidden:
        for form in soup.select(_SEARCH_FORM):
            form.decompose()
            removed = True
    for link in soup.select(_RELATED):
        if _leads_to_hidden(link, page_path, hidden):
            link.decompose()
            removed = True
    for anchor in soup.select("a[href]"):
        if not anchor.decomposed and _leads_to_hidden(anchor, page_path, hidden):
            anchor.unwrap()
            removed = True
    if not removed:
        return raw
    _remove_empty_lists(soup)
    return soup.encode()


def _holds_open_entry(entry: Tag, anchor: Tag, page_path: str, hidden: frozenset[str]) -> bool:
    """True when an entry nested under ``entry`` (other than ``anchor``) is not hidden."""
    return any(
        nested is not anchor and not _leads_to_hidden(nested, page_path, hidden)
        for nested in entry.select("li > a")
    )


def _leads_to_hidden(element: Tag, page_path: str, hidden: frozenset[str]) -> bool:
    """True when the link ``element`` (an ``a`` or a ``link``) leads to a hidden page."""
    href = element.get("href")
    return isinstance(href, str) and link_is_hidden(page_path, href, hidden)


def _remove_empty_lists(soup: BeautifulSoup) -> None:
    """Remove each empty navigation list, its caption, and a wrapper it empties."""
    for entries in soup.select(f":is({_TREES}) ul"):
        if entries.decomposed or entries.find("li") is not None:
            continue
        caption = entries.find_previous_sibling()
        if caption is not None and "caption" in caption.get_attribute_list("class"):
            caption.decompose()
        wrapper = entries.find_parent(class_="toctree-wrapper")
        entries.decompose()
        if wrapper is not None and wrapper.find("ul") is None:
            wrapper.decompose()
