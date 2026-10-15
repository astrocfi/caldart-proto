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

import logging
from functools import lru_cache
from typing import Any

import stripe
from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed, JsonResponse
from stripe.params._payment_intent_create_params import PaymentIntentCreateParams

from apps.payments.models import (
    Payment,
    PaymentStatus,
    Refund,
    RenewalMandate,
)
from apps.payments.providers.base import (
    MandateMethod,
    PaymentDeclinedError,
    PaymentError,
    PaymentPendingError,
    PaymentVerificationError,
    Provider,
    ProviderFees,
    ProviderNotConfiguredError,
    ProviderRefund,
    ProviderUnavailableError,
    register,
)
from apps.payments.providers.stripe_intents import (
    DECLINED_MESSAGE,
    PENDING_STATUSES,
    charge_customer,
    decline_reason,
    fees_from_charge,
    fees_from_intent,
    jsonable,
    method_from_card,
    payment_for_charge,
    payment_for_intent,
    renewal_intent_to_adopt,
    succeeded_refunds,
    wallet_from_intent,
)
from apps.payments.receipts import SETTLED_STATUSES
from apps.payments.refunds import record_dashboard_refund
from apps.payments.services import fees_are_known, mark_failed, mark_succeeded, record_fees

log = logging.getLogger(__name__)

#: What a member is told when Stripe times out or answers with an error of its
#: own.  It says nothing about the money: a call can fail after Stripe acted.
UNAVAILABLE_MESSAGE = "Stripe didn't answer. Try again in a moment."

#: The event Stripe sends when a charge's balance transaction becomes readable,
#: which is how a fee that was not known at checkout arrives.
CHARGE_UPDATED = "charge.updated"

#: Intent statuses that mean the customer will not be charged.
FAILED_STATUSES = frozenset({"canceled", "requires_payment_method"})

#: The status of an intent Stripe declined, whose client secret would still take
#: another payment method.  A SetupIntent that declined a card reads the same.
DECLINED_STATUS = "requires_payment_method"

#: The event Stripe sends when a SetupIntent's card is declined.
SETUP_FAILED = "setup_intent.setup_failed"

#: The key on a pending mandate's ``raw`` naming the SetupIntent saving its method,
#: so a failure reported for an older SetupIntent never discards a newer setup.
SETUP_INTENT_KEY = "setup_intent_id"

#: What every retrieval expands, so the charge and the balance transaction that
#: carries the fee come back with the intent instead of costing two more calls.
INTENT_EXPAND = ["latest_charge.balance_transaction"]


#: What the renewal scan logs about a charge Stripe is still processing.
PROCESSING_MESSAGE = "Stripe is still processing the charge."

#: What the member is told when the renewal has no saved card to charge.
NO_METHOD_MESSAGE = "There is no saved card to charge."

#: What the member is told when Stripe no longer has the saved customer or card.
METHOD_GONE_MESSAGE = "The saved card is no longer on file."

#: The parameters a ``resource_missing`` refusal names when the saved method is gone.
MISSING_METHOD_PARAMS = frozenset({"customer", "payment_method"})

#: How long before its payment row was written an off-session intent may have been
#: created, in seconds, so a lookup is not thrown by the two clocks disagreeing.
RENEWAL_LOOKUP_SLACK_SECONDS = 3_600

#: The most intents one lookup reads: Stripe's own page limit.  The lookup reads one
#: customer's intents created since the payment was written, which is a handful.
RENEWAL_LOOKUP_LIMIT = 100

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


def renewal_idempotency_key(payment: Payment) -> str:
    """The key that ties one off-session charge to one renewal payment row.

    The renewal scan keeps a payment whose charge it could not finish and charges
    the same row again, so Stripe answers the repeat with the intent it already
    made.  Stripe forgets a key after 24 hours, which is why a repeat first looks
    for that intent itself (``find_mandate_charge``).
    """
    return f"caldart-renewal-{payment.pk}"


def refund_idempotency_key(refund: Refund) -> str:
    """The key that ties one Stripe refund to one refund row.

    A call repeated after a timeout then returns the refund already taken rather
    than giving the money back twice.
    """
    return f"caldart-refund-{refund.pk}"


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


