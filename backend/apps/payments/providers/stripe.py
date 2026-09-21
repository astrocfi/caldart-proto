"""Stripe provider: Payment Element, card / Apple Pay / Google Pay / Link.

The flow:

1. ``start`` creates a PaymentIntent for the amount the *server* computed, with
   ``automatic_payment_methods`` so the Payment Element offers every method the
   account has enabled, and metadata that ties the intent back to our row.
2. The browser confirms the intent with Stripe.js.
3. ``confirm`` retrieves the intent again and refuses to activate a membership
   unless Stripe agrees about the status, amount, currency and payment id.
4. ``handle_webhook`` is the safety net for redirect-based methods, and is
   idempotent because :func:`~apps.payments.services.mark_succeeded` is.

Every call goes through :func:`stripe_client`, whose timeout and retry budget
are shorter than the timeouts of the proxies in front of Django, so a slow
Stripe never becomes a gateway error over a request that is still running.

The SDK answers with ``stripe.PaymentIntent`` and ``stripe.Event`` objects,
which are not dicts.  Each is converted with ``to_dict()`` the moment it
arrives, so everything below the boundary works on plain nested dicts that
store straight into ``Payment.raw``.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any

import stripe
from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed, JsonResponse

from apps.payments.models import Payment, PaymentProvider, PaymentWallet
from apps.payments.providers.base import (
    PaymentVerificationError,
    Provider,
    ProviderNotConfigured,
    ProviderUnavailable,
    register,
)
from apps.payments.services import mark_failed, mark_succeeded

log = logging.getLogger(__name__)

#: What a member is told when Stripe times out or answers with an error of its
#: own.  It says nothing about the money: a call can fail after Stripe acted.
UNAVAILABLE_MESSAGE = "Stripe could not be reached. Please try again."

#: ``payment_method_details.card.wallet.type`` values mapped onto our choices.
WALLET_TYPES: dict[str, str] = {
    "apple_pay": PaymentWallet.APPLE_PAY,
    "google_pay": PaymentWallet.GOOGLE_PAY,
    "link": PaymentWallet.LINK,
}

#: Intent statuses that mean the customer will not be charged.
FAILED_STATUSES = frozenset({"canceled", "requires_payment_method"})

#: How long one Stripe HTTP attempt may take, and how many times the library
#: may retry it.  The worst case is the product plus one attempt -- 40 seconds
#: -- which has to stay below gunicorn's ``timeout``, nginx's
#: ``proxy_read_timeout`` and Apache's ``ProxyTimeout``, all 60 seconds in
#: ``deploy/``.  The library's own defaults are 80 seconds and two retries,
#: which would let a call outlive the request it belongs to.
STRIPE_TIMEOUT_SECONDS = 20.0
STRIPE_MAX_NETWORK_RETRIES = 1


@lru_cache(maxsize=1)
def http_client() -> stripe.HTTPClient:
    """The one HTTP client every Stripe call shares, so it pools connections."""
    return stripe.new_default_http_client(timeout=STRIPE_TIMEOUT_SECONDS)


def stripe_client() -> stripe.StripeClient:
    """A Stripe client bound by our timeout and retry budget.

    Raises :class:`~apps.payments.providers.base.ProviderNotConfigured` when no
    secret key is configured, so the API answers 400 rather than 500.  Calls go
    through the client's ``v1`` namespace; the shorthand on the client itself
    is deprecated.
    """
    return stripe.StripeClient(
        secret_key(),
        max_network_retries=STRIPE_MAX_NETWORK_RETRIES,
        http_client=http_client(),
    )


def idempotency_key(payment: Payment) -> str:
    """The key that ties one PaymentIntent to one payment row.

    Starting the same payment twice then returns the intent already created
    instead of a second one.
    """
    return f"caldart-payment-{payment.pk}-start"


def unavailable(payment: Payment, call: str, exc: stripe.StripeError) -> ProviderUnavailable:
    """Log a failed Stripe call and build the error the API answers 400 with.

    Only the payment id and the exception's class are recorded: the message can
    quote request data, and nothing about a member belongs in the log.
    """
    log.warning("Stripe %s failed for payment %s: %s", call, payment.pk, type(exc).__name__)
    return ProviderUnavailable(UNAVAILABLE_MESSAGE)


def secret_key() -> str:
    """The configured secret key, or raise so the API answers 400 rather than 500."""
    key: str = settings.STRIPE_SECRET_KEY
    if not key:
        raise ProviderNotConfigured("Stripe is not configured (STRIPE_SECRET_KEY is empty).")
    return key


def jsonable(value: dict[str, Any]) -> dict[str, Any]:
    """A plain, JSON-serializable dict for ``Payment.raw``.

    Stripe's own types are converted to dicts at the SDK boundary, so all this
    has left to do is drop anything JSON cannot carry, such as a date.  Such a
    value is replaced by its ``str()``.
    """
    converted: dict[str, Any] = json.loads(json.dumps(value, default=str))
    return converted


def wallet_from_intent(intent: dict[str, Any]) -> str:
    """Map ``latest_charge.payment_method_details`` onto our wallet choices.

    An Apple Pay, Google Pay or Link wallet gives that choice, a Link payment
    method type gives ``link``, and any other readable card detail gives ``card``.
    An intent whose latest charge is missing or unexpanded gives ``unknown``.
    """
    charge = intent.get("latest_charge")
    if not isinstance(charge, dict):
        return PaymentWallet.UNKNOWN
    details = charge.get("payment_method_details")
    if not isinstance(details, dict):
        return PaymentWallet.UNKNOWN

    card = details.get("card")
    if isinstance(card, dict):
        wallet = card.get("wallet")
        wallet_type = wallet.get("type") if isinstance(wallet, dict) else None
        if wallet_type in WALLET_TYPES:
            return WALLET_TYPES[wallet_type]

    if details.get("type") == "link":
        return PaymentWallet.LINK
    return PaymentWallet.CARD


def payment_for_intent(intent: dict[str, Any]) -> Payment | None:
    """Find our row from the intent's metadata, falling back to the intent id.

    Matches only Stripe payments: ``metadata.payment_id`` first, then
    ``provider_ref`` against the intent's id.  Returns ``None`` when neither finds
    a row, and when the metadata holds an id that is not a number.
    """
    metadata = intent.get("metadata") or {}
    raw_id = metadata.get("payment_id")
    if raw_id:
        try:
            payment = Payment.objects.filter(
                pk=int(raw_id), provider=PaymentProvider.STRIPE
            ).first()
        except (TypeError, ValueError):
            payment = None
        if payment is not None:
            return payment

    intent_id = intent.get("id")
    if not intent_id:
        return None
    return Payment.objects.filter(provider=PaymentProvider.STRIPE, provider_ref=intent_id).first()


@register
class StripeProvider(Provider):
    """Stripe via the Payment Element: card, Apple Pay, Google Pay and Link."""

    slug = "stripe"

    # ----------------------------------------------------------------- start
    def start(self, payment: Payment) -> dict[str, Any]:
        """Create the PaymentIntent and hand the client its ``client_secret``.

        Stores the intent's id as ``provider_ref`` and the whole intent in ``raw``,
        and returns ``{"client_secret": ...}``.  The call is idempotent per payment,
        so starting the same payment twice returns the first intent rather than
        charging twice.  Raises :class:`ProviderNotConfigured` without a secret key
        and :class:`ProviderUnavailable` when Stripe cannot be reached.
        """
        client = stripe_client()
        try:
            created = client.v1.payment_intents.create(
                {
                    "amount": payment.amount_cents,
                    "currency": payment.currency,
                    "automatic_payment_methods": {"enabled": True},
                    "description": f"CalDART · {payment.description}",
                    # stripe's params type the field as a string, but its API
                    # takes null for "send no receipt".
                    "receipt_email": payment.user.email or None,  # type: ignore[typeddict-item]
                    "metadata": {
                        "payment_id": str(payment.pk),
                        "user_id": str(payment.user_id),
                        "plan": payment.plan.slug if payment.plan is not None else "",
                    },
                },
                {"idempotency_key": idempotency_key(payment)},
            )
        except stripe.StripeError as exc:
            raise unavailable(payment, "payment_intents.create", exc) from exc
        intent = created.to_dict()
        payment.provider_ref = intent["id"]
        payment.raw = jsonable(intent)
        payment.save(update_fields=["provider_ref", "raw", "updated_at"])
        return {"client_secret": intent["client_secret"]}

    # --------------------------------------------------------------- confirm
    def confirm(self, payment: Payment, *, payment_intent_id: str = "", **kwargs: Any) -> bool:
        """Retrieve the intent and verify it before activating anything.

        ``payment_intent_id`` defaults to the payment's own ``provider_ref``.
        Returns ``True`` once Stripe reports ``succeeded`` and the payment has been
        marked succeeded; returns ``False``, having marked the payment failed, when
        Stripe reports ``canceled`` or ``requires_payment_method``.  Raises
        :class:`PaymentVerificationError` when there is no intent to confirm, when
        the intent belongs to another payment, when :meth:`verify` disagrees, and
        when Stripe reports any other status.  Raises
        :class:`ProviderUnavailable` when Stripe cannot be reached.
        """
        intent_id = payment_intent_id or payment.provider_ref
        if not intent_id:
            raise PaymentVerificationError("No PaymentIntent to confirm.")
        if payment.provider_ref and intent_id != payment.provider_ref:
            raise PaymentVerificationError("That PaymentIntent belongs to another payment.")

        client = stripe_client()
        try:
            retrieved = client.v1.payment_intents.retrieve(intent_id, {"expand": ["latest_charge"]})
        except stripe.StripeError as exc:
            raise unavailable(payment, "payment_intents.retrieve", exc) from exc
        intent = retrieved.to_dict()
        self.verify(payment, intent)

        status = intent.get("status")
        if status != "succeeded":
            if status in FAILED_STATUSES:
                mark_failed(payment, jsonable(intent))
                return False
            raise PaymentVerificationError(f"Stripe reports the payment as '{status}'.")

        mark_succeeded(
            payment,
            wallet=wallet_from_intent(intent),
            raw=jsonable(intent),
            provider_ref=intent["id"],
        )
        return True

    def verify(self, payment: Payment, intent: dict[str, Any]) -> None:
        """Everything about the intent that must match our own row.

        Returns ``None`` when the intent's ``metadata.payment_id``, ``amount`` and
        ``currency`` all match the payment.  Raises
        :class:`PaymentVerificationError` naming the first that does not.
        """
        metadata = intent.get("metadata") or {}
        if str(metadata.get("payment_id") or "") != str(payment.pk):
            raise PaymentVerificationError("PaymentIntent metadata does not match this payment.")
        if int(intent.get("amount") or 0) != payment.amount_cents:
            raise PaymentVerificationError("PaymentIntent amount does not match this payment.")
        if str(intent.get("currency") or "").lower() != payment.currency.lower():
            raise PaymentVerificationError("PaymentIntent currency does not match this payment.")

    # --------------------------------------------------------------- webhook
    def handle_webhook(self, request: HttpRequest) -> HttpResponse:
        """Verify ``Stripe-Signature``, then apply the event idempotently.

        Answers 405 to any method but ``POST`` and 400 to a body whose signature
        does not check out.  Otherwise the answer is 200 with
        ``{"received": true, "handled": ...}``: ``handled`` is true when a
        ``payment_intent.succeeded`` event passed :meth:`verify` and activated the
        term, or a ``payment_intent.payment_failed`` event marked the payment
        failed.  An unknown payment, a failed verification and any other event type
        are all received but not handled.
        """
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])

        signature = request.META.get("HTTP_STRIPE_SIGNATURE", "")
        try:
            verified = stripe.Webhook.construct_event(
                request.body, signature, settings.STRIPE_WEBHOOK_SECRET
            )
        except Exception as exc:  # noqa: BLE001 - any failure here is a bad signature
            log.warning("Rejected Stripe webhook: %s", exc)
            return JsonResponse({"detail": "Invalid Stripe signature."}, status=400)

        event = verified.to_dict()
        event_type = event.get("type", "")
        intent = (event.get("data") or {}).get("object") or {}
        payment = payment_for_intent(intent)
        if payment is None:
            log.info("Stripe webhook %s referenced an unknown payment", event_type)
            return JsonResponse({"received": True, "handled": False})

        if event_type == "payment_intent.succeeded":
            try:
                self.verify(payment, intent)
            except PaymentVerificationError as exc:
                log.error("Stripe webhook verification failed: %s", exc)
                return JsonResponse({"received": True, "handled": False})
            mark_succeeded(
                payment,
                wallet=wallet_from_intent(intent),
                raw=jsonable(intent),
                provider_ref=intent.get("id") or payment.provider_ref,
            )
        elif event_type == "payment_intent.payment_failed":
            mark_failed(payment, jsonable(intent))
        else:
            return JsonResponse({"received": True, "handled": False})

        return JsonResponse({"received": True, "handled": True})
