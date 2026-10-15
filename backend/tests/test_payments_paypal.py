"""PayPal Orders v2 over ``httpx``, with the HTTP layer mocked by respx.

Covers the token cache, order creation, capture (happy path and every way it
can go wrong) and the webhook's deliberately cautious behavior.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
import respx
from django.core.cache import cache
from freezegun import freeze_time
from pytest_django.fixtures import Settings
from respx.models import AllMockedAssertionError
from rest_framework.response import Response
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.members.models import Membership, MembershipPlan
from apps.payments.api.serializers import PAYPAL_ORDER_ID_MESSAGE
from apps.payments.models import (
    Payment,
    PaymentProvider,
    PaymentStatus,
    PaymentWallet,
    Refund,
    RefundReason,
    RefundStatus,
)
from apps.payments.providers import paypal, paypal_api, paypal_orders
from apps.payments.providers.base import (
    PaymentVerificationError,
    ProviderFees,
    ProviderNotConfiguredError,
)
from apps.payments.refunds import issue_refund
from apps.payments.services import create_checkout, fees_are_known
from tests.conftest import PAYPAL_TRANSMISSION_HEADERS
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

CHECKOUT = "/api/v1/payments/checkout"
CAPTURE = "/api/v1/payments/paypal/capture"
WEBHOOK = "/api/v1/payments/paypal/webhook"

#: The lifetime PayPal reports for a token, in seconds.
TOKEN_LIFETIME_SECONDS = 3_600

SANDBOX = "https://api-m.sandbox.paypal.com"
TOKEN_URL = f"{SANDBOX}/v1/oauth2/token"
ORDERS_URL = f"{SANDBOX}/v2/checkout/orders"


@pytest.fixture(autouse=True)
def _paypal_configured(settings: Settings) -> Iterator[None]:
    """Configure fake PayPal keys and reset the token cache before and after."""
    settings.PAYPAL_CLIENT_ID = "client-id"
    settings.PAYPAL_CLIENT_SECRET = "client-secret"  # noqa: S105 - test fixture
    settings.PAYPAL_ENV = "sandbox"
    settings.PAYPAL_WEBHOOK_ID = ""
    settings.PAYMENTS_MOCK_ENABLED = True
    cache.clear()
    yield
    cache.clear()


def token_route(mock: respx.MockRouter, expires_in: int = 32_400) -> respx.Route:
    """Mock the PayPal OAuth token endpoint to return a fake token."""
    return mock.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200, json={"access_token": "A21AA-token", "expires_in": expires_in}
        )
    )


def order_payload(order_id: str = "ORDER1", status: str = "CREATED") -> dict[str, Any]:
    """A PayPal order creation response body."""
    return {"id": order_id, "status": status, "links": []}


def capture_payload(
    payment: Payment,
    *,
    order_id: str = "ORDER1",
    status: str = "COMPLETED",
    capture_status: str = "COMPLETED",
    value: str | None = None,
    currency: str = "USD",
    custom_id: str | None = None,
) -> dict[str, Any]:
    """A PayPal order-capture response body naming ``payment`` in its custom id.

    The single capture carries ``payment.pk`` as its custom id; ``custom_id=...``
    replaces it with any other value, so a caller can point the body at a different
    payment or at one that doesn't exist.
    """
    return {
        "id": order_id,
        "status": status,
        "purchase_units": [
            {
                "reference_id": f"payment-{payment.pk}",
                "payments": {
                    "captures": [
                        {
                            "id": "CAPTURE-1",
                            "status": capture_status,
                            "custom_id": custom_id or str(payment.pk),
                            "amount": {
                                "currency_code": currency,
                                "value": value or f"{payment.amount_cents / 100:.2f}",
                            },
                        }
                    ]
                },
            }
        ],
    }


# --------------------------------------------------------------------------
# live HTTP guard
# --------------------------------------------------------------------------
def test_a_call_no_route_matches_never_reaches_paypal() -> None:
    """A test that forgets to mock a route fails outright instead of calling PayPal."""
    with pytest.raises(AllMockedAssertionError, match="not mocked"):
        paypal_api.access_token()


# --------------------------------------------------------------------------
# OAuth token
# --------------------------------------------------------------------------
@respx.mock
def test_the_token_is_fetched_once_and_cached() -> None:
    """The OAuth token is fetched once and reused from cache on a second call."""
    route = token_route(respx.mock)
    assert paypal_api.access_token() == "A21AA-token"
    assert paypal_api.access_token() == "A21AA-token"
    assert route.call_count == 1

    request = route.calls[0].request
    assert request.headers["authorization"].startswith("Basic ")
    assert b"grant_type=client_credentials" in request.content


@respx.mock
def test_an_expired_token_is_fetched_again() -> None:
    """The cached token is reused until it expires, and a fresh one is fetched after.

    A token PayPal says lasts an hour is dropped ``TOKEN_SKEW_SECONDS`` early, so the
    cache holds for 3540 seconds and the next second's call fetches again.
    """
    route = token_route(respx.mock, expires_in=TOKEN_LIFETIME_SECONDS)
    with freeze_time("2026-09-22 12:00:00") as clock:
        assert paypal_api.access_token() == "A21AA-token"

        # codespell:ignore-next-line tick
        clock.tick(timedelta(seconds=TOKEN_LIFETIME_SECONDS - paypal_api.TOKEN_SKEW_SECONDS - 1))
        assert paypal_api.access_token() == "A21AA-token"
        assert route.call_count == 1

        clock.tick(timedelta(seconds=2))  # codespell:ignore tick
        assert paypal_api.access_token() == "A21AA-token"
        assert route.call_count == 2


@respx.mock
def test_emptying_the_cache_fetches_a_fresh_token() -> None:
    """Emptying Django's cache forces a fresh fetch on the next call."""
    route = token_route(respx.mock, expires_in=0)
    paypal_api.access_token()
    paypal_api.access_token()
    # expires_in=0 still leaves the 30s floor, so the cache holds.
    assert route.call_count == 1

    cache.clear()
    paypal_api.access_token()
    assert route.call_count == 2


@respx.mock
def test_bad_credentials_raise() -> None:
    """A 401 from the token endpoint raises PaymentVerificationError."""
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(401, json={"error": "invalid_client"}))
    with pytest.raises(PaymentVerificationError, match=r"refused our credentials \(HTTP 401\)"):
        paypal_api.access_token()


