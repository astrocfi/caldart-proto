"""Payments.  All money is integer cents in USD."""

from __future__ import annotations

from datetime import date
from typing import TypedDict

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.accounts.models import User
from caldart.models import TimestampedModel


class PaymentProvider(models.TextChoices):
    """The payment backends a checkout can be routed to."""

    STRIPE = "stripe", "Stripe"
    PAYPAL = "paypal", "PayPal"
    MOCK = "mock", "Mock"
    MANUAL = "manual", "Recorded by hand"


class MandateProvider(models.TextChoices):
    """The payment backends that can hold a standing renewal authority.

    These are the members of ``PaymentProvider`` that can charge again off-session.
    ``manual`` is absent deliberately: a check or a cash payment cannot be taken a
    second time without the member, so a mandate naming it would be an authority
    nobody could ever act on.
    """

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
    CHECK = "check", "Check"
    CASH = "cash", "Cash"
    BANK_TRANSFER = "bank_transfer", "Bank transfer"
    OTHER = "other", "Other"
    UNKNOWN = "unknown", "Unknown"


class PaymentStatus(models.TextChoices):
    """Where an attempt to pay got to.  Only ``SUCCEEDED`` buys a membership term."""

    PENDING = "pending", "Pending"
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed"
    PARTIALLY_REFUNDED = "partially_refunded", "Partially refunded"
    REFUNDED = "refunded", "Refunded"


class PaymentKind(models.TextChoices):
    """What a payment bought, read from its plan and its contribution."""

    MEMBERSHIP = "membership", "Membership"
    CONTRIBUTION = "contribution", "Contribution"
    BOTH = "both", "Membership and contribution"


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
        max_length=20, choices=PaymentStatus.choices, default=PaymentStatus.PENDING
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    fee_cents = models.PositiveIntegerField(
        default=0, help_text="The provider's fee, as the provider reported it."
    )
    net_cents = models.PositiveIntegerField(
        default=0, help_text="What reached CalDART's balance, as the provider reported it."
    )
    receipt_sent_at = models.DateTimeField(
        null=True, blank=True, help_text="When CalDART's own receipt was last emailed."
    )
    received_on = models.DateField(
        null=True,
        blank=True,
        help_text="For a payment recorded by hand, the day the money was received.",
    )
    reconciled_on = models.DateField(
        null=True, blank=True, help_text="The day a treasurer matched this to a statement."
    )
    reconciled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments_reconciled",
    )
    note = models.CharField(
        max_length=255,
        blank=True,
        help_text="A treasurer's note: the check number, the reason for a manual entry.",
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments_recorded",
        help_text="The administrator who recorded a payment taken by hand.",
    )
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
    def refunded_cents(self) -> int:
        """What has been given back, in cents: the sum of the succeeded refunds.

        A pending or failed refund counts for nothing, and a payment with no refunds
        at all reports ``0``.
        """
        return sum(
            refund.amount_cents
            for refund in self.refunds.all()
            if refund.status == RefundStatus.SUCCEEDED
        )

    @property
    def kind(self) -> str:
        """What this payment bought, as a :class:`PaymentKind` value.

        ``membership`` when it names a plan and carries no contribution,
        ``contribution`` when it names no plan, and ``both`` when it does both.
        """
        if self.plan is None:
            return PaymentKind.CONTRIBUTION
        if self.contribution_cents > 0:
            return PaymentKind.BOTH
        return PaymentKind.MEMBERSHIP

    @property
    def paid_on(self) -> date | None:
        """The ledger date: the day the money counts as received.

        For a payment recorded by hand that is ``received_on``, the day the check or
        the cash arrived.  For every other provider it is the local date of
        ``completed_at``, and ``None`` while the payment has not completed.
        """
        if self.provider == PaymentProvider.MANUAL:
            return self.received_on
        if self.completed_at is None:
            return None
        return timezone.localdate(self.completed_at)

    @property
    def receipt_number(self) -> str:
        """The number on CalDART's receipt: ``CALDART-`` and the id to six digits."""
        return f"CALDART-{self.pk:06d}"

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


