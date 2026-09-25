"""The membership report exports.

CSV and PDF share one column list and one filtered queryset, so most of these
assertions are about the CSV -- it is the readable one -- with the PDF checked
for validity, page geometry and the filter summary it prints as a subtitle.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

import pytest
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

from apps.accounts.models import User
from apps.darts.models import Dart
from apps.members.api.admin_filters import applied_filters
from apps.members.api.admin_views import MemberExportPdfView
from apps.members.models import (
    MedicalType,
    MembershipPlan,
    MembershipStatusChoices,
    PilotCertificateType,
)
from apps.members.reports import MEMBER_REPORT_COLUMNS, member_report_filename
from caldart.reports import filter_summary
from tests.conftest import pdf_page_count, read_csv
from tests.factories import (
    AircraftFactory,
    DartFactory,
    MemberProfileFactory,
    MembershipFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db

CSV_URL = "/api/v1/admin/members/export.csv"
PDF_URL = "/api/v1/admin/members/export.pdf"

#: The column keys ``docs/developer/reports.rst`` documents, in export order.
DOCUMENTED_COLUMNS = (
    "name",
    "email",
    "phone",
    "dart",
    "status",
    "plan",
    "expires_on",
    "certificate",
    "certificate_number",
    "ifr",
    "medical_type",
    "medical_expiration",
    "aircraft",
    "city",
    "state",
    "joined_on",
    "member_since",
    "profile_updated",
)

#: The header the CSV prints when the caller chooses no columns: the labels of
#: the ten default columns, which is what ``docs/developer/reports.rst`` shows.
DEFAULT_HEADER = [
    "Name",
    "Email",
    "Phone",
    "DART",
    "Status",
    "Expires",
    "Certificate",
    "Medical",
    "Medical expires",
    "Aircraft",
]

#: Every column, chosen by key, so a row can be read by key below.
ALL_COLUMNS = {"columns": ",".join(DOCUMENTED_COLUMNS)}


@pytest.fixture
def reportable(
    annual_plan: MembershipPlan, life_plan: MembershipPlan, today: date, dart: Dart
) -> dict[str, User]:
    """Three members whose report rows exercise every kind of cell."""
    day = timedelta(days=1)
    napa = DartFactory(name="Napa", airport_identifiers="APC")

    pilot = UserFactory(email="pilot@example.test", first_name="Ada", last_name="Marsh")
    MemberProfileFactory(
        user=pilot,
        dart=dart,
        phone="415-555-0100",
        city="Palo Alto",
        state="CA",
        pilot_certificate_type=PilotCertificateType.COMMERCIAL,
        certificate_number="7654321",
        medical_type=MedicalType.SECOND,
        medical_expiration=today + 90 * day,
    )
    pilot.profile.aircraft.add(
        AircraftFactory(n_number="N172SP"), AircraftFactory(n_number="N9021K")
    )
    MembershipFactory(user=pilot, plan=annual_plan, starts_on=today - 30 * day)

    lifer = UserFactory(email="lifer@example.test", first_name="Bo", last_name="Nakano")
    MemberProfileFactory(user=lifer, dart=napa, phone="707-555-0111", city="Napa")
    MembershipFactory(user=lifer, plan=life_plan, starts_on=today - 400 * day, ends_on=None)

    lapsed = UserFactory(email="lapsed@example.test", first_name="Cy", last_name="Orr")
    MemberProfileFactory(
        user=lapsed,
        dart=napa,
        phone="",
        city="Napa",
        pilot_certificate_type=PilotCertificateType.NONE,
        medical_type=MedicalType.NONE,
        medical_expiration=None,
    )
    MembershipFactory(
        user=lapsed,
        plan=annual_plan,
        starts_on=today - 500 * day,
        ends_on=today - 135 * day,
        status=MembershipStatusChoices.EXPIRED,
    )
    return {"pilot": pilot, "lifer": lifer, "lapsed": lapsed}


def row_for(table: list[list[str]], email: str) -> dict[str, str]:
    """The row for ``email`` from an export of every column, keyed by column key.

    ``table`` must come from a request carrying :data:`ALL_COLUMNS`, so the cells
    line up with the documented keys whatever the labels say.
    """
    for row in table[1:]:
        keyed = dict(zip(DOCUMENTED_COLUMNS, row, strict=True))
        if keyed["email"] == email:
            return keyed
    raise AssertionError(f"{email} is not in the export")


# --------------------------------------------------------------------------
# CSV
# --------------------------------------------------------------------------
def test_csv_columns_are_in_the_documented_order() -> None:
    """The report's columns are the documented ones, in the documented order."""
    assert tuple(column.key for column in MEMBER_REPORT_COLUMNS) == DOCUMENTED_COLUMNS


