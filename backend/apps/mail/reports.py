"""The email log as a CSV and a PDF.

The ``emails`` report is the log the system screen pages through, as a file: the
same filters (:class:`~apps.mail.filters.EmailLogFilterSet`), the same order, newest
first, and one column registry that the column chooser and both formats share.  The
house style lives in ``caldart.reports``; this module only decides what a row prints
and which rows the report holds.
"""

from __future__ import annotations

from django.db.models import QuerySet
from django.utils import timezone

from apps.accounts.roles import SYSTEM_ADMIN
from apps.mail.filters import EmailLogFilterSet
from apps.mail.models import EmailLog
from apps.mail.purposes import purpose_label
from caldart.reports import (
    Params,
    ReportColumn,
    ReportQuery,
    ReportSpec,
    apply_filterset,
    given_params,
    ordering_terms,
)

#: The filters the PDF subtitle names, in order, when they carry a value.
EXPORT_FILTER_PARAMS: tuple[str, ...] = ("purpose", "status", "from", "to", "q", "ordering")

#: The ``ordering`` terms the report honors, as the list does; any other is ignored.
ORDERINGS: frozenset[str] = frozenset({"sent_at", "-sent_at"})

#: The order with no ``ordering`` given: the most recent send first.
DEFAULT_ORDERING = "-sent_at"

#: The minute a message went, in the installation's own timezone.
SENT_AT_FORMAT = "%Y-%m-%d %H:%M"


def _sent_at(row: EmailLog) -> str:
    """When ``row`` went, as local ``YYYY-MM-DD HH:MM``."""
    return timezone.localtime(row.sent_at).strftime(SENT_AT_FORMAT)


def _user_name(row: EmailLog) -> str:
    """The recipient's name at send time, or ``""`` when nobody was named."""
    return row.recipient_name


#: Every column the email log can carry, in export order.  The error and the
#: attachments are off by default: the one is blank on every message that went out
#: and the other on most, so the everyday file leaves them to be asked for.
EMAIL_LOG_REPORT_COLUMNS: tuple[ReportColumn[EmailLog], ...] = (
    ReportColumn("sent_at", "Sent", True, _sent_at, width=2.4),
    ReportColumn("purpose", "Purpose", True, lambda row: purpose_label(row.purpose), width=3.6),
    ReportColumn("to_email", "To", True, lambda row: row.to_email, width=4.6),
    ReportColumn("user_name", "Name", True, _user_name, width=3.2),
    ReportColumn("subject", "Subject", True, lambda row: row.subject, width=6.0),
    ReportColumn("status", "Status", True, lambda row: row.get_status_display(), width=1.4),
    ReportColumn("error", "Error", False, lambda row: row.error, width=3.2),
    ReportColumn("attachments", "Attachments", False, lambda row: row.attachments, width=4.0),
)


def order_email_log[R](queryset: QuerySet[EmailLog, R], raw: str) -> QuerySet[EmailLog, R]:
    """``queryset`` in the order a comma-separated ``raw`` ordering asks for.

    Only ``sent_at`` and ``-sent_at`` are honored; any other term is ignored, as the
    list's ordering filter ignores it, and with no honored term the most recent send
    comes first.  Rows sent in the same instant fall back to their ``id`` in the same
    direction, so the order is stable.
    """
    terms = [term for term in ordering_terms(raw) if term in ORDERINGS] or [DEFAULT_ORDERING]
    tiebreak = "-id" if terms[0].startswith("-") else "id"
    return queryset.order_by(*terms, tiebreak)


def email_log_report_query(params: Params) -> ReportQuery[EmailLog]:
    """The email log rows for ``params``, in the list's order.

    ``params`` are the list's own query parameters: the filters of
    :class:`~apps.mail.filters.EmailLogFilterSet` and ``ordering``.  A value the
    filter set refuses raises DRF's ``ValidationError`` keyed by that filter.  The
    recipient accounts are fetched with the rows, and the applied filters are those
    of :data:`EXPORT_FILTER_PARAMS` given a value.
    """
    narrowed = apply_filterset(EmailLogFilterSet, params, EmailLog.objects.select_related("user"))
    ordered = order_email_log(narrowed, params.get("ordering", ""))
    return ReportQuery(
        rows=ordered.iterator(chunk_size=500),
        filters=given_params(params, EXPORT_FILTER_PARAMS),
    )


#: The email log, for system administrators.
EMAIL_LOG_REPORT: ReportSpec[EmailLog] = ReportSpec(
    slug="emails",
    title="CalDART email log",
    filename_stem="caldart-emails",
    columns=EMAIL_LOG_REPORT_COLUMNS,
    roles=(SYSTEM_ADMIN,),
    query=email_log_report_query,
)
