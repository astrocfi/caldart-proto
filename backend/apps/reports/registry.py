"""Every report the portal downloads, by slug.

Each app declares its own :class:`~caldart.reports.ReportSpec` next to the columns it
reports; this module gathers them, so the report endpoints (and anything that sends a
report) find one by the slug in a URL.
"""

from __future__ import annotations

from django.http import Http404

from apps.aircraft.reports import AIRCRAFT_REPORT
from apps.mail.reports import EMAIL_LOG_REPORT
from apps.members.reports import MEMBER_REPORT
from apps.payments.reconciliation import RECONCILIATION_REPORT
from apps.payments.reports import CONTRIBUTION_REPORT, DONOR_REPORT, PAYMENT_REPORT
from caldart.reports import Report

#: The reports, by slug, in the order the portal lists them.
REPORTS: dict[str, Report] = {
    spec.slug: spec
    for spec in (
        MEMBER_REPORT,
        AIRCRAFT_REPORT,
        PAYMENT_REPORT,
        RECONCILIATION_REPORT,
        CONTRIBUTION_REPORT,
        DONOR_REPORT,
        EMAIL_LOG_REPORT,
    )
}


def report_or_404(slug: str) -> Report:
    """The report registered under ``slug``.

    A slug no report carries raises ``Http404`` reading ``No report named '<slug>'.``.
    """
    if slug not in REPORTS:
        raise Http404(f"No report named '{slug}'.")
    return REPORTS[slug]
