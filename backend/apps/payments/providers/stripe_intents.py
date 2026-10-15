"""Reading a Stripe PaymentIntent or charge, and finding the payment it is for.

The provider in :mod:`apps.payments.providers.stripe` converts every SDK object to a
plain dict at the boundary and reads it through these: the wallet and the fee, the
refunds a charge carries, the payment a webhook object names, the reason an
off-session intent did not succeed, and the intent to adopt when a renewal charge
is looked up again.
"""

from __future__ import annotations

import json
from typing import Any

from apps.payments.models import Payment, PaymentProvider, PaymentWallet, RenewalMandate
from apps.payments.providers.base import MandateMethod, ProviderFees, card_label

#: What a member is told when Stripe refuses an off-session charge without
#: giving a reason of its own.
DECLINED_MESSAGE = "Your card was declined."

#: Off-session intent statuses that mean Stripe has the charge and has not settled
#: it: the money may still arrive or be refused.
PENDING_STATUSES = frozenset({"processing"})


#: ``payment_method_details.card.wallet.type`` values mapped onto our choices.
WALLET_TYPES: dict[str, str] = {
    "apple_pay": PaymentWallet.APPLE_PAY,
    "google_pay": PaymentWallet.GOOGLE_PAY,
    "link": PaymentWallet.LINK,
}


def jsonable(value: dict[str, Any]) -> dict[str, Any]:
    """A plain, JSON-serializable dict for ``Payment.raw``.

    Stripe's own types are converted to dicts at the SDK boundary, so all this
    has left to do is drop anything JSON cannot carry, such as a date.  Such a
    value is replaced by its ``str()``.
    """
    converted: dict[str, Any] = json.loads(json.dumps(value, default=str))
    return converted


def succeeded_refunds(charge: dict[str, Any]) -> list[dict[str, Any]]:
    """Every refund in a charge's ``refunds.data`` that Stripe reports as succeeded.

    A charge with no refund list, or one whose refunds are all pending or failed,
    gives an empty list: only a succeeded refund has actually moved money.
    """
    data = (charge.get("refunds") or {}).get("data") or []
    return [entry for entry in data if entry.get("status") == "succeeded"]


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


def charge_customer(mandate: RenewalMandate, payment: Payment) -> str:
    """The Stripe customer an off-session charge for ``payment`` is made for.

    The one stamped on the payment when it was first sent, so a card changed since
    never moves the lookup to another customer; the mandate's own before then.
    """
    return payment.charge_customer_ref or mandate.customer_ref


def renewal_intent_to_adopt(intents: list[dict[str, Any]]) -> dict[str, Any]:
    """Of the intents made for one renewal payment, the one that says what happened.

    A succeeded intent is the charge, then a processing one is the charge still
    settling; otherwise the first, which Stripe lists newest first.
    """
    for status in ("succeeded", *PENDING_STATUSES):
        for intent in intents:
            if intent.get("status") == status:
                return intent
    return intents[0]


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
