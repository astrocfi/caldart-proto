"""Shared CSV and PDF report helpers.

The members, aircraft and payments reports build on these, so the house style
lives here rather than in any one app.

Fraunces and IBM Plex are web fonts and are not embedded in the PDFs; the
built-in Times/Helvetica families carry the same serif-display /
sans-supporting-text contrast.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable, Iterator, Sequence
from datetime import datetime
from typing import Any

from django.http import HttpResponse, StreamingHttpResponse
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import landscape as landscape_size
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    LongTable,
    PageTemplate,
    Paragraph,
    Spacer,
    TableStyle,
)

# House palette, matching the ``sierra`` theme.
INK = colors.HexColor("#1B1F24")
MUTED = colors.HexColor("#6B6F76")
RULE = colors.HexColor("#D9D3C7")
ZEBRA = colors.HexColor("#F4F1EA")
PRIMARY = colors.HexColor("#1F4D3A")

MARGIN = 0.5 * inch
BODY_FONT = "Helvetica"
BODY_FONT_BOLD = "Helvetica-Bold"
DISPLAY_FONT = "Times-Bold"

TITLE_STYLE = ParagraphStyle(
    "CalDartTitle",
    fontName=DISPLAY_FONT,
    fontSize=16,
    leading=19,
    textColor=INK,
    alignment=TA_LEFT,
    spaceAfter=2,
)
SUBTITLE_STYLE = ParagraphStyle(
    "CalDartSubtitle",
    fontName=BODY_FONT,
    fontSize=8,
    leading=11,
    textColor=MUTED,
    alignment=TA_LEFT,
)
CELL_STYLE = ParagraphStyle(
    "CalDartCell",
    fontName=BODY_FONT,
    fontSize=7.5,
    leading=9,
    textColor=INK,
)
HEADER_CELL_STYLE = ParagraphStyle(
    "CalDartHeaderCell",
    fontName=BODY_FONT_BOLD,
    fontSize=7.5,
    leading=9,
    textColor=INK,
)


# --------------------------------------------------------------------------
# CSV
# --------------------------------------------------------------------------
class _Echo:
    """A file-like object whose ``write`` simply returns the line."""

    def write(self, value: str) -> str:
        return value


def csv_rows(header: Sequence[str], rows: Iterable[Sequence[Any]]) -> Iterator[str]:
    """Yield the report as CSV text, one line at a time."""
    writer = csv.writer(_Echo())
    yield writer.writerow(list(header))
    for row in rows:
        yield writer.writerow(["" if value is None else value for value in row])


def csv_response(
    filename: str,
    header: Sequence[str],
    rows: Iterable[Sequence[Any]],
) -> StreamingHttpResponse:
    """Stream a CSV download.

    The rows are consumed lazily, so a report over the whole member table never
    materializes in memory.
    """
    response = StreamingHttpResponse(
        csv_rows(header, rows),
        content_type="text/csv; charset=utf-8",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


# --------------------------------------------------------------------------
# PDF
# --------------------------------------------------------------------------
class _NumberedCanvas(pdf_canvas.Canvas):
    """Canvas that can print "Page n of m" because it defers the page writes."""

    def __init__(self, *args, footer_left: str = "", **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_states: list[dict] = []
        self._footer_left = footer_left

    def showPage(self) -> None:  # noqa: N802 - reportlab API
        self._saved_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        total = len(self._saved_states)
        for state in self._saved_states:
            self.__dict__.update(state)
            self._draw_footer(total)
            super().showPage()
        super().save()

    def _draw_footer(self, total: int) -> None:
        width, _height = self._pagesize
        self.saveState()
        self.setStrokeColor(RULE)
        self.setLineWidth(0.5)
        self.line(MARGIN, MARGIN + 14, width - MARGIN, MARGIN + 14)
        self.setFont(BODY_FONT, 7)
        self.setFillColor(MUTED)
        self.drawString(MARGIN, MARGIN + 4, self._footer_left)
        self.drawRightString(width - MARGIN, MARGIN + 4, f"Page {self._pageNumber} of {total}")
        self.restoreState()


def _as_cells(values: Sequence[Any], style: ParagraphStyle) -> list[Paragraph]:
    cells = []
    for value in values:
        text = "" if value is None else str(value)
        text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        cells.append(Paragraph(text, style))
    return cells


def build_pdf_table(
    buffer,
    *,
    title: str,
    subtitle: str = "",
    header: Sequence[str],
    rows: Iterable[Sequence[Any]],
    landscape: bool = True,
    generated_at: datetime | None = None,
) -> None:
    """Render the report into ``buffer`` (any writable binary stream)."""
    pagesize = landscape_size(letter) if landscape else letter
    generated_at = generated_at or timezone.localtime()
    footer_left = f"CalDART · generated {generated_at:%Y-%m-%d %H:%M %Z}".strip()

    doc = BaseDocTemplate(
        buffer,
        pagesize=pagesize,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN + 20,
        title=title,
        author="CalDART",
    )
    frame = Frame(
        doc.leftMargin,
        doc.bottomMargin,
        doc.width,
        doc.height,
        leftPadding=0,
        rightPadding=0,
        topPadding=0,
        bottomPadding=0,
        id="body",
    )
    doc.addPageTemplates([PageTemplate(id="report", frames=[frame])])

    data = [_as_cells(header, HEADER_CELL_STYLE)]
    data.extend(_as_cells(row, CELL_STYLE) for row in rows)

    columns = len(header) or 1
    col_width = doc.width / columns

    style = TableStyle(
        [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            # Hairline rules instead of boxes.
            ("LINEBELOW", (0, 0), (-1, 0), 0.75, PRIMARY),
            ("LINEBELOW", (0, 1), (-1, -1), 0.25, RULE),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ZEBRA]),
        ]
    )

    table = LongTable(data, colWidths=[col_width] * columns, repeatRows=1)
    table.setStyle(style)

    story = [Paragraph(title, TITLE_STYLE)]
    if subtitle:
        story.append(Paragraph(subtitle, SUBTITLE_STYLE))
    story.append(Spacer(1, 10))
    story.append(table)

    def make_canvas(*args, **kwargs):
        return _NumberedCanvas(*args, footer_left=footer_left, **kwargs)

    doc.build(story, canvasmaker=make_canvas)


def pdf_table_response(
    filename: str,
    *,
    title: str,
    subtitle: str = "",
    header: Sequence[str],
    rows: Iterable[Sequence[Any]],
    landscape: bool = True,
) -> HttpResponse:
    """A landscape-letter PDF table download in the CalDART house style."""
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    build_pdf_table(
        response,
        title=title,
        subtitle=subtitle,
        header=header,
        rows=rows,
        landscape=landscape,
    )
    return response


def filter_summary(filters: dict[str, Any]) -> str:
    """Render applied filters for the PDF subtitle line."""
    parts = [f"{key.replace('_', ' ')}: {value}" for key, value in filters.items() if value]
    return " · ".join(parts) if parts else "No filters applied"
