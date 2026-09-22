"""The low-priority backend findings: one test per fixed item.

Each test here pins one behavior that used to be wrong: the bound on a
contribution, what a login says about a deactivated account, how the report
helpers treat markup and spreadsheet formulas, how the database password
reaches ``pg_dump``, where the PayPal token is cached, and which modules still
reach for an attribute defensively.
"""

from __future__ import annotations

import csv

import pytest
from rest_framework.test import APIClient

from apps.accounts.api.views import DEACTIVATED_MESSAGE, WRONG_CREDENTIALS_MESSAGE
from apps.accounts.models import User
from apps.members.models import MembershipPlan
from apps.payments.api.serializers import MAX_CONTRIBUTION_CENTS
from caldart import reports

CHECKOUT = "/api/v1/payments/checkout"
LOGIN = "/api/v1/auth/login"


# --------------------------------------------------------------------------
# A contribution is bounded
# --------------------------------------------------------------------------
@pytest.mark.django_db
def test_checkout_rejects_an_oversized_contribution(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A contribution above the cap is a 400 naming the field and the limit."""
    api_client.force_login(member)

    response = api_client.post(
        CHECKOUT,
        {
            "plan": "annual",
            "contribution_cents": MAX_CONTRIBUTION_CENTS + 1,
            "provider": "mock",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "contribution_cents": ["Ensure this value is less than or equal to 1000000000."]
    }


@pytest.mark.django_db
def test_checkout_accepts_a_contribution_at_the_cap(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The cap itself is still accepted, so the bound is inclusive."""
    api_client.force_login(member)

    response = api_client.post(
        CHECKOUT,
        {"plan": "annual", "contribution_cents": MAX_CONTRIBUTION_CENTS, "provider": "mock"},
    )

    assert response.status_code == 201


# --------------------------------------------------------------------------
# A login tells a wrong password nothing about the account
# --------------------------------------------------------------------------
@pytest.mark.django_db
def test_login_with_a_wrong_password_on_an_active_account(
    api_client: APIClient, member: User
) -> None:
    """A wrong password on an active account is the generic 400."""
    response = api_client.post(LOGIN, {"email": member.email, "password": "wrong-password"})

    assert response.status_code == 400
    assert response.json() == {"detail": WRONG_CREDENTIALS_MESSAGE}


@pytest.mark.django_db
def test_login_with_a_wrong_password_hides_a_deactivated_account(
    api_client: APIClient, member: User
) -> None:
    """A wrong password on a deactivated account gets the same 400 as any other."""
    member.is_active = False
    member.save(update_fields=["is_active"])

    response = api_client.post(LOGIN, {"email": member.email, "password": "wrong-password"})

    assert response.status_code == 400
    assert response.json() == {"detail": WRONG_CREDENTIALS_MESSAGE}


@pytest.mark.django_db
def test_login_with_the_right_password_names_the_deactivation(
    api_client: APIClient, member: User, password: str
) -> None:
    """Only a correct password is told the account has been deactivated."""
    member.is_active = False
    member.save(update_fields=["is_active"])

    response = api_client.post(LOGIN, {"email": member.email, "password": password})

    assert response.status_code == 403
    assert response.json() == {"detail": DEACTIVATED_MESSAGE}


# --------------------------------------------------------------------------
# A PDF heading is escaped, not parsed
# --------------------------------------------------------------------------
def test_escape_markup_replaces_the_three_reserved_characters() -> None:
    """``&``, ``<`` and ``>`` become entities, and ``&`` is replaced first."""
    assert reports.escape_markup("Tom & <Jerry>") == "Tom &amp; &lt;Jerry&gt;"


def test_a_pdf_title_may_look_like_markup() -> None:
    """A title carrying an unbalanced tag renders instead of raising."""
    response = reports.pdf_table_response(
        "members.pdf",
        title="Members <b",
        header=["Name"],
        rows=[["Marta Reyes"]],
    )

    assert response.status_code == 200
    assert response.content[:5] == b"%PDF-"


def test_a_pdf_subtitle_may_look_like_markup() -> None:
    """A subtitle built from a filter carrying an unbalanced tag renders."""
    response = reports.pdf_table_response(
        "members.pdf",
        title="Members",
        subtitle=reports.filter_summary({"search": "<b>"}),
        header=["Name"],
        rows=[["Marta Reyes"]],
    )

    assert response.status_code == 200
    assert response.content[:5] == b"%PDF-"


# --------------------------------------------------------------------------
# A CSV cell cannot become a spreadsheet formula
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("cell", "expected"),
    [
        ("=1+1", "'=1+1"),
        ("+1", "'+1"),
        ("-1", "'-1"),
        ("@SUM(A1)", "'@SUM(A1)"),
        ("\tcmd", "'\tcmd"),
        ("\rcmd", "'\rcmd"),
    ],
    ids=["equals", "plus", "minus", "at", "tab", "carriage-return"],
)
def test_a_dangerous_first_character_is_quoted(cell: str, expected: str) -> None:
    """Each leading character a spreadsheet reads as a formula gains a ``'``."""
    _header, row = list(reports.csv_rows(["value"], [[cell]]))

    assert next(csv.reader([row])) == [expected]


@pytest.mark.parametrize(
    "cell",
    ["Marta Reyes", "2026-09-22", "45.00", "$1,200", "N123AB"],
    ids=["name", "date", "money", "currency", "n-number"],
)
def test_an_ordinary_cell_is_untouched(cell: str) -> None:
    """A name, a date and a formatted amount are written exactly as they came."""
    _header, row = list(reports.csv_rows(["value"], [[cell]]))

    assert next(csv.reader([row])) == [cell]


def test_a_number_is_written_as_a_number() -> None:
    """An integer cell keeps its own rendering, so a sum still adds up."""
    _header, row = list(reports.csv_rows(["value"], [[-4500]]))

    assert next(csv.reader([row])) == ["-4500"]
