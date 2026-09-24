"""PayPal provider: Orders v2 REST, called directly with ``httpx``.

No SDK -- the three calls we need (OAuth token, create order, capture order) are
plain JSON over HTTPS, and the SDK would add a dependency for nothing.

The client-credentials token is held in Django's default cache until shortly
before it expires; the entry records the environment and client id, so changing
either (in tests, or by editing ``.env``) fetches a fresh one.

Capture is authoritative: ``confirm`` only activates a membership when PayPal
answers ``COMPLETED`` *and* the captured amount matches our own row.  The
webhook is a recorder, and only acts when its signature has been verified.
"""

from __future__ import annotations

import json
import logging
from typing import Any, TypedDict

import httpx
from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed, JsonResponse

from apps.payments.models import Payment, PaymentProvider, PaymentWallet, Refund
from apps.payments.providers.base import (
    PaymentError,
    PaymentVerificationError,
    Provider,
    ProviderFees,
    ProviderNotConfiguredError,
    ProviderRefund,
    ProviderUnavailableError,
    register,
)
from apps.payments.refunds import record_dashboard_refund
from apps.payments.services import mark_failed, mark_succeeded, record_provider_event

log = logging.getLogger(__name__)

LIVE_BASE = "https://api-m.paypal.com"
SANDBOX_BASE = "https://api-m.sandbox.paypal.com"

#: What a member is told when PayPal times out or answers with something we
#: cannot read.  It says nothing about the money: a capture can fail in transit
#: after PayPal has already taken it.
UNAVAILABLE_MESSAGE = "PayPal could not be reached. Please try again."

#: Seconds shaved off the advertised token lifetime, so we never present one
#: that expires mid-flight.
TOKEN_SKEW_SECONDS = 60

#: How long a token is kept when PayPal advertises a lifetime shorter than the
#: skew above.  Caching for a moment is still better than a fetch per call.
MINIMUM_TOKEN_SECONDS = 30

#: Where the client-credentials token sits in Django's default cache.
TOKEN_CACHE_KEY = "paypal:access_token"  # noqa: S105 - a cache key, not a secret

TIMEOUT_SECONDS = 20.0

#: Webhook events worth acting on when the signature has been verified.
CAPTURE_COMPLETED = "PAYMENT.CAPTURE.COMPLETED"
CAPTURE_FAILED = frozenset({"PAYMENT.CAPTURE.DENIED", "PAYMENT.CAPTURE.REVERSED"})
CAPTURE_REFUNDED = "PAYMENT.CAPTURE.REFUNDED"


def api_base() -> str:
    """The PayPal API host: the live one when ``PAYPAL_ENV`` is ``live``, else sandbox."""
    return LIVE_BASE if settings.PAYPAL_ENV == "live" else SANDBOX_BASE


def unavailable(call_name: str, exc: Exception) -> ProviderUnavailableError:
    """Log a PayPal call that never completed, and build the error to raise.

    ``call_name`` is the method and path attempted.  Only the exception's class
    is recorded, because its message can quote request data.
    """
    log.warning("PayPal %s failed: %s", call_name, type(exc).__name__)
    return ProviderUnavailableError(UNAVAILABLE_MESSAGE)


def credentials() -> tuple[str, str]:
    """The configured client id and secret.

    Raises :class:`ProviderNotConfiguredError` when either is empty, so an
    unconfigured PayPal answers 400 rather than 500.
    """
    client_id = settings.PAYPAL_CLIENT_ID
    client_secret = settings.PAYPAL_CLIENT_SECRET
    if not client_id or not client_secret:
        raise ProviderNotConfiguredError(
            "PayPal is not configured (PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET are empty)."
        )
    return client_id, client_secret


def dollars(cents: int) -> str:
    """PayPal wants a decimal string, always with two places: 4500 -> ``"45.00"``."""
    return f"{cents / 100:.2f}"


def cents(value: str | float | int) -> int:
    """Inverse of :func:`dollars`, rounded to the nearest cent.

    Takes the decimal string PayPal sends, or a number.  Raises ``ValueError``
    for a string that is not a number.
    """
    return round(float(value) * 100)


