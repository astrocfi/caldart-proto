"""Stripe provider: Payment Element, card / Apple Pay / Google Pay / Link.

The flow:

1. ``start`` creates a PaymentIntent for the amount the *server* computed, with
   ``automatic_payment_methods`` so the Payment Element offers every method the
   account has enabled, and metadata that ties the intent back to our row.
2. The browser confirms the intent with Stripe.js.
3. ``confirm`` retrieves the intent again and refuses to activate a membership
   unless Stripe agrees about the status, amount, currency, and payment id.
4. ``handle_webhook`` is the safety net for redirect-based methods, and is
   idempotent because :func:`~apps.payments.services.mark_succeeded` is.  It
   also carries ``charge.updated``, which is how a fee Stripe could not report
   at the moment of the charge reaches us.

Stripe is never asked to email a receipt of its own: CalDART sends one receipt,
its own, which carries the 501(c)(3) wording a donor needs.

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
from stripe.params._payment_intent_create_params import PaymentIntentCreateParams
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed, JsonResponse

from apps.payments.models import Payment, PaymentProvider, PaymentWallet, Refund, RenewalMandate
from apps.payments.providers.base import (
    MandateMethod,
    PaymentDeclinedError,
    PaymentError,
    PaymentVerificationError,
    Provider,
    ProviderFees,
    ProviderNotConfiguredError,
    ProviderRefund,
    ProviderUnavailableError,
    card_label,
    register,
)
from apps.payments.refunds import record_dashboard_refund
from apps.payments.services import fees_are_known, mark_failed, mark_succeeded, record_fees

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

#: The event Stripe sends when a charge's balance transaction becomes readable,
#: which is how a fee that was not known at checkout arrives.
CHARGE_UPDATED = "charge.updated"

#: Intent statuses that mean the customer will not be charged.
FAILED_STATUSES = frozenset({"canceled", "requires_payment_method"})

#: What every retrieval expands, so the charge and the balance transaction that
#: carries the fee come back with the intent instead of costing two more calls.
INTENT_EXPAND = ["latest_charge.balance_transaction"]

#: What a member is told when Stripe refuses an off-session charge without
#: giving a reason of its own.
DECLINED_MESSAGE = "Your card was declined."

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

    Raises :class:`~apps.payments.providers.base.ProviderNotConfiguredError` when no
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


def refund_idempotency_key(refund: Refund) -> str:
    """The key that ties one Stripe refund to one refund row.

    A call repeated after a timeout then returns the refund already taken rather
    than giving the money back twice.
    """
    return f"caldart-refund-{refund.pk}"


def succeeded_refunds(charge: dict[str, Any]) -> list[dict[str, Any]]:
    """Every refund in a charge's ``refunds.data`` that Stripe reports as succeeded.

    A charge with no refund list, or one whose refunds are all pending or failed,
    gives an empty list: only a succeeded refund has actually moved money.
    """
    data = (charge.get("refunds") or {}).get("data") or []
    return [entry for entry in data if entry.get("status") == "succeeded"]


def unavailable(payment: Payment, call: str, exc: stripe.StripeError) -> ProviderUnavailableError:
    """Log a failed Stripe call and build the error the API answers 400 with.

    Only the payment id and the exception's class are recorded: the message can
    quote request data, and nothing about a member belongs in the log.
    """
    log.warning("Stripe %s failed for payment %s: %s", call, payment.pk, type(exc).__name__)
    return ProviderUnavailableError(UNAVAILABLE_MESSAGE)


def secret_key() -> str:
    """The configured secret key, or raise so the API answers 400 rather than 500."""
    key: str = settings.STRIPE_SECRET_KEY
    if not key:
        raise ProviderNotConfiguredError("Stripe is not configured (STRIPE_SECRET_KEY is empty).")
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


def fees_from_intent(intent: dict[str, Any]) -> ProviderFees | None:
    """What Stripe kept and paid across, from the intent's balance transaction.

    Reads ``latest_charge.balance_transaction.fee`` and ``.net``, which are
    integer cents in the settlement currency.  Answers ``None`` when the intent
    was retrieved without the expansion, and when Stripe has not created the
    balance transaction yet -- some payment methods settle minutes after the
    charge, and until they do there is no fee to report.
    """
    charge = intent.get("latest_charge")
    if not isinstance(charge, dict):
        return None
    return fees_from_charge(charge)


def fees_from_charge(charge: dict[str, Any]) -> ProviderFees | None:
    """The same, from a charge on its own, as a ``charge.updated`` event carries it.

    Answers ``None`` when the charge's ``balance_transaction`` is still an
    unexpanded id or is missing altogether.
    """
    transaction = charge.get("balance_transaction")
    if not isinstance(transaction, dict):
        return None
    fee = transaction.get("fee")
    net = transaction.get("net")
    if fee is None or net is None:
        return None
    return ProviderFees(fee_cents=int(fee), net_cents=int(net))


def payment_for_charge(charge: dict[str, Any]) -> Payment | None:
    """Find our row from a charge: its metadata first, then its intent id.

    A charge carries the intent's metadata, so the same ``payment_id`` lookup
    works; failing that, the charge's ``payment_intent`` is matched against
    ``provider_ref``.  Returns ``None`` when neither finds a row.
    """
    intent_id = charge.get("payment_intent")
    return payment_for_intent(
        {"metadata": charge.get("metadata") or {}, "id": intent_id if intent_id else None}
    )


def payment_for_intent(intent: dict[str, Any]) -> Payment | None:
    """Find our row from a webhook object's metadata, falling back to its ids.

    ``intent`` is the event's ``data.object``, which is a PaymentIntent for the
    payment events and a charge for ``charge.refunded``.  Matches only Stripe
    payments: ``metadata.payment_id`` first -- a charge inherits the intent's
    metadata -- then ``provider_ref`` against the object's own id and, for a
    charge, against the ``payment_intent`` it names.  A ``payment_id`` that is not
    a number matches nothing, and the search falls through to those ids.  Returns
    ``None`` when none of them finds a row.
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

    for ref in (intent.get("id"), intent.get("payment_intent")):
        if not ref:
            continue
        found = Payment.objects.filter(provider=PaymentProvider.STRIPE, provider_ref=ref).first()
        if found is not None:
            return found
    return None


