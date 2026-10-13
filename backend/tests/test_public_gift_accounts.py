"""A public gift from an address that already has a portal account.

The public donation page answers the same whoever holds the address, so a member's or
a friend's address gives to that account.  The giver may not be the account's owner:
the gift never touches the account's renewal mandates, an unsettled one is not shown to
the account holder, and its receipt and statement line name the giver.
``docs/developer/api-payments.rst`` describes the endpoints.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.core import mail
from django.core.cache import cache
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.payments.models import MandateStatus, Payment, RenewalMandate
from apps.payments.receipts import receipt_data, statement_data
from apps.payments.renewals.mandates import pending_mandate_for
from tests.factories import RenewalMandateFactory

pytestmark = pytest.mark.django_db

CHECKOUT_URL = "/api/v1/donations/checkout"
MOCK_COMPLETE_URL = "/api/v1/donations/mock/complete"
MY_PAYMENTS_URL = "/api/v1/me/payments"

#: What the public form's giver contributes, in cents.
GIFT_CENTS = 2_000


@pytest.fixture(autouse=True)
def empty_throttle_cache() -> None:
    """The throttle counters are shared state; no test may inherit them."""
    cache.clear()


def start_gift(client: APIClient, email: str) -> dict[str, Any]:
    """Start a mock public gift from ``email`` in the name Pat Giver; the 201 body."""
    response = client.post(
        CHECKOUT_URL,
        {
            "first_name": "Pat",
            "last_name": "Giver",
            "email": email,
            "contribution_cents": GIFT_CENTS,
            "provider": "mock",
        },
        format="json",
    )
    assert response.status_code == 201, response.content
    body: dict[str, Any] = response.json()
    return body


def settle(client: APIClient, body: dict[str, Any]) -> Payment:
    """Complete the mock gift ``start_gift`` started, and return the payment."""
    client.post(
        MOCK_COMPLETE_URL,
        {"payment_id": body["payment_id"], "token": body["token"]},
        format="json",
    )
    return Payment.objects.get(pk=body["payment_id"])


@pytest.fixture
def pending_donation(member: User) -> RenewalMandate:
    """The member's recurring donation of the gift's amount, not yet paid for."""
    mandate: RenewalMandate = RenewalMandateFactory(
        user=member,
        plan=None,
        contribution_cents=GIFT_CENTS,
        status=MandateStatus.PENDING,
        method_ref="",
    )
    return mandate


def test_a_public_gift_is_marked(api_client: APIClient, member: User) -> None:
    """A gift started on the public page reads as one."""
    body = start_gift(api_client, member.email)

    assert Payment.objects.get(pk=body["payment_id"]).is_public_gift is True


def test_a_public_gift_matches_no_pending_mandate(
    api_client: APIClient, member: User, pending_donation: RenewalMandate
) -> None:
    """The member's pending recurring donation is not this gift's to start."""
    body = start_gift(api_client, member.email)

    assert pending_mandate_for(Payment.objects.get(pk=body["payment_id"])) is None


def test_a_public_gift_leaves_a_pending_mandate_pending(
    api_client: APIClient, member: User, pending_donation: RenewalMandate
) -> None:
    """Settling the gift does not activate the member's mandate with the giver's card."""
    settle(api_client, start_gift(api_client, member.email))

    pending_donation.refresh_from_db()
    assert pending_donation.status == MandateStatus.PENDING


def test_an_unsettled_public_gift_is_not_shown_to_the_member(
    api_client: APIClient, member: User
) -> None:
    """Anybody can start one in the member's name; until it is paid it is not theirs."""
    start_gift(APIClient(), member.email)
    api_client.force_login(member)

    assert api_client.get(MY_PAYMENTS_URL).json() == []


def test_a_settled_public_gift_is_shown_to_the_member(api_client: APIClient, member: User) -> None:
    """Once the money arrived, the gift is on the member's payments."""
    payment = settle(APIClient(), start_gift(APIClient(), member.email))
    api_client.force_login(member)

    assert [row["id"] for row in api_client.get(MY_PAYMENTS_URL).json()] == [payment.pk]


def test_the_receipt_names_the_giver(api_client: APIClient, member: User) -> None:
    """The receipt is made out to the name the giver typed, not the member's."""
    payment = settle(api_client, start_gift(api_client, member.email))

    assert receipt_data(payment).payer_name == "Pat Giver"


def test_the_statement_lists_the_gift_apart_naming_the_giver(
    api_client: APIClient, member: User
) -> None:
    """The member's year statement lists the gift on its own, in the giver's name."""
    settle(api_client, start_gift(api_client, member.email))

    lines = statement_data(member, timezone.localdate().year).public_gifts
    assert [line.given_as for line in lines] == ["Pat Giver"]


def test_the_statement_total_leaves_the_gift_out(api_client: APIClient, member: User) -> None:
    """Somebody else's gift in the member's name is not the member's giving."""
    settle(api_client, start_gift(api_client, member.email))

    assert statement_data(member, timezone.localdate().year).total_cents == 0


def test_the_receipt_greets_the_account_holder(api_client: APIClient, member: User) -> None:
    """The email is to the member, so it greets the member, not the name typed."""
    settle(api_client, start_gift(api_client, member.email))

    assert f"Hello {member.first_name}," in str(mail.outbox[-1].body)


def test_the_receipt_says_how_the_gift_was_made(api_client: APIClient, member: User) -> None:
    """The member is told the gift came from the public page, and whom to ask."""
    settle(api_client, start_gift(api_client, member.email))

    body = " ".join(str(mail.outbox[-1].body).split())
    assert "made on the public donation page with your email address" in body


def test_a_members_own_payment_names_nobody_else(member: User) -> None:
    """A payment that is not a public gift is made out to the account's own name."""
    payment = Payment(user=member)

    assert payment.payer_name == member.display_name
