"""``/api/v1/`` router.

Each app keeps its routes in ``apps/<app>/api/urls.py``, so adding an endpoint
never needs an edit here.
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
