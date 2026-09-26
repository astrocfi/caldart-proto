"""Serializers for the public donation page's endpoints.

The giver's details are the profile's own fields under the profile's own rules
(:class:`~apps.members.api.profile_serializers.ProfileSerializer`), cut down to what
the donation form collects; the confirmation bodies are the portal's, plus the
``token`` that proves the anonymous caller started the payment.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from drf_spectacular.utils import PolymorphicProxySerializer
from rest_framework import serializers
from rest_framework.utils.model_meta import FieldInfo

from apps.darts.api.serializers import DartRefSerializer
from apps.members.api.profile_serializers import ProfileSerializer
from apps.members.models import US_STATE_VALUES
from apps.payments.api.serializers import (
    ContributionTierSerializer,
    MockCheckoutResponseSerializer,
    MockCompleteSerializer,
    PayPalCaptureSerializer,
    PayPalCheckoutResponseSerializer,
    StripeCheckoutResponseSerializer,
    StripeConfirmSerializer,
)
from apps.payments.donations import DONOR_PROFILE_FIELDS
from apps.payments.models import MAX_CONTRIBUTION_CENTS, PaymentProvider

#: What a gift of nothing is told.
NO_AMOUNT_MESSAGE = "Choose an amount to give."


class StateChoiceSerializer(serializers.Serializer[dict[str, str]]):
    """One state the donation form offers: its two-letter code and its name."""

    value = serializers.CharField()
    # DRF's Field.label is a different thing from this serializer's own `label`
    # field, so the stubs see the declaration as a narrowing of the attribute.
    label = serializers.CharField()  # type: ignore[assignment]


class DonationsConfigSerializer(serializers.Serializer[dict[str, Any]]):
    """``GET /donations/config``: everything the public donation form offers."""

    providers = serializers.ListField(
        child=serializers.ChoiceField(choices=PaymentProvider.choices)
    )
    stripe_publishable_key = serializers.CharField(allow_blank=True)
    paypal_client_id = serializers.CharField(allow_blank=True)
    contribution_tiers = ContributionTierSerializer(many=True)
    max_contribution_cents = serializers.IntegerField()
    counties = serializers.ListField(child=serializers.CharField())
    darts = DartRefSerializer(many=True)
    states = StateChoiceSerializer(many=True)


class DonationCheckoutSerializer(ProfileSerializer):
    """``POST /donations/checkout``: who is giving, how much, and through which provider.

    ``first_name``, ``last_name``, ``email`` and ``phone`` are required; the phone
    follows the profile's rule and is stored as ``XXX-XXX-XXXX``.  The optional fields
    are the profile's own, under the profile's own rules (a five-digit ZIP code, a
    three-character airport, an active DART named by ``dart_id``), except that a
    pilot certificate needs no number here.  ``contribution_cents`` runs from 1 to
    ``MAX_CONTRIBUTION_CENTS``: nothing is refused with "Choose an amount to give."
    There is no amount field: the gift is the contribution and nothing else.
    """

    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    email = serializers.EmailField(max_length=254)
    contribution_cents = serializers.IntegerField(min_value=0, max_value=MAX_CONTRIBUTION_CENTS)
    provider = serializers.ChoiceField(choices=PaymentProvider.choices)
    state = serializers.ChoiceField(choices=US_STATE_VALUES, required=False, allow_blank=True)

    class Meta(ProfileSerializer.Meta):
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone",
            "contribution_cents",
            "provider",
            *(name for name in DONOR_PROFILE_FIELDS if name != "dart"),
            "dart_id",
        ]

    def get_field_names(
        self, declared_fields: Mapping[str, serializers.Field[Any, Any, Any, Any]], info: FieldInfo
    ) -> list[str]:
        """The fields in ``Meta.fields``, and none of the profile's others.

        The profile serializer declares fields the donation form does not collect
        (the aircraft, the medical, the ratings); DRF would otherwise insist that every
        declared field be listed.
        """
        return list(self.Meta.fields)

    def validate_contribution_cents(self, value: int) -> int:
        """Refuse a gift of nothing with :data:`NO_AMOUNT_MESSAGE`."""
        if value == 0:
            raise serializers.ValidationError(NO_AMOUNT_MESSAGE)
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Accept the body as the field rules left it.

        The profile's cross-field rules ask a pilot for a certificate number and a
        medical expiration date, neither of which the donation form collects.
        """
        return attrs


class StripeDonationCheckoutResponseSerializer(StripeCheckoutResponseSerializer):
    """The 201 body of ``POST /donations/checkout`` when ``provider`` is Stripe."""

    token = serializers.CharField()


class PayPalDonationCheckoutResponseSerializer(PayPalCheckoutResponseSerializer):
    """The 201 body of ``POST /donations/checkout`` when ``provider`` is PayPal."""

    token = serializers.CharField()


class MockDonationCheckoutResponseSerializer(MockCheckoutResponseSerializer):
    """The 201 body of ``POST /donations/checkout`` when ``provider`` is ``mock``."""

    token = serializers.CharField()


#: The 201 body of ``POST /donations/checkout``, schema-only: the portal checkout's
#: answer for each provider, plus ``token``.
DonationCheckoutResponseSerializer = PolymorphicProxySerializer(
    component_name="DonationCheckoutResponse",
    serializers={
        PaymentProvider.STRIPE.value: StripeDonationCheckoutResponseSerializer,
        PaymentProvider.PAYPAL.value: PayPalDonationCheckoutResponseSerializer,
        PaymentProvider.MOCK.value: MockDonationCheckoutResponseSerializer,
    },
    resource_type_field_name="provider",
)


class DonationStripeConfirmSerializer(StripeConfirmSerializer):
    """``POST /donations/stripe/confirm``: the portal's body, plus ``token``."""

    token = serializers.CharField()


class DonationPayPalCaptureSerializer(PayPalCaptureSerializer):
    """``POST /donations/paypal/capture``: the portal's body, plus ``token``."""

    token = serializers.CharField()


class DonationMockCompleteSerializer(MockCompleteSerializer):
    """``POST /donations/mock/complete``: the portal's body, plus ``token``."""

    token = serializers.CharField()


class DonationStatusQuerySerializer(serializers.Serializer[dict[str, Any]]):
    """``GET /donations/{id}?token=``: the token is the only thing asked for."""

    token = serializers.CharField(required=False, allow_blank=True, default="")
