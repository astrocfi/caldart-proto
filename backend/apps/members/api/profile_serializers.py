"""Serializers for member self-service (PLAN §6.3, §6.5).

Everything here is scoped to ``request.user``: the profile they may edit, the
membership terms and payments they may read, and the two public catalogues
(DARTs and plans) the join wizard needs before anyone has signed in.
"""

from __future__ import annotations

import re

from rest_framework import serializers

from apps.aircraft.api.serializers import AircraftSummarySerializer
from apps.members.models import (
    RATING_VALUES,
    Dart,
    MedicalType,
    MemberProfile,
    Membership,
    MembershipPlan,
    PilotCertificateType,
)
from apps.payments.models import Payment

#: Two letters, e.g. ``CA``.
STATE_RE = re.compile(r"^[A-Za-z]{2}$")

#: ``12345`` or ``12345-6789``.
POSTAL_RE = re.compile(r"^\d{5}(-\d{4})?$")


class DartSerializer(serializers.ModelSerializer):
    """``GET /darts`` — the public DART catalogue."""

    class Meta:
        model = Dart
        fields = ["id", "name", "airport_identifier", "city"]
        read_only_fields = fields


class DartRefSerializer(serializers.ModelSerializer):
    """The ``dart: {id, name}`` stub nested in a profile."""

    class Meta:
        model = Dart
        fields = ["id", "name"]
        read_only_fields = fields


class PlanSerializer(serializers.ModelSerializer):
    """``GET /plans`` — the public plan catalogue."""

    class Meta:
        model = MembershipPlan
        fields = ["slug", "name", "price_cents", "duration_days", "description"]
        read_only_fields = fields


class MembershipTermSerializer(serializers.ModelSerializer):
    """One row of the membership history in ``GET /me/membership``."""

    plan = serializers.CharField(source="plan.name", read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "plan", "starts_on", "ends_on", "status", "source"]
        read_only_fields = fields


class PaymentSummarySerializer(serializers.ModelSerializer):
    """The trimmed payment row a member sees for themselves (§6.3)."""

    plan = serializers.SerializerMethodField()

    class Meta:
        model = Payment
        fields = [
            "id",
            "plan",
            "amount_cents",
            "contribution_cents",
            "provider",
            "status",
            "completed_at",
        ]
        read_only_fields = fields

    def get_plan(self, obj) -> str | None:
        return obj.plan.name if obj.plan_id else None


class ProfileSerializer(serializers.ModelSerializer):
    """``GET/PUT/PATCH /me/profile``.

    ``dart`` reads as ``{id, name}`` and is written as ``dart_id``; ``aircraft``
    is read-only here and maintained through ``/me/profile/aircraft``.  The
    admin-only ``notes`` and ``how_heard`` fields are deliberately absent.
    """

    dart = DartRefSerializer(read_only=True)
    dart_id = serializers.PrimaryKeyRelatedField(
        source="dart",
        queryset=Dart.objects.filter(is_active=True),
        required=False,
        allow_null=True,
        write_only=True,
    )
    aircraft = AircraftSummarySerializer(many=True, read_only=True)
    medical_is_current = serializers.BooleanField(read_only=True)

    # A member has to be reachable: required on PUT, never blank on PATCH.
    phone = serializers.CharField(max_length=32)
    ratings = serializers.ListField(
        child=serializers.ChoiceField(choices=RATING_VALUES),
        required=False,
        allow_empty=True,
    )

    class Meta:
        model = MemberProfile
        fields = [
            # contact
            "phone",
            "phone_alt",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "county",
            "emergency_contact_name",
            "emergency_contact_phone",
            # aviation
            "home_airport_identifier",
            "home_airport_city",
            "dart",
            "dart_id",
            "air_care_alliance_number",
            "pilot_certificate_type",
            "certificate_number",
            "ifr_rated",
            "ratings",
            "medical_type",
            "medical_expiration",
            "medical_is_current",
            "flight_review_date",
            "total_hours",
            "aircraft",
            # volunteer interests
            "vol_ground_team",
            "vol_exercise_training",
            "vol_member_support",
            "vol_fundraising",
            "vol_social_media",
            "vol_newsletter",
        ]

    # -- field-level rules -------------------------------------------------
    def validate_state(self, value: str) -> str:
        value = (value or "").strip().upper()
        if value and not STATE_RE.match(value):
            raise serializers.ValidationError("Use the two-letter state code, for example CA.")
        return value

    def validate_postal_code(self, value: str) -> str:
        value = (value or "").strip()
        if value and not POSTAL_RE.match(value):
            raise serializers.ValidationError("Use a ZIP code like 95035 or 95035-1234.")
        return value

    def validate_ratings(self, value: list[str]) -> list[str]:
        """Keep the stored order stable and drop repeats."""
        unique: list[str] = []
        for rating in value:
            if rating not in unique:
                unique.append(rating)
        return unique

    # -- cross-field rules -------------------------------------------------
    def _merged(self, attrs: dict, name: str):
        """The value a PATCH would leave in place, so rules see the whole row."""
        if name in attrs:
            return attrs[name]
        return getattr(self.instance, name, None)

    def validate(self, attrs: dict) -> dict:
        errors: dict[str, str] = {}

        medical_type = self._merged(attrs, "medical_type")
        if medical_type and medical_type != MedicalType.NONE:
            if not self._merged(attrs, "medical_expiration"):
                errors["medical_expiration"] = (
                    "Give the expiration date of your medical certificate."
                )

        certificate = self._merged(attrs, "pilot_certificate_type")
        if certificate and certificate != PilotCertificateType.NONE:
            if not (self._merged(attrs, "certificate_number") or "").strip():
                errors["certificate_number"] = "Give your pilot certificate number."

        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    # -- write -------------------------------------------------------------
    def update(self, instance, validated_data):
        """``PUT`` really replaces: anything left out goes back to its default.

        DRF's own behaviour is to ignore absent optional fields even on a full
        update, which would make ``PUT`` and ``PATCH`` indistinguishable.  The
        contract in PLAN §6.3 says one is a full update and the other partial,
        so unticked checkboxes and cleared text really do get cleared.
        """
        if not self.partial:
            for name, field in self.fields.items():
                if field.read_only:
                    continue
                source = field.source or name
                if source in validated_data:
                    continue
                validated_data[source] = MemberProfile._meta.get_field(source).get_default()
        return super().update(instance, validated_data)


class AircraftAttachSerializer(serializers.Serializer):
    """``POST /me/profile/aircraft`` body."""

    aircraft_id = serializers.IntegerField()
