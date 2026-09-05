"""``/api/v1/`` router.

Each app owns ``apps/<app>/api/urls.py``.  Phase 2 workers add their endpoints
there and never need to edit this file.
"""

from django.urls import include, path

app_name = "api"

urlpatterns = [
    path("", include("apps.accounts.api.urls")),
    path("", include("apps.members.api.urls")),
    path("", include("apps.aircraft.api.urls")),
    path("", include("apps.payments.api.urls")),
    path("", include("apps.reminders.api.urls")),
    path("", include("apps.cms.api.urls")),
    path("", include("apps.sysadmin.api.urls")),
]
