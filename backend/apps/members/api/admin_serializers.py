"""Serializers for the account-administrator member API.

The member record an administrator works with is a *user plus its profile*, so
these serializers write both halves in one request and read back the full
picture -- profile (including the admin-only notes), membership history and
payments.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any, cast

from django.contrib.auth import password_validation
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.models import User
from apps.accounts.roles import ROLE_SLUGS
from apps.accounts.services import AccountChanges
from apps.members.api.profile_serializers import (
    MembershipTermSerializer,
    PaymentSummarySerializer,
    ProfileSerializer,
)
from apps.members.api.serializers import MembershipStatusSerializer
from apps.members.models import (
    MedicalType,
    MemberProfile,
    Membership,
    MembershipPlan,
    PilotCertificateType,
)
from apps.members.services import create_member, membership_of, membership_payload, update_member

if TYPE_CHECKING:
    from apps.members.services import MemberRow
else:
    # ``MemberRow`` is a type-checking-only alias for an annotated ``User``.  The OpenAPI
    # generator evaluates every annotation on a ``SerializerMethodField`` handler, so the
    # name has to resolve at runtime as well; the plain model is what it stands for.
    MemberRow = User


# --------------------------------------------------------------------------
# Profile
# --------------------------------------------------------------------------
class AdminProfileSerializer(ProfileSerializer):
    """The profile as an administrator sees it.

    Everything ``/me/profile`` offers -- the same fields, the same validation --
    plus the admin-only ``notes`` and ``how_heard``, and nothing mandatory: an
    administrator records what they have been told, which on the day somebody
    joins at an airshow may be no more than a name.
    """

    phone = serializers.CharField(max_length=32, required=False, allow_blank=True)

    class Meta(ProfileSerializer.Meta):
        fields = [*ProfileSerializer.Meta.fields, "notes", "how_heard"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Build the serializer, then make every field optional."""
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = False


# --------------------------------------------------------------------------
# Membership terms and payments
# --------------------------------------------------------------------------
class AdminMembershipSerializer(MembershipTermSerializer):
    """A term in the history, and the target of ``PATCH /admin/memberships/{id}``.

    The member's own view of a term plus the fields only an administrator needs.
    ``ends_on``, ``status`` and ``note`` are writable -- the plan, the start date,
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

    def get_granted_by(self, obj: Membership) -> str | None:
        """The display name of the administrator who granted the term, if any."""
        return obj.granted_by.display_name if obj.granted_by is not None else None

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Refuse an end date before the start date, and return ``attrs``.

        The start date is the term's stored one, since it is read-only, and the
        end date the incoming one where the request carries it.  A term that
        would end before it began is refused against ``ends_on`` with "The end
        date cannot be before the start date."  A blank end date is a lifetime
        term and passes.
        """
        ends_on = attrs.get("ends_on", self.instance.ends_on if self.instance else None)
        starts_on = self.instance.starts_on if self.instance else attrs.get("starts_on")
        if ends_on is not None and starts_on is not None and ends_on < starts_on:
            raise serializers.ValidationError(
                {"ends_on": "The end date cannot be before the start date."}
            )
        return attrs


