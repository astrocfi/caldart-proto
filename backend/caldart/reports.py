"""Shared CSV and PDF report helpers.

The members, aircraft, and payments reports build on these, so the house style
lives here rather than in any one app.

Fraunces and IBM Plex are web fonts and are not embedded in the PDFs; the
built-in Times/Helvetica families carry the same serif-display /
sans-supporting-text contrast.
"""

from __future__ import annotations

import csv
from collections.abc import Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from typing import IO, Any, TypedDict

from django.http import HttpResponse, StreamingHttpResponse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import landscape as landscape_size
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    LongTable,
    PageTemplate,
    Paragraph,
    Spacer,
    TableStyle,
)
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

#: The media type every CSV export answers with.
CSV_MEDIA_TYPE = "text/csv; charset=utf-8"

#: The media type every PDF export answers with.
PDF_MEDIA_TYPE = "application/pdf"

#: An ``@extend_schema`` ``responses`` mapping keyed by status and media type.
type DownloadResponses = dict[tuple[HTTPStatus, str], OpenApiResponse]

# House palette, matching the ``duty`` theme.
INK = colors.HexColor("#1D2530")
MUTED = colors.HexColor("#55606D")
RULE = colors.HexColor("#CCD6E1")
ZEBRA = colors.HexColor("#EEF2F7")
PRIMARY = colors.HexColor("#1F4E79")

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

#: The padding a table cell carries on each side, in points.  It is width the
#: cell's text cannot use, so anything that asks whether a cell fits its column
#: subtracts twice this from the column.
CELL_PADDING = 3


# --------------------------------------------------------------------------
# Columns
# --------------------------------------------------------------------------
class ColumnDict(TypedDict):
    """One column as a ``columns`` endpoint reports it."""

    key: str
    label: str
    default: bool


@dataclass(frozen=True)
class ReportColumn[RowT]:
    """One column of a report: how to name it, whether to show it, how to read it.

    ``key`` is the stable name a caller asks for and an endpoint answers with,
    ``label`` the header text both exports print, ``default`` whether the column
    is in the report when the caller chooses none, and ``value`` a function from
    one row to that row's cell.  ``width`` is the share of the printable width
    the PDF gives the column, relative to the other columns of the same export,
    and defaults to an even share.  A report declares its columns once, in export
    order, and the CSV header, the PDF header and both row builders follow from
    that one tuple.
    """

    key: str
    label: str
    default: bool
    value: Callable[[RowT], object]
    width: float = 1.0


def select_columns[RowT](
    columns: Sequence[ReportColumn[RowT]],
    requested: Sequence[str] | None,
) -> list[ReportColumn[RowT]]:
    """The columns to export, given what the caller asked for.

    ``requested`` that is ``None`` or empty means the caller chose nothing, and
    the answer is every column whose ``default`` is true, in registry order.
    Otherwise the answer is one column per requested key, in the order
    requested, so a caller decides both which columns appear and where.

    A key no column carries raises ``ValueError`` reading ``Unknown column:
    <key>``, naming the first unknown key only, and a key asked for twice raises
    ``Repeated column: <key>``: a report has one cell per column, so a repeat is
    a mistake in the request rather than a wider table.  An endpoint turns
    either into a 400 keyed by ``columns``.
    """
    if requested is None or len(requested) == 0:
        return [column for column in columns if column.default]
    by_key = {column.key: column for column in columns}
    chosen: list[ReportColumn[RowT]] = []
    seen: set[str] = set()
    for key in requested:
        if key not in by_key:
            raise ValueError(f"Unknown column: {key}")
        if key in seen:
            raise ValueError(f"Repeated column: {key}")
        seen.add(key)
        chosen.append(by_key[key])
    return chosen


def column_payload[RowT](columns: Sequence[ReportColumn[RowT]]) -> list[ColumnDict]:
    """Describe ``columns`` for the screen that lets a reader choose them.

    One entry per column, in registry order, carrying the ``key`` ``?columns=``
    accepts, the ``label`` both exports print and whether the column is one of
    the ``default`` ones.  The relative width is the PDF's business and is not
    reported.
    """
    return [
        {"key": column.key, "label": column.label, "default": column.default} for column in columns
    ]


def chosen_columns[RowT](
    columns: Sequence[ReportColumn[RowT]], requested: str
) -> list[ReportColumn[RowT]]:
    """The columns a ``?columns=`` query parameter asks for, or the default ones.

    ``requested`` is the raw parameter: a comma-separated list of keys, or an
    empty string when the caller chose nothing, which means the default columns.
    A key no column carries, or one asked for twice, raises DRF's
    ``ValidationError`` keyed by ``columns`` and carrying the message
    :func:`select_columns` raises, so every export refuses a bad column list the
    same way and with a 400.
    """
    try:
        return select_columns(columns, requested.split(",") if requested else None)
    except ValueError as exc:
        raise ValidationError({"columns": [str(exc)]}) from exc


