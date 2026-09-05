"""Stripe provider: Payment Element, card / Apple Pay / Google Pay / Link.

The flow (PLAN §10):

1. ``start`` creates a PaymentIntent for the amount the *server* computed, with
   ``automatic_payment_methods`` so the Payment Element offers every method the
   account has enabled, and metadata that ties the intent back to our row.
2. The browser confirms the intent with Stripe.js.
3. ``confirm`` retrieves the intent again and refuses to activate a membership
   unless Stripe agrees about the status, amount, currency and payment id.
4. ``handle_webhook`` is the safety net for redirect-based methods, and is
   idempotent because :func:`~apps.payments.services.mark_succeeded` is.
"""

from __future__ import annotations

import json
import logging

import stripe
from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed, JsonResponse

from apps.payments.models import Payment, PaymentProvider, PaymentWallet
from apps.payments.providers.base import (
    PaymentVerificationError,
    Provider,
    ProviderNotConfigured,
    register,
)
from apps.payments.services import mark_failed, mark_succeeded

log = logging.getLogger(__name__)

#: ``payment_method_details.card.wallet.type`` values mapped onto our choices.
WALLET_TYPES: dict[str, str] = {
    "apple_pay": PaymentWallet.APPLE_PAY,
    "google_pay": PaymentWallet.GOOGLE_PAY,
    "link": PaymentWallet.LINK,
}

#: Intent statuses that mean the customer will not be charged.
FAILED_STATUSES = frozenset({"canceled", "requires_payment_method"})


def secret_key() -> str:
    """The configured secret key, or raise so the API answers 400 rather than 500."""
    key = settings.STRIPE_SECRET_KEY
    if not key:
        raise ProviderNotConfigured("Stripe is not configured (STRIPE_SECRET_KEY is empty).")
    return key


def jsonable(value) -> dict:
    """A plain, JSON-serialisable dict for ``Payment.raw``.

    Stripe's objects are dict subclasses, but they nest ``StripeObject``s and
    carry non-serialisable helpers, so round-trip through JSON.
    """
    to_dict = getattr(value, "to_dict_recursive", None)
    if callable(to_dict):
        value = to_dict()
    return json.loads(json.dumps(value, default=str))


def wallet_from_intent(intent) -> str:
    """Map ``latest_charge.payment_method_details`` onto our wallet choices."""
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


def payment_for_intent(intent) -> Payment | None:
    """Find our row from the intent's metadata, falling back to the intent id."""
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
    slug = "stripe"

    # ----------------------------------------------------------------- start
    def start(self, payment: Payment) -> dict:
        """Create the PaymentIntent and hand the client its ``client_secret``."""
        intent = stripe.PaymentIntent.create(
            api_key=secret_key(),
            amount=payment.amount_cents,
            currency=payment.currency,
            automatic_payment_methods={"enabled": True},
            description=f"CalDART · {payment.description}",
            receipt_email=payment.user.email or None,
            metadata={
                "payment_id": str(payment.pk),
                "user_id": str(payment.user_id),
                "plan": payment.plan.slug if payment.plan_id else "",
            },
        )
        payment.provider_ref = intent["id"]
        payment.raw = jsonable(intent)
        payment.save(update_fields=["provider_ref", "raw", "updated_at"])
        return {"client_secret": intent["client_secret"]}

    # --------------------------------------------------------------- confirm
    def confirm(self, payment: Payment, *, payment_intent_id: str = "", **kwargs) -> bool:
        """Retrieve the intent and verify it before activating anything."""
        intent_id = payment_intent_id or payment.provider_ref
        if not intent_id:
            raise PaymentVerificationError("No PaymentIntent to confirm.")
        if payment.provider_ref and intent_id != payment.provider_ref:
            raise PaymentVerificationError("That PaymentIntent belongs to another payment.")

        intent = stripe.PaymentIntent.retrieve(
            intent_id, api_key=secret_key(), expand=["latest_charge"]
        )
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

    def verify(self, payment: Payment, intent) -> None:
        """Everything about the intent that must match our own row."""
        metadata = intent.get("metadata") or {}
        if str(metadata.get("payment_id") or "") != str(payment.pk):
            raise PaymentVerificationError("PaymentIntent metadata does not match this payment.")
        if int(intent.get("amount") or 0) != payment.amount_cents:
            raise PaymentVerificationError("PaymentIntent amount does not match this payment.")
        if str(intent.get("currency") or "").lower() != payment.currency.lower():
            raise PaymentVerificationError("PaymentIntent currency does not match this payment.")

    # --------------------------------------------------------------- webhook
    def handle_webhook(self, request: HttpRequest) -> HttpResponse:
        """Verify ``Stripe-Signature``, then apply the event idempotently."""
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])

        signature = request.META.get("HTTP_STRIPE_SIGNATURE", "")
        try:
            event = stripe.Webhook.construct_event(
                request.body, signature, settings.STRIPE_WEBHOOK_SECRET
            )
        except Exception as exc:  # noqa: BLE001 - any failure here is a bad signature
            log.warning("Rejected Stripe webhook: %s", exc)
            return JsonResponse({"detail": "Invalid Stripe signature."}, status=400)

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
