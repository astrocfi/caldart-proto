"""Sections in the report engine: rows grouped under titled headings.

A spec that names a ``section`` for each row groups its table into sections, in the
order its query lists them or, without such a list, in the order the rows first name
them.  The CSV stays one flat table; the PDF draws a heading per section, each over
its own table.
"""

from __future__ import annotations

import io
from collections.abc import Sequence
from datetime import date

import pytest

from caldart.reports import (
    Params,
    ReportColumn,
    ReportQuery,
    ReportSection,
    ReportSpec,
    build_pdf_table,
    build_report,
)
from tests.conftest import PdfText

#: The day every table below is built on.
DAY = date(2026, 9, 26)

#: One row: the section it belongs to, then a name.
type Row = tuple[str, str]

#: Two columns over a row: its section and its name.
COLUMNS: tuple[ReportColumn[Row], ...] = (
    ReportColumn("group", "Group", True, lambda row: row[0]),
    ReportColumn("name", "Name", True, lambda row: row[1]),
)

#: Rows whose groups arrive out of order, so first-seen order is not listed order.
ROWS: list[Row] = [("Beta", "Bo"), ("Alpha", "Al"), ("Beta", "Bea")]

#: The italic line an empty section of the sectioned specs below draws.
EMPTY_LINE = "Nobody here."


def spec_for(
    rows: Sequence[Row],
    *,
    sections: Sequence[str] | None = None,
    sectioned: bool = True,
    empty_section: str = "",
) -> ReportSpec[Row]:
    """A spec over ``rows``, grouped by their first item unless ``sectioned`` is false.

    ``sections`` is what the query answers as the full list of section titles.
    """

    def query(params: Params) -> ReportQuery[Row]:
        return ReportQuery(rows=iter(rows), sections=sections)

    return ReportSpec(
        slug="grouped",
        title="Grouped report",
        filename_stem="grouped",
        columns=COLUMNS,
        roles=(),
        query=query,
        section=(lambda row: row[0]) if sectioned else None,
        empty_section=empty_section,
    )


def sections_of(spec: ReportSpec[Row]) -> list[ReportSection]:
    """The sections of ``spec``'s table, built as a CSV would build it."""
    return spec.table({}, fmt="csv", today=DAY).sections


# --------------------------------------------------------------------------
# Grouping
# --------------------------------------------------------------------------
def test_a_spec_without_sections_has_one_untitled_section_of_every_row() -> None:
    """With no ``section`` function, the table is one section titled ``""``."""
    assert sections_of(spec_for(ROWS, sectioned=False)) == [
        ReportSection(title="", rows=[["Beta", "Bo"], ["Alpha", "Al"], ["Beta", "Bea"]])
    ]


def test_listed_sections_come_in_the_listed_order() -> None:
    """With the titles listed, each section holds its rows, in the listed order."""
    assert sections_of(spec_for(ROWS, sections=["Alpha", "Beta"])) == [
        ReportSection(title="Alpha", rows=[["Alpha", "Al"]]),
        ReportSection(title="Beta", rows=[["Beta", "Bo"], ["Beta", "Bea"]]),
    ]


def test_a_listed_section_with_no_rows_still_appears() -> None:
    """A title the query lists but no row names is an empty section, in its place."""
    spec = spec_for(ROWS, sections=["Alpha", "Gamma", "Beta"])
    titles = [(section.title, len(section.rows)) for section in sections_of(spec)]
    assert titles == [("Alpha", 1), ("Gamma", 0), ("Beta", 2)]


def test_unlisted_sections_come_in_the_order_first_seen() -> None:
    """Without a list of titles, sections come in the order the rows first name them."""
    assert [section.title for section in sections_of(spec_for(ROWS))] == ["Beta", "Alpha"]


def test_a_row_in_an_unlisted_section_is_refused() -> None:
    """A row whose title the query did not list raises ``ValueError`` naming it."""
    with pytest.raises(ValueError, match=r"^Row in unlisted section 'Beta'$"):
        sections_of(spec_for(ROWS, sections=["Alpha"]))


def test_the_flat_rows_keep_every_row_in_query_order() -> None:
    """``ReportTable.rows`` is every row in the order the query answered them."""
    table = spec_for(ROWS, sections=["Alpha", "Beta"]).table({}, fmt="csv", today=DAY)
    assert table.rows == [["Beta", "Bo"], ["Alpha", "Al"], ["Beta", "Bea"]]


# --------------------------------------------------------------------------
# The CSV
# --------------------------------------------------------------------------
def test_the_csv_of_a_sectioned_report_is_one_flat_table() -> None:
    """The header, then every row, with no section heading between them."""
    document = build_report(spec_for(ROWS, sections=["Alpha", "Beta"]), {}, fmt="csv", today=DAY)
    assert document.content.decode().splitlines() == [
        "Group,Name",
        "Beta,Bo",
        "Alpha,Al",
        "Beta,Bea",
    ]


# --------------------------------------------------------------------------
# The PDF
# --------------------------------------------------------------------------
def pdf_strings(spec: ReportSpec[Row], pdf_text: PdfText) -> list[str]:
    """Every string the first page of ``spec``'s PDF draws, footer included."""
    document = build_report(spec, {}, fmt="pdf", today=DAY)
    return pdf_text(document.content)[0]


def test_the_pdf_draws_a_heading_and_a_table_per_section(pdf_text: PdfText) -> None:
    """Each section's title comes before its own header row and its own rows."""
    strings = pdf_strings(spec_for(ROWS, sections=["Alpha", "Beta"]), pdf_text)
    assert strings[2:13] == [
        "Alpha",
        "Group",
        "Name",
        "Alpha",
        "Al",
        "Beta",
        "Group",
        "Name",
        "Beta",
        "Bo",
        "Beta",
    ]


def test_an_empty_section_draws_the_spec_s_line(pdf_text: PdfText) -> None:
    """A section with no rows draws its title and then the spec's ``empty_section``."""
    spec = spec_for(ROWS, sections=["Gamma", "Alpha", "Beta"], empty_section=EMPTY_LINE)
    assert pdf_strings(spec, pdf_text)[2:5] == ["Gamma", EMPTY_LINE, "Alpha"]


def test_an_empty_section_is_its_title_alone_without_a_line(pdf_text: PdfText) -> None:
    """With a blank ``empty_section``, an empty section draws nothing under its title."""
    spec = spec_for(ROWS, sections=["Gamma", "Alpha", "Beta"])
    assert pdf_strings(spec, pdf_text)[2:5] == ["Gamma", "Alpha", "Group"]


def test_one_titled_section_is_drawn_with_its_heading(pdf_text: PdfText) -> None:
    """A report narrowed to one titled section still heads it with its title."""
    spec = spec_for([("Alpha", "Al")], sections=["Alpha"])
    assert pdf_strings(spec, pdf_text)[2:4] == ["Alpha", "Group"]


def test_an_unsectioned_pdf_draws_no_heading(pdf_text: PdfText) -> None:
    """A spec without sections draws the header row straight under the subtitle."""
    assert pdf_strings(spec_for(ROWS, sectioned=False), pdf_text)[2:4] == ["Group", "Name"]


def test_build_pdf_table_without_sections_draws_the_rows(pdf_text: PdfText) -> None:
    """``build_pdf_table`` given no ``sections`` draws ``rows`` as its one table."""
    buffer = io.BytesIO()
    build_pdf_table(buffer, title="T", header=["A"], rows=[["x"]])
    assert pdf_text(buffer.getvalue())[0][1:3] == ["A", "x"]
