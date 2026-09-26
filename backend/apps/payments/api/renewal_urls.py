"""Scheduled-charge routes: a member's own renewal and donation, and the finance screens.

``/me/renewal*`` is the automatic renewal and ``/me/donation*`` the recurring
donation; both are served by the same views, told which kind by their ``donation``
flag.
"""

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
    path("me/donation", renewal_views.MyRenewalView.as_view(donation=True), name="my-donation"),
    path(
        "me/donation/setup",
        renewal_views.MyRenewalSetupView.as_view(donation=True),
        name="my-donation-setup",
    ),
    path(
        "me/donation/confirm",
        renewal_views.MyRenewalConfirmView.as_view(donation=True),
        name="my-donation-confirm",
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
