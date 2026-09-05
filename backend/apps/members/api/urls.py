"""Members API routes (PLAN §6.3, §6.4).

Owned by ``feat/profile-join`` (``/me/profile``, ``/me/membership``,
``/darts``, ``/plans``) and ``feat/members-admin`` (``/admin/members...``).
Each branch adds exactly one ``include()`` below and keeps its own routes in
its own module, so the two never collide here.
"""

from django.urls import include, path

app_name = "members"

urlpatterns: list = [
    # -- profile (feat/profile-join) ---------------------------------------
    path("", include("apps.members.api.profile_urls")),
]
