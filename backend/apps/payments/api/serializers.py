"""Serializers for the payments API."""

from __future__ import annotations

import datetime as dt
from typing import Any

from drf_spectacular.utils import PolymorphicProxySerializer, extend_schema_field
from rest_framework import serializers

from apps.members.api.serializers import MembershipStatusSerializer, PlanSerializer
from apps.payments.models import Payment, PaymentProvider, PaymentStatus
from apps.payments.reports import DEFAULT_GROUP, GROUPS, PaymentFilters, PeriodSummary

#: What a report date parameter answers with when it is not a date on the calendar.
DATE_FORMAT_MESSAGE = "Expected a date as YYYY-MM-DD."
GROUP_MESSAGE = "Expected 'month' or 'year'."

#: The largest contribution a checkout accepts, in cents: ten million dollars.
#: Anything larger is a typo or an attack, and is refused at the boundary rather
#: than stored and handed to a provider.
MAX_CONTRIBUTION_CENTS = 1_000_000_000


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


class CheckoutSerializer(serializers.Serializer[dict[str, Any]]):
    """``POST /payments/checkout``.

    There is deliberately no amount field: the server recomputes the total from
    the plan price plus the contribution.  A contribution outside
    ``0..MAX_CONTRIBUTION_CENTS`` is a 400 naming ``contribution_cents``.
    """

    plan = serializers.CharField(required=False, allow_null=True, allow_blank=True, default="")
    contribution_cents = serializers.IntegerField(
        required=False, min_value=0, max_value=MAX_CONTRIBUTION_CENTS, default=0
    )
    provider = serializers.ChoiceField(choices=PaymentProvider.choices)


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


class MockCompleteSerializer(serializers.Serializer[dict[str, Any]]):
    """``POST /payments/mock/complete``, whose ``outcome`` is ``succeed`` or ``fail``."""

    payment_id = serializers.IntegerField()
    outcome = serializers.ChoiceField(choices=["succeed", "fail"], default="succeed")


class PaymentResultSerializer(serializers.Serializer[dict[str, Any]]):
    """``GET /payments/{id}`` and the response to every confirm endpoint."""

    status = serializers.ChoiceField(choices=PaymentStatus.choices)
    membership = MembershipStatusSerializer()


class PaymentSerializer(serializers.ModelSerializer[Payment]):
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
        """The member's full name, or their email address when they have no name."""
        full = f"{obj.user.first_name} {obj.user.last_name}".strip()
        return full or obj.user.email

    def get_plan(self, obj: Payment) -> str | None:
        """The plan's name, or ``None`` for a payment that bought no plan."""
        return obj.plan.name if obj.plan is not None else None


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
    by_provider = ProviderTotalsSerializer()


class ReportDateField(serializers.DateField):
    """One end of a report's date range, where an empty parameter is no bound at all.

    The report screen sends every parameter on every request, so ``?from=`` has to
    mean the same as leaving ``from`` out.  Anything else that is not a date the
    calendar has -- ``2026-02-30`` as much as ``last tuesday`` -- is a 400 naming
    this parameter.
    """

    def __init__(self, **kwargs: Any) -> None:
        """Build the field, defaulting to optional, unbounded, and our own message."""
        kwargs.setdefault("required", False)
        kwargs.setdefault("default", None)
        kwargs.setdefault("error_messages", {"invalid": DATE_FORMAT_MESSAGE})
        super().__init__(**kwargs)

    # DRF's DateField promises a date, and answering an empty parameter with
    # ``None`` is the whole point of this field.
    def to_internal_value(self, value: dt.date | str) -> dt.date | None:  # type: ignore[override]
        """``None`` for an empty parameter, otherwise the date the string names.

        Raises DRF's ``ValidationError`` with :data:`DATE_FORMAT_MESSAGE` for
        anything else.
        """
        if value == "":
            return None
        return super().to_internal_value(value)


class PaymentReportQuerySerializer(serializers.Serializer[dict[str, Any]]):
    """The query string ``GET /admin/payments``, ``/summary`` and ``/export.csv`` share.

    Every parameter is optional and an empty one narrows nothing: ``from`` and ``to``
    bound the date the money arrived, ``provider``, and ``status`` must name one of
    the payment choices, ``search`` matches a name, an email address or a provider
    reference, and ``group`` is the summary's period, ``month``, or ``year``.  The
    three endpoints therefore refuse the same input the same way, with the complaint
    keyed by the parameter it came from.
    """

    provider = serializers.CharField(required=False, allow_blank=True, default="")
    status = serializers.CharField(required=False, allow_blank=True, default="")
    search = serializers.CharField(required=False, allow_blank=True, default="")
    group = serializers.CharField(required=False, allow_blank=True, default=DEFAULT_GROUP)

    def get_fields(self) -> dict[str, serializers.Field[Any, Any, Any, Any]]:
        """The declared fields plus the date bounds, whose names are Python keywords."""
        fields = super().get_fields()
        fields["from"] = ReportDateField()
        fields["to"] = ReportDateField()
        return fields

    def validate_provider(self, value: str) -> str:
        """Return ``value``, or raise ``Unknown provider '<value>'.`` for an unknown one.

        An empty string is accepted and narrows nothing.
        """
        if value and value not in PaymentProvider.values:
            raise serializers.ValidationError(f"Unknown provider '{value}'.")
        return value

    def validate_status(self, value: str) -> str:
        """Return ``value``, or raise ``Unknown status '<value>'.`` for an unknown one.

        An empty string is accepted and narrows nothing.
        """
        if value and value not in PaymentStatus.values:
            raise serializers.ValidationError(f"Unknown status '{value}'.")
        return value

    def validate_group(self, value: str) -> str:
        """Return the period to group by, defaulting an empty parameter to ``month``.

        Raises DRF's ``ValidationError`` with :data:`GROUP_MESSAGE` for anything
        but ``month`` or ``year``.
        """
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
