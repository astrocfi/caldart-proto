"""Serializers for the account-administrator member API.

The member record an administrator works with is a *user plus its profile*, so
these serializers write both halves in one request and read back the full
picture — profile (including the admin-only notes), membership history and
payments.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model, password_validation
from rest_framework import serializers

from apps.members.api.profile_serializers import (
    MembershipTermSerializer,
    PaymentSummarySerializer,
    ProfileSerializer,
)
from apps.members.api.serializers import MembershipStatusSerializer
from apps.members.models import MemberProfile, MembershipPlan
from apps.members.services import create_member, membership_of, membership_payload, update_member

User = get_user_model()


# --------------------------------------------------------------------------
# Profile
# --------------------------------------------------------------------------
class AdminProfileSerializer(ProfileSerializer):
    """The profile as an administrator sees it.

    Everything ``/me/profile`` offers — the same fields, the same validation —
    plus the admin-only ``notes`` and ``how_heard``, and nothing mandatory: an
    administrator records what they have been told, which on the day somebody
    joins at an airshow may be no more than a name.
    """

    phone = serializers.CharField(max_length=32, required=False, allow_blank=True)

    class Meta(ProfileSerializer.Meta):
        fields = [*ProfileSerializer.Meta.fields, "notes", "how_heard"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = False


# --------------------------------------------------------------------------
# Membership terms and payments
# --------------------------------------------------------------------------
class AdminMembershipSerializer(MembershipTermSerializer):
    """A term in the history, and the target of ``PATCH /admin/memberships/{id}``.

    The member's own view of a term plus the fields only an administrator needs.
    ``ends_on``, ``status`` and ``note`` are writable — the plan, the start date,
    the source and the payment link are not, because rewriting those would
    falsify the history rather than correct it.
    """

    plan_slug = serializers.CharField(source="plan.slug", read_only=True)
    granted_by = serializers.SerializerMethodField()

    class Meta(MembershipTermSerializer.Meta):
        fields = [
            *MembershipTermSerializer.Meta.fields,
            "plan_slug",
            "note",
            "granted_by",
            "payment",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "plan",
            "plan_slug",
            "starts_on",
            "source",
            "granted_by",
            "payment",
            "created_at",
        ]

    def get_granted_by(self, obj) -> str | None:
        return obj.granted_by.display_name if obj.granted_by_id else None

    def validate(self, attrs):
        ends_on = attrs.get("ends_on", self.instance.ends_on if self.instance else None)
        starts_on = self.instance.starts_on if self.instance else attrs.get("starts_on")
        if ends_on is not None and starts_on is not None and ends_on < starts_on:
            raise serializers.ValidationError(
                {"ends_on": "The end date cannot be before the start date."}
            )
        return attrs


class MembershipGrantSerializer(serializers.Serializer):
    """``POST /admin/members/{id}/memberships`` — grant a term by hand."""

    plan = serializers.SlugRelatedField(
        slug_field="slug", queryset=MembershipPlan.objects.filter(is_active=True)
    )
    starts_on = serializers.DateField(required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")


class AdminPaymentSerializer(PaymentSummarySerializer):
    """The member's own payment row, plus the split and the provider reference
    an administrator needs when reconciling."""

    class Meta(PaymentSummarySerializer.Meta):
        fields = [
            "id",
            "plan",
            "amount_cents",
            "plan_amount_cents",
            "contribution_cents",
            "currency",
            "provider",
            "wallet",
            "provider_ref",
            "status",
            "created_at",
            "completed_at",
        ]
        read_only_fields = fields


# --------------------------------------------------------------------------
# Member list / detail
# --------------------------------------------------------------------------
class MemberListSerializer(serializers.Serializer):
    """One row of ``GET /admin/members`` (``MemberRow`` in the portal types)."""

    user_id = serializers.IntegerField(source="pk", read_only=True)
    name = serializers.CharField(source="display_name", read_only=True)
    email = serializers.EmailField(read_only=True)
    phone = serializers.SerializerMethodField()
    dart = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(read_only=True)
    membership = serializers.SerializerMethodField()
    pilot_certificate_type = serializers.SerializerMethodField()
    medical_type = serializers.SerializerMethodField()
    medical_expiration = serializers.SerializerMethodField()
    medical_is_current = serializers.SerializerMethodField()
    aircraft = serializers.SerializerMethodField()
    joined_on = serializers.DateField(read_only=True, allow_null=True)

    @staticmethod
    def _profile(obj) -> MemberProfile | None:
        return getattr(obj, "profile", None)

    def get_phone(self, obj) -> str:
        profile = self._profile(obj)
        return profile.phone if profile else ""

    def get_dart(self, obj) -> str | None:
        profile = self._profile(obj)
        return profile.dart.name if profile and profile.dart_id else None

    def get_membership(self, obj) -> dict:
        return MembershipStatusSerializer(membership_payload(obj)).data

    def get_pilot_certificate_type(self, obj) -> str:
        profile = self._profile(obj)
        return profile.pilot_certificate_type if profile else "none"

    def get_medical_type(self, obj) -> str:
        profile = self._profile(obj)
        return profile.medical_type if profile else "none"

    def get_medical_expiration(self, obj):
        profile = self._profile(obj)
        return profile.medical_expiration if profile else None

    def get_medical_is_current(self, obj) -> bool:
        profile = self._profile(obj)
        return bool(profile and profile.medical_is_current)

    def get_aircraft(self, obj) -> list[str]:
        profile = self._profile(obj)
        if profile is None:
            return []
        return [aircraft.n_number for aircraft in profile.aircraft.all()]


class MemberDetailSerializer(serializers.Serializer):
    """``GET /admin/members/{id}`` — user, profile, memberships and payments."""

    id = serializers.IntegerField(read_only=True)
    email = serializers.EmailField(read_only=True)
    first_name = serializers.CharField(read_only=True)
    last_name = serializers.CharField(read_only=True)
    name = serializers.CharField(source="display_name", read_only=True)
    is_active = serializers.BooleanField(read_only=True)
    roles = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(read_only=True)
    joined_on = serializers.SerializerMethodField()
    membership = serializers.SerializerMethodField()
    profile = serializers.SerializerMethodField()
    memberships = serializers.SerializerMethodField()
    payments = serializers.SerializerMethodField()

    def get_roles(self, obj) -> list[str]:
        return obj.roles

    def get_joined_on(self, obj):
        annotated = getattr(obj, "joined_on", None)
        if annotated is not None:
            return annotated
        first = obj.memberships.order_by("starts_on").first()
        return first.starts_on if first else None

    def get_membership(self, obj) -> dict:
        return MembershipStatusSerializer(membership_of(obj)).data

    def get_profile(self, obj) -> dict | None:
        profile = getattr(obj, "profile", None)
        return AdminProfileSerializer(profile).data if profile else None

    def get_memberships(self, obj) -> list[dict]:
        terms = obj.memberships.select_related("plan", "granted_by").order_by("-starts_on", "-id")
        return AdminMembershipSerializer(terms, many=True).data

    def get_payments(self, obj) -> list[dict]:
        payments = obj.payments.select_related("plan").order_by("-created_at", "-id")
        return AdminPaymentSerializer(payments, many=True).data


# --------------------------------------------------------------------------
# Write serializers
# --------------------------------------------------------------------------
class MemberCreateSerializer(serializers.Serializer):
    """``POST /admin/members`` — account plus nested profile."""

    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150, allow_blank=True, required=False, default="")
    last_name = serializers.CharField(max_length=150, allow_blank=True, required=False, default="")
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    profile = AdminProfileSerializer(required=False)

    def validate_email(self, value):
        value = value.strip()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with that email address already exists.")
        return value

    def validate_password(self, value):
        if value:
            password_validation.validate_password(value)
        return value

    def create(self, validated_data):
        request = self.context["request"]
        return create_member(
            request.user,
            email=validated_data["email"],
            password=validated_data.get("password", "") or "",
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
            profile=validated_data.get("profile") or {},
            request=request,
        )


class MemberUpdateSerializer(serializers.Serializer):
    """``PATCH /admin/members/{id}`` — account fields and nested profile.

    The account half goes through the same service as ``/admin/users/{id}``, so it
    obeys the same edit guard: changing the email address or the active flag of an
    account that holds roles the caller does not hold is a field-keyed 400, and so is
    deactivating yourself.  It therefore needs the request in its context.
    """

    email = serializers.EmailField(required=False)
    first_name = serializers.CharField(max_length=150, allow_blank=True, required=False)
    last_name = serializers.CharField(max_length=150, allow_blank=True, required=False)
    is_active = serializers.BooleanField(required=False)
    profile = AdminProfileSerializer(required=False, partial=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The profile's cross-field rules ("a medical class needs an expiry
        # date") read `self.instance` to see what a partial update would leave
        # in place.  Bind the row so a PATCH is judged against the whole
        # profile, not against the two fields it happens to send.
        profile = getattr(self.instance, "profile", None) if self.instance is not None else None
        if profile is not None:
            self.fields["profile"].instance = profile

    def validate_email(self, value):
        value = value.strip()
        clash = User.objects.filter(email__iexact=value)
        if self.instance is not None:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError("An account with that email address already exists.")
        return value

    def update(self, instance, validated_data):
        profile_data = validated_data.pop("profile", None)
        return update_member(
            self.context["request"].user,
            instance,
            account=validated_data,
            profile=profile_data,
        )


__all__ = [
    "AdminMembershipSerializer",
    "AdminPaymentSerializer",
    "AdminProfileSerializer",
    "MemberCreateSerializer",
    "MemberDetailSerializer",
    "MemberListSerializer",
    "MemberUpdateSerializer",
    "MembershipGrantSerializer",
]
