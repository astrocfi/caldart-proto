"""A donor's record, reached from the donors report, and the delete it offers.

A donor is on no member list, so the donors report links each of its rows to the
member record at ``/admin/members/{user_id}``.  The record answers for a donor, and
``DELETE`` on it removes the donor as it removes any account: the gifts move to the
**Deleted member <id>** tombstone, and the donors report's totals for the year read
the same afterwards.  The record refuses a donor a membership term granted by hand.
The report is the treasurer's and the record the account administrator's, so the
caller here holds both roles.
"""

from __future__ import annotations

from datetime import date

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import AccountKind, User
from apps.accounts.roles import ACCOUNT_ADMIN, MEMBER, TREASURER
from apps.members.models import Membership, MembershipPlan
from apps.payments.models import Payment
from tests.conftest import RecordedEvents, audit_messages
from tests.factories import MemberProfileFactory, RefundFactory, UserFactory, settled_gift

pytestmark = pytest.mark.django_db

MEMBERS_URL = "/api/v1/admin/members"
DONORS_URL = "/api/v1/admin/payments/donors"

#: The year every gift here falls in, and the donors report's range over it.
YEAR = 2025
YEAR_RANGE = {"from": f"{YEAR}-01-01", "to": f"{YEAR}-12-31"}

#: The donors report's money columns, whose sums are the year's totals.
TOTAL_KEYS = ("gifts", "given_cents", "refunded_cents", "net_cents")

#: What a grant to a donor answers with.
DONOR_GRANT_REFUSED = "A donor holds no membership, and becomes a member only by registering."


def _record_url(user: User) -> str:
    """The member record of ``user``, which answers for a donor too."""
    return f"{MEMBERS_URL}/{user.pk}"


def _year_totals(client: APIClient) -> dict[str, int]:
    """The donors report's columns summed over every row for :data:`YEAR`."""
    rows = client.get(DONORS_URL, YEAR_RANGE).json()
    return {key: sum(row[key] for row in rows) for key in TOTAL_KEYS}


def _report_row(client: APIClient, name: str) -> dict[str, int]:
    """The money columns of the donors report's row named ``name`` for :data:`YEAR`."""
    row = next(row for row in client.get(DONORS_URL, YEAR_RANGE).json() if row["name"] == name)
    return {key: row[key] for key in TOTAL_KEYS}


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
    settled_gift(user, cents=10_000, on=date(YEAR, 3, 1))
    refunded = settled_gift(user, cents=5_000, on=date(YEAR, 9, 15))
    RefundFactory(payment=refunded, amount_cents=2_000)
    return user


@pytest.fixture
def other_donor(db: None) -> User:
    """Gil Ortega, a second donor, so the year's totals cover more than one row."""
    user = UserFactory(
        email="gil@example.test", first_name="Gil", last_name="Ortega", kind=AccountKind.DONOR
    )
    settled_gift(user, cents=2_500, on=date(YEAR, 6, 1))
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


def test_a_donors_row_is_not_a_tombstone(finance_admin_client: APIClient, donor: User) -> None:
    """A living donor's row carries ``is_tombstone`` false, so the screen links it."""
    [row] = finance_admin_client.get(DONORS_URL, YEAR_RANGE).json()

    assert row["is_tombstone"] is False


def test_a_donors_record_reads_as_a_donor(finance_admin_client: APIClient, donor: User) -> None:
    """The record answers for a donor and says it is one."""
    assert finance_admin_client.get(_record_url(donor)).json()["kind"] == "donor"


def test_a_donors_record_carries_the_street_that_identifies_them(
    finance_admin_client: APIClient, donor: User
) -> None:
    """The profile on the record holds the street the donor gave."""
    profile = finance_admin_client.get(_record_url(donor)).json()["profile"]

    assert profile["address_line1"] == "12 Vine Street"


