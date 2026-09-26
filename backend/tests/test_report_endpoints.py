"""``/api/v1/reports/``: the report list, each report's columns, and its two exports.

One generic view serves every report, so the role matrix, the 404 for an unknown
report and the refusals are proved here once per slug rather than once per app.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import ACCOUNT_ADMIN, DART_LEADER, SYSTEM_ADMIN, TREASURER
from apps.aircraft.reports import AIRCRAFT_REPORT_COLUMNS
from apps.members.models import MembershipPlan
from apps.members.reports import MEMBER_REPORT_COLUMNS
from apps.payments.models import Payment, PaymentProvider, PaymentStatus
from apps.payments.reconciliation import RECONCILIATION_COLUMNS
from apps.payments.reports import CONTRIBUTION_COLUMNS, PAYMENT_REPORT_COLUMNS
from apps.reports.registry import REPORTS
from caldart.reports import FIXED_COLUMNS_MESSAGE, ReportColumn
from tests.conftest import PdfText, read_csv, role_matrix
from tests.factories import PaymentFactory, UserFactory

pytestmark = pytest.mark.django_db

REPORTS_URL = "/api/v1/reports"

#: Each report, with the roles its matrix admits.
READERS: dict[str, tuple[str, ...]] = {
    "members": (DART_LEADER, ACCOUNT_ADMIN, SYSTEM_ADMIN),
    "aircraft": (ACCOUNT_ADMIN, SYSTEM_ADMIN),
    "payments": (TREASURER, ACCOUNT_ADMIN, SYSTEM_ADMIN),
    "reconciliation": (TREASURER, ACCOUNT_ADMIN, SYSTEM_ADMIN),
    "contributions": (TREASURER, ACCOUNT_ADMIN, SYSTEM_ADMIN),
    "emails": (SYSTEM_ADMIN,),
}

#: The reports an account administrator reads, which the tests signed in as one cover.
#: The email log is the system administrator's alone and is covered in
#: ``test_email_log_report.py``.
ACCOUNT_ADMIN_REPORTS = [slug for slug, roles in READERS.items() if ACCOUNT_ADMIN in roles]

#: One case per report, per role, per URL: the whole allow/deny matrix.
MATRIX = [
    (url.format(slug=slug), role, allowed)
    for slug, roles in READERS.items()
    for url in (
        "/api/v1/reports/{slug}/columns",
        "/api/v1/reports/{slug}/export.csv",
        "/api/v1/reports/{slug}/export.pdf",
    )
    for role, allowed in role_matrix(*roles)
]


def column_payload[RowT](columns: Sequence[ReportColumn[RowT]]) -> list[dict[str, str | bool]]:
    """What ``/columns`` answers for ``columns``: key, label and default, in order."""
    return [
        {"key": column.key, "label": column.label, "default": column.default} for column in columns
    ]


#: Each report's columns payload, built from the column registries themselves.
COLUMN_PAYLOADS: dict[str, list[dict[str, str | bool]]] = {
    "members": column_payload(MEMBER_REPORT_COLUMNS),
    "aircraft": column_payload(AIRCRAFT_REPORT_COLUMNS),
    "payments": column_payload(PAYMENT_REPORT_COLUMNS),
    "reconciliation": column_payload(RECONCILIATION_COLUMNS),
    "contributions": column_payload(CONTRIBUTION_COLUMNS),
}


def export_url(slug: str, fmt: str) -> str:
    """The export URL of report ``slug`` in format ``fmt``."""
    return f"/api/v1/reports/{slug}/export.{fmt}"


# --------------------------------------------------------------------------
# GET /reports
# --------------------------------------------------------------------------
def test_the_report_list_refuses_an_anonymous_caller(api_client: APIClient) -> None:
    """Signing in comes first: an anonymous caller is a 401."""
    assert api_client.get(REPORTS_URL).status_code == 401


@pytest.mark.parametrize(
    ("role", "slugs"),
    [
        ("member", []),
        ("dart_leader", ["members"]),
        ("user_admin", []),
        ("treasurer", ["payments", "reconciliation", "contributions", "donors"]),
        ("account_admin", ["members", "aircraft", "payments", "reconciliation", "contributions"]),
        ("website_admin", []),
        (
            "system_admin",
            [
                "members",
                "aircraft",
                "payments",
                "reconciliation",
                "contributions",
                "donors",
                "emails",
            ],
        ),
    ],
)
def test_the_report_list_names_the_reports_the_caller_may_read(
    api_client: APIClient, all_role_users: dict[str, User], role: str, slugs: list[str]
) -> None:
    """Each role sees exactly the reports it may download, in registry order."""
    api_client.force_login(all_role_users[role])
    assert [row["slug"] for row in api_client.get(REPORTS_URL).json()] == slugs


def test_the_report_list_describes_each_report(account_admin_client: APIClient) -> None:
    """Each entry carries the slug, the title, whether columns are chosen, and periods."""
    assert account_admin_client.get(REPORTS_URL).json() == [
        {
            "slug": "members",
            "title": "CalDART membership report",
            "choosable": True,
            "periods": False,
        },
        {
            "slug": "aircraft",
            "title": "CalDART aircraft register",
            "choosable": True,
            "periods": False,
        },
        {"slug": "payments", "title": "CalDART payments", "choosable": True, "periods": True},
        {
            "slug": "reconciliation",
            "title": "CalDART reconciliation",
            "choosable": False,
            "periods": False,
        },
        {
            "slug": "contributions",
            "title": "CalDART contributions",
            "choosable": False,
            "periods": True,
        },
    ]


# --------------------------------------------------------------------------
# The role matrix and the unknown report
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("url", "role", "allowed"), MATRIX)
def test_each_report_admits_exactly_its_roles(
    api_client: APIClient, all_role_users: dict[str, User], url: str, role: str, allowed: bool
) -> None:
    """The spec's roles and a system administrator read a report; the rest get 403."""
    api_client.force_login(all_role_users[role])
    assert api_client.get(url).status_code == (200 if allowed else 403)


