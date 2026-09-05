"""Project-level views: the portal SPA shell.

The Apple Pay domain-association file lives in ``apps.payments.views`` with the
rest of the payment plumbing; ``urls.py`` routes ``/.well-known/...`` to it.
"""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


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
