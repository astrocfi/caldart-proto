"""The two endpoints the finance screens ask for and nothing else does.

``POST /admin/payments/{id}/fees`` is the detail screen's "Fetch fee from
provider" button, and ``GET /admin/payments/members`` is the live member search
behind the form that records a payment taken by hand.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import ACCOUNT_ADMIN, SYSTEM_ADMIN, TREASURER
from apps.members.models import MembershipPlan
from apps.payments.manual import record_manual_payment
from apps.payments.models import Payment, PaymentStatus, PaymentWallet
from apps.payments.providers.base import PaymentError
from apps.payments.providers.mock import MockProvider
from tests.conftest import role_matrix
from tests.factories import MembershipFactory, PaymentFactory, UserFactory

pytestmark = pytest.mark.django_db

MEMBER_SEARCH = "/api/v1/admin/payments/members"


def fees_url(payment: Payment) -> str:
    """The fee-refresh endpoint of one payment."""
    return f"/api/v1/admin/payments/{payment.pk}/fees"


@pytest.fixture
def settled_payment(member: User) -> Payment:
    """A succeeded mock payment whose fee nobody has recorded yet."""
    return PaymentFactory(
        user=member,
        amount_cents=10_000,
        plan_amount_cents=10_000,
        status=PaymentStatus.SUCCEEDED,
        completed_at=dt.datetime.now(tz=dt.UTC),
        fee_cents=0,
        net_cents=0,
    )


# -- POST /admin/payments/{id}/fees ---------------------------------------
def test_fetching_a_fee_records_what_the_provider_reports(
    treasurer_client: APIClient, settled_payment: Payment
) -> None:
    """The mock provider's Stripe-shaped fee, and the net it leaves, land on the row."""
    response = treasurer_client.post(fees_url(settled_payment))

    assert response.json()["fee_cents"] == 320
    assert response.json()["net_cents"] == 9_680


def test_the_fee_answer_is_the_whole_finance_row(
    treasurer_client: APIClient, settled_payment: Payment
) -> None:
    """The screen redraws from the answer, so it carries the refunds too."""
    response = treasurer_client.post(fees_url(settled_payment))

    assert response.json()["refunds"] == []


def test_a_payment_recorded_by_hand_is_refused(
    treasurer_client: APIClient, member: User, treasurer: User
) -> None:
    """A check has no provider to ask, so the button is a 400 rather than a zero fee."""
    manual = record_manual_payment(
        user=member,
        plan_slug=None,
        contribution_cents=4_500,
        method=PaymentWallet.CHECK,
        reference="1182",
        received_on=timezone.localdate(),
        note="",
        actor=treasurer,
    )

    response = treasurer_client.post(fees_url(manual))

    assert response.status_code == 400
    assert response.json()["detail"] == "The provider has no fee to report for this payment yet."


def test_a_payment_that_never_succeeded_is_refused(
    treasurer_client: APIClient, member: User
) -> None:
    """A pending payment has nothing to price, so the button is a 400."""
    pending = PaymentFactory(
        user=member,
        amount_cents=4_500,
        plan_amount_cents=4_500,
        status=PaymentStatus.PENDING,
        fee_cents=0,
        net_cents=0,
    )

    response = treasurer_client.post(fees_url(pending))

    assert response.status_code == 400
    assert response.json()["detail"] == "The provider has no fee to report for this payment yet."


