"""Automatic-renewal routes: a member's own mandate and the finance screens."""

from django.urls import path

from apps.payments.api import renewal_views

urlpatterns = [
    path("me/renewal", renewal_views.MyRenewalView.as_view(), name="my-renewal"),
    path(
        "me/renewal/setup",
        renewal_views.MyRenewalSetupView.as_view(),
        name="my-renewal-setup",
    ),
    path(
        "me/renewal/confirm",
        renewal_views.MyRenewalConfirmView.as_view(),
        name="my-renewal-confirm",
    ),
    path("admin/renewals", renewal_views.AdminRenewalListView.as_view(), name="renewals"),
    path(
        "admin/renewals/attempts",
        renewal_views.AdminRenewalAttemptListView.as_view(),
        name="renewal-attempts",
    ),
    path(
        "admin/renewals/<int:pk>",
        renewal_views.AdminRenewalDetailView.as_view(),
        name="renewal-detail",
    ),
]
