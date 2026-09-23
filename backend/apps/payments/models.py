"""Payments.  All money is integer cents in USD."""

from __future__ import annotations

from typing import TypedDict

from django.conf import settings
from django.db import models

from apps.accounts.models import User
from caldart.models import TimestampedModel


class PaymentProvider(models.TextChoices):
    """The payment backends a checkout can be routed to."""

    STRIPE = "stripe", "Stripe"
    PAYPAL = "paypal", "PayPal"
    MOCK = "mock", "Mock"


class PaymentWallet(models.TextChoices):
    """How the money was presented, as far as the provider could tell us."""

    CARD = "card", "Card"
    APPLE_PAY = "apple_pay", "Apple Pay"
    GOOGLE_PAY = "google_pay", "Google Pay"
    LINK = "link", "Link"
    PAYPAL = "paypal", "PayPal"
    MOCK = "mock", "Mock"
    UNKNOWN = "unknown", "Unknown"


class PaymentStatus(models.TextChoices):
    """Where an attempt to pay got to.  Only ``SUCCEEDED`` buys a membership term."""

    PENDING = "pending", "Pending"
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed"
    REFUNDED = "refunded", "Refunded"


class ContributionTier(TypedDict):
    """One preset contribution button: the text on it and what it charges."""

    label: str
    cents: int


#: Contribution tiers offered at checkout, from no contribution up to Platinum.
#: A member who wants some other amount types it instead of picking a tier.
#: The largest contribution a checkout accepts, in cents: $99,999.00.  It is
#: inside every provider's per-charge ceiling, so an amount the form accepts is
#: an amount the provider will take; anything larger is a typo or an attack.
MAX_CONTRIBUTION_CENTS = 9_999_900

CONTRIBUTION_TIERS: tuple[ContributionTier, ...] = (
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
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payments",
        help_text="Protected: a payment is a financial record and outlives the account.",
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
        """The provider's display name, the dollar total and the status."""
        return f"{self.get_provider_display()} ${self.amount_cents / 100:,.2f} ({self.status})"

    @property
    def is_succeeded(self) -> bool:
        """Whether the money arrived.  A pending or failed attempt is ``False``."""
        return self.status == PaymentStatus.SUCCEEDED

    @property
    def description(self) -> str:
        """What was bought, for a provider's own record of the charge.

        Names the plan, the contribution, or both joined by ``+``.  A payment that
        buys no plan and carries no contribution reads as ``Contribution``.
        """
        parts = []
        if self.plan is not None:
            parts.append(self.plan.name)
        if self.contribution_cents:
            parts.append(f"contribution ${self.contribution_cents / 100:,.2f}")
        return " + ".join(parts) or "Contribution"


def payment_deletion_refusal(user: User) -> str | None:
    """The reason ``user`` cannot be deleted, or ``None`` when nothing stops it.

    ``Payment.user`` is ``PROTECT``, so an account with any payment -- pending and
    failed rows included -- cannot be deleted.  The sentence names the account, the
    number of payment records that must be kept, and deactivation as the alternative.
    Every surface that deletes an account shows this same sentence.
    """
    count = user.payments.count()
    if count == 0:
        return None
    plural = "" if count == 1 else "s"
    return (
        f"{user.display_name} has {count} payment record{plural}, which must be kept. "
        "Deactivate the account instead."
    )
