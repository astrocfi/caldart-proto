"""Serializers for the auth and users-admin endpoints."""

from __future__ import annotations

from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers, status
from rest_framework.exceptions import APIException

from apps.accounts.models import PERSON_KIND_CHOICES, AccountKind, User
from apps.accounts.roles import ROLE_SLUGS
from apps.accounts.services import (
    AccountChanges,
    is_donor,
    normalized_email,
    user_from_uid,
)
from apps.members.api.serializers import MembershipStatusSerializer
from apps.members.services import apply_account_changes, membership_of


class UserSerializer(serializers.ModelSerializer[User]):
    """The ``user`` payload every account endpoint returns."""

    roles = serializers.SerializerMethodField()
    membership = serializers.SerializerMethodField()
    profile_complete = serializers.SerializerMethodField()
    email_verified = serializers.BooleanField(read_only=True)

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
            "email_verified",
            "kind",
            "friend_on",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.ListField(child=serializers.ChoiceField(choices=ROLE_SLUGS)))
    def get_roles(self, obj: User) -> list[str]:
        """The account's role slugs, in privilege order; empty when it holds none."""
        return obj.roles

    @extend_schema_field(MembershipStatusSerializer)
    def get_membership(self, obj: User) -> dict[str, Any]:
        """The account's membership summary, as ``MembershipStatusSerializer`` renders it.

        Carries ``status``, ``expires_on``, ``plan``, and ``is_lifetime``, read from the
        annotations when the row came from ``with_membership``.
        """
        membership: dict[str, Any] = MembershipStatusSerializer(membership_of(obj)).data
        return membership

    def get_profile_complete(self, obj: User) -> bool:
        """True when the account has a member profile and that profile is complete.

        ``MemberProfile.is_complete`` is the one definition; an account with no profile
        row at all is False.
        """
        profile = getattr(obj, "profile", None)
        return bool(profile and profile.is_complete)


class PasswordField(serializers.CharField):
    """A password input that is never trimmed and never echoed back."""

    def __init__(self, **kwargs: Any) -> None:
        """Build the field, defaulting it to write-only, untrimmed, and 128 characters.

        Any of those defaults may be overridden through ``kwargs``, which are otherwise
        passed to ``CharField`` unchanged.
        """
        kwargs.setdefault("write_only", True)
        kwargs.setdefault("trim_whitespace", False)
        kwargs.setdefault("style", {"input_type": "password"})
        kwargs.setdefault("max_length", 128)
        super().__init__(**kwargs)


def run_password_validators(
    password: str, user: User | None = None, *, field: str | None = None
) -> str:
    """Run Django's ``AUTH_PASSWORD_VALIDATORS`` over ``password`` and return it.

    ``user`` lets the similarity validator compare the password with the account's own
    name and address.  A password the validators reject raises
    ``serializers.ValidationError`` carrying their messages: keyed by ``field`` when one
    is given, so the complaint lands on the password input, and as a plain list
    otherwise, which DRF reports under ``non_field_errors``.  Pass ``field`` from a
    serializer-level ``validate()``.
    """
    try:
        validate_password(password, user=user)
    except DjangoValidationError as error:
        messages = list(error.messages)
        raise serializers.ValidationError({field: messages} if field else messages) from error
    return password


class LoginSerializer(serializers.Serializer[None]):
    """``POST /auth/login``: the email address and password to sign in with."""

    email = serializers.EmailField()
    password = serializers.CharField(style={"input_type": "password"}, trim_whitespace=False)


class DeactivatedAccountError(APIException):
    """A registration for an address a deactivated account holds.

    Rendered as 400 ``{"email": [<sentence>], "code": "deactivated"}``: the ``code``
    tells the portal to offer a sign-in, where the account can be reactivated.
    """

    status_code = status.HTTP_400_BAD_REQUEST
    MESSAGE = "This email belongs to a deactivated account. Sign in to reactivate it."

    def __init__(self) -> None:
        """Build the error with its fixed body."""
        super().__init__({"email": [self.MESSAGE], "code": "deactivated"})


