"""The column registries behind the member and aircraft reports.

Two things are proved here.  The registries and their ``columns`` endpoints
agree, and ``?columns=`` picks the cells of both exports; and the default
columns are sized so that no cell of a seeded row has to wrap in the PDF, which
is what the relative widths on the registries are for.
"""

from __future__ import annotations

from collections.abc import Sequence
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase.pdfmetrics import stringWidth
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import ACCOUNT_ADMIN, SYSTEM_ADMIN
from apps.aircraft.reports import AIRCRAFT_REPORT_COLUMNS, aircraft_rows, export_queryset
from apps.members.filters import member_admin_queryset
from apps.members.reports import MEMBER_REPORT_COLUMNS, member_report_rows
from caldart.reports import (
    CELL_PADDING,
    CELL_STYLE,
    HEADER_CELL_STYLE,
    MARGIN,
    ReportColumn,
    select_columns,
)
from tests.conftest import PdfText, RegisterDict, read_csv, role_matrix
from tests.factories import MemberProfileFactory, UserFactory

pytestmark = pytest.mark.django_db

MEMBER_COLUMNS_URL = "/api/v1/admin/members/columns"
AIRCRAFT_COLUMNS_URL = "/api/v1/admin/aircraft/columns"
MEMBER_CSV_URL = "/api/v1/admin/members/export.csv"
MEMBER_PDF_URL = "/api/v1/admin/members/export.pdf"
AIRCRAFT_CSV_URL = "/api/v1/admin/aircraft/export.csv"
AIRCRAFT_PDF_URL = "/api/v1/admin/aircraft/export.pdf"

#: The printable width of a landscape US-letter page, which the relative widths
#: of the chosen columns share out between them.
PRINTABLE_WIDTH = landscape(letter)[0] - 2 * MARGIN

#: The member columns that are in the report when the caller chooses none.
MEMBER_DEFAULTS = (
    "name",
    "email",
    "phone",
    "dart",
    "status",
    "expires_on",
    "certificate",
    "medical_type",
    "medical_expiration",
    "aircraft",
)

#: The aircraft columns that are in the register when the caller chooses none.
AIRCRAFT_DEFAULTS = (
    "n_number",
    "make",
    "model",
    "owner_name",
    "insurance_carrier",
    "liability_per_occurrence",
    "hull",
    "insurance_expiration",
    "insurance_current",
)


@pytest.fixture
def seeded(db: None) -> None:
    """The whole demo data set, which is what the default widths are sized for."""
    call_command("seed_demo", stdout=StringIO())


def fits(text: str, width: float, total: float, *, style: ParagraphStyle = CELL_STYLE) -> bool:
    """True when ``text`` is drawn on one line in a column of that relative width.

    ``width`` is the column's share and ``total`` the shares of every column in
    the same export, which together decide how many points of the printable
    width the column gets; the padding on both sides of the cell is width the
    text cannot use.  ``style`` is the paragraph style the cell is drawn in,
    the body style for a data cell and ``HEADER_CELL_STYLE`` for a heading.
    """
    room = width / total * PRINTABLE_WIDTH - 2 * CELL_PADDING
    return stringWidth(text, style.fontName, style.fontSize) <= room


def wrapped_headers[T](columns: Sequence[ReportColumn[T]]) -> list[str]:
    """The labels among ``columns`` that do not fit their column on one line."""
    total = sum(column.width for column in columns)
    return [
        column.label
        for column in columns
        if not fits(column.label, column.width, total, style=HEADER_CELL_STYLE)
    ]


# --------------------------------------------------------------------------
# The registries
# --------------------------------------------------------------------------
def test_the_member_defaults_are_the_ten_columns_of_the_everyday_report() -> None:
    """With no choice made, the membership report carries its ten default columns."""
    chosen = select_columns(MEMBER_REPORT_COLUMNS, None)
    assert tuple(column.key for column in chosen) == MEMBER_DEFAULTS


def test_the_aircraft_defaults_are_the_nine_columns_of_the_everyday_register() -> None:
    """With no choice made, the register carries its nine default columns."""
    chosen = select_columns(AIRCRAFT_REPORT_COLUMNS, None)
    assert tuple(column.key for column in chosen) == AIRCRAFT_DEFAULTS


def test_every_member_column_is_labeled_for_a_reader() -> None:
    """No member column falls back to its key: every label is written for a person."""
    assert [column.label for column in MEMBER_REPORT_COLUMNS if "_" in column.label] == []


