"""Serializers for the auth and users-admin endpoints."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.accounts.roles import ROLE_SLUGS
from apps.accounts.services import update_account, user_from_uid
from apps.members.api.serializers import MembershipStatusSerializer
from apps.members.services import membership_of

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """The ``user`` payload every account endpoint returns."""

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
        return MembershipStatusSerializer(membership_of(obj)).data

    def get_profile_complete(self, obj) -> bool:
        """``MemberProfile.is_complete`` is the one definition."""
        profile = getattr(obj, "profile", None)
        return bool(profile and profile.is_complete)


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
    """``POST /auth/register``."""

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
    """``POST /auth/password/change``."""

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
    """``/admin/users``: the ``user`` shape, partly writable.

    The serializer validates the input — the field formats, the role slugs against
    ``accounts.roles``, and that the address is free — and ``accounts.services``
    owns the rules that need both the caller and the target: only a ``system_admin``
    may move ``system_admin``, and the email address and active flag of an account
    holding roles the caller lacks are untouchable.
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

    def update(self, instance, validated_data: dict):
        return update_account(self._actor, instance, validated_data)
