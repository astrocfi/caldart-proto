"""PayPal Orders v2 over ``httpx``, with the HTTP layer mocked by respx.

Covers the token cache, order creation, capture (happy path and every way it
can go wrong) and the webhook's deliberately cautious behavior.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import timedelta
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
from apps.payments.models import (
    Payment,
    PaymentProvider,
    PaymentStatus,
    PaymentWallet,
    Refund,
    RefundReason,
    RefundStatus,
)
from apps.payments.providers import paypal
from apps.payments.providers.base import (
    PaymentVerificationError,
    ProviderFees,
    ProviderNotConfiguredError,
)
from apps.payments.refunds import issue_refund
from apps.payments.services import create_checkout, fees_are_known
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


def order_payload(order_id: str = "ORDER-1", status: str = "CREATED") -> dict[str, Any]:
    """A PayPal order creation response body."""
    return {"id": order_id, "status": status, "links": []}


def capture_payload(
    payment: Payment,
    *,
    order_id: str = "ORDER-1",
    status: str = "COMPLETED",
    capture_status: str = "COMPLETED",
    value: str | None = None,
    currency: str = "USD",
    custom_id: str | None = None,
) -> dict[str, Any]:
    """A PayPal order-capture response body naming ``payment`` in its custom id.

    The single capture carries ``payment.pk`` as its custom id; ``custom_id=...``
    replaces it with any other value, so a caller can point the body at a different
    payment or at no payment at all.
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
        paypal.access_token()


# --------------------------------------------------------------------------
# OAuth token
# --------------------------------------------------------------------------
@respx.mock
def test_the_token_is_fetched_once_and_cached() -> None:
    """The OAuth token is fetched once and reused from cache on a second call."""
    route = token_route(respx.mock)
    assert paypal.access_token() == "A21AA-token"
    assert paypal.access_token() == "A21AA-token"
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
        assert paypal.access_token() == "A21AA-token"

        clock.tick(timedelta(seconds=TOKEN_LIFETIME_SECONDS - paypal.TOKEN_SKEW_SECONDS - 1))
        assert paypal.access_token() == "A21AA-token"
        assert route.call_count == 1

        clock.tick(timedelta(seconds=2))
        assert paypal.access_token() == "A21AA-token"
        assert route.call_count == 2


@respx.mock
def test_emptying_the_cache_fetches_a_fresh_token() -> None:
    """Emptying Django's cache forces a fresh fetch on the next call."""
    route = token_route(respx.mock, expires_in=0)
    paypal.access_token()
    paypal.access_token()
    # expires_in=0 still leaves the 30s floor, so the cache holds.
    assert route.call_count == 1

    cache.clear()
    paypal.access_token()
    assert route.call_count == 2


@respx.mock
def test_bad_credentials_raise() -> None:
    """A 401 from the token endpoint raises PaymentVerificationError."""
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(401, json={"error": "invalid_client"}))
    with pytest.raises(PaymentVerificationError, match=r"refused our credentials \(HTTP 401\)"):
        paypal.access_token()


def test_missing_credentials_raise(settings: Settings) -> None:
    """Fetching a token with no client id configured raises ProviderNotConfiguredError."""
    settings.PAYPAL_CLIENT_ID = ""
    with pytest.raises(
        ProviderNotConfiguredError,
        match=r"PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET are empty",
    ):
        paypal.access_token()


def test_the_live_environment_uses_the_live_host(settings: Settings) -> None:
    """PAYPAL_ENV selects the live or sandbox API host."""
    settings.PAYPAL_ENV = "live"
    assert paypal.api_base() == "https://api-m.paypal.com"
    settings.PAYPAL_ENV = "sandbox"
    assert paypal.api_base() == SANDBOX


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
        return_value=httpx.Response(201, json=order_payload("ORDER-XYZ"))
    )

    api_client.force_login(member)
    response = api_client.post(
        CHECKOUT, {"plan": "annual", "contribution_cents": 2_000, "provider": "paypal"}
    )

    assert response.status_code == 201
    assert response.json()["client"] == {"order_id": "ORDER-XYZ"}

    payment = Payment.objects.get(pk=response.json()["payment_id"])
    assert payment.provider_ref == "ORDER-XYZ"

    body = json.loads(route.calls[0].request.content)
    unit = body["purchase_units"][0]
    assert body["intent"] == "CAPTURE"
    assert unit["amount"] == {"currency_code": "USD", "value": "65.00"}
    assert unit["custom_id"] == str(payment.pk)
    assert body["payment_source"]["paypal"]["experience_context"]["brand_name"] == "CalDART"
    assert route.calls[0].request.headers["authorization"] == "Bearer A21AA-token"


