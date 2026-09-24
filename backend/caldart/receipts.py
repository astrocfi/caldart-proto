"""The receipt and the annual contribution statement, as PDFs.

Two builders, both pure: a typed dataclass in, a rendered PDF out.  Nothing
here reads a model or the database, so whichever app holds the payments can
gather the facts it already has and hand them over without an import cycle.

Both documents are upright US letter in the CalDART house palette, which lives
in :mod:`caldart.reports` alongside the CSV and table-PDF exports.  A receipt
acknowledges one payment; a statement gathers a calendar year of contributions
for a member's tax return.  Membership dues are printed as dues: only a
contribution carries the 501(c)(3) wording, because only a contribution is a
gift.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import IO

from django.utils import timezone
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from caldart.org import OrgDetails
from caldart.reports import (
    BODY_FONT,
    BODY_FONT_BOLD,
    CELL_STYLE,
    HEADER_CELL_STYLE,
    INK,
    MARGIN,
    MUTED,
    PRIMARY,
    RULE,
    SUBTITLE_STYLE,
    TITLE_STYLE,
    dollars,
    escape_markup,
)

#: The printable width of an upright US-letter page inside one-inch margins.
CONTENT_WIDTH = letter[0] - 4 * MARGIN

#: What a receipt says under a contribution, and what makes it usable as a
#: donor's substantiation.
CONTRIBUTION_NOTICE = "No goods or services were provided in exchange for this contribution."

#: The same, for a statement covering a year of them.
CONTRIBUTIONS_NOTICE = "No goods or services were provided in exchange for these contributions."

#: Style for the one-line heading above a block of detail.
HEADING_STYLE = ParagraphStyle(
    "CalDartReceiptHeading",
    fontName=BODY_FONT_BOLD,
    fontSize=11,
    leading=14,
    textColor=PRIMARY,
    spaceAfter=4,
)

#: Style for a line of ordinary running text.
TEXT_STYLE = ParagraphStyle(
    "CalDartReceiptText",
    fontName=BODY_FONT,
    fontSize=9,
    leading=12,
    textColor=INK,
)

#: Style for the quieter lines: the letterhead and the closing note.
NOTE_STYLE = ParagraphStyle(
    "CalDartReceiptNote",
    fontName=BODY_FONT,
    fontSize=8,
    leading=11,
    textColor=MUTED,
)

#: Table cells carrying money, which reads best flush right.
AMOUNT_STYLE = ParagraphStyle("CalDartReceiptAmount", parent=CELL_STYLE, alignment=TA_RIGHT)

#: The same for a money column's header.
AMOUNT_HEADER_STYLE = ParagraphStyle(
    "CalDartReceiptAmountHeader", parent=HEADER_CELL_STYLE, alignment=TA_RIGHT
)

#: Style for a total, which is the one row a reader looks for.
TOTAL_STYLE = ParagraphStyle("CalDartReceiptTotal", parent=AMOUNT_STYLE, fontName=BODY_FONT_BOLD)

#: Style for the label beside a total.
TOTAL_LABEL_STYLE = ParagraphStyle(
    "CalDartReceiptTotalLabel", parent=CELL_STYLE, fontName=BODY_FONT_BOLD
)


@dataclass(frozen=True)
class ReceiptLine:
    """One thing a payment bought.

    ``label`` names it ("Annual membership", "Contribution"), ``detail`` says
    more where there is more to say (a term's dates), and ``amount_cents`` is
    what that part of the payment came to.  ``deductible`` marks a line as a
    gift rather than value received, which is what brings the 501(c)(3)
    sentence onto the page.
    """

    label: str
    detail: str = ""
    amount_cents: int = 0
    deductible: bool = False


@dataclass(frozen=True)
class ReceiptData:
    """Everything a receipt prints.

    ``receipt_number`` is the reference a member quotes when they write in,
    ``issued_on`` the day the money was received, and ``provider_label`` and
    ``provider_ref`` how it arrived and the reference to trace it by.  An empty
    ``provider_ref`` -- a check, say -- prints the provider alone.
    """

    org: OrgDetails
    receipt_number: str
    issued_on: date
    payer_name: str
    payer_email: str
    lines: Sequence[ReceiptLine] = ()
    provider_label: str = ""
    provider_ref: str = ""

    @property
    def total_cents(self) -> int:
        """What the payment came to: the sum of the lines, in cents."""
        return sum(line.amount_cents for line in self.lines)

    @property
    def has_contribution(self) -> bool:
        """Whether any line is a gift, and so whether the receipt claims a deduction."""
        return any(line.deductible for line in self.lines)


@dataclass(frozen=True)
class StatementLine:
    """One contribution in a year's statement.

    ``amount_cents`` is what was given and ``refunded_cents`` what came back,
    so a contribution refunded in part still appears, honestly netted.
    """

    paid_on: date
    receipt_number: str
    amount_cents: int
    refunded_cents: int = 0

    @property
    def net_cents(self) -> int:
        """What the member gave and kept giving: the amount less the refund."""
        return self.amount_cents - self.refunded_cents


@dataclass(frozen=True)
class StatementData:
    """A member's contributions for one calendar year.

    ``contributions`` are in the order they are printed, which is the order
    they were paid.  A year with none renders a page whose total is zero rather
    than an empty document.
    """

    org: OrgDetails
    year: int
    member_name: str
    member_email: str
    contributions: Sequence[StatementLine] = field(default_factory=tuple)

    @property
    def total_cents(self) -> int:
        """The year's giving, net of every refund, in cents."""
        return sum(line.net_cents for line in self.contributions)


def build_receipt_pdf(buffer: IO[bytes], receipt: ReceiptData) -> None:
    """Render the receipt for one payment into ``buffer``.

    One upright US-letter page: the organization's letterhead, the receipt
    number and date, who paid, a line per thing the payment bought with its
    amount in dollars, the total, and how the money arrived.  A receipt
    carrying a contribution also prints :data:`CONTRIBUTION_NOTICE`; one that
    is dues alone does not, because dues are value received.
    """
    story = _letterhead(receipt.org)
    story.append(Paragraph(escape_markup(f"Receipt {receipt.receipt_number}"), TITLE_STYLE))
    story.append(
        Paragraph(escape_markup(f"Received {receipt.issued_on.isoformat()}"), SUBTITLE_STYLE)
    )
    story.append(Spacer(1, 12))
    story.append(Paragraph("Received from", HEADING_STYLE))
    story.append(Paragraph(escape_markup(receipt.payer_name), TEXT_STYLE))
    story.append(Paragraph(escape_markup(receipt.payer_email), TEXT_STYLE))
    story.append(Spacer(1, 14))

    rows: list[list[Paragraph]] = [
        [
            Paragraph("Description", HEADER_CELL_STYLE),
            Paragraph("Amount", AMOUNT_HEADER_STYLE),
        ]
    ]
    rows.extend(
        [
            Paragraph(escape_markup(_described(line)), CELL_STYLE),
            Paragraph(dollars(line.amount_cents), AMOUNT_STYLE),
        ]
        for line in receipt.lines
    )
    rows.append(
        [
            Paragraph("Total", TOTAL_LABEL_STYLE),
            Paragraph(dollars(receipt.total_cents), TOTAL_STYLE),
        ]
    )
    story.append(_money_table(rows, widths=[5.2, 1.8]))

    if receipt.has_contribution:
        story.append(Spacer(1, 12))
        story.append(Paragraph(CONTRIBUTION_NOTICE, TEXT_STYLE))

    paid_with = _paid_with(receipt)
    if paid_with:
        story.append(Spacer(1, 12))
        story.append(Paragraph(escape_markup(paid_with), NOTE_STYLE))

    _render(buffer, title=f"Receipt {receipt.receipt_number}", story=story)


def build_statement_pdf(buffer: IO[bytes], statement: StatementData) -> None:
    """Render a member's annual contribution statement into ``buffer``.

    One upright US-letter page: the letterhead, the year, the member, a row per
    contribution with its date, receipt number, amount, refund and net, the
    year's total net of refunds, and :data:`CONTRIBUTIONS_NOTICE`.  Membership
    dues are not on it; a statement covers gifts alone.
    """
    story = _letterhead(statement.org)
    story.append(
        Paragraph(escape_markup(f"Contribution statement for {statement.year}"), TITLE_STYLE)
    )
    story.append(Spacer(1, 12))
    story.append(Paragraph("Contributions from", HEADING_STYLE))
    story.append(Paragraph(escape_markup(statement.member_name), TEXT_STYLE))
    story.append(Paragraph(escape_markup(statement.member_email), TEXT_STYLE))
    story.append(Spacer(1, 14))

    rows: list[list[Paragraph]] = [
        [
            Paragraph("Date", HEADER_CELL_STYLE),
            Paragraph("Receipt", HEADER_CELL_STYLE),
            Paragraph("Contribution", AMOUNT_HEADER_STYLE),
            Paragraph("Refunded", AMOUNT_HEADER_STYLE),
            Paragraph("Net", AMOUNT_HEADER_STYLE),
        ]
    ]
    rows.extend(
        [
            Paragraph(line.paid_on.isoformat(), CELL_STYLE),
            Paragraph(escape_markup(line.receipt_number), CELL_STYLE),
            Paragraph(dollars(line.amount_cents), AMOUNT_STYLE),
            Paragraph(dollars(line.refunded_cents), AMOUNT_STYLE),
            Paragraph(dollars(line.net_cents), AMOUNT_STYLE),
        ]
        for line in statement.contributions
    )
    rows.append(
        [
            Paragraph(f"Total for {statement.year}", TOTAL_LABEL_STYLE),
            Paragraph("", CELL_STYLE),
            Paragraph("", CELL_STYLE),
            Paragraph("", CELL_STYLE),
            Paragraph(dollars(statement.total_cents), TOTAL_STYLE),
        ]
    )
    story.append(_money_table(rows, widths=[1.2, 1.7, 1.4, 1.3, 1.4]))

    story.append(Spacer(1, 12))
    story.append(Paragraph(CONTRIBUTIONS_NOTICE, TEXT_STYLE))

    _render(buffer, title=f"Contribution statement {statement.year}", story=story)


def _described(line: ReceiptLine) -> str:
    """The receipt's description cell: the label, and the detail when there is one."""
    return f"{line.label} ({line.detail})" if line.detail else line.label


def _paid_with(receipt: ReceiptData) -> str:
    """The closing note naming the provider and its reference, or ``""``."""
    if not receipt.provider_label:
        return ""
    if not receipt.provider_ref:
        return f"Paid with {receipt.provider_label}"
    return f"Paid with {receipt.provider_label}, reference {receipt.provider_ref}"


def _letterhead(org: OrgDetails) -> list[Flowable]:
    """The organization's name, address, EIN and contact address, then a gap.

    A field nobody has filled in draws no line at all, so an unconfigured site
    still yields a tidy page.
    """
    story: list[Flowable] = [Paragraph(escape_markup(org.name), TITLE_STYLE)]
    story.extend(
        Paragraph(escape_markup(part), NOTE_STYLE)
        for part in org.mailing_address.splitlines()
        if part.strip()
    )
    if org.ein:
        story.append(Paragraph(escape_markup(f"EIN {org.ein}"), NOTE_STYLE))
    if org.contact_email:
        story.append(Paragraph(escape_markup(org.contact_email), NOTE_STYLE))
    story.append(Spacer(1, 18))
    return story


def _money_table(rows: list[list[Paragraph]], *, widths: list[float]) -> Table:
    """A table of amounts: a ruled header, hairline rows and a ruled total.

    ``widths`` are the columns' relative shares of the printable width, scaled
    to fill it, so their units do not matter.
    """
    share = CONTENT_WIDTH / sum(widths)
    table = Table(rows, colWidths=[width * share for width in widths])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, 0), 0.75, PRIMARY),
                ("LINEBELOW", (0, 1), (-1, -2), 0.25, RULE),
                ("LINEABOVE", (0, -1), (-1, -1), 0.75, PRIMARY),
            ]
        )
    )
    return table


def _render(buffer: IO[bytes], *, title: str, story: list[Flowable]) -> None:
    """Lay ``story`` out on upright US letter and write the PDF to ``buffer``."""
    doc = BaseDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=MARGIN * 2,
        rightMargin=MARGIN * 2,
        topMargin=MARGIN * 2,
        bottomMargin=MARGIN * 2,
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
    doc.addPageTemplates([PageTemplate(id="receipt", frames=[frame])])
    generated = timezone.localtime()
    story = [*story, Spacer(1, 18), Paragraph(f"Generated {generated:%Y-%m-%d}", NOTE_STYLE)]
    doc.build(story)