class ReportColumnSerializer(serializers.Serializer[ColumnDict]):
    """One entry of a report's ``columns`` endpoint, as :func:`column_payload` builds it.

    The chooser on the screen reads exactly these three fields.
    """

    key = serializers.CharField()
    # DRF's Field.label is a different thing from this serializer's own `label`
    # field, so the stubs see the declaration as a narrowing of the attribute.
    label = serializers.CharField()  # type: ignore[assignment]
    default = serializers.BooleanField()


def money_label(cents: int, *, currency: bool = True) -> str:
    """Integer cents as the dollars a reader sees, e.g. ``12345`` -> ``$123.45``.

    Money is integer cents everywhere in the database and the API, and this
    turns it into the text a person reads: a PDF cell, an email, a screen.
    Thousands are separated with commas and the cents are always shown.
    ``currency=False`` drops the dollar sign and the separators, giving
    ``123.45``, which is what a CSV cell carries so a spreadsheet reads the
    column as numbers.

    This is text for people.  A provider payload is not: an amount bound for
    Stripe or PayPal is built by the provider module that speaks to it, which
    knows what that API wants.
    """
    if not currency:
        return f"{cents / 100:.2f}"
    return f"${cents / 100:,.2f}"


# --------------------------------------------------------------------------
# CSV
# --------------------------------------------------------------------------
#: First characters a spreadsheet reads as the start of a formula rather than as
#: text.  Excel, LibreOffice, and Google Sheets all agree on these six.
FORMULA_PREFIXES = frozenset({"=", "+", "-", "@", "\t", "\r"})


class _Echo:
    """A file-like object whose ``write`` simply returns the line."""

    def write(self, value: str) -> str:
        return value


def csv_cell(value: object) -> object:
    """One value as the CSV should carry it.

    ``None`` becomes an empty cell.  A string that opens with one of
    :data:`FORMULA_PREFIXES` gains a leading apostrophe, which every spreadsheet
    strips on import and which stops the cell being evaluated as a formula.
    Everything else -- a number, a date, a decimal -- is handed to the ``csv``
    module untouched, so a negative amount stays a number a spreadsheet can add
    up.
    """
    if value is None:
        return ""
    if isinstance(value, str) and value[:1] in FORMULA_PREFIXES:
        return f"'{value}"
    return value


def csv_rows(header: Sequence[str], rows: Iterable[Sequence[Any]]) -> Iterator[str]:
    """Yield the report as CSV text, one line at a time.

    Every cell goes through :func:`csv_cell`, so no exported value can be read
    back as a spreadsheet formula.
    """
    writer = csv.writer(_Echo())
    yield writer.writerow(list(header))
    for row in rows:
        yield writer.writerow([csv_cell(value) for value in row])


def csv_response(
    filename: str,
    header: Sequence[str],
    rows: Iterable[Sequence[Any]],
) -> StreamingHttpResponse:
    """Stream a CSV download.

    The rows are consumed lazily, so a report over the whole member table never
    materializes in memory.
    """
    response = StreamingHttpResponse(csv_rows(header, rows), content_type=CSV_MEDIA_TYPE)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def download_responses(media_type: str, description: str) -> DownloadResponses:
    """The ``responses`` mapping of an endpoint that answers with a file download.

    An export answers with an attachment rather than a serialized object, so the
    one entry describes a ``200`` carrying an opaque binary body of ``media_type``,
    and leans on ``description`` to say which file arrives.  Pass the result
    straight to ``@extend_schema(responses=...)``.
    """
    return {
        (HTTPStatus.OK, media_type): OpenApiResponse(
            response=OpenApiTypes.BINARY, description=description
        )
    }


# --------------------------------------------------------------------------
# PDF
# --------------------------------------------------------------------------
class _NumberedCanvas(pdf_canvas.Canvas):
    """Canvas that can print "Page n of m" because it defers the page writes."""

    def __init__(self, *args: Any, footer_left: str = "", **kwargs: Any) -> None:
        """Wrap :class:`~reportlab.pdfgen.canvas.Canvas`, adding a ``footer_left`` label.

        ``args`` and ``kwargs`` pass straight through to ``Canvas.__init__``.
        """
        super().__init__(*args, **kwargs)
        self._saved_states: list[dict[str, Any]] = []
        self._footer_left = footer_left

    def showPage(self) -> None:  # noqa: N802 - reportlab API
        self._saved_states.append(dict(self.__dict__))
        self._startPage()  # type: ignore[attr-defined]  # reportlab-stubs omits this private method

    def save(self) -> None:
        total = len(self._saved_states)
        for state in self._saved_states:
            self.__dict__.update(state)
            self._draw_footer(total)
            super().showPage()
        super().save()

    def _draw_footer(self, total: int) -> None:
        # reportlab-stubs omits these private attributes (`_pagesize`, `_pageNumber`).
        width, _height = self._pagesize  # type: ignore[attr-defined]
        self.saveState()
        self.setStrokeColor(RULE)
        self.setLineWidth(0.5)
        self.line(MARGIN, MARGIN + 14, width - MARGIN, MARGIN + 14)
        self.setFont(BODY_FONT, 7)
        self.setFillColor(MUTED)
        self.drawString(MARGIN, MARGIN + 4, self._footer_left)
        page_number = self._pageNumber  # type: ignore[attr-defined]
        self.drawRightString(width - MARGIN, MARGIN + 4, f"Page {page_number} of {total}")
        self.restoreState()


