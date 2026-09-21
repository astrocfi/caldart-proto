"""Project middleware.

``WagtailAdminCspMiddleware`` is the one place the Content-Security-Policy in
``caldart.settings.base`` is relaxed.  Everything else -- the public site, the
portal SPA and the API -- is served under that policy unchanged.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import cached_property

from csp.constants import SELF, UNSAFE_INLINE
from django.http import HttpRequest, HttpResponseBase
from django.urls import reverse


class WagtailAdminCspMiddleware:
    """Replace ``script-src`` with ``'self' 'unsafe-inline'`` under the Wagtail admin.

    Wagtail's admin templates inline scripts -- the inline-panel and date/time
    widgets among them -- so the admin cannot run under the site's
    ``script-src``.  The relaxation follows the path rather than the user, so
    the admin's own login page gets it too, and it reaches no other URL: the
    portal, the API and the public site keep the site policy.  The other
    directives are left alone, so an admin page still loads images, styles and
    frames only from the sources the site policy names.

    The marked response is read by ``csp.middleware.CSPMiddleware``, which must
    therefore sit above this middleware in ``MIDDLEWARE``.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponseBase]) -> None:
        """Store the next handler in the chain."""
        self.get_response = get_response

    @cached_property
    def admin_prefix(self) -> str:
        """The path the Wagtail admin is mounted at, such as ``/admin/``.

        Read from the URLconf rather than written down, so moving the mount in
        ``caldart.urls`` moves the relaxation with it.
        """
        return reverse("wagtailadmin_home")

    def __call__(self, request: HttpRequest) -> HttpResponseBase:
        """Mark a Wagtail admin response with its relaxed ``script-src``."""
        response = self.get_response(request)
        if request.path_info.startswith(self.admin_prefix):
            # django-csp reads this attribute off the response; it is part of
            # that library's contract but absent from Django's response types.
            response._csp_replace = {  # type: ignore[attr-defined]
                "script-src": [SELF, UNSAFE_INLINE],
            }
        return response