class RefundReason(models.TextChoices):
    """Why money was given back.  The treasurer picks one when issuing a refund."""

    REQUESTED_BY_MEMBER = "requested_by_member", "Requested by the member"
    DUPLICATE = "duplicate", "Duplicate payment"
    ERROR = "error", "Charged in error"
    FRAUDULENT = "fraudulent", "Fraudulent"
    OTHER = "other", "Other"


class RefundStatus(models.TextChoices):
    """Where an attempt to give money back got to.  Only ``SUCCEEDED`` counts."""

    PENDING = "pending", "Pending"
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed"


class Refund(TimestampedModel):
    """Money given back against one payment, in whole or in part.

    A refund is a record in its own right: it carries its own amount, the reason
    the treasurer chose, an optional note, and the provider's reference for the
    refund once the provider has taken it.  ``requested_by`` is the administrator
    who issued it, and is null for a refund somebody made in the provider's own
    dashboard, which arrives here by webhook.

    The rule that a payment's succeeded refunds never exceed its ``amount_cents``
    is kept by the refund service, not by the database.
    """

    payment = models.ForeignKey(
        Payment,
        on_delete=models.PROTECT,
        related_name="refunds",
        help_text=(
            "Protected: a refund is a financial record, and the payment it "
            "reverses cannot be deleted out from under it."
        ),
    )
    amount_cents = models.PositiveIntegerField(help_text="What was given back.")
    reason = models.CharField(max_length=24, choices=RefundReason.choices)
    note = models.CharField(max_length=255, blank=True)
    status = models.CharField(
        max_length=12, choices=RefundStatus.choices, default=RefundStatus.PENDING
    )
    provider_ref = models.CharField(
        max_length=128,
        blank=True,
        help_text="The Stripe or PayPal refund id; blank for a manual or mock refund.",
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="refunds_requested",
        help_text="Null when the refund was issued in the provider's own dashboard.",
    )
    refunded_at = models.DateTimeField(null=True, blank=True)
    raw = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["payment", "-created_at"], name="payments_refund_pay_idx"),
            models.Index(fields=["status", "-refunded_at"], name="payments_refund_status_idx"),
        ]

    def __str__(self) -> str:
        """The dollar amount and the status, as ``Refund $25.00 (succeeded)``."""
        return f"Refund ${self.amount_cents / 100:,.2f} ({self.status})"


class MandateStatus(models.TextChoices):
    """Where a member's standing authority to be charged each year got to."""

    PENDING = "pending", "Pending"
    ACTIVE = "active", "Active"
    PAUSED = "paused", "Paused"
    CANCELED = "canceled", "Canceled"


