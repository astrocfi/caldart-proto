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
``/docs/`` to signed-in members.  The developer guide is outside that build's
source tree, so a user page never links into it: every reference on a user page
resolves inside ``docs/user/``, and the guide build needs no special case.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from docutils.nodes import Node
    from sphinx.application import Sphinx

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
# build tag records the decision.  ``docs/developer/data-model.rst`` draws its
# three entity-relationship diagrams inside ``.. only:: graphviz`` and keeps an
# ASCII equivalent of each inside ``.. only:: not graphviz``, so both
# environments get a diagram and neither gets a warning.  Install Graphviz for
# the nicer one.
_HAS_DOT = shutil.which("dot") is not None

# ``guide_roles`` is the one local extension, in ``docs/_ext``: pure Python, it reads
# each user page's ``:roles:`` field, fails the build on a slug that is not a role,
# and writes ``roles.json`` beside the built pages for the site's ``user_guide`` view
# and ``_static/guide-roles.js``.  The path is taken from this file, so the guide
# build, whose source tree is ``docs/user``, finds it too.
sys.path.insert(0, str(Path(__file__).resolve().parent / "_ext"))

extensions: list[str] = ["guide_roles", *(["sphinx.ext.graphviz"] if _HAS_DOT else [])]

if _HAS_DOT:
    tags.add("graphviz")  # noqa: F821 - Sphinx injects ``tags`` into conf.py

graphviz_output_format = "svg"


def setup(app: Sphinx) -> None:
    """Register a stand-in for the graphviz directive when Graphviz is missing.

    ``.. only::`` prunes the doctree *after* parsing, so a ``graphviz``
    directive inside a branch that will be discarded is still parsed -- and an
    unknown directive is a warning, which ``-W`` turns into a failed build.
    Registering a no-op under the same name closes that hole; the ``only``
    directive then discards the (empty) result as intended.
    """
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
html_js_files: list[tuple[str | None, dict[str, str]]] = [("figure-zoom.js", {"defer": "defer"})]
templates_path: list[str] = []

# The guide the site serves takes out of its sidebar and its tables of contents
# every page the reader's roles do not reach.  ``guide-roles.js`` does it, reading
# ``roles.json`` and the reader's roles; until it has, the inline script marks the
# page ``guide-roles-pending`` and ``guide-roles.css`` keeps the trees hidden, so a
# reader never sees an entry appear and then vanish.  The inline script runs in the
# head, before the trees exist; the guide's ``script-src`` allows inline scripts.
if tags.has("guide"):  # noqa: F821 - Sphinx injects ``tags``
    html_css_files.append("guide-roles.css")
    html_js_files += [
        (None, {"body": "document.documentElement.classList.add('guide-roles-pending');"}),
        ("guide-roles.js", {"defer": "defer"}),
    ]
