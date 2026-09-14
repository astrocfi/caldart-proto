"""Non-API payment views.

Only one so far: the file Apple Pay's domain verification fetches over plain
HTTP before the Payment Element will offer the Apple Pay button.
Stripe issues the file when you register the domain; ``docs/developer/
payments-setup.rst`` walks through it.
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_safe


@require_safe
@cache_control(max_age=3600, public=True)
def apple_pay_domain_association(request: HttpRequest) -> HttpResponse:
    """Serve ``/.well-known/apple-developer-merchantid-domain-association``.

    404 rather than 500 when unconfigured or missing: an unregistered domain is
    a normal state for a development machine, and Apple Pay simply does not
    appear in the Payment Element.
    """
    configured = getattr(settings, "STRIPE_APPLE_PAY_DOMAIN_ASSOCIATION", "")
    if not configured:
        raise Http404("Apple Pay domain association file is not configured")

    path = Path(configured)
    if not path.is_file():
        raise Http404("Apple Pay domain association file is missing")

    return HttpResponse(path.read_bytes(), content_type="text/plain")
