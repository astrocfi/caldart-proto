"""Serializers more than one app's API returns.

The computed membership status rides on the account payload, the payment result
and the member-admin record; the plan catalog is read by the join wizard and by
the checkout.  Each shape is declared once here so the three APIs cannot drift
apart, and imported wherever it is needed.
"""

from __future__ import annotations

from rest_framework import serializers

from apps.members.models import MembershipPlan, MembershipState


class MembershipStatusSerializer(serializers.Serializer):
    """The dict ``members.services.membership_status`` returns."""

    status = serializers.ChoiceField(choices=MembershipState.choices)
    expires_on = serializers.DateField(allow_null=True)
    plan = serializers.CharField(allow_null=True)
    is_lifetime = serializers.BooleanField()


class PlanSerializer(serializers.ModelSerializer):
    """One membership plan, as the public catalog and the checkout list it."""

    class Meta:
        model = MembershipPlan
        fields = ["slug", "name", "price_cents", "duration_days", "description"]
        read_only_fields = fields
