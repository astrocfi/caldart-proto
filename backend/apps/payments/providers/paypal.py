"""PayPal provider skeleton.

Filled in by ``feat/payments`` (PLAN §10): Orders v2 REST called with
``httpx`` (no SDK).  ``start`` creates an ``intent=CAPTURE`` order,
``confirm`` captures it and treats ``COMPLETED`` as success.
"""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse

from apps.payments.models import Payment
from apps.payments.providers.base import Provider, register


@register
class PayPalProvider(Provider):
    slug = "paypal"

    def start(self, payment: Payment) -> dict:
        raise NotImplementedError("PayPal order creation is implemented by feat/payments")

    def confirm(self, payment: Payment, **kwargs) -> bool:
        raise NotImplementedError("PayPal capture is implemented by feat/payments")

    def handle_webhook(self, request: HttpRequest) -> HttpResponse:
        raise NotImplementedError("PayPal webhooks are implemented by feat/payments")
