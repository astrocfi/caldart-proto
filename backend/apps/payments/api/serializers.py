"""Serializers for the payments API."""

from __future__ import annotations

import datetime as dt
from typing import Any

from django.utils import timezone
from drf_spectacular.utils import PolymorphicProxySerializer, extend_schema_field
from rest_framework import serializers

from apps.members.api.serializers import MembershipStatusSerializer, PlanSerializer
from apps.members.models import Membership
from apps.payments.dates import is_in_the_future
from apps.payments.manual import MANUAL_METHOD_CHOICES
from apps.payments.models import (
    MAX_CONTRIBUTION_CENTS,
    MandateCadence,
    MandateProvider,
    MandateStatus,
    Payment,
    PaymentKind,
    PaymentProvider,
    PaymentStatus,
    Refund,
    RefundReason,
    RenewalAttempt,
    RenewalMandate,
    RenewalOutcome,
)
from apps.payments.reconciliation import ReconciliationRow
from apps.payments.renewals import (
    PAST_CHARGE_DATE_MESSAGE,
    RENEWAL_PLAN_MESSAGE,
    YEARLY_ONLY_MESSAGE,
    MandateKind,
    charge_date,
    mandate_kind,
    renewal_amount_cents,
)
from apps.payments.reports import ContributionRow, PeriodSummary
from caldart.runs import RunActionSerializer


class ContributionTierSerializer(serializers.Serializer[dict[str, Any]]):
    """One preset contribution button of ``GET /payments/config``."""

    # DRF's Field.label is a different thing from this serializer's own `label`
    # field, so the stubs see the declaration as a narrowing of the attribute.
    label = serializers.CharField()  # type: ignore[assignment]
    cents = serializers.IntegerField()


class PaymentsConfigSerializer(serializers.Serializer[dict[str, Any]]):
    """``GET /payments/config``."""

    providers = serializers.ListField(
        child=serializers.ChoiceField(choices=PaymentProvider.choices)
    )
    stripe_publishable_key = serializers.CharField(allow_blank=True)
    paypal_client_id = serializers.CharField(allow_blank=True)
    plans = PlanSerializer(many=True)
    contribution_tiers = ContributionTierSerializer(many=True)
    max_contribution_cents = serializers.IntegerField()


def no_past_charge_date(value: dt.date) -> None:
    """Refuse a charge date that has already gone by, with a message for the member.

    Raises DRF's ``ValidationError`` carrying ``PAST_CHARGE_DATE_MESSAGE``, which the
    endpoint answers keyed by ``next_charge_on``.  Today itself is allowed, and so is
    any day after it.
    """
    if value < timezone.localdate():
        raise serializers.ValidationError(PAST_CHARGE_DATE_MESSAGE)


def next_charge_on_field() -> serializers.DateField:
    """The optional day a member asks to be charged on, shared by the three endpoints.

    Absent or null means "leave it to the server": a new renewal takes the day the
    membership runs out, a new recurring donation takes today, and a change leaves
    the stored day alone.
    """
    return serializers.DateField(
        required=False, allow_null=True, default=None, validators=[no_past_charge_date]
    )


def cadence_field(*, default: str | None) -> serializers.ChoiceField:
    """How often a standing authority charges, shared by every endpoint that sets one.

    ``default`` is what an absent field reads as: ``yearly`` where an authority is
    being made, and ``None`` -- leave it alone -- where one is being changed.
    """
    return serializers.ChoiceField(
        choices=MandateCadence.choices, required=False, allow_null=default is None, default=default
    )


def remove_renewal_contribution_field() -> serializers.BooleanField:
    """The member's agreement to move their renewal's contribution to a donation.

    Only a recurring donation reads it.  Without it, a donation asked for by a member
    whose renewal takes a contribution is refused with the code
    ``renewal_contribution``; with it, the renewal's contribution becomes nothing
    first.
    """
    return serializers.BooleanField(required=False, default=False)


def refuse_non_yearly_renewal(cadence: str | None) -> None:
    """Refuse a renewal on any cadence but yearly, keyed by ``cadence``.

    Dues are charged once a year, so ``monthly`` and ``quarterly`` are a 400 carrying
    ``Automatic renewal is charged once a year.``; an absent cadence passes.
    """
    if cadence is not None and cadence != MandateCadence.YEARLY:
        raise serializers.ValidationError({"cadence": [YEARLY_ONLY_MESSAGE]})


