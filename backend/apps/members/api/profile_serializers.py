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
from apps.darts.api.serializers import DartRefSerializer
from apps.darts.models import (
    AIRPORT_IDENTIFIER_MESSAGE,
    AIRPORT_IDENTIFIER_RE,
    Dart,
    normalize_airport_identifier,
)
from apps.members.api.serializers import MembershipStatusSerializer
from apps.members.models import (
    CALIFORNIA_COUNTIES,
    MAX_TOTAL_HOURS,
    RATING_VALUES,
    US_STATE_VALUES,
    MedicalType,
    MemberProfile,
    Membership,
    PilotCertificateType,
)
from apps.payments.models import Payment, PaymentKind
from caldart.phone import PHONE_EXTENSION_RE, PHONE_RE, normalize_phone

#: Five digits, e.g. ``95035``.  The four-digit add-on is not collected: it is
#: not needed to reach anybody and it is one more thing to keep right.
POSTAL_RE = re.compile(r"^\d{5}$")

#: What every phone field answers when it cannot be read as ten digits.
PHONE_MESSAGE = "Use a ten-digit number like 415-555-0100."

#: How long a typed number may be before it is refused on length alone: enough
#: for ``+1 (415) 555-0100`` and its spaces, and nowhere near a paragraph.
RAW_PHONE_LENGTH = 24


class MembershipTermSerializer(serializers.ModelSerializer[Membership]):
    """One row of the membership history in ``GET /me/membership``."""

    plan = serializers.CharField(source="plan.name", read_only=True)

    class Meta:
        model = Membership
        fields = ["id", "plan", "starts_on", "ends_on", "status", "source"]
        read_only_fields = fields


class MembershipDetailSerializer(MembershipStatusSerializer):
    """``GET /me/membership`` -- the status summary plus every term, newest first."""

    history = MembershipTermSerializer(many=True, read_only=True)


class PaymentTermSerializer(serializers.ModelSerializer[Membership]):
    """The membership term one payment bought, as its own payment row names it."""

    class Meta:
        model = Membership
        fields = ["id", "starts_on", "ends_on"]
        read_only_fields = fields


