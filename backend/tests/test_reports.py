"""Shared CSV/PDF report helpers."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from django.http import StreamingHttpResponse

from caldart.reports import (
    ReportColumn,
    csv_response,
    csv_rows,
    dollars,
    filter_summary,
    pdf_table_response,
    select_columns,
)
from tests.conftest import PdfText, pdf_page_count, read_csv

HEADER: list[str] = ["name", "email", "n_number", "expires_on"]
ROWS: list[list[str | None]] = [
    ["Marta Reyes", "marta@example.org", "N172SP", "2027-01-31"],
    ["Owen Delgado", "owen@example.org", "N9021K", None],
    ['Quote "Q" & Co', "q@example.org", "N1", "2026-12-01"],
]

#: The subtitle line under the title, with the middle dot the summary joins on.
SUBTITLE = "status: current \u00b7 dart: Palo Alto"


def test_csv_response_is_streaming_and_has_a_download_header() -> None:
    """``csv_response`` returns a streaming response with a CSV download header."""
    response = csv_response("members.csv", HEADER, iter(ROWS))
    assert isinstance(response, StreamingHttpResponse)
    assert response["Content-Disposition"] == 'attachment; filename="members.csv"'
    assert response["Content-Type"].startswith("text/csv")


def test_csv_response_content() -> None:
    """The streamed body is well-formed CSV matching the header and rows given."""
    parsed = read_csv(csv_response("members.csv", HEADER, iter(ROWS)))
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
    assert pdf_page_count(body) == 1


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


def test_filter_summary_joins_the_active_filters_and_skips_the_empty_ones() -> None:
    """Active filters join with a middle dot; a filter with an empty value is dropped."""
    assert filter_summary({"status": "current", "dart": "", "expiring_within": 30}) == (
        "status: current \u00b7 expiring within: 30"
    )


def test_filter_summary_says_so_when_no_filter_is_active() -> None:
    """An empty filter mapping summarizes as "No filters applied"."""
    assert filter_summary({}) == "No filters applied"


#: A three-column registry over a ``(name, email, note)`` row, two columns on by default.
COLUMNS: tuple[ReportColumn[tuple[str, str, str]], ...] = (
    ReportColumn("name", "Name", True, lambda row: row[0]),
    ReportColumn("email", "Email", True, lambda row: row[1]),
    ReportColumn("note", "Note", False, lambda row: row[2]),
)


def test_select_columns_answers_the_defaults_when_nothing_is_requested() -> None:
    """No requested list means the columns whose ``default`` is true, in order."""
    assert [column.key for column in select_columns(COLUMNS, None)] == ["name", "email"]


def test_select_columns_answers_the_defaults_for_an_empty_request() -> None:
    """An empty requested list is read as "no choice made", not as "no columns"."""
    assert [column.key for column in select_columns(COLUMNS, [])] == ["name", "email"]


def test_select_columns_follows_the_requested_order() -> None:
    """The chosen columns come back in the order asked for, defaults ignored."""
    chosen = select_columns(COLUMNS, ["note", "name"])
    assert [column.key for column in chosen] == ["note", "name"]


def test_select_columns_rejects_the_first_unknown_key() -> None:
    """An unrecognized key raises ``ValueError`` naming that key and nothing else."""
    with pytest.raises(ValueError, match="Unknown column: shoe_size"):
        select_columns(COLUMNS, ["name", "shoe_size", "hat_size"])


def test_report_column_reads_a_row_through_its_value_function() -> None:
    """A column's ``value`` turns one row into the cell the exports write."""
    column = select_columns(COLUMNS, ["email"])[0]
    assert column.label == "Email"
    assert column.value(("Marta Reyes", "marta@example.org", "check 1180")) == "marta@example.org"


@pytest.mark.parametrize(
    ("cents", "expected"),
    [(0, "$0.00"), (5, "$0.05"), (12345, "$123.45"), (100000000, "$1,000,000.00")],
    ids=["zero", "cents-only", "dollars-and-cents", "millions"],
)
def test_dollars_formats_integer_cents_for_a_reader(cents: int, expected: str) -> None:
    """Integer cents read as dollars with a thousands separator and two decimals."""
    assert dollars(cents) == expected


@pytest.mark.parametrize(
    ("landscape", "expected_box"),
    [(True, b"/MediaBox [ 0 0 792 612 ]"), (False, b"/MediaBox [ 0 0 612 792 ]")],
    ids=["landscape", "portrait"],
)
def test_pdf_page_size_follows_the_landscape_flag(landscape: bool, expected_box: bytes) -> None:
    """``landscape`` chooses between US letter on its side and US letter upright."""
    response = pdf_table_response(
        "members.pdf", title="Report", header=HEADER, rows=ROWS, landscape=landscape
    )
    assert expected_box in response.content


def test_pdf_relative_widths_decide_how_much_room_each_column_gets(pdf_text: PdfText) -> None:
    """A column given the larger share of the width fits text that otherwise wraps."""
    sentence = "Palo Alto Airport disaster airlift standby"
    wide_first = pdf_table_response(
        "x.pdf",
        title="Report",
        header=["note", "code"],
        rows=[[sentence, "A"]],
        widths=[9, 1],
    )
    narrow_first = pdf_table_response(
        "x.pdf",
        title="Report",
        header=["note", "code"],
        rows=[[sentence, "A"]],
        widths=[1, 9],
    )
    assert sentence in pdf_text(wide_first.content)[0]
    assert sentence not in pdf_text(narrow_first.content)[0]


def test_pdf_rejects_widths_that_do_not_match_the_header() -> None:
    """One relative width per column, or ``ValueError`` before anything is drawn."""
    with pytest.raises(ValueError, match="4 columns but 2 widths"):
        pdf_table_response("x.pdf", title="Report", header=HEADER, rows=ROWS, widths=[1, 1])
