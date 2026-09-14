"""Payments API routes."""

from django.urls import path

from apps.payments.api import views

app_name = "payments"

urlpatterns = [
    # -- checkout ---------------------------------------------------------
    path("payments/config", views.PaymentsConfigView.as_view(), name="config"),
    path("payments/checkout", views.CheckoutView.as_view(), name="checkout"),
    path("payments/stripe/confirm", views.StripeConfirmView.as_view(), name="stripe-confirm"),
    path("payments/stripe/webhook", views.StripeWebhookView.as_view(), name="stripe-webhook"),
    path("payments/paypal/capture", views.PayPalCaptureView.as_view(), name="paypal-capture"),
    path("payments/paypal/webhook", views.PayPalWebhookView.as_view(), name="paypal-webhook"),
    path("payments/mock/complete", views.MockCompleteView.as_view(), name="mock-complete"),
    path("payments/<int:pk>", views.PaymentDetailView.as_view(), name="detail"),
    # -- reports ----------------------------------------------------------
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
