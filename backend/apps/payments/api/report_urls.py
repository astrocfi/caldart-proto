"""The finance area's routes: the list, the tables, the ledger and the writes.

Every route here is guarded by ``IsFinance``: a treasurer or an account
administrator, and a system administrator through the usual rule -- except
``admin/payments/donors``, the treasurer's own, which a system administrator
still reaches but an account administrator does not.  The fixed paths come
before ``admin/payments/<int:pk>`` so a word such as ``summary`` is never read
as an id.
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
        "admin/payments/reconciliation",
        views.AdminReconciliationView.as_view(),
        name="admin-reconciliation",
    ),
    path(
        "admin/payments/contributions",
        views.AdminContributionsView.as_view(),
        name="admin-contributions",
    ),
    path(
        "admin/payments/donors",
        views.AdminDonorsView.as_view(),
        name="admin-donors",
    ),
    path(
        "admin/payments/members",
        views.AdminFinanceMemberSearchView.as_view(),
        name="admin-member-search",
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
        "admin/payments/<int:pk>/fees",
        views.AdminPaymentFeesView.as_view(),
        name="admin-fees",
    ),
    path(
        "admin/payments/<int:pk>",
        views.AdminPaymentDetailView.as_view(),
        name="admin-detail",
    ),
]
