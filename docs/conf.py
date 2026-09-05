"""Sphinx configuration for the CalDART documentation set (PLAN.rst §16).

Kept deliberately minimal: no extensions beyond the built-in defaults, so
``make docs`` needs nothing in the environment except Sphinx and the ``furo``
theme.  The whole set must build clean under ``sphinx-build -W`` (warnings are
errors) -- CI runs it that way on every PR (PLAN.rst §15).
"""

# -- Project information -----------------------------------------------------

project = "CalDART"
author = "The California DART Network"
copyright = "2026, The California DART Network"  # noqa: A001

# The prototype is unversioned; keep these empty rather than inventing numbers.
version = ""
release = ""

# -- General configuration ---------------------------------------------------

# No extensions on purpose.  Anything added here becomes a new dependency in
# pyproject.toml, so add one only when a page genuinely needs it.
extensions: list[str] = []

# The document that holds the root toctree.
master_doc = "index"
root_doc = "index"

source_suffix = {".rst": "restructuredtext"}

exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
]

# ``default`` lets Pygments fall back silently when a literal block is not
# Python; naming a concrete language here would make ``-W`` fail on the many
# shell / JSON / pseudo-code blocks included from PLAN.rst.
highlight_language = "default"

# Prepended to every source file.  Keeps the organisation's full name spelled
# identically everywhere without retyping it.
rst_prolog = """
.. |org| replace:: The California DART Network
"""

language = "en"
nitpicky = False

# ``developer/architecture.rst`` includes ``PLAN.rst`` from the repository
# root verbatim, so a reStructuredText defect in the spec fails this build.
# That is deliberate: PLAN.rst is a deliverable, and ``-W`` keeps it valid.
# No warnings are suppressed.

# -- HTML output -------------------------------------------------------------

html_theme = "furo"
html_title = "CalDART"

# No custom static assets or templates yet.  Pointing at directories that do
# not exist raises a warning, and warnings are errors.
html_static_path: list[str] = []
templates_path: list[str] = []
