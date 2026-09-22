"""Payment reports for account administrators.

The list, the month/year summary and the CSV export, including the role matrix
and the arithmetic over a fixture spanning three months and two years.
"""

from __future__ import annotations

import datetime as dt

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import ACCOUNT_ADMIN, SYSTEM_ADMIN
from apps.members.models import MembershipPlan
from apps.payments.models import Payment, PaymentProvider, PaymentStatus, PaymentWallet
from tests.conftest import Golden, csv_body, read_csv, role_matrix
from tests.factories import PaymentFactory, UserFactory

pytestmark = pytest.mark.django_db

LIST = "/api/v1/admin/payments"
SUMMARY = "/api/v1/admin/payments/summary"
EXPORT = "/api/v1/admin/payments/export.csv"


def paid_at(year: int, month: int, day: int = 15) -> dt.datetime:
    """Local noon on a date, which is unambiguous in every US time zone."""
    return timezone.make_aware(dt.datetime(year, month, day, 12, 0))


def make_payment(
    user: User,
    plan: MembershipPlan,
    *,
    when: dt.datetime,
    provider: str = PaymentProvider.STRIPE,
    plan_cents: int = 4_500,
    contribution_cents: int = 0,
    status: str = PaymentStatus.SUCCEEDED,
    ref: str = "",
) -> Payment:
    """Create a completed (or not) payment backdated to ``when``."""
    return PaymentFactory(
        user=user,
        plan=plan,
        amount_cents=plan_cents + contribution_cents,
        plan_amount_cents=plan_cents,
        contribution_cents=contribution_cents,
        provider=provider,
        wallet=PaymentWallet.CARD,
        provider_ref=ref or f"ref-{user.pk}-{when:%Y%m%d}-{provider}",
        status=status,
        completed_at=when if status == PaymentStatus.SUCCEEDED else None,
        created_at=when,
    )


@pytest.fixture
def history(
    member: User, user_factory: type[UserFactory], annual_plan: MembershipPlan
) -> list[Payment]:
    """Three months of payments across two years and both real providers."""
    other = user_factory(email="wilma@example.test", first_name="Wilma", last_name="Voss")
    return [
        make_payment(member, annual_plan, when=paid_at(2025, 11, 3)),
        make_payment(
            other, annual_plan, when=paid_at(2025, 11, 20), provider=PaymentProvider.PAYPAL
        ),
        make_payment(member, annual_plan, when=paid_at(2026, 1, 8), contribution_cents=10_000),
        make_payment(
            other,
            annual_plan,
            when=paid_at(2026, 1, 25),
            provider=PaymentProvider.PAYPAL,
            contribution_cents=2_000,
        ),
        make_payment(member, annual_plan, when=paid_at(2026, 2, 2)),
        # Neither of these is revenue, so the summary must skip both.
        make_payment(
            other, annual_plan, when=paid_at(2026, 2, 3), status=PaymentStatus.FAILED, ref="dud"
        ),
        make_payment(
            member, annual_plan, when=paid_at(2026, 2, 4), status=PaymentStatus.PENDING, ref="wip"
        ),
    ]


# --------------------------------------------------------------------------
# GET /admin/payments
# --------------------------------------------------------------------------
def test_list_is_paginated_and_newest_first(
    api_client: APIClient, account_admin: User, member: User, history: list[Payment]
) -> None:
    """The payments list paginates and sorts newest first."""
    api_client.force_login(account_admin)
    body = api_client.get(LIST).json()

    assert body["count"] == 7
    periods = [row["created_at"][:7] for row in body["results"]]
    assert periods == ["2026-02", "2026-02", "2026-02", "2026-01", "2026-01", "2025-11", "2025-11"]
    assert body["results"][0]["user_name"] == f"{member.first_name} {member.last_name}"
    assert body["results"][0]["plan"] == "Annual"


def test_list_filters_by_date_range(
    api_client: APIClient, account_admin: User, history: list[Payment]
) -> None:
    """The list filters to payments created within the given date range."""
    api_client.force_login(account_admin)
    body = api_client.get(LIST, {"from": "2026-01-01", "to": "2026-01-31"}).json()
    assert body["count"] == 2


def test_list_filters_by_provider_and_status(
    api_client: APIClient, account_admin: User, history: list[Payment]
) -> None:
    """The list filters independently by provider and by status."""
    api_client.force_login(account_admin)
    assert api_client.get(LIST, {"provider": "paypal"}).json()["count"] == 2
    assert api_client.get(LIST, {"status": "failed"}).json()["count"] == 1
    assert api_client.get(LIST, {"provider": "stripe", "status": "succeeded"}).json()["count"] == 3