# --------------------------------------------------------------------------
# OAuth token cache
# --------------------------------------------------------------------------
class CachedToken(TypedDict):
    """The cached OAuth token and the API base and client id it was fetched for."""

    key: list[str]
    token: str


def access_token() -> str:
    """A valid client-credentials token, fetched at most once per lifetime.

    The token is held in Django's default cache under
    :data:`TOKEN_CACHE_KEY` for its remaining lifetime less
    ``TOKEN_SKEW_SECONDS``, so it is never presented after PayPal has dropped it.
    Whether that cache is shared between worker processes is the cache backend's
    business: a per-process backend simply costs one token fetch per process.
    The entry records the API base and client id it was fetched for, so changing
    either fetches a fresh token rather than presenting one PayPal will refuse.
    Emptying the cache forces the next call to fetch.

    Raises :class:`ProviderNotConfiguredError` without credentials,
    :class:`ProviderUnavailableError` when the token call does not complete, and
    :class:`PaymentVerificationError` when PayPal refuses the credentials or
    returns no token.
    """
    client_id, client_secret = credentials()
    key = [api_base(), client_id]
    cached: CachedToken | None = cache.get(TOKEN_CACHE_KEY)
    if cached is not None and cached["key"] == key:
        return cached["token"]

    try:
        response = httpx.post(
            f"{api_base()}/v1/oauth2/token",
            auth=(client_id, client_secret),
            data={"grant_type": "client_credentials"},
            headers={"Accept": "application/json"},
            timeout=TIMEOUT_SECONDS,
        )
    except httpx.HTTPError as exc:
        raise unavailable("POST /v1/oauth2/token", exc) from exc
    if response.status_code != 200:
        raise PaymentVerificationError(
            f"PayPal refused our credentials (HTTP {response.status_code})."
        )
    try:
        body = response.json()
    except ValueError as exc:
        raise unavailable("POST /v1/oauth2/token", exc) from exc
    token: str = body.get("access_token") or ""
    if not token:
        raise PaymentVerificationError("PayPal returned no access token.")

    lifetime = max(int(body.get("expires_in", 0)) - TOKEN_SKEW_SECONDS, MINIMUM_TOKEN_SECONDS)
    cache.set(TOKEN_CACHE_KEY, CachedToken(key=key, token=token), timeout=lifetime)
    return token


def call(method: str, path: str, *, json_body: dict[str, Any] | None = None) -> dict[str, Any]:
    """One authenticated Orders v2 call, returning the decoded body.

    Raises :class:`~apps.payments.providers.base.ProviderUnavailableError` when the
    call never completes, and
    :class:`~apps.payments.providers.base.PaymentVerificationError` when PayPal
    answers with an error status.  A body that is not JSON is read as an empty
    dict, so a successful call with an unreadable body returns ``{}``.
    """
    try:
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
    except httpx.HTTPError as exc:
        raise unavailable(f"{method} {path}", exc) from exc
    try:
        body: dict[str, Any] = response.json()
    except ValueError:
        body = {}
    if response.status_code >= 400:
        detail = body.get("message") or body.get("name") or f"HTTP {response.status_code}"
        raise PaymentVerificationError(f"PayPal rejected the request: {detail}")
    return body


# --------------------------------------------------------------------------
# Capture helpers
# --------------------------------------------------------------------------
def completed_captures(order: dict[str, Any]) -> list[dict[str, Any]]:
    """Every ``COMPLETED`` capture in a capture response.

    Reads ``purchase_units[].payments.captures[]`` and skips a capture in any other
    state.  An order with no purchase units gives an empty list.
    """
    captures: list[dict[str, Any]] = []
    for unit in order.get("purchase_units") or []:
        captures.extend(
            capture
            for capture in (unit.get("payments") or {}).get("captures") or []
            if capture.get("status") == "COMPLETED"
        )
    return captures


