"""The report registry: the five reports, who may read each, and what each query does.

Every report's query is the filter and ordering code its JSON list runs, so the same
params narrow and order a download exactly as they narrow and order the screen.  The
tests below hold each report to its list by asking both the same question.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta

import pytest
from django.http import Http404
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import ACCOUNT_ADMIN, DART_LEADER, ROLE_SLUGS, SYSTEM_ADMIN, TREASURER
from apps.aircraft.models import Aircraft
from apps.aircraft.reports import AIRCRAFT_REPORT
from apps.darts.models import Dart
from apps.members.models import MembershipPlan
from apps.members.reports import MEMBER_REPORT, RowContext
from apps.payments.models import Payment, PaymentProvider, PaymentStatus
from apps.payments.reconciliation import RECONCILIATION_REPORT, ReconciliationRow
from apps.payments.reports import CONTRIBUTION_REPORT, PAYMENT_REPORT, ContributionRow
from apps.reports.permissions import can_read_report
from apps.reports.registry import REPORTS, report_or_404
from caldart.reports import Params, ReportSpec
from tests.conftest import RegisterDict
from tests.factories import DartFactory, MemberProfileFactory, PaymentFactory, UserFactory

pytestmark = pytest.mark.django_db

#: The day the dated tests below are run on.
DAY = date(2026, 9, 25)


# --------------------------------------------------------------------------
# The registry
# --------------------------------------------------------------------------
def test_the_registry_holds_the_five_reports_by_slug() -> None:
    """Members, aircraft, payments, reconciliation and contributions, each by its slug."""
    assert list(REPORTS) == ["members", "aircraft", "payments", "reconciliation", "contributions"]


@pytest.mark.parametrize(
    "slug", ["members", "aircraft", "payments", "reconciliation", "contributions"]
)
def test_each_report_is_filed_under_its_own_slug(slug: str) -> None:
    """The key a report is registered under is the slug it declares."""
    assert REPORTS[slug].slug == slug


def test_report_or_404_finds_a_registered_report() -> None:
    """A registered slug answers its spec."""
    assert report_or_404("aircraft") is AIRCRAFT_REPORT


def test_report_or_404_refuses_an_unknown_slug() -> None:
    """A slug the registry does not hold is a 404."""
    with pytest.raises(Http404, match=r"No report named 'karma'\."):
        report_or_404("karma")


@pytest.mark.parametrize(
    ("slug", "roles"),
    [
        ("members", (DART_LEADER, ACCOUNT_ADMIN)),
        ("aircraft", (ACCOUNT_ADMIN,)),
        ("payments", (TREASURER, ACCOUNT_ADMIN)),
        ("reconciliation", (TREASURER, ACCOUNT_ADMIN)),
        ("contributions", (TREASURER, ACCOUNT_ADMIN)),
    ],
)
def test_each_report_names_the_roles_that_may_read_it(slug: str, roles: tuple[str, ...]) -> None:
    """The members report is for leaders and administrators, the money for finance."""
    assert REPORTS[slug].roles == roles


@pytest.mark.parametrize(
    ("slug", "shape"),
    [
        ("members", (True, True, False)),
        ("aircraft", (True, True, False)),
        ("payments", (True, True, True)),
        ("reconciliation", (False, False, False)),
        ("contributions", (False, False, True)),
    ],
)
def test_each_report_declares_its_columns_orientation_and_periods(
    slug: str, shape: tuple[bool, bool, bool]
) -> None:
    """``(choosable, landscape, periods)``: the finance tables are fixed and upright."""
    spec = REPORTS[slug]
    assert (spec.choosable, spec.landscape, spec.periods) == shape


@pytest.mark.parametrize(
    ("slug", "title", "stem"),
    [
        ("members", "CalDART membership report", "caldart-members"),
        ("aircraft", "CalDART aircraft register", "caldart-aircraft"),
        ("payments", "CalDART payments", "caldart-payments"),
        ("reconciliation", "CalDART reconciliation", "caldart-reconciliation"),
        ("contributions", "CalDART contributions", "caldart-contributions"),
    ],
)
def test_each_report_carries_its_title_and_file_name(slug: str, title: str, stem: str) -> None:
    """The title heads the PDF and labels the report; the stem begins its file name."""
    spec = REPORTS[slug]
    assert (spec.title, spec.filename_stem) == (title, stem)


@pytest.mark.parametrize(
    ("slug", "allowed"),
    [
        ("members", {DART_LEADER, ACCOUNT_ADMIN, SYSTEM_ADMIN}),
        ("aircraft", {ACCOUNT_ADMIN, SYSTEM_ADMIN}),
        ("payments", {TREASURER, ACCOUNT_ADMIN, SYSTEM_ADMIN}),
        ("reconciliation", {TREASURER, ACCOUNT_ADMIN, SYSTEM_ADMIN}),
        ("contributions", {TREASURER, ACCOUNT_ADMIN, SYSTEM_ADMIN}),
    ],
)
def test_can_read_report_admits_the_report_roles_and_the_system_administrator(
    all_role_users: dict[str, User], slug: str, allowed: set[str]
) -> None:
    """Holding one of the spec's roles, or ``system_admin``, is what reading takes."""
    readers = {role for role in ROLE_SLUGS if can_read_report(all_role_users[role], REPORTS[slug])}
    assert readers == allowed


