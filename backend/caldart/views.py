"""Project-level views: the portal SPA shell and the user guide.

The Apple Pay domain-association file lives in ``apps.payments.views`` with the
rest of the payment plumbing; ``urls.py`` routes ``/.well-known/...`` to it.
"""

import logging
import mimetypes
from pathlib import Path

from csp.constants import SELF, UNSAFE_INLINE
from django.conf import settings
from django.contrib.auth.decorators import login_required
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
from django.utils.http import http_date
from django.views.static import was_modified_since

log = logging.getLogger(__name__)

#: The file a directory of the built guide is served as.
GUIDE_INDEX = "index.html"

#: Served when the file's type cannot be guessed from its name.
FALLBACK_CONTENT_TYPE = "application/octet-stream"


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
    login page with ``next`` set to the page they asked for.  ``path`` is the
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