def test_every_aircraft_column_is_labeled_for_a_reader() -> None:
    """No aircraft column falls back to its key: every label is written for a person."""
    assert [column.label for column in AIRCRAFT_REPORT_COLUMNS if "_" in column.label] == []


# --------------------------------------------------------------------------
# No default cell wraps
# --------------------------------------------------------------------------
@pytest.mark.slow
def test_no_default_member_cell_wraps_in_the_pdf(seeded: None) -> None:
    """Every default cell of every seeded member fits its column on one line."""
    columns = select_columns(MEMBER_REPORT_COLUMNS, None)
    assert wrapped_headers(columns) == []
    total = sum(column.width for column in columns)
    rows = member_report_rows(member_admin_queryset(), columns)
    too_wide = [
        (column.key, cell)
        for row in rows
        for column, cell in zip(columns, row, strict=True)
        if not fits(cell, column.width, total)
    ]
    assert too_wide == []


@pytest.mark.slow
def test_no_default_aircraft_cell_wraps_in_the_pdf(seeded: None) -> None:
    """Every default cell of every seeded aircraft fits its column on one line."""
    columns = select_columns(AIRCRAFT_REPORT_COLUMNS, None)
    assert wrapped_headers(columns) == []
    total = sum(column.width for column in columns)
    rows = aircraft_rows(export_queryset(), columns, currency=True)
    too_wide = [
        (column.key, cell)
        for row in rows
        for column, cell in zip(columns, row, strict=True)
        if not fits(cell, column.width, total)
    ]
    assert too_wide == []


# --------------------------------------------------------------------------
# The columns endpoints
# --------------------------------------------------------------------------
@pytest.mark.parametrize("url", [MEMBER_COLUMNS_URL, AIRCRAFT_COLUMNS_URL])
def test_columns_refuse_an_anonymous_caller(api_client: APIClient, url: str) -> None:
    """Both columns endpoints answer an anonymous caller with a 401."""
    assert api_client.get(url).status_code == 401


@pytest.mark.parametrize("url", [MEMBER_COLUMNS_URL, AIRCRAFT_COLUMNS_URL])
@pytest.mark.parametrize(("slug", "allowed"), role_matrix(ACCOUNT_ADMIN, SYSTEM_ADMIN))
def test_columns_role_matrix(
    api_client: APIClient, all_role_users: dict[str, User], url: str, slug: str, allowed: bool
) -> None:
    """Only an account or system administrator reads either columns endpoint."""
    api_client.force_login(all_role_users[slug])
    assert api_client.get(url).status_code == (200 if allowed else 403)


def test_member_columns_answer_the_registry(account_admin_client: APIClient) -> None:
    """The member columns endpoint reports every column, in export order."""
    payload = account_admin_client.get(MEMBER_COLUMNS_URL).json()
    assert payload == [
        {"key": column.key, "label": column.label, "default": column.default}
        for column in MEMBER_REPORT_COLUMNS
    ]


def test_aircraft_columns_answer_the_registry(account_admin_client: APIClient) -> None:
    """The aircraft columns endpoint reports every column, in export order."""
    payload = account_admin_client.get(AIRCRAFT_COLUMNS_URL).json()
    assert payload == [
        {"key": column.key, "label": column.label, "default": column.default}
        for column in AIRCRAFT_REPORT_COLUMNS
    ]


# --------------------------------------------------------------------------
# ?columns= on the four exports
# --------------------------------------------------------------------------
def test_the_member_csv_header_is_the_default_labels(account_admin_client: APIClient) -> None:
    """With no choice made, the member CSV heads its columns with the default labels."""
    table = read_csv(account_admin_client.get(MEMBER_CSV_URL))
    assert table[0] == [column.label for column in select_columns(MEMBER_REPORT_COLUMNS, None)]


def test_the_member_csv_follows_the_requested_columns(account_admin_client: APIClient) -> None:
    """``?columns=`` picks the member CSV's columns and their order."""
    table = read_csv(account_admin_client.get(MEMBER_CSV_URL, {"columns": "state,name"}))
    assert table[0] == ["State", "Name"]


def test_the_aircraft_csv_header_is_the_default_labels(
    account_admin_client: APIClient, register: RegisterDict
) -> None:
    """With no choice made, the register CSV heads its columns with the default labels."""
    table = read_csv(account_admin_client.get(AIRCRAFT_CSV_URL))
    assert table[0] == [column.label for column in select_columns(AIRCRAFT_REPORT_COLUMNS, None)]


def test_the_aircraft_csv_follows_the_requested_columns(
    account_admin_client: APIClient, register: RegisterDict
) -> None:
    """``?columns=`` picks the register CSV's columns and their order."""
    table = read_csv(account_admin_client.get(AIRCRAFT_CSV_URL, {"columns": "pilots,n_number"}))
    assert table[0] == ["Pilots", "N-number"]


