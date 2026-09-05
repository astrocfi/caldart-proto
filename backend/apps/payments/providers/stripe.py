"""Stripe provider skeleton.

Filled in by ``feat/payments`` (PLAN §10): create a PaymentIntent with
``automatic_payment_methods`` and metadata ``{payment_id, user_id, plan}``,
verify amount and ``status == "succeeded"`` on confirm, and verify the
``Stripe-Signature`` header in ``handle_webhook``.
"""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse

from apps.payments.models import Payment
from apps.payments.providers.base import Provider, register


@register
class StripeProvider(Provider):
    slug = "stripe"

    def start(self, payment: Payment) -> dict:
        raise NotImplementedError("Stripe checkout is implemented by feat/payments")

    def confirm(self, payment: Payment, **kwargs) -> bool:
        raise NotImplementedError("Stripe confirmation is implemented by feat/payments")

    def handle_webhook(self, request: HttpRequest) -> HttpResponse:
        raise NotImplementedError("Stripe webhooks are implemented by feat/payments")
