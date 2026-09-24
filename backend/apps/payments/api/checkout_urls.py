"""Checkout, confirmation and webhook routes.

These are the routes a member's own payment goes through: the configuration the
checkout screen reads, starting a payment, each provider's confirmation call,
the provider webhooks, and the payment's own status.  The finance area's routes
live in the sibling modules.
"""

from django.urls import path

from apps.payments.api import views

urlpatterns = [
    path("payments/config", views.PaymentsConfigView.as_view(), name="config"),
    path("payments/checkout", views.CheckoutView.as_view(), name="checkout"),
    path("payments/stripe/confirm", views.StripeConfirmView.as_view(), name="stripe-confirm"),
    path("payments/stripe/webhook", views.StripeWebhookView.as_view(), name="stripe-webhook"),
    path("payments/paypal/capture", views.PayPalCaptureView.as_view(), name="paypal-capture"),
    path("payments/paypal/webhook", views.PayPalWebhookView.as_view(), name="paypal-webhook"),
    path("payments/mock/complete", views.MockCompleteView.as_view(), name="mock-complete"),
    path("payments/<int:pk>", views.PaymentDetailView.as_view(), name="detail"),
]
