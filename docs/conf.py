"""Sphinx configuration for the CalDART documentation set.

Kept deliberately minimal: ``make docs`` needs nothing in the environment
except Sphinx and the ``furo`` theme, both of which are in the ``docs``
dependency group.  Graphviz is used when it is installed and skipped cleanly
when it is not (see ``extensions`` below).  The whole set must build clean
under ``sphinx-build -n -W`` (nitpicky; warnings are errors) -- ``make docs``
runs it that way, and CI runs ``make docs`` on every PR.

The same configuration builds two things.  ``make docs`` builds the whole tree
from ``docs/``.  ``make guide`` builds ``docs/user/`` alone, with the ``guide``
tag and the ``dirhtml`` builder, into the user guide the site serves at
``/docs/`` to signed-in members; the developer guide stays unpublished, so a
reference into it renders as the page's title in italics (see
``_unpublished_developer_reference`` below).
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from docutils import nodes

if TYPE_CHECKING:
    from docutils.nodes import Element, Node
    from sphinx.addnodes import pending_xref
    from sphinx.application import Sphinx
    from sphinx.environment import BuildEnvironment

# -- Project information -----------------------------------------------------

project = "CalDART"
author = "The California DART Network"
copyright = "2026, The California DART Network"  # noqa: A001

# The prototype is unversioned; keep these empty rather than inventing numbers.
version = ""
release = ""

# -- General configuration ---------------------------------------------------

# Only ``sphinx.ext.graphviz``, and only when it can actually work.  It ships
# with Sphinx, so it adds nothing to pyproject.toml, but it shells out to
# Graphviz's ``dot`` and warns when that binary is missing -- which, under
# ``-W``, would fail the build on any machine without Graphviz installed.
#
# So the extension is enabled only when ``dot`` is on PATH, and the ``graphviz``
# build tag records the decision.  ``docs/developer/data-model.rst`` draws the
# entity-relationship diagram inside ``.. only:: graphviz`` and keeps an ASCII
# equivalent inside ``.. only:: not graphviz``, so both environments get a
# diagram and neither gets a warning.  Install Graphviz for the nicer one.
_HAS_DOT = shutil.which("dot") is not None

extensions: list[str] = ["sphinx.ext.graphviz"] if _HAS_DOT else []

if _HAS_DOT:
    tags.add("graphviz")  # noqa: F821 - Sphinx injects ``tags`` into conf.py

graphviz_output_format = "svg"


# -- The user guide on its own -----------------------------------------------

# The directory the developer guide lives in.  ``make guide`` builds from
# ``docs/user`` with this file as its configuration, so the developer pages are
# outside that build's source tree, and every reference into them from the user
# guide (``:doc:`/developer/backup-restore``` and the like) would otherwise be
# an unresolved reference and, under ``-W``, a failed build.
_DEVELOPER_DIR = Path(__file__).parent / "developer"

# The characters reStructuredText accepts for a section title's underline.
_ADORNMENTS = "=-~^\"'`#*+_:.<>"


def _underlines(candidate: str, title: str) -> bool:
    """True when ``candidate`` is a title underline at least as long as ``title``."""
    return len(candidate) >= len(title) and len(set(candidate)) == 1 and candidate[0] in _ADORNMENTS


def _section_titles(lines: list[str]) -> list[tuple[int, str]]:
    """Every section title in an rst source, as ``(line index, title)`` pairs."""
    return [
        (index, line.strip())
        for index, line in enumerate(lines[:-1])
        if line.strip() and _underlines(lines[index + 1], line)
    ]


def _developer_titles() -> tuple[dict[str, str], dict[str, str]]:
    """Read the developer guide's page and section titles off its sources.

    Returns two maps: docname (``developer/deployment``) to page title, and
    label (``deploy-troubleshooting``) to the title of the section the label
    precedes.  Read from the files rather than from Sphinx because the guide
    build never parses them.
    """
    pages: dict[str, str] = {}
    labels: dict[str, str] = {}
    for source in sorted(_DEVELOPER_DIR.glob("*.rst")):
        lines = source.read_text(encoding="utf-8").splitlines()
        titles = _section_titles(lines)
        if not titles:
            continue
        pages[f"developer/{source.stem}"] = titles[0][1]
        for index, line in enumerate(lines):
            if line.startswith(".. _") and line.rstrip().endswith(":"):
                label = line.strip()[4:-1]
                following = [title for title_index, title in titles if title_index > index]
                if following:
                    labels[label] = following[0]
    return pages, labels


_DEVELOPER_PAGES, _DEVELOPER_LABELS = _developer_titles()


def _unpublished_developer_reference(
    app: Sphinx, env: BuildEnvironment, node: pending_xref, contnode: Element
) -> Node | None:
    """Render a reference into a developer page this build leaves out.

    Fires only for a reference Sphinx could not resolve.  In the whole-tree
    build every developer page is present, so the handler declines and the
    usual warning stands.  In the guide build the developer directory is
    outside the source tree; a ``:doc:`` to one of its pages, or a ``:ref:`` to
    a label defined in one, then renders as the page or section title in
    italics (or as the explicit link text, when the reference gave one), and
    anything else still warns.
    """
    if (Path(env.srcdir) / _DEVELOPER_DIR.name).is_dir():
        return None
    reftype = node["reftype"]
    target = node["reftarget"]
    if reftype == "doc":
        title = _DEVELOPER_PAGES.get(target.removeprefix("/"))
    elif reftype == "ref":
        title = _DEVELOPER_LABELS.get(target)
    else:
        return None
    if title is None:
        return None
    if node.get("refexplicit"):
        return nodes.emphasis("", "", *contnode.children)
    return nodes.emphasis(title, title)


def setup(app: Sphinx) -> None:
    """Register the guide build's reference handler and the graphviz stand-in.

    ``.. only::`` prunes the doctree *after* parsing, so a ``graphviz``
    directive inside a branch that will be discarded is still parsed -- and an
    unknown directive is a warning, which ``-W`` turns into a failed build.
    Registering a no-op under the same name closes that hole; the ``only``
    directive then discards the (empty) result as intended.
    """
    app.connect("missing-reference", _unpublished_developer_reference)

    if _HAS_DOT:
        return

    from docutils.parsers.rst import Directive, directives

    class _NoGraphviz(Directive):
        has_content = True
        required_arguments = 0
        optional_arguments = 1
        final_argument_whitespace = True
        option_spec = {
            "alt": directives.unchanged,
            "align": directives.unchanged,
            "caption": directives.unchanged,
            "class": directives.class_option,
            "layout": directives.unchanged,
            "name": directives.unchanged,
        }

        def run(self) -> list[Node]:
            """Discard the directive's content and produce no nodes."""
            return []

    directives.register_directive("graphviz", _NoGraphviz)