def test_a_provider_that_cannot_be_asked_says_so(
    treasurer_client: APIClient,
    settled_payment: Payment,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A provider that is unconfigured or unreachable is a 400 in its own words."""

    def unreachable(self: MockProvider, payment: Payment) -> None:
        raise PaymentError("Stripe is not configured.")

    monkeypatch.setattr(MockProvider, "fetch_fees", unreachable)

    response = treasurer_client.post(fees_url(settled_payment))

    assert response.status_code == 400
    assert response.json()["detail"] == "Stripe is not configured."


def test_an_unknown_payment_has_no_fee_to_fetch(treasurer_client: APIClient) -> None:
    """A payment id nobody recognizes is a 404, not an empty 200."""
    response = treasurer_client.post("/api/v1/admin/payments/99999/fees")

    assert response.status_code == 404


@pytest.mark.parametrize(("slug", "allowed"), role_matrix(TREASURER, ACCOUNT_ADMIN, SYSTEM_ADMIN))
def test_only_finance_fetches_a_fee(
    api_client: APIClient,
    all_role_users: dict[str, User],
    settled_payment: Payment,
    slug: str,
    allowed: bool,
) -> None:
    """The finance roles reach the fee refresh; every other role gets 403."""
    api_client.force_login(all_role_users[slug])

    response = api_client.post(fees_url(settled_payment))

    assert (response.status_code != 403) is allowed


# -- GET /admin/payments/members ------------------------------------------
@pytest.fixture
def searchable_members(db: None) -> list[User]:
    """Three members a search can tell apart by name and by address."""
    return [
        UserFactory(email="marta@example.test", first_name="Marta", last_name="Reyes"),
        UserFactory(email="tomas@example.test", first_name="Tomas", last_name="Reyes"),
        UserFactory(email="ana@elsewhere.test", first_name="Ana", last_name="Bracco"),
    ]


def search(client: APIClient, term: str) -> list[dict[str, Any]]:
    """The member search's rows for ``term``."""
    response = client.get(MEMBER_SEARCH, {"search": term})
    assert response.status_code == 200
    rows: list[dict[str, Any]] = response.json()
    return rows


def test_a_full_name_finds_the_member_it_names(
    treasurer_client: APIClient, searchable_members: list[User]
) -> None:
    """A check made out to "Marta Reyes" is searched for exactly as it is written."""
    assert [row["name"] for row in search(treasurer_client, "Marta Reyes")] == ["Marta Reyes"]


def test_a_surname_finds_everybody_who_carries_it(
    treasurer_client: APIClient, searchable_members: list[User]
) -> None:
    """Both members named Reyes come back for the surname."""
    assert len(search(treasurer_client, "reyes")) == 2


def test_the_search_reads_an_address_as_well_as_a_name(
    treasurer_client: APIClient, searchable_members: list[User]
) -> None:
    """A fragment of a domain finds the member who receives mail there."""
    assert [row["email"] for row in search(treasurer_client, "elsewhere")] == ["ana@elsewhere.test"]


def test_a_row_names_the_member_the_record_form_will_charge(
    treasurer_client: APIClient, searchable_members: list[User]
) -> None:
    """The row carries the id the manual payment is recorded against."""
    rows = search(treasurer_client, "elsewhere")

    assert rows[0]["user_id"] == searchable_members[2].pk


def test_a_row_says_where_the_member_s_membership_stands(
    treasurer_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The form shows the term the payment will extend, so the row carries it."""
    MembershipFactory(user=member, plan=annual_plan)

    rows = search(treasurer_client, member.email)

    assert rows[0]["membership"]["status"] == "current"


def test_an_empty_search_asks_for_nobody(
    treasurer_client: APIClient, searchable_members: list[User]
) -> None:
    """A search box nobody has typed in lists no members at all."""
    response = treasurer_client.get(MEMBER_SEARCH)

    assert response.json() == []


def test_the_search_stops_at_its_limit(treasurer_client: APIClient, db: None) -> None:
    """A term that matches everybody answers one page of names, not the register."""
    for index in range(15):
        UserFactory(email=f"pilot{index}@example.test", first_name="Pat", last_name="Pilot")

    assert len(search(treasurer_client, "pilot")) == 10


def test_the_search_is_ordered_by_name(treasurer_client: APIClient, db: None) -> None:
    """Rows read alphabetically, so the same term always lists them the same way."""
    UserFactory(email="zed@sorted.test", first_name="Zed", last_name="Zimmer")
    UserFactory(email="abe@sorted.test", first_name="Abe", last_name="Adler")

    rows = search(treasurer_client, "sorted.test")

    assert [row["name"] for row in rows] == ["Abe Adler", "Zed Zimmer"]


@pytest.mark.parametrize(("slug", "allowed"), role_matrix(TREASURER, ACCOUNT_ADMIN, SYSTEM_ADMIN))
def test_only_finance_searches_members_from_the_finance_area(
    api_client: APIClient,
    all_role_users: dict[str, User],
    slug: str,
    allowed: bool,
) -> None:
    """The finance roles reach the member search; every other role gets 403."""
    api_client.force_login(all_role_users[slug])

    response = api_client.get(MEMBER_SEARCH, {"search": "reyes"})

    assert (response.status_code != 403) is allowed
