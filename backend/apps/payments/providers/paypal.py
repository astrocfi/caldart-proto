"""PayPal provider: Orders v2 REST, called directly with ``httpx``.

No SDK -- the three calls we need (OAuth token, create order, capture order) are
plain JSON over HTTPS, and the SDK would add a dependency without any gain.

Every call goes through :func:`~apps.payments.providers.paypal_api.call`, which
holds the client-credentials token and tells a call PayPal never answered from one
it refused.

Capture is authoritative: ``confirm`` only activates a membership when PayPal
answers ``COMPLETED`` *and* the capture matches our own row.  The webhook doesn't
read anything until PayPal has verified the notification's signature.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.utils import timezone

from apps.payments.models import Payment, PaymentProvider, PaymentWallet, Refund, RenewalMandate
from apps.payments.providers.base import (
    MandateMethod,
    PaymentDeclinedError,
    PaymentError,
    PaymentInDoubtError,
    PaymentPendingError,
    PaymentUnansweredError,
    PaymentVerificationError,
    Provider,
    ProviderFees,
    ProviderRefund,
    ProviderUnavailableError,
    RequestNotSentError,
    register,
)
from apps.payments.providers.paypal_api import (
    UNAVAILABLE_MESSAGE,
    PayPalRequestError,
    call,
    cents,
    dollars,
    segment,
)
from apps.payments.providers.paypal_orders import (
    WEBHOOK_CAPTURE_KEY,
    belongs_to_payment_order,
    capture_id,
    captured_cents,
    captures_with_status,
    completed_captures,
    fees_from_capture,
    fees_from_order,
    related_order_id,
    same_currency,
    verify_capture,
)
from apps.payments.receipts import SETTLED_STATUSES
from apps.payments.refunds import record_dashboard_refund
from apps.payments.services import mark_failed, mark_succeeded, record_provider_event

log = logging.getLogger(__name__)

#: The issue PayPal names when it refuses a capture because the buyer's card or
#: account was declined.
DECLINED_ISSUE = "INSTRUMENT_DECLINED"

#: Webhook events worth acting on when the signature has been verified.
CAPTURE_COMPLETED = "PAYMENT.CAPTURE.COMPLETED"
CAPTURE_FAILED = frozenset({"PAYMENT.CAPTURE.DENIED", "PAYMENT.CAPTURE.REVERSED"})
CAPTURE_REFUNDED = "PAYMENT.CAPTURE.REFUNDED"

#: What the member is told when PayPal will not take a vaulted payment.
DECLINED_MESSAGE = "PayPal refused the saved payment method."


#: The pauses, in seconds, before each in-process retry of a renewal order create
#: that never answered: three retries over three and a half minutes, all well
#: inside the hours PayPal keeps a ``PayPal-Request-Id``.
CREATE_RETRY_SECONDS: tuple[float, ...] = (30.0, 60.0, 120.0)

#: How long a renewal order's ``PayPal-Request-Id`` is trusted to bring back the
#: order a create already made.  PayPal keeps one for six hours; an hour is left
#: spare.
REQUEST_ID_RETENTION = timedelta(hours=5)

#: The longest the in-process retries of one renewal order create may take, in
#: seconds: well inside the 15 minutes a claim is held before another scan may take
#: it over, so no retry is still running when the charge is taken up again.
CREATE_DEADLINE_SECONDS = 300.0

#: PayPal's issue code for an order whose ``invoice_id`` was already paid.
DUPLICATE_INVOICE = "DUPLICATE_INVOICE_ID"

#: Why a renewal charge is in doubt when its create never answered.
UNANSWERED_MESSAGE = "PayPal never answered the renewal order, so it may hold a charge."

#: Why a renewal charge is in doubt when PayPal calls its invoice a duplicate.
DUPLICATE_INVOICE_MESSAGE = "PayPal says this renewal's invoice was already paid."

#: What the member is told when the renewal doesn't have a vaulted account to charge.
NO_METHOD_MESSAGE = "There isn't a saved PayPal account to charge."

#: The largest webhook body read, in bytes.  PayPal's notifications are a few
#: kilobytes; anything near this size is not one of theirs.
MAX_WEBHOOK_BYTES = 64 * 1024

#: What the webhook answers while ``PAYPAL_WEBHOOK_ID`` is empty.
WEBHOOK_NOT_CONFIGURED_MESSAGE = "PayPal notifications are not configured."

#: What the webhook answers a body over :data:`MAX_WEBHOOK_BYTES`.
WEBHOOK_TOO_LARGE_MESSAGE = "Notification too large."

#: What the webhook answers a notification PayPal does not vouch for.
UNVERIFIED_MESSAGE = "PayPal did not verify this notification."

#: The headers PayPal signs every notification with.  A delivery missing any of
#: them is refused without asking PayPal, which would only say no.
TRANSMISSION_HEADERS = (
    "Paypal-Transmission-Id",
    "Paypal-Transmission-Sig",
    "Paypal-Transmission-Time",
)


#: What the renewal scan logs about a capture PayPal is holding as ``PENDING``.
PENDING_MESSAGE = "PayPal is holding the capture as pending."

#: The vault instruction attached to a checkout order that is to save the payer's
#: account for automatic renewal.
VAULT_ATTRIBUTES = {"store_in_vault": "ON_SUCCESS", "usage_type": "MERCHANT"}


def clock() -> float:
    """Seconds on a clock that only moves forward, for the retry deadline."""
    return time.monotonic()


def renewal_refusal(
    exc: PaymentVerificationError, *, unanswered: bool, creating: bool
) -> PaymentError:
    """What a renewal charge makes of PayPal refusing a request about it.

    After an earlier try went unanswered PayPal may hold the order whatever it says
    now, so the charge is in doubt.  Otherwise a refusal of CalDART's own
    credentials -- a 401 or a 403, or a token PayPal would not give -- doesn't say
    anything about the payer and is an outage: for a create, one that didn't send
    anything (:class:`RequestNotSentError`).  PayPal calling the order a duplicate of an
    invoice it was already paid for is a charge in doubt too.  Anything else is
    the payer's method refused, a decline.
    """
    if unanswered:
        return PaymentInDoubtError(UNANSWERED_MESSAGE)
    if not isinstance(exc, PayPalRequestError) or exc.is_authorization:
        if creating:
            return RequestNotSentError(UNAVAILABLE_MESSAGE)
        return ProviderUnavailableError(UNAVAILABLE_MESSAGE)
    if DUPLICATE_INVOICE in exc.issues:
        return PaymentInDoubtError(DUPLICATE_INVOICE_MESSAGE)
    return PaymentDeclinedError(str(exc) or DECLINED_MESSAGE)


def pause(seconds: float) -> None:
    """Wait ``seconds`` before asking PayPal again; tests replace it so none waits."""
    time.sleep(seconds)


def renewal_request_id(payment: Payment) -> str:
    """The ``PayPal-Request-Id`` that ties one off-session order to one renewal payment.

    The renewal scan keeps a payment whose charge it could not finish and charges
    the same row again, so PayPal answers the repeat with the order it already made.
    """
    return f"caldart-renewal-{payment.pk}"


# --------------------------------------------------------------------------
# OAuth token cache
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# Capture helpers
# --------------------------------------------------------------------------


def is_signed_delivery(request: HttpRequest, payload: dict[str, Any]) -> bool:
    """Whether a delivery carries everything PayPal signs a notification with.

    That is every one of :data:`TRANSMISSION_HEADERS`, and an ``id`` and an
    ``event_type`` in the body.  A delivery without them cannot pass PayPal's check,
    so it is refused without spending a call on asking.
    """
    if not all(request.headers.get(name) for name in TRANSMISSION_HEADERS):
        return False
    return bool(payload.get("id")) and bool(payload.get("event_type"))


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
        captures it.  A payer with a ``pending`` renewal mandate has the order
        created with PayPal's vault instruction, so the account they pay with is
        saved for automatic renewal.  Raises :class:`ProviderNotConfiguredError`
        without credentials,
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
                "payment_source": {"paypal": paypal_source(payment)},
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

        The order captured is always the payment's own ``provider_ref``, the one
        :meth:`start` recorded; ``order_id``, when given, has to name that order.
        The answer is ``True`` once the term is activated, and ``True`` without
        calling PayPal for a payment whose money already arrived -- succeeded,
        partly refunded, or refunded -- so a second click is harmless and a refund
        is never undone.
        Raises :class:`PaymentVerificationError` when the payment doesn't hold an
        order of its own, when ``order_id`` names another order, when PayPal reports
        anything but ``COMPLETED``, when it completes the order without a capture,
        and when :func:`verify_capture` finds the captured total, the currency, the
        capture's ``custom_id``, or the order id disagreeing with the payment, and
        :class:`PayPalRequestError` when PayPal refuses the capture.  Of those, a
        status other than ``COMPLETED``, a completed order without a capture, and a
        refusal naming :data:`DECLINED_ISSUE` also mark the payment failed, so the
        order is never captured again; the rest leave it as it was.  A capture that
        never completes raises :class:`ProviderUnavailableError` and is logged at
        ERROR for reconciliation, because the money may have moved.
        """
        if payment.status in SETTLED_STATUSES:
            # A second click, a webhook that beat the browser back, or a refund since.
            return True

        # Only the order PayPal gave this payment is ever captured: a payment without
        # one, such as an abandoned checkout, doesn't have anything to capture.
        if not payment.provider_ref:
            raise PaymentVerificationError("No PayPal order to capture.")
        if order_id and order_id != payment.provider_ref:
            raise PaymentVerificationError("That PayPal order belongs to another payment.")
        order_id = payment.provider_ref

        try:
            order = call("POST", f"/v2/checkout/orders/{segment(order_id)}/capture")
        except PayPalRequestError as exc:
            if DECLINED_ISSUE in exc.issues:
                # The order body stored at start stays; the refusal is added to it.
                refusal = {"capture_refused": list(exc.issues)}
                mark_failed(payment, {**(payment.raw or {}), **refusal})
            raise
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

        verify_capture(
            payment,
            captures[0],
            captured=captured_cents(order),
            order_id=str(order.get("id") or ""),
        )

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

        The call carries ``PayPal-Request-Id: caldart-refund-<refund id>``, so a
        repeat for the same refund row gives the money back once.  Returns PayPal's
        refund id and the body it answered with.  Raises
        :class:`PaymentVerificationError` when the payment doesn't hold a completed
        capture, when PayPal rejects the refund, and when it answers without a
        refund id, and :class:`ProviderUnavailableError` when PayPal cannot be
        reached.
        """
        answer = call(
            "POST",
            f"/v2/payments/captures/{segment(capture_id(payment))}/refund",
            json_body={
                "amount": {
                    "currency_code": payment.currency.upper(),
                    "value": dollars(refund.amount_cents),
                },
                "custom_id": str(payment.pk),
            },
            request_id=f"caldart-refund-{refund.pk}",
        )
        refund_id = answer.get("id")
        if not refund_id:
            raise PaymentVerificationError("PayPal did not return a refund id.")
        return ProviderRefund(provider_ref=str(refund_id), raw=answer)

    # --------------------------------------------------------------- webhook
    def handle_webhook(self, request: HttpRequest) -> HttpResponse:
        """Verify the notification with PayPal, then file it and act on it.

        PayPal's signature check needs a ``PAYPAL_WEBHOOK_ID`` from the developer
        dashboard, so without one the route answers 404 and doesn't read anything.  A
        body over :data:`MAX_WEBHOOK_BYTES` is a 413 and one that is not a JSON
        object a 400, both before PayPal is asked.  A notification PayPal does not
        vouch for is a 400 that doesn't record anything or touch a payment.

        A delivery missing any of :data:`TRANSMISSION_HEADERS`, or a body ``id`` or
        ``event_type``, is that same 400 without a call to PayPal.

        A verified notification is filed as the matching payment's
        ``raw["last_webhook"]`` and answered 200 with ``{"received": true,
        "handled": ...}``.  ``handled`` is true when a ``PAYMENT.CAPTURE.COMPLETED``
        passed :func:`verify_capture` and settled the payment, which keeps its stored
        order and files the capture under :data:`WEBHOOK_CAPTURE_KEY`; when a
        denial or a reversal of the payment's own order was applied (which fails a
        payment still waiting on its money and leaves a settled one as it is); and
        when a ``PAYMENT.CAPTURE.REFUNDED`` in the payment's currency was filed:
        the refund somebody took in PayPal's dashboard, so the ledger is right
        whoever issued it.  A notification that isn't about one of our payments, a
        denial or a reversal of another order, a refund in another currency, and any
        other event type, are received but not handled.
        """
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        if not settings.PAYPAL_WEBHOOK_ID:
            return JsonResponse({"detail": WEBHOOK_NOT_CONFIGURED_MESSAGE}, status=404)
        if exceeds_webhook_cap(request):
            return JsonResponse({"detail": WEBHOOK_TOO_LARGE_MESSAGE}, status=413)

        try:
            payload = json_body(request)
        except ValueError:
            return JsonResponse({"detail": "Malformed JSON."}, status=400)

        event_type = payload.get("event_type", "")
        if not is_signed_delivery(request, payload):
            log.warning("Refused an unsigned PayPal webhook %r", event_type)
            return JsonResponse({"detail": UNVERIFIED_MESSAGE}, status=400)
        # Nothing is written, and no payment row is locked, until PayPal vouches for
        # the notification: the route is anonymous.
        if not self.verify_signature(request, payload):
            log.warning("Refused an unverified PayPal webhook %r", event_type)
            return JsonResponse({"detail": UNVERIFIED_MESSAGE}, status=400)

        resource = payload.get("resource") or {}
        payment = payment_for_resource(resource)
        if payment is None:
            log.info("PayPal webhook %r referenced an unknown payment", event_type)
            return JsonResponse({"received": True, "handled": False})

        payment = record_provider_event(payment, {"event_type": event_type, "payload": payload})

        if event_type == CAPTURE_COMPLETED:
            try:
                verify_capture(
                    payment,
                    resource,
                    captured=cents((resource.get("amount") or {}).get("value", 0)),
                    order_id=related_order_id(resource),
                )
            except PaymentVerificationError:
                return JsonResponse({"received": True, "handled": False})
            fees = fees_from_capture(resource)
            # The stored order stays, so the capture is filed beside it for a refund.
            mark_succeeded(
                payment,
                wallet=PaymentWallet.PAYPAL,
                raw={**(payment.raw or {}), WEBHOOK_CAPTURE_KEY: resource},
                fee_cents=fees.fee_cents if fees is not None else None,
                net_cents=fees.net_cents if fees is not None else None,
            )
        elif event_type in CAPTURE_FAILED:
            if not belongs_to_payment_order(payment, resource):
                log.error("PayPal %r for payment %s names another order", event_type, payment.pk)
                return JsonResponse({"received": True, "handled": False})
            mark_failed(payment, payload)
        elif event_type == CAPTURE_REFUNDED:
            if not same_currency(payment, resource):
                log.error("PayPal refund for payment %s is in another currency", payment.pk)
                return JsonResponse({"received": True, "handled": False})
            self.record_refund(payment, resource)
        else:
            return JsonResponse({"received": True, "handled": False})

        return JsonResponse({"received": True, "handled": True})

    # ------------------------------------------------------------------ fees
    def fetch_fees(self, payment: Payment) -> ProviderFees | None:
        """Read the order again and take the fee off its capture's breakdown.

        Answers ``None`` for a payment without an order id, and for an order PayPal
        has not settled.  Raises
        :class:`~apps.payments.providers.base.ProviderNotConfiguredError` without
        credentials and
        :class:`~apps.payments.providers.base.ProviderUnavailableError` when
        PayPal cannot be reached.
        """
        if not payment.provider_ref:
            return None
        return fees_from_order(call("GET", f"/v2/checkout/orders/{segment(payment.provider_ref)}"))

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
        unverifiable notification is never acted on.
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

    # ------------------------------------------------------------- mandates
    def start_mandate(self, mandate: RenewalMandate) -> dict[str, Any]:
        """Create the vault setup token the PayPal buttons approve.

        Returns ``{"setup_token": ...}``.  No money moves: approving the token is
        what lets :meth:`confirm_mandate` exchange it for a payment token.  Raises
        :class:`ProviderNotConfiguredError` without credentials,
        :class:`ProviderUnavailableError` when PayPal cannot be reached, and
        :class:`PaymentVerificationError` when PayPal answers without a token id.
        """
        token = call(
            "POST",
            "/v3/vault/setup-tokens",
            json_body={
                "payment_source": {
                    "paypal": {
                        "usage_type": "MERCHANT",
                        "experience_context": dict(EXPERIENCE_CONTEXT),
                    }
                }
            },
        )
        token_id = token.get("id")
        if not token_id:
            raise PaymentVerificationError("PayPal did not return a setup token.")
        return {"setup_token": token_id}

    def confirm_mandate(self, mandate: RenewalMandate, **kwargs: Any) -> MandateMethod:
        """Exchange the approved setup token for the vaulted payment token.

        ``setup_token`` names the token the buttons approved.  Raises
        :class:`PaymentVerificationError` when no token is given and when PayPal
        answers without a vault id, and :class:`ProviderUnavailableError` when
        PayPal cannot be reached.
        """
        setup_token = str(kwargs.get("setup_token") or "")
        if not setup_token:
            raise PaymentVerificationError("No PayPal setup token to confirm.")
        token = call(
            "POST",
            "/v3/vault/payment-tokens",
            json_body={"payment_source": {"token": {"id": setup_token, "type": "SETUP_TOKEN"}}},
        )
        vault_id = token.get("id")
        if not vault_id:
            raise PaymentVerificationError("PayPal did not return a payment token.")
        paypal = (token.get("payment_source") or {}).get("paypal") or {}
        return MandateMethod(
            method_ref=str(vault_id),
            customer_ref=str(token.get("customer", {}).get("id") or ""),
            label=paypal_label(str(paypal.get("email_address") or "")),
            raw=token,
        )

    def charge_mandate(self, mandate: RenewalMandate, payment: Payment) -> None:
        """Create an order against the vaulted account and capture it at once.

        The vaulted account charged is the one stamped on the payment when it was
        first sent (``charge_method_ref``), falling back to the mandate's own.  The
        order is created by :meth:`create_renewal_order` under ``PayPal-Request-Id:
        caldart-renewal-<payment id>``, with that same string as the purchase
        unit's ``invoice_id``, and settled by :meth:`settle_renewal_order`, which
        stores the order's id as ``provider_ref`` before any separate capture.
        Raises :class:`PaymentDeclinedError` when PayPal will not take the vaulted
        method or there isn't one, :class:`PaymentPendingError` when PayPal holds the
        capture as ``PENDING``, :class:`PaymentInDoubtError` when the create never
        answered or PayPal refuses the invoice as a duplicate, and
        :class:`ProviderUnavailableError` when the capture cannot be asked for.
        """
        method_ref = payment.charge_method_ref or mandate.method_ref
        if not method_ref:
            raise PaymentDeclinedError(NO_METHOD_MESSAGE)
        order = self.create_renewal_order(
            payment,
            {
                "intent": "CAPTURE",
                "purchase_units": [
                    {
                        "reference_id": f"payment-{payment.pk}",
                        "custom_id": str(payment.pk),
                        "invoice_id": renewal_request_id(payment),
                        "description": f"CalDART \u00b7 {payment.description}"[:127],
                        "amount": {
                            "currency_code": payment.currency.upper(),
                            "value": dollars(payment.amount_cents),
                        },
                    }
                ],
                "payment_source": {"paypal": {"vault_id": method_ref}},
            },
        )
        self.settle_renewal_order(payment, order)

    def create_renewal_order(self, payment: Payment, body: dict[str, Any]) -> dict[str, Any]:
        """Create the renewal order, retrying a create that never answered.

        PayPal keeps a ``PayPal-Request-Id`` for a few hours and doesn't offer a
        search of orders by our reference, so a create that never answers is tried
        again at
        once, under the same id, after each of :data:`CREATE_RETRY_SECONDS`, for no
        longer than :data:`CREATE_DEADLINE_SECONDS` in all: a repeat answers with
        the order the first call made, if it made one.

        Once any try has gone unanswered PayPal may hold an order, so every answer
        but the order itself raises :class:`PaymentInDoubtError` --
        :class:`PaymentUnansweredError` when PayPal doesn't answer at all.  Before
        that, a request that never left (:class:`RequestNotSentError`) and PayPal
        refusing CalDART's credentials (a 401 or a 403, or a token it would not
        give) raise :class:`RequestNotSentError`, since PayPal didn't take anything;
        PayPal refusing the order as a duplicate of an invoice it was already paid for
        (``DUPLICATE_INVOICE_ID``) raises :class:`PaymentInDoubtError`; and any other
        refusal raises :class:`PaymentDeclinedError`.
        """
        started = clock()
        unanswered = False
        for delay in (*CREATE_RETRY_SECONDS, None):
            try:
                return call(
                    "POST",
                    "/v2/checkout/orders",
                    json_body=body,
                    request_id=renewal_request_id(payment),
                )
            except RequestNotSentError as exc:
                if not unanswered:
                    raise
                log.warning("PayPal could not be asked again about payment %s", payment.pk)
                if delay is None or clock() - started + delay > CREATE_DEADLINE_SECONDS:
                    raise PaymentUnansweredError(UNANSWERED_MESSAGE) from exc
            except ProviderUnavailableError as exc:
                unanswered = True
                if delay is None or clock() - started + delay > CREATE_DEADLINE_SECONDS:
                    raise PaymentUnansweredError(UNANSWERED_MESSAGE) from exc
                log.warning(
                    "PayPal did not answer the renewal order for payment %s; "
                    "asking again in %s seconds",
                    payment.pk,
                    delay,
                )
            except PaymentVerificationError as exc:
                raise renewal_refusal(exc, unanswered=unanswered, creating=True) from exc
            if delay is not None:
                pause(delay)
        raise PaymentUnansweredError(UNANSWERED_MESSAGE)

    def find_mandate_charge(self, mandate: RenewalMandate, payment: Payment) -> bool:
        """Settle ``payment`` from the order an earlier charge made, if there is one.

        A payment that names its order has it read again and settled by
        :meth:`settle_renewal_order`, captured first when it never was, and the
        answer is ``True``.  One that doesn't name an order and was never sent, or was
        sent less than :data:`REQUEST_ID_RETENTION` ago, answers ``False``: charging again
        repeats the create under the same ``PayPal-Request-Id``, which PayPal answers
        with the order it already made.  One sent longer ago than that names an
        order PayPal may hold and no longer recognize the id of, and raises
        :class:`PaymentInDoubtError` rather than risk a second charge.  Raises
        :class:`PaymentDeclinedError` when PayPal refuses to show the order, and
        :class:`ProviderUnavailableError` when it cannot be reached or refuses
        CalDART's credentials.
        """
        if not payment.provider_ref:
            sent_at = payment.charge_sent_at
            if sent_at is None or timezone.now() - sent_at < REQUEST_ID_RETENTION:
                return False
            raise PaymentInDoubtError(UNANSWERED_MESSAGE)
        try:
            order = call("GET", f"/v2/checkout/orders/{segment(payment.provider_ref)}")
        except PaymentVerificationError as exc:
            raise renewal_refusal(exc, unanswered=False, creating=False) from exc
        self.settle_renewal_order(payment, order)
        return True

    def settle_renewal_order(self, payment: Payment, order: dict[str, Any]) -> None:
        """Capture a vault-sourced renewal order if it needs it, and record the result.

        Stores the order's id as ``provider_ref``, captures an order that is not yet
        ``COMPLETED`` under ``PayPal-Request-Id: caldart-renewal-<payment id>-capture``,
        and marks the payment succeeded once :func:`verify_capture` agrees with the
        completed capture: its total, its currency, and its order.  Raises
        :class:`PaymentDeclinedError` when the capture is refused or the order does
        not complete, :class:`PaymentPendingError` when its only capture is
        ``PENDING``, :class:`PaymentInDoubtError` when PayPal captured money the
        checks do not match, which a person has to reconcile, and
        :class:`ProviderUnavailableError` when the capture cannot be asked for.
        """
        order_id = str(order.get("id") or "")
        if order_id and order_id != payment.provider_ref:
            payment.provider_ref = order_id
            payment.save(update_fields=["provider_ref", "updated_at"])
        if order.get("status") != "COMPLETED":
            try:
                order = call(
                    "POST",
                    f"/v2/checkout/orders/{segment(order_id)}/capture",
                    request_id=f"{renewal_request_id(payment)}-capture",
                )
            except PaymentVerificationError as exc:
                raise renewal_refusal(exc, unanswered=False, creating=False) from exc

        if order.get("status") != "COMPLETED":
            raise PaymentDeclinedError(DECLINED_MESSAGE)
        captures = completed_captures(order)
        if not captures:
            if captures_with_status(order, "PENDING"):
                raise PaymentPendingError(PENDING_MESSAGE)
            raise PaymentDeclinedError(DECLINED_MESSAGE)
        try:
            verify_capture(payment, captures[0], captured=captured_cents(order), order_id=order_id)
        except PaymentVerificationError as exc:
            raise PaymentInDoubtError(str(exc)) from exc
        mark_succeeded(
            payment,
            wallet=PaymentWallet.PAYPAL,
            raw=order,
            provider_ref=order_id or payment.provider_ref,
        )

    def record_charge_reference(self, payment: Payment, reference: str) -> None:
        """Mark ``payment`` paid from the PayPal capture ``reference``, once checked.

        ``reference`` is the capture id a treasurer copied from PayPal's dashboard.
        The capture is read from PayPal -- one call -- and must be ``COMPLETED``,
        carry this payment's ``custom_id`` or ``invoice_id``, and be for the
        payment's amount and currency.  The payment then succeeds with its capture's
        order as ``provider_ref`` and the capture filed under
        :data:`WEBHOOK_CAPTURE_KEY`, exactly as the capture notification files it, so
        a later refund finds it.  Raises :class:`PaymentVerificationError` naming the
        first check that fails, a capture PayPal doesn't have a record of included, and
        :class:`ProviderUnavailableError` when PayPal cannot be reached or refuses
        CalDART's credentials.
        """
        try:
            capture = call("GET", f"/v2/payments/captures/{segment(reference)}")
        except PayPalRequestError as exc:
            if exc.is_authorization:
                raise ProviderUnavailableError(UNAVAILABLE_MESSAGE) from exc
            raise PaymentVerificationError(f"PayPal doesn't have a capture {reference}.") from exc
        if capture.get("status") != "COMPLETED":
            raise PaymentVerificationError("That PayPal capture has not completed.")
        ours = {str(payment.pk), renewal_request_id(payment)}
        if not {str(capture.get("custom_id") or ""), str(capture.get("invoice_id") or "")} & ours:
            raise PaymentVerificationError("That PayPal capture belongs to another payment.")
        amount = capture.get("amount") or {}
        if cents(amount.get("value", 0)) != payment.amount_cents:
            raise PaymentVerificationError("That PayPal capture is for another amount.")
        if str(amount.get("currency_code") or "").lower() != payment.currency.lower():
            raise PaymentVerificationError("That PayPal capture is in another currency.")
        order_id = related_order_id(capture)
        if not order_id:
            raise PaymentVerificationError("PayPal doesn't name an order for that capture.")
        mark_succeeded(
            payment,
            wallet=PaymentWallet.PAYPAL,
            raw={**(payment.raw or {}), WEBHOOK_CAPTURE_KEY: capture},
            provider_ref=order_id,
        )

    def method_from_payment(self, payment: Payment) -> MandateMethod | None:
        """The vaulted account a captured order saved, or ``None`` if it didn't."""
        return vault_from_capture(payment.raw or {})


