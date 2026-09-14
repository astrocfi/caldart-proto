"""Members API routes.

Member self-service (``/me/...``, ``/darts``, ``/plans``) lives in
``profile_urls.py`` and account-administrator management
(``/admin/members...``) in ``admin_urls.py``.  Each keeps its routes in its own
module and is included once below, so the two never collide here.
"""

from django.urls import include, path

app_name = "members"

urlpatterns: list = [
    # -- profile -----------------------------------------------------------
    path("", include("apps.members.api.profile_urls")),
    # -- admin -------------------------------------------------------------
    path("", include("apps.members.api.admin_urls")),
]
