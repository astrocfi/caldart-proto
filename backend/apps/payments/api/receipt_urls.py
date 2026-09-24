"""Receipt and contribution-statement routes, for a member and for finance.

A member reaches their own through ``/me/payments``; a treasurer or an account
administrator reaches any member's through ``/admin/payments``.
"""

from django.urls import path

from apps.payments.api import receipt_views

urlpatterns = [
    path(
        "me/payments/statements",
        receipt_views.MyStatementYearsView.as_view(),
        name="my-statement-years",
    ),
    path(
        "me/payments/statements/<int:year>.pdf",
        receipt_views.MyStatementView.as_view(),
        name="my-statement",
    ),
    path(
        "me/payments/<int:pk>/receipt.pdf",
        receipt_views.MyReceiptView.as_view(),
        name="my-receipt",
    ),
    path(
        "admin/payments/<int:pk>/receipt",
        receipt_views.AdminReceiptSendView.as_view(),
        name="admin-receipt-send",
    ),
    path(
        "admin/payments/<int:pk>/receipt.pdf",
        receipt_views.AdminReceiptView.as_view(),
        name="admin-receipt",
    ),
    path(
        "admin/payments/ledger/<int:user_id>/statements/<int:year>.pdf",
        receipt_views.AdminMemberStatementView.as_view(),
        name="admin-member-statement",
    ),
]
