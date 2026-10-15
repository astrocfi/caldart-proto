"""A PayPal answer that is silent on the request reads as PayPal not answering.

``docs/developer/api-payments.rst`` and ``docs/developer/payments-setup.rst`` are the
contract.  A 5xx, a 429 and a 408 may follow work PayPal has already done, so every
caller of ``apps.payments.providers.paypal_api.call`` treats one as an outage -- a 400
reading "PayPal didn't answer" for a person, a charge put off for the scanner -- and
never as PayPal refusing the request.  PayPal is intercepted with ``respx``.
"""

from __future__ import annotations

import httpx
import pytest
import respx
from django.test import RequestFactory
from pytest_django.fixtures import Settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.members.models import MembershipPlan
from apps.payments import refunds
from apps.payments.models import Payment, PaymentProvider, PaymentStatus, RefundStatus
from apps.payments.providers import paypal_api
from apps.payments.providers.base import ProviderUnavailableError
from apps.payments.providers.paypal import PayPalProvider
from apps.payments.services import create_checkout, mark_succeeded
from tests.conftest import PAYPAL_SANDBOX, paypal_token

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("paypal_sandbox")]

CHECKOUT = "/api/v1/payments/checkout"
CAPTURE = "/api/v1/payments/paypal/capture"
ORDERS = f"{PAYPAL_SANDBOX}/v2/checkout/orders"

#: The statuses that don't say anything about the request: PayPal's faults, a rate limit,
#: a request that timed out at PayPal.
TRANSIENT = [500, 502, 503, 504, 429, 408]


def pending_order(member: User) -> Payment:
    """A pending PayPal checkout whose order PayPal has already made."""
    payment = create_checkout(member, "annual", 0, PaymentProvider.PAYPAL)
    Payment.objects.filter(pk=payment.pk).update(provider_ref="ORDER1")
    payment.refresh_from_db()
    return payment


@pytest.mark.parametrize("status", TRANSIENT)
def test_a_transient_status_from_paypal_is_an_outage(status: int) -> None:
    """``call`` raises the outage error, not the refusal one, for each such status."""
    with respx.mock as router:
        paypal_token(router)
        router.get(f"{ORDERS}/ORDER1").mock(return_value=httpx.Response(status, json={}))
        with pytest.raises(ProviderUnavailableError, match="PayPal didn't answer"):
            paypal_api.call("GET", "/v2/checkout/orders/ORDER1")


def test_a_refusal_about_the_request_is_still_a_refusal() -> None:
    """A 422 is PayPal's answer about the request, and carries its issue codes."""
    body = {"name": "UNPROCESSABLE_ENTITY", "details": [{"issue": "DUPLICATE_INVOICE_ID"}]}
    with respx.mock as router:
        paypal_token(router)
        router.post(ORDERS).mock(return_value=httpx.Response(422, json=body))
        with pytest.raises(paypal_api.PayPalRequestError) as refused:
            paypal_api.call("POST", "/v2/checkout/orders", json_body={})

    assert refused.value.issues == ["DUPLICATE_INVOICE_ID"]


def test_a_token_call_paypal_cannot_answer_is_an_outage() -> None:
    """A 503 fetching the token is PayPal being down, not our credentials refused."""
    with respx.mock as router:
        router.post(f"{PAYPAL_SANDBOX}/v1/oauth2/token").mock(return_value=httpx.Response(503))
        with pytest.raises(ProviderUnavailableError, match="PayPal didn't answer"):
            paypal_api.access_token()


