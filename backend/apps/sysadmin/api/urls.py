"""System API routes (PLAN §6.9).  Owned by ``feat/ops``."""

from django.urls import path

from apps.sysadmin.api import views

app_name = "sysadmin"

urlpatterns = [
    path("system/health", views.HealthView.as_view(), name="health"),
    path("system/backups", views.BackupListCreateView.as_view(), name="backups"),
    # ``path:`` rather than ``str:`` on purpose: a traversal attempt should
    # reach the view and be rejected there, not fall through to a 404 from the
    # URL resolver that no test can tell from a typo.
    path(
        "system/backups/<path:name>/download",
        views.BackupDownloadView.as_view(),
        name="backup-download",
    ),
]
