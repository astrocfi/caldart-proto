"""Serializers for member self-service.

Everything here is scoped to ``request.user``: the profile they may edit, the
membership terms and payments they may read, and the two public catalogs
(DARTs and plans) the join wizard needs before anyone has signed in.
"""

from __future__ import annotations

import re
from typing import Any, cast

from django.db import models, transaction
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.aircraft.api.serializers import AircraftSummarySerializer, VerificationSerializer
from apps.darts.api.serializers import DartRefSerializer
from apps.darts.models import (
    AIRPORT_IDENTIFIER_MESSAGE,
    AIRPORT_IDENTIFIER_RE,
    Dart,
    normalize_airport_identifier,
)
from apps.members.api.serializers import MembershipStatusSerializer
from apps.members.labels import NAME_FIELDS, changed_field_labels
from apps.members.models import (
    CALIFORNIA_COUNTIES,
    HAM_CALLSIGN_MESSAGE,
    HAM_CALLSIGN_RE,
    MAX_TOTAL_HOURS,
    RATING_VALUES,
    US_STATE_VALUES,
    MemberProfile,
    Membership,
    check_certificate_number,
    normalize_ham_callsign,
)
from apps.members.services import touch_profile
from apps.members.verification import VerificationState, clear_stale, item_state
from apps.payments.models import Payment, PaymentKind
from caldart import events
from caldart.casing import person_last_name, person_name
from caldart.messages import when_missing
from caldart.phone import PHONE_EXTENSION_RE, PHONE_RE, normalize_phone

#: Five digits, e.g. ``95035``.  The four-digit add-on is not collected: it is
#: not needed to reach anybody and it is one more thing to keep right.
POSTAL_RE = re.compile(r"^\d{5}$")

#: What a blank first or last name is refused with, wherever somebody's names are edited:
#: worded neutrally, since an administrator edits other people's names with them.
FIRST_NAME_MESSAGE = "Enter a first name."
LAST_NAME_MESSAGE = "Enter a last name."

#: What every phone field answers when it cannot be read as ten digits.
PHONE_MESSAGE = "Use a ten-digit number like 415-555-0100."

#: How long a typed number may be before it is refused on length alone: enough
#: for ``+1 (415) 555-0100`` and its spaces, and nowhere near a paragraph.
RAW_PHONE_LENGTH = 24


def airport_identifier(value: str) -> str:
    """An airport identifier as this system stores it: three characters, or blank.

    A blank value passes: every airport field is optional.  The ICAO spelling is
    accepted and trimmed, so ``KCRQ`` is stored as ``CRQ``; anything that is not then
    three letters or digits (``KSQL1``, ``PA-``) raises a ``ValidationError`` carrying
    ``AIRPORT_IDENTIFIER_MESSAGE``.
    """
    value = normalize_airport_identifier(value or "")
    if value and not AIRPORT_IDENTIFIER_RE.match(value):
        raise serializers.ValidationError(AIRPORT_IDENTIFIER_MESSAGE)
    return value


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


class ProfileVerificationSerializer(serializers.Serializer[dict[str, VerificationState]]):
    """The verified state of a person's three items, as a profile reports it."""

    certificate = VerificationSerializer()
    medical = VerificationSerializer()
    photo_id = VerificationSerializer()


