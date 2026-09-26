"""Payments API routes.

The routes themselves live in six modules, one per area of the payments API:
checkout and the provider callbacks, the public donation page, receipts and
statements, refunds, automatic renewal, and the finance reports.  This module
includes all six under one ``payments`` namespace.
"""

from apps.payments.api import (
    checkout_urls,
    donation_urls,
    receipt_urls,
    refund_urls,
    renewal_urls,
    report_urls,
)

app_name = "payments"

urlpatterns = [
    *checkout_urls.urlpatterns,
    *donation_urls.urlpatterns,
    *receipt_urls.urlpatterns,
    *refund_urls.urlpatterns,
    *renewal_urls.urlpatterns,
    *report_urls.urlpatterns,
]
