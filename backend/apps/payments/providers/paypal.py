"""PayPal provider: Orders v2 REST, called directly with ``httpx`` (PLAN §2).

No SDK — the three calls we need (OAuth token, create order, capture order) are
plain JSON over HTTPS, and the SDK would add a dependency for nothing.

The client-credentials token is cached in-process until shortly before it
expires; the cache is keyed on the environment and client id so changing either
(in tests, or by editing ``.env``) invalidates it.

Capture is authoritative: ``confirm`` only activates a membership when PayPal
answers ``COMPLETED`` *and* the captured amount matches our own row.  The
webhook is a recorder, and only acts when its signature has been verified.
"""

from __future__ import annotations

import json
import logging
from datetime import timedelta

import httpx
from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.utils import timezone

from apps.payments.models import Payment, PaymentProvider, PaymentWallet
from apps.payments.providers.base import (
    PaymentVerificationError,
    Provider,
    ProviderNotConfigured,
    register,
)
from apps.payments.services import mark_failed, mark_succeeded, record_provider_event

log = logging.getLogger(__name__)

LIVE_BASE = "https://api-m.paypal.com"
SANDBOX_BASE = "https://api-m.sandbox.paypal.com"

#: Seconds shaved off the advertised token lifetime, so we never present one
#: that expires mid-flight.
TOKEN_SKEW_SECONDS = 60
TIMEOUT_SECONDS = 20.0

#: Webhook events worth acting on when the signature has been verified.
CAPTURE_COMPLETED = "PAYMENT.CAPTURE.COMPLETED"
CAPTURE_FAILED = frozenset({"PAYMENT.CAPTURE.DENIED", "PAYMENT.CAPTURE.REVERSED"})


def api_base() -> str:
    """Sandbox or live, from ``PAYPAL_ENV``."""
    return LIVE_BASE if settings.PAYPAL_ENV == "live" else SANDBOX_BASE


def credentials() -> tuple[str, str]:
    client_id = settings.PAYPAL_CLIENT_ID
    client_secret = settings.PAYPAL_CLIENT_SECRET
    if not client_id or not client_secret:
        raise ProviderNotConfigured(
            "PayPal is not configured (PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET are empty)."
        )
    return client_id, client_secret


def dollars(cents: int) -> str:
    """PayPal wants a decimal string: 4500 -> ``"45.00"``."""
    return f"{cents / 100:.2f}"


def cents(value: str | float | int) -> int:
    """Inverse of :func:`dollars`, rounded to the nearest cent."""
    return int(round(float(value) * 100))


# --------------------------------------------------------------------------
# OAuth token cache (in-process, PLAN §10)
# --------------------------------------------------------------------------
_token_cache: dict = {"key": None, "token": "", "expires_at": None}


def reset_token_cache() -> None:
    """Forget the cached token.  Used by tests and after a config change."""
    _token_cache.update({"key": None, "token": "", "expires_at": None})


def access_token() -> str:
    """A valid client-credentials token, fetched at most once per lifetime."""
    client_id, client_secret = credentials()
    key = (api_base(), client_id)
    now = timezone.now()
    if (
        _token_cache["key"] == key
        and _token_cache["token"]
        and _token_cache["expires_at"] is not None
        and _token_cache["expires_at"] > now
    ):
        return _token_cache["token"]

    response = httpx.post(
        f"{api_base()}/v1/oauth2/token",
        auth=(client_id, client_secret),
        data={"grant_type": "client_credentials"},
        headers={"Accept": "application/json"},
        timeout=TIMEOUT_SECONDS,
    )
    if response.status_code != 200:
        raise PaymentVerificationError(
            f"PayPal refused our credentials (HTTP {response.status_code})."
        )
    body = response.json()
    token = body.get("access_token") or ""
    if not token:
        raise PaymentVerificationError("PayPal returned no access token.")

    _token_cache.update(
        {
            "key": key,
            "token": token,
            "expires_at": now
            + timedelta(seconds=max(int(body.get("expires_in", 0)) - TOKEN_SKEW_SECONDS, 30)),
        }
    )
    return token


