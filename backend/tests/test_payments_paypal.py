"""PayPal Orders v2 over ``httpx``, with the HTTP layer mocked by respx.

Covers the token cache, order creation, capture (happy path and every way it
can go wrong) and the webhook's deliberately cautious behaviour.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from apps.members.models import Membership
from apps.payments.models import Payment, PaymentProvider, PaymentStatus, PaymentWallet
from apps.payments.providers import paypal
from apps.payments.services import create_checkout

pytestmark = pytest.mark.django_db

CHECKOUT = "/api/v1/payments/checkout"
CAPTURE = "/api/v1/payments/paypal/capture"
WEBHOOK = "/api/v1/payments/paypal/webhook"

SANDBOX = "https://api-m.sandbox.paypal.com"
TOKEN_URL = f"{SANDBOX}/v1/oauth2/token"
ORDERS_URL = f"{SANDBOX}/v2/checkout/orders"


@pytest.fixture(autouse=True)
def _paypal_configured(settings):
    settings.PAYPAL_CLIENT_ID = "client-id"
    settings.PAYPAL_CLIENT_SECRET = "client-secret"  # noqa: S105 - test fixture
    settings.PAYPAL_ENV = "sandbox"
    settings.PAYPAL_WEBHOOK_ID = ""
    settings.PAYMENTS_MOCK_ENABLED = True
    paypal.reset_token_cache()
    yield
    paypal.reset_token_cache()


def token_route(mock, expires_in: int = 32_400):
    return mock.post(TOKEN_URL).mock(
        return_value=httpx.Response(
            200, json={"access_token": "A21AA-token", "expires_in": expires_in}
        )
    )


def order_payload(order_id: str = "ORDER-1", status: str = "CREATED") -> dict:
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
) -> dict:
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
# OAuth token
# --------------------------------------------------------------------------
@respx.mock
def test_the_token_is_fetched_once_and_cached():
    route = token_route(respx)
    assert paypal.access_token() == "A21AA-token"
    assert paypal.access_token() == "A21AA-token"
    assert route.call_count == 1

    request = route.calls[0].request
    assert request.headers["authorization"].startswith("Basic ")
    assert b"grant_type=client_credentials" in request.content


@respx.mock
def test_an_expired_token_is_fetched_again():
    route = token_route(respx, expires_in=0)
    paypal.access_token()
    paypal.access_token()
    # expires_in=0 still leaves the 30s floor, so the cache holds.
    assert route.call_count == 1

    paypal.reset_token_cache()
    paypal.access_token()
    assert route.call_count == 2


@respx.mock
def test_bad_credentials_raise():
    respx.post(TOKEN_URL).mock(return_value=httpx.Response(401, json={"error": "invalid_client"}))
    with pytest.raises(paypal.PaymentVerificationError):
        paypal.access_token()


def test_missing_credentials_raise(settings):
    settings.PAYPAL_CLIENT_ID = ""
    with pytest.raises(paypal.ProviderNotConfigured):
        paypal.access_token()


def test_the_live_environment_uses_the_live_host(settings):
    settings.PAYPAL_ENV = "live"
    assert paypal.api_base() == "https://api-m.paypal.com"
    settings.PAYPAL_ENV = "sandbox"
    assert paypal.api_base() == SANDBOX


# --------------------------------------------------------------------------
# create order
# --------------------------------------------------------------------------
@respx.mock
def test_checkout_creates_a_paypal_order(api_client, member, annual_plan):
    token_route(respx)
    route = respx.post(ORDERS_URL).mock(
        return_value=httpx.Response(201, json=order_payload("ORDER-XYZ"))
    )

    api_client.force_login(member)
    response = api_client.post(
        CHECKOUT, {"plan": "annual", "contribution_cents": 2_000, "provider": "paypal"}
    )

    assert response.status_code == 201
    assert response.data["client"] == {"order_id": "ORDER-XYZ"}

    payment = Payment.objects.get(pk=response.data["payment_id"])
    assert payment.provider_ref == "ORDER-XYZ"

    body = json.loads(route.calls[0].request.content)
    unit = body["purchase_units"][0]
    assert body["intent"] == "CAPTURE"
    assert unit["amount"] == {"currency_code": "USD", "value": "65.00"}
    assert unit["custom_id"] == str(payment.pk)
    assert body["payment_source"]["paypal"]["experience_context"]["brand_name"] == "CalDART"
    assert route.calls[0].request.headers["authorization"] == "Bearer A21AA-token"


@respx.mock
def test_a_rejected_order_leaves_no_payment_behind(api_client, member, annual_plan):
    token_route(respx)
    respx.post(ORDERS_URL).mock(
        return_value=httpx.Response(422, json={"message": "AMOUNT_MISMATCH"})
    )

    api_client.force_login(member)
    response = api_client.post(
        CHECKOUT, {"plan": "annual", "contribution_cents": 0, "provider": "paypal"}
    )

    assert response.status_code == 400
    assert "AMOUNT_MISMATCH" in str(response.data)
    assert Payment.objects.count() == 0


# --------------------------------------------------------------------------
# capture
# --------------------------------------------------------------------------
def pending_paypal_payment(member, order_id: str = "ORDER-1") -> Payment:
    payment = create_checkout(member, "annual", 0, PaymentProvider.PAYPAL)
    payment.provider_ref = order_id
    payment.save(update_fields=["provider_ref"])
    return payment


@respx.mock
def test_capture_activates_the_membership(api_client, member, annual_plan):
    payment = pending_paypal_payment(member)
    token_route(respx)
    route = respx.post(f"{ORDERS_URL}/ORDER-1/capture").mock(
        return_value=httpx.Response(201, json=capture_payload(payment))
    )

    api_client.force_login(member)
    response = api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER-1"})

    assert response.status_code == 200
    assert response.data["status"] == "succeeded"
    assert response.data["membership"]["status"] == "current"
    assert route.call_count == 1

    payment.refresh_from_db()
    assert payment.wallet == PaymentWallet.PAYPAL
    assert payment.completed_at is not None
    assert Membership.objects.filter(payment=payment).count() == 1


@respx.mock
def test_capture_that_is_not_completed_grants_nothing(api_client, member, annual_plan):
    payment = pending_paypal_payment(member)
    token_route(respx)
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
def test_capture_of_the_wrong_amount_is_refused(api_client, member, annual_plan):
    payment = pending_paypal_payment(member)
    token_route(respx)
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
def test_capture_in_another_currency_is_refused(api_client, member, annual_plan):
    payment = pending_paypal_payment(member)
    token_route(respx)
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
def test_capture_for_another_payment_is_refused(api_client, member, annual_plan):
    payment = pending_paypal_payment(member)
    other = create_checkout(member, "annual", 0, PaymentProvider.PAYPAL)
    token_route(respx)
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
def test_completed_order_without_a_capture_is_refused(api_client, member, annual_plan):
    payment = pending_paypal_payment(member)
    token_route(respx)
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


def test_capture_of_an_order_id_we_did_not_issue_is_refused(api_client, member, annual_plan):
    payment = pending_paypal_payment(member)
    api_client.force_login(member)
    response = api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER-OTHER"})
    assert response.status_code == 400


@respx.mock
def test_capturing_twice_grants_one_term(api_client, member, annual_plan):
    payment = pending_paypal_payment(member)
    token_route(respx)
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


def test_capture_requires_a_session(api_client, member, annual_plan):
    payment = pending_paypal_payment(member)
    assert api_client.post(CAPTURE, {"payment_id": payment.pk}).status_code == 401


def test_capture_rejects_someone_elses_payment(api_client, member, user_factory, annual_plan):
    payment = pending_paypal_payment(member)
    api_client.force_login(user_factory(email="thief@example.test", roles=["member"]))
    response = api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER-1"})
    assert response.status_code == 404


# --------------------------------------------------------------------------
# webhook
# --------------------------------------------------------------------------
def webhook_event(payment: Payment, event_type: str = "PAYMENT.CAPTURE.COMPLETED") -> dict:
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


def post_webhook(client, body: dict):
    return client.post(WEBHOOK, data=json.dumps(body), content_type="application/json")


def test_an_unverified_webhook_only_records(api_client, member, annual_plan):
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
def test_a_verified_webhook_activates_the_membership(api_client, member, annual_plan, settings):
    settings.PAYPAL_WEBHOOK_ID = "WH-CONFIG"
    payment = pending_paypal_payment(member)
    token_route(respx)
    respx.post(f"{SANDBOX}/v1/notifications/verify-webhook-signature").mock(
        return_value=httpx.Response(200, json={"verification_status": "SUCCESS"})
    )

    response = post_webhook(api_client, webhook_event(payment))
    assert json.loads(response.content)["handled"] is True

    payment.refresh_from_db()
    assert payment.status == PaymentStatus.SUCCEEDED
    assert Membership.objects.filter(payment=payment).count() == 1


@respx.mock
def test_a_failed_verification_does_not_activate(api_client, member, annual_plan, settings):
    settings.PAYPAL_WEBHOOK_ID = "WH-CONFIG"
    payment = pending_paypal_payment(member)
    token_route(respx)
    respx.post(f"{SANDBOX}/v1/notifications/verify-webhook-signature").mock(
        return_value=httpx.Response(200, json={"verification_status": "FAILURE"})
    )

    response = post_webhook(api_client, webhook_event(payment))
    assert json.loads(response.content)["verified"] is False
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.PENDING


@respx.mock
def test_a_verified_webhook_of_the_wrong_amount_is_ignored(
    api_client, member, annual_plan, settings
):
    settings.PAYPAL_WEBHOOK_ID = "WH-CONFIG"
    payment = pending_paypal_payment(member)
    token_route(respx)
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
def test_a_verified_denial_marks_the_payment_failed(api_client, member, annual_plan, settings):
    settings.PAYPAL_WEBHOOK_ID = "WH-CONFIG"
    payment = pending_paypal_payment(member)
    token_route(respx)
    respx.post(f"{SANDBOX}/v1/notifications/verify-webhook-signature").mock(
        return_value=httpx.Response(200, json={"verification_status": "SUCCESS"})
    )

    post_webhook(api_client, webhook_event(payment, "PAYMENT.CAPTURE.DENIED"))
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.FAILED


def test_a_webhook_for_an_unknown_payment_is_accepted(api_client, member, annual_plan):
    response = post_webhook(
        api_client,
        {"event_type": "PAYMENT.CAPTURE.COMPLETED", "resource": {"custom_id": "9999"}},
    )
    assert response.status_code == 200
    assert json.loads(response.content)["handled"] is False


def test_a_malformed_webhook_is_a_400(api_client):
    response = api_client.post(WEBHOOK, data="not json", content_type="application/json")
    assert response.status_code == 400


def test_the_webhook_finds_the_payment_by_order_id(api_client, member, annual_plan):
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
