"""Serializers for the account-administrator member API (PLAN §6.4).

The member record an administrator works with is a *user plus its profile*, so
these serializers write both halves in one request and read back the full
picture — profile (including the admin-only notes), membership history and
payments.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import serializers

from apps.accounts.roles import MEMBER
from apps.members.api.admin_filters import membership_payload
from apps.members.models import (
    RATING_VALUES,
    Dart,
    MemberProfile,
    Membership,
    MembershipPlan,
)

User = get_user_model()


# --------------------------------------------------------------------------
# Small shared pieces
# --------------------------------------------------------------------------
class DartRelatedField(serializers.PrimaryKeyRelatedField):
    """Accepts a DART id, renders ``{"id", "name"}`` (PLAN §6.3 ``profile``)."""

    def __init__(self, **kwargs):
        kwargs.setdefault("queryset", Dart.objects.all())
        kwargs.setdefault("allow_null", True)
        kwargs.setdefault("required", False)
        super().__init__(**kwargs)

    def use_pk_only_optimization(self) -> bool:
        return False

    def to_representation(self, value):
        return {"id": value.pk, "name": value.name}


class AircraftSummarySerializer(serializers.Serializer):
    """The aircraft summary PLAN §6.5 defines, read-only here."""

    id = serializers.IntegerField(read_only=True)
    n_number = serializers.CharField(read_only=True)
    make = serializers.CharField(read_only=True)
    model = serializers.CharField(read_only=True)
    insurance_is_current = serializers.BooleanField(read_only=True)
    insurance_expiration = serializers.DateField(read_only=True, allow_null=True)
    insurance_summary = serializers.CharField(read_only=True)


class MembershipStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=["current", "expired", "none"])
    expires_on = serializers.DateField(allow_null=True)
    plan = serializers.CharField(allow_null=True)
    is_lifetime = serializers.BooleanField()


class RatingsField(serializers.ListField):
    """``ratings`` is a JSON list drawn from a fixed vocabulary (PLAN §4.2)."""

    child = serializers.ChoiceField(choices=list(RATING_VALUES))

    def __init__(self, **kwargs):
        kwargs.setdefault("required", False)
        kwargs.setdefault("allow_empty", True)
        super().__init__(**kwargs)


# --------------------------------------------------------------------------
# Profile
# --------------------------------------------------------------------------
class AdminProfileSerializer(serializers.ModelSerializer):
    """Every profile field, *including* the admin-only ``notes``/``how_heard``."""

    dart = DartRelatedField()
    ratings = RatingsField()
    aircraft = AircraftSummarySerializer(many=True, read_only=True)
    medical_is_current = serializers.BooleanField(read_only=True)

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
            # admin only
            "notes",
            "how_heard",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # A member record can be created with only an email address, so nothing
        # in the profile half is mandatory.
        for field in self.fields.values():
            field.required = False


# --------------------------------------------------------------------------
# Membership terms and payments
# --------------------------------------------------------------------------
class AdminMembershipSerializer(serializers.ModelSerializer):
    """One term in the history, and the target of ``PATCH /admin/memberships/{id}``."""

    plan = serializers.CharField(source="plan.name", read_only=True)
    plan_slug = serializers.CharField(source="plan.slug", read_only=True)
    granted_by = serializers.SerializerMethodField()

    class Meta:
        model = Membership
        fields = [
            "id",
            "plan",
            "plan_slug",
            "starts_on",
            "ends_on",
            "status",
            "source",
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


class AdminPaymentSerializer(serializers.Serializer):
    """The payment rows shown on a member record (PLAN §4.4)."""

    id = serializers.IntegerField(read_only=True)
    plan = serializers.SerializerMethodField()
    amount_cents = serializers.IntegerField(read_only=True)
    plan_amount_cents = serializers.IntegerField(read_only=True)
    contribution_cents = serializers.IntegerField(read_only=True)
    currency = serializers.CharField(read_only=True)
    provider = serializers.CharField(read_only=True)
    wallet = serializers.CharField(read_only=True)
    provider_ref = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    completed_at = serializers.DateTimeField(read_only=True, allow_null=True)

    def get_plan(self, obj) -> str | None:
        return obj.plan.name if obj.plan_id else None


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
        if hasattr(obj, "covers_today"):
            payload = membership_payload(obj)
        else:
            payload = obj.membership_status
        return MembershipStatusSerializer(payload).data

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
def send_password_invitation(user) -> None:
    """Email a "set your password" link to an account created without one.

    The link points at the portal's reset-password screen, which posts back to
    ``/auth/password/reset/confirm`` (PLAN §6.1).
    """
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    url = f"{settings.SITE_URL}/portal/reset-password?uid={uid}&token={token}"
    name = user.first_name or user.display_name
    body = (
        f"Hello {name},\n\n"
        "An account has been created for you on the CalDART member portal.\n"
        "Choose a password to finish setting it up:\n\n"
        f"{url}\n\n"
        "If you were not expecting this, you can ignore this message.\n\n"
        "— The California DART Network\n"
    )
    send_mail(
        subject="Set your CalDART password",
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


class MemberCreateSerializer(serializers.Serializer):
    """``POST /admin/members`` — account plus nested profile."""

    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150, allow_blank=True, required=False, default="")
    last_name = serializers.CharField(max_length=150, allow_blank=True, required=False, default="")
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False, default=True)
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

    @transaction.atomic
    def create(self, validated_data):
        profile_data = validated_data.pop("profile", {}) or {}
        password = validated_data.pop("password", "") or ""

        user = User(
            email=validated_data["email"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
            is_active=validated_data.get("is_active", True),
        )
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        user.add_role(MEMBER)

        MemberProfile.objects.create(user=user, **profile_data)

        if not password:
            transaction.on_commit(lambda: send_password_invitation(user))
        return user


class MemberUpdateSerializer(serializers.Serializer):
    """``PATCH /admin/members/{id}`` — account fields and nested profile."""

    email = serializers.EmailField(required=False)
    first_name = serializers.CharField(max_length=150, allow_blank=True, required=False)
    last_name = serializers.CharField(max_length=150, allow_blank=True, required=False)
    is_active = serializers.BooleanField(required=False)
    profile = AdminProfileSerializer(required=False, partial=True)

    def validate_email(self, value):
        value = value.strip()
        clash = User.objects.filter(email__iexact=value)
        if self.instance is not None:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError("An account with that email address already exists.")
        return value

    @transaction.atomic
    def update(self, instance, validated_data):
        profile_data = validated_data.pop("profile", None)

        for field in ("email", "first_name", "last_name", "is_active"):
            if field in validated_data:
                setattr(instance, field, validated_data[field])
        instance.save()

        if profile_data is not None:
            profile, _ = MemberProfile.objects.get_or_create(user=instance)
            for field, value in profile_data.items():
                setattr(profile, field, value)
            profile.save()
            instance.refresh_from_db()
        return instance


__all__ = [
    "AdminMembershipSerializer",
    "AdminPaymentSerializer",
    "AdminProfileSerializer",
    "MemberCreateSerializer",
    "MemberDetailSerializer",
    "MemberListSerializer",
    "MemberUpdateSerializer",
    "MembershipGrantSerializer",
    "send_password_invitation",
]
