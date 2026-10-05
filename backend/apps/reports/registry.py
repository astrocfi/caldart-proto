"""Every report the portal downloads, by slug.

Each app declares its own :class:`~caldart.reports.ReportSpec` next to the columns it
reports; this module gathers them, so the report endpoints (and anything that sends a
report) find one by the slug in a URL.
"""

from __future__ import annotations

from django.http import Http404

from apps.aircraft.reports import AIRCRAFT_REPORT
from apps.aircraft.verification_report import VERIFICATION_REPORT
from apps.mail.reports import EMAIL_LOG_REPORT
from apps.members.reports import MEMBER_REPORT
from apps.members.roles_report import ROLES_REPORT
from apps.payments.reconciliation import RECONCILIATION_REPORT
from apps.payments.renewals_report import RENEWAL_REPORT
from apps.payments.reports import CONTRIBUTION_REPORT, DONOR_REPORT, PAYMENT_REPORT
from caldart.reports import Report

#: The reports, by slug, in the order the portal lists them.
REPORTS: dict[str, Report] = {
    spec.slug: spec
    for spec in (
        MEMBER_REPORT,
        ROLES_REPORT,
        VERIFICATION_REPORT,
        AIRCRAFT_REPORT,
        PAYMENT_REPORT,
        RENEWAL_REPORT,
        RECONCILIATION_REPORT,
        CONTRIBUTION_REPORT,
        DONOR_REPORT,
        EMAIL_LOG_REPORT,
    )
}


#: Each report by the name the portal's tabs and menu give it (``Payments``), rather than
#: the title its PDF carries (``CalDART payments``): what a run's actions call it.
REPORT_NAMES: dict[str, str] = {
    MEMBER_REPORT.slug: "Members",
    ROLES_REPORT.slug: "Roles",
    VERIFICATION_REPORT.slug: "Verification",
    AIRCRAFT_REPORT.slug: "Aircraft",
    PAYMENT_REPORT.slug: "Payments",
    RENEWAL_REPORT.slug: "Renewals",
    RECONCILIATION_REPORT.slug: "Reconciliation",
    CONTRIBUTION_REPORT.slug: "Contributions",
    DONOR_REPORT.slug: "Donors",
    EMAIL_LOG_REPORT.slug: "Sent emails",
}


def report_name(spec: Report) -> str:
    """``spec`` by its name in the portal (:data:`REPORT_NAMES`), else by its title."""
    return REPORT_NAMES.get(spec.slug, spec.title)


def report_or_404(slug: str) -> Report:
    """The report registered under ``slug``.

    A slug no report carries raises ``Http404`` reading ``No report named '<slug>'.``.
    """
    if slug not in REPORTS:
        raise Http404(f"No report named '{slug}'.")
    return REPORTS[slug]
