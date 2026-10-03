"""A donor's record, reached from the donors report, and the delete it offers.

A donor is on no member list, so the donors report links each of its rows to the
member record at ``/admin/members/{user_id}``.  The record answers for a donor, and
``DELETE`` on it removes the donor as it removes any account: the gifts move to the
**Deleted member <id>** tombstone, and the donors report's totals for the year read
the same afterwards.  The report is the treasurer's and the record the account
administrator's, so the caller here holds both roles.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import AccountKind, User
from apps.accounts.roles import ACCOUNT_ADMIN, MEMBER, TREASURER
from apps.payments.models import Payment, PaymentStatus
from tests.factories import MemberProfileFactory, PaymentFactory, RefundFactory, UserFactory

pytestmark = pytest.mark.django_db

MEMBERS_URL = "/api/v1/admin/members"
DONORS_URL = "/api/v1/admin/payments/donors"
PAYMENTS_URL = "/api/v1/admin/payments"

#: The year every gift here falls in, and the donors report's range over it.
YEAR = 2025
YEAR_RANGE = {"from": f"{YEAR}-01-01", "to": f"{YEAR}-12-31"}

#: The donors report's money columns, whose sums are the year's totals.
TOTAL_KEYS = ("gifts", "given_cents", "refunded_cents", "net_cents")


def record_url(user: User) -> str:
    """The member record of ``user``, which answers for a donor too."""
    return f"{MEMBERS_URL}/{user.pk}"


def gift(user: User, *, cents: int, on: date) -> Payment:
    """A settled, contribution-only gift of ``cents`` from ``user``, paid on ``on``."""
    return PaymentFactory(
        user=user,
        plan=None,
        status=PaymentStatus.SUCCEEDED,
        contribution_cents=cents,
        plan_amount_cents=0,
        amount_cents=cents,
        completed_at=datetime(on.year, on.month, on.day, 12, 0, tzinfo=UTC),
    )


def year_totals(client: APIClient) -> dict[str, int]:
    """The donors report's columns summed over every row for :data:`YEAR`."""
    rows = client.get(DONORS_URL, YEAR_RANGE).json()
    return {key: sum(row[key] for row in rows) for key in TOTAL_KEYS}


@pytest.fixture
def finance_admin_client(api_client: APIClient) -> APIClient:
    """A client signed in as a treasurer who is also an account administrator."""
    admin = UserFactory(
        email="books-and-records@example.test", roles=[MEMBER, TREASURER, ACCOUNT_ADMIN]
    )
    api_client.force_login(admin)
    return api_client


@pytest.fixture
def donor(db: None) -> User:
    """Rosa Delgado, a donor with an address on file and two gifts in :data:`YEAR`."""
    user = UserFactory(
        email="rosa@example.test", first_name="Rosa", last_name="Delgado", kind=AccountKind.DONOR
    )
    MemberProfileFactory(user=user, address_line1="12 Vine Street", city="Napa", dart=None)
    gift(user, cents=10_000, on=date(YEAR, 3, 1))
    refunded = gift(user, cents=5_000, on=date(YEAR, 9, 15))
    RefundFactory(payment=refunded, amount_cents=2_000)
    return user


@pytest.fixture
def other_donor(db: None) -> User:
    """Gil Ortega, a second donor, so the year's totals cover more than one row."""
    user = UserFactory(
        email="gil@example.test", first_name="Gil", last_name="Ortega", kind=AccountKind.DONOR
    )
    gift(user, cents=2_500, on=date(YEAR, 6, 1))
    return user


# --------------------------------------------------------------------------
# Reaching the record
# --------------------------------------------------------------------------
def test_each_donors_report_row_names_the_account_its_record_opens(
    finance_admin_client: APIClient, donor: User
) -> None:
    """A row's ``user_id`` is the id the member record answers to."""
    [row] = finance_admin_client.get(DONORS_URL, YEAR_RANGE).json()

    assert row["user_id"] == donor.pk


def test_a_donors_record_reads_as_a_donor(finance_admin_client: APIClient, donor: User) -> None:
    """The record answers for a donor and says it is one."""
    assert finance_admin_client.get(record_url(donor)).json()["kind"] == "donor"


def test_a_donors_record_carries_the_address_that_identifies_them(
    finance_admin_client: APIClient, donor: User
) -> None:
    """The profile on the record holds the street and city the donor gave."""
    profile = finance_admin_client.get(record_url(donor)).json()["profile"]

    assert (profile["address_line1"], profile["city"]) == ("12 Vine Street", "Napa")


def test_a_donors_record_lists_every_gift(finance_admin_client: APIClient, donor: User) -> None:
    """The record's payments are the donor's gifts, so the administrator sees them."""
    payments = finance_admin_client.get(record_url(donor)).json()["payments"]

    assert sorted(payment["contribution_cents"] for payment in payments) == [5_000, 10_000]


# --------------------------------------------------------------------------
# Deleting through the record
# --------------------------------------------------------------------------
def test_deleting_a_donor_through_the_record_removes_the_account(
    finance_admin_client: APIClient, donor: User
) -> None:
    """The delete answers 204 and the donor's account is gone."""
    response = finance_admin_client.delete(record_url(donor))

    assert response.status_code == 204
    assert not User.objects.filter(pk=donor.pk).exists()


def test_a_deleted_donors_gifts_go_to_the_tombstone(
    finance_admin_client: APIClient, donor: User
) -> None:
    """Both gifts move to **Deleted member <id>**, refunds and all."""
    gift_ids = sorted(Payment.objects.filter(user=donor).values_list("pk", flat=True))
    target_id = donor.pk

    finance_admin_client.delete(record_url(donor))

    tombstone = User.objects.get(first_name="Deleted member", last_name=str(target_id))
    assert sorted(Payment.objects.filter(user=tombstone).values_list("pk", flat=True)) == gift_ids


def test_the_donors_report_lists_the_gifts_under_the_tombstone(
    finance_admin_client: APIClient, donor: User, other_donor: User
) -> None:
    """The deleted donor's row reads **Deleted member <id>** with the same giving."""
    target_id = donor.pk
    before = next(
        row
        for row in finance_admin_client.get(DONORS_URL, YEAR_RANGE).json()
        if row["user_id"] == target_id
    )

    finance_admin_client.delete(record_url(donor))

    after = next(
        row
        for row in finance_admin_client.get(DONORS_URL, YEAR_RANGE).json()
        if row["name"] == f"Deleted member {target_id}"
    )
    assert {key: after[key] for key in TOTAL_KEYS} == {key: before[key] for key in TOTAL_KEYS}


def test_the_donors_report_year_totals_are_unchanged_by_the_delete(
    finance_admin_client: APIClient, donor: User, other_donor: User
) -> None:
    """Gifts, given, refunded, and net summed over the year read exactly as before."""
    before = year_totals(finance_admin_client)

    finance_admin_client.delete(record_url(donor))

    assert year_totals(finance_admin_client) == before


def test_the_payment_list_names_the_tombstone_as_the_giver(
    finance_admin_client: APIClient, donor: User
) -> None:
    """Each of the donor's gifts reads **Deleted member <id>** on the payment list."""
    target_id = donor.pk

    finance_admin_client.delete(record_url(donor))

    rows = finance_admin_client.get(PAYMENTS_URL).json()["results"]
    assert [row["user_name"] for row in rows] == [f"Deleted member {target_id}"] * 2