@register
class StripeProvider(Provider):
    """Stripe via the Payment Element: card, Apple Pay, Google Pay and Link."""

    slug = "stripe"

    @classmethod
    def is_configured(cls) -> bool:
        """Whether both ``STRIPE_SECRET_KEY`` and ``STRIPE_PUBLISHABLE_KEY`` are set.

        The Payment Element needs the publishable key in the browser as much as the
        server needs the secret key, so one without the other is not usable.
        """
        return bool(settings.STRIPE_SECRET_KEY and settings.STRIPE_PUBLISHABLE_KEY)

    # ----------------------------------------------------------------- start
    def start(self, payment: Payment) -> dict[str, Any]:
        """Create the PaymentIntent and hand the client its ``client_secret``.

        Stores the intent's id as ``provider_ref`` and the whole intent in ``raw``,
        and returns ``{"client_secret": ...}``.  The call is idempotent per payment,
        so starting the same payment twice returns the first intent rather than
        charging twice.

        A payer with a ``pending`` renewal mandate has a Stripe customer created
        for them, and the intent is created against it with
        ``setup_future_usage="off_session"``, so the method they pay with is the
        one CalDART renews from.  Raises :class:`ProviderNotConfiguredError`
        without a secret key and :class:`ProviderUnavailableError` when Stripe
        cannot be reached.
        """
        client = stripe_client()
        params: PaymentIntentCreateParams = {
            "amount": payment.amount_cents,
            "currency": payment.currency,
            "automatic_payment_methods": {"enabled": True},
            "description": f"CalDART \u00b7 {payment.description}",
            # stripe's params type the field as a string, but its API takes null
            # for "send no receipt".
            "receipt_email": payment.user.email or None,  # type: ignore[typeddict-item]
            "metadata": {
                "payment_id": str(payment.pk),
                "user_id": str(payment.user_id),
                "plan": payment.plan.slug if payment.plan is not None else "",
            },
        }
        mandate = pending_mandate(payment)
        if mandate is not None:
            # Saving the method needs a customer to save it against, and
            # off-session usage has to be declared when the intent is created.
            params["customer"] = self.ensure_customer(mandate)
            params["setup_future_usage"] = "off_session"
        try:
            created = client.v1.payment_intents.create(
                params, {"idempotency_key": idempotency_key(payment)}
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
        :class:`ProviderUnavailableError` when Stripe cannot be reached.
        """
        intent_id = payment_intent_id or payment.provider_ref
        if not intent_id:
            raise PaymentVerificationError("No PaymentIntent to confirm.")
        if payment.provider_ref and intent_id != payment.provider_ref:
            raise PaymentVerificationError("That PaymentIntent belongs to another payment.")

        client = stripe_client()
        try:
            retrieved = client.v1.payment_intents.retrieve(intent_id, {"expand": INTENT_EXPAND})
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

        fees = fees_from_intent(intent)
        mark_succeeded(
            payment,
            wallet=wallet_from_intent(intent),
            raw=jsonable(intent),
            provider_ref=intent["id"],
            fee_cents=fees.fee_cents if fees is not None else None,
            net_cents=fees.net_cents if fees is not None else None,
        )
        return True

    def record_refunds(self, payment: Payment, charge: dict[str, Any]) -> int:
        """File every succeeded refund on ``charge`` that we have no row for yet.

        Returns how many refunds were recorded, which is zero when they are all
        already on file -- the ordinary answer to a redelivered webhook, and to
        the notification for a refund CalDART itself issued.  A refund Stripe
        reports as pending or failed is skipped: no money has moved.
        """
        recorded = 0
        for entry in succeeded_refunds(charge):
            written = record_dashboard_refund(
                payment,
                amount_cents=int(entry.get("amount") or 0),
                provider_ref=str(entry.get("id") or ""),
                raw=jsonable(entry),
            )
            if written is not None:
                recorded += 1
        return recorded

    def verify(self, payment: Payment, intent: dict[str, Any]) -> None:
        """Everything about the intent that must match our own row.

        Returns ``None`` when the intent's ``metadata.payment_id``, ``amount``, and
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

    # ---------------------------------------------------------------- refund
    def refund(self, payment: Payment, refund: Refund) -> ProviderRefund:
        """Refund ``refund.amount_cents`` of the payment's PaymentIntent.

        Returns Stripe's refund id and the refund object it answered with.  The
        call carries an idempotency key built from the refund row, so a repeat
        after a timeout gives the money back once.  Raises
        :class:`PaymentVerificationError` when the payment carries no intent to
        refund, :class:`ProviderNotConfiguredError` without a secret key and
        :class:`ProviderUnavailableError` when Stripe cannot be reached or
        refuses the refund.
        """
        if not payment.provider_ref:
            raise PaymentVerificationError("That payment has no PaymentIntent to refund.")
        client = stripe_client()
        try:
            created = client.v1.refunds.create(
                {
                    "payment_intent": payment.provider_ref,
                    "amount": refund.amount_cents,
                    "metadata": {"refund_id": str(refund.pk), "payment_id": str(payment.pk)},
                },
                {"idempotency_key": refund_idempotency_key(refund)},
            )
        except stripe.StripeError as exc:
            raise unavailable(payment, "refunds.create", exc) from exc
        answer = created.to_dict()
        return ProviderRefund(provider_ref=answer["id"], raw=jsonable(answer))

    # --------------------------------------------------------------- webhook
    def handle_webhook(self, request: HttpRequest) -> HttpResponse:
        """Verify ``Stripe-Signature``, then apply the event idempotently.

        Answers 405 to any method but ``POST`` and 400 to a body whose signature
        does not check out.  Otherwise the answer is 200 with
        ``{"received": true, "handled": ...}``: ``handled`` is true when a
        ``payment_intent.succeeded`` event passed :meth:`verify` and activated the
        term, when a ``payment_intent.payment_failed`` event marked the payment
        failed, when a ``charge.updated`` event filled in a fee that was not known
        when the money arrived, and when a ``charge.refunded`` event recorded a
        refund taken in Stripe's own dashboard.  An unknown payment, a failed
        verification and any other event type are all received but not handled.
        """
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])

        signature = request.META.get("HTTP_STRIPE_SIGNATURE", "")
        try:
            verified = stripe.Webhook.construct_event(
                request.body, signature, settings.STRIPE_WEBHOOK_SECRET
            )
        except Exception as exc:
            log.warning("Rejected Stripe webhook: %s", exc)
            return JsonResponse({"detail": "Invalid Stripe signature."}, status=400)

        event = verified.to_dict()
        event_type = event.get("type", "")
        resource = (event.get("data") or {}).get("object") or {}
        if event_type == CHARGE_UPDATED:
            return self.handle_charge_updated(resource)

        intent = resource
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
            fees = fees_from_intent(intent)
            mark_succeeded(
                payment,
                wallet=wallet_from_intent(intent),
                raw=jsonable(intent),
                provider_ref=intent.get("id") or payment.provider_ref,
                fee_cents=fees.fee_cents if fees is not None else None,
                net_cents=fees.net_cents if fees is not None else None,
            )
        elif event_type == "payment_intent.payment_failed":
            mark_failed(payment, jsonable(intent))
        elif event_type == "charge.refunded":
            self.record_refunds(payment, intent)
        else:
            return JsonResponse({"received": True, "handled": False})

        return JsonResponse({"received": True, "handled": True})

    def handle_charge_updated(self, charge: dict[str, Any]) -> JsonResponse:
        """Fill in a fee Stripe could not report when the money arrived.

        ``charge.updated`` is the event that fires when the balance transaction
        finally exists.  The fee is taken from the event when it carries an
        expanded balance transaction, and asked for again otherwise.  A payment
        whose fee is already recorded is left alone, so a re-delivery changes
        nothing, and a payment Stripe cannot be asked about is acknowledged
        unhandled rather than failing the delivery.

        The fee is recorded whatever state the payment is in: Stripe orders no
        deliveries, so this event can arrive before the
        ``payment_intent.succeeded`` that settles the row, and
        :func:`~apps.payments.services.settled_fees` keeps what is already
        there.
        """
        payment = payment_for_charge(charge)
        if payment is None or fees_are_known(payment):
            return JsonResponse({"received": True, "handled": False})

        fees = fees_from_charge(charge)
        if fees is None:
            try:
                fees = self.fetch_fees(payment)
            except PaymentError as exc:
                log.warning("Could not read the fee for payment %s: %s", payment.pk, exc)
                return JsonResponse({"received": True, "handled": False})
        if fees is None:
            return JsonResponse({"received": True, "handled": False})

        record_fees(payment, fee_cents=fees.fee_cents, net_cents=fees.net_cents)
        return JsonResponse({"received": True, "handled": True})

    # ------------------------------------------------------------------ fees
    def fetch_fees(self, payment: Payment) -> ProviderFees | None:
        """Retrieve the intent again and read the fee off its balance transaction.

        Answers ``None`` for a payment with no intent id, and for one whose
        balance transaction Stripe has still not created.  Raises
        :class:`ProviderNotConfiguredError` without a secret key and
        :class:`ProviderUnavailableError` when Stripe cannot be reached.
        """
        if not payment.provider_ref:
            return None
        client = stripe_client()
        try:
            retrieved = client.v1.payment_intents.retrieve(
                payment.provider_ref, {"expand": INTENT_EXPAND}
            )
        except stripe.StripeError as exc:
            raise unavailable(payment, "payment_intents.retrieve", exc) from exc
        return fees_from_intent(retrieved.to_dict())

    # ------------------------------------------------------------- mandates
    def ensure_customer(self, mandate: RenewalMandate) -> str:
        """The Stripe customer this mandate saves its method against.

        Returns the mandate's ``customer_ref`` when it already has one; otherwise
        creates a customer carrying the member's name, email address and id, saves
        its id on the mandate and returns that.  Raises
        :class:`ProviderUnavailableError` when Stripe cannot be reached.
        """
        if mandate.customer_ref:
            return mandate.customer_ref
        user = mandate.user
        try:
            created = stripe_client().v1.customers.create(
                {
                    "email": user.email,
                    "name": user.display_name,
                    "metadata": {"user_id": str(user.pk)},
                }
            )
        except stripe.StripeError as exc:
            log.warning(
                "Stripe customers.create failed for user %s: %s", user.pk, type(exc).__name__
            )
            raise ProviderUnavailableError(UNAVAILABLE_MESSAGE) from exc
        customer_id: str = created.to_dict()["id"]
        mandate.customer_ref = customer_id
        mandate.save(update_fields=["customer_ref", "updated_at"])
        return customer_id

    def start_mandate(self, mandate: RenewalMandate) -> dict[str, Any]:
        """Create the SetupIntent the Payment Element collects a card into.

        Returns ``{"client_secret": ...}`` for the Element rendered in ``setup``
        mode, having made sure the mandate has a customer to save against.  No
        money moves.  Raises :class:`ProviderNotConfiguredError` without a secret
        key, :class:`ProviderUnavailableError` when Stripe cannot be reached, and
        :class:`PaymentVerificationError` when Stripe answers without a client
        secret.
        """
        customer = self.ensure_customer(mandate)
        try:
            created = stripe_client().v1.setup_intents.create(
                {
                    "customer": customer,
                    "usage": "off_session",
                    "automatic_payment_methods": {"enabled": True},
                    "metadata": {
                        "user_id": str(mandate.user_id),
                        "mandate_id": str(mandate.pk),
                    },
                }
            )
        except stripe.StripeError as exc:
            log.warning("Stripe setup_intents.create failed: %s", type(exc).__name__)
            raise ProviderUnavailableError(UNAVAILABLE_MESSAGE) from exc
        intent = created.to_dict()
        secret = intent.get("client_secret")
        if not secret:
            raise PaymentVerificationError("Stripe returned no SetupIntent client secret.")
        return {"client_secret": secret}

    def confirm_mandate(self, mandate: RenewalMandate, **kwargs: Any) -> MandateMethod:
        """Read back the card the member saved, and check it is theirs.

        ``setup_intent_id`` names the SetupIntent the browser confirmed.  Raises
        :class:`PaymentVerificationError` when no id is given, when the intent
        belongs to another customer, when Stripe reports anything but
        ``succeeded``, and when the intent carries no payment method; raises
        :class:`ProviderUnavailableError` when Stripe cannot be reached.
        """
        setup_intent_id = str(kwargs.get("setup_intent_id") or "")
        if not setup_intent_id:
            raise PaymentVerificationError("No SetupIntent to confirm.")
        try:
            retrieved = stripe_client().v1.setup_intents.retrieve(
                setup_intent_id, {"expand": ["payment_method"]}
            )
        except stripe.StripeError as exc:
            log.warning("Stripe setup_intents.retrieve failed: %s", type(exc).__name__)
            raise ProviderUnavailableError(UNAVAILABLE_MESSAGE) from exc
        intent = retrieved.to_dict()

        customer = intent.get("customer")
        customer_id = customer.get("id") if isinstance(customer, dict) else customer
        if str(customer_id or "") != mandate.customer_ref:
            raise PaymentVerificationError("That SetupIntent belongs to another customer.")
        if intent.get("status") != "succeeded":
            raise PaymentVerificationError(f"Stripe reports the setup as '{intent.get('status')}'.")

        method = intent.get("payment_method")
        if not isinstance(method, dict):
            raise PaymentVerificationError("Stripe saved no payment method.")
        return method_from_card(
            str(method.get("id") or ""),
            str(customer_id or ""),
            method.get("card") or {},
            intent,
        )

    def charge_mandate(self, mandate: RenewalMandate, payment: Payment) -> None:
        """Charge the saved card off-session, without the member present.

        Confirms a PaymentIntent against the mandate's customer and payment
        method, keyed so a repeated attempt cannot charge twice, and marks the
        payment succeeded when Stripe reports ``succeeded``.  Raises
        :class:`PaymentDeclinedError` carrying Stripe's own wording when the card
        is refused or further authentication is required, and
        :class:`ProviderUnavailableError` when Stripe cannot be reached.
        """
        try:
            created = stripe_client().v1.payment_intents.create(
                {
                    "amount": payment.amount_cents,
                    "currency": payment.currency,
                    "customer": mandate.customer_ref,
                    "payment_method": mandate.method_ref,
                    "off_session": True,
                    "confirm": True,
                    "description": f"CalDART \u00b7 {payment.description}",
                    "metadata": {
                        "payment_id": str(payment.pk),
                        "user_id": str(payment.user_id),
                        "plan": payment.plan.slug if payment.plan is not None else "",
                    },
                },
                {"idempotency_key": f"caldart-renewal-{payment.pk}"},
            )
        except stripe.CardError as exc:
            raise PaymentDeclinedError(exc.user_message or DECLINED_MESSAGE) from exc
        except stripe.StripeError as exc:
            raise unavailable(payment, "payment_intents.create off-session", exc) from exc

        intent = created.to_dict()
        payment.provider_ref = intent["id"]
        payment.save(update_fields=["provider_ref", "updated_at"])
        if intent.get("status") != "succeeded":
            raise PaymentDeclinedError(decline_reason(intent))
        mark_succeeded(
            payment,
            wallet=wallet_from_intent(intent),
            raw=jsonable(intent),
            provider_ref=intent["id"],
        )

    def method_from_payment(self, payment: Payment) -> MandateMethod | None:
        """The card a succeeded checkout saved, read off the stored intent.

        ``None`` when the intent recorded no payment method or no card details,
        which is what a payment that saved nothing looks like.
        """
        intent = payment.raw or {}
        method_id = intent.get("payment_method")
        charge = intent.get("latest_charge")
        details = charge.get("payment_method_details") if isinstance(charge, dict) else None
        card = details.get("card") if isinstance(details, dict) else None
        if not method_id or not isinstance(card, dict):
            return None
        customer = intent.get("customer")
        customer_id = customer.get("id") if isinstance(customer, dict) else customer
        return method_from_card(str(method_id), str(customer_id or ""), card, intent)