#: Every export, with a column list naming one key it carries and one it does
#: not, so the same refusal is proved on all four.
UNKNOWN_CASES = [
    (MEMBER_CSV_URL, "name,bogus"),
    (MEMBER_PDF_URL, "name,bogus"),
    (AIRCRAFT_CSV_URL, "n_number,bogus"),
    (AIRCRAFT_PDF_URL, "n_number,bogus"),
]

#: The same four exports, each asked for one of its own columns twice.
REPEATED_CASES = [
    (MEMBER_CSV_URL, "name,name", "name"),
    (MEMBER_PDF_URL, "name,name", "name"),
    (AIRCRAFT_CSV_URL, "n_number,n_number", "n_number"),
    (AIRCRAFT_PDF_URL, "n_number,n_number", "n_number"),
]


@pytest.mark.parametrize(("url", "columns"), UNKNOWN_CASES)
def test_an_unknown_column_is_a_400_keyed_columns(
    account_admin_client: APIClient, url: str, columns: str
) -> None:
    """A column no export carries is refused with a 400 rather than exported."""
    assert account_admin_client.get(url, {"columns": columns}).status_code == 400


@pytest.mark.parametrize(("url", "columns"), UNKNOWN_CASES)
def test_an_unknown_column_names_the_key_at_fault(
    account_admin_client: APIClient, url: str, columns: str
) -> None:
    """The refusal names the first unknown key, under the ``columns`` parameter."""
    response = account_admin_client.get(url, {"columns": columns})
    assert response.json()["columns"] == ["Unknown column: bogus"]


@pytest.mark.parametrize(("url", "columns", "key"), REPEATED_CASES)
def test_a_repeated_column_is_refused(
    account_admin_client: APIClient, url: str, columns: str, key: str
) -> None:
    """A column asked for twice is refused rather than exported twice."""
    response = account_admin_client.get(url, {"columns": columns})
    assert response.json()["columns"] == [f"Repeated column: {key}"]


def test_the_member_pdf_prints_the_chosen_columns(
    account_admin_client: APIClient, pdf_text: PdfText
) -> None:
    """The member PDF's header row is the labels of the columns asked for."""
    body = account_admin_client.get(MEMBER_PDF_URL, {"columns": "name,city"}).content
    assert pdf_text(body)[0][2:4] == ["Name", "City"]


def test_the_aircraft_pdf_prints_the_chosen_columns(
    account_admin_client: APIClient, register: RegisterDict, pdf_text: PdfText
) -> None:
    """The register PDF's header row is the labels of the columns asked for."""
    body = account_admin_client.get(AIRCRAFT_PDF_URL, {"columns": "n_number,hull"}).content
    assert pdf_text(body)[0][2:4] == ["N-number", "Hull"]


# --------------------------------------------------------------------------
# The profile_updated column
# --------------------------------------------------------------------------
def test_profile_updated_is_documented_and_off_by_default() -> None:
    """The ``profile_updated`` column is registered, off by default, for a reader."""
    column = next(c for c in MEMBER_REPORT_COLUMNS if c.key == "profile_updated")
    assert column.label == "Profile updated"
    assert column.default is False


def test_the_member_csv_reports_the_profile_updated_date(account_admin_client: APIClient) -> None:
    """``?columns=profile_updated`` prints the local date the profile was last written."""
    stamped = UserFactory(email="stamped@example.test", roles=["member"])
    stamped_profile = MemberProfileFactory(user=stamped)
    stamp = timezone.now().replace(microsecond=0)
    stamped_profile.profile_updated_at = stamp
    stamped_profile.save(update_fields=["profile_updated_at"])

    table = read_csv(account_admin_client.get(MEMBER_CSV_URL, {"columns": "email,profile_updated"}))
    row = next(cells for cells in table[1:] if cells[0] == "stamped@example.test")
    assert row[1] == timezone.localdate(stamp).isoformat()


def test_the_member_csv_blanks_a_never_edited_profile(account_admin_client: APIClient) -> None:
    """A profile nobody has edited exports a blank ``profile_updated`` cell."""
    never_edited = UserFactory(email="untouched@example.test", roles=["member"])
    MemberProfileFactory(user=never_edited)

    table = read_csv(account_admin_client.get(MEMBER_CSV_URL, {"columns": "email,profile_updated"}))
    row = next(cells for cells in table[1:] if cells[0] == "untouched@example.test")
    assert row[1] == ""