class ProfileSerializer(serializers.ModelSerializer[MemberProfile]):
    """``GET/PUT/PATCH /me/profile``.

    ``first_name`` and ``last_name`` are the account's, read from and written to the
    ``User`` row: optional on ``PUT`` and ``PATCH`` alike (left out, they are left
    alone), never blank, and stored through :func:`caldart.casing.person_name` and
    :func:`caldart.casing.person_last_name`.
    ``dart`` reads as ``{id, name}`` and is written as ``dart_id``; ``aircraft``
    is read-only here and maintained through ``/me/profile/aircraft``.  The
    admin-only ``notes`` and ``how_heard`` fields are deliberately absent.
    ``verification`` is read-only: only the member check's verification endpoint
    verifies an item.
    """

    # The names live on the account, so a PUT that leaves them out does not reset
    # them the way it resets a profile field; trimming makes a blank of spaces only.
    # The messages are neutral because an administrator edits someone else's names here.
    first_name = serializers.CharField(
        source="user.first_name",
        max_length=150,
        required=False,
        error_messages=when_missing(FIRST_NAME_MESSAGE),
    )
    last_name = serializers.CharField(
        source="user.last_name",
        max_length=150,
        required=False,
        error_messages=when_missing(LAST_NAME_MESSAGE),
    )

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

    # Every phone number is optional, the member's own included: an email address is how
    # CalDART reaches a member.
    #
    # The three phone fields take a longer string than the column holds, because
    # what arrives may carry a country code, spaces and brackets.  What is stored
    # is always the canonical twelve characters, and a number too long to be one
    # is answered with `PHONE_MESSAGE` rather than a column-width complaint.
    phone = serializers.CharField(max_length=RAW_PHONE_LENGTH, required=False, allow_blank=True)
    phone_alt = serializers.CharField(max_length=RAW_PHONE_LENGTH, required=False, allow_blank=True)
    emergency_contact_phone = serializers.CharField(
        max_length=RAW_PHONE_LENGTH, required=False, allow_blank=True
    )
    # Wider than the column, so a pasted ICAO identifier is answered with the
    # rule rather than with a complaint about length.
    home_airport_identifier = serializers.CharField(max_length=8, required=False, allow_blank=True)
    secondary_airport_identifier = serializers.CharField(
        max_length=8, required=False, allow_blank=True
    )
    state = serializers.ChoiceField(choices=US_STATE_VALUES)
    # Wider than the column, so a callsign typed with spaces is answered with the
    # rule rather than with a complaint about length.
    ham_callsign = serializers.CharField(max_length=12, required=False, allow_blank=True)
    # Declared, with its rule in validate_certificate_number, so the schema reads it as
    # a plain string rather than a pattern or a blank.
    certificate_number = serializers.CharField(max_length=40, required=False, allow_blank=True)
    county = serializers.ChoiceField(choices=CALIFORNIA_COUNTIES, required=False, allow_blank=True)
    total_hours = serializers.IntegerField(
        min_value=0, max_value=MAX_TOTAL_HOURS, required=False, allow_null=True
    )
    ratings = serializers.ListField(
        child=serializers.ChoiceField(choices=RATING_VALUES),
        required=False,
        allow_empty=True,
    )
    verification = serializers.SerializerMethodField()

    class Meta:
        model = MemberProfile
        fields = [
            # the account's names
            *NAME_FIELDS,
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
            "ham_callsign",
            "member_since",
            # aviation
            "home_airport_identifier",
            "secondary_airport_identifier",
            "dart",
            "dart_id",
            "air_care_alliance_number",
            "pilot_certificate_type",
            "certificate_number",
            "ratings",
            "medical_type",
            "medical_expiration",
            "medical_is_current",
            "flight_review_date",
            "total_hours",
            "photo_id_type",
            "verification",
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

    @extend_schema_field(ProfileVerificationSerializer)
    def get_verification(self, obj: MemberProfile) -> dict[str, VerificationState]:
        """The verified state of ``obj``'s pilot certificate, medical, and photo ID."""
        states = {slug: item_state(obj, slug) for slug in ("certificate", "medical", "photo_id")}
        return cast("dict[str, VerificationState]", ProfileVerificationSerializer(states).data)

    # -- field-level rules -------------------------------------------------
    def validate_first_name(self, value: str) -> str:
        """The first name as it will be stored, by :func:`caldart.casing.person_name`."""
        return person_name(value)

    def validate_last_name(self, value: str) -> str:
        """The last name as stored, by :func:`caldart.casing.person_last_name`."""
        return person_last_name(value)

    def validate_certificate_number(self, value: str) -> str:
        """The certificate number, refused unless it is blank or seven digits.

        Anything else is refused with "Enter the 7 digits of the pilot certificate
        number."
        """
        return check_certificate_number(value)

    def validate_ham_callsign(self, value: str) -> str:
        """The callsign upper case without spaces, refused unless it is in US format.

        A blank value passes: the field is optional.  Anything else is refused with
        "Enter a US amateur radio callsign, such as W6ABC."
        """
        value = normalize_ham_callsign(value)
        if value and not HAM_CALLSIGN_RE.match(value):
            raise serializers.ValidationError(HAM_CALLSIGN_MESSAGE)
        return value

    def validate_phone(self, value: str) -> str:
        """The member's own number, optional, in canonical form."""
        return self._phone(value, required=False)

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
        """The home airport as this system stores it, by :func:`airport_identifier`."""
        return airport_identifier(value)

    def validate_secondary_airport_identifier(self, value: str) -> str:
        """The secondary airport, by the same rule: :func:`airport_identifier`."""
        return airport_identifier(value)

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

    # -- write -------------------------------------------------------------
    @transaction.atomic
    def update(self, instance: MemberProfile, validated_data: dict[str, Any]) -> MemberProfile:
        """``PUT`` really replaces: anything left out goes back to its default.

        DRF's own behavior is to ignore absent optional fields even on a full
        update, which would make ``PUT`` and ``PATCH`` indistinguishable.  The
        API contract says one is a full update and the other partial,
        so unchecked checkboxes and cleared text really do get cleared.

        The account's names are the exception: they are written to the ``User`` row
        when the request carries them and left alone when it does not.

        Raises ``TypeError`` if a writable field names something other than a
        concrete model field, since only a concrete field carries the default
        the reset needs.  Stamps ``profile_updated_at`` once the write lands.

        The write that turns an incomplete profile complete
        (``MemberProfile.is_complete``) is the join wizard's profile step finishing,
        so it raises the ``signed_up`` event with the account and the profile's
        ``dart`` (``None`` when none was chosen), and no ``profile_changed``.  Any
        other write that changes a field's value raises ``profile_changed`` with the
        account, the labels of those fields
        (:func:`apps.members.labels.changed_field_labels`: names first) and
        ``actor=None``, the
        member having edited their own profile.  A write that moves nothing raises
        nothing, and neither does one to an incomplete profile that leaves it
        incomplete: the join is under way.

        A write that changes a field a verified item covers clears that item in the
        same save (:func:`apps.members.verification.clear_stale`); the member's own
        edit raises no ``verification_changed``, only the ``profile_changed`` above.

        Locks the profile row with ``select_for_update`` before reading its stored
        values, so a save racing this one -- a verifier stamping an item on the same
        record -- waits for this transaction to finish rather than being read here as
        though it had not happened.
        """
        instance = MemberProfile.objects.select_for_update().get(pk=instance.pk)
        names: dict[str, str] = validated_data.pop("user", {})
        if not self.partial:
            for name, field in self.fields.items():
                if field.read_only or field.source_attrs[0] == "user":
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
        was_complete = instance.is_complete
        changed = changed_field_labels(instance.user, names)
        changed += changed_field_labels(instance, validated_data)
        clear_stale(instance, validated_data)
        instance = super().update(instance, validated_data)
        if len(names) > 0:
            for account_field, value in names.items():
                setattr(instance.user, account_field, value)
            instance.user.save(update_fields=[*names, "updated_at"])
        touch_profile(instance)
        if not was_complete and instance.is_complete:
            events.emit("signed_up", user=instance.user, dart=instance.dart)
        elif was_complete and len(changed) > 0:
            events.emit("profile_changed", user=instance.user, fields=changed, actor=None)
        return instance


class AircraftAttachSerializer(serializers.Serializer[Any]):
    """``POST /me/profile/aircraft`` body."""

    aircraft_id = serializers.IntegerField()


class AttachedAircraftSerializer(serializers.Serializer[dict[str, Any]]):
    """``POST /me/profile/aircraft`` response: the aircraft the profile now lists."""

    aircraft = AircraftSummarySerializer(many=True, read_only=True)


class BecomeFriendSerializer(serializers.Serializer[None]):
    """``POST /me/kind/friend``: whether a renewal's contribution carries on.

    ``keep_contribution`` is needed only when the member's automatic renewal takes a
    contribution: true keeps it as a yearly recurring donation, false lets it stop.
    """

    keep_contribution = serializers.BooleanField(required=False)
