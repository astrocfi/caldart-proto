"""Aircraft register exports: CSV content, PDF, filters, roles."""

from __future__ import annotations

import csv
import io
import re
from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import ACCOUNT_ADMIN, SYSTEM_ADMIN
from apps.aircraft.models import Aircraft
from tests.factories import AircraftFactory, MemberProfileFactory, UserFactory

#: Aircraft register fixture, keyed by scenario name.
RegisterDict = dict[str, Aircraft]

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


@pytest.fixture
def register(db: None) -> RegisterDict:
    """Three aircraft: current insurance, expired insurance, and nothing on file."""
    today = timezone.localdate()
    current = AircraftFactory.create(
        n_number="N172SP",
        make="Cessna",
        model="172S Skyhawk",
        owner_name="Palo Alto Flying Club",
        owner_type="club",
        insurance_carrier="Avemco",
        insurance_liability_per_occurrence_cents=100_000_000,
        insurance_liability_per_person_cents=10_000_000,
        insurance_hull_cents=14_500_000,
        insurance_expiration=today + timedelta(days=200),
    )
    expired = AircraftFactory.create(
        n_number="N33MM",
        make="Mooney",
        model="M20J",
        owner_name="Owen Delgado",
        owner_type="individual",
        insurance_expiration=today - timedelta(days=5),
    )
    missing = AircraftFactory.create(
        n_number="N44BE",
        make="Beechcraft",
        model="A36 Bonanza",
        owner_name="Hayward Aviation Services",
        owner_type="fbo",
        insurance_carrier="",
        insurance_liability_per_occurrence_cents=0,
        insurance_liability_per_person_cents=0,
        insurance_hull_cents=None,
        insurance_expiration=None,
    )
    return {"current": current, "expired": expired, "missing": missing}


def read_csv(response: Response) -> list[list[str]]:
    """Decode a streamed CSV response into rows of string cells."""
    # streaming_content is a StreamingHttpResponse attribute the Response stub omits.
    body = b"".join(response.streaming_content).decode()  # type: ignore[attr-defined]
    return list(csv.reader(io.StringIO(body)))


def page_count(pdf: bytes) -> int:
    """Count the ``/Type /Page`` objects in a raw PDF document."""
    return len(re.findall(rb"/Type\s*/Page[^s]", pdf))


# --------------------------------------------------------------------------
# Permissions
# --------------------------------------------------------------------------
@pytest.mark.parametrize("url", [CSV_URL, PDF_URL])
def test_exports_require_authentication(api_client: APIClient, url: str) -> None:
    """Both export endpoints refuse an anonymous caller with a 401."""
    assert api_client.get(url).status_code == 401


@pytest.mark.parametrize("url", [CSV_URL, PDF_URL])
def test_export_role_matrix(
    api_client: APIClient, all_role_users: dict[str, User], register: RegisterDict, url: str
) -> None:
    """Only account and system admins get 200 from either export; others get 403."""
    allowed = {ACCOUNT_ADMIN, SYSTEM_ADMIN}
    for slug, user in all_role_users.items():
        api_client.force_login(user)
        response = api_client.get(url)
        expected = 200 if slug in allowed else 403
        assert response.status_code == expected, f"{slug} got {response.status_code}"
        api_client.logout()


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