def exceeds_webhook_cap(request: HttpRequest) -> bool:
    """Whether the request's body is larger than :data:`MAX_WEBHOOK_BYTES`.

    A declared ``Content-Length`` over the cap is enough, so such a body is never
    read into memory; otherwise the body itself is measured.
    """
    declared = str(request.META.get("CONTENT_LENGTH") or "")
    if declared.isdigit() and int(declared) > MAX_WEBHOOK_BYTES:
        return True
    return len(request.body) > MAX_WEBHOOK_BYTES


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
    number doesn't match anything, and the search falls through to those ids.  Returns
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


EXPERIENCE_CONTEXT = {
    "brand_name": "CalDART",
    "shipping_preference": "NO_SHIPPING",
    "user_action": "PAY_NOW",
}


def paypal_source(payment: Payment) -> dict[str, Any]:
    """The ``payment_source.paypal`` block a checkout order carries.

    The experience context always, plus the vault instruction when the payer
    asked for automatic renewal, which is what makes PayPal keep the account for
    a later charge.
    """
    # Inline: renewals reads this package, so a top-level import would close the
    # cycle between the two.
    from apps.payments.renewals.mandates import pending_mandate_for

    source: dict[str, Any] = {"experience_context": dict(EXPERIENCE_CONTEXT)}
    if pending_mandate_for(payment) is not None:
        source["attributes"] = {"vault": dict(VAULT_ATTRIBUTES)}
    return source


def vault_from_capture(order: dict[str, Any]) -> MandateMethod | None:
    """The vaulted PayPal account a captured order saved, or ``None``.

    Reads ``payment_source.paypal.attributes.vault.id`` and the payer's email
    address, which is what the member sees: ``"PayPal (m***@example.org)"``.
    ``None`` when the order didn't save an account.
    """
    paypal = (order.get("payment_source") or {}).get("paypal") or {}
    vault = (paypal.get("attributes") or {}).get("vault") or {}
    vault_id = vault.get("id")
    if not vault_id:
        return None
    return MandateMethod(
        method_ref=str(vault_id),
        customer_ref=str(paypal.get("account_id") or ""),
        label=paypal_label(str(paypal.get("email_address") or "")),
        raw=order,
    )


def paypal_label(email: str) -> str:
    """How a saved PayPal account reads to its owner.

    ``"PayPal (m***@example.org)"`` for a known address, with everything after the
    first character of the local part hidden, and ``"PayPal"`` when PayPal didn't
    give an address at all.
    """
    if "@" not in email:
        return "PayPal"
    local, _, domain = email.partition("@")
    masked = f"{local[0]}***" if local else "***"
    return f"PayPal ({masked}@{domain})"
