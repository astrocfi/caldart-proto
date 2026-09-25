"""Reconciling the books against a bank or provider statement.

``GET /admin/payments/reconciliation`` and the reconciliation report answer one row per
period, or per provider, over a range: what arrived, what the provider kept,
what reached the bank, what went back, and how much is still unmatched.
"""

from __future__ import annotations

import datetime as dt

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import ACCOUNT_ADMIN, SYSTEM_ADMIN, TREASURER
from apps.members.models import MembershipPlan
from apps.payments.models import Payment, PaymentProvider, PaymentStatus
from tests.conftest import PdfText, read_csv, role_matrix
from tests.factories import PaymentFactory, RefundFactory

pytestmark = pytest.mark.django_db

TABLE = "/api/v1/admin/payments/reconciliation"
EXPORT_CSV = "/api/v1/reports/reconciliation/export.csv"
EXPORT_PDF = "/api/v1/reports/reconciliation/export.pdf"


def at_noon(year: int, month: int, day: int) -> dt.datetime:
    """Local noon on a date, which is unambiguous in every US time zone."""
    return timezone.make_aware(dt.datetime(year, month, day, 12, 0))


def settled(
    user: User,
    plan: MembershipPlan,
    *,
    when: dt.datetime,
    total: int,
    fee: int,
    provider: str = PaymentProvider.STRIPE,
    reconciled_on: dt.date | None = None,
) -> Payment:
    """A succeeded payment of ``total`` cents that the provider took ``fee`` from."""
    return PaymentFactory(
        user=user,
        plan=plan,
        amount_cents=total,
        plan_amount_cents=total,
        contribution_cents=0,
        fee_cents=fee,
        net_cents=total - fee,
        provider=provider,
        provider_ref=f"rec-{provider}-{when:%Y%m%d}-{total}",
        status=PaymentStatus.SUCCEEDED,
        completed_at=when,
        created_at=when,
        reconciled_on=reconciled_on,
    )


@pytest.fixture
def books(member: User, annual_plan: MembershipPlan) -> list[Payment]:
    """Two months of settled payments across both real providers.

    January holds two Stripe payments, one of them already matched to a
    statement; February holds one PayPal payment that is not matched.
    """
    return [
        settled(
            member,
            annual_plan,
            when=at_noon(2026, 1, 5),
            total=10_000,
            fee=320,
            reconciled_on=dt.date(2026, 2, 1),
        ),
        settled(member, annual_plan, when=at_noon(2026, 1, 20), total=5_000, fee=175),
        settled(
            member,
            annual_plan,
            when=at_noon(2026, 2, 10),
            total=20_000,
            fee=747,
            provider=PaymentProvider.PAYPAL,
        ),
    ]


# --------------------------------------------------------------------------
# The table
# --------------------------------------------------------------------------
def test_the_table_answers_one_row_per_month(
    treasurer_client: APIClient, books: list[Payment]
) -> None:
    """Months are the default grouping, oldest first."""
    rows = treasurer_client.get(TABLE).json()
    assert [row["period"] for row in rows] == ["2026-01", "2026-02"]


def test_a_month_adds_up_the_gross_the_fees_and_the_net(
    treasurer_client: APIClient, books: list[Payment]
) -> None:
    """The three money columns are the sums of the month's payments."""
    january = treasurer_client.get(TABLE).json()[0]
    assert january["gross_cents"] == 15_000
    assert january["fee_cents"] == 495
    assert january["net_cents"] == 14_505


def test_a_month_counts_what_is_matched_and_what_is_not(
    treasurer_client: APIClient, books: list[Payment]
) -> None:
    """The two counts together are the month's payment count."""
    january = treasurer_client.get(TABLE).json()[0]
    assert january["reconciled_count"] == 1
    assert january["unreconciled_count"] == 1


def test_a_check_counts_in_the_month_it_was_received(
    treasurer_client: APIClient, books: list[Payment], member: User, annual_plan: MembershipPlan
) -> None:
    """A check received in January but keyed in February is January's deposit."""
    check = settled(
        member,
        annual_plan,
        when=at_noon(2026, 2, 20),
        total=3_000,
        fee=0,
        provider=PaymentProvider.MANUAL,
    )
    Payment.objects.filter(pk=check.pk).update(received_on=dt.date(2026, 1, 28))
    january = treasurer_client.get(TABLE).json()[0]
    assert january["gross_cents"] == 18_000