def test_list_searches_name_email_and_reference(
    api_client: APIClient, account_admin: User, history: list[Payment]
) -> None:
    """The search parameter matches on name, email, or provider reference."""
    api_client.force_login(account_admin)
    assert api_client.get(LIST, {"search": "wilma"}).json()["count"] == 3
    assert api_client.get(LIST, {"search": "member@example.test"}).json()["count"] == 4
    assert api_client.get(LIST, {"search": "dud"}).json()["count"] == 1


def test_list_orders_by_amount(
    api_client: APIClient, account_admin: User, history: list[Payment]
) -> None:
    """The list orders by amount_cents when asked."""
    api_client.force_login(account_admin)
    amounts = [
        row["amount_cents"]
        for row in api_client.get(LIST, {"ordering": "-amount_cents"}).json()["results"]
    ]
    assert amounts == sorted(amounts, reverse=True)


def test_list_rejects_a_bad_ordering_field(
    api_client: APIClient, account_admin: User, history: list[Payment]
) -> None:
    """Ordering by a field outside the allowed set is refused."""
    api_client.force_login(account_admin)
    assert api_client.get(LIST, {"ordering": "user__password"}).status_code == 400


def test_list_rejects_a_bad_date(
    api_client: APIClient, account_admin: User, history: list[Payment]
) -> None:
    """An unreadable date filter is refused with a 400."""
    api_client.force_login(account_admin)
    assert api_client.get(LIST, {"from": "last tuesday"}).status_code == 400


def test_list_rejects_an_unknown_provider(
    api_client: APIClient, account_admin: User, history: list[Payment]
) -> None:
    """A provider outside the known choices is refused with a 400."""
    api_client.force_login(account_admin)
    assert api_client.get(LIST, {"provider": "bitcoin"}).status_code == 400


def test_list_page_size(api_client: APIClient, account_admin: User, history: list[Payment]) -> None:
    """The page_size parameter controls how many results come back per page."""
    api_client.force_login(account_admin)
    body = api_client.get(LIST, {"page_size": 2}).json()
    assert len(body["results"]) == 2
    assert body["next"] is not None


# --------------------------------------------------------------------------
# GET /admin/payments/summary
# --------------------------------------------------------------------------
def test_summary_by_month(
    api_client: APIClient, account_admin: User, history: list[Payment]
) -> None:
    """The month summary groups payments by month, with correct totals per provider."""
    api_client.force_login(account_admin)
    rows = api_client.get(SUMMARY, {"group": "month"}).json()

    assert [row["period"] for row in rows] == ["2025-11", "2026-01", "2026-02"]

    november, january, february = rows
    assert november["count"] == 2
    assert november["total_cents"] == 9_000
    assert november["plan_cents"] == 9_000
    assert november["contribution_cents"] == 0
    assert november["by_provider"] == {"stripe": 4_500, "paypal": 4_500}

    assert january["count"] == 2
    assert january["total_cents"] == 21_000
    assert january["contribution_cents"] == 12_000
    assert january["by_provider"] == {"stripe": 14_500, "paypal": 6_500}

    # Only the succeeded payment counts in February.
    assert february["count"] == 1
    assert february["total_cents"] == 4_500
    assert february["by_provider"] == {"stripe": 4_500}


def test_summary_by_year(
    api_client: APIClient, account_admin: User, history: list[Payment]
) -> None:
    """The year summary groups payments by year, with correct totals per provider."""
    api_client.force_login(account_admin)
    rows = api_client.get(SUMMARY, {"group": "year"}).json()

    assert [row["period"] for row in rows] == ["2025", "2026"]
    assert rows[0]["total_cents"] == 9_000
    assert rows[1]["count"] == 3
    assert rows[1]["total_cents"] == 25_500
    assert rows[1]["contribution_cents"] == 12_000
    assert rows[1]["by_provider"] == {"stripe": 19_000, "paypal": 6_500}


def test_summary_defaults_to_month(
    api_client: APIClient, account_admin: User, history: list[Payment]
) -> None:
    """With no group parameter the summary groups by month."""
    api_client.force_login(account_admin)
    assert api_client.get(SUMMARY).json()[0]["period"] == "2025-11"


def test_summary_honors_the_date_filter(
    api_client: APIClient, account_admin: User, history: list[Payment]
) -> None:
    """The summary applies the same date filter as the list."""
    api_client.force_login(account_admin)
    rows = api_client.get(SUMMARY, {"from": "2026-01-01"}).json()
    assert [row["period"] for row in rows] == ["2026-01", "2026-02"]


