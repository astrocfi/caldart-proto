"""Members API routes.

Member self-service (``/me/...``, ``/darts``, ``/plans``) lives in
``profile_urls.py`` and account-administrator management
(``/admin/members...``) in ``admin_urls.py``.  Each keeps its routes in its own
module and is included once below, so the two never collide here.  Street-address
suggestions for the profile form (``/addresses/suggest``) are routed here directly.
"""

from django.urls import URLPattern, URLResolver, include, path

from apps.members.api.address_views import AddressSuggestView

app_name = "members"

urlpatterns: list[URLPattern | URLResolver] = [
    # -- profile -----------------------------------------------------------
    path("", include("apps.members.api.profile_urls")),
    # -- admin -------------------------------------------------------------
    path("", include("apps.members.api.admin_urls")),
    # -- addresses ---------------------------------------------------------
    path("addresses/suggest", AddressSuggestView.as_view(), name="addresses-suggest"),
]
