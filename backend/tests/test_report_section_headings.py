"""A sectioned PDF report keeps each section's title on the page with its rows.

A title that would land at the foot of a page, with no room under it for the table's
header and first row, starts the next page instead, so a reader never meets a heading
standing alone above the page break.
"""

from __future__ import annotations

import io

import pytest

from caldart.reports import ReportSection, build_pdf_table
from tests.conftest import PdfText

#: The second section's title, which the test looks for on every page.
SECOND = "Second section"

#: The table header every section repeats.
HEADER = "Heading cell"


def _second_title_and_next(pdf_text: PdfText, rows_before: int) -> list[str]:
    """The second section's title and the string drawn after it, on its own page.

    The first section holds ``rows_before`` rows, which moves the second title down the
    page as it grows.  The title is followed on its page by the table's header when the
    two are kept together, and by the page footer when the title stands alone.
    """
    buffer = io.BytesIO()
    build_pdf_table(
        buffer,
        title="Report",
        header=[HEADER],
        rows=[],
        landscape=False,
        sections=[
            ReportSection(title="First section", rows=[["x"]] * rows_before),
            ReportSection(title=SECOND, rows=[["y"]]),
        ],
    )
    for page in pdf_text(buffer.getvalue()):
        if SECOND in page:
            index = page.index(SECOND)
            return page[index : index + 2]
    return []


@pytest.mark.parametrize("rows_before", range(30, 60))
def test_a_section_title_is_never_left_alone_at_the_foot_of_a_page(
    pdf_text: PdfText, rows_before: int
) -> None:
    """Wherever the second title falls, its table's header follows it on the same page."""
    assert _second_title_and_next(pdf_text, rows_before) == [SECOND, HEADER]
