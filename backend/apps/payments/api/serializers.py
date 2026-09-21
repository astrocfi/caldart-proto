"""Serializers for the payments API."""

from __future__ import annotations

from rest_framework import serializers

from apps.members.api.serializers import MembershipStatusSerializer, PlanSerializer
from apps.payments.models import Payment, PaymentProvider, PaymentStatus
from apps.payments.reports import DEFAULT_GROUP, GROUPS, PaymentFilters

#: What a report date parameter answers with when it is not a date on the calendar.
DATE_FORMAT_MESSAGE = "Expected a date as YYYY-MM-DD."
GROUP_MESSAGE = "Expected 'month' or 'year'."


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


class ReportDateField(serializers.DateField):
    """One end of a report's date range, where an empty parameter is no bound at all.

    The report screen sends every parameter on every request, so ``?from=`` has to
    mean the same as leaving ``from`` out.  Anything else that is not a date the
    calendar has -- ``2026-02-30`` as much as ``last tuesday`` -- is a 400 naming
    this parameter.
    """

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("required", False)
        kwargs.setdefault("default", None)
        kwargs.setdefault("error_messages", {"invalid": DATE_FORMAT_MESSAGE})
        super().__init__(**kwargs)

    def to_internal_value(self, value):
        if value == "":
            return None
        return super().to_internal_value(value)


class PaymentReportQuerySerializer(serializers.Serializer):
    """The query string ``GET /admin/payments``, ``/summary`` and ``/export.csv`` share.

    Every parameter is optional and an empty one narrows nothing: ``from`` and ``to``
    bound the date the money arrived, ``provider`` and ``status`` must name one of
    the payment choices, ``search`` matches a name, an email address or a provider
    reference, and ``group`` is the summary's period, ``month`` or ``year``.  The
    three endpoints therefore refuse the same input the same way, with the complaint
    keyed by the parameter it came from.
    """

    provider = serializers.CharField(required=False, allow_blank=True, default="")
    status = serializers.CharField(required=False, allow_blank=True, default="")
    search = serializers.CharField(required=False, allow_blank=True, default="")
    group = serializers.CharField(required=False, allow_blank=True, default=DEFAULT_GROUP)

    def get_fields(self) -> dict:
        """The declared fields plus the date bounds, whose names are Python keywords."""
        fields = super().get_fields()
        fields["from"] = ReportDateField()
        fields["to"] = ReportDateField()
        return fields

    def validate_provider(self, value: str) -> str:
        if value and value not in PaymentProvider.values:
            raise serializers.ValidationError(f"Unknown provider '{value}'.")
        return value

    def validate_status(self, value: str) -> str:
        if value and value not in PaymentStatus.values:
            raise serializers.ValidationError(f"Unknown status '{value}'.")
        return value

    def validate_group(self, value: str) -> str:
        group = value or DEFAULT_GROUP
        if group not in GROUPS:
            raise serializers.ValidationError(GROUP_MESSAGE)
        return group

    def to_filters(self) -> PaymentFilters:
        """The validated parameters as the narrowing the report functions take.

        Call it after ``is_valid``.  The summary reads its period from
        ``validated_data["group"]``, which no filter uses.
        """
        data = self.validated_data
        return PaymentFilters(
            date_from=data["from"],
            date_to=data["to"],
            provider=data["provider"],
            status=data["status"],
            search=data["search"],
        )