class RegisterSerializer(serializers.Serializer[None]):
    """``POST /auth/register``: the fields a self-service signup supplies."""

    email = serializers.EmailField()
    password = PasswordField()
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    kind = serializers.ChoiceField(
        choices=PERSON_KIND_CHOICES, default=AccountKind.MEMBER.value, required=False
    )

    def validate_email(self, value: str) -> str:
        """The address, stripped, provided no active member or friend already uses it.

        An address belonging to an active donor passes: registering upgrades the
        donor in place.  An address belonging to a deactivated account, of any kind,
        raises ``DeactivatedAccountError``.  Any other taken address, compared
        case-insensitively, is rejected with "An account already uses that email
        address. Sign in, or reset your password."
        """
        value = value.strip()
        existing = User.objects.filter(email__iexact=value).first()
        if existing is None:
            return value
        if not existing.is_active:
            raise DeactivatedAccountError
        if is_donor(existing):
            return value
        raise serializers.ValidationError(
            "An account already uses that email address. Sign in, or reset your password."
        )

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """``attrs`` unchanged, once the password passes Django's validators.

        A rejected password raises ``serializers.ValidationError`` under the
        ``password`` key.
        """
        # Validate against the user-to-be so UserAttributeSimilarityValidator
        # can reject "marta.reyes" as a password for marta.reyes@example.org.
        candidate = User(
            email=attrs.get("email", ""),
            first_name=attrs.get("first_name", ""),
            last_name=attrs.get("last_name", ""),
        )
        run_password_validators(attrs["password"], user=candidate, field="password")
        return attrs


class CurrentPasswordSerializer(serializers.Serializer[None]):
    """A request the signed-in user confirms with their current password."""

    current_password = PasswordField()

    WRONG_PASSWORD = "That is not your current password."  # noqa: S105 - an error message

    def validate_current_password(self, value: str) -> str:
        """``value`` unchanged when it really is the signed-in user's password.

        Rejects anything else with "That is not your current password."
        """
        user: User = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError(self.WRONG_PASSWORD)
        return value


class PasswordChangeSerializer(CurrentPasswordSerializer):
    """``POST /auth/password/change``: the current password and the one to replace it."""

    new_password = PasswordField()

    def validate_new_password(self, value: str) -> str:
        """``value`` unchanged when Django's password validators accept it.

        The signed-in user is passed to them, so a password resembling that account's
        own name or address is rejected with their messages.
        """
        password: str = run_password_validators(value, user=self.context["request"].user)
        return password


class DeactivateSerializer(CurrentPasswordSerializer):
    """``POST /auth/deactivate``: the signed-in user's current password alone."""


class PasswordResetSerializer(serializers.Serializer[None]):
    """``POST /auth/password/reset`` -- the request half: the address to mail."""

    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer[None]):
    """``POST /auth/password/reset/confirm`` -- the token half: the link and password."""

    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = PasswordField()

    #: One message for every way a link can be unusable, so a caller cannot
    #: tell "no such account" from "already used".
    INVALID_LINK = "That password reset link is invalid or has expired. Request a new one."

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """``attrs`` with the account the link names added under ``user``.

        An unreadable or unknown ``uid``, a donor's account (a donor cannot hold a
        password), and a ``token`` the default generator refuses all raise
        ``serializers.ValidationError`` under the ``token`` key carrying
        ``INVALID_LINK``, so a caller cannot tell them apart.  A deactivated account's
        link is accepted: completing the reset reactivates it.  A password Django's
        validators reject is raised under ``new_password``.
        """
        user = user_from_uid(attrs["uid"])
        if user is None or is_donor(user):
            raise serializers.ValidationError({"token": [self.INVALID_LINK]})
        if not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError({"token": [self.INVALID_LINK]})
        run_password_validators(attrs["new_password"], user=user, field="new_password")
        attrs["user"] = user
        return attrs


class EmailVerifySerializer(serializers.Serializer[None]):
    """``POST /auth/email/verify``: the token from a verification link."""

    token = serializers.CharField()


class EmailVerifiedSerializer(serializers.Serializer[dict[str, str]]):
    """``POST /auth/email/verify``: the address the link verified."""

    email = serializers.EmailField()


class VerificationSentSerializer(serializers.Serializer[dict[str, str]]):
    """The sentence a verification resend answers with, naming the address mailed."""

    detail = serializers.CharField()


