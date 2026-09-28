"""Project-level views: the portal SPA shell and the user guide.

The Apple Pay domain-association file lives in ``apps.payments.views`` with the
rest of the payment plumbing; ``urls.py`` routes ``/.well-known/...`` to it.
"""

import json
import logging
import mimetypes
from functools import lru_cache
from pathlib import Path

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
    HttpResponseNotModified,
    HttpResponseRedirect,
)
from django.shortcuts import render
from django.urls import reverse
from django.utils.http import http_date
from django.views.static import was_modified_since

log = logging.getLogger(__name__)

#: The file a directory of the built guide is served as.
GUIDE_INDEX = "index.html"

#: Served when the file's type cannot be guessed from its name.
FALLBACK_CONTENT_TYPE = "application/octet-stream"

#: The file the guide build writes beside its index: each role-restricted page's
#: docname and the role slugs that may read it.
GUIDE_ROLES = "roles.json"

#: The docname of the guide's front page, and the last part of every group's index page.
INDEX_DOCNAME = "index"


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
    """Serve one file of the built user guide from ``USER_GUIDE_ROOT``.

    Anyone signed in may read it; an anonymous visitor is sent to the portal's
    login page with ``next`` set to the page they asked for.  A page that
    ``roles.json`` restricts to some roles is served only to a reader holding one
    of them (a system administrator holds them all); anyone else is redirected
    to the guide's front page.  ``roles.json`` itself, the static assets, and
    every page it does not name are served to everyone signed in, and a guide
    built without ``roles.json`` serves every page.  ``path`` is the
    part after ``/docs/``: an empty path or one ending in a slash serves that
    directory's ``index.html``, a path naming a directory redirects to the
    slashed form, and a path that names no file, or escapes the root, answers
    404.  A guide that has not been built at all answers 404 too, and logs a
    warning saying so.

    The response is marked private and revalidated on every request, with
    ``Last-Modified`` and ``If-Modified-Since`` doing the revalidating, so a
    freshly deployed guide shows at once and a proxy never keeps a copy.
    Sphinx pages inline the theme's mode switch, so ``script-src`` is replaced
    with ``'self' 'unsafe-inline'`` for the guide alone, exactly as the Wagtail
    admin's is.
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
    if not target.is_file():
        raise Http404("No such page in the user guide.")
    roles = _page_roles(root, target)
    # ``login_required`` has already sent an anonymous visitor to sign in; the check
    # narrows the type.
    if roles and (isinstance(request.user, AnonymousUser) or not request.user.has_any_role(*roles)):
        return HttpResponseRedirect(reverse("user-guide", kwargs={"path": ""}))

    modified = target.stat().st_mtime
    if not was_modified_since(request.META.get("HTTP_IF_MODIFIED_SINCE"), int(modified)):
        return HttpResponseNotModified()

    content_type, encoding = mimetypes.guess_type(str(target))
    response = FileResponse(target.open("rb"), content_type=content_type or FALLBACK_CONTENT_TYPE)
    response.headers["Last-Modified"] = http_date(modified)
    response.headers["Cache-Control"] = "private, no-cache"
    if encoding is not None:
        response.headers["Content-Encoding"] = encoding
    # django-csp reads this attribute off the response; it is part of that
    # library's contract but absent from Django's response types.
    response._csp_replace = {"script-src": [SELF, UNSAFE_INLINE]}  # type: ignore[attr-defined]
    return response


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


def _page_roles(root: Path, target: Path) -> tuple[str, ...]:
    """The role slugs that may read the guide file ``target``, or none for everyone.

    The page is named by where ``target`` resolved to, so a path that detours
    through ``..`` is judged by the page it lands on.  ``dirhtml`` writes the page
    ``admin/members`` as ``admin/members/index.html`` and the index page
    ``admin/index`` as ``admin/index.html``, so a file named ``index.html`` is
    looked up under both docnames.  A file that is not a page (a stylesheet, an
    image, ``roles.json``) has no roles.
    """
    roles_file = root / GUIDE_ROLES
    if not roles_file.is_file():
        return ()
    page_roles = _load_roles(roles_file, roles_file.stat().st_mtime)
    relative = target.relative_to(root.resolve()).as_posix()
    if relative == GUIDE_INDEX:
        return page_roles.get(INDEX_DOCNAME, ())
    suffix = f"/{GUIDE_INDEX}"
    if not relative.endswith(suffix):
        return ()
    directory = relative.removesuffix(suffix)
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