class MandateScopedSerializer(serializers.Serializer[dict[str, Any]]):
    """A request body read differently for an automatic renewal and a recurring donation.

    The views behind ``/me/renewal*`` and ``/me/donation*`` are one set, told which
    kind they serve; they hand the same flag to their serializer as the ``donation``
    context key, which is ``False`` when absent.
    """

    @property
    def is_donation(self) -> bool:
        """Whether this body is for the recurring donation rather than the renewal."""
        return bool(self.context.get("donation", False))


class CheckoutSerializer(serializers.Serializer[dict[str, Any]]):
    """``POST /payments/checkout``.

    There is deliberately no amount field: the server recomputes the total from
    the plan price plus the contribution.  A contribution outside
    ``0..MAX_CONTRIBUTION_CENTS`` is a 400 naming ``contribution_cents``.

    ``auto_renew`` asks for the payment method to be saved and charged again on a
    schedule.  With a plan, that is an automatic renewal, which is always yearly:
    any other ``cadence`` is a 400 naming ``cadence``, and a plan that never expires
    or a provider that cannot charge a saved method is a 400 naming ``auto_renew``.
    With no plan, it is a recurring donation of ``contribution_cents`` on
    ``cadence`` (``monthly``, ``quarterly`` or ``yearly``, which is the default).
    ``remove_renewal_contribution`` agrees to move the renewal's contribution off it
    to make room for the donation.  ``next_charge_on`` is the day that authority
    first charges on; leaving it out takes the day the term this payment buys runs
    out for a renewal, and one cadence after today for a donation.  A day before
    today is a 400 naming ``next_charge_on``.
    """

    plan = serializers.CharField(required=False, allow_null=True, allow_blank=True, default="")
    contribution_cents = serializers.IntegerField(
        required=False, min_value=0, max_value=MAX_CONTRIBUTION_CENTS, default=0
    )
    provider = serializers.ChoiceField(choices=PaymentProvider.choices)
    auto_renew = serializers.BooleanField(required=False, default=False)
    next_charge_on = next_charge_on_field()
    cadence = cadence_field(default=MandateCadence.YEARLY)
    remove_renewal_contribution = remove_renewal_contribution_field()

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Refuse an automatic renewal on any cadence but yearly, keyed by ``cadence``."""
        if attrs["auto_renew"] and attrs["plan"]:
            refuse_non_yearly_renewal(attrs["cadence"])
        return attrs


class StripeCheckoutClientSerializer(serializers.Serializer[dict[str, str]]):
    """What the Stripe Payment Element needs: the PaymentIntent's client secret."""

    client_secret = serializers.CharField()


class PayPalCheckoutClientSerializer(serializers.Serializer[dict[str, str]]):
    """What the PayPal Buttons need: the id of the order just created."""

    order_id = serializers.CharField()


# A serializer with no fields renders as nothing at all, which would drop `client`
# from the mock response the view does send.  The explicit schema keeps the empty
# object in the document.
@extend_schema_field({"type": "object"})
class MockCheckoutClientSerializer(serializers.Serializer[dict[str, Any]]):
    """The mock provider needs nothing from the browser to proceed."""


class StripeCheckoutResponseSerializer(serializers.Serializer[dict[str, Any]]):
    """The 201 body of ``POST /payments/checkout`` when ``provider`` is Stripe."""

    payment_id = serializers.IntegerField()
    provider = serializers.ChoiceField(choices=[PaymentProvider.STRIPE])
    client = StripeCheckoutClientSerializer()


class PayPalCheckoutResponseSerializer(serializers.Serializer[dict[str, Any]]):
    """The 201 body of ``POST /payments/checkout`` when ``provider`` is PayPal."""

    payment_id = serializers.IntegerField()
    provider = serializers.ChoiceField(choices=[PaymentProvider.PAYPAL])
    client = PayPalCheckoutClientSerializer()


class MockCheckoutResponseSerializer(serializers.Serializer[dict[str, Any]]):
    """The 201 body of ``POST /payments/checkout`` when ``provider`` is ``mock``."""

    payment_id = serializers.IntegerField()
    provider = serializers.ChoiceField(choices=[PaymentProvider.MOCK])
    client = MockCheckoutClientSerializer()


