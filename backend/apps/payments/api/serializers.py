"""Serializers for the payments API."""

from __future__ import annotations

from rest_framework import serializers

from apps.members.models import MembershipPlan
from apps.payments.models import Payment, PaymentProvider, PaymentStatus


class MembershipStatusSerializer(serializers.Serializer):
    """The dict returned by ``members.services.membership_status``."""

    status = serializers.ChoiceField(choices=["current", "expired", "none"])
    expires_on = serializers.DateField(allow_null=True)
    plan = serializers.CharField(allow_null=True)
    is_lifetime = serializers.BooleanField()


class PlanSerializer(serializers.ModelSerializer):
    """A purchasable plan, as offered by the checkout."""

    class Meta:
        model = MembershipPlan
        fields = ["slug", "name", "price_cents", "duration_days", "description"]
        read_only_fields = fields


class ContributionTierSerializer(serializers.Serializer):
    label = serializers.CharField()
    cents = serializers.IntegerField()


class PaymentsConfigSerializer(serializers.Serializer):
    """``GET /payments/config``."""

    providers = serializers.ListField(child=serializers.CharField())
    stripe_publishable_key = serializers.CharField(allow_blank=True)
    paypal_client_id = serializers.CharField(allow_blank=True)
    plans = PlanSerializer(many=True)
    contribution_tiers = ContributionTierSerializer(many=True)


class CheckoutSerializer(serializers.Serializer):
    """``POST /payments/checkout``.

    There is deliberately no amount field: the server recomputes the total from
    the plan price plus the contribution.
    """

    plan = serializers.CharField(required=False, allow_null=True, allow_blank=True, default="")
    contribution_cents = serializers.IntegerField(required=False, min_value=0, default=0)
    provider = serializers.ChoiceField(choices=PaymentProvider.values)


class CheckoutResponseSerializer(serializers.Serializer):
    payment_id = serializers.IntegerField()
    provider = serializers.CharField()
    client = serializers.DictField()


class StripeConfirmSerializer(serializers.Serializer):
    payment_id = serializers.IntegerField()
    payment_intent_id = serializers.CharField(required=False, allow_blank=True, default="")


class PayPalCaptureSerializer(serializers.Serializer):
    payment_id = serializers.IntegerField()
    order_id = serializers.CharField(required=False, allow_blank=True, default="")


class MockCompleteSerializer(serializers.Serializer):
    payment_id = serializers.IntegerField()
    outcome = serializers.ChoiceField(choices=["succeed", "fail"], default="succeed")


class PaymentResultSerializer(serializers.Serializer):
    """``GET /payments/{id}`` and the response to every confirm endpoint."""

    status = serializers.ChoiceField(choices=PaymentStatus.values)
    membership = MembershipStatusSerializer()


class PaymentSerializer(serializers.ModelSerializer):
    """A row of the ``account_admin`` payment report."""

    user_id = serializers.IntegerField(read_only=True)
    user_name = serializers.SerializerMethodField()
    plan = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            "id",
            "user_id",
            "user_name",
            "plan",
            "amount_cents",
            "plan_amount_cents",
            "contribution_cents",
            "currency",
            "provider",
            "wallet",
            "provider_ref",
            "status",
            "created_at",
            "completed_at",
        ]
        read_only_fields = fields

    def get_user_name(self, obj: Payment) -> str:
        full = f"{obj.user.first_name} {obj.user.last_name}".strip()
        return full or obj.user.email

    def get_plan(self, obj: Payment) -> str | None:
        return obj.plan.name if obj.plan_id else None


class PaymentPeriodSummarySerializer(serializers.Serializer):
    """One row of ``GET /admin/payments/summary``."""

    period = serializers.CharField()
    count = serializers.IntegerField()
    total_cents = serializers.IntegerField()
    plan_cents = serializers.IntegerField()
    contribution_cents = serializers.IntegerField()
    by_provider = serializers.DictField(child=serializers.IntegerField())
