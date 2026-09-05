"""Aircraft API routes (PLAN §6.5, §6.6).  Owned by ``feat/aircraft-leader``."""

from django.urls import path

from apps.aircraft.api import views

app_name = "aircraft"

urlpatterns = [
    # -- register (PLAN §6.5) ---------------------------------------------
    path("aircraft", views.AircraftListCreateView.as_view(), name="list"),
    path("aircraft/lookup", views.AircraftLookupView.as_view(), name="lookup"),
    path("aircraft/<int:pk>", views.AircraftDetailView.as_view(), name="detail"),
    # -- exports (PLAN §11) -----------------------------------------------
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
    # -- leader check (PLAN §6.6) -----------------------------------------
    path("leader/search", views.LeaderSearchView.as_view(), name="leader-search"),
    path(
        "leader/members/<int:user_id>/status",
        views.LeaderMemberStatusView.as_view(),
        name="leader-member-status",
    ),
    path("leader/aircraft", views.LeaderAircraftView.as_view(), name="leader-aircraft"),
]
