"""Aircraft API routes."""

from django.urls import path

from apps.aircraft.api import views

app_name = "aircraft"

urlpatterns = [
    # -- register ---------------------------------------------------------
    path("aircraft", views.AircraftListCreateView.as_view(), name="list"),
    path("aircraft/lookup", views.AircraftLookupView.as_view(), name="lookup"),
    path("aircraft/types", views.AircraftTypeSearchView.as_view(), name="types"),
    path(
        "aircraft/coverage-policy",
        views.CoveragePolicyView.as_view(),
        name="coverage-policy",
    ),
    # -- the FAA registry -------------------------------------------------
    path("aircraft/registry", views.RegistryStatusView.as_view(), name="registry"),
    path(
        "aircraft/registrations",
        views.RegistrationSearchView.as_view(),
        name="registrations",
    ),
    path(
        "aircraft/registry/<str:n_number>",
        views.RegistrationLookupView.as_view(),
        name="registry-lookup",
    ),
    path("aircraft/<int:pk>", views.AircraftDetailView.as_view(), name="detail"),
    path("aircraft/<int:pk>/changes", views.AircraftChangesView.as_view(), name="changes"),
    # -- leader check -----------------------------------------------------
    path("leader/search", views.LeaderSearchView.as_view(), name="leader-search"),
    path(
        "leader/members/<int:user_id>/status",
        views.LeaderMemberStatusView.as_view(),
        name="leader-member-status",
    ),
    path(
        "leader/members/<int:user_id>/verification",
        views.LeaderMemberVerificationView.as_view(),
        name="leader-member-verification",
    ),
    path(
        "leader/members/<int:user_id>/verifier",
        views.LeaderMemberVerifierView.as_view(),
        name="leader-member-verifier",
    ),
    path("leader/aircraft", views.LeaderAircraftView.as_view(), name="leader-aircraft"),
    path(
        "leader/aircraft/<int:pk>/verification",
        views.LeaderAircraftVerificationView.as_view(),
        name="leader-aircraft-verification",
    ),
]
