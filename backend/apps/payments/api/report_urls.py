"""The finance reports: the payment list, the period summary and the exports.

Every route here is guarded by ``IsFinance``: a treasurer or an account
administrator, and a system administrator through the usual rule.
"""

from django.urls import path

from apps.payments.api import views

urlpatterns = [
    path("admin/payments", views.AdminPaymentListView.as_view(), name="admin-list"),
    path(
        "admin/payments/summary",
        views.AdminPaymentSummaryView.as_view(),
        name="admin-summary",
    ),
    path(
        "admin/payments/export.csv",
        views.AdminPaymentExportView.as_view(),
        name="admin-export-csv",
    ),
]