class PaymentSummarySerializer(serializers.ModelSerializer[Payment]):
    """The payment row a member sees for themselves on ``GET /me/payments``.

    It carries everything the payments screen draws, so the screen needs no
    second call per row: what the payment bought and what it cost, how much of
    it has come back, when CalDART's receipt was emailed, and the term it
    activated.
    """

    plan = serializers.SerializerMethodField()
    kind = serializers.ChoiceField(choices=PaymentKind.choices, read_only=True)
    paid_on = serializers.DateField(read_only=True, allow_null=True)
    refunded_cents = serializers.IntegerField(read_only=True)
    membership = PaymentTermSerializer(read_only=True, allow_null=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "plan",
            "kind",
            "amount_cents",
            "plan_amount_cents",
            "contribution_cents",
            "refunded_cents",
            "provider",
            "wallet",
            "status",
            "paid_on",
            "completed_at",
            "receipt_sent_at",
            "membership",
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

    dart = DartRefSerializer(read_only=True, allow_null=True)
    dart_id = serializers.PrimaryKeyRelatedField(
        source="dart",
        queryset=Dart.objects.filter(is_active=True),
        required=False,
        allow_null=True,
        write_only=True,
    )
    aircraft = AircraftSummarySerializer(many=True, read_only=True)
    medical_is_current = serializers.BooleanField(read_only=True)
    # Stamped when the first term is created and never moved, so it is reported
    # rather than edited here; an administrator corrects it on the member record.
    member_since = serializers.DateField(read_only=True, allow_null=True)

    # A member has to be reachable: required on PUT, never blank on PATCH.
    #
    # The three phone fields take a longer string than the column holds, because
    # what arrives may carry a country code, spaces and brackets.  What is stored
    # is always the canonical twelve characters, and a number too long to be one
    # is answered with `PHONE_MESSAGE` rather than a column-width complaint.
    phone = serializers.CharField(max_length=RAW_PHONE_LENGTH)
    phone_alt = serializers.CharField(max_length=RAW_PHONE_LENGTH, required=False, allow_blank=True)
    emergency_contact_phone = serializers.CharField(
        max_length=RAW_PHONE_LENGTH, required=False, allow_blank=True
    )
    # Wider than the column, so a pasted ICAO identifier is answered with the
    # rule rather than with a complaint about length.
    home_airport_identifier = serializers.CharField(max_length=8, required=False, allow_blank=True)
    state = serializers.ChoiceField(choices=US_STATE_VALUES)
    county = serializers.ChoiceField(choices=CALIFORNIA_COUNTIES, required=False, allow_blank=True)
    total_hours = serializers.IntegerField(
        min_value=0, max_value=MAX_TOTAL_HOURS, required=False, allow_null=True
    )
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
            "phone_extension",
            "phone_alt_extension",
            "emergency_contact_name",
            "emergency_contact_phone",
            "emergency_contact_phone_extension",
            "member_since",
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
            "flies_rented_aircraft",
            # volunteer interests
            "vol_mission_pilot",
            "vol_ground_team",
            "vol_exercise_training",
            "vol_member_support",
            "vol_fundraising",
            "vol_social_media",
            "vol_newsletter",
        ]

    # -- field-level rules -------------------------------------------------
    def validate_phone(self, value: str) -> str:
        """The member's own number, in canonical form and never blank."""
        return self._phone(value, required=True)

    def validate_phone_alt(self, value: str) -> str:
        """A second number, optional, in canonical form."""
        return self._phone(value, required=False)

    def validate_emergency_contact_phone(self, value: str) -> str:
        """The emergency contact's number, optional, in canonical form."""
        return self._phone(value, required=False)

    def _phone(self, value: str, *, required: bool) -> str:
        """``value`` as ``XXX-XXX-XXXX``, refusing anything that is not ten digits.

        A blank value passes when the field is optional and is refused with
        ``PHONE_MESSAGE`` when it is not.  ``+1``, spaces, dots and parentheses
        are all accepted on the way in and none of them are stored.
        """
        normalized = normalize_phone(value)
        if not normalized:
            if required:
                raise serializers.ValidationError(PHONE_MESSAGE)
            return ""
        if not PHONE_RE.match(normalized):
            raise serializers.ValidationError(PHONE_MESSAGE)
        return normalized

    def validate_phone_extension(self, value: str) -> str:
        """The member's own extension, up to six digits."""
        return self._extension(value)

    def validate_phone_alt_extension(self, value: str) -> str:
        """The extension on the second number, up to six digits."""
        return self._extension(value)

    def validate_emergency_contact_phone_extension(self, value: str) -> str:
        """The extension on the emergency contact's number, up to six digits."""
        return self._extension(value)

    def _extension(self, value: str) -> str:
        """``value`` as up to six digits, and nothing else.

        A blank value passes: every extension is optional.  Anything else is
        refused with "An extension is digits only, for example 4021."  The
        extension is its own field so nobody appends it to the number and
        breaks the format every other screen relies on.
        """
        value = (value or "").strip()
        if value and not PHONE_EXTENSION_RE.match(value):
            raise serializers.ValidationError("An extension is digits only, for example 4021.")
        return value

    def validate_home_airport_identifier(self, value: str) -> str:
        """The home airport as this system stores it: three characters.

        A blank value passes: the field is optional.  The ICAO spelling is
        accepted and trimmed, so ``KCRQ`` is stored as ``CRQ``; anything that
        is not then three letters or digits is refused with
        ``AIRPORT_IDENTIFIER_MESSAGE``.
        """
        value = normalize_airport_identifier(value or "")
        if value and not AIRPORT_IDENTIFIER_RE.match(value):
            raise serializers.ValidationError(AIRPORT_IDENTIFIER_MESSAGE)
        return value

    def validate_postal_code(self, value: str) -> str:
        """Trim the ZIP code, rejecting anything but five digits.

        A blank value passes: the field is optional.  Anything else is refused
        with "Use a five-digit ZIP code like 95035."
        """
        value = (value or "").strip()
        if value and not POSTAL_RE.match(value):
            raise serializers.ValidationError("Use a five-digit ZIP code like 95035.")
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
        if (
            medical_type
            and medical_type != MedicalType.NONE
            and not self._merged(attrs, "medical_expiration")
        ):
            errors["medical_expiration"] = "Give the expiration date of your medical certificate."

        certificate = self._merged(attrs, "pilot_certificate_type")
        if (
            certificate
            and certificate != PilotCertificateType.NONE
            and not self._merged_text(attrs, "certificate_number").strip()
        ):
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


class AttachedAircraftSerializer(serializers.Serializer[dict[str, Any]]):
    """``POST /me/profile/aircraft`` response: the aircraft the profile now lists."""

    aircraft = AircraftSummarySerializer(many=True, read_only=True)