def test_a_superuser_may_read_every_report(superuser: User) -> None:
    """A Django superuser reads everything, whatever roles a spec names."""
    assert all(can_read_report(superuser, spec) for spec in REPORTS.values())


# --------------------------------------------------------------------------
# The same filters and ordering as the list
# --------------------------------------------------------------------------
def member_emails(params: Params) -> list[str]:
    """The addresses the members report lists for ``params``, in its order."""
    rows: list[RowContext] = list(MEMBER_REPORT.query(params).rows)
    return [row["user"].email for row in rows]


def list_emails(client: APIClient, url: str, params: Params) -> list[str]:
    """The addresses a JSON list answers for ``params``, in order, on one 200-row page."""
    body = client.get(url, {**params, "page_size": "200"}).json()
    return [row["email"] for row in body["results"]]


@pytest.fixture
def roster(annual_plan: MembershipPlan, dart: Dart) -> list[User]:
    """Five members in two DARTs, one of them with a lapsed membership."""
    napa = DartFactory(name="Napa", airport_identifiers="APC")
    people = [
        UserFactory(email=f"{first.lower()}@example.test", first_name=first, last_name=last)
        for first, last in [
            ("Ada", "Marsh"),
            ("Bo", "Nakano"),
            ("Cy", "Orr"),
            ("Di", "Abbot"),
            ("Ed", "Marsh"),
        ]
    ]
    for index, person in enumerate(people):
        MemberProfileFactory(user=person, dart=dart if index % 2 == 0 else napa)
    return people


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"dart": "Napa"},
        {"search": "Marsh"},
        {"ordering": "-email"},
        {"ordering": "dart"},
        {"ordering": "nonsense"},
        {"search": "example.test", "ordering": "-name"},
    ],
    ids=["everyone", "dart", "search", "email-descending", "dart-order", "bad-order", "combined"],
)
def test_the_members_report_lists_what_the_member_list_lists(
    account_admin_client: APIClient,
    fixed_name_admin: User,
    roster: list[User],
    params: dict[str, str],
) -> None:
    """The report's rows are the list's rows, in the list's order, for the same params."""
    expected = list_emails(account_admin_client, "/api/v1/admin/members", params)
    assert member_emails(params) == expected


def test_the_members_report_refuses_a_filter_the_list_refuses(roster: list[User]) -> None:
    """A status that is not a status is a validation error keyed by ``status``."""
    with pytest.raises(ValidationError) as caught:
        MEMBER_REPORT.query({"status": "sideways"})
    assert "status" in caught.value.get_full_details()


def test_the_members_report_names_the_filters_it_applied(roster: list[User]) -> None:
    """Only the filters supplied with a value are named, in the list's order."""
    query = MEMBER_REPORT.query({"search": "", "dart": "Napa", "ordering": "-name", "page": "2"})
    assert query.filters == {"dart": "Napa", "ordering": "-name"}


def n_numbers(rows: list[Aircraft]) -> list[str]:
    """The registrations of ``rows``, in order."""
    return [aircraft.n_number for aircraft in rows]


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"insurance": "expired"},
        {"owner_type": "club"},
        {"search": "cessna"},
        {"ordering": "-n_number"},
        {"ordering": "-insurance_expiration"},
        {"ordering": "karma"},
    ],
    ids=["everything", "expired", "owner", "search", "descending", "expiry", "bad-order"],
)
def test_the_aircraft_report_lists_what_the_register_lists(
    account_admin_client: APIClient, register: RegisterDict, params: dict[str, str]
) -> None:
    """The report's rows are the register's rows, in the register's order."""
    body = account_admin_client.get("/api/v1/aircraft", {**params, "page_size": "200"}).json()
    expected = [row["n_number"] for row in body["results"]]
    assert n_numbers(list(AIRCRAFT_REPORT.query(params).rows)) == expected


def test_the_aircraft_report_names_the_filters_it_applied(register: RegisterDict) -> None:
    """Every register filter supplied with a value is named for the subtitle."""
    query = AIRCRAFT_REPORT.query({"insurance": "expired", "make": "", "ordering": "make"})
    assert query.filters == {"insurance": "expired", "ordering": "make"}