def test_a_checkout_order_paypal_cannot_answer_is_a_400(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The member is told to try again, and nothing is left behind."""
    api_client.force_login(member)
    with respx.mock as router:
        paypal_token(router)
        router.post(ORDERS).mock(return_value=httpx.Response(503))
        response = api_client.post(
            CHECKOUT, {"plan": "annual", "contribution_cents": 0, "provider": "paypal"}
        )

    assert response.status_code == 400
    assert response.json()["detail"] == paypal_api.UNAVAILABLE_MESSAGE
    assert Payment.objects.count() == 0


def test_a_capture_paypal_cannot_answer_leaves_the_payment_pending(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The money may have moved, so the payment is neither failed nor paid."""
    payment = pending_order(member)
    api_client.force_login(member)
    with respx.mock as router:
        paypal_token(router)
        router.post(f"{ORDERS}/ORDER1/capture").mock(return_value=httpx.Response(503))
        response = api_client.post(CAPTURE, {"payment_id": payment.pk, "order_id": "ORDER1"})

    payment.refresh_from_db()
    assert response.status_code == 400
    assert payment.status == PaymentStatus.PENDING


def test_a_refund_paypal_cannot_answer_tells_the_treasurer_to_check_first(
    treasurer_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The row is failed, and the treasurer is told to look before trying again."""
    payment = pending_order(member)
    mark_succeeded(
        payment,
        raw={
            "id": "ORDER1",
            "purchase_units": [
                {"payments": {"captures": [{"id": "CAPTURE1", "status": "COMPLETED"}]}}
            ],
        },
    )
    with respx.mock as router:
        paypal_token(router)
        router.post(f"{PAYPAL_SANDBOX}/v2/payments/captures/CAPTURE1/refund").mock(
            return_value=httpx.Response(503)
        )
        response = treasurer_client.post(
            f"/api/v1/admin/payments/{payment.pk}/refunds",
            {"amount_cents": 100, "reason": "error"},
            format="json",
        )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        f"{paypal_api.UNAVAILABLE_MESSAGE} {refunds.CHECK_DASHBOARD_MESSAGE}"
    )
    assert payment.refunds.get().status == RefundStatus.FAILED


def test_a_webhook_check_paypal_cannot_answer_does_not_vouch_for_anything(
    settings: Settings,
) -> None:
    """A 503 from the signature check means the notification is not verified."""
    settings.PAYPAL_WEBHOOK_ID = "WH-1"
    request = RequestFactory().post(
        "/api/v1/payments/paypal/webhook", data="{}", content_type="application/json"
    )
    with respx.mock as router:
        paypal_token(router)
        router.post(f"{PAYPAL_SANDBOX}/v1/notifications/verify-webhook-signature").mock(
            return_value=httpx.Response(503)
        )
        verified = PayPalProvider().verify_signature(request, {})

    assert verified is False


def test_saving_an_account_paypal_cannot_answer_is_a_400(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """Starting a vault setup through an outage tells the member to try again."""
    api_client.force_login(member)
    with respx.mock as router:
        paypal_token(router)
        router.post(f"{PAYPAL_SANDBOX}/v3/vault/setup-tokens").mock(
            return_value=httpx.Response(503)
        )
        response = api_client.post(
            "/api/v1/me/renewal/setup",
            {"plan": annual_plan.slug, "contribution_cents": 0, "provider": "paypal"},
            format="json",
        )

    assert response.status_code == 400
    assert response.json()["detail"] == paypal_api.UNAVAILABLE_MESSAGE


def test_a_paypal_refund_is_keyed_on_its_refund_row(
    treasurer_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A repeat of the same refund row gives the money back once."""
    payment = pending_order(member)
    mark_succeeded(
        payment,
        raw={
            "id": "ORDER1",
            "purchase_units": [
                {"payments": {"captures": [{"id": "CAPTURE1", "status": "COMPLETED"}]}}
            ],
        },
    )
    with respx.mock as router:
        paypal_token(router)
        route = router.post(f"{PAYPAL_SANDBOX}/v2/payments/captures/CAPTURE1/refund").mock(
            return_value=httpx.Response(201, json={"id": "REFUND1", "status": "COMPLETED"})
        )
        treasurer_client.post(
            f"/api/v1/admin/payments/{payment.pk}/refunds",
            {"amount_cents": 100, "reason": "error"},
            format="json",
        )

    refund = payment.refunds.get()
    assert route.calls.last.request.headers["PayPal-Request-Id"] == f"caldart-refund-{refund.pk}"
