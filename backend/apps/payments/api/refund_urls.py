"""Refund routes: issuing a refund against a payment."""

from django.urls import path

from apps.payments.api import refund_views

urlpatterns = [
    path(
        "admin/payments/<int:payment_id>/refunds",
        refund_views.AdminPaymentRefundView.as_view(),
        name="admin-payment-refunds",
    ),
]
