"""Serializers for the auth and users-admin endpoints."""

from __future__ import annotations

from typing import Any

from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers, status
from rest_framework.exceptions import APIException

from apps.accounts.models import (
    PERSON_KIND_CHOICES,
    AccountChange,
    AccountChangeKind,
    AccountKind,
    User,
)
from apps.accounts.roles import ROLE_SLUGS
from apps.accounts.services import (
    AccountChanges,
    is_donor,
    normalized_email,
    update_account,
    user_from_uid,
)
from apps.accounts.status import closed_account_message
from apps.members.api.serializers import MembershipStatusSerializer
from apps.members.models import MembershipStatusChoices
from apps.members.services import membership_of
from caldart.messages import USER_RECORD_ROLES_ONLY, email_messages, when_missing


class UserSerializer(serializers.ModelSerializer[User]):
    """The ``user`` payload every account endpoint returns.

    ``admin_created`` is true for an account an account administrator created on New
    member: its owner has joined already, so once the address is verified the portal
    opens without the profile and pay steps.
    """

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
            "admin_created",
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

    email = serializers.EmailField(error_messages=email_messages("Enter your email address."))
    password = serializers.CharField(
        style={"input_type": "password"},
        trim_whitespace=False,
        error_messages=when_missing("Enter your password."),
    )


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

    email = serializers.EmailField(error_messages=email_messages("Enter your email address."))
    password = PasswordField(error_messages=when_missing("Choose a password."))
    first_name = serializers.CharField(
        max_length=150, error_messages=when_missing("Enter your first name.")
    )
    last_name = serializers.CharField(
        max_length=150, error_messages=when_missing("Enter your last name.")
    )
    kind = serializers.ChoiceField(
        choices=PERSON_KIND_CHOICES, default=AccountKind.MEMBER.value, required=False
    )

    def validate_email(self, value: str) -> str:
        """The address, stripped, provided no active member or friend already uses it.

        An address belonging to an active donor passes: registering upgrades the
        donor in place.  An address belonging to an account a user administrator has
        blocked from reactivating is rejected with "This account has been closed.
        Contact <organization name> to reopen it."; one belonging to any other
        deactivated account, of any kind, raises ``DeactivatedAccountError``.  Any
        other taken address, compared case-insensitively, is rejected with "An account
        already uses that email address. Sign in, or reset your password."
        """
        value = value.strip()
        existing = User.objects.filter(email__iexact=value).first()
        if existing is None:
            return value
        if existing.reactivation_blocked:
            raise serializers.ValidationError(closed_account_message())
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

    current_password = PasswordField(error_messages=when_missing("Enter your current password."))

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

    new_password = PasswordField(error_messages=when_missing("Choose a new password."))

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

    email = serializers.EmailField(error_messages=email_messages("Enter your email address."))


class PasswordResetConfirmSerializer(serializers.Serializer[None]):
    """``POST /auth/password/reset/confirm`` -- the token half: the link and password."""

    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = PasswordField(error_messages=when_missing("Choose a new password."))

    #: One message for every way a link can be unusable, so a caller cannot
    #: tell "no such account" from "already used".
    INVALID_LINK = "That password reset link is invalid or has expired. Request a new one."

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """``attrs`` with the account the link names added under ``user``.

        An unreadable or unknown ``uid``, a donor's account (a donor cannot hold a
        password), and a ``token`` the default generator refuses all raise
        ``serializers.ValidationError`` under the ``token`` key carrying
        ``INVALID_LINK``, so a caller cannot tell them apart.  A deactivated account's
        link is accepted: completing the reset reactivates it.  A good link for an
        account a user administrator has blocked from reactivating is refused under
        ``token`` with "This account has been closed. Contact <organization name> to
        reopen it.", and no password is set.  A password Django's validators reject is
        raised under ``new_password``.
        """
        user = user_from_uid(attrs["uid"])
        if user is None or is_donor(user):
            raise serializers.ValidationError({"token": [self.INVALID_LINK]})
        if not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError({"token": [self.INVALID_LINK]})
        if user.reactivation_blocked:
            raise serializers.ValidationError({"token": [closed_account_message()]})
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

    email = serializers.EmailField(error_messages=email_messages("Enter the new address."))
    current_password = PasswordField(error_messages=when_missing("Enter your current password."))

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


#: The account columns the user record shows but never changes.
ROLES_ONLY_REFUSED_FIELDS: tuple[str, ...] = ("first_name", "last_name", "email")