@pytest.mark.parametrize(
    "url",
    [
        "/api/v1/reports/members/columns",
        "/api/v1/reports/members/export.csv",
        "/api/v1/reports/members/export.pdf",
    ],
)
def test_a_report_refuses_an_anonymous_caller(api_client: APIClient, url: str) -> None:
    """An anonymous caller is a 401 rather than a 403."""
    assert api_client.get(url).status_code == 401


@pytest.mark.parametrize(
    "url",
    [
        "/api/v1/reports/karma/columns",
        "/api/v1/reports/karma/export.csv",
        "/api/v1/reports/karma/export.pdf",
    ],
)
def test_an_unknown_report_is_a_404(account_admin_client: APIClient, url: str) -> None:
    """A slug the registry does not hold is a 404, before any role is checked."""
    assert account_admin_client.get(url).status_code == 404


def test_an_unknown_report_is_a_404_even_for_a_member(api_client: APIClient, member: User) -> None:
    """A caller who may read nothing still learns only that the report does not exist."""
    api_client.force_login(member)
    assert api_client.get(export_url("karma", "csv")).status_code == 404


def test_an_unknown_format_is_a_404(account_admin_client: APIClient) -> None:
    """Only ``csv`` and ``pdf`` are formats."""
    assert account_admin_client.get(export_url("members", "xlsx")).status_code == 404


# --------------------------------------------------------------------------
# The columns of each report
# --------------------------------------------------------------------------
@pytest.mark.parametrize("slug", ACCOUNT_ADMIN_REPORTS)
def test_the_columns_answer_the_registry(account_admin_client: APIClient, slug: str) -> None:
    """Every column, in export order, with its key, label and whether it is a default."""
    response = account_admin_client.get(f"/api/v1/reports/{slug}/columns")
    assert response.json() == COLUMN_PAYLOADS[slug]


