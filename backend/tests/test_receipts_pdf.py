"""The receipt and contribution-statement PDFs."""

from __future__ import annotations

import io
from dataclasses import replace
from datetime import date

import pytest

from caldart.org import OrgDetails
from caldart.receipts import (
    CONTRIBUTION_NOTICE,
    CONTRIBUTIONS_NOTICE,
    ReceiptData,
    ReceiptLine,
    StatementData,
    StatementLine,
    build_receipt_pdf,
    build_statement_pdf,
)
from tests.conftest import PdfText, pdf_page_count

ORG = OrgDetails(
    name="The California DART Network",
    contact_email="info@caldart.example.org",
    mailing_address="PO Box 41\nPalo Alto, CA 94301",
    ein="94-1234567",
    site_url="https://caldart.example.org",
)

DUES = ReceiptLine(
    label="Annual membership",
    detail="2026-03-04 to 2027-03-03",
    amount_cents=9500,
    deductible=False,
)
GIFT = ReceiptLine(label="Contribution", detail="", amount_cents=5000, deductible=True)


def receipt(*lines: ReceiptLine) -> ReceiptData:
    """A receipt for Marta Reyes carrying ``lines``, everything else fixed."""
    return ReceiptData(
        org=ORG,
        receipt_number="CALDART-000123",
        issued_on=date(2026, 3, 4),
        payer_name="Marta Reyes",
        payer_email="marta@example.org",
        lines=lines,
        provider_label="Stripe",
        provider_ref="pi_3Nabc123",
    )


def render_receipt(data: ReceiptData) -> bytes:
    """The receipt PDF as bytes."""
    buffer = io.BytesIO()
    build_receipt_pdf(buffer, data)
    return buffer.getvalue()


def render_statement(data: StatementData) -> bytes:
    """The statement PDF as bytes."""
    buffer = io.BytesIO()
    build_statement_pdf(buffer, data)
    return buffer.getvalue()


def drawn(pdf: bytes, pdf_text: PdfText) -> str:
    """Everything the first page draws, as one string.

    reportlab draws a paragraph as one string per line, so a value that shares a
    line with its label is found in the whole page's text rather than on its own.
    """
    return " ".join(pdf_text(pdf)[0])


STATEMENT = StatementData(
    org=ORG,
    year=2026,
    member_name="Marta Reyes",
    member_email="marta@example.org",
    contributions=(
        StatementLine(paid_on=date(2026, 3, 4), receipt_number="CALDART-000123", amount_cents=5000),
        StatementLine(
            paid_on=date(2026, 7, 19),
            receipt_number="CALDART-000456",
            amount_cents=25000,
            refunded_cents=10000,
        ),
    ),
)


def test_the_receipt_is_one_upright_letter_page() -> None:
    """A receipt is a single portrait US-letter page."""
    body = render_receipt(receipt(DUES, GIFT))

    assert pdf_page_count(body) == 1
    assert b"/MediaBox [ 0 0 612 792 ]" in body


def test_the_receipt_prints_its_number(pdf_text: PdfText) -> None:
    """The receipt number is on the page, so a treasurer can be asked about it."""
    assert "CALDART-000123" in drawn(render_receipt(receipt(DUES, GIFT)), pdf_text)


def test_the_receipt_names_the_payer(pdf_text: PdfText) -> None:
    """The name and the address the payment came from are both printed."""
    page = pdf_text(render_receipt(receipt(DUES, GIFT)))[0]

    assert "Marta Reyes" in page
    assert "marta@example.org" in page


def test_the_receipt_dates_itself(pdf_text: PdfText) -> None:
    """The day the money was received is printed as an ISO date."""
    assert "Received 2026-03-04" in drawn(render_receipt(receipt(DUES, GIFT)), pdf_text)


def test_the_receipt_prints_the_letterhead(pdf_text: PdfText) -> None:
    """The organization's name, mailing address and EIN head the page."""
    page = pdf_text(render_receipt(receipt(DUES, GIFT)))[0]

    assert page[0] == "The California DART Network"
    assert "PO Box 41" in page
    assert "Palo Alto, CA 94301" in page
    assert "EIN 94-1234567" in page


def test_the_receipt_lists_each_line_with_its_amount(pdf_text: PdfText) -> None:
    """Dues and contribution are separate lines, each in dollars."""
    page = drawn(render_receipt(receipt(DUES, GIFT)), pdf_text)

    assert "Annual membership (2026-03-04 to 2027-03-03)" in page
    assert "$95.00" in page
    assert "Contribution" in page
    assert "$50.00" in page


def test_the_receipt_totals_the_lines(pdf_text: PdfText) -> None:
    """The total is the sum of the lines, shown in dollars."""
    page = pdf_text(render_receipt(receipt(DUES, GIFT)))[0]

    assert "Total" in page
    assert "$145.00" in page