class EmailChangeSerializer(serializers.Serializer[None]):
    """``POST /auth/email/change``: the address to move to, and the current password."""

    email = serializers.EmailField()
    current_password = PasswordField()

    #: The address is the login, so moving it asks for the password first.
    WRONG_PASSWORD = "That is not your current password."  # noqa: S105 - an error message
    SAME_ADDRESS = "That is already your email address."
    TAKEN_ADDRESS = "Another account already uses that email address."

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """``attrs`` with the address stripped, once the change passes three checks.

        They run in this order and the first failure is the only one reported: the
        current password must be the signed-in user's (``current_password``: "That is
        not your current password."); the address must differ from the account's own,
        compared case-insensitively (``email``: "That is already your email
        address."); and no other account may use it, compared the same way
        (``email``: "Another account already uses that email address.").
        """
        user: User = self.context["request"].user
        if not user.check_password(attrs["current_password"]):
            raise serializers.ValidationError({"current_password": [self.WRONG_PASSWORD]})
        email = attrs["email"].strip()
        if normalized_email(email) == normalized_email(user.email):
            raise serializers.ValidationError({"email": [self.SAME_ADDRESS]})
        if User.objects.filter(email__iexact=email).exclude(pk=user.pk).exists():
            raise serializers.ValidationError({"email": [self.TAKEN_ADDRESS]})
        attrs["email"] = email
        return attrs


class RoleSerializer(serializers.Serializer[dict[str, str]]):
    """``GET /roles``: one role's slug and its human description."""

    slug = serializers.ChoiceField(choices=list(ROLE_SLUGS))
    description = serializers.CharField()


class SendPasswordResetResultSerializer(serializers.Serializer[dict[str, str]]):
    """``POST /admin/users/{id}/send-password-reset``: the sentence to show.

    The one field, ``detail``, names the address the link went to.
    """

    detail = serializers.CharField()


class AdminUserSerializer(UserSerializer):
    """``/admin/users``: the ``user`` shape, partly writable.

    The serializer validates the input -- the field formats, the role slugs against
    ``accounts.roles``, and that the address is free -- and ``accounts.services``
    owns the rules that need both the caller and the target: only a ``system_admin``
    may move ``system_admin``, and the email address and active flag of an account
    holding roles the caller lacks are untouchable.
    """

    # djangorestframework-stubs types SerializerMethodField as a bare Field, so
    # replacing the inherited declared field reads as an incompatible assignment.
    roles = serializers.ListField(  # type: ignore[assignment]
        child=serializers.ChoiceField(choices=list(ROLE_SLUGS)),
        allow_empty=True,
        required=False,
    )
    email_verified_at = serializers.DateTimeField(read_only=True, allow_null=True)

    class Meta(UserSerializer.Meta):
        fields = [*UserSerializer.Meta.fields, "email_verified_at"]
        # `membership`, `profile_complete`, `email_verified`, `email_verified_at`,
        # and `roles` are declared fields, so only the model columns need listing here.
        # The kind is the account administrator's to change, never the user
        # administrator's.
        read_only_fields = ["id", "kind", "friend_on"]
        extra_kwargs = {
            "email": {"required": False},
            "first_name": {"required": False},
            "last_name": {"required": False},
            "is_active": {"required": False},
        }

    @property
    def _actor(self) -> User:
        """The signed-in user making the edit, taken from the request in the context."""
        actor: User = self.context["request"].user
        return actor

    def validate_email(self, value: str) -> str:
        """The address, stripped, provided no other account uses it.

        The account being edited is excluded from the check, so resending its own
        address is accepted.  Any other match, compared case-insensitively, is rejected
        with "Another account already uses that email address."
        """
        value = value.strip()
        clash = User.objects.filter(email__iexact=value)
        if self.instance is not None:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError("Another account already uses that email address.")
        return value

    def update(self, instance: User, validated_data: AccountChanges) -> User:
        """Hand the change to ``accounts.services.update_account`` and return the account.

        That is where the rules needing both accounts live, so a refusal surfaces as the
        ``DomainValidationError`` it raises rather than as a serializer error.  It goes
        through ``members.services.apply_account_changes``, so ticking the active flag
        on a deactivated account also brings back its suspended membership terms.
        """
        return apply_account_changes(self._actor, instance, validated_data)