def test_a_refund_is_dated_by_the_day_it_was_taken(
    treasurer_client: APIClient, books: list[Payment]
) -> None:
    """A January payment refunded in February belongs to February here."""
    RefundFactory(payment=books[0], amount_cents=2_500, refunded_at=at_noon(2026, 2, 14))
    february = treasurer_client.get(TABLE).json()[1]
    assert february["refunded_cents"] == 2_500


def test_the_net_after_refunds_takes_the_refunds_off(
    treasurer_client: APIClient, books: list[Payment]
) -> None:
    """The last money column is the net less what went back in the same period."""
    RefundFactory(payment=books[2], amount_cents=1_000, refunded_at=at_noon(2026, 2, 20))
    february = treasurer_client.get(TABLE).json()[1]
    assert february["net_after_refunds_cents"] == 18_253


def test_a_period_with_only_a_refund_still_gets_a_row(
    treasurer_client: APIClient, books: list[Payment]
) -> None:
    """The statement has that line, so the table does too, with a zero count."""
    RefundFactory(payment=books[0], amount_cents=1_000, refunded_at=at_noon(2026, 3, 3))
    march = treasurer_client.get(TABLE).json()[2]
    assert march["period"] == "2026-03"
    assert march["count"] == 0
    assert march["refunded_cents"] == 1_000


def test_grouping_by_provider_answers_one_row_per_provider(
    treasurer_client: APIClient, books: list[Payment]
) -> None:
    """``?group=provider`` puts every period together and splits by who took the money."""
    rows = treasurer_client.get(TABLE, {"group": "provider"}).json()
    assert [row["period"] for row in rows] == ["stripe", "paypal"]


def test_the_provider_rows_add_up_to_the_same_gross_as_the_months(
    treasurer_client: APIClient, books: list[Payment]
) -> None:
    """The two groupings answer the same question, so their totals agree."""
    by_month = treasurer_client.get(TABLE).json()
    by_provider = treasurer_client.get(TABLE, {"group": "provider"}).json()
    assert sum(row["gross_cents"] for row in by_provider) == sum(
        row["gross_cents"] for row in by_month
    )


def test_the_range_narrows_the_table(treasurer_client: APIClient, books: list[Payment]) -> None:
    """``?from=`` and ``?to=`` bound the periods reported."""
    rows = treasurer_client.get(TABLE, {"from": "2026-02-01"}).json()
    assert [row["period"] for row in rows] == ["2026-02"]


def test_the_provider_filter_narrows_the_table(
    treasurer_client: APIClient, books: list[Payment]
) -> None:
    """``?provider=`` reports one provider's money alone."""
    rows = treasurer_client.get(TABLE, {"provider": "paypal"}).json()
    assert [row["gross_cents"] for row in rows] == [20_000]