#: The 201 body of ``POST /payments/checkout``, schema-only: the view never calls this
#: serializer, it only documents the shape ``get_provider(...).start()`` already produces.
#: ``client`` carries what the chosen provider's browser SDK needs, discriminated by
#: ``provider`` -- ``client_secret`` for Stripe, ``order_id`` for PayPal, nothing for the
#: mock provider.  The keys are the plain ``str`` values, not the ``TextChoices``
#: members: they become mapping keys in the document, and the YAML renderer
#: ``manage.py spectacular`` defaults to refuses a ``str`` subclass.
CheckoutResponseSerializer = PolymorphicProxySerializer(
    component_name="CheckoutResponse",
    serializers={
        PaymentProvider.STRIPE.value: StripeCheckoutResponseSerializer,
        PaymentProvider.PAYPAL.value: PayPalCheckoutResponseSerializer,
        PaymentProvider.MOCK.value: MockCheckoutResponseSerializer,
    },
    resource_type_field_name="provider",
)


class StripeConfirmSerializer(serializers.Serializer[dict[str, Any]]):
    """``POST /payments/stripe/confirm``.

    ``payment_intent_id`` may be left out: the payment's own reference is used.
    """

    payment_id = serializers.IntegerField()
    payment_intent_id = serializers.CharField(required=False, allow_blank=True, default="")


class PayPalCaptureSerializer(serializers.Serializer[dict[str, Any]]):
    """``POST /payments/paypal/capture``.

    ``order_id`` may be left out: the payment's own reference is used.
    """

    payment_id = serializers.IntegerField()
    order_id = serializers.CharField(required=False, allow_blank=True, default="")


#: What a mock payment can be told to do.
MOCK_OUTCOMES: tuple[str, ...] = ("succeed", "fail")


class MockCompleteSerializer(serializers.Serializer[dict[str, Any]]):
    """``POST /payments/mock/complete``, whose ``outcome`` is ``succeed`` or ``fail``."""

    payment_id = serializers.IntegerField()
    outcome = serializers.ChoiceField(choices=MOCK_OUTCOMES, default="succeed")


class PaymentResultSerializer(serializers.Serializer[dict[str, Any]]):
    """``GET /payments/{id}`` and the response to every confirm endpoint."""

    status = serializers.ChoiceField(choices=PaymentStatus.choices)
    membership = MembershipStatusSerializer()


class ProviderTotalsSerializer(serializers.Serializer[dict[str, int]]):
    """One period's money split by payment provider, in cents.

    A provider that took no money in the period is left out rather than sent as
    zero, so every key is optional.  The keys are exactly the payment providers,
    whichever ones are configured.
    """

    def get_fields(self) -> dict[str, serializers.Field[Any, Any, Any, Any]]:
        """One optional integer field per payment provider, in declared order."""
        return {
            provider: serializers.IntegerField(required=False)
            for provider in PaymentProvider.values
        }


class PaymentPeriodSummarySerializer(serializers.Serializer[PeriodSummary]):
    """One row of ``GET /admin/payments/summary``."""

    period = serializers.CharField()
    count = serializers.IntegerField()
    total_cents = serializers.IntegerField()
    plan_cents = serializers.IntegerField()
    contribution_cents = serializers.IntegerField()
    fee_cents = serializers.IntegerField()
    net_cents = serializers.IntegerField()
    refunded_cents = serializers.IntegerField()
    by_provider = ProviderTotalsSerializer()


class StatementYearsSerializer(serializers.Serializer[dict[str, Any]]):
    """``GET /me/payments/statements`` -- the years a statement can be had for.

    Newest first, and a year appears only when the member made at least one
    contribution in it that settled.  An empty list means there is nothing to
    download.
    """

    years = serializers.ListField(child=serializers.IntegerField())


class ReceiptSendSerializer(serializers.Serializer[dict[str, Any]]):
    """``POST /admin/payments/{id}/receipt`` -- what came of sending it again.

    ``sent`` says whether the mail server took the message, and
    ``receipt_sent_at`` is the stamp on the payment afterwards: the moment it
    went, or null when it did not and the send is still owed.
    """

    sent = serializers.BooleanField()
    receipt_sent_at = serializers.DateTimeField(allow_null=True)