def test_missing_credentials_raise(settings: Settings) -> None:
    """Fetching a token without a client id raises ProviderNotConfiguredError."""
    settings.PAYPAL_CLIENT_ID = ""
    with pytest.raises(
        ProviderNotConfiguredError,
        match=r"PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET are empty",
    ):
        paypal_api.access_token()


def test_the_live_environment_uses_the_live_host(settings: Settings) -> None:
    """PAYPAL_ENV selects the live or sandbox API host."""
    settings.PAYPAL_ENV = "live"
    assert paypal_api.api_base() == "https://api-m.paypal.com"
    settings.PAYPAL_ENV = "sandbox"
    assert paypal_api.api_base() == SANDBOX


# --------------------------------------------------------------------------
# create order
# --------------------------------------------------------------------------
@respx.mock
def test_checkout_creates_a_paypal_order(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """Checkout creates a PayPal order for the full amount, signed with a bearer token."""
    token_route(respx.mock)
    route = respx.post(ORDERS_URL).mock(
        return_value=httpx.Response(201, json=order_payload("ORDERXYZ"))
    )

    api_client.force_login(member)
    response = api_client.post(
        CHECKOUT, {"plan": "annual", "contribution_cents": 2_000, "provider": "paypal"}
    )

    assert response.status_code == 201
    assert response.json()["client"] == {"order_id": "ORDERXYZ"}

    payment = Payment.objects.get(pk=response.json()["payment_id"])
    assert payment.provider_ref == "ORDERXYZ"

    body = json.loads(route.calls[0].request.content)
    unit = body["purchase_units"][0]
    assert body["intent"] == "CAPTURE"
    assert unit["amount"] == {"currency_code": "USD", "value": "65.00"}
    assert unit["custom_id"] == str(payment.pk)
    assert body["payment_source"]["paypal"]["experience_context"]["brand_name"] == "CalDART"
    assert route.calls[0].request.headers["authorization"] == "Bearer A21AA-token"


@respx.mock
def test_a_rejected_order_does_not_leave_a_payment_behind(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """An order PayPal rejects is a 400 and doesn't create a payment."""
    token_route(respx.mock)
    respx.post(ORDERS_URL).mock(
        return_value=httpx.Response(422, json={"message": "AMOUNT_MISMATCH"})
    )

    api_client.force_login(member)
    response = api_client.post(
        CHECKOUT, {"plan": "annual", "contribution_cents": 0, "provider": "paypal"}
    )

    assert response.status_code == 400
    assert "AMOUNT_MISMATCH" in str(response.json())
    assert Payment.objects.count() == 0


# --------------------------------------------------------------------------
# capture
# --------------------------------------------------------------------------
def pending_paypal_payment(member: User, order_id: str = "ORDER1") -> Payment:
    """Start a pending PayPal checkout with ``order_id`` already attached."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.PAYPAL)
    payment.provider_ref = order_id
    payment.save(update_fields=["provider_ref"])
    return payment


@respx.mock
def test_capture_activates_the_membership(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """Capturing a completed order succeeds the payment and grants a membership."""
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    route = respx.post(f"{ORDERS_URL}/ORDER1/capture").mock(
        return_value=httpx.Response(201, json=capture_payload(payment))
    )

    api_client.force_login(member)
    response = api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER1"})

    assert response.status_code == 200
    assert response.json()["status"] == "succeeded"
    assert response.json()["membership"]["status"] == "current"
    assert route.call_count == 1

    payment.refresh_from_db()
    assert payment.wallet == PaymentWallet.PAYPAL
    assert payment.completed_at is not None
    assert Membership.objects.filter(payment=payment).count() == 1


@respx.mock
def test_capture_that_is_not_completed_does_not_grant_anything(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A capture not COMPLETED fails the payment and doesn't grant anything."""
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    respx.post(f"{ORDERS_URL}/ORDER1/capture").mock(
        return_value=httpx.Response(
            201, json=capture_payload(payment, status="PAYER_ACTION_REQUIRED")
        )
    )

    api_client.force_login(member)
    response = api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER1"})

    assert response.status_code == 400
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.FAILED
    assert Membership.objects.count() == 0


def unprocessable(issue: str) -> httpx.Response:
    """PayPal's 422 answer to a capture it refuses for ``issue``."""
    return httpx.Response(
        422,
        json={
            "name": "UNPROCESSABLE_ENTITY",
            "message": "The requested action could not be performed.",
            "details": [{"issue": issue, "description": "The instrument was refused."}],
        },
    )


@respx.mock
def test_a_declined_capture_fails_the_payment(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A capture PayPal refuses as ``INSTRUMENT_DECLINED`` fails the payment."""
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    respx.post(f"{ORDERS_URL}/ORDER1/capture").mock(
        return_value=unprocessable("INSTRUMENT_DECLINED")
    )

    api_client.force_login(member)
    api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER1"})

    payment.refresh_from_db()
    assert payment.status == PaymentStatus.FAILED


@respx.mock
def test_a_declined_capture_keeps_the_stored_order(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The refusal is added to the stored order body rather than replacing it."""
    payment = pending_paypal_payment(member)
    payment.raw = {"id": "ORDER1", "status": "CREATED"}
    payment.save(update_fields=["raw"])
    token_route(respx.mock)
    respx.post(f"{ORDERS_URL}/ORDER1/capture").mock(
        return_value=unprocessable("INSTRUMENT_DECLINED")
    )

    api_client.force_login(member)
    api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER1"})

    payment.refresh_from_db()
    assert payment.raw == {
        "id": "ORDER1",
        "status": "CREATED",
        "capture_refused": ["INSTRUMENT_DECLINED"],
    }


@respx.mock
def test_a_declined_order_is_never_captured_again(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """After a decline, capturing the same order again asks PayPal nothing."""
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    route = respx.post(f"{ORDERS_URL}/ORDER1/capture").mock(
        return_value=unprocessable("INSTRUMENT_DECLINED")
    )

    api_client.force_login(member)
    body = {"payment_id": payment.pk, "order_id": "ORDER1"}
    api_client.post(CAPTURE, body)
    api_client.post(CAPTURE, body)

    assert route.call_count == 1


@respx.mock
def test_a_capture_refused_for_another_reason_stays_pending(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A refusal other than a decline, such as an unapproved order, leaves it pending."""
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    respx.post(f"{ORDERS_URL}/ORDER1/capture").mock(
        return_value=unprocessable("ORDER_NOT_APPROVED")
    )

    api_client.force_login(member)
    response = api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER1"})

    assert response.status_code == 400
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.PENDING


@respx.mock
def test_capture_of_the_wrong_amount_is_refused(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A capture whose amount does not match the payment is refused."""
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    respx.post(f"{ORDERS_URL}/ORDER1/capture").mock(
        return_value=httpx.Response(201, json=capture_payload(payment, value="1.00"))
    )

    api_client.force_login(member)
    response = api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER1"})

    assert response.status_code == 400
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.PENDING
    assert Membership.objects.count() == 0


@respx.mock
def test_capture_in_another_currency_is_refused(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A capture in the wrong currency is refused."""
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    respx.post(f"{ORDERS_URL}/ORDER1/capture").mock(
        return_value=httpx.Response(201, json=capture_payload(payment, currency="CAD"))
    )

    api_client.force_login(member)
    assert (
        api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER1"}).status_code
        == 400
    )
    assert Membership.objects.count() == 0


@respx.mock
def test_capture_for_another_payment_is_refused(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A capture whose custom id names a different payment is refused."""
    payment = pending_paypal_payment(member)
    other = create_checkout(member, "annual", 0, PaymentProvider.PAYPAL)
    token_route(respx.mock)
    respx.post(f"{ORDERS_URL}/ORDER1/capture").mock(
        return_value=httpx.Response(201, json=capture_payload(payment, custom_id=str(other.pk)))
    )

    api_client.force_login(member)
    assert (
        api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER1"}).status_code
        == 400
    )
    assert Membership.objects.count() == 0


@respx.mock
def test_capture_answered_for_another_order_is_refused(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A capture naming an order other than the payment's own doesn't grant anything."""
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    respx.post(f"{ORDERS_URL}/ORDER1/capture").mock(
        return_value=httpx.Response(201, json=capture_payload(payment, order_id="ORDEROTHER"))
    )

    api_client.force_login(member)
    response = api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER1"})

    assert response.status_code == 400
    assert Membership.objects.count() == 0


@respx.mock
def test_completed_order_without_a_capture_is_refused(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """An order without a completed capture is refused and marks the payment failed."""
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    respx.post(f"{ORDERS_URL}/ORDER1/capture").mock(
        return_value=httpx.Response(201, json=capture_payload(payment, capture_status="DECLINED"))
    )

    api_client.force_login(member)
    assert (
        api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER1"}).status_code
        == 400
    )
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.FAILED


def test_capture_of_an_order_id_we_did_not_issue_is_refused(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """Capturing with an order id that does not match the payment's own is refused."""
    payment = pending_paypal_payment(member)
    api_client.force_login(member)
    response = api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDEROTHER"})
    assert response.status_code == 400


#: Order ids that are not PayPal's shape: path segments, query and fragment
#: delimiters, lower case, spaces, and hyphens.
MALFORMED_ORDER_IDS = [
    "../../v2/payments/captures/CAPTURE1/refund",
    "ORDER1/../../v1/notifications",
    "ORDER1?x=1",
    "ORDER1#frag",
    "order1",
    "ORDER 1",
    "ORDER-1",
]


@pytest.mark.parametrize("order_id", MALFORMED_ORDER_IDS)
def test_capture_refuses_an_order_id_that_is_not_paypals_shape(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, order_id: str
) -> None:
    """An order id of anything but upper-case letters and digits is refused by field."""
    payment = pending_paypal_payment(member)
    api_client.force_login(member)

    response = api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": order_id})

    assert response.json() == {"order_id": [PAYPAL_ORDER_ID_MESSAGE]}


@respx.mock
def test_capture_of_a_payment_without_an_order_is_refused(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A pending payment PayPal never gave an order is not captured under another."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.PAYPAL)
    token_route(respx.mock)
    route = respx.post(f"{ORDERS_URL}/ORDERELSE/capture").mock(
        return_value=httpx.Response(201, json=capture_payload(payment, order_id="ORDERELSE"))
    )

    api_client.force_login(member)
    response = api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDERELSE"})

    assert response.status_code == 400
    assert route.call_count == 0


@respx.mock
def test_a_failed_payment_without_an_order_is_answered_without_asking_paypal(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A failed payment is answered from its row, like every payment no longer pending."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.PAYPAL)
    payment.status = PaymentStatus.FAILED
    payment.save(update_fields=["status"])
    token_route(respx.mock)
    route = respx.post(f"{ORDERS_URL}/ORDERELSE/capture").mock(
        return_value=httpx.Response(201, json=capture_payload(payment, order_id="ORDERELSE"))
    )

    api_client.force_login(member)
    response = api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDERELSE"})

    assert response.json()["status"] == PaymentStatus.FAILED
    assert route.call_count == 0


@respx.mock
def test_capture_without_an_order_id_captures_the_stored_order(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """Leaving ``order_id`` out captures the order PayPal gave the payment at checkout."""
    payment = pending_paypal_payment(member, order_id="ORDERSTORED")
    token_route(respx.mock)
    route = respx.post(f"{ORDERS_URL}/ORDERSTORED/capture").mock(
        return_value=httpx.Response(201, json=capture_payload(payment, order_id="ORDERSTORED"))
    )

    api_client.force_login(member)
    api_client.post(CAPTURE, {"payment_id": payment.pk})

    assert route.call_count == 1


@respx.mock
def test_a_stored_order_id_is_sent_as_one_path_segment(
    member: User, annual_plan: MembershipPlan
) -> None:
    """A reference holding a slash is escaped as one segment, not followed as a path."""
    payment = pending_paypal_payment(member, order_id="ORDER1/../../v1/x")
    token_route(respx.mock)
    route = respx.get(url__regex=r".*").mock(return_value=httpx.Response(200, json={}))

    paypal.PayPalProvider().fetch_fees(payment)

    assert route.calls.last.request.url.raw_path == b"/v2/checkout/orders/ORDER1%2F..%2F..%2Fv1%2Fx"


@respx.mock
def test_capturing_twice_grants_one_term(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """Capturing the same payment twice grants exactly one membership term."""
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    route = respx.post(f"{ORDERS_URL}/ORDER1/capture").mock(
        return_value=httpx.Response(201, json=capture_payload(payment))
    )

    api_client.force_login(member)
    body = {"payment_id": payment.pk, "order_id": "ORDER1"}
    assert api_client.post(CAPTURE, body).status_code == 200
    assert api_client.post(CAPTURE, body).status_code == 200

    # The second call short-circuits before PayPal is asked again.
    assert route.call_count == 1
    assert Membership.objects.filter(user=member).count() == 1


# --- a payment already refunded ---------------------------------------------
#: When the refunded payments below settled, well before any test runs.
SETTLED_AT = datetime(2025, 3, 14, 12, 0, tzinfo=UTC)

REFUNDED_STATUSES = [PaymentStatus.REFUNDED, PaymentStatus.PARTIALLY_REFUNDED]


def refunded_paypal_payment(member: User, status: str) -> Payment:
    """A PayPal payment for ``ORDER1``, settled at :data:`SETTLED_AT`, now ``status``."""
    payment = pending_paypal_payment(member)
    payment.status = status
    payment.completed_at = SETTLED_AT
    payment.save(update_fields=["status", "completed_at"])
    return payment


@pytest.mark.parametrize("status", REFUNDED_STATUSES)
@respx.mock
def test_capture_leaves_a_refunded_payment_refunded(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, status: str
) -> None:
    """Capturing a refunded payment answers its refunded status."""
    payment = refunded_paypal_payment(member, status)
    token_route(respx.mock)
    respx.post(f"{ORDERS_URL}/ORDER1/capture").mock(
        return_value=httpx.Response(201, json=capture_payload(payment))
    )

    api_client.force_login(member)
    response = api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER1"})

    assert response.json()["status"] == status


@pytest.mark.parametrize("status", REFUNDED_STATUSES)
@respx.mock
def test_capture_of_a_refunded_payment_does_not_ask_paypal_anything(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, status: str
) -> None:
    """A payment whose money arrived is not captured again."""
    payment = refunded_paypal_payment(member, status)
    token_route(respx.mock)
    route = respx.post(f"{ORDERS_URL}/ORDER1/capture").mock(
        return_value=httpx.Response(201, json=capture_payload(payment))
    )

    api_client.force_login(member)
    api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER1"})

    assert route.call_count == 0


@pytest.mark.parametrize("status", REFUNDED_STATUSES)
@respx.mock
def test_capture_keeps_a_refunded_payments_completion_date(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, status: str
) -> None:
    """Capturing a refunded payment does not move it into the current period."""
    payment = refunded_paypal_payment(member, status)
    token_route(respx.mock)
    respx.post(f"{ORDERS_URL}/ORDER1/capture").mock(
        return_value=httpx.Response(201, json=capture_payload(payment))
    )

    api_client.force_login(member)
    api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER1"})

    payment.refresh_from_db()
    assert payment.completed_at == SETTLED_AT


def test_capture_requires_a_session(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """Capturing while signed out is a 401."""
    payment = pending_paypal_payment(member)
    assert api_client.post(CAPTURE, {"payment_id": payment.pk}).status_code == 401


def test_capture_rejects_someone_elses_payment(
    api_client: APIClient,
    member: User,
    user_factory: type[UserFactory],
    annual_plan: MembershipPlan,
) -> None:
    """A signed-in user capturing another member's payment gets a 404."""
    payment = pending_paypal_payment(member)
    thief = user_factory(email="thief@example.test", roles=["member"])
    api_client.force_login(thief)
    response = api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER1"})
    assert response.status_code == 404


# --------------------------------------------------------------------------
# webhook
# --------------------------------------------------------------------------
def webhook_event(
    payment: Payment, event_type: str = "PAYMENT.CAPTURE.COMPLETED"
) -> dict[str, Any]:
    """A PayPal webhook payload of ``event_type`` for ``payment``.

    The resource is a capture of the payment's own order, as PayPal sends it: it names
    the payment in ``custom_id`` and the order in ``supplementary_data``.
    """
    return {
        "id": "WH-1",
        "event_type": event_type,
        "resource": {
            "id": "CAPTURE-1",
            "custom_id": str(payment.pk),
            "status": "COMPLETED",
            "amount": {"currency_code": "USD", "value": f"{payment.amount_cents / 100:.2f}"},
            "supplementary_data": {"related_ids": {"order_id": payment.provider_ref}},
        },
    }


def post_webhook(client: APIClient, body: dict[str, Any], *, signed: bool = True) -> Response:
    """POST the body to the PayPal webhook endpoint as JSON.

    The delivery carries PayPal's transmission headers unless ``signed`` is false;
    whether they verify is up to the mocked verification call.
    """
    headers = PAYPAL_TRANSMISSION_HEADERS if signed else {}
    return client.post(
        WEBHOOK, data=json.dumps(body), content_type="application/json", headers=headers
    )


@respx.mock(assert_all_called=False)
def test_the_webhook_is_refused_while_no_webhook_id_is_set(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """Without a ``PAYPAL_WEBHOOK_ID``, the route answers 404."""
    payment = pending_paypal_payment(member)

    response = post_webhook(api_client, webhook_event(payment))

    assert response.status_code == 404


def test_the_webhook_without_a_webhook_id_says_so(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The 404 names the missing configuration."""
    payment = pending_paypal_payment(member)

    response = post_webhook(api_client, webhook_event(payment))

    assert json.loads(response.content) == {"detail": paypal.WEBHOOK_NOT_CONFIGURED_MESSAGE}


@respx.mock(assert_all_called=False)
def test_the_webhook_without_a_webhook_id_does_not_ask_paypal_anything(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """Neither a token nor a verification is asked for while the route is refused."""
    payment = pending_paypal_payment(member)
    token = token_route(respx.mock)
    verify = verification_route(respx.mock)

    post_webhook(api_client, webhook_event(payment))

    assert token.call_count + verify.call_count == 0


@pytest.mark.parametrize(
    "case",
    ["no headers", "no id", "no event type", "empty body"],
)
@respx.mock(assert_all_called=False)
def test_an_unsigned_delivery_is_refused_without_asking_paypal(
    api_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    settings: Settings,
    case: str,
) -> None:
    """A delivery missing what PayPal signs is a 400, and no verification call is made."""
    settings.PAYPAL_WEBHOOK_ID = "WH-CONFIG"
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    route = verification_route(respx.mock)
    event = webhook_event(payment)
    if case == "no id":
        del event["id"]
    elif case == "no event type":
        del event["event_type"]
    elif case == "empty body":
        event = {}

    post_webhook(api_client, event, signed=case != "no headers")

    assert route.call_count == 0


def test_an_unsigned_delivery_is_answered_as_unverified(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, settings: Settings
) -> None:
    """A delivery without transmission headers is the unverified 400."""
    settings.PAYPAL_WEBHOOK_ID = "WH-CONFIG"
    payment = pending_paypal_payment(member)

    response = post_webhook(api_client, webhook_event(payment), signed=False)

    assert json.loads(response.content) == {"detail": paypal.UNVERIFIED_MESSAGE}


def test_without_a_webhook_id_nothing_is_recorded(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A notification the route refuses is not filed against the payment it names."""
    payment = pending_paypal_payment(member)

    post_webhook(api_client, webhook_event(payment))

    payment.refresh_from_db()
    assert "last_webhook" not in payment.raw


@respx.mock
def test_a_verified_webhook_activates_the_membership(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, settings: Settings
) -> None:
    """A verified capture-completed webhook succeeds the payment and grants a term."""
    settings.PAYPAL_WEBHOOK_ID = "WH-CONFIG"
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    respx.post(f"{SANDBOX}/v1/notifications/verify-webhook-signature").mock(
        return_value=httpx.Response(200, json={"verification_status": "SUCCESS"})
    )

    response = post_webhook(api_client, webhook_event(payment))
    assert json.loads(response.content)["handled"] is True

    payment.refresh_from_db()
    assert payment.status == PaymentStatus.SUCCEEDED
    assert Membership.objects.filter(payment=payment).count() == 1


@respx.mock
def test_a_failed_verification_does_not_activate(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, settings: Settings
) -> None:
    """A webhook whose signature fails verification leaves the payment pending."""
    settings.PAYPAL_WEBHOOK_ID = "WH-CONFIG"
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    respx.post(f"{SANDBOX}/v1/notifications/verify-webhook-signature").mock(
        return_value=httpx.Response(200, json={"verification_status": "FAILURE"})
    )

    response = post_webhook(api_client, webhook_event(payment))
    assert response.status_code == 400
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.PENDING


@pytest.mark.parametrize(
    "answer",
    [
        httpx.Response(200, json={"verification_status": "FAILURE"}),
        httpx.Response(500, json={"name": "INTERNAL_SERVICE_ERROR"}),
    ],
    ids=["failure", "error"],
)
@respx.mock
def test_an_unverified_webhook_does_not_record_anything(
    api_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    settings: Settings,
    answer: httpx.Response,
) -> None:
    """A notification PayPal does not vouch for leaves the payment's stored response."""
    settings.PAYPAL_WEBHOOK_ID = "WH-CONFIG"
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    respx.post(f"{SANDBOX}/v1/notifications/verify-webhook-signature").mock(return_value=answer)

    post_webhook(api_client, webhook_event(payment))

    payment.refresh_from_db()
    assert "last_webhook" not in payment.raw


@respx.mock
def test_an_unverified_webhook_is_logged_with_its_type_quoted(
    api_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    settings: Settings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The caller's ``event_type`` reaches the log quoted, never as a line of its own."""
    settings.PAYPAL_WEBHOOK_ID = "WH-CONFIG"
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    verification_route(respx.mock, status="FAILURE")
    event = webhook_event(payment, "PAYMENT.CAPTURE.COMPLETED\nFORGED LINE")

    with caplog.at_level(logging.INFO, logger=paypal.__name__):
        post_webhook(api_client, event)

    assert "'PAYMENT.CAPTURE.COMPLETED\\nFORGED LINE'" in caplog.text


@respx.mock
def test_a_verified_webhook_is_filed_against_its_payment(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, settings: Settings
) -> None:
    """A notification PayPal vouches for is kept on the payment as its last one."""
    settings.PAYPAL_WEBHOOK_ID = "WH-CONFIG"
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    verification_route(respx.mock)

    post_webhook(api_client, webhook_event(payment, "PAYMENT.CAPTURE.PENDING"))

    payment.refresh_from_db()
    assert payment.raw["last_webhook"]["event_type"] == "PAYMENT.CAPTURE.PENDING"


@respx.mock
def test_a_body_over_the_cap_is_refused_before_paypal_is_asked(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, settings: Settings
) -> None:
    """A body larger than the webhook's cap is a 413, and no verification call is made."""
    settings.PAYPAL_WEBHOOK_ID = "WH-CONFIG"
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    route = verification_route(respx.mock)
    event = webhook_event(payment)
    event["padding"] = "x" * paypal.MAX_WEBHOOK_BYTES

    response = post_webhook(api_client, event)

    assert response.status_code == 413
    assert route.call_count == 0


@respx.mock
def test_a_verified_webhook_of_the_wrong_amount_is_ignored(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, settings: Settings
) -> None:
    """A verified webhook whose amount does not match is accepted but unhandled."""
    settings.PAYPAL_WEBHOOK_ID = "WH-CONFIG"
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    respx.post(f"{SANDBOX}/v1/notifications/verify-webhook-signature").mock(
        return_value=httpx.Response(200, json={"verification_status": "SUCCESS"})
    )

    event = webhook_event(payment)
    event["resource"]["amount"]["value"] = "1.00"
    response = post_webhook(api_client, event)

    assert json.loads(response.content)["handled"] is False
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.PENDING


@respx.mock
def test_a_verified_capture_in_another_currency_is_ignored(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, settings: Settings
) -> None:
    """A verified capture of the right number in another currency leaves it pending."""
    settings.PAYPAL_WEBHOOK_ID = "WH-CONFIG"
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    verification_route(respx.mock)
    event = webhook_event(payment)
    event["resource"]["amount"]["currency_code"] = "JPY"

    post_webhook(api_client, event)

    payment.refresh_from_db()
    assert payment.status == PaymentStatus.PENDING


@pytest.mark.parametrize(
    "related_ids",
    [{"order_id": "ORDERSOMEONEELSE"}, {}],
    ids=["another order", "no order"],
)
@respx.mock
def test_a_verified_capture_of_another_order_is_ignored(
    api_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    settings: Settings,
    related_ids: dict[str, str],
) -> None:
    """A verified capture naming the payment but not its order leaves it pending."""
    settings.PAYPAL_WEBHOOK_ID = "WH-CONFIG"
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    verification_route(respx.mock)
    event = webhook_event(payment)
    event["resource"]["supplementary_data"] = {"related_ids": related_ids}

    post_webhook(api_client, event)

    payment.refresh_from_db()
    assert payment.status == PaymentStatus.PENDING


@respx.mock
def test_a_verified_capture_of_another_order_is_reported_unhandled(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, settings: Settings
) -> None:
    """The notification is acknowledged, so PayPal stops retrying it, but not handled."""
    settings.PAYPAL_WEBHOOK_ID = "WH-CONFIG"
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    verification_route(respx.mock)
    event = webhook_event(payment)
    event["resource"]["supplementary_data"] = {"related_ids": {"order_id": "ORDERSOMEONEELSE"}}

    response = post_webhook(api_client, event)

    assert json.loads(response.content)["handled"] is False


@respx.mock
def test_a_webhook_settled_payment_can_be_refunded_through_caldart(
    api_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    settings: Settings,
    account_admin: User,
) -> None:
    """A payment settled by the capture notification is refunded against that capture."""
    settings.PAYPAL_WEBHOOK_ID = "WH-CONFIG"
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    verification_route(respx.mock)
    post_webhook(api_client, webhook_event(payment))
    payment.refresh_from_db()
    route = refund_route(respx.mock, "CAPTURE-1", "REFUND-AFTER-WEBHOOK")

    refund = issue_refund(
        payment, amount_cents=1_000, reason=RefundReason.ERROR, actor=account_admin
    )

    assert refund.status == RefundStatus.SUCCEEDED
    assert route.call_count == 1


@respx.mock
def test_a_webhook_settled_payment_keeps_its_stored_order(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, settings: Settings
) -> None:
    """Settling by notification keeps what checkout stored, with the capture beside it."""
    settings.PAYPAL_WEBHOOK_ID = "WH-CONFIG"
    payment = pending_paypal_payment(member)
    payment.raw = order_payload("ORDER1")
    payment.save(update_fields=["raw"])
    token_route(respx.mock)
    verification_route(respx.mock)

    post_webhook(api_client, webhook_event(payment))

    payment.refresh_from_db()
    assert payment.raw["id"] == "ORDER1"


def someone_elses_order_event(victim: Payment, event_type: str) -> dict[str, Any]:
    """A verified ``event_type`` for an order the payer made in their own browser.

    The resource names ``victim`` in ``custom_id``, which a browser-created order may
    carry, but belongs to another order entirely.
    """
    event = webhook_event(victim, event_type)
    event["resource"]["supplementary_data"] = {"related_ids": {"order_id": "ORDERBROWSER"}}
    return event


@pytest.mark.parametrize("event_type", sorted(paypal.CAPTURE_FAILED))
@respx.mock
def test_a_reversal_of_someone_elses_order_leaves_the_payment_pending(
    api_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    settings: Settings,
    event_type: str,
) -> None:
    """A verified denial or reversal of another order does not fail this payment."""
    settings.PAYPAL_WEBHOOK_ID = "WH-CONFIG"
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    verification_route(respx.mock)

    post_webhook(api_client, someone_elses_order_event(payment, event_type))

    payment.refresh_from_db()
    assert payment.status == PaymentStatus.PENDING


@pytest.mark.parametrize("event_type", sorted(paypal.CAPTURE_FAILED))
@respx.mock
def test_a_reversal_of_someone_elses_order_is_reported_unhandled(
    api_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    settings: Settings,
    event_type: str,
) -> None:
    """The notification is acknowledged but not handled."""
    settings.PAYPAL_WEBHOOK_ID = "WH-CONFIG"
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    verification_route(respx.mock)

    response = post_webhook(api_client, someone_elses_order_event(payment, event_type))

    assert json.loads(response.content)["handled"] is False


@respx.mock
def test_a_verified_denial_marks_the_payment_failed(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, settings: Settings
) -> None:
    """A verified capture-denied webhook marks the payment failed."""
    settings.PAYPAL_WEBHOOK_ID = "WH-CONFIG"
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    respx.post(f"{SANDBOX}/v1/notifications/verify-webhook-signature").mock(
        return_value=httpx.Response(200, json={"verification_status": "SUCCESS"})
    )

    post_webhook(api_client, webhook_event(payment, "PAYMENT.CAPTURE.DENIED"))
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.FAILED


@pytest.mark.parametrize("status", REFUNDED_STATUSES)
@respx.mock
def test_a_replayed_capture_leaves_a_refunded_payment_refunded(
    api_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    settings: Settings,
    status: str,
) -> None:
    """A verified capture-completed delivered again after a refund keeps the status."""
    settings.PAYPAL_WEBHOOK_ID = "WH-CONFIG"
    payment = refunded_paypal_payment(member, status)
    token_route(respx.mock)
    verification_route(respx.mock)

    post_webhook(api_client, webhook_event(payment))

    payment.refresh_from_db()
    assert payment.status == status


@pytest.mark.parametrize("status", REFUNDED_STATUSES)
@respx.mock
def test_a_replayed_capture_keeps_a_refunded_payments_completion_date(
    api_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    settings: Settings,
    status: str,
) -> None:
    """A verified capture-completed delivered again after a refund keeps every date."""
    settings.PAYPAL_WEBHOOK_ID = "WH-CONFIG"
    payment = refunded_paypal_payment(member, status)
    token_route(respx.mock)
    verification_route(respx.mock)

    post_webhook(api_client, webhook_event(payment))

    payment.refresh_from_db()
    assert payment.completed_at == SETTLED_AT


@pytest.mark.parametrize("event_type", sorted(paypal.CAPTURE_FAILED))
@pytest.mark.parametrize("status", REFUNDED_STATUSES)
@respx.mock
def test_a_verified_reversal_leaves_a_refunded_payment_refunded(
    api_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    settings: Settings,
    status: str,
    event_type: str,
) -> None:
    """A verified denial or reversal after a refund does not mark the payment failed."""
    settings.PAYPAL_WEBHOOK_ID = "WH-CONFIG"
    payment = refunded_paypal_payment(member, status)
    token_route(respx.mock)
    verification_route(respx.mock)

    post_webhook(api_client, webhook_event(payment, event_type))

    payment.refresh_from_db()
    assert payment.status == status


@respx.mock
def test_a_webhook_for_an_unknown_payment_is_accepted(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, settings: Settings
) -> None:
    """A webhook naming a payment id that does not exist is accepted but unhandled."""
    settings.PAYPAL_WEBHOOK_ID = "WH-CONFIG"
    token_route(respx.mock)
    verification_route(respx.mock)
    response = post_webhook(
        api_client,
        {
            "id": "WH-2",
            "event_type": "PAYMENT.CAPTURE.COMPLETED",
            "resource": {"custom_id": "9999"},
        },
    )
    assert response.status_code == 200
    assert json.loads(response.content)["handled"] is False


def test_a_malformed_webhook_is_a_400(api_client: APIClient, settings: Settings) -> None:
    """A body that is not valid JSON is refused with a 400."""
    settings.PAYPAL_WEBHOOK_ID = "WH-CONFIG"
    response = api_client.post(WEBHOOK, data="not json", content_type="application/json")
    assert response.status_code == 400


@respx.mock
def test_the_webhook_finds_the_payment_by_order_id(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, settings: Settings
) -> None:
    """A webhook is matched to its payment by order id when it lacks a custom id."""
    settings.PAYPAL_WEBHOOK_ID = "WH-CONFIG"
    token_route(respx.mock)
    verification_route(respx.mock)
    payment = pending_paypal_payment(member, order_id="ORDERREF")
    response = post_webhook(
        api_client,
        {
            "id": "WH-3",
            "event_type": "PAYMENT.CAPTURE.COMPLETED",
            "resource": {
                "id": "CAPTURE-9",
                "supplementary_data": {"related_ids": {"order_id": "ORDERREF"}},
            },
        },
    )
    assert response.status_code == 200
    payment.refresh_from_db()
    assert "last_webhook" in payment.raw


# --------------------------------------------------------------------------
# fees
# --------------------------------------------------------------------------
def with_breakdown(
    order: dict[str, Any], *, fee: str = "1.61", net: str = "43.39"
) -> dict[str, Any]:
    """The same capture response, with the seller receivable breakdown PayPal adds."""
    capture = order["purchase_units"][0]["payments"]["captures"][0]
    capture["seller_receivable_breakdown"] = {
        "gross_amount": {"currency_code": "USD", "value": "45.00"},
        "paypal_fee": {"currency_code": "USD", "value": fee},
        "net_amount": {"currency_code": "USD", "value": net},
    }
    return order


@respx.mock
def test_capture_records_the_fee_from_the_seller_breakdown(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The fee PayPal reports on the capture lands on the payment in cents."""
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    respx.post(f"{ORDERS_URL}/ORDER1/capture").mock(
        return_value=httpx.Response(201, json=with_breakdown(capture_payload(payment)))
    )

    api_client.force_login(member)
    api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER1"})

    payment.refresh_from_db()
    assert payment.fee_cents == 161


@respx.mock
def test_capture_records_the_net_from_the_seller_breakdown(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The net PayPal reports is stored as reported."""
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    respx.post(f"{ORDERS_URL}/ORDER1/capture").mock(
        return_value=httpx.Response(201, json=with_breakdown(capture_payload(payment)))
    )

    api_client.force_login(member)
    api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER1"})

    payment.refresh_from_db()
    assert payment.net_cents == 4_339


@respx.mock
def test_a_capture_without_a_breakdown_leaves_the_fee_unknown(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """An order PayPal has not settled doesn't report a fee, and none is invented."""
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    respx.post(f"{ORDERS_URL}/ORDER1/capture").mock(
        return_value=httpx.Response(201, json=capture_payload(payment))
    )

    api_client.force_login(member)
    api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER1"})

    payment.refresh_from_db()
    assert fees_are_known(payment) is False


def test_a_breakdown_that_is_not_a_number_does_not_report_a_fee() -> None:
    """A fee PayPal sends as something other than a decimal is refused, not guessed."""
    capture = {
        "seller_receivable_breakdown": {
            "paypal_fee": {"value": "not-a-number"},
            "net_amount": {"value": "43.39"},
        }
    }

    assert paypal_orders.fees_from_capture(capture) is None


@respx.mock
def test_a_verified_capture_webhook_records_the_fee(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, settings: Settings
) -> None:
    """The breakdown on a verified capture notification is recorded too."""
    settings.PAYPAL_WEBHOOK_ID = "WH-CONFIG"
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    respx.post(f"{SANDBOX}/v1/notifications/verify-webhook-signature").mock(
        return_value=httpx.Response(200, json={"verification_status": "SUCCESS"})
    )
    event = webhook_event(payment)
    event["resource"]["seller_receivable_breakdown"] = {
        "paypal_fee": {"value": "1.61"},
        "net_amount": {"value": "43.39"},
    }

    post_webhook(api_client, event)

    payment.refresh_from_db()
    assert payment.fee_cents == 161


@respx.mock
def test_fetch_fees_reads_the_order_again(member: User, annual_plan: MembershipPlan) -> None:
    """Asking PayPal what a settled order cost reads the breakdown off the order."""
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    respx.get(f"{ORDERS_URL}/ORDER1").mock(
        return_value=httpx.Response(200, json=with_breakdown(capture_payload(payment)))
    )

    fees = paypal.PayPalProvider().fetch_fees(payment)

    assert fees == ProviderFees(fee_cents=161, net_cents=4_339)


def test_fetch_fees_for_a_payment_without_an_order_does_not_ask_anything(
    member: User, annual_plan: MembershipPlan
) -> None:
    """A payment that never reached PayPal doesn't have anything to ask about."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.PAYPAL)

    assert paypal.PayPalProvider().fetch_fees(payment) is None


# --------------------------------------------------------------------------
# refunds
# --------------------------------------------------------------------------
def captured_paypal_payment(member: User, capture_id: str = "CAPTURE-1") -> Payment:
    """A succeeded PayPal payment whose stored capture response names ``capture_id``."""
    payment = pending_paypal_payment(member)
    payment.status = PaymentStatus.SUCCEEDED
    payment.raw = capture_payload(payment)
    payment.raw["purchase_units"][0]["payments"]["captures"][0]["id"] = capture_id
    payment.save(update_fields=["status", "raw"])
    return payment


def refund_route(mock: respx.MockRouter, capture_id: str, refund_id: str) -> respx.Route:
    """Mock the refund of one capture, answering with a completed refund."""
    return mock.post(f"{SANDBOX}/v2/payments/captures/{capture_id}/refund").mock(
        return_value=httpx.Response(201, json={"id": refund_id, "status": "COMPLETED"})
    )


@respx.mock
def test_a_refund_posts_the_amount_against_the_capture(
    member: User, annual_plan: MembershipPlan, account_admin: User
) -> None:
    """PayPal refunds a capture, so the call names the capture id and the dollars."""
    payment = captured_paypal_payment(member)
    token_route(respx.mock)
    route = refund_route(respx.mock, "CAPTURE-1", "REFUND-1")

    issue_refund(payment, amount_cents=1_500, reason=RefundReason.ERROR, actor=account_admin)

    body = json.loads(route.calls.last.request.content)
    assert body["amount"] == {"currency_code": "USD", "value": "15.00"}


@respx.mock
def test_a_refund_keeps_the_paypal_refund_id(
    member: User, annual_plan: MembershipPlan, account_admin: User
) -> None:
    """The provider reference is what a later webhook is recognized by."""
    payment = captured_paypal_payment(member)
    token_route(respx.mock)
    refund_route(respx.mock, "CAPTURE-1", "REFUND-1")

    refund = issue_refund(
        payment, amount_cents=1_500, reason=RefundReason.ERROR, actor=account_admin
    )

    assert refund.provider_ref == "REFUND-1"


@respx.mock
def test_a_refund_of_a_payment_without_a_capture_is_refused(
    member: User, annual_plan: MembershipPlan, account_admin: User
) -> None:
    """Without a capture id, there isn't anything to refund against."""
    payment = pending_paypal_payment(member)
    payment.status = PaymentStatus.SUCCEEDED
    payment.save(update_fields=["status"])

    with pytest.raises(PaymentVerificationError, match="doesn't have a completed PayPal capture"):
        issue_refund(payment, amount_cents=1_500, reason=RefundReason.ERROR, actor=account_admin)

    assert Refund.objects.get().status == RefundStatus.FAILED


@respx.mock
def test_a_refund_paypal_rejects_leaves_the_refund_failed(
    member: User, annual_plan: MembershipPlan, account_admin: User
) -> None:
    """PayPal refusing the refund keeps the attempt on the record."""
    payment = captured_paypal_payment(member)
    token_route(respx.mock)
    respx.post(f"{SANDBOX}/v2/payments/captures/CAPTURE-1/refund").mock(
        return_value=httpx.Response(422, json={"message": "REFUND_CAPTURE_CURRENCY_MISMATCH"})
    )

    with pytest.raises(PaymentVerificationError, match="REFUND_CAPTURE_CURRENCY_MISMATCH"):
        issue_refund(payment, amount_cents=1_500, reason=RefundReason.ERROR, actor=account_admin)

    assert Refund.objects.get().status == RefundStatus.FAILED


# --- PAYMENT.CAPTURE.REFUNDED ---------------------------------------------
def refund_event(payment: Payment, refund_id: str, amount_cents: int) -> dict[str, Any]:
    """A ``PAYMENT.CAPTURE.REFUNDED`` payload for ``payment``."""
    return {
        "id": "WH-REFUND",
        "event_type": "PAYMENT.CAPTURE.REFUNDED",
        "resource": {
            "id": refund_id,
            "custom_id": str(payment.pk),
            "status": "COMPLETED",
            "amount": {"currency_code": "USD", "value": f"{amount_cents / 100:.2f}"},
        },
    }


def verification_route(mock: respx.MockRouter, status: str = "SUCCESS") -> respx.Route:
    """Mock PayPal's webhook-signature verification with ``status``."""
    return mock.post(f"{SANDBOX}/v1/notifications/verify-webhook-signature").mock(
        return_value=httpx.Response(200, json={"verification_status": status})
    )


@respx.mock
def test_a_verified_refund_webhook_records_the_refund(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, settings: Settings
) -> None:
    """Somebody refunding in PayPal's dashboard still lands in the ledger."""
    settings.PAYPAL_WEBHOOK_ID = "WH-CONFIG"
    payment = captured_paypal_payment(member)
    token_route(respx.mock)
    verification_route(respx.mock)

    response = post_webhook(api_client, refund_event(payment, "REFUND-DASH", 1_000))

    assert json.loads(response.content)["handled"] is True
    refund = Refund.objects.get()
    assert refund.amount_cents == 1_000
    assert refund.provider_ref == "REFUND-DASH"


@respx.mock
def test_a_verified_refund_webhook_updates_the_payment(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, settings: Settings
) -> None:
    """A full refund taken in the dashboard leaves the payment refunded here."""
    settings.PAYPAL_WEBHOOK_ID = "WH-CONFIG"
    payment = captured_paypal_payment(member)
    token_route(respx.mock)
    verification_route(respx.mock)

    post_webhook(api_client, refund_event(payment, "REFUND-FULL", payment.amount_cents))

    payment.refresh_from_db()
    assert payment.status == PaymentStatus.REFUNDED


@respx.mock
def test_a_refund_in_another_currency_does_not_record_anything(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, settings: Settings
) -> None:
    """A verified refund naming the payment in another currency doesn't file a refund."""
    settings.PAYPAL_WEBHOOK_ID = "WH-CONFIG"
    payment = captured_paypal_payment(member)
    token_route(respx.mock)
    verification_route(respx.mock)
    event = refund_event(payment, "REFUND-YEN", 1_000)
    event["resource"]["amount"]["currency_code"] = "JPY"

    post_webhook(api_client, event)

    assert Refund.objects.count() == 0


@respx.mock
def test_a_refund_of_a_payment_that_never_settled_does_not_record_anything(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, settings: Settings
) -> None:
    """A verified refund of a payment CalDART never saw settle doesn't file a refund."""
    settings.PAYPAL_WEBHOOK_ID = "WH-CONFIG"
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    verification_route(respx.mock)

    post_webhook(api_client, refund_event(payment, "REFUND-EARLY", 1_000))

    assert Refund.objects.count() == 0


@respx.mock
def test_a_second_delivery_of_the_refund_webhook_does_not_record_anything(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, settings: Settings
) -> None:
    """PayPal retries a notification, and the refund id makes that harmless."""
    settings.PAYPAL_WEBHOOK_ID = "WH-CONFIG"
    payment = captured_paypal_payment(member)
    token_route(respx.mock)
    verification_route(respx.mock)
    event = refund_event(payment, "REFUND-TWICE", 1_000)

    post_webhook(api_client, event)
    post_webhook(api_client, event)

    assert Refund.objects.count() == 1


@respx.mock
def test_an_unverified_refund_webhook_does_not_record_anything(
    api_client: APIClient, member: User, annual_plan: MembershipPlan, settings: Settings
) -> None:
    """A refund notification PayPal does not vouch for doesn't file a refund."""
    settings.PAYPAL_WEBHOOK_ID = "WH-CONFIG"
    payment = captured_paypal_payment(member)
    token_route(respx.mock)
    verification_route(respx.mock, status="FAILURE")

    post_webhook(api_client, refund_event(payment, "REFUND-UNVERIFIED", 1_000))

    assert Refund.objects.count() == 0