def captured_cents(order: dict[str, Any]) -> int:
    """The total of every ``COMPLETED`` capture in ``order``, in cents.

    An order with no completed capture totals zero.
    """
    return sum(cents((c.get("amount") or {}).get("value", 0)) for c in completed_captures(order))


def fees_from_capture(capture: dict[str, Any]) -> ProviderFees | None:
    """What PayPal kept and paid across, from one capture's seller breakdown.

    Reads ``seller_receivable_breakdown.paypal_fee.value`` and
    ``.net_amount.value``, the decimal strings PayPal reports, and converts both
    to cents.  Answers ``None`` when the capture carries no breakdown, which is
    what an order that has not settled looks like, and when either figure cannot
    be read as a number.
    """
    breakdown = capture.get("seller_receivable_breakdown")
    if not isinstance(breakdown, dict):
        return None
    fee = (breakdown.get("paypal_fee") or {}).get("value")
    net = (breakdown.get("net_amount") or {}).get("value")
    if fee is None or net is None:
        return None
    try:
        return ProviderFees(fee_cents=cents(fee), net_cents=cents(net))
    except ValueError:
        log.warning("PayPal reported a fee that is not a number: %r", fee)
        return None


def fees_from_order(order: dict[str, Any]) -> ProviderFees | None:
    """The same, from a whole order: the breakdown of its first completed capture.

    Answers ``None`` for an order with no completed capture, and for one whose
    capture carries no breakdown yet.
    """
    captures = completed_captures(order)
    if not captures:
        return None
    return fees_from_capture(captures[0])


def capture_id(payment: Payment) -> str:
    """The id of the capture that took ``payment``'s money, read from its stored order.

    A refund is issued against the capture rather than the order, so this is what
    the refund call needs.  Raises :class:`PaymentVerificationError` when the
    stored response holds no completed capture, which is what a payment that was
    never captured looks like.
    """
    captures = completed_captures(payment.raw or {})
    found = captures[0].get("id") if captures else None
    if not found:
        raise PaymentVerificationError(
            "That payment has no completed PayPal capture to refund against."
        )
    return str(found)


def log_capture_mismatch(payment: Payment, order: dict[str, Any], reason: str) -> None:
    """Record at ERROR a capture that took money we cannot match to our row.

    PayPal has the money by this point, so the refusal needs a human to
    reconcile it.  ``reason`` names the field that disagreed.  The record
    carries the payment id and both amounts, and no personal data.
    """
    log.error(
        "PayPal capture mismatch (%s) for payment %s: captured %s cents, expected %s cents",
        reason,
        payment.pk,
        captured_cents(order),
        payment.amount_cents,
    )


