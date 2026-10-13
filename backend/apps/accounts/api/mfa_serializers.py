"""Serializers for two-factor sign-in: the code step, enrolling, and the Security card."""

from __future__ import annotations

from drf_spectacular.utils import PolymorphicProxySerializer
from rest_framework import serializers

from apps.accounts.api.serializers import CurrentPasswordSerializer, UserSerializer
from apps.accounts.mfa import CODE_MISSING, SignInStep
from caldart.messages import when_missing

#: The longest code worth reading: a backup code typed with spaces around its hyphen.
OTP_MAX_LENGTH = 32


class OtpSerializer(serializers.Serializer[None]):
    """A request carrying one two-factor code: an authenticator code or a backup code."""

    otp = serializers.CharField(
        max_length=OTP_MAX_LENGTH, trim_whitespace=True, error_messages=when_missing(CODE_MISSING)
    )


class MfaChallengeSerializer(serializers.Serializer[dict[str, str]]):
    """What a right password answers when the account needs a second factor.

    ``mfa`` is ``verify`` when the account has a device and a code is asked for, and
    ``enroll`` when it must set one up first.  Nothing about the account is told.
    """

    mfa = serializers.ChoiceField(choices=[step.value for step in SignInStep])


#: The 200 body of ``POST /auth/login`` and ``POST /auth/reactivate``: the ``user``
#: payload once signed in, or the challenge when a second factor is still needed.  It
#: documents the shape only; the views build each half themselves.
LoginResponseSerializer = PolymorphicProxySerializer(
    component_name="LoginResponse",
    serializers=[UserSerializer, MfaChallengeSerializer],
    resource_type_field_name=None,
)


class EnrollmentSerializer(serializers.Serializer[dict[str, str]]):
    """What an authenticator app needs: the secret, its ``otpauth://`` address, the QR.

    ``qr_svg`` is the QR code of ``otpauth_uri`` as an SVG document; ``secret`` is the
    base32 secret for typing in by hand.
    """

    secret = serializers.CharField()
    otpauth_uri = serializers.CharField()
    qr_svg = serializers.CharField()


class RecoveryCodesSerializer(serializers.Serializer[dict[str, list[str]]]):
    """A fresh set of backup codes, shown this once."""

    recovery_codes = serializers.ListField(child=serializers.CharField())


class EnrolledSignInSerializer(RecoveryCodesSerializer):
    """The end of signing in by enrolling: the ``user`` payload and the backup codes."""

    user = UserSerializer()


class MfaStatusSerializer(serializers.Serializer[dict[str, object]]):
    """``GET /auth/mfa``: whether two-factor sign-in is on, and whether it must be.

    ``enabled`` is true with a confirmed device; ``required_by_role`` is true when a role
    the account holds requires it, when it cannot be turned off; and
    ``recovery_codes_remaining`` counts the unused backup codes.
    """

    enabled = serializers.BooleanField()
    required_by_role = serializers.BooleanField()
    recovery_codes_remaining = serializers.IntegerField()


class MfaEnrollSerializer(CurrentPasswordSerializer):
    """``POST /auth/mfa/enroll``: the current password, before a secret is drawn."""


class MfaDisableSerializer(CurrentPasswordSerializer):
    """``POST /auth/mfa/disable``: the current password and a current code."""

    otp = serializers.CharField(
        max_length=OTP_MAX_LENGTH, trim_whitespace=True, error_messages=when_missing(CODE_MISSING)
    )
