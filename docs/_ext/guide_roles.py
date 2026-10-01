"""Role-restricted pages of the user guide: the ``:roles:`` field and ``roles.json``.

A user-guide page that only some roles may read opens with a field list before its
title::

    :roles: account_admin, dart_leader

Sphinx reads a field list that comes before anything else as the page's metadata, so
the field never shows on the page.  A reader holding any one of the named roles may
read the page, and a system administrator may read every page.  A page without the
field is every signed-in reader's.  A page that carries no field and lists pages in a
toctree (a group's ``index.rst``) takes the union of its children's roles, in role
order, and is open to everyone when any child is.

The extension warns about a slug that is not one of the site's roles, so the ``-W``
build fails on a misspelling, and at the end of an HTML build writes ``roles.json``
into the output directory: one entry per restricted page, its docname mapped to its
role slugs.  The site's ``user_guide`` view reads that file to refuse a restricted
page to a reader without its roles, and to take those pages out of the navigation and
the search index it serves that reader.  So that the index holds a page's title only
under that page, the extension marks every table of contents ``no-search``; Sphinx
would otherwise index the titles a table of contents lists as words of the page
holding it.

The extension is pure Python and imports nothing from the Django project, so the
role slugs are spelled here; ``backend/tests/test_docs_user.py`` holds them equal to
``apps.accounts.roles.ROLE_SLUGS``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from docutils import nodes
from sphinx import addnodes
from sphinx.util import logging

if TYPE_CHECKING:
    from sphinx.application import Sphinx
    from sphinx.environment import BuildEnvironment
    from sphinx.util.typing import ExtensionMetadata

#: Every role slug, least privileged first: the order ``roles.json`` lists them in.
ROLE_SLUGS: tuple[str, ...] = (
    "member",
    "verifier",
    "dart_leader",
    "user_admin",
    "treasurer",
    "account_admin",
    "website_admin",
    "system_admin",
)

#: The metadata field a restricted page names its roles in.
ROLES_FIELD = "roles"

#: The file written into the output directory.
ROLES_FILE = "roles.json"

#: The class Sphinx's search indexer skips a node for.
NO_SEARCH = "no-search"

log = logging.getLogger(__name__)


def setup(app: Sphinx) -> ExtensionMetadata:
    """Check the ``:roles:`` fields once every page is read; write ``roles.json`` last.

    Each table of contents is kept out of the search index as each page is read.

    The extension keeps no state of its own (the fields live in Sphinx's metadata), so
    it is safe for parallel reading and writing.
    """
    app.connect("doctree-read", keep_toctrees_out_of_search)
    app.connect("env-check-consistency", check_roles)
    app.connect("build-finished", write_roles)
    return {"version": "1", "parallel_read_safe": True, "parallel_write_safe": True}


def declared_roles(env: BuildEnvironment, docname: str) -> tuple[str, ...]:
    """The slugs the page ``docname``'s own ``:roles:`` field names, or none.

    Slugs are separated by commas; spaces around them and empty entries are dropped.
    """
    raw = env.metadata.get(docname, {}).get(ROLES_FIELD)
    if raw is None:
        return ()
    return tuple(slug for slug in (part.strip() for part in str(raw).split(",")) if slug)


def keep_toctrees_out_of_search(app: Sphinx, doctree: nodes.document) -> None:
    """Mark every table of contents on a page ``no-search``, so the index skips it.

    A table of contents shows the titles of the pages it lists, and Sphinx would
    otherwise index them as words of the page that holds it: the front page would
    match a word from a restricted page's title.  Each page's own words are indexed
    on that page alone.
    """
    for toctree in doctree.findall(addnodes.toctree):
        wrapper = toctree.parent
        if isinstance(wrapper, nodes.compound) and NO_SEARCH not in wrapper["classes"]:
            wrapper["classes"].append(NO_SEARCH)


def check_roles(app: Sphinx, env: BuildEnvironment) -> None:
    """Warn, against the page, about a ``:roles:`` field that names no role or a stranger.

    Under ``-W`` the warning fails the build.
    """
    for docname in sorted(env.found_docs):
        if ROLES_FIELD not in env.metadata.get(docname, {}):
            continue
        slugs = declared_roles(env, docname)
        if len(slugs) == 0:
            log.warning("the :roles: field names no role", location=docname, type="guide_roles")
        for slug in slugs:
            if slug not in ROLE_SLUGS:
                log.warning(
                    "unknown role %r in the :roles: field (the roles are %s)",
                    slug,
                    ", ".join(ROLE_SLUGS),
                    location=docname,
                    type="guide_roles",
                )


def page_roles(env: BuildEnvironment) -> dict[str, list[str]]:
    """Every restricted page's docname and its role slugs, in role order.

    A page's own ``:roles:`` field wins.  Without one, a page that lists others in a
    toctree takes the union of their roles, and is open when any of them is; a page
    that lists nothing is open.  Open pages are left out of the result.
    """
    computed: dict[str, tuple[str, ...]] = {}

    def roles_of(docname: str) -> tuple[str, ...]:
        """The roles of ``docname``, computed once and remembered in ``computed``."""
        if docname in computed:
            return computed[docname]
        # Held open while the children are visited, so a toctree that lists its own
        # ancestor cannot recurse forever.
        computed[docname] = ()
        own = declared_roles(env, docname)
        children = env.toctree_includes.get(docname, [])
        if own or len(children) == 0:
            result = own
        else:
            child_roles = [roles_of(child) for child in children]
            if any(len(roles) == 0 for roles in child_roles):
                result = ()
            else:
                union = {slug for roles in child_roles for slug in roles}
                result = tuple(slug for slug in ROLE_SLUGS if slug in union)
        computed[docname] = result
        return result

    return {
        docname: [slug for slug in ROLE_SLUGS if slug in roles]
        for docname in sorted(env.found_docs)
        if (roles := roles_of(docname))
    }


def write_roles(app: Sphinx, exception: Exception | None) -> None:
    """Write ``roles.json`` into the output directory after a successful HTML build.

    The file is written to a temporary name beside it and renamed over it, so the site
    reading it during a rebuild finds the old file or the new one, never half of one.
    """
    if exception is not None or app.builder.format != "html":
        return
    target = Path(app.outdir) / ROLES_FILE
    partial = target.with_name(f".{ROLES_FILE}.partial")
    partial.write_text(json.dumps(page_roles(app.env), indent=2) + "\n", encoding="utf-8")
    partial.replace(target)
