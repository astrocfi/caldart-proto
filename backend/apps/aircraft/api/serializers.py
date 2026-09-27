"""Serializers for the aircraft register and the leader check."""

from __future__ import annotations

from datetime import date
from typing import Any, cast

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from apps.accounts.models import User
from apps.aircraft.models import (
    N_NUMBER_MESSAGE,
    N_NUMBER_RE,
    Aircraft,
    AircraftChange,
    AircraftChangeKind,
    AircraftType,
    normalize_n_number,
)
from apps.aircraft.verification import INSURANCE_FIELDS
from apps.members.models import (
    RATING_VALUES,
    IfrRated,
    MedicalType,
    MembershipState,
    PhotoIdType,
    PilotCertificateType,
)
from apps.members.verification import (
    ITEM_CHOICES,
    ITEM_LABELS,
    VerificationState,
    document_errors,
    verification_state,
)

NEGATIVE_MONEY_MESSAGE = "Enter an amount of $0 or more."

#: What a write without a usable aircraft type is answered with.
TYPE_MESSAGE = "Pick the aircraft type from the list."


def _actor_payload(user: User | None) -> dict[str, Any] | None:
    """``{"id": ..., "name": ...}`` for ``user``, or ``None`` when nobody is recorded."""
    if user is None:
        return None
    return {"id": user.pk, "name": user.display_name}


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


# --------------------------------------------------------------------------
# Verification
# --------------------------------------------------------------------------
class VerificationSerializer(serializers.Serializer[VerificationState]):
    """One verified item's state: whether it is verified, by whom, and when.

    ``verified_by`` is the verifier's display name and ``verified_at`` the moment; both
    are ``null`` while the item is unverified, and ``verified_by`` is ``null`` too once
    the verifying account is deleted.
    """

    verified = serializers.BooleanField()
    verified_by = serializers.CharField(allow_null=True)
    verified_at = serializers.DateTimeField(allow_null=True)


class AircraftTypeSerializer(serializers.ModelSerializer[AircraftType]):
    """One aircraft type: its display make and model, seats, engines, and whether custom.

    ``seats`` and ``engines`` are null when the registry does not say; ``is_custom`` is
    true for a type an account administrator added by hand.
    """

    class Meta:
        model = AircraftType
        fields = ["id", "make", "model", "seats", "engines", "is_custom"]
        read_only_fields = fields


class AircraftSummarySerializer(serializers.ModelSerializer[Aircraft]):
    """The short form embedded in profiles, leader cards and pickers.

    ``make`` and ``model`` are the display names of the aircraft's ``type``.
    """

    make = serializers.CharField(read_only=True)
    model = serializers.CharField(read_only=True)
    type = AircraftTypeSerializer(read_only=True)
    insurance_is_current = serializers.BooleanField(read_only=True)
    insurance_summary = serializers.CharField(read_only=True)
    insurance_verified = serializers.BooleanField(source="insurance_is_verified", read_only=True)

    class Meta:
        model = Aircraft
        fields = [
            "id",
            "n_number",
            "make",
            "model",
            "type",
            "insurance_is_current",
            "insurance_expiration",
            "insurance_summary",
            "insurance_verified",
        ]
        read_only_fields = fields


class AircraftSerializer(serializers.ModelSerializer[Aircraft]):
    """The full record.  ``created_by`` is set by the view.

    The aircraft type is written as ``type_id``, the id of an ``AircraftType`` (required
    on create, refused with :data:`TYPE_MESSAGE` when missing, null, or unknown), and read
    back as the nested ``type`` with its display ``make`` and ``model`` beside it; neither
    ``make`` nor ``model`` is written.
    """

    n_number = NNumberField(
        max_length=12,
        validators=[
            UniqueValidator(
                queryset=Aircraft.objects.all(),
                message="An aircraft with this N-number is already on file.",
            )
        ],
    )
    make = serializers.CharField(read_only=True)
    model = serializers.CharField(read_only=True)
    type = AircraftTypeSerializer(read_only=True)
    type_id = serializers.PrimaryKeyRelatedField(
        source="type",
        queryset=AircraftType.objects.all(),
        write_only=True,
        error_messages={
            "required": TYPE_MESSAGE,
            "null": TYPE_MESSAGE,
            "does_not_exist": TYPE_MESSAGE,
            "incorrect_type": TYPE_MESSAGE,
        },
    )
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
    insurance_verification = serializers.SerializerMethodField()

    class Meta:
        model = Aircraft
        fields = [
            "id",
            "n_number",
            "make",
            "model",
            "type",
            "type_id",
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
            "insurance_verification",
            "notes",
            "created_by",
            "updated_at",
            "is_active",
        ]
        read_only_fields = [
            "id",
            "make",
            "model",
            "type",
            "created_by",
            "updated_at",
            "insurance_is_current",
            "insurance_summary",
        ]

    @extend_schema_field(VerificationSerializer)
    def get_insurance_verification(self, obj: Aircraft) -> VerificationState:
        """Whether ``obj``'s insurance is verified, by whom, and when."""
        state = verification_state(obj.insurance_verified_at, obj.insurance_verified_by)
        return cast("VerificationState", VerificationSerializer(state).data)