def test_a_payment_that_never_arrived_is_not_on_the_statement(
    treasurer_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A failed attempt never reached the bank, so it is not reconciled against it."""
    PaymentFactory(
        user=member,
        plan=annual_plan,
        status=PaymentStatus.FAILED,
        completed_at=None,
        created_at=at_noon(2026, 1, 9),
    )
    assert treasurer_client.get(TABLE).json() == []


def test_an_unknown_grouping_is_refused(treasurer_client: APIClient) -> None:
    """The grouping is month, year or provider, and nothing else."""
    assert treasurer_client.get(TABLE, {"group": "week"}).json() == {
        "group": ["Expected 'month', 'year' or 'provider'."]
    }


def test_an_unknown_provider_is_refused(treasurer_client: APIClient) -> None:
    """A provider outside the choices is refused by name."""
    assert treasurer_client.get(TABLE, {"provider": "bitcoin"}).json() == {
        "provider": ["Unknown provider 'bitcoin'."]
    }


# --------------------------------------------------------------------------
# The exports
# --------------------------------------------------------------------------
def test_the_csv_export_is_named_for_the_day_it_was_run(
    treasurer_client: APIClient, books: list[Payment], today: dt.date
) -> None:
    """The filename carries the day the report was built, whatever range it covers."""
    response = treasurer_client.get(EXPORT_CSV, {"from": "2026-01-01", "to": "2026-02-28"})
    assert (
        response["Content-Disposition"]
        == f'attachment; filename="caldart-reconciliation-{today.isoformat()}.csv"'
    )


def test_the_csv_export_prints_the_nine_columns_of_the_table(
    treasurer_client: APIClient, books: list[Payment]
) -> None:
    """The header is the table's columns, in the table's order."""
    assert read_csv(treasurer_client.get(EXPORT_CSV))[0] == [
        "Period",
        "Payments",
        "Gross",
        "Fees",
        "Net",
        "Refunded",
        "Net after refunds",
        "Reconciled",
        "Unreconciled",
    ]


def test_the_csv_export_carries_the_same_rows_as_the_table(
    treasurer_client: APIClient, books: list[Payment]
) -> None:
    """One header line and one line per period."""
    rows = read_csv(treasurer_client.get(EXPORT_CSV))
    assert [row[0] for row in rows] == ["Period", "2026-01", "2026-02"]


def test_the_csv_export_writes_money_a_spreadsheet_can_add_up(
    treasurer_client: APIClient, books: list[Payment]
) -> None:
    """The cells are plain decimals, with no currency symbol."""
    rows = read_csv(treasurer_client.get(EXPORT_CSV))
    assert rows[1][2] == "150.00"


def test_the_pdf_export_is_named_for_the_day_it_was_run(
    treasurer_client: APIClient, books: list[Payment], today: dt.date
) -> None:
    """The PDF is an attachment under the same name as the CSV."""
    response = treasurer_client.get(EXPORT_PDF, {"from": "2026-01-01", "to": "2026-02-28"})
    assert (
        response["Content-Disposition"]
        == f'attachment; filename="caldart-reconciliation-{today.isoformat()}.pdf"'
    )


def test_the_pdf_export_names_the_range_under_its_title(
    treasurer_client: APIClient, books: list[Payment], pdf_text: PdfText
) -> None:
    """The subtitle carries the range, which the filename no longer does."""
    body = treasurer_client.get(EXPORT_PDF, {"from": "2026-01-01", "to": "2026-02-28"}).content
    assert pdf_text(body)[0][1] == "from: 2026-01-01 \u00b7 to: 2026-02-28"


def test_the_pdf_export_is_upright(treasurer_client: APIClient, books: list[Payment]) -> None:
    """Nine narrow columns fit portrait letter."""
    assert b"/MediaBox [ 0 0 612 792 ]" in treasurer_client.get(EXPORT_PDF).content


def test_the_pdf_export_draws_its_title_and_first_row(
    treasurer_client: APIClient, books: list[Payment], pdf_text: PdfText
) -> None:
    """The document a treasurer files reads as the table they saw."""
    page = pdf_text(treasurer_client.get(EXPORT_PDF).content)[0]
    assert "CalDART reconciliation" in page
    assert "2026-01" in page


def test_the_pdf_export_prints_money_with_its_currency(
    treasurer_client: APIClient, books: list[Payment], pdf_text: PdfText
) -> None:
    """A PDF is read by a person, so its cells carry the dollar sign."""
    page = pdf_text(treasurer_client.get(EXPORT_PDF).content)[0]
    assert "$150.00" in page


# --------------------------------------------------------------------------
# Role matrix
# --------------------------------------------------------------------------
@pytest.mark.parametrize("url", [TABLE])
@pytest.mark.parametrize(("slug", "allowed"), role_matrix(TREASURER, ACCOUNT_ADMIN, SYSTEM_ADMIN))
def test_reconciliation_is_for_the_finance_roles_only(
    api_client: APIClient,
    all_role_users: dict[str, User],
    url: str,
    slug: str,
    allowed: bool,
) -> None:
    """Only a treasurer, an account admin or a system admin reconciles."""
    api_client.force_login(all_role_users[slug])
    assert api_client.get(url).status_code == (200 if allowed else 403)


@pytest.mark.parametrize("url", [TABLE])
def test_reconciliation_rejects_anonymous_callers(api_client: APIClient, url: str) -> None:
    """An anonymous caller gets a 401 from every reconciliation endpoint."""
    assert api_client.get(url).status_code == 401