def test_a_donors_record_carries_the_city_that_identifies_them(
    finance_admin_client: APIClient, donor: User
) -> None:
    """The profile on the record holds the city the donor gave."""
    profile = finance_admin_client.get(_record_url(donor)).json()["profile"]

    assert profile["city"] == "Napa"


def test_a_donors_record_lists_every_gift(finance_admin_client: APIClient, donor: User) -> None:
    """The record's payments are the donor's gifts, so the administrator sees them."""
    payments = finance_admin_client.get(_record_url(donor)).json()["payments"]

    assert sorted(payment["contribution_cents"] for payment in payments) == [5_000, 10_000]


# --------------------------------------------------------------------------
# Deleting through the record
# --------------------------------------------------------------------------
def test_a_deleted_donors_gifts_go_to_the_tombstone(
    finance_admin_client: APIClient, donor: User
) -> None:
    """Both gifts move to **Deleted member <id>**, refunds and all."""
    gift_ids = sorted(Payment.objects.filter(user=donor).values_list("pk", flat=True))
    target_id = donor.pk

    finance_admin_client.delete(_record_url(donor))

    tombstone = User.objects.get(first_name="Deleted member", last_name=str(target_id))
    assert sorted(Payment.objects.filter(user=tombstone).values_list("pk", flat=True)) == gift_ids


def test_the_donors_report_lists_the_gifts_under_the_tombstone(
    finance_admin_client: APIClient, donor: User, other_donor: User
) -> None:
    """The deleted donor's row reads **Deleted member <id>** with the same giving."""
    target_id = donor.pk
    before = _report_row(finance_admin_client, "Rosa Delgado")

    finance_admin_client.delete(_record_url(donor))

    assert _report_row(finance_admin_client, f"Deleted member {target_id}") == before


def test_the_donors_report_year_totals_are_unchanged_by_the_delete(
    finance_admin_client: APIClient, donor: User, other_donor: User
) -> None:
    """Gifts, given, refunded, and net summed over the year read exactly as before."""
    before = _year_totals(finance_admin_client)

    finance_admin_client.delete(_record_url(donor))

    assert _year_totals(finance_admin_client) == before


# --------------------------------------------------------------------------
# No membership for a donor
# --------------------------------------------------------------------------
def test_granting_a_donor_a_term_is_refused(
    finance_admin_client: APIClient, donor: User, annual_plan: MembershipPlan
) -> None:
    """A grant to a donor is a 400 carrying the reason."""
    response = finance_admin_client.post(
        f"{_record_url(donor)}/memberships", {"plan": annual_plan.slug}, format="json"
    )

    assert (response.status_code, response.json()) == (400, {"detail": DONOR_GRANT_REFUSED})


def test_a_refused_grant_writes_no_term(
    finance_admin_client: APIClient, donor: User, annual_plan: MembershipPlan
) -> None:
    """The donor holds no term after the refusal."""
    finance_admin_client.post(
        f"{_record_url(donor)}/memberships", {"plan": annual_plan.slug}, format="json"
    )

    assert not Membership.objects.filter(user=donor).exists()


def test_a_refused_grant_raises_no_event(
    finance_admin_client: APIClient,
    donor: User,
    annual_plan: MembershipPlan,
    recorded_events: RecordedEvents,
) -> None:
    """Nobody hears of a membership the donor was never granted."""
    finance_admin_client.post(
        f"{_record_url(donor)}/memberships", {"plan": annual_plan.slug}, format="json"
    )

    assert [name for name, _ in recorded_events] == []


def test_a_refused_grant_is_audited_with_its_reason(
    finance_admin_client: APIClient,
    donor: User,
    annual_plan: MembershipPlan,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """The refusal is a ``membership.grant`` line ending in ``reason=donor_account``."""
    finance_admin_client.post(
        f"{_record_url(donor)}/memberships", {"plan": annual_plan.slug}, format="json"
    )

    [line] = [line for line in audit_messages(audit_log) if "membership.grant" in line]
    assert line.endswith("reason=donor_account")
