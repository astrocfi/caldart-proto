"""Report API routes."""

from django.urls import path, re_path

from apps.reports.api import views

app_name = "reports"

urlpatterns = [
    path("reports", views.ReportListView.as_view(), name="list"),
    path("reports/<slug:slug>/columns", views.ReportColumnsView.as_view(), name="columns"),
    path(
        "reports/<slug:slug>/column-sets",
        views.ColumnSetListView.as_view(),
        name="column-sets",
    ),
    path(
        "reports/<slug:slug>/column-sets/<int:pk>",
        views.ColumnSetDetailView.as_view(),
        name="column-set",
    ),
    re_path(
        r"^reports/(?P<slug>[-\w]+)/export\.(?P<fmt>csv|pdf)$",
        views.ReportExportView.as_view(),
        name="export",
    ),
]