# The document that holds the root toctree.
root_doc = "index"

source_suffix = {".rst": "restructuredtext"}

exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
]

# ``default`` lets Pygments fall back silently when a ``::`` literal block is
# not Python; naming a concrete language here would make ``-W`` fail on the
# many directory trees, endpoint listings and shell snippets written that way.
highlight_language = "default"

# Prepended to every source file.  Keeps the organization's full name spelled
# identically everywhere without retyping it.
rst_prolog = """
.. |org| replace:: The California DART Network
"""

language = "en"
nitpicky = True

# No warnings are suppressed: there is no ``nitpick_ignore`` and no
# ``suppress_warnings``.

# -- HTML output -------------------------------------------------------------

html_theme = "furo"
html_title = "CalDART user guide" if tags.has("guide") else "CalDART"  # noqa: F821 - Sphinx injects ``tags``

# ``docs/_static`` holds the one set of hand-written assets both builds ship:
# ``figure-zoom.css``, which puts every diagram on a light panel so it stays
# readable in furo's dark mode, and ``figure-zoom.js``, which adds the
# **Open full size** and **Zoom** toolbar under every figure.  The path is
# relative to this file, so ``make guide``, whose source tree is ``docs/user``,
# finds the same directory.  The script is deferred and loads from the site's
# own origin, so the guide's ``script-src`` needs nothing more.  There are no
# custom templates; pointing ``templates_path`` at a directory that does not
# exist would raise a warning, and warnings are errors.
html_static_path = ["_static"]
html_css_files = ["figure-zoom.css"]
html_js_files = [("figure-zoom.js", {"defer": "defer"})]
templates_path: list[str] = []
