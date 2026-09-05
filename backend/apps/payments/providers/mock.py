"""Mock payment provider used in development, tests and e2e runs."""

from __future__ import annotations

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed

from apps.payments.models import Payment, PaymentWallet
from apps.payments.providers.base import Provider, register
from apps.payments.services import mark_failed, mark_succeeded


class MockPaymentsDisabled(RuntimeError):
    """Raised when the mock provider is used with ``PAYMENTS_MOCK_ENABLED`` off."""


@register
class MockProvider(Provider):
    slug = "mock"

    def _check_enabled(self) -> None:
        if not settings.PAYMENTS_MOCK_ENABLED:
            raise MockPaymentsDisabled("The mock payment provider is disabled.")

    def start(self, payment: Payment) -> dict:
        self._check_enabled()
        return {}

    def confirm(self, payment: Payment, *, outcome: str = "succeed", **kwargs) -> bool:
        """``outcome`` is ``"succeed"`` or ``"fail"``."""
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
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        return HttpResponse(status=204)
