"""Serializers for the aircraft register and the leader check."""

from __future__ import annotations

from typing import Any, cast
from uuid import uuid4

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from apps.accounts.models import User
from apps.aircraft.coverage import CoverageRule, current_rule
from apps.aircraft.models import (
    N_NUMBER_MESSAGE,
    N_NUMBER_RE,
    Aircraft,
    AircraftCategory,
    AircraftChange,
    AircraftChangeKind,
    AircraftCoveragePolicy,
    AircraftType,
    Airworthiness,
    RegistrantType,
    Registration,
    RegistrationStatus,
    RegistryImport,
    normalize_n_number,
)
from apps.aircraft.naming import display_make, display_model
from apps.aircraft.verification import INSURANCE_FIELDS
from apps.members.models import (
    RATING_VALUES,
    MedicalType,
    MembershipState,
    PhotoIdType,
    PilotCertificateType,
    check_certificate_number,
)
from apps.members.verification import (
    ITEM_CHOICES,
    ITEM_LABELS,
    VerificationState,
    verification_state,
)

NEGATIVE_MONEY_MESSAGE = "Enter an amount of $0 or more."

#: What a write without a usable aircraft type is answered with.
TYPE_MESSAGE = "Pick the aircraft type from the list."

#: The attribute the root serializer keeps one response's coverage rule under, so a
#: page of aircraft reads the policy once rather than once a row.
COVERAGE_RULE_ATTRIBUTE = "_coverage_rule"

#: The longest coverage note the policy takes.
COVERAGE_NOTE_MAX_LENGTH = 1000


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


def _read_only_choice(choices: list[tuple[str, str]]) -> serializers.ChoiceField:
    """A read-only choice that may be blank, as the schema must describe it."""
    return serializers.ChoiceField(choices=choices, allow_blank=True, read_only=True)


class CoverageSerializer(serializers.Serializer[Any]):
    """Whether the coverage policy excludes an aircraft, and what the check says of it.

    ``reason`` is blank when there is nothing to say, ``Category not recorded`` for an
    aircraft with no category the policy does not otherwise exclude, and ``Not covered:
    <what> are excluded by <organization>'s policy`` for an excluded one.
    """

    excluded = serializers.BooleanField()
    reason = serializers.CharField(allow_blank=True)


def coverage_payload(
    serializer: serializers.Field[Any, Any, Any, Any], aircraft: Aircraft
) -> dict[str, Any]:
    """``aircraft``'s :class:`CoverageSerializer` payload, judged by the stored policy.

    The rule is read on the first call and kept on ``serializer``'s root serializer, so
    every later call under the same root (the rows of one page, the aircraft on one
    status card) reuses it.
    """
    root = serializer.root
    rule = getattr(root, COVERAGE_RULE_ATTRIBUTE, None)
    if not isinstance(rule, CoverageRule):
        rule = current_rule()
        setattr(root, COVERAGE_RULE_ATTRIBUTE, rule)
    judged = rule.judge(category=aircraft.category, airworthiness=aircraft.airworthiness)
    return {"excluded": judged.excluded, "reason": judged.reason}


class AircraftTypeSerializer(serializers.ModelSerializer[AircraftType]):
    """One aircraft type: display make and model, seats, engines, category, custom.

    ``seats`` and ``engines`` are null when the registry does not say, and ``category``
    is blank when it does not (always, for a hand-added type); ``is_custom`` is true
    for a type an account administrator added by hand.
    """

    category = _read_only_choice(AircraftCategory.choices)

    class Meta:
        model = AircraftType
        fields = ["id", "make", "model", "seats", "engines", "category", "is_custom"]
        read_only_fields = fields


#: What adding a type the vocabulary already holds is answered with.
DUPLICATE_TYPE_MESSAGE = "That aircraft type is already listed."

#: What a name left blank by normalization -- a corporate suffix alone (``INC``), or
#: only punctuation (``.``) -- is answered with.
BLANK_NAME_MESSAGE = "Enter a name, not only a corporate suffix or punctuation."