def decline_reason(intent: dict[str, Any]) -> str:
    """The member-facing reason an off-session intent did not succeed.

    Stripe's ``last_payment_error.message`` when there is one, otherwise the
    intent's status spelled out, so the renewal attempt always records something
    a person can act on.
    """
    error = intent.get("last_payment_error")
    if isinstance(error, dict) and error.get("message"):
        return str(error["message"])
    status = intent.get("status")
    if status == "requires_action":
        return "Your bank asked for confirmation, which we cannot give off-session."
    return DECLINED_MESSAGE


def pending_mandate(payment: Payment) -> RenewalMandate | None:
    """The Stripe mandate this payment would activate, or ``None``.

    Read at checkout, so an intent that is going to save a card is created with
    a customer and with ``setup_future_usage``.
    """
    # Inline: renewals reads this package, so a top-level import would close the
    # cycle between the two.
    from apps.payments.renewals import pending_mandate_for

    return pending_mandate_for(payment)


def method_from_card(
    payment_method_id: str, customer_ref: str, card: dict[str, Any], raw: dict[str, Any]
) -> MandateMethod:
    """Build the saved-method record from a Stripe card object."""
    brand = str(card.get("brand") or "")
    last4 = str(card.get("last4") or "")
    exp_month = card.get("exp_month")
    exp_year = card.get("exp_year")
    return MandateMethod(
        method_ref=payment_method_id,
        customer_ref=customer_ref,
        brand=brand,
        last4=last4,
        exp_month=int(exp_month) if exp_month is not None else None,
        exp_year=int(exp_year) if exp_year is not None else None,
        label=card_label(
            brand,
            last4,
            int(exp_month) if exp_month is not None else None,
            int(exp_year) if exp_year is not None else None,
        ),
        raw=jsonable(raw),
    )
