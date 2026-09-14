"""Site configuration endpoint.

``GET /api/v1/site/config`` is the one API call the portal makes before it has
a user: it carries the organization name, the active theme, the contact
address and the same navigation the server-rendered site shows.  Members-only
pages are listed only for callers who may actually open them.
"""

from __future__ import annotations

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.cms.context_processors import build_nav
from apps.cms.models import (
    DEFAULT_THEME,
    get_site_settings,
    members_only_pages,
    user_can_access_members_content,
)


class SiteConfigView(APIView):
    """``GET /site/config`` — the chrome the SPA needs before it has a user."""

    permission_classes = [AllowAny]

    def get(self, request):
        settings_obj = get_site_settings(request)
        can_see_members = user_can_access_members_content(request.user)

        return Response(
            {
                "org_name": settings_obj.org_name if settings_obj else "CalDART",
                "theme": (settings_obj.theme if settings_obj else DEFAULT_THEME) or DEFAULT_THEME,
                "contact_email": settings_obj.contact_email if settings_obj else "",
                "nav": build_nav(request),
                "members_pages": (
                    [{"title": page.title, "url": page.url} for page in members_only_pages(request)]
                    if can_see_members
                    else []
                ),
            }
        )
