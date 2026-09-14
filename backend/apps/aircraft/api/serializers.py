"""Serializers for the aircraft register and the leader check."""

from __future__ import annotations

from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from apps.aircraft.models import Aircraft, normalize_n_number

NEGATIVE_MONEY_MESSAGE = "Enter an amount of $0 or more."


class NNumberField(serializers.CharField):
    """A registration field that always stores the canonical ``N12345`` form.

    Normalising in ``to_internal_value`` (rather than in ``validate_n_number``)
    matters: DRF runs a field's validators on the value this returns, so the
    uniqueness check sees ``N12345`` even when the member typed ``n-12345``.
    """

    def to_internal_value(self, data) -> str:
        value = super().to_internal_value(data)
        normalized = normalize_n_number(value)
        if not normalized:
            raise serializers.ValidationError("Enter a registration, for example N12345.")
        return normalized


class AircraftSummarySerializer(serializers.ModelSerializer):
    """The short form embedded in profiles, leader cards and pickers."""

    insurance_is_current = serializers.BooleanField(read_only=True)
    insurance_summary = serializers.CharField(read_only=True)

    class Meta:
        model = Aircraft
        fields = [
            "id",
            "n_number",
            "make",
            "model",
            "insurance_is_current",
            "insurance_expiration",
            "insurance_summary",
        ]
        read_only_fields = fields


class AircraftSerializer(serializers.ModelSerializer):
    """The full record.  ``created_by`` is set by the view."""

    n_number = NNumberField(
        max_length=12,
        validators=[
            UniqueValidator(
                queryset=Aircraft.objects.all(),
                message="An aircraft with this N-number is already on file.",
            )
        ],
    )
    make = serializers.CharField(max_length=60, allow_blank=False)
    model = serializers.CharField(max_length=60, allow_blank=False)
    insurance_liability_per_occurrence_cents = serializers.IntegerField(
        min_value=0, required=False, error_messages={"min_value": NEGATIVE_MONEY_MESSAGE}
    )
    insurance_liability_per_person_cents = serializers.IntegerField(
        min_value=0, required=False, error_messages={"min_value": NEGATIVE_MONEY_MESSAGE}
    )
    insurance_hull_cents = serializers.IntegerField(
        min_value=0,
        required=False,
        allow_null=True,
        error_messages={"min_value": NEGATIVE_MONEY_MESSAGE},
    )
    insurance_is_current = serializers.BooleanField(read_only=True)
    insurance_summary = serializers.CharField(read_only=True)

    class Meta:
        model = Aircraft
        fields = [
            "id",
            "n_number",
            "make",
            "model",
            "year",
            "owner_type",
            "owner_name",
            "owner_contact",
            "seats",
            "insurance_carrier",
            "insurance_policy_number",
            "insurance_liability_per_occurrence_cents",
            "insurance_liability_per_person_cents",
            "insurance_hull_cents",
            "insurance_expiration",
            "insurance_is_current",
            "insurance_summary",
            "notes",
            "created_by",
            "is_active",
        ]
        read_only_fields = ["id", "created_by", "insurance_is_current", "insurance_summary"]


class AircraftPilotSerializer(serializers.Serializer):
    """A member who lists this aircraft as one they commonly fly."""

    user_id = serializers.IntegerField()
    name = serializers.CharField()
    email = serializers.EmailField()
    membership_status = serializers.ChoiceField(choices=["current", "expired", "none"])
    medical_is_current = serializers.BooleanField()


class AircraftDetailSerializer(AircraftSerializer):
    """The record plus the members who fly it, for admin and leader screens."""

    pilots = serializers.SerializerMethodField()

    class Meta(AircraftSerializer.Meta):
        fields = [*AircraftSerializer.Meta.fields, "pilots"]

    def get_pilots(self, obj: Aircraft) -> list[dict]:
        from apps.aircraft.services import aircraft_pilots

        return AircraftPilotSerializer(aircraft_pilots(obj), many=True).data


# --------------------------------------------------------------------------
# Leader check
# --------------------------------------------------------------------------
class LeaderSearchResultSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    name = serializers.CharField()
    email = serializers.EmailField()
    dart = serializers.CharField(allow_null=True)
    membership_status = serializers.ChoiceField(choices=["current", "expired", "none"])


class LeaderMembershipSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["current", "expired", "none"])
    expires_on = serializers.DateField(allow_null=True)
    plan = serializers.CharField(allow_null=True)


class LeaderCertificateSerializer(serializers.Serializer):
    type = serializers.CharField()
    number = serializers.CharField(allow_blank=True)
    ifr_rated = serializers.CharField()
    ratings = serializers.ListField(child=serializers.CharField())


class LeaderMedicalSerializer(serializers.Serializer):
    type = serializers.CharField()
    expiration = serializers.DateField(allow_null=True)
    is_current = serializers.BooleanField()


class LeaderGoNoGoSerializer(serializers.Serializer):
    membership = serializers.BooleanField()
    medical = serializers.BooleanField()


class LeaderStatusSerializer(serializers.Serializer):
    """The status card a DART leader reads before a flight."""

    name = serializers.CharField()
    email = serializers.EmailField()
    phone = serializers.CharField(allow_blank=True)
    dart = serializers.CharField(allow_null=True)
    membership = LeaderMembershipSerializer()
    certificate = LeaderCertificateSerializer()
    medical = LeaderMedicalSerializer()
    aircraft = AircraftSummarySerializer(many=True)
    go_no_go = LeaderGoNoGoSerializer()
