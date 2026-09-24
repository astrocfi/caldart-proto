"""The finance area's routes: the list, the reports, the ledger and the writes.

Every route here is guarded by ``IsFinance``: a treasurer or an account
administrator, and a system administrator through the usual rule.  The fixed
paths come before ``admin/payments/<int:pk>`` so a word such as ``summary`` is
never read as an id.
"""

from django.urls import path

from apps.payments.api import report_views as views

urlpatterns = [
    path("admin/payments", views.AdminPaymentListView.as_view(), name="admin-list"),
    path(
        "admin/payments/summary",
        views.AdminPaymentSummaryView.as_view(),
        name="admin-summary",
    ),
    path(
        "admin/payments/columns",
        views.AdminPaymentColumnsView.as_view(),
        name="admin-columns",
    ),
    path(
        "admin/payments/export.csv",
        views.AdminPaymentExportCsvView.as_view(),
        name="admin-export-csv",
    ),
    path(
        "admin/payments/export.pdf",
        views.AdminPaymentExportPdfView.as_view(),
        name="admin-export-pdf",
    ),
    path(
        "admin/payments/reconciliation",
        views.AdminReconciliationView.as_view(),
        name="admin-reconciliation",
    ),
    path(
        "admin/payments/reconciliation/export.csv",
        views.AdminReconciliationCsvView.as_view(),
        name="admin-reconciliation-csv",
    ),
    path(
        "admin/payments/reconciliation/export.pdf",
        views.AdminReconciliationPdfView.as_view(),
        name="admin-reconciliation-pdf",
    ),
    path(
        "admin/payments/contributions",
        views.AdminContributionsView.as_view(),
        name="admin-contributions",
    ),
    path(
        "admin/payments/contributions/export.csv",
        views.AdminContributionsCsvView.as_view(),
        name="admin-contributions-csv",
    ),
    path(
        "admin/payments/contributions/export.pdf",
        views.AdminContributionsPdfView.as_view(),
        name="admin-contributions-pdf",
    ),
    path(
        "admin/payments/record",
        views.AdminPaymentRecordView.as_view(),
        name="admin-record",
    ),
    path(
        "admin/payments/ledger/<int:user_id>",
        views.AdminMemberLedgerView.as_view(),
        name="admin-ledger",
    ),
    path(
        "admin/payments/<int:pk>",
        views.AdminPaymentDetailView.as_view(),
        name="admin-detail",
    ),
]