class RefundSerializer(serializers.ModelSerializer[Refund]):
    """One refund row against a payment."""

    payment_id = serializers.IntegerField(read_only=True)
    requested_by_id = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = Refund
        fields = [
            "id",
            "payment_id",
            "amount_cents",
            "reason",
            "note",
            "status",
            "provider_ref",
            "requested_by_id",
            "refunded_at",
            "created_at",
        ]
        read_only_fields = fields


class RefundCreateSerializer(serializers.Serializer[dict[str, Any]]):
    """``POST /admin/payments/{id}/refunds``.

    There is no payment field: the payment is the one in the path.  ``amount_cents``
    is what to give back, at most what the payment has left unrefunded, and
    ``cancel_term`` ends the membership term the payment bought.
    """

    amount_cents = serializers.IntegerField(min_value=1)
    reason = serializers.ChoiceField(choices=RefundReason.choices)
    note = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")
    cancel_term = serializers.BooleanField(required=False, default=False)


class RefundedPaymentSerializer(serializers.ModelSerializer[Payment]):
    """A payment as it stands after a refund: enough to redraw the row it came from."""

    refunded_cents = serializers.IntegerField(read_only=True)

    class Meta:
        model = Payment
        fields = ["id", "amount_cents", "refunded_cents", "status"]
        read_only_fields = fields


class RefundIssuedSerializer(serializers.Serializer[dict[str, Any]]):
    """The 201 body of ``POST /admin/payments/{id}/refunds``."""

    refund = RefundSerializer()
    payment = RefundedPaymentSerializer()


# --------------------------------------------------------------------------
# Automatic renewal
# --------------------------------------------------------------------------
class RenewalMandateSerializer(serializers.ModelSerializer[RenewalMandate]):
    """One member's standing authority, as the member and finance screens read it."""

    user_id = serializers.IntegerField(read_only=True)
    user_name = serializers.SerializerMethodField()
    user_email = serializers.SerializerMethodField()
    plan = serializers.SerializerMethodField()
    plan_name = serializers.SerializerMethodField()
    kind = serializers.SerializerMethodField()
    amount_cents = serializers.SerializerMethodField()
    next_charge_on = serializers.SerializerMethodField()
    last_error = serializers.SerializerMethodField()

    class Meta:
        model = RenewalMandate
        fields = [
            "id",
            "user_id",
            "user_name",
            "user_email",
            "plan",
            "plan_name",
            "kind",
            "cadence",
            "contribution_cents",
            "amount_cents",
            "provider",
            "method_label",
            "method_brand",
            "method_last4",
            "method_exp_month",
            "method_exp_year",
            "status",
            "failure_count",
            "next_charge_on",
            "last_error",
            "last_charged_at",
            "canceled_at",
            "created_at",
        ]
        read_only_fields = fields

    def get_user_name(self, obj: RenewalMandate) -> str:
        """The member's display name."""
        return obj.user.display_name

    def get_user_email(self, obj: RenewalMandate) -> str:
        """The member's email address."""
        return obj.user.email

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_plan(self, obj: RenewalMandate) -> str | None:
        """The slug of the plan that renews, or ``None`` for a recurring donation."""
        return obj.plan.slug if obj.plan is not None else None

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_plan_name(self, obj: RenewalMandate) -> str | None:
        """The name of the plan that renews, or ``None`` for a recurring donation."""
        return obj.plan.name if obj.plan is not None else None

    @extend_schema_field(serializers.ChoiceField(choices=MandateKind.choices))
    def get_kind(self, obj: RenewalMandate) -> str:
        """What this authority charges for: a renewal, a donation, or both at once."""
        return mandate_kind(obj)

    def get_amount_cents(self, obj: RenewalMandate) -> int:
        """What the next charge comes to: the plan's price plus the contribution."""
        return renewal_amount_cents(obj)

    def get_next_charge_on(self, obj: RenewalMandate) -> dt.date | None:
        """The day of the next charge, or ``None`` for a mandate that is not active."""
        return charge_date(obj)

    def get_last_error(self, obj: RenewalMandate) -> str:
        """The reason the most recent failed charge was refused, or an empty string.

        The attempts are walked in Python, so a list view that has prefetched them
        answers every row without a further query.
        """
        failed = [
            attempt for attempt in obj.attempts.all() if attempt.outcome == RenewalOutcome.FAILED
        ]
        if len(failed) == 0:
            return ""
        return max(failed, key=lambda attempt: attempt.pk).error


