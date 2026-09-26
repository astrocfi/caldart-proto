"""The finance payment list, the period summary and the payments report.

The role matrix, the filters, the arithmetic over a fixture spanning three
months and two years, and the column registry that drives both formats of the
report and the screen's column chooser.
"""

from __future__ import annotations

import datetime as dt

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import ACCOUNT_ADMIN, SYSTEM_ADMIN, TREASURER
from apps.members.models import MembershipPlan
from apps.payments.models import (
    Payment,
    PaymentProvider,
    PaymentStatus,
    PaymentWallet,
    RenewalOutcome,
)
from tests.conftest import Golden, PdfText, csv_body, read_csv, role_matrix
from tests.factories import (
    MembershipFactory,
    PaymentFactory,
    RefundFactory,
    RenewalAttemptFactory,
    RenewalMandateFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db

LIST = "/api/v1/admin/payments"
SUMMARY = "/api/v1/admin/payments/summary"
EXPORT = "/api/v1/reports/payments/export.csv"
EXPORT_PDF = "/api/v1/reports/payments/export.pdf"
COLUMNS = "/api/v1/reports/payments/columns"

#: The header the export prints when the caller chooses no columns.
DEFAULT_HEADER = [
    "Date",
    "Name",
    "Email",
    "Plan",
    "Kind",
    "Dues",
    "Contribution",
    "Total",
    "Fee",
    "Net",
    "Refunded",
    "Provider",
    "Method",
    "Status",
    "Reference",
    "Reconciled",
]


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
    fee_cents: int = 0,
) -> Payment:
    """Create a completed (or not) payment backdated to ``when``.

    ``fee_cents`` is what the provider kept; the net is the rest of the total.
    """
    total = plan_cents + contribution_cents
    return PaymentFactory(
        user=user,
        plan=plan,
        amount_cents=total,
        plan_amount_cents=plan_cents,
        contribution_cents=contribution_cents,
        fee_cents=fee_cents,
        net_cents=total - fee_cents,
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
        make_payment(member, annual_plan, when=paid_at(2025, 11, 3), fee_cents=161),
        make_payment(
            other, annual_plan, when=paid_at(2025, 11, 20), provider=PaymentProvider.PAYPAL
        ),
        make_payment(
            member,
            annual_plan,
            when=paid_at(2026, 1, 8),
            contribution_cents=10_000,
            fee_cents=450,
        ),
        make_payment(
            other,
            annual_plan,
            when=paid_at(2026, 1, 25),
            provider=PaymentProvider.PAYPAL,
            contribution_cents=2_000,
        ),
        make_payment(member, annual_plan, when=paid_at(2026, 2, 2)),
        # Neither of these is revenue, so the summary must skip both.  Their
        # references are spelled out in full so that no cell of the export can
        # hold one as a substring: the golden comparison replaces them literally.
        make_payment(
            other,
            annual_plan,
            when=paid_at(2026, 2, 3),
            status=PaymentStatus.FAILED,
            ref="ref-dud-0001",
        ),
        make_payment(
            member,
            annual_plan,
            when=paid_at(2026, 2, 4),
            status=PaymentStatus.PENDING,
            ref="ref-wip-0001",
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
    assert api_client.get(LIST, {"search": "ref-dud-0001"}).json()["count"] == 1


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


@pytest.mark.parametrize("ordering", ["user__password", "--paid_at", "-"])
def test_list_rejects_a_bad_ordering_field(
    api_client: APIClient, account_admin: User, history: list[Payment], ordering: str
) -> None:
    """Ordering by anything outside the allowed set is refused, not a 500."""
    api_client.force_login(account_admin)
    assert api_client.get(LIST, {"ordering": ordering}).status_code == 400


def test_list_dates_a_recorded_payment_by_the_day_it_was_received(
    treasurer_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A check keyed in during March but received in February filters as February."""
    payment = make_payment(
        member, annual_plan, when=paid_at(2026, 3, 9), provider=PaymentProvider.MANUAL
    )
    Payment.objects.filter(pk=payment.pk).update(received_on=dt.date(2026, 2, 27))
    body = treasurer_client.get(LIST, {"from": "2026-02-01", "to": "2026-02-28"}).json()
    assert [row["id"] for row in body["results"]] == [payment.pk]


def test_list_runs_the_same_queries_however_many_payments_it_holds(
    treasurer_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """Serializing one more payment, renewal attempt and all, costs no more queries."""
    mandate = RenewalMandateFactory(user=member)
    first = make_payment(member, annual_plan, when=paid_at(2026, 2, 2))
    RenewalAttemptFactory(mandate=mandate, payment=first, outcome=RenewalOutcome.SUCCEEDED)
    with CaptureQueriesContext(connection) as one_row:
        assert treasurer_client.get(LIST).status_code == 200

    second = make_payment(member, annual_plan, when=paid_at(2026, 2, 3))
    RenewalAttemptFactory(mandate=mandate, payment=second, outcome=RenewalOutcome.SUCCEEDED)
    with CaptureQueriesContext(connection) as two_rows:
        assert treasurer_client.get(LIST).status_code == 200

    assert len(two_rows) == len(one_row)


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
# The payments report columns
# --------------------------------------------------------------------------
def test_the_column_registry_lists_every_export_column(
    treasurer_client: APIClient,
) -> None:
    """The chooser is data-driven: one entry per column, in export order."""
    rows = treasurer_client.get(COLUMNS).json()
    assert [row["key"] for row in rows] == [
        "paid_on",
        "receipt_number",
        "name",
        "email",
        "plan",
        "kind",
        "plan_amount",
        "contribution",
        "total",
        "fee",
        "net",
        "refunded",
        "provider",
        "wallet",
        "status",
        "provider_ref",
        "received_on",
        "reconciled_on",
        "note",
        "membership_starts",
        "membership_ends",
    ]


def test_the_columns_that_are_off_by_default_are_named(treasurer_client: APIClient) -> None:
    """Five columns are for an audit rather than the everyday list."""
    rows = treasurer_client.get(COLUMNS).json()
    assert [row["key"] for row in rows if not row["default"]] == [
        "receipt_number",
        "received_on",
        "note",
        "membership_starts",
        "membership_ends",
    ]


def test_every_column_carries_the_label_the_exports_print(
    treasurer_client: APIClient,
) -> None:
    """The label is the header text, not the key."""
    rows = treasurer_client.get(COLUMNS).json()
    assert [row["label"] for row in rows if row["default"]] == DEFAULT_HEADER


# --------------------------------------------------------------------------
# The payments report as CSV
# --------------------------------------------------------------------------
def test_export_returns_a_csv_download_named_for_today(
    treasurer_client: APIClient, history: list[Payment], today: dt.date
) -> None:
    """The export is a dated, downloadable CSV with the seven history rows."""
    response = treasurer_client.get(EXPORT)

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    assert (
        response["Content-Disposition"]
        == f'attachment; filename="caldart-payments-{today.isoformat()}.csv"'
    )
    assert len(read_csv(response)) == 8  # header + 7 payments


def test_export_prints_the_default_columns_when_none_are_chosen(
    treasurer_client: APIClient, history: list[Payment]
) -> None:
    """With no ``columns`` parameter the export carries the default sixteen."""
    assert read_csv(treasurer_client.get(EXPORT))[0] == DEFAULT_HEADER


def test_export_carries_the_chosen_columns_in_the_order_asked_for(
    treasurer_client: APIClient, history: list[Payment]
) -> None:
    """``?columns=`` decides both which columns appear and where."""
    rows = read_csv(treasurer_client.get(EXPORT, {"columns": "total,email"}))
    assert rows[0] == ["Total", "Email"]


def test_export_refuses_a_column_no_report_carries(
    treasurer_client: APIClient, history: list[Payment]
) -> None:
    """An unknown column key is a 400 keyed by ``columns``."""
    response = treasurer_client.get(EXPORT, {"columns": "total,karma"})
    assert response.json() == {"columns": ["Unknown column: karma"]}


def test_export_honors_the_filters(treasurer_client: APIClient, history: list[Payment]) -> None:
    """The export applies the same provider and status filters as the list."""
    rows = read_csv(treasurer_client.get(EXPORT, {"provider": "paypal", "status": "succeeded"}))
    assert len(rows) == 3


def test_export_honors_the_ordering(treasurer_client: APIClient, history: list[Payment]) -> None:
    """``?ordering=`` reorders the export rows, not only the list."""
    rows = read_csv(treasurer_client.get(EXPORT, {"columns": "total", "ordering": "amount_cents"}))
    totals = [float(row[0]) for row in rows[1:]]
    assert totals == sorted(totals)


def test_export_matches_the_recorded_document(
    treasurer_client: APIClient,
    member: User,
    history: list[Payment],
    golden: Golden,
) -> None:
    """The whole export -- header, every row, every column -- matches its record."""
    body = csv_body(treasurer_client.get(EXPORT))

    # The fixture's names come from Faker and its references carry row ids, so
    # both are replaced by fixed stand-ins before the documents are compared.
    replace = {payment.provider_ref: f"ref-{index}" for index, payment in enumerate(history, 1)}
    replace[f"{member.first_name} {member.last_name}"] = "Fran Member"
    golden("payments-export.csv", body, replace=replace)


def test_export_formats_money_as_dollars(
    treasurer_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The export formats cent amounts as two-decimal dollar strings."""
    make_payment(
        member, annual_plan, when=paid_at(2026, 3, 9), contribution_cents=10_000, fee_cents=450
    )
    row = read_csv(treasurer_client.get(EXPORT))[1]

    assert row[0] == "2026-03-09"
    assert row[5] == "45.00"  # dues
    assert row[6] == "100.00"  # contribution
    assert row[7] == "145.00"  # total
    assert row[8] == "4.50"  # fee
    assert row[9] == "140.50"  # net


def test_export_leaves_the_date_blank_for_a_payment_that_never_arrived(
    treasurer_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A failed attempt has no ledger date, so its date cell is empty."""
    make_payment(member, annual_plan, when=paid_at(2026, 3, 9), status=PaymentStatus.FAILED)
    assert read_csv(treasurer_client.get(EXPORT))[1][0] == ""


def test_export_dates_a_recorded_payment_by_the_day_it_was_received(
    treasurer_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A check is dated the day it arrived, not the day it was keyed in."""
    payment = make_payment(
        member, annual_plan, when=paid_at(2026, 3, 9), provider=PaymentProvider.MANUAL
    )
    Payment.objects.filter(pk=payment.pk).update(received_on=dt.date(2026, 2, 27))
    assert read_csv(treasurer_client.get(EXPORT))[1][0] == "2026-02-27"


def test_the_summary_counts_a_recorded_payment_in_the_month_it_arrived(
    treasurer_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A check received in February is February's money, whenever it was keyed in."""
    payment = make_payment(
        member, annual_plan, when=paid_at(2026, 3, 9), provider=PaymentProvider.MANUAL
    )
    Payment.objects.filter(pk=payment.pk).update(received_on=dt.date(2026, 2, 27))
    periods = [row["period"] for row in treasurer_client.get(SUMMARY).json()]
    assert periods == ["2026-02"]


# --------------------------------------------------------------------------
# The payments report as PDF
# --------------------------------------------------------------------------
def test_pdf_export_returns_a_dated_pdf_download(
    treasurer_client: APIClient, history: list[Payment], today: dt.date
) -> None:
    """The PDF export is an attachment named for the day it was run."""
    response = treasurer_client.get(EXPORT_PDF)

    assert response["Content-Type"] == "application/pdf"
    assert (
        response["Content-Disposition"]
        == f'attachment; filename="caldart-payments-{today.isoformat()}.pdf"'
    )


def test_pdf_export_names_the_filters_in_its_subtitle(
    treasurer_client: APIClient, history: list[Payment], pdf_text: PdfText
) -> None:
    """The subtitle under the title says which filters produced the table."""
    response = treasurer_client.get(EXPORT_PDF, {"provider": "paypal"})
    assert "provider: paypal" in " ".join(pdf_text(response.content)[0])


def test_pdf_export_carries_the_chosen_columns(
    treasurer_client: APIClient, history: list[Payment], pdf_text: PdfText
) -> None:
    """``?columns=`` drives the PDF exactly as it drives the CSV."""
    response = treasurer_client.get(EXPORT_PDF, {"columns": "email"})
    page = pdf_text(response.content)[0]
    assert "Email" in page


# --------------------------------------------------------------------------
# Fees, net and refunds
# --------------------------------------------------------------------------
def test_summary_reports_the_fees_and_the_net(
    treasurer_client: APIClient, history: list[Payment]
) -> None:
    """Each period carries what the providers kept and what reached the bank."""
    january = next(
        row for row in treasurer_client.get(SUMMARY).json() if row["period"] == "2026-01"
    )
    assert january["fee_cents"] == 450
    assert january["net_cents"] == 20_550


def test_summary_reports_what_went_back(
    treasurer_client: APIClient, history: list[Payment]
) -> None:
    """A succeeded refund is reported against the period the payment arrived in."""
    RefundFactory(payment=history[2], amount_cents=2_500)
    january = next(
        row for row in treasurer_client.get(SUMMARY).json() if row["period"] == "2026-01"
    )
    assert january["refunded_cents"] == 2_500


def test_a_refunded_payment_still_counts_as_money_that_arrived(
    treasurer_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A refunded payment is revenue that came and went, not revenue that never came."""
    make_payment(member, annual_plan, when=paid_at(2026, 4, 2), status=PaymentStatus.REFUNDED)
    assert treasurer_client.get(SUMMARY).json()[0]["count"] == 1


# --------------------------------------------------------------------------
# The wider filters
# --------------------------------------------------------------------------
def test_list_filters_by_plan_slug(
    treasurer_client: APIClient, history: list[Payment], member: User, life_plan: MembershipPlan
) -> None:
    """``?plan=`` narrows to the payments that bought one plan."""
    make_payment(member, life_plan, when=paid_at(2026, 3, 1))
    assert treasurer_client.get(LIST, {"plan": "life"}).json()["count"] == 1


def test_list_filters_by_kind(treasurer_client: APIClient, history: list[Payment]) -> None:
    """``?kind=both`` finds the payments that bought a term and gave as well."""
    assert treasurer_client.get(LIST, {"kind": "both"}).json()["count"] == 2


def test_list_filters_by_member(
    treasurer_client: APIClient, history: list[Payment], member: User
) -> None:
    """``?member=`` narrows to one member's payments."""
    assert treasurer_client.get(LIST, {"member": member.pk}).json()["count"] == 4


def test_list_filters_by_amount_range(treasurer_client: APIClient, history: list[Payment]) -> None:
    """``?min_cents=`` and ``?max_cents=`` bound the total."""
    assert treasurer_client.get(LIST, {"min_cents": 6_000}).json()["count"] == 2


def test_list_filters_by_wallet(
    treasurer_client: APIClient, history: list[Payment], member: User, annual_plan: MembershipPlan
) -> None:
    """``?wallet=`` narrows to how the money was presented."""
    payment = make_payment(member, annual_plan, when=paid_at(2026, 3, 4))
    Payment.objects.filter(pk=payment.pk).update(wallet=PaymentWallet.CHECK)
    assert treasurer_client.get(LIST, {"wallet": "check"}).json()["count"] == 1


def test_list_filters_to_the_payments_still_to_be_matched(
    treasurer_client: APIClient, history: list[Payment]
) -> None:
    """``?reconciled=no`` is how a treasurer finds what is left to do."""
    Payment.objects.filter(pk=history[0].pk).update(reconciled_on=dt.date(2026, 3, 1))
    assert treasurer_client.get(LIST, {"reconciled": "no"}).json()["count"] == 6


def test_list_filters_to_the_payments_already_matched(
    treasurer_client: APIClient, history: list[Payment]
) -> None:
    """``?reconciled=yes`` is the other half of the same question."""
    Payment.objects.filter(pk=history[0].pk).update(reconciled_on=dt.date(2026, 3, 1))
    assert treasurer_client.get(LIST, {"reconciled": "yes"}).json()["count"] == 1


def test_list_orders_by_the_net_amount(treasurer_client: APIClient, history: list[Payment]) -> None:
    """The net the provider handed over is an ordering field of its own."""
    rows = treasurer_client.get(LIST, {"ordering": "-net_cents"}).json()["results"]
    assert [row["net_cents"] for row in rows] == sorted(
        (row["net_cents"] for row in rows), reverse=True
    )


def test_a_row_carries_the_term_it_bought(
    treasurer_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The finance row names the membership term the payment paid for."""
    payment = make_payment(member, annual_plan, when=paid_at(2026, 3, 9))
    MembershipFactory(user=member, plan=annual_plan, payment=payment)
    row = treasurer_client.get(LIST).json()["results"][0]
    assert row["membership"]["starts_on"] == timezone.localdate().isoformat()


def test_a_row_never_carries_the_provider_payload(
    treasurer_client: APIClient, history: list[Payment]
) -> None:
    """``raw`` is the provider's own payload and stays out of the API."""
    assert "raw" not in treasurer_client.get(LIST).json()["results"][0]


# --------------------------------------------------------------------------
# Role matrix
# --------------------------------------------------------------------------
@pytest.mark.parametrize("url", [LIST, SUMMARY, COLUMNS, EXPORT, EXPORT_PDF])
@pytest.mark.parametrize(("slug", "allowed"), role_matrix(TREASURER, ACCOUNT_ADMIN, SYSTEM_ADMIN))
def test_reports_are_for_the_finance_roles_only(
    api_client: APIClient,
    all_role_users: dict[str, User],
    history: list[Payment],
    url: str,
    slug: str,
    allowed: bool,
) -> None:
    """Only a treasurer, an account admin or a system admin views the reports."""
    api_client.force_login(all_role_users[slug])
    assert api_client.get(url).status_code == (200 if allowed else 403)


@pytest.mark.parametrize("url", [LIST, SUMMARY, COLUMNS, EXPORT, EXPORT_PDF])
def test_reports_reject_anonymous_callers(api_client: APIClient, url: str) -> None:
    """An anonymous caller gets a 401 from every report endpoint."""
    assert api_client.get(url).status_code == 401
