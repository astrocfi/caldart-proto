"""The member report's Status column and its certificate abbreviation.

The membership report prints the ``MembershipState`` choice's label in its
``status`` cell, never the stored slug, and abbreviates the airline transport
pilot certificate to "ATP" in its ``certificate`` cell while the profile
screens keep spelling it out.  See ``docs/developer/reports.rst`` for the
report's columns and ``docs/user/account-administrator-guide.rst`` for what a
reader sees.
"""

from __future__ import annotations

from datetime import date

import pytest
from rest_framework.test import APIClient

from apps.members.models import (
    MembershipPlan,
    MembershipState,
    MembershipStatusChoices,
    PilotCertificateType,
)
from apps.members.reports import REPORT_CERTIFICATE_LABELS
from tests.conftest import PdfText, read_csv
from tests.factories import MemberProfileFactory, MembershipFactory, UserFactory

pytestmark = pytest.mark.django_db

CSV_URL = "/api/v1/reports/members/export.csv"
PDF_URL = "/api/v1/reports/members/export.pdf"

#: Export only the two columns each test below reads, so a row's cells are
#: unambiguous by position without pulling in the whole default column set.
STATUS_COLUMNS = {"columns": "email,status"}
CERTIFICATE_COLUMNS = {"columns": "email,certificate"}


def row_by_email(table: list[list[str]], email: str) -> list[str]:
    """The data row whose first cell is ``email``, from a two-column export."""
    return next(row for row in table[1:] if row[0] == email)


def test_membership_state_choices_are_the_five_report_words() -> None:
    """The five ``MembershipState`` labels, in order.

    The report, the member list's status filter, and the portal's status select all
    read their labels from here, so this is the one place the five words live.
    """
    assert MembershipState.choices == [
        ("current", "Current"),
        ("new", "Unpaid"),
        ("expired", "Expired"),
        ("none", "No membership"),
        ("friend", "Friend"),
    ]


def test_member_report_prints_no_membership_never_the_slug(
    account_admin_client: APIClient,
) -> None:
    """A member who has never held a term reads "No membership", never "none"."""
    UserFactory(email="never-a-member@example.test")
    table = read_csv(account_admin_client.get(CSV_URL, STATUS_COLUMNS))
    assert row_by_email(table, "never-a-member@example.test")[1] == "No membership"


def test_member_report_prints_unpaid_for_a_joined_but_uncovered_member(
    account_admin_client: APIClient, annual_plan: MembershipPlan, today: date
) -> None:
    """A member whose only term is unpaid reads "Unpaid", not the "new" slug."""
    user = UserFactory(email="unpaid@example.test")
    MembershipFactory(
        user=user, plan=annual_plan, starts_on=today, status=MembershipStatusChoices.NEW
    )
    table = read_csv(account_admin_client.get(CSV_URL, STATUS_COLUMNS))
    assert row_by_email(table, "unpaid@example.test")[1] == "Unpaid"


def test_member_report_abbreviates_the_atp_certificate(
    account_admin_client: APIClient,
) -> None:
    """The certificate column shows "ATP", never the full certificate name."""
    user = UserFactory(email="atp-pilot@example.test")
    MemberProfileFactory(user=user, pilot_certificate_type=PilotCertificateType.ATP)
    table = read_csv(account_admin_client.get(CSV_URL, CERTIFICATE_COLUMNS))
    assert row_by_email(table, "atp-pilot@example.test")[1] == "ATP"


def test_member_report_keeps_other_certificates_spelled_out(
    account_admin_client: APIClient,
) -> None:
    """A certificate other than ATP still prints its full choice label."""
    user = UserFactory(email="private-pilot@example.test")
    MemberProfileFactory(user=user, pilot_certificate_type=PilotCertificateType.PRIVATE)
    table = read_csv(account_admin_client.get(CSV_URL, CERTIFICATE_COLUMNS))
    assert row_by_email(table, "private-pilot@example.test")[1] == "Private"


def test_report_certificate_labels_overrides_only_the_atp_certificate() -> None:
    """The report-only abbreviation applies to ATP and to nothing else."""
    assert REPORT_CERTIFICATE_LABELS == {PilotCertificateType.ATP: "ATP"}


def test_member_report_pdf_prints_the_label_and_the_abbreviation(
    account_admin_client: APIClient, pdf_text: PdfText
) -> None:
    """The rendered PDF shows "No membership" and "ATP", never the raw codes."""
    UserFactory(email="never-pdf-label@example.test")
    pilot = UserFactory(email="atp-pdf-label@example.test")
    MemberProfileFactory(user=pilot, pilot_certificate_type=PilotCertificateType.ATP)
    body = account_admin_client.get(
        PDF_URL, {"columns": "email,status,certificate", "search": "pdf-label"}
    ).content
    text = " ".join(cell for page in pdf_text(body) for cell in page)
    assert "No membership" in text
    assert "ATP" in text
    assert "none" not in text.lower()