class AircraftTypeCreateSerializer(serializers.Serializer[AircraftType]):
    """``POST /aircraft/types``: a type the FAA has never registered, added by hand.

    ``make`` and ``model`` are required and written as display names, as the registry's
    would be: ``make`` through ``display_make`` and ``model`` through
    ``display_model`` of its upper-cased form (``cessna aircraft co`` is ``Cessna``,
    ``t-51`` is ``T-51``).  ``seats`` (at least 1) and ``engines`` (at least 0) are
    optional.  A name that normalizes to nothing -- ``display_make`` drops every word
    of a make that is only a corporate suffix or punctuation, such as ``INC`` or a bare
    ``.`` -- is refused under that field with :data:`BLANK_NAME_MESSAGE`.  A make and
    model the vocabulary already holds, compared case-insensitively after that
    normalization, is refused under ``model`` with :data:`DUPLICATE_TYPE_MESSAGE`.
    ``create`` saves an ``is_custom`` type coded ``CUSTOM-<id>``, its FAA spellings the
    upper-cased names as given.  The duplicate check reads the vocabulary and the save
    that follows are not atomic, so two requests adding the same type at once could
    both pass it and both save; the prototype accepts that rare race rather than
    locking every write against it, since a genuine duplicate is easy to notice and
    fold away by hand.
    """

    make = serializers.CharField(max_length=120)
    model = serializers.CharField(max_length=60)
    seats = serializers.IntegerField(min_value=1, max_value=999, required=False, allow_null=True)
    engines = serializers.IntegerField(min_value=0, max_value=99, required=False, allow_null=True)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Normalize the names, refuse a blank one, and refuse one already listed."""
        faa_make = " ".join(str(attrs["make"]).upper().split())
        faa_model = " ".join(str(attrs["model"]).upper().split())
        make = display_make(faa_make, faa_model)
        model = display_model(faa_model)
        errors: dict[str, list[str]] = {}
        if not make:
            errors["make"] = [BLANK_NAME_MESSAGE]
        if not model:
            errors["model"] = [BLANK_NAME_MESSAGE]
        if errors:
            raise serializers.ValidationError(errors)
        if AircraftType.objects.filter(make__iexact=make, model__iexact=model).exists():
            raise serializers.ValidationError({"model": [DUPLICATE_TYPE_MESSAGE]})
        return {
            **attrs,
            "faa_make": faa_make,
            "faa_model": faa_model,
            "make": make,
            "model": model,
        }

    def create(self, validated_data: dict[str, Any]) -> AircraftType:
        """Save the custom type, then code it ``CUSTOM-<id>`` once its id is known."""
        created = AircraftType.objects.create(
            faa_code=f"CUSTOM-{uuid4().hex[:9]}",
            is_custom=True,
            **validated_data,
        )
        created.faa_code = f"CUSTOM-{created.pk}"
        created.save(update_fields=["faa_code"])
        return created


class RegistrationSerializer(serializers.ModelSerializer[Registration]):
    """``GET /aircraft/registry/{n_number}``: one N-number as the registry holds it.

    ``airworthiness`` is blank when the registry records no certificate.
    """

    type = AircraftTypeSerializer(read_only=True)
    registrant_type = serializers.ChoiceField(choices=RegistrantType.choices, read_only=True)
    status = serializers.ChoiceField(choices=RegistrationStatus.choices, read_only=True)
    airworthiness = _read_only_choice(Airworthiness.choices)

    class Meta:
        model = Registration
        fields = [
            "n_number",
            "type",
            "year",
            "registrant_name",
            "registrant_type",
            "status",
            "certificate_issued_on",
            "expires_on",
            "airworthiness",
            "imported_at",
        ]
        read_only_fields = fields


class RegistryImportSerializer(serializers.ModelSerializer[RegistryImport]):
    """One run of the registry import: when, from where, how it ended, and its counts.

    ``finished_at`` is null while the run is under way; ``error`` is blank unless the
    run failed.
    """

    class Meta:
        model = RegistryImport
        fields = [
            "started_at",
            "finished_at",
            "ok",
            "error",
            "types_written",
            "registrations_written",
            "types_folded",
            "source",
        ]
        read_only_fields = fields


class RegistryStatusSerializer(serializers.Serializer[dict[str, Any]]):
    """``GET /aircraft/registry``: the date the registry is as of, and the last run.

    ``as_of`` is when the newest successful import finished (null before one has, and
    whenever the registrations table is empty, as after a restore);
    ``running`` whether an import is under way; ``last`` the newest import of any
    outcome, or null.
    """

    as_of = serializers.DateTimeField(allow_null=True)
    running = serializers.BooleanField()
    last = RegistryImportSerializer(allow_null=True)


class AircraftSummarySerializer(serializers.ModelSerializer[Aircraft]):
    """The short form embedded in profiles, leader cards and pickers.

    ``make`` and ``model`` are the display names of the aircraft's ``type``;
    ``coverage`` is whether the coverage policy excludes the aircraft (see
    :func:`coverage_payload`).  ``created_by`` is the id of the account that added the
    record, or null, so a member's own list can tell the records they may edit; the two
    liability limits, in cents, let a screen label each one.
    """

    make = serializers.CharField(read_only=True)
    model = serializers.CharField(read_only=True)
    type = AircraftTypeSerializer(read_only=True)
    insurance_is_current = serializers.BooleanField(read_only=True)
    insurance_summary = serializers.CharField(read_only=True)
    insurance_verified = serializers.BooleanField(source="insurance_is_verified", read_only=True)
    category = _read_only_choice(AircraftCategory.choices)
    airworthiness = _read_only_choice(Airworthiness.choices)
    coverage = serializers.SerializerMethodField()

    class Meta:
        model = Aircraft
        fields = [
            "id",
            "n_number",
            "make",
            "model",
            "type",
            "category",
            "airworthiness",
            "coverage",
            "insurance_is_current",
            "insurance_expiration",
            "insurance_liability_per_occurrence_cents",
            "insurance_liability_per_person_cents",
            "insurance_summary",
            "insurance_verified",
            "created_by",
        ]
        read_only_fields = fields

    @extend_schema_field(CoverageSerializer)
    def get_coverage(self, obj: Aircraft) -> dict[str, Any]:
        """Whether the coverage policy excludes ``obj``, and the reason to print."""
        return coverage_payload(self, obj)


class AircraftSerializer(serializers.ModelSerializer[Aircraft]):
    """The full record.  ``created_by`` is set by the view.

    The aircraft type is written as ``type_id``, the id of an ``AircraftType`` (required
    on create, refused with :data:`TYPE_MESSAGE` when missing, null, or unknown), and read
    back as the nested ``type`` with its display ``make`` and ``model`` beside it; neither
    ``make`` nor ``model`` is written.  ``category`` and ``airworthiness`` are optional
    choices, blank when not recorded; ``coverage`` is read-only (see
    :func:`coverage_payload`).
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
    coverage = serializers.SerializerMethodField()

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
            "category",
            "airworthiness",
            "coverage",
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

    @extend_schema_field(CoverageSerializer)
    def get_coverage(self, obj: Aircraft) -> dict[str, Any]:
        """Whether the coverage policy excludes ``obj``, and the reason to print."""
        return coverage_payload(self, obj)