def close_declined_intent(payment: Payment, intent: dict[str, Any]) -> None:
    """Cancel ``intent`` at Stripe once ``payment`` is marked failed after a decline.

    An intent left in ``requires_payment_method`` takes another card through the same
    client secret, straight from a browser.  Canceling it leaves the client secret good
    for nothing, so paying after a decline starts a payment of its own, one the
    server starts and counts.  Nothing is asked
    of Stripe for an intent in any other status, or for a payment that is not failed
    (one that succeeded first).  A cancel Stripe refuses, or cannot be reached for, is
    logged at WARNING and otherwise ignored, since the payment is failed either way.
    """
    if payment.status != PaymentStatus.FAILED or intent.get("status") != DECLINED_STATUS:
        return
    try:
        stripe_client().v1.payment_intents.cancel(intent["id"])
    except stripe.StripeError as exc:
        log.warning("Could not cancel declined PaymentIntent %s: %s", intent["id"], exc)


def cancel_setup_intent(setup_id: str) -> None:
    """Cancel the SetupIntent ``setup_id``, so its client secret takes no card.

    Used after a decline and whenever a pending mandate's setup is replaced or thrown
    away.  A cancel Stripe refuses, or cannot be reached for, and a Stripe with no
    secret key configured, are logged at WARNING and otherwise ignored: the setup is
    finished with either way.
    """
    try:
        stripe_client().v1.setup_intents.cancel(setup_id)
    except (stripe.StripeError, ProviderNotConfiguredError) as exc:
        log.warning("Could not cancel SetupIntent %s: %s", setup_id, exc)


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
        marked succeeded, and ``True`` without asking Stripe for a payment whose
        money already arrived -- succeeded, partly refunded, or refunded -- which is
        left exactly as it is; returns ``False``, having marked the payment failed, when
        Stripe reports ``canceled`` or ``requires_payment_method``, and canceling a
        ``requires_payment_method`` intent so it takes no other card
        (:func:`close_declined_intent`).  Raises
        :class:`PaymentVerificationError` when there is no intent to confirm, when
        the intent belongs to another payment, when :meth:`verify` disagrees, and
        when Stripe reports any other status.  Raises
        :class:`ProviderUnavailableError` when Stripe cannot be reached.
        """
        if payment.status in SETTLED_STATUSES:
            # A second click, a webhook that beat the browser back, or a refund
            # since: nothing Stripe says now changes where the money went.
            return True

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
                close_declined_intent(mark_failed(payment, jsonable(intent)), intent)
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
        failed (and canceled the declined intent, :func:`close_declined_intent`),
        when a ``charge.updated`` event filled in a fee that was not known when the
        money arrived, when a ``charge.refunded`` event recorded a refund taken in
        Stripe's own dashboard, and when a ``setup_intent.setup_failed`` event canceled
        a declined SetupIntent (:meth:`handle_setup_failed`).  An unknown payment, a
        failed verification and any other event type are all received but not handled.
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
        if event_type == SETUP_FAILED:
            return self.handle_setup_failed(resource)

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
            close_declined_intent(mark_failed(payment, jsonable(intent)), intent)
        elif event_type == "charge.refunded":
            self.record_refunds(payment, intent)
        else:
            return JsonResponse({"received": True, "handled": False})

        return JsonResponse({"received": True, "handled": True})

    def handle_setup_failed(self, setup: dict[str, Any]) -> JsonResponse:
        """Cancel a SetupIntent Stripe declined, whatever became of its mandate.

        A SetupIntent left in ``requires_payment_method`` is canceled
        (:func:`cancel_setup_intent`), so its client secret takes no other card, and
        the event is answered ``handled``.  The event is signed, so the SetupIntent
        is canceled without looking for the mandate it was started for, which may
        have been discarded or set up again with another provider since.  No mandate
        is changed: a pending one is replaced by the member's next setup or thrown
        away by a checkout that saves nothing.  A SetupIntent in any other status is
        answered ``handled`` false.
        """
        if setup.get("status") != DECLINED_STATUS:
            return JsonResponse({"received": True, "handled": False})
        cancel_setup_intent(str(setup.get("id") or ""))
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
        mode, having made sure the mandate has a customer to save against, and
        records the SetupIntent's id on the mandate's ``raw`` under
        :data:`SETUP_INTENT_KEY`, canceling one recorded there before
        (:meth:`abandon_setup`).  No money moves.  Raises
        :class:`ProviderNotConfiguredError` without a secret key,
        :class:`ProviderUnavailableError` when Stripe cannot be reached, and
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
        self.abandon_setup(mandate)
        mandate.raw = {**(mandate.raw or {}), SETUP_INTENT_KEY: str(intent.get("id") or "")}
        mandate.save(update_fields=["raw", "updated_at"])
        return {"client_secret": secret}

    def abandon_setup(self, mandate: RenewalMandate) -> None:
        """Cancel the SetupIntent ``mandate.raw`` names under :data:`SETUP_INTENT_KEY`.

        Nothing is asked of Stripe for a mandate that names none.  The key itself is
        left for the caller, which is about to replace or delete the mandate's ``raw``.
        """
        setup_id = (mandate.raw or {}).get(SETUP_INTENT_KEY)
        if setup_id:
            cancel_setup_intent(str(setup_id))

    def confirm_mandate(self, mandate: RenewalMandate, **kwargs: Any) -> MandateMethod:
        """Read back the card the member saved, and check it is theirs.

        ``setup_intent_id`` names the SetupIntent the browser confirmed.  Raises
        :class:`PaymentVerificationError` when no id is given, when the intent
        belongs to another customer, when Stripe reports anything but
        ``succeeded``, and when the intent carries no payment method; raises
        :class:`ProviderUnavailableError` when Stripe cannot be reached.  A
        SetupIntent Stripe reports as ``requires_payment_method``, which is what a
        declined card leaves, is canceled before the refusal is raised, so its client
        secret takes no other card.
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
        status = intent.get("status")
        if status != "succeeded":
            if status == DECLINED_STATUS:
                cancel_setup_intent(setup_intent_id)
            raise PaymentVerificationError(f"Stripe reports the setup as '{status}'.")

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

        Confirms a PaymentIntent against the customer and payment method stamped on
        the payment when it was first sent (``charge_customer_ref``,
        ``charge_method_ref``), falling back to the mandate's own, under
        :func:`renewal_idempotency_key`, so a repeated attempt for the same payment
        cannot charge twice even after the member changed card, and settles the
        payment from what Stripe answers (:meth:`settle_renewal`).  Raises
        :class:`PaymentDeclinedError` carrying Stripe's own wording when the card is
        refused or further authentication is required, and also when there is no
        customer or method to charge or Stripe no longer has the one named
        (``resource_missing``); :class:`PaymentPendingError` when Stripe reports the
        charge ``processing``; and :class:`ProviderUnavailableError` when Stripe
        cannot be reached.
        """
        customer = charge_customer(mandate, payment)
        method = payment.charge_method_ref or mandate.method_ref
        if not customer or not method:
            raise PaymentDeclinedError(NO_METHOD_MESSAGE)
        try:
            created = stripe_client().v1.payment_intents.create(
                {
                    "amount": payment.amount_cents,
                    "currency": payment.currency,
                    "customer": customer,
                    "payment_method": method,
                    "off_session": True,
                    "confirm": True,
                    "description": f"CalDART \u00b7 {payment.description}",
                    "metadata": {
                        "payment_id": str(payment.pk),
                        "user_id": str(payment.user_id),
                        "plan": payment.plan.slug if payment.plan is not None else "",
                    },
                },
                {"idempotency_key": renewal_idempotency_key(payment)},
            )
        except stripe.CardError as exc:
            raise PaymentDeclinedError(exc.user_message or DECLINED_MESSAGE) from exc
        except stripe.InvalidRequestError as exc:
            # A customer or a card deleted at Stripe was never charged: that is the
            # member's method gone, not Stripe out of reach.
            if exc.code == "resource_missing" and exc.param in MISSING_METHOD_PARAMS:
                raise PaymentDeclinedError(METHOD_GONE_MESSAGE) from exc
            raise unavailable(payment, "payment_intents.create off-session", exc) from exc
        except stripe.StripeError as exc:
            raise unavailable(payment, "payment_intents.create off-session", exc) from exc
        self.settle_renewal(payment, created.to_dict())

    def find_mandate_charge(self, mandate: RenewalMandate, payment: Payment) -> bool:
        """Settle ``payment`` from the off-session intent an earlier call made, if any.

        A payment that already names its intent has that intent retrieved.  One that
        does not -- the create call timed out before Stripe's answer arrived -- has
        the intents of the customer it was sent for (``charge_customer_ref``) listed
        from shortly before the payment was written, and the one whose
        ``metadata.payment_id`` is this payment's is taken: a succeeded one first,
        then a processing one.  Listing is strongly consistent, unlike Stripe's
        search.  An intent found is settled by :meth:`settle_renewal` and answers
        ``True``; none answers ``False``.  A payment with no customer to list was
        never charged, and answers ``False`` without asking Stripe.  Raises
        :class:`ProviderUnavailableError` when Stripe cannot be asked, and when the
        list runs past one page without finding the payment, since the intent could
        be on the next.
        """
        client = stripe_client()
        customer = charge_customer(mandate, payment)
        has_more = False
        try:
            if payment.provider_ref:
                retrieved = client.v1.payment_intents.retrieve(payment.provider_ref)
                intents = [retrieved.to_dict()]
            elif not customer:
                return False
            else:
                since = int(payment.created_at.timestamp()) - RENEWAL_LOOKUP_SLACK_SECONDS
                listed = client.v1.payment_intents.list(
                    {
                        "customer": customer,
                        "created": {"gte": since},
                        "limit": RENEWAL_LOOKUP_LIMIT,
                    }
                )
                intents = [intent.to_dict() for intent in listed.data]
                has_more = bool(listed.has_more)
        except stripe.StripeError as exc:
            raise unavailable(payment, "payment_intents lookup off-session", exc) from exc

        mine = [
            intent
            for intent in intents
            if str((intent.get("metadata") or {}).get("payment_id") or "") == str(payment.pk)
        ]
        if not mine and has_more:
            log.error("Stripe listed more intents than one page for payment %s", payment.pk)
            raise ProviderUnavailableError(UNAVAILABLE_MESSAGE)
        if not mine:
            return False
        self.settle_renewal(payment, renewal_intent_to_adopt(mine))
        return True

    def settle_renewal(self, payment: Payment, intent: dict[str, Any]) -> None:
        """Record what Stripe made of an off-session charge for ``payment``.

        The intent's id is stored as ``provider_ref`` first, whatever its status,
        so a later lookup retrieves it directly.  ``succeeded`` marks the payment
        succeeded; ``processing`` raises :class:`PaymentPendingError`; every other
        status raises :class:`PaymentDeclinedError` with :func:`decline_reason`.
        """
        payment.provider_ref = intent["id"]
        payment.save(update_fields=["provider_ref", "updated_at"])
        status = intent.get("status")
        if status in PENDING_STATUSES:
            raise PaymentPendingError(PROCESSING_MESSAGE)
        if status != "succeeded":
            raise PaymentDeclinedError(decline_reason(intent))
        mark_succeeded(
            payment,
            wallet=wallet_from_intent(intent),
            raw=jsonable(intent),
            provider_ref=intent["id"],
        )

    def method_from_payment(self, payment: Payment) -> MandateMethod | None:
        """The card a succeeded checkout saved, read off the stored intent.

        The intent stored by the browser's confirm carries its charge expanded, so
        the card is read straight out of it.  The intent stored by the
        ``payment_intent.succeeded`` webhook does not -- ``latest_charge`` is a
        bare id there -- so the payment method is retrieved from Stripe instead,
        and the mandate is activated whichever of the two arrives first.

        ``None`` when the intent recorded no payment method at all, which is what
        a payment that saved nothing looks like, and ``None`` when Stripe cannot
        be asked for the card.
        """
        intent = payment.raw or {}
        method = intent.get("payment_method")
        method_id = method.get("id") if isinstance(method, dict) else method
        if not method_id:
            return None
        charge = intent.get("latest_charge")
        details = charge.get("payment_method_details") if isinstance(charge, dict) else None
        card = details.get("card") if isinstance(details, dict) else None
        if not isinstance(card, dict):
            card = self.card_for_method(str(method_id))
        if card is None:
            return None
        customer = intent.get("customer")
        customer_id = customer.get("id") if isinstance(customer, dict) else customer
        return method_from_card(str(method_id), str(customer_id or ""), card, intent)

    def card_for_method(self, method_id: str) -> dict[str, Any] | None:
        """The ``card`` block of a saved payment method, asked of Stripe directly.

        ``None`` when the method is not a card and when Stripe cannot be reached,
        which is logged rather than raised: a mandate that cannot be activated now
        is left pending for the next attempt rather than failing the payment that
        was already taken.
        """
        try:
            retrieved = stripe_client().v1.payment_methods.retrieve(method_id)
        except (stripe.StripeError, ProviderNotConfiguredError) as exc:
            log.warning(
                "Stripe payment_methods.retrieve failed for %s: %s", method_id, type(exc).__name__
            )
            return None
        card = retrieved.to_dict().get("card")
        return card if isinstance(card, dict) else None


def pending_mandate(payment: Payment) -> RenewalMandate | None:
    """The Stripe mandate this payment would activate, or ``None``.

    Read at checkout, so an intent that is going to save a card is created with
    a customer and with ``setup_future_usage``.
    """
    # Inline: renewals reads this package, so a top-level import would close the
    # cycle between the two.
    from apps.payments.renewals.mandates import pending_mandate_for

    return pending_mandate_for(payment)
