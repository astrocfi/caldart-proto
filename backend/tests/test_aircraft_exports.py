"""Aircraft register exports: CSV content, PDF, filters, roles."""

from __future__ import annotations

from datetime import date

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.aircraft.models import Aircraft
from apps.aircraft.reports import AIRCRAFT_REPORT, AIRCRAFT_REPORT_COLUMNS, EXPORT_FILTER_PARAMS
from caldart.reports import ReportFormat, cell_text
from tests.conftest import PdfText, RegisterDict, pdf_page_count, read_csv
from tests.factories import AircraftFactory, MemberProfileFactory, UserFactory

pytestmark = pytest.mark.django_db

CSV_URL = "/api/v1/reports/aircraft/export.csv"
PDF_URL = "/api/v1/reports/aircraft/export.pdf"

#: The header the CSV prints when the caller chooses no columns: the labels of
#: the nine default columns.
EXPECTED_HEADER = [
    "N-number",
    "Make",
    "Model",
    "Owner",
    "Carrier",
    "Liability / occurrence",
    "Hull",
    "Expires",
    "Current",
]

#: Every column, by key, so a test can read a cell by its position below.
ALL_COLUMNS = {"columns": ",".join(column.key for column in AIRCRAFT_REPORT_COLUMNS)}

#: Index of the first data row on a rendered page: the title, the subtitle and
#: the nine default column headings come first, each on one line.
PDF_FIRST_ROW = 11

#: The footer draws two more strings after the last row of the page.
PDF_FOOTER = -2


# --------------------------------------------------------------------------
# CSV
# --------------------------------------------------------------------------
def test_csv_headers_and_filename(
    api_client: APIClient, account_admin: User, register: RegisterDict, today: date
) -> None:
    """The CSV export sets a ``text/csv`` type and a dated attachment filename."""
    api_client.force_login(account_admin)
    response = api_client.get(CSV_URL)
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    assert response["Content-Disposition"] == (
        f'attachment; filename="caldart-aircraft-{today.isoformat()}.csv"'
    )


def test_csv_columns_are_in_the_documented_order(
    api_client: APIClient, account_admin: User, register: RegisterDict
) -> None:
    """The CSV header row matches the documented column order exactly."""
    api_client.force_login(account_admin)
    rows = read_csv(api_client.get(CSV_URL))
    assert rows[0] == EXPECTED_HEADER


def test_csv_content(api_client: APIClient, account_admin: User, register: RegisterDict) -> None:
    """Each row's fields, including formatted money and insurance status, are correct."""
    api_client.force_login(account_admin)
    rows = read_csv(api_client.get(CSV_URL, ALL_COLUMNS))
    by_number = {row[0]: row for row in rows[1:]}

    current = by_number["N172SP"]
    assert current[1:6] == [
        "Cessna",
        "172S Skyhawk",
        "Palo Alto Flying Club",
        "Flying club",
        "Avemco",
    ]
    assert current[6:9] == ["1000000.00", "100000.00", "145000.00"]
    expiration = register["current"].insurance_expiration
    assert expiration is not None
    assert current[9] == expiration.isoformat()
    assert current[10] == "yes"

    assert by_number["N33MM"][10] == "no"
    missing = by_number["N44BE"]
    assert missing[8] == ""
    assert missing[9] == ""
    assert missing[10] == "no"


def test_csv_pilots_column_lists_attached_members(
    api_client: APIClient, account_admin: User, register: RegisterDict
) -> None:
    """The pilots column lists every profile attached to the aircraft, joined by "; "."""
    marta = UserFactory(email="marta@example.test", first_name="Marta", last_name="Reyes")
    owen = UserFactory(email="owen@example.test", first_name="Owen", last_name="Delgado")
    MemberProfileFactory(user=marta).aircraft.add(register["current"])
    MemberProfileFactory(user=owen).aircraft.add(register["current"])

    api_client.force_login(account_admin)
    rows = read_csv(api_client.get(CSV_URL, ALL_COLUMNS))
    pilots = {row[0]: row[11] for row in rows[1:]}
    assert set(pilots["N172SP"].split("; ")) == {"Marta Reyes", "Owen Delgado"}
    assert pilots["N33MM"] == ""


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ({"insurance": "expired"}, ["N33MM"]),
        ({"search": "cessna"}, ["N172SP"]),
        ({"owner_type": "fbo"}, ["N44BE"]),
    ],
    ids=["insurance", "search", "owner_type"],
)
def test_csv_honors_the_same_filters_as_the_list(
    api_client: APIClient,
    account_admin: User,
    register: RegisterDict,
    query: dict[str, str],
    expected: list[str],
) -> None:
    """The CSV export applies the ``insurance``, ``search`` and ``owner_type`` filters."""
    api_client.force_login(account_admin)
    rows = read_csv(api_client.get(CSV_URL, query))
    assert [row[0] for row in rows[1:]] == expected


def test_csv_honors_ordering(
    api_client: APIClient, account_admin: User, register: RegisterDict
) -> None:
    """The CSV export honors the ``ordering`` parameter, descending N-number here."""
    api_client.force_login(account_admin)
    rows = read_csv(api_client.get(CSV_URL, {"ordering": "-n_number"}))
    assert [row[0] for row in rows[1:]] == ["N9021K", "N44BE", "N33MM", "N172SP"]