class CoveragePolicySerializer(serializers.ModelSerializer[AircraftCoveragePolicy]):
    """``GET``/``PUT /aircraft/coverage-policy``: what CalDART's insurance does not cover.

    ``excluded_categories`` lists aircraft category values and ``excluded_airworthiness``
    airworthiness values; each list is answered in the order of its choices, without
    repeats, and a value outside its choices is refused.  ``note`` is a plain-text
    statement of at most 1,000 characters, stripped of surrounding space, and may be
    blank.  A ``PUT`` sends all three.
    """

    excluded_categories = serializers.ListField(
        child=serializers.ChoiceField(choices=AircraftCategory.choices), allow_empty=True
    )
    excluded_airworthiness = serializers.ListField(
        child=serializers.ChoiceField(choices=Airworthiness.choices), allow_empty=True
    )
    note = serializers.CharField(max_length=COVERAGE_NOTE_MAX_LENGTH, allow_blank=True)

    class Meta:
        model = AircraftCoveragePolicy
        fields = ["excluded_categories", "excluded_airworthiness", "note"]

    def validate_excluded_categories(self, value: list[str]) -> list[str]:
        """The categories in ``value``, in choice order and without repeats."""
        return [choice for choice in AircraftCategory.values if choice in value]

    def validate_excluded_airworthiness(self, value: list[str]) -> list[str]:
        """The classifications in ``value``, in choice order and without repeats."""
        return [choice for choice in Airworthiness.values if choice in value]


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


class LeaderGoNoGoSerializer(serializers.Serializer[Any]):
    """The go/no-go booleans, so a leader sees why, not just whether.

    ``verified`` is true when the person holds a pilot certificate, a medical, and a
    photo ID, and all three are verified.
    """

    membership = serializers.BooleanField()
    medical = serializers.BooleanField()
    verified = serializers.BooleanField()


class AircraftPilotSerializer(serializers.Serializer[Any]):
    """A member or friend who lists this aircraft as one they commonly fly.

    ``go_no_go`` is the member check's verdict for the person, so the aircraft check
    and the member check never disagree about them.
    """

    user_id = serializers.IntegerField()
    name = serializers.CharField()
    email = serializers.EmailField()
    membership_status = serializers.ChoiceField(choices=MembershipState.choices)
    medical_is_current = serializers.BooleanField()
    go_no_go = LeaderGoNoGoSerializer()


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


class LeaderSearchResultSerializer(serializers.Serializer[Any]):
    """One row of a leader's member search, carrying its own go/no-go.

    The two booleans are the same ones the status card shows, so the list
    answers "may this member fly?" without a second request.
    """

    user_id = serializers.IntegerField()
    name = serializers.CharField()
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
    is_dart_leader = serializers.BooleanField()
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
    ``Unknown item '<slug>'.``  A ``certificate_number`` that is not blank must be the
    seven digits the profile form asks for, or it is refused with the profile's message.
    """

    pilot_certificate_type = serializers.ChoiceField(
        choices=PilotCertificateType.choices, required=False
    )
    certificate_number = serializers.CharField(max_length=40, required=False, allow_blank=True)
    medical_type = serializers.ChoiceField(choices=MedicalType.choices, required=False)
    medical_expiration = serializers.DateField(required=False, allow_null=True)
    photo_id_type = serializers.ChoiceField(choices=PhotoIdType.choices, required=False)
    verified = serializers.ListField(child=ItemSlugField(), allow_empty=True)

    def validate_certificate_number(self, value: str) -> str:
        """Refuse a certificate number that is not blank or seven digits; return it."""
        return check_certificate_number(value)

    def validate_verified(self, value: list[str]) -> list[str]:
        """Refuse a slug that names no item; return the slugs without repeats."""
        for slug in value:
            if slug not in ITEM_LABELS:
                raise serializers.ValidationError(f"Unknown item '{slug}'.")
        return list(dict.fromkeys(value))


class VerifierGrantSerializer(serializers.Serializer[Any]):
    """``PUT /leader/members/{user_id}/verifier``: whether the member holds the role."""

    verifier = serializers.BooleanField()
