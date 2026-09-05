"""Project-level views: the portal SPA shell and small well-known endpoints."""

from pathlib import Path

from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse
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


def apple_pay_domain_association(request: HttpRequest) -> HttpResponse:
    """Serve the Stripe Apple Pay domain association file (PLAN §10)."""
    configured = getattr(settings, "STRIPE_APPLE_PAY_DOMAIN_ASSOCIATION", "")
    if not configured:
        raise Http404("Apple Pay domain association file is not configured")
    path = Path(configured)
    if not path.is_file():
        raise Http404("Apple Pay domain association file is missing")
    return HttpResponse(path.read_text(), content_type="text/plain")
