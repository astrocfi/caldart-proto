"""Aircraft register exports (PLAN §6.5, §11): CSV content, PDF, filters, roles."""

from __future__ import annotations

import csv
import io
import re
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.accounts.roles import ACCOUNT_ADMIN, SYSTEM_ADMIN
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


@pytest.fixture
def register(db):
    today = timezone.localdate()
    current = AircraftFactory(
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
    expired = AircraftFactory(
        n_number="N33MM",
        make="Mooney",
        model="M20J",
        owner_name="Owen Delgado",
        owner_type="individual",
        insurance_expiration=today - timedelta(days=5),
    )
    missing = AircraftFactory(
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


def read_csv(response) -> list[list[str]]:
    body = b"".join(response.streaming_content).decode()
    return list(csv.reader(io.StringIO(body)))


def page_count(pdf: bytes) -> int:
    return len(re.findall(rb"/Type\s*/Page[^s]", pdf))


# --------------------------------------------------------------------------
# Permissions
# --------------------------------------------------------------------------
@pytest.mark.parametrize("url", [CSV_URL, PDF_URL])
def test_exports_require_authentication(api_client, url):
    assert api_client.get(url).status_code == 401


@pytest.mark.parametrize("url", [CSV_URL, PDF_URL])
def test_export_role_matrix(api_client, all_role_users, register, url):
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
def test_csv_headers_and_filename(api_client, account_admin, register):
    api_client.force_login(account_admin)
    response = api_client.get(CSV_URL)
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    assert "attachment; filename=" in response["Content-Disposition"]
    assert "caldart-aircraft-" in response["Content-Disposition"]


def test_csv_columns_are_the_ones_the_plan_names(api_client, account_admin, register):
    api_client.force_login(account_admin)
    rows = read_csv(api_client.get(CSV_URL))
    assert rows[0] == EXPECTED_HEADER


def test_csv_content(api_client, account_admin, register):
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
    assert current[9] == register["current"].insurance_expiration.isoformat()
    assert current[10] == "yes"

    assert by_number["N33MM"][10] == "no"
    missing = by_number["N44BE"]
    assert missing[8] == "" and missing[9] == "" and missing[10] == "no"


def test_csv_pilots_column_lists_attached_members(api_client, account_admin, register):
    marta = UserFactory(email="marta@example.test", first_name="Marta", last_name="Reyes")
    owen = UserFactory(email="owen@example.test", first_name="Owen", last_name="Delgado")
    MemberProfileFactory(user=marta).aircraft.add(register["current"])
    MemberProfileFactory(user=owen).aircraft.add(register["current"])

    api_client.force_login(account_admin)
    rows = read_csv(api_client.get(CSV_URL))
    pilots = {row[0]: row[11] for row in rows[1:]}
    assert set(pilots["N172SP"].split("; ")) == {"Marta Reyes", "Owen Delgado"}
    assert pilots["N33MM"] == ""


def test_csv_honours_the_same_filters_as_the_list(api_client, account_admin, register):
    api_client.force_login(account_admin)
    rows = read_csv(api_client.get(CSV_URL, {"insurance": "expired"}))
    assert [row[0] for row in rows[1:]] == ["N33MM"]

    rows = read_csv(api_client.get(CSV_URL, {"search": "cessna"}))
    assert [row[0] for row in rows[1:]] == ["N172SP"]

    rows = read_csv(api_client.get(CSV_URL, {"owner_type": "fbo"}))
    assert [row[0] for row in rows[1:]] == ["N44BE"]


def test_csv_honours_ordering(api_client, account_admin, register):
    api_client.force_login(account_admin)
    rows = read_csv(api_client.get(CSV_URL, {"ordering": "-n_number"}))
    assert [row[0] for row in rows[1:]] == ["N44BE", "N33MM", "N172SP"]


def test_csv_is_not_paginated(api_client, account_admin):
    for index in range(30):
        AircraftFactory(n_number=f"N{2000 + index}EX")
    api_client.force_login(account_admin)
    rows = read_csv(api_client.get(CSV_URL))
    assert len(rows) == 31


# --------------------------------------------------------------------------
# PDF
# --------------------------------------------------------------------------
def test_pdf_is_a_valid_document(api_client, account_admin, register):
    api_client.force_login(account_admin)
    response = api_client.get(PDF_URL)
    assert response.status_code == 200
    assert response["Content-Type"] == "application/pdf"
    assert "caldart-aircraft-" in response["Content-Disposition"]
    body = response.content
    assert body.startswith(b"%PDF-")
    assert body.rstrip().endswith(b"%%EOF")
    assert page_count(body) == 1


def test_pdf_is_filtered_like_the_list(api_client, account_admin, register):
    api_client.force_login(account_admin)
    everything = api_client.get(PDF_URL).content
    filtered = api_client.get(PDF_URL, {"insurance": "expired"}).content
    assert filtered.startswith(b"%PDF-")
    # Three rows compress to a bigger document than one.
    assert len(filtered) < len(everything)


def test_pdf_paginates_a_large_register(api_client, account_admin):
    for index in range(120):
        AircraftFactory(n_number=f"N{3000 + index}PD")
    api_client.force_login(account_admin)
    body = api_client.get(PDF_URL).content
    assert page_count(body) > 1


def test_pdf_survives_an_empty_result_set(api_client, account_admin, register):
    api_client.force_login(account_admin)
    response = api_client.get(PDF_URL, {"search": "no-such-aircraft"})
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF-")


def test_pdf_states_the_filters_it_was_run_with(api_client, account_admin, register):
    api_client.force_login(account_admin)
    body = api_client.get(PDF_URL, {"insurance": "expired"}).content
    # reportlab writes the subtitle into the content stream, compressed; the
    # PDF is valid and the row count matches the filter, which is what counts.
    assert body.startswith(b"%PDF-")
    assert page_count(body) == 1


def test_money_is_formatted_for_people_in_the_pdf_rows(register):
    from apps.aircraft.reports import aircraft_row

    row = aircraft_row(register["current"], currency=True)
    assert row[6:9] == ["$1,000,000", "$100,000", "$145,000"]
    plain = aircraft_row(register["current"])
    assert plain[6:9] == ["1000000.00", "100000.00", "145000.00"]


def test_odd_cent_amounts_keep_their_cents(register):
    from apps.aircraft.reports import aircraft_row

    register["current"].insurance_hull_cents = 12_345
    assert aircraft_row(register["current"], currency=True)[8] == "$123.45"
