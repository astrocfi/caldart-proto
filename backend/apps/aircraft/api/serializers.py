"""Serializers for the aircraft register and the leader check."""

from __future__ import annotations

from typing import Any, cast

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from apps.aircraft.models import (
    N_NUMBER_MESSAGE,
    N_NUMBER_RE,
    Aircraft,
    normalize_n_number,
)
from apps.members.models import (
    RATING_VALUES,
    IfrRated,
    MedicalType,
    MembershipState,
    PilotCertificateType,
)

NEGATIVE_MONEY_MESSAGE = "Enter an amount of $0 or more."


class NNumberField(serializers.CharField):
    """A registration field that always stores the canonical ``N172SP`` form.

    Normalizing in ``to_internal_value`` (rather than in ``validate_n_number``)
    matters: DRF runs a field's validators on the value this returns, so the
    uniqueness check sees ``N12345`` even when the member typed ``n-12345``.
    """

    def to_internal_value(self, data: object) -> str:
        """Return ``data`` normalized to canonical N-number form.

        ``data`` is the raw value from the request body, which ``CharField`` coerces
        to a string and rejects when it is a mapping, a list or a boolean.  Raises a
        validation error when normalization leaves nothing usable.
        """
        # The stubs type `CharField.to_internal_value` as taking a `str`; the runtime
        # field also coerces an int or a float and rejects every other type itself.
        value = super().to_internal_value(cast("str", data))
        normalized = normalize_n_number(value)
        if not normalized:
            raise serializers.ValidationError("Enter a registration, for example N172SP.")
        if not N_NUMBER_RE.match(normalized):
            raise serializers.ValidationError(N_NUMBER_MESSAGE)
        return normalized


class AircraftSummarySerializer(serializers.ModelSerializer[Aircraft]):
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


class AircraftSerializer(serializers.ModelSerializer[Aircraft]):
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


class AircraftPilotSerializer(serializers.Serializer[Any]):
    """A member who lists this aircraft as one they commonly fly."""

    user_id = serializers.IntegerField()
    name = serializers.CharField()
    email = serializers.EmailField()
    membership_status = serializers.ChoiceField(choices=MembershipState.choices)
    medical_is_current = serializers.BooleanField()


class AircraftDetailSerializer(AircraftSerializer):
    """The record plus the members who fly it, for admin and leader screens."""

    pilots = serializers.SerializerMethodField()

    class Meta(AircraftSerializer.Meta):
        fields = [*AircraftSerializer.Meta.fields, "pilots"]

    @extend_schema_field(AircraftPilotSerializer(many=True))
    def get_pilots(self, obj: Aircraft) -> list[dict[str, Any]]:
        """Return the serialized pilots who list ``obj`` among the aircraft they fly."""
        from apps.aircraft.services import aircraft_pilots

        # The stubs type a serializer's `.data` for the single-instance case; with
        # `many=True` DRF builds a `ListSerializer` at runtime and `.data` is a list.
        return cast(
            "list[dict[str, Any]]", AircraftPilotSerializer(aircraft_pilots(obj), many=True).data
        )


# --------------------------------------------------------------------------
# Leader check
# --------------------------------------------------------------------------
class LeaderSearchResultSerializer(serializers.Serializer[Any]):
    """One row of a leader's member search."""

    user_id = serializers.IntegerField()
    name = serializers.CharField()
    email = serializers.EmailField()
    dart = serializers.CharField(allow_null=True)
    membership_status = serializers.ChoiceField(choices=MembershipState.choices)


class LeaderMembershipSerializer(serializers.Serializer[Any]):
    """The membership fields of the leader status card."""

    status = serializers.ChoiceField(choices=MembershipState.choices)
    expires_on = serializers.DateField(allow_null=True)
    plan = serializers.CharField(allow_null=True)


class LeaderCertificateSerializer(serializers.Serializer[Any]):
    """The pilot certificate fields of the leader status card."""

    type = serializers.ChoiceField(choices=PilotCertificateType.choices)
    number = serializers.CharField(allow_blank=True)
    ifr_rated = serializers.ChoiceField(choices=IfrRated.choices)
    ratings = serializers.ListField(child=serializers.ChoiceField(choices=RATING_VALUES))


class LeaderMedicalSerializer(serializers.Serializer[Any]):
    """The medical certificate fields of the leader status card."""

    type = serializers.ChoiceField(choices=MedicalType.choices)
    expiration = serializers.DateField(allow_null=True)
    is_current = serializers.BooleanField()


class LeaderGoNoGoSerializer(serializers.Serializer[Any]):
    """The two go/no-go booleans, so a leader sees why, not just whether."""

    membership = serializers.BooleanField()
    medical = serializers.BooleanField()


class LeaderStatusSerializer(serializers.Serializer[Any]):
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
