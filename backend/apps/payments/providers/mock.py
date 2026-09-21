"""Mock payment provider used in development, tests and e2e runs."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed

from apps.payments.models import Payment, PaymentWallet
from apps.payments.providers.base import Provider, register
from apps.payments.services import mark_failed, mark_succeeded


class MockPaymentsDisabledError(RuntimeError):
    """Raised when the mock provider is used with ``PAYMENTS_MOCK_ENABLED`` off."""


@register
class MockProvider(Provider):
    """A provider that moves no money, for development, tests and e2e runs.

    Every entry point raises :class:`MockPaymentsDisabledError` unless
    ``PAYMENTS_MOCK_ENABLED`` is on, so a production deployment cannot use it to
    grant itself a membership.
    """

    slug = "mock"

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
        it has none, activates the term and returns ``True``; anything else marks it
        failed and returns ``False``.  Either way ``raw`` records the outcome and the
        amount.  Raises :class:`MockPaymentsDisabledError` when ``PAYMENTS_MOCK_ENABLED``
        is off.
        """
        self._check_enabled()
        raw = {"provider": "mock", "outcome": outcome, "amount_cents": payment.amount_cents}
        if outcome == "succeed":
            mark_succeeded(
                payment,
                wallet=PaymentWallet.MOCK,
                raw=raw,
                provider_ref=payment.provider_ref or f"mock_{payment.pk}",
            )
            return True
        mark_failed(payment, raw)
        return False

    def handle_webhook(self, request: HttpRequest) -> HttpResponse:
        """Accept and ignore: 204 for a ``POST``, 405 for any other method."""
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        return HttpResponse(status=204)
