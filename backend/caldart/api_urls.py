"""``/api/v1/`` router.

Each app keeps its routes in ``apps/<app>/api/urls.py``, so adding an endpoint
never needs an edit here.

This module also carries what the OpenAPI generator needs to describe those
routes: the hook that narrows the schema to ``/api/v1/`` and the description of
the project's session authentication.  The schema itself is a build artifact,
written by ``manage.py spectacular``; no route serves it.
"""

from typing import Any

from django.conf import settings
from django.urls import include, path
from drf_spectacular.extensions import OpenApiAuthenticationExtension

app_name = "api"

#: The prefix every route below is mounted under, and the only prefix the
#: OpenAPI schema describes.
API_PATH_PREFIX = "/api/v1/"


def portal_api_endpoints(*, endpoints: list[tuple[str, Any, Any, Any]], **_: Any) -> list[
    tuple[str, Any, Any, Any]
]:
    """Keep only the routes mounted under ``/api/v1/`` when generating the schema.

    Wagtail's admin API view sets share the project's URL configuration but are driven by
    Wagtail's own router, which cannot describe itself without a live request.  The portal
    contract covers ``/api/v1/`` alone, so every other path is dropped before the generator
    inspects it.  ``endpoints`` is a list of ``(path, path_regex, method, callback)``
    tuples, and the return value is the filtered list in the same order.
    """
    return [entry for entry in endpoints if entry[0].startswith(API_PATH_PREFIX)]


class SessionAuthenticationScheme(OpenApiAuthenticationExtension):
    """Describe the project's session authentication to the OpenAPI generator.

    Importing this module registers the scheme, which every operation then names as
    ``sessionAuth``: the session cookie Django sets at sign-in, sent back on each
    request, with a CSRF token on anything that writes.
    """

    target_class = "caldart.authentication.CsrfEnforcingSessionAuthentication"
    name = "sessionAuth"

    def get_security_definition(self, auto_schema: Any) -> dict[str, str]:
        """Return the OpenAPI security scheme for the session cookie."""
        return {
            "type": "apiKey",
            "in": "cookie",
            "name": settings.SESSION_COOKIE_NAME,
            "description": (
                "The session cookie Django sets at sign-in.  Unsafe methods also "
                "require the `X-CSRFToken` header."
            ),
        }


urlpatterns = [
    path("", include("apps.accounts.api.urls")),
    path("", include("apps.members.api.urls")),
    path("", include("apps.aircraft.api.urls")),
    path("", include("apps.payments.api.urls")),
    path("", include("apps.reminders.api.urls")),
    path("", include("apps.cms.api.urls")),
    path("", include("apps.sysadmin.api.urls")),
]
