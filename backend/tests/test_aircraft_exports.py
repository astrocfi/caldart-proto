"""Aircraft register exports: CSV content, PDF, filters, roles."""

from __future__ import annotations

import pytest
from rest_framework.request import Request
from rest_framework.test import APIClient, APIRequestFactory

from apps.accounts.models import User
from apps.accounts.roles import ACCOUNT_ADMIN, SYSTEM_ADMIN
from apps.aircraft.api.views import AircraftExportPdfView
from apps.aircraft.reports import aircraft_row
from tests.conftest import PdfText, RegisterDict, pdf_page_count, read_csv, role_matrix
from tests.factories import AircraftFactory, MemberProfileFactory, UserFactory

pytestmark = pytest.mark.django_db

CSV_URL = "/api/v1/admin/aircraft/export.csv"
PDF_URL = "/api/v1/admin/aircraft/export.pdf"

EXPECTED_HEADER = [
    "n_number",
    "make",
    "model",
    "owner",
    "owner_type",
    "insurance_carrier",
    "liability_per_occurrence",
    "liability_per_person",
    "hull",
    "insurance_expiration",
    "insurance_current",
    "pilots",
]

#: Index of the first data row on a rendered page: the title, the subtitle and
#: the twelve column headings come first, two of which wrap onto a second line.
PDF_FIRST_ROW = 16

#: The footer draws two more strings after the last row of the page.
PDF_FOOTER = -2


# --------------------------------------------------------------------------
# Permissions
# --------------------------------------------------------------------------
@pytest.mark.parametrize("url", [CSV_URL, PDF_URL])
def test_exports_require_authentication(api_client: APIClient, url: str) -> None:
    """Both export endpoints refuse an anonymous caller with a 401."""
    assert api_client.get(url).status_code == 401


@pytest.mark.parametrize("url", [CSV_URL, PDF_URL])
@pytest.mark.parametrize(("slug", "allowed"), role_matrix(ACCOUNT_ADMIN, SYSTEM_ADMIN))
def test_export_role_matrix(
    api_client: APIClient,
    all_role_users: dict[str, User],
    register: RegisterDict,
    url: str,
    slug: str,
    allowed: bool,
) -> None:
    """Only account and system admins get 200 from either export; others get 403."""
    api_client.force_login(all_role_users[slug])
    assert api_client.get(url).status_code == (200 if allowed else 403)


# --------------------------------------------------------------------------
# CSV
# --------------------------------------------------------------------------
def test_csv_headers_and_filename(
    api_client: APIClient, account_admin: User, register: RegisterDict
) -> None:
    """The CSV export sets a ``text/csv`` type and an attachment filename."""
    api_client.force_login(account_admin)
    response = api_client.get(CSV_URL)
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    assert "attachment; filename=" in response["Content-Disposition"]
    assert "caldart-aircraft-" in response["Content-Disposition"]


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
    rows = read_csv(api_client.get(CSV_URL))
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
    rows = read_csv(api_client.get(CSV_URL))
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
    api_client: APIClient, account_admin: User, register: RegisterDict
) -> None:
    """The PDF export is a one-page, well-formed PDF with the standard filename prefix."""
    api_client.force_login(account_admin)
    response = api_client.get(PDF_URL)
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert "caldart-aircraft-" in response["Content-Disposition"]
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
        "Individual",
        "Avemco",
        "$1,000,000",
        "$100,000",
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


def test_money_is_formatted_for_people_in_the_pdf_rows(register: RegisterDict) -> None:
    """``aircraft_row`` formats cents as dollar amounts only when ``currency`` is set."""
    row = aircraft_row(register["current"], currency=True)
    assert row[6:9] == ["$1,000,000", "$100,000", "$145,000"]
    plain = aircraft_row(register["current"])
    assert plain[6:9] == ["1000000.00", "100000.00", "145000.00"]


def test_odd_cent_amounts_keep_their_cents(register: RegisterDict) -> None:
    """``aircraft_row``'s currency format keeps non-round cent amounts precise."""
    register["current"].insurance_hull_cents = 12_345
    assert aircraft_row(register["current"], currency=True)[8] == "$123.45"


def test_the_export_subtitle_covers_every_filter_the_list_applies() -> None:
    """``applied_filters`` reports every filter the register list supports."""
    view = AircraftExportPdfView()
    view.request = Request(APIRequestFactory().get("/", {"is_active": "true", "search": "N1"}))

    filters = view.applied_filters()

    assert filters["is_active"] == "true"
    assert filters["search"] == "N1"
    assert set(filters) == {
        "search",
        "make",
        "owner_type",
        "insurance",
        "expiring_within",
        "is_active",
        "ordering",
    }
