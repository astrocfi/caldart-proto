"""Payments.  All money is integer cents in USD."""

from __future__ import annotations

from django.conf import settings
from django.db import models

from apps.members.models import TimestampedModel


class PaymentProvider(models.TextChoices):
    STRIPE = "stripe", "Stripe"
    PAYPAL = "paypal", "PayPal"
    MOCK = "mock", "Mock"


class PaymentWallet(models.TextChoices):
    CARD = "card", "Card"
    APPLE_PAY = "apple_pay", "Apple Pay"
    GOOGLE_PAY = "google_pay", "Google Pay"
    LINK = "link", "Link"
    PAYPAL = "paypal", "PayPal"
    MOCK = "mock", "Mock"
    UNKNOWN = "unknown", "Unknown"


class PaymentStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed"
    REFUNDED = "refunded", "Refunded"


#: Contribution tiers offered at checkout.  ``None`` means "other".
CONTRIBUTION_TIERS: tuple[dict, ...] = (
    {"label": "No contribution", "cents": 0},
    {"label": "Participating", "cents": 2_000},
    {"label": "Bronze", "cents": 10_000},
    {"label": "Silver", "cents": 30_000},
    {"label": "Gold", "cents": 100_000},
    {"label": "Diamond", "cents": 300_000},
    {"label": "Platinum", "cents": 1_000_000},
)


class Payment(TimestampedModel):
    """One attempt to pay for a membership term and/or make a contribution."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="payments"
    )
    plan = models.ForeignKey(
        "members.MembershipPlan",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="payments",
        help_text="Null for a pure donation.",
    )
    amount_cents = models.PositiveIntegerField(help_text="Total charged.")
    plan_amount_cents = models.PositiveIntegerField(default=0)
    contribution_cents = models.PositiveIntegerField(default=0)
    currency = models.CharField(max_length=3, default="usd")
    provider = models.CharField(max_length=12, choices=PaymentProvider.choices)
    wallet = models.CharField(
        max_length=16, choices=PaymentWallet.choices, default=PaymentWallet.UNKNOWN
    )
    provider_ref = models.CharField(
        max_length=128, blank=True, help_text="PaymentIntent id / PayPal order id."
    )
    status = models.CharField(
        max_length=12, choices=PaymentStatus.choices, default=PaymentStatus.PENDING
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    raw = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_ref"],
                condition=~models.Q(provider_ref=""),
                name="payments_provider_ref_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "-created_at"], name="payments_user_created_idx"),
            models.Index(fields=["status", "-completed_at"], name="payments_status_idx"),
            models.Index(fields=["provider", "status"], name="payments_provider_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.get_provider_display()} ${self.amount_cents / 100:,.2f} ({self.status})"

    @property
    def amount_dollars(self) -> float:
        return self.amount_cents / 100

    @property
    def is_succeeded(self) -> bool:
        return self.status == PaymentStatus.SUCCEEDED

    @property
    def description(self) -> str:
        parts = []
        if self.plan_id:
            parts.append(self.plan.name)
        if self.contribution_cents:
            parts.append(f"contribution ${self.contribution_cents / 100:,.2f}")
        return " + ".join(parts) or "Contribution"
