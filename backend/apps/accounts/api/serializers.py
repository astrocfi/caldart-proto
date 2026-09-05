"""Serializers for the auth and users-admin endpoints (PLAN §6.1, §6.2)."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.accounts.roles import ROLE_SLUGS, SYSTEM_ADMIN
from apps.accounts.services import user_from_uid

User = get_user_model()

#: The profile fields a member must fill in before the portal stops nagging
#: (PLAN §6.1, ``profile_complete``).
PROFILE_COMPLETE_FIELDS = (
    "phone",
    "address_line1",
    "city",
    "postal_code",
    "pilot_certificate_type",
)


class MembershipStatusSerializer(serializers.Serializer):
    """The ``membership_status`` dict returned by ``members.services``."""

    status = serializers.ChoiceField(choices=["current", "expired", "none"])
    expires_on = serializers.DateField(allow_null=True)
    plan = serializers.CharField(allow_null=True)
    is_lifetime = serializers.BooleanField()


class UserSerializer(serializers.ModelSerializer):
    """``user :=`` in PLAN §6.1."""

    roles = serializers.SerializerMethodField()
    membership = serializers.SerializerMethodField()
    profile_complete = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "roles",
            "is_active",
            "membership",
            "profile_complete",
        ]
        read_only_fields = fields

    def get_roles(self, obj) -> list[str]:
        return obj.roles

    def get_membership(self, obj) -> dict:
        return MembershipStatusSerializer(obj.membership_status).data

    def get_profile_complete(self, obj) -> bool:
        profile = getattr(obj, "profile", None)
        if profile is None:
            return False
        return all(getattr(profile, field, "") for field in PROFILE_COMPLETE_FIELDS)


class PasswordField(serializers.CharField):
    """A password input that is never trimmed and never echoed back."""

    def __init__(self, **kwargs):
        kwargs.setdefault("write_only", True)
        kwargs.setdefault("trim_whitespace", False)
        kwargs.setdefault("style", {"input_type": "password"})
        kwargs.setdefault("max_length", 128)
        super().__init__(**kwargs)


def run_password_validators(password: str, user=None, *, field: str | None = None) -> str:
    """Django's ``AUTH_PASSWORD_VALIDATORS`` as a DRF validator.

    Pass ``field`` from a serializer-level ``validate()`` so the complaint
    lands on the password input rather than in ``non_field_errors``.
    """
    try:
        validate_password(password, user=user)
    except DjangoValidationError as error:
        messages = list(error.messages)
        raise serializers.ValidationError({field: messages} if field else messages) from error
    return password


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(style={"input_type": "password"}, trim_whitespace=False)


class RegisterSerializer(serializers.Serializer):
    """``POST /auth/register`` (PLAN §6.1)."""

    email = serializers.EmailField()
    password = PasswordField()
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)

    def validate_email(self, value: str) -> str:
        value = value.strip()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(
                "An account already uses that email address. Sign in, or reset your password."
            )
        return value

    def validate(self, attrs: dict) -> dict:
        # Validate against the user-to-be so UserAttributeSimilarityValidator
        # can reject "marta.reyes" as a password for marta.reyes@example.org.
        candidate = User(
            email=attrs.get("email", ""),
            first_name=attrs.get("first_name", ""),
            last_name=attrs.get("last_name", ""),
        )
        run_password_validators(attrs["password"], user=candidate, field="password")
        return attrs


class PasswordChangeSerializer(serializers.Serializer):
    """``POST /auth/password/change`` (PLAN §6.1)."""

    current_password = PasswordField()
    new_password = PasswordField()

    def validate_current_password(self, value: str) -> str:
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("That is not your current password.")
        return value

    def validate_new_password(self, value: str) -> str:
        return run_password_validators(value, user=self.context["request"].user)


class PasswordResetSerializer(serializers.Serializer):
    """``POST /auth/password/reset`` — the request half."""

    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """``POST /auth/password/reset/confirm`` — the token half."""

    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = PasswordField()

    #: One message for every way a link can be unusable, so a caller cannot
    #: tell "no such account" from "already used".
    INVALID_LINK = "That password reset link is invalid or has expired. Request a new one."

    def validate(self, attrs: dict) -> dict:
        from django.contrib.auth.tokens import default_token_generator

        user = user_from_uid(attrs["uid"])
        if user is None or not user.is_active:
            raise serializers.ValidationError({"token": [self.INVALID_LINK]})
        if not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError({"token": [self.INVALID_LINK]})
        run_password_validators(attrs["new_password"], user=user, field="new_password")
        attrs["user"] = user
        return attrs


class RoleSerializer(serializers.Serializer):
    slug = serializers.CharField()
    description = serializers.CharField()


class AdminUserSerializer(UserSerializer):
    """``/admin/users`` (PLAN §6.2): the ``user`` shape, partly writable.

    ``roles`` is validated against ``accounts.roles``; the escalation rule —
    only a ``system_admin`` may grant or revoke ``system_admin`` — lives here
    because it needs both the caller and the target.
    """

    roles = serializers.ListField(
        child=serializers.ChoiceField(choices=list(ROLE_SLUGS)),
        allow_empty=True,
        required=False,
    )

    class Meta(UserSerializer.Meta):
        # `membership`, `profile_complete` and `roles` are declared fields, so
        # only the model columns need listing here.
        read_only_fields = ["id"]
        extra_kwargs = {
            "email": {"required": False},
            "first_name": {"required": False},
            "last_name": {"required": False},
            "is_active": {"required": False},
        }

    @property
    def _actor(self):
        return self.context["request"].user

    def validate_email(self, value: str) -> str:
        value = value.strip()
        clash = User.objects.filter(email__iexact=value)
        if self.instance is not None:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError("Another account already uses that email address.")
        return value

    def validate_is_active(self, value: bool) -> bool:
        if not value and self.instance is not None and self.instance == self._actor:
            raise serializers.ValidationError("You cannot deactivate your own account.")
        return value

    def validate_roles(self, value: list[str]) -> list[str]:
        wanted = set(value)
        held = set(self.instance.roles) if self.instance is not None else set()
        if SYSTEM_ADMIN in wanted ^ held and not self._actor.has_role(SYSTEM_ADMIN):
            raise serializers.ValidationError(
                "Only a system administrator can grant or revoke the system_admin role."
            )
        # Keep the canonical privilege order rather than whatever came in.
        return [slug for slug in ROLE_SLUGS if slug in wanted]

    def update(self, instance, validated_data: dict):
        from apps.accounts.services import sync_django_flags

        roles = validated_data.pop("roles", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if roles is not None:
            instance.set_roles(roles)
            sync_django_flags(instance)
        instance.save()
        return instance