class RenewalEnvelopeSerializer(serializers.Serializer[dict[str, Any]]):
    """``GET | PATCH /me/renewal`` and ``/me/donation``, and their ``POST .../confirm``.

    One key, ``mandate``, which is ``null`` for a member who has never set that
    kind of authority up.  The envelope is what carries that null: a bare null
    body is indistinguishable from an empty one.
    """

    mandate = RenewalMandateSerializer(allow_null=True)


class RenewalAttemptSerializer(serializers.ModelSerializer[RenewalAttempt]):
    """One scheduled charge, as ``GET /admin/renewals/attempts`` lists it."""

    mandate_id = serializers.IntegerField(read_only=True)
    payment_id = serializers.IntegerField(read_only=True, allow_null=True)
    membership_id = serializers.IntegerField(read_only=True, allow_null=True)
    user_id = serializers.SerializerMethodField()
    user_name = serializers.SerializerMethodField()

    class Meta:
        model = RenewalAttempt
        fields = [
            "id",
            "mandate_id",
            "membership_id",
            "payment_id",
            "user_id",
            "user_name",
            "scheduled_on",
            "outcome",
            "error",
            "noticed_at",
            "attempted_at",
            "result_emailed_at",
            "created_at",
        ]
        read_only_fields = fields

    def get_user_id(self, obj: RenewalAttempt) -> int:
        """The id of the member whose renewal this attempt is."""
        return obj.mandate.user_id

    def get_user_name(self, obj: RenewalAttempt) -> str:
        """The display name of the member whose renewal this attempt is."""
        return obj.mandate.user.display_name