def test_summary_honors_the_provider_filter(
    api_client: APIClient, account_admin: User, history: list[Payment]
) -> None:
    """The summary applies the provider filter to every grouped row."""
    api_client.force_login(account_admin)
    rows = api_client.get(SUMMARY, {"provider": "paypal"}).json()
    assert [row["period"] for row in rows] == ["2025-11", "2026-01"]
    assert all(set(row["by_provider"]) == {"paypal"} for row in rows)


def test_summary_rejects_an_unknown_grouping(
    api_client: APIClient, account_admin: User, history: list[Payment]
) -> None:
    """A grouping other than month or year is refused with a 400."""
    api_client.force_login(account_admin)
    assert api_client.get(SUMMARY, {"group": "week"}).status_code == 400


def test_summary_of_nothing_is_an_empty_list(api_client: APIClient, account_admin: User) -> None:
    """With no payments at all the summary is an empty list."""
    api_client.force_login(account_admin)
    assert api_client.get(SUMMARY).json() == []


# --------------------------------------------------------------------------
# GET /admin/payments/export.csv
# --------------------------------------------------------------------------
def test_export_returns_a_csv_download(
    api_client: APIClient, account_admin: User, history: list[Payment]
) -> None:
    """The export is a named, downloadable CSV with the seven history rows."""
    api_client.force_login(account_admin)
    response = api_client.get(EXPORT)

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    assert response["Content-Disposition"] == 'attachment; filename="caldart-payments.csv"'

    rows = read_csv(response)
    assert rows[0][:4] == ["paid_on", "name", "email", "plan"]
    assert len(rows) == 8  # header + 7 payments


def test_export_honors_the_filters(
    api_client: APIClient, account_admin: User, history: list[Payment]
) -> None:
    """The export applies the same provider and status filters as the list."""
    api_client.force_login(account_admin)
    response = api_client.get(EXPORT, {"provider": "paypal", "status": "succeeded"})
    rows = read_csv(response)

    assert len(rows) == 3
    assert [row[7] for row in rows[1:]] == ["paypal", "paypal"]


def test_export_matches_the_recorded_document(
    api_client: APIClient,
    account_admin: User,
    member: User,
    history: list[Payment],
    golden: Golden,
) -> None:
    """The whole export -- header, every row, all eleven columns -- matches its record."""
    api_client.force_login(account_admin)

    body = csv_body(api_client.get(EXPORT))

    # The fixture's names come from Faker and its references carry row ids, so
    # both are replaced by fixed stand-ins before the documents are compared.
    replace = {payment.provider_ref: f"ref-{index}" for index, payment in enumerate(history, 1)}
    replace[f"{member.first_name} {member.last_name}"] = "Fran Member"
    golden("payments-export.csv", body, replace=replace)


def test_export_formats_money_as_dollars(
    api_client: APIClient, member: User, account_admin: User, annual_plan: MembershipPlan
) -> None:
    """The export formats cent amounts as two-decimal dollar strings."""
    make_payment(member, annual_plan, when=paid_at(2026, 3, 9), contribution_cents=10_000)
    api_client.force_login(account_admin)
    row = read_csv(api_client.get(EXPORT))[1]

    assert row[0] == "2026-03-09"
    assert row[4] == "45.00"  # plan_amount
    assert row[5] == "100.00"  # contribution
    assert row[6] == "145.00"  # total


# --------------------------------------------------------------------------
# Role matrix
# --------------------------------------------------------------------------
@pytest.mark.parametrize("url", [LIST, SUMMARY, EXPORT])
@pytest.mark.parametrize(("slug", "allowed"), role_matrix(ACCOUNT_ADMIN, SYSTEM_ADMIN))
def test_reports_are_account_admin_only(
    api_client: APIClient,
    all_role_users: dict[str, User],
    history: list[Payment],
    url: str,
    slug: str,
    allowed: bool,
) -> None:
    """Only account admins and system admins may view any of the three reports."""
    api_client.force_login(all_role_users[slug])
    assert api_client.get(url).status_code == (200 if allowed else 403)


@pytest.mark.parametrize("url", [LIST, SUMMARY, EXPORT])
def test_reports_reject_anonymous_callers(api_client: APIClient, url: str) -> None:
    """An anonymous caller gets a 401 from every report endpoint."""
    assert api_client.get(url).status_code == 401
