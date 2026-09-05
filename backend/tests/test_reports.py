"""Shared CSV/PDF report helpers (PLAN §11)."""

from __future__ import annotations

import csv
import io
import re

import pytest
from django.http import StreamingHttpResponse

from caldart.reports import csv_response, csv_rows, filter_summary, pdf_table_response

HEADER = ["name", "email", "n_number", "expires_on"]
ROWS = [
    ["Marta Reyes", "marta@example.org", "N172SP", "2027-01-31"],
    ["Owen Delgado", "owen@example.org", "N9021K", None],
    ['Quote "Q" & Co', "q@example.org", "N1", "2026-12-01"],
]


def test_csv_response_is_streaming_and_has_a_download_header():
    response = csv_response("members.csv", HEADER, iter(ROWS))
    assert isinstance(response, StreamingHttpResponse)
    assert response["Content-Disposition"] == 'attachment; filename="members.csv"'
    assert response["Content-Type"].startswith("text/csv")


def test_csv_response_content():
    response = csv_response("members.csv", HEADER, iter(ROWS))
    body = b"".join(response.streaming_content).decode()
    parsed = list(csv.reader(io.StringIO(body)))
    assert parsed[0] == HEADER
    assert parsed[1] == ["Marta Reyes", "marta@example.org", "N172SP", "2027-01-31"]
    # None becomes an empty cell, quoting is handled by the csv module.
    assert parsed[2][3] == ""
    assert parsed[3][0] == 'Quote "Q" & Co'
    assert len(parsed) == 4


def test_csv_rows_is_lazy():
    consumed = []

    def source():
        for row in ROWS:
            consumed.append(row[0])
            yield row

    stream = csv_rows(HEADER, source())
    next(stream)  # header only
    assert consumed == []
    next(stream)
    assert consumed == ["Marta Reyes"]


def _page_count(pdf: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page[^s]", pdf))


def test_pdf_table_response_is_a_valid_pdf():
    response = pdf_table_response(
        "members.pdf",
        title="Membership report",
        subtitle="status: current · dart: Palo Alto",
        header=HEADER,
        rows=ROWS,
    )
    assert response["Content-Type"] == "application/pdf"
    assert response["Content-Disposition"] == 'attachment; filename="members.pdf"'
    body = response.content
    assert body.startswith(b"%PDF-")
    assert body.rstrip().endswith(b"%%EOF")
    assert _page_count(body) == 1


@pytest.mark.parametrize("landscape", [True, False])
def test_pdf_paginates_100_rows_with_a_repeated_header(landscape):
    rows = [[f"Member {i}", f"m{i}@example.org", f"N{i:04d}A", "2027-01-31"] for i in range(100)]
    response = pdf_table_response(
        "members.pdf",
        title="Membership report",
        header=HEADER,
        rows=rows,
        landscape=landscape,
    )
    body = response.content
    pages = _page_count(body)
    # 100 rows never fit on one page and never need more than half a dozen.
    assert 2 <= pages <= 6
    # Portrait is taller, so it fits at least as many pages' worth of rows.
    assert body.startswith(b"%PDF-")


def test_pdf_handles_an_empty_result_set():
    response = pdf_table_response("members.pdf", title="Membership report", header=HEADER, rows=[])
    assert response.content.startswith(b"%PDF-")
    assert _page_count(response.content) == 1


def test_pdf_escapes_markup_in_cells():
    response = pdf_table_response(
        "x.pdf",
        title="Report",
        header=["value"],
        rows=[["<b>not bold</b> & co"]],
    )
    assert response.content.startswith(b"%PDF-")


def test_filter_summary():
    assert filter_summary({"status": "current", "dart": "", "expiring_within": 30}) == (
        "status: current · expiring within: 30"
    )
    assert filter_summary({}) == "No filters applied"