class RenewalSetupSerializer(MandateScopedSerializer):
    """``POST /me/renewal/setup`` and ``/me/donation/setup``: what to save a method for.

    For the renewal, ``plan`` is the slug of the plan to renew and must be given
    (a 400 naming ``auto_renew`` otherwise) and have a duration, and ``cadence``
    may only be ``yearly`` (a 400 naming ``cadence`` otherwise).  For the donation,
    ``plan`` is not read, ``contribution_cents`` must be more than nothing, and
    ``cadence`` is ``monthly``, ``quarterly`` or ``yearly``, which is the default;
    ``remove_renewal_contribution`` agrees to move the renewal's contribution to it.
    ``provider`` must be one that can charge a saved method.  ``next_charge_on`` is
    the day of the first charge; leaving it out takes the day the membership runs
    out for a renewal, and today for a donation.  A day before today is a 400 naming
    ``next_charge_on``.
    """

    plan = serializers.CharField(required=False, allow_blank=True, default="")
    contribution_cents = serializers.IntegerField(
        required=False, min_value=0, max_value=MAX_CONTRIBUTION_CENTS, default=0
    )
    provider = serializers.ChoiceField(choices=MandateProvider.choices)
    next_charge_on = next_charge_on_field()
    cadence = cadence_field(default=MandateCadence.YEARLY)
    remove_renewal_contribution = remove_renewal_contribution_field()

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Drop the plan from a donation; refuse a renewal with no plan or not yearly."""
        if self.is_donation:
            return {**attrs, "plan": ""}
        refuse_non_yearly_renewal(attrs["cadence"])
        if not attrs["plan"]:
            raise serializers.ValidationError({"auto_renew": [RENEWAL_PLAN_MESSAGE]})
        return attrs


class StripeRenewalSetupClientSerializer(serializers.Serializer[dict[str, str]]):
    """What the Stripe Payment Element in setup mode needs."""

    client_secret = serializers.CharField()


class PayPalRenewalSetupClientSerializer(serializers.Serializer[dict[str, str]]):
    """What the PayPal buttons need to have the member approve a vault token."""

    setup_token = serializers.CharField()


@extend_schema_field({"type": "object"})
class MockRenewalSetupClientSerializer(serializers.Serializer[dict[str, Any]]):
    """The mock provider needs nothing from the browser to save its test card."""


class StripeRenewalSetupResponseSerializer(serializers.Serializer[dict[str, Any]]):
    """The body of ``POST /me/renewal/setup`` when ``provider`` is Stripe."""

    provider = serializers.ChoiceField(choices=[MandateProvider.STRIPE])
    client = StripeRenewalSetupClientSerializer()


class PayPalRenewalSetupResponseSerializer(serializers.Serializer[dict[str, Any]]):
    """The body of ``POST /me/renewal/setup`` when ``provider`` is PayPal."""

    provider = serializers.ChoiceField(choices=[MandateProvider.PAYPAL])
    client = PayPalRenewalSetupClientSerializer()


class MockRenewalSetupResponseSerializer(serializers.Serializer[dict[str, Any]]):
    """The body of ``POST /me/renewal/setup`` when ``provider`` is ``mock``."""

    provider = serializers.ChoiceField(choices=[MandateProvider.MOCK])
    client = MockRenewalSetupClientSerializer()


#: The body of ``POST /me/renewal/setup``, schema-only: ``client`` carries what the
#: chosen provider's browser SDK needs, discriminated by ``provider``.  The keys are
#: the plain ``str`` values, since they become mapping keys in the document.
RenewalSetupResponseSerializer = PolymorphicProxySerializer(
    component_name="RenewalSetupResponse",
    serializers={
        MandateProvider.STRIPE.value: StripeRenewalSetupResponseSerializer,
        MandateProvider.PAYPAL.value: PayPalRenewalSetupResponseSerializer,
        MandateProvider.MOCK.value: MockRenewalSetupResponseSerializer,
    },
    resource_type_field_name="provider",
)


class RenewalConfirmSerializer(serializers.Serializer[dict[str, Any]]):
    """``POST /me/renewal/confirm`` -- the provider's handle on what the browser did.

    ``setup_intent_id`` for Stripe and ``setup_token`` for PayPal; the mock
    provider needs neither.  Which one is required is the provider's business,
    and it answers 400 when the one it needs is missing.
    """

    setup_intent_id = serializers.CharField(required=False, allow_blank=True, default="")
    setup_token = serializers.CharField(required=False, allow_blank=True, default="")


class RenewalPatchSerializer(MandateScopedSerializer):
    """``PATCH /me/renewal`` and ``PATCH /me/donation``: what the authority charges.

    ``contribution_cents`` is required.  ``plan`` is the slug of the plan a renewal
    renews from now on; leaving it out leaves the plan alone, and a donation does
    not read it.  ``cadence`` changes how often a donation charges, and a renewal
    takes only ``yearly`` (a 400 naming ``cadence`` otherwise); leaving it out
    leaves the cadence alone.  ``next_charge_on`` moves the next charge; leaving it
    out leaves the stored day alone, and a day before today is a 400 naming
    ``next_charge_on``.
    """

    plan = serializers.CharField(required=False, allow_blank=True, default="")
    contribution_cents = serializers.IntegerField(min_value=0, max_value=MAX_CONTRIBUTION_CENTS)
    next_charge_on = next_charge_on_field()
    cadence = cadence_field(default=None)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Drop the plan from a donation, and refuse a renewal that is not yearly."""
        if self.is_donation:
            return {**attrs, "plan": ""}
        refuse_non_yearly_renewal(attrs["cadence"])
        return attrs


class RenewalStatusFilterSerializer(serializers.Serializer[dict[str, Any]]):
    """``GET /admin/renewals?status=&kind=`` -- an empty value narrows nothing.

    ``kind`` is one of the mandate kinds the rows carry: ``renewal``, ``both`` or
    ``contribution`` (a recurring donation).
    """

    status = serializers.CharField(required=False, allow_blank=True, default="")
    kind = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_status(self, value: str) -> str:
        """Return ``value``, or raise ``Unknown status '<value>'.`` for an unknown one."""
        if value and value not in MandateStatus.values:
            raise serializers.ValidationError(f"Unknown status '{value}'.")
        return value

    def validate_kind(self, value: str) -> str:
        """Return ``value``, or raise ``Unknown kind '<value>'.`` for an unknown one."""
        if value and value not in MandateKind.values:
            raise serializers.ValidationError(f"Unknown kind '{value}'.")
        return value


class RenewalRunRequestSerializer(serializers.Serializer[dict[str, Any]]):
    """``POST /system/renewals/run`` body: ``dry_run``, defaulting to ``False``."""

    dry_run = serializers.BooleanField(default=False)


class RenewalRunResultSerializer(serializers.Serializer[dict[str, Any]]):
    """The counts one automatic-renewal scan reports, and who they were about."""

    noticed = serializers.IntegerField()
    warned = serializers.IntegerField()
    charged = serializers.IntegerField()
    failed = serializers.IntegerField()
    paused = serializers.IntegerField()
    skipped = serializers.IntegerField()
    actions = RunActionSerializer(many=True)


