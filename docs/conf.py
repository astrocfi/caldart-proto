"""Sphinx configuration for the CalDART documentation set.

Kept deliberately minimal: ``make docs`` needs nothing in the environment
except Sphinx and the ``furo`` theme, both of which are in the ``dev``
dependency group.  Graphviz is used when it is installed and skipped cleanly
when it is not (see ``extensions`` below).  The whole set must build clean
under ``sphinx-build -n -W`` (nitpicky; warnings are errors) -- ``make docs``
runs it that way, and CI runs ``make docs`` on every PR.
"""

import shutil

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


def setup(app: object) -> None:
    """Keep ``.. graphviz::`` parseable even when the extension is not loaded.

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

        def run(self) -> list[object]:
            """Discard the directive's content and produce no nodes."""
            return []

    directives.register_directive("graphviz", _NoGraphviz)


# The document that holds the root toctree.
master_doc = "index"
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
nitpicky = False

# No warnings are suppressed: there is no ``nitpick_ignore`` and no
# ``suppress_warnings``.

# -- HTML output -------------------------------------------------------------

html_theme = "furo"
html_title = "CalDART"

# No custom static assets or templates yet.  Pointing at directories that do
# not exist raises a warning, and warnings are errors.
html_static_path: list[str] = []
templates_path: list[str] = []
