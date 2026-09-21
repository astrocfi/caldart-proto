"""Serializers for member self-service.

Everything here is scoped to ``request.user``: the profile they may edit, the
membership terms and payments they may read, and the two public catalogs
(DARTs and plans) the join wizard needs before anyone has signed in.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from django.db import models
from rest_framework import serializers

from apps.aircraft.api.serializers import AircraftSummarySerializer
from apps.members.models import (
    RATING_VALUES,
    Dart,
    MedicalType,
    MemberProfile,
    Membership,
    PilotCertificateType,
)
from apps.payments.models import Payment

#: Two letters, e.g. ``CA``.
STATE_RE = re.compile(r"^[A-Za-z]{2}$")

#: ``12345`` or ``12345-6789``.
POSTAL_RE = re.compile(r"^\d{5}(-\d{4})?$")


class DartSerializer(serializers.ModelSerializer[Dart]):
    """``GET /darts`` — the public DART catalog."""

    class Meta:
        model = Dart
        fields = ["id", "name", "airport_identifier", "city"]
        read_only_fields = fields


class DartRefSerializer(serializers.ModelSerializer[Dart]):
    """The ``dart: {id, name}`` stub nested in a profile."""

    class Meta:
        model = Dart
        fields = ["id", "name"]
        read_only_fields = fields


class MembershipTermSerializer(serializers.ModelSerializer[Membership]):
    """One row of the membership history in ``GET /me/membership``."""

    plan = serializers.CharField(source="plan.name", read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "plan", "starts_on", "ends_on", "status", "source"]
        read_only_fields = fields


class PaymentSummarySerializer(serializers.ModelSerializer[Payment]):
    """The trimmed payment row a member sees for themselves."""

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

    def get_plan(self, obj: Payment) -> str | None:
        """The plan name behind the payment, or ``None`` for a bare contribution."""
        return obj.plan.name if obj.plan is not None else None


class ProfileSerializer(serializers.ModelSerializer[MemberProfile]):
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
        """Uppercase the state, rejecting anything but two letters.

        A blank value passes: the field is optional.  Anything else that is not
        exactly two letters is refused with "Use the two-letter state code, for
        example CA."
        """
        value = (value or "").strip().upper()
        if value and not STATE_RE.match(value):
            raise serializers.ValidationError("Use the two-letter state code, for example CA.")
        return value

    def validate_postal_code(self, value: str) -> str:
        """Trim the ZIP code, rejecting anything but ``12345`` or ``12345-6789``.

        A blank value passes: the field is optional.  Anything else is refused
        with "Use a ZIP code like 95035 or 95035-1234."
        """
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
    def _merged(self, attrs: dict[str, Any], name: str) -> str | date | None:
        """The value a PATCH would leave in place, so rules see the whole row.

        ``name`` is one of the choice or date fields the rules below read, and
        the answer is the incoming value when the request carries the field and
        the stored one otherwise, or ``None`` when neither has it.
        """
        merged: str | date | None = (
            attrs[name] if name in attrs else getattr(self.instance, name, None)
        )
        return merged

    def _merged_text(self, attrs: dict[str, Any], name: str) -> str:
        """:meth:`_merged` for a text field, with anything unset read as blank."""
        value = self._merged(attrs, name)
        return value if isinstance(value, str) else ""

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Check the two rules that need more than one field, and return ``attrs``.

        A medical class other than ``none`` needs an expiration date, refused
        against ``medical_expiration`` with "Give the expiration date of your
        medical certificate."  A pilot certificate other than ``none`` needs a
        number, refused against ``certificate_number`` with "Give your pilot
        certificate number."  Both are judged on the row a PATCH would leave
        behind, not on the fields this request happens to carry, and both
        complaints are raised together when both apply.
        """
        errors: dict[str, str] = {}

        medical_type = self._merged(attrs, "medical_type")
        if medical_type and medical_type != MedicalType.NONE:
            if not self._merged(attrs, "medical_expiration"):
                errors["medical_expiration"] = (
                    "Give the expiration date of your medical certificate."
                )

        certificate = self._merged(attrs, "pilot_certificate_type")
        if certificate and certificate != PilotCertificateType.NONE:
            if not self._merged_text(attrs, "certificate_number").strip():
                errors["certificate_number"] = "Give your pilot certificate number."

        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    # -- write -------------------------------------------------------------
    def update(self, instance: MemberProfile, validated_data: dict[str, Any]) -> MemberProfile:
        """``PUT`` really replaces: anything left out goes back to its default.

        DRF's own behavior is to ignore absent optional fields even on a full
        update, which would make ``PUT`` and ``PATCH`` indistinguishable.  The
        API contract says one is a full update and the other partial,
        so unticked checkboxes and cleared text really do get cleared.

        Raises ``TypeError`` if a writable field names something other than a
        concrete model field, since only a concrete field carries the default
        the reset needs.
        """
        if not self.partial:
            for name, field in self.fields.items():
                if field.read_only:
                    continue
                source = field.source or name
                if source in validated_data:
                    continue
                # ``get_field`` also answers reverse relations and generic foreign
                # keys, which carry no default. None of the writable fields above
                # is one, so such an answer means the field list and the model have
                # drifted apart, and the reset would silently skip a field.
                model_field = MemberProfile._meta.get_field(source)
                if not isinstance(model_field, models.Field):
                    raise TypeError(
                        f"MemberProfile.{source} is not a concrete field and has no "
                        f"default to reset {name!r} to."
                    )
                validated_data[source] = model_field.get_default()
        return super().update(instance, validated_data)


class AircraftAttachSerializer(serializers.Serializer[Any]):
    """``POST /me/profile/aircraft`` body."""

    aircraft_id = serializers.IntegerField()