class InsuranceVerificationSerializer(AircraftSerializer):
    """``PUT /leader/aircraft/{id}/verification``: the insurance fields and the verdict.

    The six insurance fields are optional and validated as the register validates them
    (money in integer cents, ``>= 0``); one given is written, one omitted is left as it
    is.  ``verified`` is required: whether the insurance ends verified.  No other
    register field is accepted.
    """

    verified = serializers.BooleanField()

    class Meta(AircraftSerializer.Meta):
        fields = [*INSURANCE_FIELDS, "verified"]
        read_only_fields: list[str] = []


class AircraftPilotSerializer(serializers.Serializer[Any]):
    """A member who lists this aircraft as one they commonly fly."""

    user_id = serializers.IntegerField()
    name = serializers.CharField()
    email = serializers.EmailField()
    membership_status = serializers.ChoiceField(choices=MembershipState.choices)
    medical_is_current = serializers.BooleanField()


class AircraftActorSerializer(serializers.Serializer[Any]):
    """The account behind a write: its id and the name to print beside a date."""

    id = serializers.IntegerField()
    name = serializers.CharField()


class AircraftChangeSerializer(serializers.ModelSerializer[AircraftChange]):
    """One row of ``GET /aircraft/{id}/changes``."""

    changed_by = serializers.SerializerMethodField()
    kind = serializers.ChoiceField(choices=AircraftChangeKind.choices, read_only=True)
    # DRF's metaclass moves every declared field out of the class namespace into
    # ``_declared_fields``, so naming one ``fields`` never shadows ``Serializer.fields``
    # at runtime; the stubs type the class attribute as the base property.
    fields = serializers.ListField(  # type: ignore[assignment]
        child=serializers.CharField(), read_only=True
    )

    class Meta:
        model = AircraftChange
        fields = ["id", "changed_at", "changed_by", "kind", "fields"]
        read_only_fields = fields

    @extend_schema_field(AircraftActorSerializer(allow_null=True))
    def get_changed_by(self, obj: AircraftChange) -> dict[str, Any] | None:
        """The id and display name of the account that made ``obj``, or ``None``."""
        return _actor_payload(obj.changed_by)


class AircraftDetailSerializer(AircraftSerializer):
    """The record plus the members who fly it, for admin and leader screens."""

    pilots = serializers.SerializerMethodField()
    updated_by = serializers.SerializerMethodField()

    class Meta(AircraftSerializer.Meta):
        fields = [*AircraftSerializer.Meta.fields, "updated_by", "pilots"]

    @extend_schema_field(AircraftActorSerializer(allow_null=True))
    def get_updated_by(self, obj: Aircraft) -> dict[str, Any] | None:
        """Return the id and display name of the account that last wrote ``obj``."""
        return _actor_payload(obj.updated_by)

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
class LeaderMembershipSerializer(serializers.Serializer[Any]):
    """The membership fields of the leader status card.

    ``status`` is the computed membership state, ``friend`` among them: a friend of
    CalDART pays no dues, so ``expires_on`` and ``plan`` are null and the card's
    membership go/no-go is false, whatever terms the friend once held.
    """

    status = serializers.ChoiceField(choices=MembershipState.choices)
    expires_on = serializers.DateField(allow_null=True)
    plan = serializers.CharField(allow_null=True)


class LeaderCertificateSerializer(serializers.Serializer[Any]):
    """The pilot certificate fields of the status card, and their verification."""

    type = serializers.ChoiceField(choices=PilotCertificateType.choices)
    number = serializers.CharField(allow_blank=True)
    ifr_rated = serializers.ChoiceField(choices=IfrRated.choices)
    ratings = serializers.ListField(child=serializers.ChoiceField(choices=RATING_VALUES))
    verification = VerificationSerializer()