@respx.mock
def test_a_rejected_order_leaves_no_payment_behind(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """An order PayPal rejects is a 400 and creates no payment."""
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
def pending_paypal_payment(member: User, order_id: str = "ORDER-1") -> Payment:
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
    route = respx.post(f"{ORDERS_URL}/ORDER-1/capture").mock(
        return_value=httpx.Response(201, json=capture_payload(payment))
    )

    api_client.force_login(member)
    response = api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER-1"})

    assert response.status_code == 200
    assert response.json()["status"] == "succeeded"
    assert response.json()["membership"]["status"] == "current"
    assert route.call_count == 1

    payment.refresh_from_db()
    assert payment.wallet == PaymentWallet.PAYPAL
    assert payment.completed_at is not None
    assert Membership.objects.filter(payment=payment).count() == 1


@respx.mock
def test_capture_that_is_not_completed_grants_nothing(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A capture whose status is not COMPLETED fails the payment and grants nothing."""
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    respx.post(f"{ORDERS_URL}/ORDER-1/capture").mock(
        return_value=httpx.Response(
            201, json=capture_payload(payment, status="PAYER_ACTION_REQUIRED")
        )
    )

    api_client.force_login(member)
    response = api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER-1"})

    assert response.status_code == 400
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.FAILED
    assert Membership.objects.count() == 0


@respx.mock
def test_capture_of_the_wrong_amount_is_refused(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A capture whose amount does not match the payment is refused."""
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    respx.post(f"{ORDERS_URL}/ORDER-1/capture").mock(
        return_value=httpx.Response(201, json=capture_payload(payment, value="1.00"))
    )

    api_client.force_login(member)
    response = api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER-1"})

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
    respx.post(f"{ORDERS_URL}/ORDER-1/capture").mock(
        return_value=httpx.Response(201, json=capture_payload(payment, currency="CAD"))
    )

    api_client.force_login(member)
    assert (
        api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER-1"}).status_code
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
    respx.post(f"{ORDERS_URL}/ORDER-1/capture").mock(
        return_value=httpx.Response(201, json=capture_payload(payment, custom_id=str(other.pk)))
    )

    api_client.force_login(member)
    assert (
        api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER-1"}).status_code
        == 400
    )
    assert Membership.objects.count() == 0


@respx.mock
def test_completed_order_without_a_capture_is_refused(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """An order without a completed capture is refused and marks the payment failed."""
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    respx.post(f"{ORDERS_URL}/ORDER-1/capture").mock(
        return_value=httpx.Response(201, json=capture_payload(payment, capture_status="DECLINED"))
    )

    api_client.force_login(member)
    assert (
        api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER-1"}).status_code
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
    response = api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER-OTHER"})
    assert response.status_code == 400


@respx.mock
def test_capturing_twice_grants_one_term(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """Capturing the same payment twice grants exactly one membership term."""
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    route = respx.post(f"{ORDERS_URL}/ORDER-1/capture").mock(
        return_value=httpx.Response(201, json=capture_payload(payment))
    )

    api_client.force_login(member)
    body = {"payment_id": payment.pk, "order_id": "ORDER-1"}
    assert api_client.post(CAPTURE, body).status_code == 200
    assert api_client.post(CAPTURE, body).status_code == 200

    # The second call short-circuits before PayPal is asked again.
    assert route.call_count == 1
    assert Membership.objects.filter(user=member).count() == 1


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
    response = api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER-1"})
    assert response.status_code == 404


# --------------------------------------------------------------------------
# webhook
# --------------------------------------------------------------------------
def webhook_event(
    payment: Payment, event_type: str = "PAYMENT.CAPTURE.COMPLETED"
) -> dict[str, Any]:
    """A PayPal webhook payload of ``event_type`` for ``payment``."""
    return {
        "id": "WH-1",
        "event_type": event_type,
        "resource": {
            "id": "CAPTURE-1",
            "custom_id": str(payment.pk),
            "status": "COMPLETED",
            "amount": {"currency_code": "USD", "value": f"{payment.amount_cents / 100:.2f}"},
        },
    }


def post_webhook(client: APIClient, body: dict[str, Any]) -> Response:
    """POST the body to the PayPal webhook endpoint as JSON, with no signature headers."""
    return client.post(WEBHOOK, data=json.dumps(body), content_type="application/json")


def test_an_unverified_webhook_only_records(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """With no webhook id configured, the event is recorded but never verified."""
    payment = pending_paypal_payment(member)
    response = post_webhook(api_client, webhook_event(payment))

    assert response.status_code == 200
    body = json.loads(response.content)
    assert body == {"received": True, "verified": False, "handled": False}

    payment.refresh_from_db()
    assert payment.status == PaymentStatus.PENDING
    assert payment.raw["last_webhook"]["event_type"] == "PAYMENT.CAPTURE.COMPLETED"
    assert Membership.objects.count() == 0


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
    assert json.loads(response.content)["verified"] is False
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.PENDING


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


def test_a_webhook_for_an_unknown_payment_is_accepted(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A webhook naming a payment id that does not exist is accepted but unhandled."""
    response = post_webhook(
        api_client,
        {"event_type": "PAYMENT.CAPTURE.COMPLETED", "resource": {"custom_id": "9999"}},
    )
    assert response.status_code == 200
    assert json.loads(response.content)["handled"] is False


def test_a_malformed_webhook_is_a_400(api_client: APIClient) -> None:
    """A body that is not valid JSON is refused with a 400."""
    response = api_client.post(WEBHOOK, data="not json", content_type="application/json")
    assert response.status_code == 400


def test_the_webhook_finds_the_payment_by_order_id(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A webhook is matched to its payment by order id when there is no custom id."""
    payment = pending_paypal_payment(member, order_id="ORDER-REF")
    response = post_webhook(
        api_client,
        {
            "event_type": "PAYMENT.CAPTURE.COMPLETED",
            "resource": {
                "id": "CAPTURE-9",
                "supplementary_data": {"related_ids": {"order_id": "ORDER-REF"}},
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
    respx.post(f"{ORDERS_URL}/ORDER-1/capture").mock(
        return_value=httpx.Response(201, json=with_breakdown(capture_payload(payment)))
    )

    api_client.force_login(member)
    api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER-1"})

    payment.refresh_from_db()
    assert payment.fee_cents == 161


@respx.mock
def test_capture_records_the_net_from_the_seller_breakdown(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The net PayPal reports is stored as reported."""
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    respx.post(f"{ORDERS_URL}/ORDER-1/capture").mock(
        return_value=httpx.Response(201, json=with_breakdown(capture_payload(payment)))
    )

    api_client.force_login(member)
    api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER-1"})

    payment.refresh_from_db()
    assert payment.net_cents == 4_339


@respx.mock
def test_a_capture_without_a_breakdown_leaves_the_fee_unknown(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """An order PayPal has not settled reports no fee, and none is invented."""
    payment = pending_paypal_payment(member)
    token_route(respx.mock)
    respx.post(f"{ORDERS_URL}/ORDER-1/capture").mock(
        return_value=httpx.Response(201, json=capture_payload(payment))
    )

    api_client.force_login(member)
    api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER-1"})

    payment.refresh_from_db()
    assert fees_are_known(payment) is False


def test_a_breakdown_that_is_not_a_number_reports_no_fee() -> None:
    """A fee PayPal sends as something other than a decimal is refused, not guessed."""
    capture = {
        "seller_receivable_breakdown": {
            "paypal_fee": {"value": "not-a-number"},
            "net_amount": {"value": "43.39"},
        }
    }

    assert paypal.fees_from_capture(capture) is None


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
    respx.get(f"{ORDERS_URL}/ORDER-1").mock(
        return_value=httpx.Response(200, json=with_breakdown(capture_payload(payment)))
    )

    fees = paypal.PayPalProvider().fetch_fees(payment)

    assert fees == ProviderFees(fee_cents=161, net_cents=4_339)


def test_fetch_fees_for_a_payment_with_no_order_asks_nothing(
    member: User, annual_plan: MembershipPlan
) -> None:
    """A payment that never reached PayPal has nothing to ask about."""
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
def test_a_refund_of_a_payment_with_no_capture_is_refused(
    member: User, annual_plan: MembershipPlan, account_admin: User
) -> None:
    """Without a capture id there is nothing to refund against."""
    payment = pending_paypal_payment(member)
    payment.status = PaymentStatus.SUCCEEDED
    payment.save(update_fields=["status"])

    with pytest.raises(PaymentVerificationError, match="no completed PayPal capture"):
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
def test_a_second_delivery_of_the_refund_webhook_records_nothing(
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
def test_an_unverified_refund_webhook_records_nothing(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """Without a webhook id the notification is filed and acted on by nobody."""
    payment = captured_paypal_payment(member)

    response = post_webhook(api_client, refund_event(payment, "REFUND-UNVERIFIED", 1_000))

    assert json.loads(response.content)["verified"] is False
    assert Refund.objects.count() == 0
