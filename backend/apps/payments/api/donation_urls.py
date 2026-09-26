"""Routes of the public donation page.

Every one is open to anyone: the configuration the form reads, starting a gift,
each provider's confirmation, and the gift's own status.  They live beside the
portal's checkout routes and reach the same providers.
"""

from django.urls import path

from apps.payments.api import donation_views

urlpatterns = [
    path("donations/config", donation_views.DonationsConfigView.as_view(), name="donation-config"),
    path(
        "donations/checkout",
        donation_views.DonationCheckoutView.as_view(),
        name="donation-checkout",
    ),
    path(
        "donations/stripe/confirm",
        donation_views.DonationStripeConfirmView.as_view(),
        name="donation-stripe-confirm",
    ),
    path(
        "donations/paypal/capture",
        donation_views.DonationPayPalCaptureView.as_view(),
        name="donation-paypal-capture",
    ),
    path(
        "donations/mock/complete",
        donation_views.DonationMockCompleteView.as_view(),
        name="donation-mock-complete",
    ),
    path("donations/<int:pk>", donation_views.DonationStatusView.as_view(), name="donation-detail"),
]
