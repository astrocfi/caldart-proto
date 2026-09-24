"""Mock payment provider used in development, tests, and e2e runs."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed

from apps.payments.models import Payment, PaymentWallet, Refund
from apps.payments.providers.base import Provider, ProviderFees, ProviderRefund, register
from apps.payments.services import mark_failed, mark_succeeded

#: The mock provider charges a Stripe-shaped fee -- 2.9% of the amount plus 30
#: cents -- so seeded and test data carry figures that look like the real thing
#: rather than a suspiciously round zero.  The rate is kept as a fraction in
#: whole numbers so the fee is integer arithmetic from end to end.
FEE_NUMERATOR = 29
FEE_DENOMINATOR = 1_000
FEE_FIXED_CENTS = 30


def fee_cents(amount_cents: int) -> int:
    """The mock provider's fee on ``amount_cents``: 2.9% plus 30 cents.

    The percentage is rounded half up to the cent, as a card processor rounds
    it, so $45.00 costs 161 cents rather than 160.  A payment of nothing costs
    nothing: the fixed part is only charged where there is money to charge it on.
    """
    if amount_cents == 0:
        return 0
    percentage = (amount_cents * FEE_NUMERATOR + FEE_DENOMINATOR // 2) // FEE_DENOMINATOR
    return percentage + FEE_FIXED_CENTS


def fees_for(payment: Payment) -> ProviderFees:
    """What the mock provider kept out of ``payment`` and what it paid across."""
    fee = fee_cents(payment.amount_cents)
    return ProviderFees(fee_cents=fee, net_cents=payment.amount_cents - fee)


class MockPaymentsDisabledError(RuntimeError):
    """Raised when the mock provider is used with ``PAYMENTS_MOCK_ENABLED`` off."""


@register
class MockProvider(Provider):
    """A provider that moves no money, for development, tests, and e2e runs.

    Every entry point raises :class:`MockPaymentsDisabledError` unless
    ``PAYMENTS_MOCK_ENABLED`` is on, so a production deployment cannot use it to
    grant itself a membership.
    """

    slug = "mock"

    @classmethod
    def is_configured(cls) -> bool:
        """Whether ``PAYMENTS_MOCK_ENABLED`` is on.  The provider needs no keys."""
        return bool(settings.PAYMENTS_MOCK_ENABLED)

    def _check_enabled(self) -> None:
        if not settings.PAYMENTS_MOCK_ENABLED:
            raise MockPaymentsDisabledError("The mock payment provider is disabled.")

    def start(self, payment: Payment) -> dict[str, Any]:
        """Nothing for the browser to do, so an empty dict.

        Raises :class:`MockPaymentsDisabledError` when ``PAYMENTS_MOCK_ENABLED`` is off.
        """
        self._check_enabled()
        return {}

    def confirm(self, payment: Payment, *, outcome: str = "succeed", **kwargs: Any) -> bool:
        """Complete the payment the way ``outcome`` asks.

        ``outcome`` is ``"succeed"`` or ``"fail"``.  Succeeding marks the payment
        succeeded with the ``mock`` wallet, gives it the reference ``mock_<id>`` if
        it has none, records the fee :func:`fee_cents` works out, activates the term
        and returns ``True``; anything else marks it failed and returns ``False``.
        Either way ``raw`` records the outcome and the amount.  Raises
        :class:`MockPaymentsDisabledError` when ``PAYMENTS_MOCK_ENABLED`` is off.
        """
        self._check_enabled()
        raw = {"provider": "mock", "outcome": outcome, "amount_cents": payment.amount_cents}
        if outcome == "succeed":
            fees = fees_for(payment)
            mark_succeeded(
                payment,
                wallet=PaymentWallet.MOCK,
                raw=raw,
                provider_ref=payment.provider_ref or f"mock_{payment.pk}",
                fee_cents=fees.fee_cents,
                net_cents=fees.net_cents,
            )
            return True
        mark_failed(payment, raw)
        return False

    def refund(self, payment: Payment, refund: Refund) -> ProviderRefund:
        """Give the money back instantly, with no provider reference.

        Nothing moves, so nothing can fail: the answer records the amount and the
        payment it came off.  There is no provider holding a refund id, so the
        reference is blank, as it is for a refund written by hand.  Raises
        :class:`MockPaymentsDisabledError` when ``PAYMENTS_MOCK_ENABLED`` is off.
        """
        self._check_enabled()
        return ProviderRefund(
            provider_ref="",
            raw={
                "provider": "mock",
                "amount_cents": refund.amount_cents,
                "payment_ref": payment.provider_ref,
            },
        )

    def handle_webhook(self, request: HttpRequest) -> HttpResponse:
        """Accept and ignore: 204 for a ``POST``, 405 for any other method."""
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        return HttpResponse(status=204)

    def fetch_fees(self, payment: Payment) -> ProviderFees:
        """The fee the mock provider would have charged, worked out afresh.

        It needs nothing from outside, so it always answers, whatever state the
        payment is in.
        """
        return fees_for(payment)
