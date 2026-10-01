"""Project-level views: the portal SPA shell and the user guide.

The Apple Pay domain-association file lives in ``apps.payments.views`` with the
rest of the payment plumbing; ``urls.py`` routes ``/.well-known/...`` to it.
"""

import hashlib
import io
import json
import logging
import mimetypes
from functools import lru_cache
from pathlib import Path
from typing import BinaryIO

from csp.constants import SELF, UNSAFE_INLINE
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import AnonymousUser
from django.http import (
    FileResponse,
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseBase,
    HttpResponseRedirect,
)
from django.shortcuts import render
from django.urls import reverse
from django.utils.cache import get_conditional_response
from django.utils.http import http_date

from caldart.guide_search import (
    INDEX_DOCNAME,
    INDEX_FILE,
    SEARCH_INDEX,
    SearchIndexError,
    trimmed_page,
    trimmed_search_index,
)

log = logging.getLogger(__name__)

#: The file a directory of the built guide is served as.
GUIDE_INDEX = INDEX_FILE

#: Served when the file's type cannot be guessed from its name.
FALLBACK_CONTENT_TYPE = "application/octet-stream"

#: The file the guide build writes beside its index: each role-restricted page's
#: docname and the role slugs that may read it.
GUIDE_ROLES = "roles.json"

#: Files the build leaves at the guide's root that a reader never needs, each of which
#: names the restricted pages: ``roles.json`` their docnames, and Sphinx's inventory
#: their titles.  A path with a part that starts with a dot (``.doctrees``, which holds
#: every page's whole text, and ``.buildinfo``) is refused as well.
GUIDE_PRIVATE_FILES = frozenset({GUIDE_ROLES, "objects.inv"})

#: The suffix of a guide page, which carries the navigation to trim.
PAGE_SUFFIX = ".html"


def portal_shell(request: HttpRequest, path: str = "") -> HttpResponse:
    """Serve the React portal for every ``/portal/...`` URL.

    The SPA owns routing below ``/portal``; the server only needs to hand back
    the shell with the right theme applied.
    """
    from apps.cms.models import SiteSettings

    theme = SiteSettings.get_theme(request)
    return render(
        request,
        "portal.html",
        {"theme": theme, "portal_path": path},
    )


@login_required
def user_guide(request: HttpRequest, path: str) -> HttpResponseBase:
    """Serve one file of the user guide from ``USER_GUIDE_ROOT``, trimmed to the reader.

    Anyone signed in may read it; an anonymous visitor is sent to the portal's
    login page with ``next`` set to the page they asked for.  A page that
    ``roles.json`` restricts to some roles is served only to a reader holding one
    of them (a system administrator holds them all); anyone else is redirected
    to the guide's front page.  Every page the reader is served, and
    ``searchindex.js``, comes without the pages they may not open: the page's
    navigation leaves out every entry and next or previous link that leads to one,
    and the index leaves out their titles and words (``caldart.guide_search``).  An
    index that cannot be trimmed is logged as an error and answers 404.  The static
    assets and every page ``roles.json`` does not name are served to everyone signed
    in, and a guide built without ``roles.json`` serves every file as built.
    ``roles.json``, Sphinx's ``objects.inv``, and any path with a part that starts
    with a dot (the build's ``.doctrees`` and ``.buildinfo``) answer 404.  ``path`` is
    the part after ``/docs/``: an empty path or one ending in a slash serves that
    directory's ``index.html``, a path naming a directory redirects to the slashed
    form, and a path that names no file, or escapes the root, answers 404.  A guide
    that has not been built at all answers 404 too, and logs a warning saying so.

    The response is marked private and revalidated on every request.  A page and the
    index carry an ``ETag`` naming the file's modification time and the pages taken
    out, so a reader whose roles change is sent the file again; every file carries
    ``Last-Modified``, which revalidates a request that names no ``ETag``.  Sphinx
    pages inline the theme's mode switch, so ``script-src`` is replaced with
    ``'self' 'unsafe-inline'`` for the guide alone, exactly as the Wagtail admin's is.
    """
    root: Path = settings.USER_GUIDE_ROOT
    if not (root / GUIDE_INDEX).is_file():
        log.warning("The user guide has not been built: %s has no %s", root, GUIDE_INDEX)
        raise Http404("The user guide has not been built on this server.")

    if path == "" or path.endswith("/"):
        path += GUIDE_INDEX
    target = _guide_file(root, path)
    if target.is_dir():
        return HttpResponseRedirect(f"{request.path}/")
    relative = target.relative_to(root.resolve())
    if not target.is_file() or _is_private(relative):
        raise Http404("No such page in the user guide.")
    # ``login_required`` has already sent an anonymous visitor to sign in; the check
    # narrows the type.
    if isinstance(request.user, AnonymousUser):
        return HttpResponseRedirect(reverse("user-guide", kwargs={"path": ""}))
    page_roles = _guide_roles(root)
    roles = _page_roles(page_roles, relative)
    if roles and not request.user.has_any_role(*roles):
        return HttpResponseRedirect(reverse("user-guide", kwargs={"path": ""}))

    hidden = frozenset(
        docname for docname, slugs in page_roles.items() if not request.user.has_any_role(*slugs)
    )
    modified = target.stat().st_mtime_ns
    trims = relative.suffix == PAGE_SUFFIX or relative.as_posix() == SEARCH_INDEX
    etag = _guide_etag(modified, hidden) if trims else None
    last_modified = modified // 1_000_000_000
    not_modified = get_conditional_response(request, etag=etag, last_modified=last_modified)
    if not_modified is not None:
        return not_modified

    content_type, encoding = mimetypes.guess_type(str(target))
    response = FileResponse(
        _guide_content(target, relative, modified, hidden),
        content_type=content_type or FALLBACK_CONTENT_TYPE,
    )
    response.headers["Last-Modified"] = http_date(last_modified)
    if etag is not None:
        response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "private, no-cache"
    if encoding is not None:
        response.headers["Content-Encoding"] = encoding
    # django-csp reads this attribute off the response; it is part of that
    # library's contract but absent from Django's response types.
    response._csp_replace = {"script-src": [SELF, UNSAFE_INLINE]}  # type: ignore[attr-defined]
    return response


