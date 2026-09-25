"""Aircraft API routes."""

from django.urls import path

from apps.aircraft.api import views

app_name = "aircraft"

urlpatterns = [
    # -- register ---------------------------------------------------------
    path("aircraft", views.AircraftListCreateView.as_view(), name="list"),
    path("aircraft/lookup", views.AircraftLookupView.as_view(), name="lookup"),
    path("aircraft/<int:pk>", views.AircraftDetailView.as_view(), name="detail"),
    path("aircraft/<int:pk>/changes", views.AircraftChangesView.as_view(), name="changes"),
    # -- exports ----------------------------------------------------------
    path(
        "admin/aircraft/columns",
        views.AircraftColumnsView.as_view(),
        name="columns",
    ),
    path(
        "admin/aircraft/export.csv",
        views.AircraftExportCsvView.as_view(),
        name="export-csv",
    ),
    path(
        "admin/aircraft/export.pdf",
        views.AircraftExportPdfView.as_view(),
        name="export-pdf",
    ),
    # -- leader check -----------------------------------------------------
    path("leader/search", views.LeaderSearchView.as_view(), name="leader-search"),
    path(
        "leader/members/<int:user_id>/status",
        views.LeaderMemberStatusView.as_view(),
        name="leader-member-status",
    ),
    path("leader/aircraft", views.LeaderAircraftView.as_view(), name="leader-aircraft"),
]