# --------------------------------------------------------------------------
# Finance reports
# --------------------------------------------------------------------------
class FinancePaymentTermSerializer(serializers.ModelSerializer[Membership]):
    """The membership term a payment bought, as the finance row carries it."""

    class Meta:
        model = Membership
        fields = ["id", "starts_on", "ends_on", "status"]
        read_only_fields = fields


class PaymentRenewalAttemptSerializer(serializers.ModelSerializer[RenewalAttempt]):
    """The automatic charge a payment came from, when it came from one."""

    class Meta:
        model = RenewalAttempt
        fields = ["id", "scheduled_on", "outcome"]
        read_only_fields = fields


class FinancePaymentSerializer(serializers.ModelSerializer[Payment]):
    """One row of the finance payment list: everything but the refunds.

    Carries the provider's fee and net alongside the gross, what has been given
    back, the term the payment bought, the automatic charge it came from when it
    came from one, and the reconciliation fields a treasurer writes.  ``raw`` is
    never exposed: it is the provider's own payload and can hold anything.
    """

    user_id = serializers.IntegerField(read_only=True)
    user_name = serializers.SerializerMethodField()
    user_email = serializers.EmailField(source="user.email", read_only=True)
    plan = serializers.SerializerMethodField()
    kind = serializers.ChoiceField(choices=PaymentKind.choices, read_only=True)
    paid_on = serializers.DateField(read_only=True, allow_null=True)
    receipt_number = serializers.CharField(read_only=True)
    refunded_cents = serializers.IntegerField(read_only=True)
    reconciled_by = serializers.SerializerMethodField()
    recorded_by = serializers.SerializerMethodField()
    membership = FinancePaymentTermSerializer(read_only=True, allow_null=True)
    renewal_attempt = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            "id",
            "user_id",
            "user_name",
            "user_email",
            "plan",
            "kind",
            "amount_cents",
            "plan_amount_cents",
            "contribution_cents",
            "fee_cents",
            "net_cents",
            "refunded_cents",
            "currency",
            "provider",
            "wallet",
            "provider_ref",
            "status",
            "receipt_number",
            "receipt_sent_at",
            "paid_on",
            "received_on",
            "reconciled_on",
            "reconciled_by",
            "recorded_by",
            "note",
            "membership",
            "renewal_attempt",
            "created_at",
            "completed_at",
        ]
        read_only_fields = fields

    def get_user_name(self, obj: Payment) -> str:
        """The member's full name, or their email address when they have no name."""
        full = f"{obj.user.first_name} {obj.user.last_name}".strip()
        return full or obj.user.email

    def get_plan(self, obj: Payment) -> str | None:
        """The plan's name, or ``None`` for a payment that bought no plan."""
        return obj.plan.name if obj.plan is not None else None

    def get_reconciled_by(self, obj: Payment) -> str | None:
        """The treasurer who matched it to a statement, or ``None``."""
        return obj.reconciled_by.display_name if obj.reconciled_by is not None else None

    def get_recorded_by(self, obj: Payment) -> str | None:
        """The administrator who recorded it by hand, or ``None``."""
        return obj.recorded_by.display_name if obj.recorded_by is not None else None

    @extend_schema_field(PaymentRenewalAttemptSerializer(allow_null=True))
    def get_renewal_attempt(self, obj: Payment) -> dict[str, Any] | None:
        """The automatic charge behind it, or ``None`` when a person paid it.

        Read from the prefetched attempts rather than with a query of its own, so
        a page of the list costs the same as a single row.
        """
        attempt = next(iter(obj.renewal_attempts.all()), None)
        if attempt is None:
            return None
        return dict(PaymentRenewalAttemptSerializer(attempt).data)


class FinancePaymentDetailSerializer(FinancePaymentSerializer):
    """``GET /admin/payments/{id}``: the finance row with its refunds beneath it."""

    refunds = RefundSerializer(many=True, read_only=True)

    class Meta(FinancePaymentSerializer.Meta):
        fields = [*FinancePaymentSerializer.Meta.fields, "refunds"]
        read_only_fields = fields