def test_csv_download_headers(
    account_admin_client: APIClient, reportable: dict[str, User], today: date
) -> None:
    """The CSV download carries a CSV content type and a dated filename."""
    response = account_admin_client.get(CSV_URL)
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    assert response["Content-Disposition"] == (
        f'attachment; filename="caldart-members-{today.isoformat()}.csv"'
    )
    assert member_report_filename("csv") == f"caldart-members-{today.isoformat()}.csv"


def test_csv_row_content(
    account_admin_client: APIClient,
    reportable: dict[str, User],
    today: date,
    annual_plan: MembershipPlan,
) -> None:
    """A pilot's row carries every documented column, correctly formatted."""
    table = read_csv(account_admin_client.get(CSV_URL, ALL_COLUMNS))
    row = row_for(table, "pilot@example.test")
    assert row["name"] == "Ada Marsh"
    assert row["phone"] == "415-555-0100"
    assert row["dart"] == "Palo Alto"
    assert row["status"] == "current"
    assert row["plan"] == annual_plan.name
    assert row["expires_on"] == (today + timedelta(days=334)).isoformat()
    assert row["certificate"] == "Commercial"
    assert row["certificate_number"] == "7654321"
    assert row["ifr"] == "Yes"
    assert row["medical_type"] == "Second class"
    assert row["medical_expiration"] == (today + timedelta(days=90)).isoformat()
    assert set(row["aircraft"].split()) == {"N172SP", "N9021K"}
    assert row["city"] == "Palo Alto"
    assert row["state"] == "CA"
    assert row["joined_on"] == (today - timedelta(days=30)).isoformat()
    assert row["member_since"] == ""


def test_csv_leaves_a_lifetime_expiry_blank(
    account_admin_client: APIClient, reportable: dict[str, User], life_plan: MembershipPlan
) -> None:
    """A lifetime member's row leaves the expiry column blank."""
    row = row_for(read_csv(account_admin_client.get(CSV_URL, ALL_COLUMNS)), "lifer@example.test")
    assert row["status"] == "current"
    assert row["plan"] == life_plan.name
    assert row["expires_on"] == ""


def test_csv_blanks_a_missing_certificate_and_medical(
    account_admin_client: APIClient, reportable: dict[str, User]
) -> None:
    """A member with no certificate, medical or aircraft on file gets blank cells."""
    table = read_csv(account_admin_client.get(CSV_URL, ALL_COLUMNS))
    row = row_for(table, "lapsed@example.test")
    assert row["status"] == "expired"
    assert row["certificate"] == ""
    assert row["medical_type"] == ""
    assert row["medical_expiration"] == ""
    assert row["aircraft"] == ""


@pytest.fixture
def fixed_name_reportable(reportable: dict[str, User], fixed_name_admin: User) -> dict[str, User]:
    """``reportable`` with the signed-in admin given a fixed name too.

    See ``fixed_name_admin`` in ``conftest.py``: the report lists every account,
    admins included, so a Faker-drawn last name that happens to contain a search
    term used below would add an unwanted row.
    """
    return reportable


def test_csv_honors_the_list_filters(
    account_admin_client: APIClient, fixed_name_reportable: dict[str, User]
) -> None:
    """The CSV export applies the same status, dart and search filters as the list."""
    table = read_csv(account_admin_client.get(CSV_URL, {"status": "expired"}))
    assert len(table) == 2
    assert table[1][1] == "lapsed@example.test"

    table = read_csv(account_admin_client.get(CSV_URL, {"dart": "Napa"}))
    exported = {row[1] for row in table[1:]}
    assert exported == {"lifer@example.test", "lapsed@example.test"}

    table = read_csv(account_admin_client.get(CSV_URL, {"search": "Marsh"}))
    assert len(table) == 2
    assert table[1][1] == "pilot@example.test"