def escape_markup(text: str) -> str:
    """Escape ``&``, ``<`` and ``>`` for reportlab's paragraph mini-markup.

    Every string that reaches a ``Paragraph`` goes through this first.  reportlab
    parses a paragraph as XML, so an unbalanced tag in a member's name or in a
    filter a caller chose -- ``<b``, say -- would otherwise abort the whole
    export with a parse error.  ``&`` is replaced first, so an escape sequence is
    never escaped twice.
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _as_cells(values: Sequence[Any], style: ParagraphStyle) -> list[Paragraph]:
    return [
        Paragraph(escape_markup("" if value is None else str(value)), style) for value in values
    ]


def build_pdf_table(
    buffer: IO[bytes],
    *,
    title: str,
    subtitle: str = "",
    header: Sequence[str],
    rows: Iterable[Sequence[Any]],
    landscape: bool = True,
    widths: Sequence[float] | None = None,
    generated_at: datetime | None = None,
) -> None:
    """Render the report into ``buffer`` (any writable binary stream).

    ``landscape`` chooses US letter on its side (792 x 612 points) or upright
    (612 x 792).  ``widths`` gives the columns relative shares of the printable
    width -- ``[3, 1, 1]`` makes the first column three times either of the
    others -- and the shares are scaled to fill the page, so their units do not
    matter.  Without it every column is the same width.  One width per column,
    or ``ValueError`` reading ``<n> columns but <m> widths`` before anything is
    drawn.
    """
    if widths is not None and len(widths) != len(header):
        raise ValueError(f"{len(header)} columns but {len(widths)} widths")
    pagesize = landscape_size(letter) if landscape else letter
    generated_at = generated_at or timezone.localtime()
    footer_left = f"CalDART \u00b7 generated {generated_at:%Y-%m-%d %H:%M %Z}".strip()

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
    if widths is None:
        col_widths = [doc.width / columns] * columns
    else:
        share = doc.width / sum(widths)
        col_widths = [width * share for width in widths]

    style = TableStyle(
        [
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), CELL_PADDING),
            ("RIGHTPADDING", (0, 0), (-1, -1), CELL_PADDING),
            ("TOPPADDING", (0, 0), (-1, -1), CELL_PADDING),
            ("BOTTOMPADDING", (0, 0), (-1, -1), CELL_PADDING),
            # Hairline rules instead of boxes.
            ("LINEBELOW", (0, 0), (-1, 0), 0.75, PRIMARY),
            ("LINEBELOW", (0, 1), (-1, -1), 0.25, RULE),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ZEBRA]),
        ]
    )

    table = LongTable(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(style)

    story: list[Flowable] = [Paragraph(escape_markup(title), TITLE_STYLE)]
    if subtitle:
        story.append(Paragraph(escape_markup(subtitle), SUBTITLE_STYLE))
    story.append(Spacer(1, 10))
    story.append(table)

    def make_canvas(*args: Any, **kwargs: Any) -> _NumberedCanvas:
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
    widths: Sequence[float] | None = None,
) -> HttpResponse:
    """A letter-size PDF table download in the CalDART house style.

    ``landscape`` and ``widths`` mean what they mean in :func:`build_pdf_table`;
    the default is a landscape page with columns of equal width.
    """
    response = HttpResponse(content_type=PDF_MEDIA_TYPE)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    build_pdf_table(
        response,  # type: ignore[arg-type]  # HttpResponse.write() duck-types IO[bytes]
        title=title,
        subtitle=subtitle,
        header=header,
        rows=rows,
        landscape=landscape,
        widths=widths,
    )
    return response


def filter_summary(filters: dict[str, Any]) -> str:
    """Render applied filters for the PDF subtitle line."""
    parts = [f"{key.replace('_', ' ')}: {value}" for key, value in filters.items() if value]
    return " \u00b7 ".join(parts) if parts else "No filters applied"