class PaymentPatchSerializer(serializers.Serializer[dict[str, Any]]):
    """``PATCH /admin/payments/{id}``: the two fields a treasurer writes.

    ``reconciled_on`` is the day the payment was matched to a statement, or
    ``null`` to un-match it; ``note`` is the treasurer's own line.  Sending
    neither is a 400: the request would change nothing, and so is a
    ``reconciled_on`` later than the day ``apps.payments.dates`` allows.
    """

    reconciled_on = serializers.DateField(required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True, max_length=255)

    def validate_reconciled_on(self, value: dt.date | None) -> dt.date | None:
        """Return ``value``, or refuse a day no statement can have carried yet."""
        if value is not None and is_in_the_future(value):
            raise serializers.ValidationError("A payment cannot have been matched in the future.")
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Return ``attrs``, or refuse a body that names neither field."""
        if len(attrs) == 0:
            raise serializers.ValidationError("Send reconciled_on, note, or both.")
        return attrs


class ManualPaymentSerializer(serializers.Serializer[dict[str, Any]]):
    """``POST /admin/payments/record``: money taken by check, cash or transfer.

    ``plan`` is a plan slug or empty for a pure contribution, ``method`` is one of
    ``check``, ``cash``, ``bank_transfer`` or ``other``, ``reference`` is the check
    number and may be empty, and ``received_on`` is the day the money arrived.
    """

    user_id = serializers.IntegerField()
    plan = serializers.CharField(required=False, allow_null=True, allow_blank=True, default="")
    contribution_cents = serializers.IntegerField(
        required=False, min_value=0, max_value=MAX_CONTRIBUTION_CENTS, default=0
    )
    method = serializers.ChoiceField(choices=MANUAL_METHOD_CHOICES)
    reference = serializers.CharField(required=False, allow_blank=True, max_length=128, default="")
    received_on = serializers.DateField()
    note = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")


class ReconciliationRowSerializer(serializers.Serializer[ReconciliationRow]):
    """One row of ``GET /admin/payments/reconciliation``."""

    period = serializers.CharField()
    count = serializers.IntegerField()
    gross_cents = serializers.IntegerField()
    fee_cents = serializers.IntegerField()
    net_cents = serializers.IntegerField()
    refunded_cents = serializers.IntegerField()
    net_after_refunds_cents = serializers.IntegerField()
    reconciled_count = serializers.IntegerField()
    unreconciled_count = serializers.IntegerField()


class ContributionRowSerializer(serializers.Serializer[ContributionRow]):
    """One row of ``GET /admin/payments/contributions``."""

    user_id = serializers.IntegerField()
    name = serializers.CharField()
    email = serializers.EmailField()
    count = serializers.IntegerField()
    contribution_cents = serializers.IntegerField()
    refunded_cents = serializers.IntegerField()
    net_contribution_cents = serializers.IntegerField()


class LedgerMemberSerializer(serializers.Serializer[dict[str, Any]]):
    """Who the ledger is about."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    email = serializers.EmailField()
    membership = MembershipStatusSerializer()


class LedgerTotalsSerializer(serializers.Serializer[dict[str, int]]):
    """What the member has paid over their whole history, in cents."""

    paid_cents = serializers.IntegerField()
    contribution_cents = serializers.IntegerField()
    fee_cents = serializers.IntegerField()
    refunded_cents = serializers.IntegerField()


class MemberLedgerSerializer(serializers.Serializer[dict[str, Any]]):
    """``GET /admin/payments/ledger/{user_id}``: one member's whole money history."""

    user = LedgerMemberSerializer()
    totals = LedgerTotalsSerializer()
    payments = FinancePaymentDetailSerializer(many=True)
    mandate = RenewalMandateSerializer(allow_null=True)
    statement_years = serializers.ListField(child=serializers.IntegerField())


class FinanceMemberSerializer(serializers.Serializer[dict[str, Any]]):
    """One row of ``GET /admin/payments/members``: a member the finance area can bill.

    The finance screens never read the member record, so the search that stands
    behind the "record a payment" form carries only who the member is and where
    their membership stands.
    """

    user_id = serializers.IntegerField()
    name = serializers.CharField()
    email = serializers.EmailField()
    membership = MembershipStatusSerializer()


class MemberSearchQuerySerializer(serializers.Serializer[dict[str, Any]]):
    """``?search=`` for the finance area's member search.

    The parameter is optional, and an empty one asks for nobody rather than for
    everybody: the form shows names only once somebody has typed.
    """

    search = serializers.CharField(required=False, allow_blank=True, default="")
