"""The one place the backend writes a date for a reader: ``caldart.dates``.

A date a portal screen or a download shows reads ``MM/DD/YYYY``, and a moment adds
a 24-hour ``HH:MM`` in the installation's own time zone.  The docs page is
``docs/developer/architecture.rst``.
"""

from __future__ import annotations

import datetime as dt
import io
from zoneinfo import ZoneInfo

import pytest

from caldart.dates import (
    DISPLAY_DATE_FORMAT,
    DISPLAY_DATETIME_FORMAT,
    format_display_date,
    format_display_datetime,
)
from caldart.reports import build_pdf_table
from tests.conftest import PdfText

#: The installation's time zone, which ``TIME_ZONE`` names.
PACIFIC = ZoneInfo("America/Los_Angeles")


def test_the_date_format_is_month_day_year() -> None:
    """``DISPLAY_DATE_FORMAT`` is the ``strftime`` pattern for ``MM/DD/YYYY``."""
    assert DISPLAY_DATE_FORMAT == "%m/%d/%Y"


def test_the_datetime_format_adds_a_24_hour_clock() -> None:
    """``DISPLAY_DATETIME_FORMAT`` is ``MM/DD/YYYY HH:MM``."""
    assert DISPLAY_DATETIME_FORMAT == "%m/%d/%Y %H:%M"


def test_a_date_reads_month_day_year_with_leading_zeros() -> None:
    """September 4, 2026 reads ``09/04/2026``."""
    assert format_display_date(dt.date(2026, 9, 4)) == "09/04/2026"


def test_a_moment_reads_in_the_local_time_zone() -> None:
    """A UTC instant prints as the installation's own day and minute."""
    moment = dt.datetime(2026, 1, 8, 17, 5, tzinfo=dt.UTC)

    assert format_display_datetime(moment) == "01/08/2026 09:05"


def test_a_moment_just_after_utc_midnight_reads_the_local_day_before() -> None:
    """03:00 UTC on the 2nd is still the evening of the 1st in California."""
    moment = dt.datetime(2026, 3, 2, 3, 0, tzinfo=dt.UTC)

    assert format_display_datetime(moment) == "03/01/2026 19:00"


def test_a_naive_moment_is_refused() -> None:
    """A datetime without a time zone cannot be placed in the local day, so it raises."""
    with pytest.raises(ValueError, match="naive"):
        format_display_datetime(dt.datetime(2026, 9, 27, 14, 30))


def test_the_pdf_footer_stamps_the_moment_in_the_display_format(pdf_text: PdfText) -> None:
    """The report footer stamps its moment as ``generated MM/DD/YYYY HH:MM <zone>``."""
    buffer = io.BytesIO()
    build_pdf_table(
        buffer,
        title="Anything",
        header=["One"],
        rows=[["a"]],
        generated_at=dt.datetime(2026, 9, 27, 14, 30, tzinfo=PACIFIC),
    )

    assert "CalDART \u00b7 generated 09/27/2026 14:30 PDT" in pdf_text(buffer.getvalue())[0]


def test_the_pdf_footer_stamps_a_utc_moment_in_local_time(pdf_text: PdfText) -> None:
    """A UTC ``generated_at`` is stamped as the installation's own time and zone."""
    buffer = io.BytesIO()
    build_pdf_table(
        buffer,
        title="Anything",
        header=["One"],
        rows=[["a"]],
        generated_at=dt.datetime(2026, 9, 27, 21, 30, tzinfo=dt.UTC),
    )

    assert "CalDART \u00b7 generated 09/27/2026 14:30 PDT" in pdf_text(buffer.getvalue())[0]