class AdminUserSerializer(UserSerializer):
    """``/admin/users``: the ``user`` shape, with only ``roles`` writable.

    The serializer checks the role slugs against ``accounts.roles``, and
    ``accounts.services`` owns the rule that needs both the caller and the target: only
    a ``system_admin`` may move ``system_admin``.  ``first_name``, ``last_name``, and
    ``email`` are read here and changed on the member record or by the person; a request
    carrying any of them, even unchanged, is refused 400 keyed on each one it carries,
    with :data:`caldart.messages.USER_RECORD_ROLES_ONLY`, and changes nothing.  The
    active flag and ``reactivation_blocked`` are read
    here and changed only through the record's own actions (deactivate, reactivate,
    block, unblock).  ``email_bounced_at`` and ``email_bounce_detail`` say when and why
    the bounce check last found the address bouncing, null and blank with no bounce
    known; they are changed only by the bounce check, a new or verified address, and
    the record's **Clear bounce** action.  ``phone``, ``dart`` (the DART's name),
    ``city``, ``county``, and ``home_airport`` are read from the profile, for the
    columns the users list can show; blank, and a null DART, without a profile.
    """

    # djangorestframework-stubs types SerializerMethodField as a bare Field, so
    # replacing the inherited declared field reads as an incompatible assignment.
    roles = serializers.ListField(  # type: ignore[assignment]
        child=serializers.ChoiceField(choices=list(ROLE_SLUGS)),
        allow_empty=True,
        required=False,
    )
    email_verified_at = serializers.DateTimeField(read_only=True, allow_null=True)
    email_bounced_at = serializers.DateTimeField(read_only=True, allow_null=True)
    phone = serializers.SerializerMethodField()
    dart = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    county = serializers.SerializerMethodField()
    home_airport = serializers.SerializerMethodField()

    class Meta(UserSerializer.Meta):
        fields = [
            *UserSerializer.Meta.fields,
            "email_verified_at",
            "email_bounced_at",
            "email_bounce_detail",
            "reactivation_blocked",
            "phone",
            "dart",
            "city",
            "county",
            "home_airport",
        ]
        # `membership`, `profile_complete`, `email_verified`, `email_verified_at`,
        # `email_bounced_at`, and `roles` are declared fields, so only the model columns
        # need listing here.  The kind is the account administrator's to change, never
        # the user administrator's.
        read_only_fields = [
            "id",
            *ROLES_ONLY_REFUSED_FIELDS,
            "kind",
            "friend_on",
            "admin_created",
            "is_active",
            "reactivation_blocked",
            "email_bounce_detail",
        ]

    @staticmethod
    def _profile_text(obj: User, field: str) -> str:
        """The profile's ``field``, or a blank string when the account has no profile."""
        profile = getattr(obj, "profile", None)
        text: str = getattr(profile, field) if profile is not None else ""
        return text

    def get_phone(self, obj: User) -> str:
        """The account's phone number, blank without a profile."""
        return self._profile_text(obj, "phone")

    def get_dart(self, obj: User) -> str | None:
        """The name of the account's DART, or ``None`` without one."""
        profile = getattr(obj, "profile", None)
        if profile is None or profile.dart is None:
            return None
        name: str = profile.dart.name
        return name

    def get_city(self, obj: User) -> str:
        """The account's city, blank without a profile."""
        return self._profile_text(obj, "city")

    def get_county(self, obj: User) -> str:
        """The account's California county, blank without a profile."""
        return self._profile_text(obj, "county")

    def get_home_airport(self, obj: User) -> str:
        """The home airport's identifier, blank without a profile."""
        return self._profile_text(obj, "home_airport_identifier")

    @property
    def _actor(self) -> User:
        """The signed-in user making the edit, taken from the request in the context."""
        actor: User = self.context["request"].user
        return actor

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """``attrs`` unchanged, unless the request carries a name or the address.

        A read-only field is otherwise dropped without a word, so each of
        ``ROLES_ONLY_REFUSED_FIELDS`` the request carries is refused here, keyed on the
        field, with :data:`caldart.messages.USER_RECORD_ROLES_ONLY`.
        """
        carried = [field for field in ROLES_ONLY_REFUSED_FIELDS if field in self.initial_data]
        if len(carried) > 0:
            raise serializers.ValidationError(
                {field: [USER_RECORD_ROLES_ONLY] for field in carried}
            )
        return attrs

    def update(self, instance: User, validated_data: AccountChanges) -> User:
        """Hand the change to ``accounts.services.update_account`` and return the account.

        That is where the rules needing both accounts live, so a refusal surfaces as the
        ``DomainValidationError`` it raises rather than as a serializer error.
        """
        return update_account(self._actor, instance, validated_data)


class AdminUserDetailSerializer(AdminUserSerializer):
    """``/admin/users/{id}``: the list's row, plus two facts about the terms.

    The user record words the membership as the member record does, and a user
    administrator cannot read the terms, so the record carries what the wording needs:
    ``has_terms`` (the account holds any term at all) and ``has_suspended_term`` (a
    deactivation set one aside).  The list leaves them out, since each costs a query per
    row.
    """

    has_terms = serializers.SerializerMethodField()
    has_suspended_term = serializers.SerializerMethodField()

    class Meta(AdminUserSerializer.Meta):
        fields = [
            *AdminUserSerializer.Meta.fields,
            "has_terms",
            "has_suspended_term",
        ]

    def get_has_terms(self, obj: User) -> bool:
        """True when the account holds any membership term, of any status."""
        return obj.memberships.exists()

    def get_has_suspended_term(self, obj: User) -> bool:
        """True when a deactivation set one of the account's terms aside."""
        return obj.memberships.filter(status=MembershipStatusChoices.SUSPENDED).exists()


class AccountActorSerializer(serializers.Serializer[User]):
    """The account behind a history entry: its id and the name to print beside a date."""

    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(source="display_name", read_only=True)


class AccountChangeSerializer(serializers.ModelSerializer[AccountChange]):
    """One entry of ``GET /admin/users/{id}/history``.

    ``changed_by`` is ``{id, name}`` for the account that acted, or null for a
    management command (``by_command`` true) or an account since deleted
    (``by_command`` false).  ``added`` and ``removed`` are the
    role slugs a ``roles`` entry granted and took away, in privilege order, and empty for
    every other kind.
    """

    changed_by = AccountActorSerializer(read_only=True, allow_null=True)
    kind = serializers.ChoiceField(choices=AccountChangeKind.choices, read_only=True)
    added = serializers.ListField(child=serializers.ChoiceField(choices=ROLE_SLUGS), read_only=True)
    removed = serializers.ListField(
        child=serializers.ChoiceField(choices=ROLE_SLUGS), read_only=True
    )

    class Meta:
        model = AccountChange
        fields = ["id", "changed_at", "changed_by", "by_command", "kind", "added", "removed"]
        read_only_fields = fields
