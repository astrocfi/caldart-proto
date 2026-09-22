"""Shared CSV/PDF report helpers."""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Callable, Iterator
from typing import cast

import pytest
from django.http import StreamingHttpResponse

from caldart.reports import csv_response, csv_rows, filter_summary, pdf_table_response

HEADER: list[str] = ["name", "email", "n_number", "expires_on"]
ROWS: list[list[str | None]] = [
    ["Marta Reyes", "marta@example.org", "N172SP", "2027-01-31"],
    ["Owen Delgado", "owen@example.org", "N9021K", None],
    ['Quote "Q" & Co', "q@example.org", "N1", "2026-12-01"],
]

#: The subtitle line under the title, with the middle dot the summary joins on.
SUBTITLE = "status: current \u00b7 dart: Palo Alto"

#: ``pdf_text(body)`` -> the strings each page of a rendered PDF draws.
PdfText = Callable[[bytes], list[list[str]]]


def test_csv_response_is_streaming_and_has_a_download_header() -> None:
    """``csv_response`` returns a streaming response with a CSV download header."""
    response = csv_response("members.csv", HEADER, iter(ROWS))
    assert isinstance(response, StreamingHttpResponse)
    assert response["Content-Disposition"] == 'attachment; filename="members.csv"'
    assert response["Content-Type"].startswith("text/csv")


def test_csv_response_content() -> None:
    """The streamed body is well-formed CSV matching the header and rows given."""
    response = csv_response("members.csv", HEADER, iter(ROWS))
    # django-stubs types streaming_content for ASGI too; this response is sync-only.
    streaming_content = cast("Iterator[bytes]", response.streaming_content)
    body = b"".join(streaming_content).decode()
    parsed = list(csv.reader(io.StringIO(body)))
    assert parsed[0] == HEADER
    assert parsed[1] == ["Marta Reyes", "marta@example.org", "N172SP", "2027-01-31"]
    # None becomes an empty cell, quoting is handled by the csv module.
    assert parsed[2][3] == ""
    assert parsed[3][0] == 'Quote "Q" & Co'
    assert len(parsed) == 4


def test_csv_rows_is_lazy() -> None:
    """``csv_rows`` pulls from its source only as each row is consumed."""
    consumed: list[str | None] = []

    def source() -> Iterator[list[str | None]]:
        for row in ROWS:
            consumed.append(row[0])
            yield row

    stream = csv_rows(HEADER, source())
    next(stream)  # header only
    assert consumed == []
    next(stream)
    assert consumed == ["Marta Reyes"]


def _page_count(pdf: bytes) -> int:
    """Return the number of ``/Type /Page`` objects in a rendered PDF's bytes."""
    return len(re.findall(rb"/Type\s*/Page[^s]", pdf))


def test_pdf_table_response_is_a_valid_pdf() -> None:
    """``pdf_table_response`` returns a one-page PDF with the right download headers."""
    response = pdf_table_response(
        "members.pdf",
        title="Membership report",
        subtitle=SUBTITLE,
        header=HEADER,
        rows=ROWS,
    )
    assert response["Content-Type"] == "application/pdf"
    assert response["Content-Disposition"] == 'attachment; filename="members.pdf"'
    body = response.content
    assert body.startswith(b"%PDF-")
    assert body.rstrip().endswith(b"%%EOF")
    assert _page_count(body) == 1


def test_pdf_draws_the_title_the_subtitle_and_every_cell(pdf_text: PdfText) -> None:
    """The page shows the title, the subtitle, the header and every non-empty cell."""
    response = pdf_table_response(
        "members.pdf",
        title="Membership report",
        subtitle=SUBTITLE,
        header=HEADER,
        rows=ROWS,
    )
    page = pdf_text(response.content)[0]
    assert page[:2] == ["Membership report", SUBTITLE]
    assert page[2:6] == HEADER
    # The ``None`` cell of the second row draws nothing at all.
    assert page[6:17] == [
        "Marta Reyes",
        "marta@example.org",
        "N172SP",
        "2027-01-31",
        "Owen Delgado",
        "owen@example.org",
        "N9021K",
        'Quote "Q" & Co',
        "q@example.org",
        "N1",
        "2026-12-01",
    ]


@pytest.mark.parametrize(
    ("landscape", "expected_pages"), [(True, 4), (False, 3)], ids=["landscape", "portrait"]
)
def test_pdf_paginates_100_rows_with_a_repeated_header(
    landscape: bool, expected_pages: int, pdf_text: PdfText
) -> None:
    """A 100-row table spans several pages, each continuation repeating the header."""
    rows = [[f"Member {i}", f"m{i}@example.org", f"N{i:04d}A", "2027-01-31"] for i in range(100)]
    response = pdf_table_response(
        "members.pdf",
        title="Membership report",
        header=HEADER,
        rows=rows,
        landscape=landscape,
    )
    pages = pdf_text(response.content)
    assert len(pages) == expected_pages
    # The title opens the first page; every later page opens with the header.
    assert pages[0][:5] == ["Membership report", *HEADER]
    assert [page[:4] for page in pages[1:]] == [HEADER] * (expected_pages - 1)
    assert "Member 0" in pages[0]
    assert "Member 99" in pages[-1]


def test_pdf_handles_an_empty_result_set(pdf_text: PdfText) -> None:
    """A table with no rows renders one page carrying the title and header alone."""
    response = pdf_table_response("members.pdf", title="Membership report", header=HEADER, rows=[])
    pages = pdf_text(response.content)
    assert len(pages) == 1
    assert pages[0][:5] == ["Membership report", *HEADER]


def test_pdf_escapes_markup_in_cells(pdf_text: PdfText) -> None:
    """A cell containing HTML-like markup is drawn as the literal text it holds."""
    response = pdf_table_response(
        "x.pdf",
        title="Report",
        header=["value"],
        rows=[["<b>not bold</b> & co"]],
    )
    page = pdf_text(response.content)[0]
    # The paragraph splits at each angle bracket, so read the cell as one string.
    assert "".join(page[2:-2]) == "<b>not bold</b> & co"


def test_filter_summary() -> None:
    """``filter_summary`` joins active filters and reports when none are active."""
    assert filter_summary({"status": "current", "dart": "", "expiring_within": 30}) == (
        "status: current · expiring within: 30"
    )
    assert filter_summary({}) == "No filters applied"