def test_csv_honors_the_ordering(
    account_admin_client: APIClient, reportable: dict[str, User]
) -> None:
    """The CSV export applies the requested ordering."""
    table = read_csv(account_admin_client.get(CSV_URL, {"ordering": "-email"}))
    exported = [row[1] for row in table[1:]]
    assert exported == sorted(exported, reverse=True)


def test_csv_is_not_paginated(account_admin_client: APIClient, reportable: dict[str, User]) -> None:
    """The CSV export is not paginated: every matching member is a row."""
    for index in range(30):
        MemberProfileFactory(user=UserFactory(email=f"bulk{index}@example.test"))
    table = read_csv(account_admin_client.get(CSV_URL))
    assert len(table) - 1 == User.objects.count()


def test_csv_with_no_matches_is_a_header_only(
    account_admin_client: APIClient, reportable: dict[str, User]
) -> None:
    """A filter matching nobody exports the header row alone."""
    table = read_csv(account_admin_client.get(CSV_URL, {"search": "nobody-by-that-name"}))
    assert table == [DEFAULT_HEADER]


# --------------------------------------------------------------------------
# PDF
# --------------------------------------------------------------------------
def test_pdf_is_a_valid_landscape_letter_document(
    account_admin_client: APIClient, reportable: dict[str, User], today: date
) -> None:
    """The PDF export is a valid landscape US-letter document with a title."""
    response = account_admin_client.get(PDF_URL)
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert response["Content-Disposition"] == (
        f'attachment; filename="caldart-members-{today.isoformat()}.pdf"'
    )
    body = response.content
    assert body.startswith(b"%PDF-")
    assert body.rstrip().endswith(b"%%EOF")
    # Landscape US letter is 792 x 612 points.
    assert re.search(rb"/MediaBox\s*\[\s*0\s+0\s+792\s+612\s*\]", body)
    assert b"/Title (CalDART membership report)" in body


def test_pdf_survives_an_empty_result_set(
    account_admin_client: APIClient, reportable: dict[str, User]
) -> None:
    """A filter matching nobody still produces a valid PDF."""
    response = account_admin_client.get(PDF_URL, {"search": "nobody-by-that-name"})
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF-")


def test_pdf_subtitle_summarizes_the_applied_filters(account_admin: User) -> None:
    """The PDF subtitle names every non-empty filter applied to the export."""
    request = APIRequestFactory().get(
        PDF_URL, {"status": "current", "dart": "Napa", "expiring_within": "30", "search": ""}
    )
    force_authenticate(request, user=account_admin)
    view = MemberExportPdfView()
    view.request = view.initialize_request(request)

    assert applied_filters(view.request) == {
        "status": "current",
        "dart": "Napa",
        "expiring_within": "30",
    }
    subtitle = view.subtitle(view.request)
    assert "status: current" in subtitle
    assert "dart: Napa" in subtitle
    assert "expiring within: 30" in subtitle
    # An empty parameter is not a filter.
    assert "search" not in subtitle


def test_pdf_subtitle_when_nothing_is_filtered(account_admin: User) -> None:
    """With no filters applied, the PDF subtitle is the default summary."""
    request = APIRequestFactory().get(PDF_URL)
    force_authenticate(request, user=account_admin)
    view = MemberExportPdfView()
    view.request = view.initialize_request(request)
    assert view.subtitle(view.request) == filter_summary({})


def test_pdf_paginates_a_long_report(
    account_admin_client: APIClient, reportable: dict[str, User]
) -> None:
    """A report of 124 members is drawn across the pages they fill, not one long one.

    One row to a line, so 124 members fill four landscape pages.
    """
    for index in range(120):
        MemberProfileFactory(user=UserFactory(email=f"bulk{index}@example.test"))
    body = account_admin_client.get(PDF_URL).content
    assert User.objects.count() == 124
    assert pdf_page_count(body) == 4