@register
class PayPalProvider(Provider):
    """PayPal Orders v2: create an order, then capture it to take the money."""

    slug = "paypal"

    @classmethod
    def is_configured(cls) -> bool:
        """Whether both ``PAYPAL_CLIENT_ID`` and ``PAYPAL_CLIENT_SECRET`` are set.

        The buttons need the client id in the browser and the server needs both to
        fetch an access token, so one without the other is not usable.
        """
        return bool(settings.PAYPAL_CLIENT_ID and settings.PAYPAL_CLIENT_SECRET)

    # ----------------------------------------------------------------- start
    def start(self, payment: Payment) -> dict[str, Any]:
        """Create an ``intent=CAPTURE`` order and return its id for the buttons.

        Stores the order id as ``provider_ref`` and the order in ``raw``, and
        returns ``{"order_id": ...}``.  No money moves yet: :meth:`confirm` is what
        captures it.  Raises :class:`ProviderNotConfiguredError` without credentials,
        :class:`ProviderUnavailableError` when PayPal cannot be reached, and
        :class:`PaymentVerificationError` when PayPal rejects the request or
        answers without an order id.
        """
        order = call(
            "POST",
            "/v2/checkout/orders",
            json_body={
                "intent": "CAPTURE",
                "purchase_units": [
                    {
                        "reference_id": f"payment-{payment.pk}",
                        "custom_id": str(payment.pk),
                        "description": f"CalDART \u00b7 {payment.description}"[:127],
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
    def confirm(self, payment: Payment, *, order_id: str = "", **kwargs: Any) -> bool:
        """Capture the order; ``COMPLETED`` for the right amount activates the term.

        ``order_id`` defaults to the payment's own ``provider_ref``.  Returns
        ``True`` once the term is activated, and ``True`` without calling PayPal
        for a payment that already succeeded, so a second click is harmless.
        Raises :class:`PaymentVerificationError` when there is no order to
        capture, when the order belongs to another payment, when PayPal reports
        anything but ``COMPLETED``, when it completes the order without a capture,
        and when the captured total, the currency or the capture's ``custom_id``
        disagrees with the payment.  Of those, a status other than ``COMPLETED``
        and a completed order without a capture also mark the payment failed;
        the rest leave it as it was.  A capture that never completes raises
        :class:`ProviderUnavailableError` and is logged at ERROR for reconciliation,
        because the money may have moved.
        """
        if payment.is_succeeded:
            # A second click, or a webhook that beat the browser back.
            return True

        order_id = order_id or payment.provider_ref
        if not order_id:
            raise PaymentVerificationError("No PayPal order to capture.")
        if payment.provider_ref and order_id != payment.provider_ref:
            raise PaymentVerificationError("That PayPal order belongs to another payment.")

        try:
            order = call("POST", f"/v2/checkout/orders/{order_id}/capture")
        except ProviderUnavailableError:
            # The capture may have been taken before the connection died, so
            # this one needs reconciling rather than a silent retry.
            log.error(
                "PayPal capture for payment %s did not complete; up to %s cents may have moved",
                payment.pk,
                payment.amount_cents,
            )
            raise

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
            log_capture_mismatch(payment, order, "amount")
            raise PaymentVerificationError(
                f"PayPal captured ${total / 100:,.2f}, not ${payment.amount_cents / 100:,.2f}."
            )

        currency = (captures[0].get("amount") or {}).get("currency_code", "")
        if currency.lower() != payment.currency.lower():
            log_capture_mismatch(payment, order, "currency")
            raise PaymentVerificationError("PayPal captured a different currency.")

        custom_id = captures[0].get("custom_id")
        if custom_id and str(custom_id) != str(payment.pk):
            log_capture_mismatch(payment, order, "custom_id")
            raise PaymentVerificationError("The PayPal capture belongs to another payment.")

        fees = fees_from_order(order)
        mark_succeeded(
            payment,
            wallet=PaymentWallet.PAYPAL,
            raw=order,
            provider_ref=order_id,
            fee_cents=fees.fee_cents if fees is not None else None,
            net_cents=fees.net_cents if fees is not None else None,
        )
        return True

    # ---------------------------------------------------------------- refund
    def refund(self, payment: Payment, refund: Refund) -> ProviderRefund:
        """Refund ``refund.amount_cents`` against the capture that took the money.

        Returns PayPal's refund id and the body it answered with.  Raises
        :class:`PaymentVerificationError` when the payment holds no completed
        capture, when PayPal rejects the refund, and when it answers without a
        refund id, and :class:`ProviderUnavailableError` when PayPal cannot be
        reached.
        """
        answer = call(
            "POST",
            f"/v2/payments/captures/{capture_id(payment)}/refund",
            json_body={
                "amount": {
                    "currency_code": payment.currency.upper(),
                    "value": dollars(refund.amount_cents),
                },
                "custom_id": str(payment.pk),
            },
        )
        refund_id = answer.get("id")
        if not refund_id:
            raise PaymentVerificationError("PayPal did not return a refund id.")
        return ProviderRefund(provider_ref=str(refund_id), raw=answer)

    # --------------------------------------------------------------- webhook
    def handle_webhook(self, request: HttpRequest) -> HttpResponse:
        """Record the notification; act on it only once it is verified.

        PayPal's signature check needs a ``PAYPAL_WEBHOOK_ID`` from the
        developer dashboard.  Without one we cannot tell a real notification
        from a forged one, so the payload is filed against the payment and
        nothing else happens -- capture (above) is what activates memberships.

        A verified ``PAYMENT.CAPTURE.REFUNDED`` is the one notification that
        writes a record of its own: it files the refund somebody took in PayPal's
        dashboard, so the ledger is right whoever issued it.
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
            fees = fees_from_capture(resource)
            mark_succeeded(
                payment,
                wallet=PaymentWallet.PAYPAL,
                raw=payload,
                fee_cents=fees.fee_cents if fees is not None else None,
                net_cents=fees.net_cents if fees is not None else None,
            )
        elif event_type in CAPTURE_FAILED:
            mark_failed(payment, payload)
        elif event_type == CAPTURE_REFUNDED:
            self.record_refund(payment, resource)
        else:
            return JsonResponse({"received": True, "verified": True, "handled": False})

        return JsonResponse({"received": True, "verified": True, "handled": True})

    # ------------------------------------------------------------------ fees
    def fetch_fees(self, payment: Payment) -> ProviderFees | None:
        """Read the order again and take the fee off its capture's breakdown.

        Answers ``None`` for a payment with no order id, and for an order PayPal
        has not settled.  Raises
        :class:`~apps.payments.providers.base.ProviderNotConfiguredError` without
        credentials and
        :class:`~apps.payments.providers.base.ProviderUnavailableError` when
        PayPal cannot be reached.
        """
        if not payment.provider_ref:
            return None
        return fees_from_order(call("GET", f"/v2/checkout/orders/{payment.provider_ref}"))

    def record_refund(self, payment: Payment, resource: dict[str, Any]) -> Refund | None:
        """File a refund taken in PayPal's own dashboard against ``payment``.

        ``resource`` is the notification's refund object.  Returns the row
        written, or ``None`` when the refund is already on file -- the ordinary
        answer to a redelivered notification, and to the one for a refund CalDART
        itself issued -- and when PayPal reports it as anything but ``COMPLETED``,
        since no money has moved yet.
        """
        if resource.get("status") != "COMPLETED":
            return None
        return record_dashboard_refund(
            payment,
            amount_cents=cents((resource.get("amount") or {}).get("value", 0)),
            provider_ref=str(resource.get("id") or ""),
            raw=resource,
        )

    def verify_signature(self, request: HttpRequest, payload: dict[str, Any]) -> bool:
        """Ask PayPal whether the notification really came from them.

        Returns ``False`` without calling PayPal when ``PAYPAL_WEBHOOK_ID`` is
        unset, and ``False`` when the verification call itself fails, so an
        unverifiable notification is only ever recorded.
        """
        webhook_id = settings.PAYPAL_WEBHOOK_ID
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
        except PaymentError as exc:
            log.warning("PayPal webhook verification call failed: %s", exc)
            return False
        return result.get("verification_status") == "SUCCESS"


def json_body(request: HttpRequest) -> dict[str, Any]:
    """The request body as a dict.

    An empty body reads as ``{}``.  Raises ``ValueError`` for a body that is not
    JSON and for one whose top level is not an object.
    """
    body = json.loads(request.body or b"{}")
    if not isinstance(body, dict):
        raise ValueError("Webhook payload must be an object.")
    return body


def payment_for_resource(resource: dict[str, Any]) -> Payment | None:
    """Find our row from a webhook resource's ``custom_id`` or order id.

    Matches only PayPal payments: ``custom_id`` as a payment id first, then
    ``provider_ref`` against the resource's own id, the related order id and the
    id at the end of the resource's ``up`` link.  A ``custom_id`` that is not a
    number matches nothing, and the search falls through to those ids.  Returns
    ``None`` when none of them finds a row.
    """
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
    refs.extend(
        (link.get("href") or "").rstrip("/").rsplit("/", 1)[-1]
        for link in resource.get("links") or []
        if link.get("rel") == "up"
    )

    for ref in refs:
        if not ref:
            continue
        payment = Payment.objects.filter(provider=PaymentProvider.PAYPAL, provider_ref=ref).first()
        if payment is not None:
            return payment
    return None