def test_a_receipt_with_a_contribution_carries_the_deduction_wording(
    pdf_text: PdfText,
) -> None:
    """A gift on the receipt brings the 501(c)(3) sentence with it."""
    page = pdf_text(render_receipt(receipt(DUES, GIFT)))[0]

    assert CONTRIBUTION_NOTICE in page


def test_a_dues_only_receipt_claims_no_deduction(pdf_text: PdfText) -> None:
    """Dues are dues: without a gift the page says nothing about a deduction."""
    page = pdf_text(render_receipt(receipt(DUES)))[0]

    assert CONTRIBUTION_NOTICE not in page


def test_the_receipt_names_the_provider_and_its_reference(pdf_text: PdfText) -> None:
    """How the money arrived, and the reference to look it up by."""
    page = drawn(render_receipt(receipt(DUES, GIFT)), pdf_text)

    assert "Paid with Stripe, reference pi_3Nabc123" in page


def test_the_receipt_total_adds_up_the_lines() -> None:
    """``total_cents`` is the sum of the line amounts, in cents."""
    assert receipt(DUES, GIFT).total_cents == 14500


def test_the_statement_is_one_upright_letter_page() -> None:
    """A year's statement is a single portrait US-letter page."""
    body = render_statement(STATEMENT)

    assert pdf_page_count(body) == 1
    assert b"/MediaBox [ 0 0 612 792 ]" in body


def test_the_statement_names_the_year(pdf_text: PdfText) -> None:
    """The heading says which calendar year the statement covers."""
    page = pdf_text(render_statement(STATEMENT))[0]

    assert "Contribution statement for 2026" in page


def test_the_statement_names_the_member(pdf_text: PdfText) -> None:
    """The member's name and address identify whose contributions these are."""
    page = pdf_text(render_statement(STATEMENT))[0]

    assert "Marta Reyes" in page
    assert "marta@example.org" in page


def test_the_statement_lists_every_contribution(pdf_text: PdfText) -> None:
    """One row per contribution, each with its date and its receipt number."""
    page = pdf_text(render_statement(STATEMENT))[0]

    assert "2026-03-04" in page
    assert "CALDART-000123" in page
    assert "2026-07-19" in page
    assert "CALDART-000456" in page


def test_the_statement_shows_what_was_refunded(pdf_text: PdfText) -> None:
    """A refunded contribution shows the refund and the net beside the amount."""
    page = pdf_text(render_statement(STATEMENT))[0]

    assert "$250.00" in page
    assert "$100.00" in page
    assert "$150.00" in page


def test_the_statement_totals_the_year_net_of_refunds(pdf_text: PdfText) -> None:
    """The year's total is what the member gave less what came back."""
    page = pdf_text(render_statement(STATEMENT))[0]

    assert "$200.00" in page


def test_the_statement_total_is_net_of_refunds() -> None:
    """``total_cents`` subtracts every refund from the contributions."""
    assert STATEMENT.total_cents == 20000


def test_a_statement_line_nets_its_refund() -> None:
    """One line's ``net_cents`` is its amount less its refund."""
    assert STATEMENT.contributions[1].net_cents == 15000


def test_the_statement_carries_the_deduction_wording(pdf_text: PdfText) -> None:
    """The statement is a 501(c)(3) acknowledgment and says so."""
    page = pdf_text(render_statement(STATEMENT))[0]

    assert CONTRIBUTIONS_NOTICE in page


def test_the_statement_prints_the_letterhead(pdf_text: PdfText) -> None:
    """The organization's name and EIN head the statement too."""
    page = pdf_text(render_statement(STATEMENT))[0]

    assert page[0] == "The California DART Network"
    assert "EIN 94-1234567" in page


@pytest.mark.parametrize(
    ("blank", "gone"),
    [
        ("mailing_address", "Palo Alto, CA 94301"),
        ("ein", "EIN 94-1234567"),
        ("contact_email", "info@caldart.example.org"),
    ],
    ids=["no-address", "no-ein", "no-contact"],
)
def test_the_letterhead_leaves_out_what_nobody_has_filled_in(
    blank: str, gone: str, pdf_text: PdfText
) -> None:
    """A letterhead field nobody has entered draws no line at all."""
    data = replace(receipt(DUES), org=replace(ORG, **{blank: ""}))

    page = pdf_text(render_receipt(data))[0]

    assert gone not in page
    assert page[0] == "The California DART Network"


def test_a_statement_year_with_nothing_in_it_still_renders(pdf_text: PdfText) -> None:
    """A member with no contributions that year gets a page totaling zero."""
    empty = replace(STATEMENT, contributions=())

    page = pdf_text(render_statement(empty))[0]

    assert "$0.00" in page