class RenewalMandate(TimestampedModel):
    """One member's standing authority for CalDART to renew their membership.

    A mandate holds the saved payment method, the plan and contribution it renews,
    and how the member sees the method described.  It is created ``pending`` at a
    checkout that asked for automatic renewal and becomes ``active`` when that
    payment succeeds; three failed charges in a row pause it, and the member or an
    administrator can cancel it at any time.

    ``plan`` is the plan that renews, and it always has a duration: a lifetime
    plan never renews.  ``plan`` is null instead for a member who already holds a
    lifetime term: their membership needs no renewing, so the mandate is a
    standing authority for the contribution alone, charged once a year.  The
    provider is always one that can charge off-session -- ``stripe``, ``paypal``
    or ``mock``, never ``manual``.

    ``next_charge_on`` is the day the member chose to be charged on, which
    defaults to the day their membership runs out.  Every mandate carries one, and
    a successful charge rolls it forward a year.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="renewal_mandate",
    )
    plan = models.ForeignKey(
        "members.MembershipPlan",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="renewal_mandates",
        help_text="Null when the member is a life member and only the contribution renews.",
    )
    contribution_cents = models.PositiveIntegerField(
        default=0, help_text="Renewed alongside the dues."
    )
    next_charge_on = models.DateField(
        help_text="The day the member chose to be charged; rolled forward after each charge.",
    )
    provider = models.CharField(max_length=12, choices=MandateProvider.choices)
    customer_ref = models.CharField(
        max_length=128, blank=True, help_text="Stripe customer id / PayPal payer id."
    )
    method_ref = models.CharField(
        max_length=128, help_text="Stripe payment method id / PayPal vault id."
    )
    method_brand = models.CharField(max_length=32, blank=True)
    method_last4 = models.CharField(max_length=4, blank=True)
    method_exp_month = models.PositiveSmallIntegerField(null=True, blank=True)
    method_exp_year = models.PositiveSmallIntegerField(null=True, blank=True)
    method_label = models.CharField(
        max_length=128,
        help_text='What the member sees: "Visa ending 4242, expires 03/2028".',
    )
    status = models.CharField(
        max_length=12, choices=MandateStatus.choices, default=MandateStatus.PENDING
    )
    failure_count = models.PositiveSmallIntegerField(
        default=0, help_text="Consecutive failed charges; reset on success."
    )
    canceled_at = models.DateTimeField(null=True, blank=True)
    canceled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="renewal_mandates_canceled",
        help_text="The member themselves, or the administrator who turned it off.",
    )
    last_charged_at = models.DateTimeField(null=True, blank=True)
    raw = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["status", "-created_at"], name="payments_mandate_status_idx"),
        ]

    def __str__(self) -> str:
        """The member, the method label and the status, separated by middle dots."""
        return f"{self.user} \u00b7 {self.method_label} ({self.status})"


class RenewalOutcome(models.TextChoices):
    """Where one scheduled renewal charge got to."""

    SCHEDULED = "scheduled", "Scheduled"
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed"
    SKIPPED = "skipped", "Skipped"


class RenewalAttempt(TimestampedModel):
    """One scheduled charge against a mandate, and every email keyed on it.

    An attempt is created when the scanner notices that a term is running out.  It
    carries the day the charge is due, the membership whose expiry it renews, the
    payment it created once it ran, and the provider's decline reason when it
    failed.  The three timestamps say which emails have gone out, so a scan that
    runs twice in one day sends nothing twice.  ``retry_of`` chains a retry back to
    the attempt that failed.
    """

    mandate = models.ForeignKey(RenewalMandate, on_delete=models.CASCADE, related_name="attempts")
    membership = models.ForeignKey(
        "members.Membership",
        on_delete=models.CASCADE,
        related_name="renewal_attempts",
        help_text="The term whose expiry this charge renews.",
    )
    scheduled_on = models.DateField(help_text="The day the charge is due.")
    retry_of = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="retries",
        help_text="The attempt this one retries.",
    )
    outcome = models.CharField(
        max_length=12, choices=RenewalOutcome.choices, default=RenewalOutcome.SCHEDULED
    )
    payment = models.ForeignKey(
        Payment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="renewal_attempts",
    )
    error = models.CharField(
        max_length=255, blank=True, help_text="The provider's decline reason, for the member."
    )
    noticed_at = models.DateTimeField(
        null=True, blank=True, help_text="When the advance-warning email went out."
    )
    attempted_at = models.DateTimeField(null=True, blank=True)
    result_emailed_at = models.DateTimeField(
        null=True, blank=True, help_text="When the charged or failed email went out."
    )

    class Meta:
        ordering = ["-scheduled_on", "-id"]
        indexes = [
            models.Index(fields=["mandate", "-scheduled_on"], name="payments_attempt_man_idx"),
            models.Index(fields=["outcome", "scheduled_on"], name="payments_attempt_out_idx"),
        ]

    def __str__(self) -> str:
        """The member, the scheduled day and the outcome, separated by middle dots."""
        return f"{self.mandate.user} \u00b7 {self.scheduled_on.isoformat()} ({self.outcome})"


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