def test_csv_is_not_paginated(api_client: APIClient, account_admin: User) -> None:
    """The CSV export returns every matching row, not one page of the list view."""
    for index in range(30):
        AircraftFactory(n_number=f"N{2000 + index}EX")
    api_client.force_login(account_admin)
    rows = read_csv(api_client.get(CSV_URL))
    assert len(rows) == 31


# --------------------------------------------------------------------------
# PDF
# --------------------------------------------------------------------------
def test_pdf_is_a_valid_document(
    api_client: APIClient, account_admin: User, register: RegisterDict, today: date
) -> None:
    """The PDF export is a one-page, well-formed PDF with a dated attachment filename."""
    api_client.force_login(account_admin)
    response = api_client.get(PDF_URL)
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response["Content-Disposition"] == (
        f'attachment; filename="caldart-aircraft-{today.isoformat()}.pdf"'
    )
    body = response.content
    assert body.startswith(b"%PDF-")
    assert body.rstrip().endswith(b"%%EOF")
    assert pdf_page_count(body) == 1


def test_pdf_is_filtered_like_the_list(
    api_client: APIClient, account_admin: User, register: RegisterDict, pdf_text: PdfText
) -> None:
    """A filtered PDF draws exactly the rows the same filter leaves in the list."""
    api_client.force_login(account_admin)
    page = pdf_text(api_client.get(PDF_URL, {"insurance": "expired"}).content)[0]
    expires_on = register["expired"].insurance_expiration
    assert expires_on is not None
    assert page[PDF_FIRST_ROW:PDF_FOOTER] == [
        "N33MM",
        "Mooney",
        "M20J",
        "Owen Delgado",
        "Avemco",
        "$1,000,000",
        "$200,000",
        expires_on.isoformat(),
        "no",
    ]


def test_pdf_paginates_a_large_register(api_client: APIClient, account_admin: User) -> None:
    """A register too large for one page produces a multi-page PDF."""
    for index in range(120):
        AircraftFactory(n_number=f"N{3000 + index}PD")
    api_client.force_login(account_admin)
    body = api_client.get(PDF_URL).content
    assert pdf_page_count(body) > 1


def test_pdf_survives_an_empty_result_set(
    api_client: APIClient, account_admin: User, register: RegisterDict, pdf_text: PdfText
) -> None:
    """A filter that matches nothing returns a PDF with a header and no rows."""
    api_client.force_login(account_admin)
    response = api_client.get(PDF_URL, {"search": "no-such-aircraft"})
    assert response.status_code == 200
    page = pdf_text(response.content)[0]
    assert page[:2] == ["CalDART aircraft register", "search: no-such-aircraft"]
    assert page[PDF_FIRST_ROW:PDF_FOOTER] == []


def test_pdf_states_the_filters_it_was_run_with(
    api_client: APIClient, account_admin: User, register: RegisterDict, pdf_text: PdfText
) -> None:
    """The subtitle under the title names the filter the export was run with."""
    api_client.force_login(account_admin)
    page = pdf_text(api_client.get(PDF_URL, {"insurance": "expired"}).content)[0]
    assert page[1] == "insurance: expired"


def test_pdf_says_when_it_was_run_with_no_filters(
    api_client: APIClient, account_admin: User, register: RegisterDict, pdf_text: PdfText
) -> None:
    """An unfiltered export says so in the same subtitle line."""
    api_client.force_login(account_admin)
    page = pdf_text(api_client.get(PDF_URL).content)[0]
    assert page[1] == "No filters applied"


def money_cells(aircraft: Aircraft, fmt: ReportFormat) -> list[str]:
    """The three insured amounts of ``aircraft``, as format ``fmt`` prints them."""
    keys = {"liability_per_occurrence", "liability_per_person", "hull"}
    return [
        cell_text(column.value(aircraft), fmt)
        for column in AIRCRAFT_REPORT_COLUMNS
        if column.key in keys
    ]


def test_money_is_formatted_for_a_reader_in_the_pdf_rows(register: RegisterDict) -> None:
    """The insured amounts are dollar amounts when the export renders for a reader."""
    assert money_cells(register["current"], "pdf") == [
        "$1,000,000",
        "$100,000",
        "$145,000",
    ]


def test_money_is_a_plain_number_a_spreadsheet_sums_in_the_csv(register: RegisterDict) -> None:
    """The same amounts are plain two-place numbers when the export is a CSV."""
    assert money_cells(register["current"], "csv") == [
        "1000000.00",
        "100000.00",
        "145000.00",
    ]


def test_odd_cent_amounts_keep_their_cents(register: RegisterDict) -> None:
    """A reader's money format keeps non-round cent amounts precise."""
    register["current"].insurance_hull_cents = 12_345
    assert money_cells(register["current"], "pdf")[2] == "$123.45"


def test_the_export_subtitle_covers_every_filter_the_list_applies() -> None:
    """The subtitle can name every filter the register list supports, and ordering."""
    assert EXPORT_FILTER_PARAMS == (
        "search",
        "make",
        "owner_type",
        "insurance",
        "expiring_within",
        "is_active",
        "ordering",
    )


def test_the_export_subtitle_names_the_filters_given_a_value(register: RegisterDict) -> None:
    """A filter supplied with a value is named; a blank one is not."""
    filters = AIRCRAFT_REPORT.query({"is_active": "true", "search": "N1", "make": ""}).filters
    assert filters == {"search": "N1", "is_active": "true"}