def _is_private(relative: Path) -> bool:
    """True for a guide file no reader is served: a build file naming restricted pages."""
    if relative.as_posix() in GUIDE_PRIVATE_FILES:
        return True
    return any(part.startswith(".") for part in relative.parts)


def _guide_content(target: Path, relative: Path, modified: int, hidden: frozenset[str]) -> BinaryIO:
    """The body of the guide file ``target`` for a reader who may not open ``hidden``.

    A page or the search index is trimmed when anything is hidden; every other file,
    and every file for a reader from whom nothing is hidden, is the file itself.
    Raises ``Http404`` for a search index that cannot be trimmed, after logging it.
    """
    if len(hidden) == 0:
        return target.open("rb")
    if relative.suffix == PAGE_SUFFIX:
        return io.BytesIO(trimmed_page(target, relative.as_posix(), modified, hidden))
    if relative.as_posix() != SEARCH_INDEX:
        return target.open("rb")
    try:
        return io.BytesIO(trimmed_search_index(target, modified, hidden))
    except SearchIndexError as exc:
        log.exception("The user guide's %s cannot be trimmed; refusing it", target)
        raise Http404("No such page in the user guide.") from exc


def _guide_etag(modified: int, hidden: frozenset[str]) -> str:
    """A strong ``ETag`` for a file modified at ``modified`` and trimmed of ``hidden``."""
    digest = hashlib.sha256("\n".join(sorted(hidden)).encode()).hexdigest()[:16]
    return f'"{modified:x}-{digest}"'


def _guide_file(root: Path, path: str) -> Path:
    """Resolve ``path`` inside ``root``, answering 404 for anything that leaves it.

    ``..`` segments, absolute paths and a symlink pointing outside the root all
    resolve to somewhere else and are refused; a NUL byte, which no file name
    may carry, is refused the same way.
    """
    try:
        target = (root / path).resolve()
    except ValueError as exc:
        raise Http404("No such page in the user guide.") from exc
    if not target.is_relative_to(root.resolve()):
        raise Http404("No such page in the user guide.")
    return target


def _guide_roles(root: Path) -> dict[str, tuple[str, ...]]:
    """Each restricted docname of the guide at ``root`` and its role slugs."""
    roles_file = root / GUIDE_ROLES
    if not roles_file.is_file():
        return {}
    return _load_roles(roles_file, roles_file.stat().st_mtime)


def _page_roles(page_roles: dict[str, tuple[str, ...]], relative: Path) -> tuple[str, ...]:
    """The role slugs that may read the guide file ``relative``, or none for everyone.

    ``relative`` is where the request resolved to inside the guide, so a path that
    detours through ``..`` is judged by the page it lands on.  ``dirhtml`` writes the
    page ``admin/members`` as ``admin/members/index.html`` and the index page
    ``admin/index`` as ``admin/index.html``, so a file named ``index.html`` is
    looked up under both docnames.  A file that is not a page (a stylesheet, an
    image) has no roles.
    """
    path = relative.as_posix()
    if path == GUIDE_INDEX:
        return page_roles.get(INDEX_DOCNAME, ())
    suffix = f"/{GUIDE_INDEX}"
    if not path.endswith(suffix):
        return ()
    directory = path.removesuffix(suffix)
    return page_roles.get(directory, ()) or page_roles.get(f"{directory}/{INDEX_DOCNAME}", ())


@lru_cache(maxsize=4)
def _load_roles(roles_file: Path, modified: float) -> dict[str, tuple[str, ...]]:
    """Read ``roles.json``: each restricted docname and the role slugs that may read it.

    ``modified`` is the file's modification time and part of the cache key, so a
    rebuilt guide is read again on its first request and never before.  A file that is
    not valid JSON is logged as an error and read as restricting nothing, so every page
    is served, as for a guide built without the roles extension, rather than every
    request failing.
    """
    try:
        raw: dict[str, list[str]] = json.loads(roles_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        log.exception("The user guide's %s is not valid JSON; serving every page", roles_file)
        return {}
    return {docname: tuple(slugs) for docname, slugs in raw.items()}