@pytest.fixture
def ledger(annual_plan: MembershipPlan, today: date) -> list[Payment]:
    """Four payments over two providers and two statuses, a few days apart."""
    member = UserFactory(email="payer@example.test", first_name="Pat", last_name="Payer")
    return [
        PaymentFactory(
            user=member,
            plan=annual_plan,
            provider=provider,
            status=status,
            amount_cents=amount,
            plan_amount_cents=amount,
            received_on=today - timedelta(days=offset),
            provider_ref=f"ref-{offset}",
        )
        for offset, provider, status, amount in [
            (1, PaymentProvider.STRIPE, PaymentStatus.SUCCEEDED, 5000),
            (40, PaymentProvider.PAYPAL, PaymentStatus.SUCCEEDED, 7000),
            (400, PaymentProvider.STRIPE, PaymentStatus.FAILED, 6000),
            (3, PaymentProvider.PAYPAL, PaymentStatus.SUCCEEDED, 4000),
        ]
    ]


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"provider": "stripe"},
        {"status": "failed"},
        {"ordering": "amount_cents"},
        {"ordering": "-amount_cents", "provider": "paypal"},
    ],
    ids=["everything", "provider", "status", "amount", "combined"],
)
def test_the_payments_report_lists_what_the_payment_list_lists(
    treasurer_client: APIClient, ledger: list[Payment], params: dict[str, str]
) -> None:
    """The report's rows are the finance list's rows, in the same order."""
    body = treasurer_client.get("/api/v1/admin/payments", {**params, "page_size": "200"}).json()
    expected = [row["id"] for row in body["results"]]
    rows: list[Payment] = list(PAYMENT_REPORT.query(params).rows)
    assert [payment.pk for payment in rows] == expected


def test_the_payments_report_refuses_an_ordering_the_list_refuses(ledger: list[Payment]) -> None:
    """A field the list cannot order by is refused, keyed by ``ordering``."""
    with pytest.raises(ValidationError, match=r"Cannot order by 'karma'\."):
        PAYMENT_REPORT.query({"ordering": "karma"})


def test_the_payments_report_names_the_filters_it_applied(ledger: list[Payment]) -> None:
    """The filters supplied with a value are named, the range and ordering included."""
    query = PAYMENT_REPORT.query(
        {"provider": "stripe", "status": "", "from": "2026-01-01", "ordering": "-amount_cents"}
    )
    assert query.filters == {
        "from": "2026-01-01",
        "provider": "stripe",
        "ordering": "-amount_cents",
    }


def test_the_reconciliation_report_answers_the_rows_the_table_answers(
    treasurer_client: APIClient, ledger: list[Payment]
) -> None:
    """Grouped by provider, the report and the table agree row for row."""
    params = {"group": "provider"}
    expected = treasurer_client.get("/api/v1/admin/payments/reconciliation", params).json()
    rows: list[ReconciliationRow] = list(RECONCILIATION_REPORT.query(params).rows)
    assert [dict(row) for row in rows] == expected


def test_the_contributions_report_answers_the_rows_the_list_answers(
    treasurer_client: APIClient, annual_plan: MembershipPlan, today: date
) -> None:
    """For one year, the report and the contributions list agree row for row."""
    giver = UserFactory(email="giver@example.test", first_name="Gil", last_name="Giver")
    PaymentFactory(
        user=giver,
        plan=None,
        status=PaymentStatus.SUCCEEDED,
        contribution_cents=2500,
        plan_amount_cents=0,
        amount_cents=2500,
    )
    params = {"year": str(today.year)}
    expected = treasurer_client.get("/api/v1/admin/payments/contributions", params).json()
    rows: list[ContributionRow] = list(CONTRIBUTION_REPORT.query(params).rows)
    assert [dict(row) for row in rows] == expected


def test_the_contributions_report_names_the_year_even_by_default(today: date) -> None:
    """The year is always named, since the report's title does not carry it."""
    assert CONTRIBUTION_REPORT.query({}).filters == {"year": str(today.year)}


# --------------------------------------------------------------------------
# Periods
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("spec", "period", "expected"),
    [
        (PAYMENT_REPORT, "last_month", {"from": "2026-08-01", "to": "2026-08-31"}),
        (PAYMENT_REPORT, "this_year", {"from": "2026-01-01", "to": "2026-12-31"}),
        (CONTRIBUTION_REPORT, "last_year", {"year": "2025"}),
        (CONTRIBUTION_REPORT, "this_month", {"year": "2026"}),
    ],
    ids=[
        "payments-last-month",
        "payments-this-year",
        "contributions-last-year",
        "contributions-now",
    ],
)
def test_a_dated_report_resolves_a_period_into_its_own_params(
    spec: ReportSpec[Payment] | ReportSpec[ContributionRow], period: str, expected: dict[str, str]
) -> None:
    """Payments take a date range and contributions a year; ``period`` is dropped."""
    assert spec.resolve({"period": period, "columns": "total"}, DAY) == {
        "columns": "total",
        **expected,
    }


@pytest.mark.parametrize(
    "resolve",
    [MEMBER_REPORT.resolve, AIRCRAFT_REPORT.resolve, RECONCILIATION_REPORT.resolve],
    ids=["members", "aircraft", "reconciliation"],
)
def test_every_other_report_ignores_a_period(resolve: Callable[[Params, date], Params]) -> None:
    """A report without a period takes its params as they come."""
    params = {"period": "last_year", "dart": "3"}
    assert resolve(params, DAY) == params
