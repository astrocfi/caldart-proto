"""The one place the backend writes a date or a moment for a reader to see.

Every date that reaches a portal screen or a download as text -- an email subject
the Sent Emails page lists, a cell of the verification report, the footer of a PDF
report -- passes through this module, so the format can change here alone.  A date
reads ``MM/DD/YYYY``; a moment adds a 24-hour ``HH:MM`` in the installation's own
time zone (``TIME_ZONE``).

Three kinds of date deliberately do not: an ISO-8601 date in a CSV data column,
which a spreadsheet sorts; a date written into the prose of an email body or a
public-site page (``F j, Y``); and the dates on a receipt PDF, which is a financial
record.
"""

from __future__ import annotations

from datetime import date, datetime

from django.utils import timezone

#: The ``strftime`` pattern for a date a reader sees: ``09/27/2026``.
DISPLAY_DATE_FORMAT = "%m/%d/%Y"

#: The ``strftime`` pattern for a moment a reader sees: ``09/27/2026 14:30``.
DISPLAY_DATETIME_FORMAT = f"{DISPLAY_DATE_FORMAT} %H:%M"


def format_display_date(day: date) -> str:
    """Return ``day`` as ``MM/DD/YYYY``, with leading zeros: ``09/04/2026``."""
    return day.strftime(DISPLAY_DATE_FORMAT)


def format_display_datetime(moment: datetime) -> str:
    """Return an aware ``moment`` as local ``MM/DD/YYYY HH:MM`` on a 24-hour clock.

    The moment is converted to the installation's time zone first, so an instant just
    after midnight UTC reads as the evening before in California.  A naive datetime
    raises ``ValueError``, as :func:`django.utils.timezone.localtime` does.
    """
    return timezone.localtime(moment).strftime(DISPLAY_DATETIME_FORMAT)
