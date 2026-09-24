"""Member self-service routes.

Included from ``apps/members/api/urls.py`` without an ``app_name`` of its own,
so these names live in the ``members`` namespace alongside the admin routes.
"""

from django.urls import path

from apps.members.api import profile_views as views

urlpatterns = [
    path("me/profile", views.MyProfileView.as_view(), name="me-profile"),
    path(
        "me/profile/aircraft",
        views.MyProfileAircraftView.as_view(),
        name="me-profile-aircraft",
    ),
    path(
        "me/profile/aircraft/<int:aircraft_id>",
        views.MyProfileAircraftDetailView.as_view(),
        name="me-profile-aircraft-detail",
    ),
    path("me/membership", views.MyMembershipView.as_view(), name="me-membership"),
    path("me/payments", views.MyPaymentsView.as_view(), name="me-payments"),
    path("plans", views.PlanListView.as_view(), name="plans"),
]