# --------------------------------------------------------------------------
# The exports
# --------------------------------------------------------------------------
@pytest.mark.parametrize("slug", ACCOUNT_ADMIN_REPORTS)
@pytest.mark.parametrize(
    ("fmt", "content_type"), [("csv", "text/csv; charset=utf-8"), ("pdf", "application/pdf")]
)
def test_each_export_is_a_dated_download(
    account_admin_client: APIClient, today: date, slug: str, fmt: str, content_type: str
) -> None:
    """Every report downloads as ``<stem>-<YYYY-MM-DD>.<fmt>`` with its media type."""
    response = account_admin_client.get(export_url(slug, fmt))
    stem = REPORTS[slug].filename_stem
    assert (response["Content-Type"], response["Content-Disposition"]) == (
        content_type,
        f'attachment; filename="{stem}-{today.isoformat()}.{fmt}"',
    )


@pytest.mark.parametrize("slug", ["reconciliation", "contributions"])
def test_a_fixed_report_refuses_a_column_choice(account_admin_client: APIClient, slug: str) -> None:
    """``?columns=`` on a fixed report is a 400 saying the columns are fixed."""
    response = account_admin_client.get(export_url(slug, "csv"), {"columns": "period"})
    assert (response.status_code, response.json()) == (400, {"columns": [FIXED_COLUMNS_MESSAGE]})


@pytest.mark.parametrize("slug", ["members", "aircraft", "payments"])
def test_a_choosable_report_refuses_an_unknown_column(
    account_admin_client: APIClient, slug: str
) -> None:
    """A column the report does not carry is a 400 keyed ``columns`` naming it."""
    response = account_admin_client.get(export_url(slug, "pdf"), {"columns": "bogus"})
    assert (response.status_code, response.json()) == (
        400,
        {"columns": ["Unknown column: bogus"]},
    )


def test_a_filter_the_report_refuses_is_a_400(account_admin_client: APIClient) -> None:
    """The export refuses what its list refuses, keyed by the param at fault."""
    response = account_admin_client.get(export_url("payments", "csv"), {"provider": "barter"})
    assert (response.status_code, response.json()) == (
        400,
        {"provider": ["Unknown provider 'barter'."]},
    )


def test_an_unknown_period_is_a_400(treasurer_client: APIClient) -> None:
    """A period that is not one of the four is refused, keyed ``period``."""
    response = treasurer_client.get(export_url("payments", "csv"), {"period": "next_week"})
    assert (response.status_code, response.json()) == (
        400,
        {"period": ["Unknown period 'next_week'."]},
    )


@pytest.fixture
def two_years(annual_plan: MembershipPlan, today: date) -> list[Payment]:
    """One succeeded payment received this year and one received last year."""
    payer = UserFactory(email="payer@example.test", first_name="Pat", last_name="Payer")
    return [
        PaymentFactory(
            user=payer,
            plan=annual_plan,
            provider=PaymentProvider.MANUAL,
            status=PaymentStatus.SUCCEEDED,
            received_on=date(year, 3, 1),
            amount_cents=amount,
            plan_amount_cents=amount - 1000,
            contribution_cents=1000,
        )
        for year, amount in [(today.year, 6000), (today.year - 1, 8000)]
    ]


def test_a_period_narrows_a_payments_download(
    treasurer_client: APIClient, two_years: list[Payment]
) -> None:
    """``period=last_year`` downloads last year's payments alone."""
    rows = read_csv(
        treasurer_client.get(
            export_url("payments", "csv"), {"period": "last_year", "columns": "total"}
        )
    )
    assert rows == [["Total"], ["80.00"]]


def test_a_period_picks_the_contributions_year(
    treasurer_client: APIClient, two_years: list[Payment], today: date, pdf_text: PdfText
) -> None:
    """``period=last_year`` reports last year's giving and names that year."""
    body = treasurer_client.get(export_url("contributions", "pdf"), {"period": "last_year"}).content
    page = pdf_text(body)[0]
    assert page[:2] == ["CalDART contributions", f"year: {today.year - 1}"]


def test_a_period_is_ignored_by_a_report_without_dates(
    account_admin_client: APIClient, fixed_name_admin: User
) -> None:
    """The members report takes no period, so one changes nothing."""
    with_period = account_admin_client.get(export_url("members", "csv"), {"period": "last_year"})
    without = account_admin_client.get(export_url("members", "csv"))
    assert with_period.content == without.content
