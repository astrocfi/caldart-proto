"""Payments API routes.

The routes themselves live in five modules, one per area of the payments API:
checkout and the provider callbacks, receipts and statements, refunds,
automatic renewal, and the finance reports.  This module includes all five
under one ``payments`` namespace.
"""

from apps.payments.api import (
    checkout_urls,
    receipt_urls,
    refund_urls,
    renewal_urls,
    report_urls,
)

app_name = "payments"

urlpatterns = [
    *checkout_urls.urlpatterns,
    *receipt_urls.urlpatterns,
    *refund_urls.urlpatterns,
    *renewal_urls.urlpatterns,
    *report_urls.urlpatterns,
]