def call(method: str, path: str, *, json_body: dict | None = None) -> dict:
    """One authenticated Orders v2 call, returning the decoded body."""
    response = httpx.request(
        method,
        f"{api_base()}{path}",
        headers={
            "Authorization": f"Bearer {access_token()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        json=json_body,
        timeout=TIMEOUT_SECONDS,
    )
    try:
        body = response.json()
    except ValueError:
        body = {}
    if response.status_code >= 400:
        detail = body.get("message") or body.get("name") or f"HTTP {response.status_code}"
        raise PaymentVerificationError(f"PayPal rejected the request: {detail}")
    return body


# --------------------------------------------------------------------------
# Capture helpers
# --------------------------------------------------------------------------
def completed_captures(order: dict) -> list[dict]:
    """Every ``COMPLETED`` capture in a capture response."""
    captures: list[dict] = []
    for unit in order.get("purchase_units") or []:
        for capture in (unit.get("payments") or {}).get("captures") or []:
            if capture.get("status") == "COMPLETED":
                captures.append(capture)
    return captures


def captured_cents(order: dict) -> int:
    return sum(cents((c.get("amount") or {}).get("value", 0)) for c in completed_captures(order))


@register
class PayPalProvider(Provider):
    slug = "paypal"

    # ----------------------------------------------------------------- start
    def start(self, payment: Payment) -> dict:
        """Create an ``intent=CAPTURE`` order and return its id for the buttons."""
        order = call(
            "POST",
            "/v2/checkout/orders",
            json_body={
                "intent": "CAPTURE",
                "purchase_units": [
                    {
                        "reference_id": f"payment-{payment.pk}",
                        "custom_id": str(payment.pk),
                        "description": f"CalDART · {payment.description}"[:127],
                        "amount": {
                            "currency_code": payment.currency.upper(),
                            "value": dollars(payment.amount_cents),
                        },
                    }
                ],
                "payment_source": {
                    "paypal": {
                        "experience_context": {
                            "brand_name": "CalDART",
                            "shipping_preference": "NO_SHIPPING",
                            "user_action": "PAY_NOW",
                        }
                    }
                },
            },
        )
        order_id = order.get("id")
        if not order_id:
            raise PaymentVerificationError("PayPal did not return an order id.")

        payment.provider_ref = order_id
        payment.raw = order
        payment.save(update_fields=["provider_ref", "raw", "updated_at"])
        return {"order_id": order_id}

    # --------------------------------------------------------------- confirm
    def confirm(self, payment: Payment, *, order_id: str = "", **kwargs) -> bool:
        """Capture the order; ``COMPLETED`` for the right amount activates the term."""
        if payment.is_succeeded:
            # A second click, or a webhook that beat the browser back.
            return True

        order_id = order_id or payment.provider_ref
        if not order_id:
            raise PaymentVerificationError("No PayPal order to capture.")
        if payment.provider_ref and order_id != payment.provider_ref:
            raise PaymentVerificationError("That PayPal order belongs to another payment.")

        order = call("POST", f"/v2/checkout/orders/{order_id}/capture")

        if order.get("status") != "COMPLETED":
            mark_failed(payment, order)
            raise PaymentVerificationError(
                f"PayPal reports the order as '{order.get('status')}', not COMPLETED."
            )

        captures = completed_captures(order)
        if not captures:
            mark_failed(payment, order)
            raise PaymentVerificationError("PayPal completed the order without a capture.")

        total = captured_cents(order)
        if total != payment.amount_cents:
            raise PaymentVerificationError(
                f"PayPal captured ${total / 100:,.2f}, not ${payment.amount_cents / 100:,.2f}."
            )

        currency = (captures[0].get("amount") or {}).get("currency_code", "")
        if currency.lower() != payment.currency.lower():
            raise PaymentVerificationError("PayPal captured a different currency.")

        custom_id = captures[0].get("custom_id")
        if custom_id and str(custom_id) != str(payment.pk):
            raise PaymentVerificationError("The PayPal capture belongs to another payment.")

        mark_succeeded(
            payment,
            wallet=PaymentWallet.PAYPAL,
            raw=order,
            provider_ref=order_id,
        )
        return True

    # --------------------------------------------------------------- webhook
    def handle_webhook(self, request: HttpRequest) -> HttpResponse:
        """Record the notification; act on it only once it is verified.

        PayPal's signature check needs a ``PAYPAL_WEBHOOK_ID`` from the
        developer dashboard.  Without one we cannot tell a real notification
        from a forged one, so the payload is filed against the payment and
        nothing else happens — capture (above) is what activates memberships.
        """
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])

        try:
            payload = json_body(request)
        except ValueError:
            return JsonResponse({"detail": "Malformed JSON."}, status=400)

        verified = self.verify_signature(request, payload)
        event_type = payload.get("event_type", "")
        resource = payload.get("resource") or {}
        payment = payment_for_resource(resource)

        if payment is None:
            log.info("PayPal webhook %s referenced an unknown payment", event_type)
            return JsonResponse({"received": True, "verified": verified, "handled": False})

        record_provider_event(payment, {"event_type": event_type, "payload": payload})

        if not verified:
            log.info("PayPal webhook %s recorded but not verified", event_type)
            return JsonResponse({"received": True, "verified": False, "handled": False})

        if event_type == CAPTURE_COMPLETED:
            amount = cents((resource.get("amount") or {}).get("value", 0))
            if amount != payment.amount_cents:
                log.error("PayPal webhook amount %s does not match payment %s", amount, payment.pk)
                return JsonResponse({"received": True, "verified": True, "handled": False})
            mark_succeeded(payment, wallet=PaymentWallet.PAYPAL, raw=payload)
        elif event_type in CAPTURE_FAILED:
            mark_failed(payment, payload)
        else:
            return JsonResponse({"received": True, "verified": True, "handled": False})

        return JsonResponse({"received": True, "verified": True, "handled": True})

    def verify_signature(self, request: HttpRequest, payload: dict) -> bool:
        """Ask PayPal whether the notification really came from them."""
        webhook_id = getattr(settings, "PAYPAL_WEBHOOK_ID", "")
        if not webhook_id:
            return False
        headers = request.headers
        try:
            result = call(
                "POST",
                "/v1/notifications/verify-webhook-signature",
                json_body={
                    "auth_algo": headers.get("Paypal-Auth-Algo", ""),
                    "cert_url": headers.get("Paypal-Cert-Url", ""),
                    "transmission_id": headers.get("Paypal-Transmission-Id", ""),
                    "transmission_sig": headers.get("Paypal-Transmission-Sig", ""),
                    "transmission_time": headers.get("Paypal-Transmission-Time", ""),
                    "webhook_id": webhook_id,
                    "webhook_event": payload,
                },
            )
        except (PaymentVerificationError, ProviderNotConfigured, httpx.HTTPError) as exc:
            log.warning("PayPal webhook verification call failed: %s", exc)
            return False
        return result.get("verification_status") == "SUCCESS"


def json_body(request: HttpRequest) -> dict:
    """The request body as a dict, or ``ValueError``."""
    body = json.loads(request.body or b"{}")
    if not isinstance(body, dict):
        raise ValueError("Webhook payload must be an object.")
    return body


def payment_for_resource(resource: dict) -> Payment | None:
    """Find our row from a webhook resource's ``custom_id`` or order id."""
    custom_id = resource.get("custom_id")
    if custom_id:
        try:
            payment = Payment.objects.filter(
                pk=int(custom_id), provider=PaymentProvider.PAYPAL
            ).first()
        except (TypeError, ValueError):
            payment = None
        if payment is not None:
            return payment

    refs = [resource.get("id")]
    supplementary = (resource.get("supplementary_data") or {}).get("related_ids") or {}
    refs.append(supplementary.get("order_id"))
    for link in resource.get("links") or []:
        if link.get("rel") == "up":
            refs.append((link.get("href") or "").rstrip("/").rsplit("/", 1)[-1])

    for ref in refs:
        if not ref:
            continue
        payment = Payment.objects.filter(provider=PaymentProvider.PAYPAL, provider_ref=ref).first()
        if payment is not None:
            return payment
    return None