class MembershipGrantSerializer(serializers.Serializer[Any]):
    """``POST /admin/members/{id}/memberships`` -- grant a term by hand."""

    plan = serializers.SlugRelatedField(
        slug_field="slug", queryset=MembershipPlan.objects.filter(is_active=True)
    )
    starts_on = serializers.DateField(required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")


class AdminPaymentSerializer(PaymentSummarySerializer):
    """The member's own payment row, plus what reconciling needs.

    The split between plan price and contribution, the wallet and the
    provider's own reference are added; every field is read-only.
    """

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
class MemberListSerializer(serializers.Serializer["MemberRow"]):
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
    def _profile(obj: MemberRow) -> MemberProfile | None:
        """The member's profile row, or ``None`` when the account has none."""
        profile: MemberProfile | None = getattr(obj, "profile", None)
        return profile

    def get_phone(self, obj: MemberRow) -> str:
        """The member's phone number, blank when there is no profile."""
        profile = self._profile(obj)
        return profile.phone if profile else ""

    def get_dart(self, obj: MemberRow) -> str | None:
        """The name of the DART the member belongs to, or ``None``."""
        profile = self._profile(obj)
        return profile.dart.name if profile and profile.dart is not None else None

    @extend_schema_field(MembershipStatusSerializer)
    def get_membership(self, obj: MemberRow) -> dict[str, Any]:
        """The membership status, read off the row's annotations."""
        return dict(MembershipStatusSerializer(membership_payload(obj)).data)

    @extend_schema_field(serializers.ChoiceField(choices=PilotCertificateType.choices))
    def get_pilot_certificate_type(self, obj: MemberRow) -> str:
        """The certificate the member holds, ``none`` when there is no profile."""
        profile = self._profile(obj)
        return profile.pilot_certificate_type if profile else "none"

    @extend_schema_field(serializers.ChoiceField(choices=MedicalType.choices))
    def get_medical_type(self, obj: MemberRow) -> str:
        """The medical the member holds, ``none`` when there is no profile."""
        profile = self._profile(obj)
        return profile.medical_type if profile else "none"

    def get_medical_expiration(self, obj: MemberRow) -> date | None:
        """The medical expiration date, or ``None`` when there is none on file."""
        profile = self._profile(obj)
        return profile.medical_expiration if profile else None

    def get_medical_is_current(self, obj: MemberRow) -> bool:
        """True when the member holds a medical that has not expired.

        False when the account has no profile, and false when the profile records
        no medical.
        """
        profile = self._profile(obj)
        return bool(profile and profile.medical_is_current)

    def get_aircraft(self, obj: MemberRow) -> list[str]:
        """The N-numbers of the aircraft on the member's profile.

        Empty when the account has no profile, and empty when the profile has no
        aircraft attached.
        """
        profile = self._profile(obj)
        if profile is None:
            return []
        return [aircraft.n_number for aircraft in profile.aircraft.all()]


class MemberDetailSerializer(serializers.Serializer[User]):
    """``GET /admin/members/{id}`` -- user, profile, memberships and payments."""

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

    @extend_schema_field(serializers.ListField(child=serializers.ChoiceField(choices=ROLE_SLUGS)))
    def get_roles(self, obj: User) -> list[str]:
        """The role slugs the account holds, in the order the roles are declared."""
        return obj.roles

    def get_joined_on(self, obj: User) -> date | None:
        """The start of the member's earliest term, or ``None`` if they have none.

        An annotated row answers from its annotation; any other row spends a
        query on it.
        """
        annotated: date | None = getattr(obj, "joined_on", None)
        if annotated is not None:
            return annotated
        first = obj.memberships.order_by("starts_on").first()
        return first.starts_on if first else None

    @extend_schema_field(MembershipStatusSerializer)
    def get_membership(self, obj: User) -> dict[str, Any]:
        """The membership status, from the row's annotations where it has them."""
        return dict(MembershipStatusSerializer(membership_of(obj)).data)

    @extend_schema_field(AdminProfileSerializer(allow_null=True))
    def get_profile(self, obj: User) -> dict[str, Any] | None:
        """The profile including the admin-only fields, or ``None`` if there is none."""
        profile: MemberProfile | None = getattr(obj, "profile", None)
        return dict(AdminProfileSerializer(profile).data) if profile else None

    @extend_schema_field(AdminMembershipSerializer(many=True))
    def get_memberships(self, obj: User) -> list[dict[str, Any]]:
        """Every term the member holds, newest start first."""
        terms = obj.memberships.select_related("plan", "granted_by").order_by("-starts_on", "-id")
        return list(AdminMembershipSerializer(terms, many=True).data)

    @extend_schema_field(AdminPaymentSerializer(many=True))
    def get_payments(self, obj: User) -> list[dict[str, Any]]:
        """Every payment the member has made, newest first."""
        payments = obj.payments.select_related("plan").order_by("-created_at", "-id")
        return list(AdminPaymentSerializer(payments, many=True).data)


# --------------------------------------------------------------------------
# Write serializers
# --------------------------------------------------------------------------
class MemberCreateSerializer(serializers.Serializer[User]):
    """``POST /admin/members`` -- account plus nested profile."""

    email = serializers.EmailField()
    first_name = serializers.CharField(max_length=150, allow_blank=True, required=False, default="")
    last_name = serializers.CharField(max_length=150, allow_blank=True, required=False, default="")
    password = serializers.CharField(write_only=True, required=False, allow_blank=True)
    profile = AdminProfileSerializer(required=False)

    def validate_email(self, value: str) -> str:
        """Trim the address, refusing one an account already has.

        The test ignores case, and the complaint is "An account with that email
        address already exists."
        """
        value = value.strip()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("An account with that email address already exists.")
        return value

    def validate_password(self, value: str) -> str:
        """Put a password through Django's validators; a blank one is allowed.

        A blank password means the account is mailed an invitation instead, so
        only a value that was given is checked, and a weak one is refused with
        Django's own sentences.
        """
        if value:
            password_validation.validate_password(value)
        return value

    def create(self, validated_data: dict[str, Any]) -> User:
        """Create the account and its profile, and return the account.

        The acting administrator comes from the request in the serializer's
        context, and is recorded in the audit log by the service.
        """
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


class MemberUpdateSerializer(serializers.Serializer[User]):
    """``PATCH /admin/members/{id}`` -- account fields and nested profile.

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

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Build the serializer, binding the member's profile row to the nested field."""
        super().__init__(*args, **kwargs)
        # The profile's cross-field rules ("a medical class needs an expiry
        # date") read `self.instance` to see what a partial update would leave
        # in place.  Bind the row so a PATCH is judged against the whole
        # profile, not against the two fields it happens to send.
        profile = getattr(self.instance, "profile", None) if self.instance is not None else None
        if profile is not None:
            # DRF types every entry of ``fields`` as a plain ``Field``, which a
            # nested serializer is, without a way to say which one.
            nested = cast("AdminProfileSerializer", self.fields["profile"])
            nested.instance = profile

    def validate_email(self, value: str) -> str:
        """Trim the address, refusing one another account already has.

        The test ignores case and skips the member being edited, and the
        complaint is "An account with that email address already exists."
        """
        value = value.strip()
        clash = User.objects.filter(email__iexact=value)
        if self.instance is not None:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError("An account with that email address already exists.")
        return value

    def update(self, instance: User, validated_data: dict[str, Any]) -> User:
        """Apply the edit through the member service, and return the account.

        The account fields and the nested profile are written together, so an
        edit the guard refuses leaves the profile alone.
        """
        profile_data = validated_data.pop("profile", None)
        account: AccountChanges = {}
        if "email" in validated_data:
            account["email"] = validated_data["email"]
        if "first_name" in validated_data:
            account["first_name"] = validated_data["first_name"]
        if "last_name" in validated_data:
            account["last_name"] = validated_data["last_name"]
        if "is_active" in validated_data:
            account["is_active"] = validated_data["is_active"]
        return update_member(
            self.context["request"].user,
            instance,
            account=account,
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