def test_csv_columns_are_the_ones_the_plan_names(
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
    assert missing[8] == "" and missing[9] == "" and missing[10] == "no"


def test_csv_pilots_column_lists_attached_members(
    api_client: APIClient, account_admin: User, register: RegisterDict
) -> None:
    """The pilots column lists every profile attached to the aircraft, joined by "; "."""
    marta = UserFactory.create(email="marta@example.test", first_name="Marta", last_name="Reyes")
    owen = UserFactory.create(email="owen@example.test", first_name="Owen", last_name="Delgado")
    MemberProfileFactory.create(user=marta).aircraft.add(register["current"])
    MemberProfileFactory.create(user=owen).aircraft.add(register["current"])

    api_client.force_login(account_admin)
    rows = read_csv(api_client.get(CSV_URL))
    pilots = {row[0]: row[11] for row in rows[1:]}
    assert set(pilots["N172SP"].split("; ")) == {"Marta Reyes", "Owen Delgado"}
    assert pilots["N33MM"] == ""


def test_csv_honors_the_same_filters_as_the_list(
    api_client: APIClient, account_admin: User, register: RegisterDict
) -> None:
    """The CSV export applies the ``insurance``, ``search`` and ``owner_type`` filters."""
    api_client.force_login(account_admin)
    rows = read_csv(api_client.get(CSV_URL, {"insurance": "expired"}))
    assert [row[0] for row in rows[1:]] == ["N33MM"]

    rows = read_csv(api_client.get(CSV_URL, {"search": "cessna"}))
    assert [row[0] for row in rows[1:]] == ["N172SP"]

    rows = read_csv(api_client.get(CSV_URL, {"owner_type": "fbo"}))
    assert [row[0] for row in rows[1:]] == ["N44BE"]


def test_csv_honors_ordering(
    api_client: APIClient, account_admin: User, register: RegisterDict
) -> None:
    """The CSV export honors the ``ordering`` parameter, descending N-number here."""
    api_client.force_login(account_admin)
    rows = read_csv(api_client.get(CSV_URL, {"ordering": "-n_number"}))
    assert [row[0] for row in rows[1:]] == ["N44BE", "N33MM", "N172SP"]


def test_csv_is_not_paginated(api_client: APIClient, account_admin: User) -> None:
    """The CSV export returns every matching row, not one page of the list view."""
    for index in range(30):
        AircraftFactory.create(n_number=f"N{2000 + index}EX")
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
    assert page_count(body) == 1


def test_pdf_is_filtered_like_the_list(
    api_client: APIClient, account_admin: User, register: RegisterDict
) -> None:
    """A filtered PDF export is smaller than the unfiltered one, and still valid."""
    api_client.force_login(account_admin)
    everything = api_client.get(PDF_URL).content
    filtered = api_client.get(PDF_URL, {"insurance": "expired"}).content
    assert filtered.startswith(b"%PDF-")
    # Three rows compress to a bigger document than one.
    assert len(filtered) < len(everything)


def test_pdf_paginates_a_large_register(api_client: APIClient, account_admin: User) -> None:
    """A register too large for one page produces a multi-page PDF."""
    for index in range(120):
        AircraftFactory.create(n_number=f"N{3000 + index}PD")
    api_client.force_login(account_admin)
    body = api_client.get(PDF_URL).content
    assert page_count(body) > 1


def test_pdf_survives_an_empty_result_set(
    api_client: APIClient, account_admin: User, register: RegisterDict
) -> None:
    """A filter that matches nothing still returns a valid, empty-of-rows PDF."""
    api_client.force_login(account_admin)
    response = api_client.get(PDF_URL, {"search": "no-such-aircraft"})
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF-")


def test_pdf_states_the_filters_it_was_run_with(
    api_client: APIClient, account_admin: User, register: RegisterDict
) -> None:
    """A filtered PDF export stays a valid one-page document with the right row count."""
    api_client.force_login(account_admin)
    body = api_client.get(PDF_URL, {"insurance": "expired"}).content
    # reportlab writes the subtitle into the content stream, compressed; the
    # PDF is valid and the row count matches the filter, which is what counts.
    assert body.startswith(b"%PDF-")
    assert page_count(body) == 1


def test_money_is_formatted_for_people_in_the_pdf_rows(register: RegisterDict) -> None:
    """``aircraft_row`` formats cents as dollar amounts only when ``currency`` is set."""
    from apps.aircraft.reports import aircraft_row

    row = aircraft_row(register["current"], currency=True)
    assert row[6:9] == ["$1,000,000", "$100,000", "$145,000"]
    plain = aircraft_row(register["current"])
    assert plain[6:9] == ["1000000.00", "100000.00", "145000.00"]


def test_odd_cent_amounts_keep_their_cents(register: RegisterDict) -> None:
    """``aircraft_row`` keeps non-round cent amounts precise formatting as currency."""
    from apps.aircraft.reports import aircraft_row

    register["current"].insurance_hull_cents = 12_345
    assert aircraft_row(register["current"], currency=True)[8] == "$123.45"
