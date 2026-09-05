"""Site configuration endpoint (PLAN §6.10).  Expanded by ``feat/cms-site``."""

from __future__ import annotations

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.cms.context_processors import build_nav
from apps.cms.models import DEFAULT_THEME, get_site_settings


class SiteConfigView(APIView):
    """``GET /site/config`` — the chrome the SPA needs before it has a user."""

    permission_classes = [AllowAny]

    def get(self, request):
        settings_obj = get_site_settings(request)

        user = request.user
        can_see_members = bool(
            user and user.is_authenticated and getattr(user, "can_access_members_content", False)
        )

        return Response(
            {
                "org_name": settings_obj.org_name if settings_obj else "CalDART",
                "theme": (settings_obj.theme if settings_obj else DEFAULT_THEME) or DEFAULT_THEME,
                "contact_email": settings_obj.contact_email if settings_obj else "",
                "nav": build_nav(request),
                # `feat/cms-site` fills this from the members-only page tree.
                "members_pages": [] if can_see_members else [],
            }
        )
