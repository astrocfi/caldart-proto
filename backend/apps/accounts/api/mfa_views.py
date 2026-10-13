"""Two-factor sign-in endpoints: the code steps of signing in, and the Security card.

The code steps (``/auth/login/mfa*``) finish a sign-in a right password started
(``apps.accounts.api.sign_in.start_session``); they act on the pending sign-in in the
caller's session and on nothing else.  The ``/auth/mfa*`` endpoints are the signed-in
person's own: turning two-factor sign-in on, replacing the backup codes, and turning it
off.  Every endpoint that takes a code is throttled under ``auth_mfa``, and a wrong code
counts against the address's lockout.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict

from django.db import transaction
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts import lockout, mfa
from apps.accounts.api.mfa_serializers import (
    EnrolledSignInSerializer,
    EnrollmentSerializer,
    MfaDisableSerializer,
    MfaEnrollSerializer,
    MfaStatusSerializer,
    OtpSerializer,
    RecoveryCodesSerializer,
)
from apps.accounts.api.serializers import UserSerializer
from apps.accounts.api.sign_in import finish_sign_in, refuse_if_locked_out
from apps.accounts.api.views import reactivate, signed_in_user
from apps.accounts.models import User
from apps.accounts.status import closed_account_message
from apps.accounts.throttling import MfaThrottle
from caldart.exceptions import DomainError, DomainValidationError

#: What the code steps answer when there is no pending sign-in to finish: it expired,
#: took too many wrong codes, or was never started.
SIGN_IN_EXPIRED = "Your sign-in has expired. Enter your email address and password again."

#: The ``code`` that answer carries, which sends the portal back to the password step.
SIGN_IN_EXPIRED_CODE = "mfa_expired"


def _expired() -> Response:
    """The 400 a code step answers without a pending sign-in to finish."""
    return Response(
        {"detail": SIGN_IN_EXPIRED, "code": SIGN_IN_EXPIRED_CODE},
        status=status.HTTP_400_BAD_REQUEST,
    )


def _otp(request: Request) -> str:
    """The ``otp`` the body carries, or a 400 naming the field when it is missing."""
    serializer = OtpSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    otp: str = serializer.validated_data["otp"]
    return otp


def _wrong_code(request: Request, user: User) -> Response:
    """Count a wrong code at sign-in against the pending sign-in and the address.

    The first wrong code of a pending sign-in mails the owner.  The fifth ends the
    pending sign-in and answers the expiry; any other is a 400 ``{"otp": [...]}``.
    """
    lockout.record_failure(user.email, code=True)
    if mfa.count_wrong_code(request.session, user):
        return _expired()
    return Response({"otp": [mfa.CODE_REFUSED]}, status=status.HTTP_400_BAD_REQUEST)


def _pending(request: Request, step: mfa.SignInStep) -> mfa.PendingSignIn | None:
    """The caller's pending sign-in when it is at ``step``, after the lockout check.

    A locked-out address ends the pending sign-in and raises the lockout's 429.
    """
    pending = mfa.pending_sign_in(request.session)
    if pending is None or pending.step != step:
        return None
    if lockout.lockout_wait(pending.user.email) is not None:
        mfa.clear_pending(request.session)
        refuse_if_locked_out(pending.user.email)
    return pending


def _finish(request: Request, pending: mfa.PendingSignIn) -> User | Response:
    """Sign the pending sign-in's account in, reactivating it first when it asked to.

    Reactivation and ``login`` run in one transaction; an account blocked from
    reactivating meanwhile is refused with the 403 sign-in gives a closed account, and
    the pending sign-in is cleared.
    """
    try:
        with transaction.atomic():
            if pending.reactivate and not pending.user.is_active:
                reactivate(pending.user)
            return finish_sign_in(request, pending.user, passed_mfa=True)
    except DomainError:
        mfa.clear_pending(request.session)
        return Response({"detail": closed_account_message()}, status=status.HTTP_403_FORBIDDEN)


# --------------------------------------------------------------------------
# The code steps of signing in
# --------------------------------------------------------------------------
class LoginMfaView(APIView):
    """``POST /auth/login/mfa`` -- finish a sign-in with a code, 200."""

    permission_classes = [AllowAny]
    throttle_classes = [MfaThrottle]

    @extend_schema(request=OtpSerializer, responses={200: UserSerializer})
    def post(self, request: Request) -> Response:
        """Finish the pending sign-in with ``otp`` and answer the ``user`` payload.

        ``otp`` is the authenticator code or one of the account's backup codes.  On a
        right code the account is signed in -- reactivated first, for a sign-in
        ``/auth/reactivate`` started -- the session is marked as having passed the
        second factor, and the answer is the ``user`` payload a sign-in gives.  A wrong
        code is a 400 ``{"otp": [...]}`` and counts against the address's lockout; the
        first of a pending sign-in mails the account.  The fifth wrong code, an expired
        or missing pending sign-in, and one that needs enrolling instead are each a 400
        ``{"detail": "Your sign-in has expired. Enter your email address and password
        again.", "code": "mfa_expired"}``.  A locked-out address is a 429, and an
        account blocked from reactivating meanwhile a 403.  Open to anonymous callers;
        throttled under ``auth_mfa``.
        """
        otp = _otp(request)
        pending = _pending(request, mfa.SignInStep.VERIFY)
        if pending is None:
            return _expired()
        if mfa.check_code(pending.user, otp) is None:
            return _wrong_code(request, pending.user)
        user = _finish(request, pending)
        if isinstance(user, Response):
            return user
        return Response(UserSerializer(user).data)


class LoginMfaEnrollView(APIView):
    """``POST /auth/login/mfa/enroll`` -- start setting up a device while signing in."""

    permission_classes = [AllowAny]
    throttle_classes = [MfaThrottle]

    @extend_schema(request=None, responses={200: EnrollmentSerializer})
    def post(self, request: Request) -> Response:
        """Answer the secret, ``otpauth://`` address, and QR code for a new device.

        Only a pending sign-in whose account has no device may call it.  The secret
        waits in this session until the confirm step checks a code from it; calling
        again replaces it.  Without such a pending sign-in the answer is the 400
        ``mfa_expired`` refusal.  Open to anonymous callers; throttled under
        ``auth_mfa``.
        """
        pending = _pending(request, mfa.SignInStep.ENROLL)
        if pending is None:
            return _expired()
        enrollment = mfa.start_enrollment(request.session, pending.user)
        return Response(EnrollmentSerializer(asdict(enrollment)).data)


class LoginMfaEnrollConfirmView(APIView):
    """``POST /auth/login/mfa/enroll/confirm`` -- confirm the new device and sign in."""

    permission_classes = [AllowAny]
    throttle_classes = [MfaThrottle]

    @extend_schema(request=OtpSerializer, responses={200: EnrolledSignInSerializer})
    def post(self, request: Request) -> Response:
        """Confirm the device with ``otp``, sign in, and answer the user and backup codes.

        The answer is ``{"user": <user payload>, "recovery_codes": [ten codes]}``, the
        only time the codes are shown.  The session is marked as having passed the
        second factor.  A wrong code is a 400 ``{"otp": [...]}`` and counts as at the
        code step; no pending sign-in that is enrolling, or enrollment not started in
        this session, is the 400 ``mfa_expired`` refusal.  Open to anonymous callers;
        throttled under ``auth_mfa``.
        """
        otp = _otp(request)
        pending = _pending(request, mfa.SignInStep.ENROLL)
        if pending is None:
            return _expired()
        try:
            codes = mfa.confirm_enrollment(request.session, pending.user, otp)
        except DomainValidationError:
            return _wrong_code(request, pending.user)
        except DomainError:
            return _expired()
        user = _finish(request, pending)
        if isinstance(user, Response):
            return user
        return Response({"user": UserSerializer(user).data, "recovery_codes": codes})


# --------------------------------------------------------------------------
# The signed-in person's own two-factor sign-in
# --------------------------------------------------------------------------
def _with_code[T](request: Request, action: Callable[[User, str], T], otp: str) -> T:
    """Run ``action`` for the signed-in account with ``otp``, counting a refused code.

    The account's address must not be locked out (429).  A refused code counts against
    it, and the refusal is raised again for the exception handler to answer 400 under
    ``otp``.
    """
    user = signed_in_user(request)
    refuse_if_locked_out(user.email)
    try:
        return action(user, otp)
    except DomainValidationError:
        lockout.record_failure(user.email, code=True)
        raise


def _refused(error: DomainError) -> Response:
    """The 400 ``{"detail": <sentence>}`` a refusal naming no field is answered with."""
    return Response({"detail": error.message}, status=status.HTTP_400_BAD_REQUEST)


class MfaStatusView(APIView):
    """``GET /auth/mfa`` -- whether two-factor sign-in is on, and whether it must be."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: MfaStatusSerializer})
    def get(self, request: Request) -> Response:
        """The caller's two-factor status, as ``MfaStatusSerializer`` describes it."""
        user = signed_in_user(request)
        return Response(
            {
                "enabled": mfa.has_two_factor(user),
                "required_by_role": mfa.mfa_required(user),
                "recovery_codes_remaining": mfa.recovery_codes_remaining(user),
            }
        )


class MfaEnrollView(APIView):
    """``POST /auth/mfa/enroll`` -- start turning two-factor sign-in on."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [MfaThrottle]

    @extend_schema(request=MfaEnrollSerializer, responses={200: EnrollmentSerializer})
    def post(self, request: Request) -> Response:
        """Answer the secret, ``otpauth://`` address, and QR code for a new device.

        The body carries ``current_password``, so a session left open on somebody
        else's screen cannot attach a stranger's phone; a wrong one is a 400 under that
        field.  The secret waits in this session until the confirm step; calling again
        replaces it.  An account whose two-factor sign-in is already on is a 400
        ``{"detail": "Two-factor sign-in is already on for this account."}``.
        Throttled under ``auth_mfa``.
        """
        serializer = MfaEnrollSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        try:
            enrollment = mfa.start_enrollment(request.session, signed_in_user(request))
        except DomainError as error:
            return _refused(error)
        return Response(EnrollmentSerializer(asdict(enrollment)).data)


class MfaEnrollConfirmView(APIView):
    """``POST /auth/mfa/enroll/confirm`` -- confirm the new device, turning it on."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [MfaThrottle]

    @extend_schema(request=OtpSerializer, responses={200: RecoveryCodesSerializer})
    def post(self, request: Request) -> Response:
        """Confirm the device with ``otp`` and answer ``{"recovery_codes": [...]}``.

        Two-factor sign-in is on from then, the session is marked as having passed it,
        and the account is mailed.  A wrong code is a 400 ``{"otp": [...]}`` and counts
        against the address's lockout; enrollment not started in this session, or
        already on, is a 400 ``{"detail": ...}``.  Throttled under ``auth_mfa``.
        """
        otp = _otp(request)
        session = request.session
        try:
            codes = _with_code(
                request, lambda user, code: mfa.confirm_enrollment(session, user, code), otp
            )
        except DomainValidationError:
            raise
        except DomainError as error:
            return _refused(error)
        mfa.mark_session(request.session, signed_in_user(request))
        return Response({"recovery_codes": codes})


class MfaRecoveryCodesView(APIView):
    """``POST /auth/mfa/recovery-codes`` -- replace the backup codes."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [MfaThrottle]

    @extend_schema(request=OtpSerializer, responses={200: RecoveryCodesSerializer})
    def post(self, request: Request) -> Response:
        """Replace every backup code, given a current ``otp``, and answer the new set.

        ``otp`` may be an authenticator code or one of the codes being replaced.  A
        wrong code is a 400 ``{"otp": [...]}`` and counts against the address's
        lockout; an account without two-factor sign-in is a 400 ``{"detail": ...}``.
        Throttled under ``auth_mfa``.
        """
        otp = _otp(request)
        try:
            codes = _with_code(request, mfa.regenerate_recovery_codes, otp)
        except DomainValidationError:
            raise
        except DomainError as error:
            return _refused(error)
        return Response({"recovery_codes": codes})


class MfaDisableView(APIView):
    """``POST /auth/mfa/disable`` -- turn two-factor sign-in off, 204."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [MfaThrottle]

    @extend_schema(
        request=MfaDisableSerializer,
        responses={204: OpenApiResponse(description="Two-factor sign-in is off; no body.")},
    )
    def post(self, request: Request) -> Response:
        """Turn the caller's two-factor sign-in off, given the password and a code.

        The body carries ``current_password`` and ``otp``.  A role that requires
        two-factor sign-in is a 403 ``{"detail": "Your role requires two-factor sign-in,
        so it cannot be turned off. ..."}`` whatever the body; a wrong password is a 400
        under ``current_password``; a wrong code a 400 under ``otp``, counted against
        the address's lockout; and an account without two-factor sign-in a 400
        ``{"detail": ...}``.  Once it is off the session's second-factor mark is taken
        away too, so a role that requires it later asks this session for it again.
        Throttled under ``auth_mfa``.
        """
        mfa.refuse_if_required(signed_in_user(request))
        serializer = MfaDisableSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        try:
            _with_code(request, mfa.disable_two_factor, serializer.validated_data["otp"])
        except DomainValidationError:
            raise
        except DomainError as error:
            return _refused(error)
        mfa.unmark_session(request.session)
        return Response(status=status.HTTP_204_NO_CONTENT)