class LeaderMedicalSerializer(serializers.Serializer[Any]):
    """The medical certificate fields of the status card, and their verification."""

    type = serializers.ChoiceField(choices=MedicalType.choices)
    expiration = serializers.DateField(allow_null=True)
    is_current = serializers.BooleanField()
    verification = VerificationSerializer()


class LeaderPhotoIdSerializer(serializers.Serializer[Any]):
    """The kind of photo ID on file, and its verification; nothing else is recorded."""

    type = serializers.ChoiceField(choices=PhotoIdType.choices)
    verification = VerificationSerializer()


class LeaderGoNoGoSerializer(serializers.Serializer[Any]):
    """The go/no-go booleans, so a leader sees why, not just whether.

    ``verified`` is true when the pilot certificate, the medical, and the photo ID are
    all verified.
    """

    membership = serializers.BooleanField()
    medical = serializers.BooleanField()
    verified = serializers.BooleanField()


class LeaderSearchResultSerializer(serializers.Serializer[Any]):
    """One row of a leader's member search, carrying its own go/no-go.

    The two booleans are the same ones the status card shows, so the list
    answers "may this member fly?" without a second request.
    """

    user_id = serializers.IntegerField()
    name = serializers.CharField()
    email = serializers.EmailField()
    dart = serializers.CharField(allow_null=True)
    membership_status = serializers.ChoiceField(choices=MembershipState.choices)
    go_no_go = LeaderGoNoGoSerializer()


class LeaderStatusSerializer(serializers.Serializer[Any]):
    """The status card a DART leader reads before a flight."""

    name = serializers.CharField()
    email = serializers.EmailField()
    phone = serializers.CharField(allow_blank=True)
    dart = serializers.CharField(allow_null=True)
    membership = LeaderMembershipSerializer()
    certificate = LeaderCertificateSerializer()
    medical = LeaderMedicalSerializer()
    photo_id = LeaderPhotoIdSerializer()
    is_verifier = serializers.BooleanField()
    aircraft = AircraftSummarySerializer(many=True)
    go_no_go = LeaderGoNoGoSerializer()


@extend_schema_field(serializers.ChoiceField(choices=ITEM_CHOICES))
class ItemSlugField(serializers.CharField):
    """One item slug.  The schema lists the catalog; the serializer refuses any other."""


class MemberVerificationSerializer(serializers.Serializer[Any]):
    """``PUT /leader/members/{user_id}/verification``: the covered fields and the items.

    Each field is optional: one given is written, one omitted is left as it is.
    ``verified`` is required and lists the slugs of the items that end verified; an
    item left out ends unverified, and a slug outside the catalog is refused with
    ``Unknown item '<slug>'.``  The profile form's two rules hold on the record the
    write would leave (see :func:`apps.members.verification.document_errors`), judged
    against the profile passed in the ``profile`` context key (``None`` for an account
    with no profile).
    """

    pilot_certificate_type = serializers.ChoiceField(
        choices=PilotCertificateType.choices, required=False
    )
    certificate_number = serializers.CharField(max_length=40, required=False, allow_blank=True)
    medical_type = serializers.ChoiceField(choices=MedicalType.choices, required=False)
    medical_expiration = serializers.DateField(required=False, allow_null=True)
    photo_id_type = serializers.ChoiceField(choices=PhotoIdType.choices, required=False)
    verified = serializers.ListField(child=ItemSlugField(), allow_empty=True)

    def validate_verified(self, value: list[str]) -> list[str]:
        """Refuse a slug that names no item; return the slugs without repeats."""
        for slug in value:
            if slug not in ITEM_LABELS:
                raise serializers.ValidationError(f"Unknown item '{slug}'.")
        return list(dict.fromkeys(value))

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Apply the profile form's two document rules to the merged record."""
        profile = self.context.get("profile")

        def merged(name: str, default: object) -> object:
            if name in attrs:
                return attrs[name]
            return getattr(profile, name) if profile is not None else default

        expiration = merged("medical_expiration", None)
        errors = document_errors(
            certificate_type=str(merged("pilot_certificate_type", PilotCertificateType.NONE)),
            certificate_number=str(merged("certificate_number", "")),
            medical_type=str(merged("medical_type", MedicalType.NONE)),
            medical_expiration=expiration if isinstance(expiration, date) else None,
        )
        if len(errors) > 0:
            raise serializers.ValidationError(errors)
        return attrs


class VerifierGrantSerializer(serializers.Serializer[Any]):
    """``PUT /leader/members/{user_id}/verifier``: whether the member holds the role."""

    verifier = serializers.BooleanField()
