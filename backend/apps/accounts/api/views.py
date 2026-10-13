"""Auth and users-admin endpoints."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import QuerySet
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import NotAuthenticated
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api.account_actions import (
    block_for,
    deactivate_for,
    reactivate_for,
    require_new_password_for,
    unblock_for,
)
from apps.accounts.api.filters import UserFilter
from apps.accounts.api.serializers import (
    AccountChangeSerializer,
    AdminUserDetailSerializer,
    AdminUserSerializer,
    DeactivateSerializer,
    EmailChangeSerializer,
    EmailChangeUndoneSerializer,
    EmailChangeUndoSerializer,
    EmailVerifiedSerializer,
    EmailVerifySerializer,
    LoginSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetSerializer,
    RegisterSerializer,
    RoleSerializer,
    SendPasswordResetResultSerializer,
    UserSerializer,
    VerificationSentSerializer,
)
from apps.accounts.email_change import (
    follow_verification_link,
    request_email_change,
    send_email_change_link,
    undo_email_change,
)
from apps.accounts.models import AccountChange, AccountKind, User
from apps.accounts.notices import send_password_changed_notice
from apps.accounts.permissions import IsUserAdmin
from apps.accounts.roles import ROLE_DESCRIPTIONS
from apps.accounts.services import (
    DonorPasswordRequiredError,
    clear_email_bounce,
    confirm_email_address,
    is_donor,
    may_edit_protected_fields,
    replace_password,
    send_email_verification,
    send_password_reset_email,
)
from apps.accounts.status import (
    closed_account_message,
    deactivate_own_account,
    deactivated_account,
    reactivate_own_account,
)
from apps.accounts.throttling import (
    EmailChangeThrottle,
    EmailVerifyResendThrottle,
    EmailVerifyThrottle,
    LoginThrottle,
    PasswordResetThrottle,
    RegisterThrottle,
)
from apps.members.services import (
    refuse_tombstone_change,
    register_member,
    restore_terms,
    suspend_terms,
    with_membership,
)
from apps.payments.renewals.mandates import cancel_all_mandates
from caldart import audit
from caldart.exceptions import DomainError
from caldart.mail import (
    MailRefusedError,
    log_refusal,
    send_after_response,
    send_logging_refusal,
    send_on_commit,
)

#: What every refused login says.  It names neither half of the credentials, and
#: a deactivated account whose password was wrong is answered with it too, so a
#: guess can never be used to find out which addresses are registered.
WRONG_CREDENTIALS_MESSAGE = "Incorrect email address or password."

#: What a deactivated account is told, and only once its password has matched.
DEACTIVATED_MESSAGE = "This account is deactivated. You can reactivate it."

#: The ``code`` a refused sign-in carries for a deactivated account, which tells the
#: portal to offer reactivation.
DEACTIVATED_CODE = "deactivated"

#: The ``code`` a verification answers with when the link opens a donor's account and
#: no password came with it, which tells the portal to ask for one.
DONOR_UPGRADE_CODE = "password_required"

#: What the user administrator is told when asking to mail a donor a password or
#: verification link: a donor cannot sign in, so neither link would lead anywhere.
DONOR_RESET_REFUSED = "A donor cannot sign in, so no reset email was sent."
DONOR_VERIFICATION_REFUSED = "A donor cannot sign in, so no verification message was sent."

#: What the user administrator is told when asking to mail their own account a reset
#: link: their own password is changed on the Change password page.
SELF_RESET_REFUSED = (
    "You cannot send a password reset to your own account. Use Change password instead."
)

#: What the user administrator is told when the account holds a role they lack: a reset
#: link reaches the account's owner, but the account-edit guard covers it all the same.
RESET_ROLES_REFUSED = (
    "You cannot send a password reset to an account that holds roles you do not hold."
)

#: What the user administrator is told when the mail server refuses a message they
#: asked to send, so they know it did not go and where to see the attempt.
MAIL_REFUSED = (
    "The mail server did not accept the message. "
    "A system administrator can see the attempt on the Sent emails page."
)

#: What **Require a new password** has done once it goes through, before what was mailed.
CREDENTIAL_RESET_DONE = "The old password no longer works and every session is ended."

#: What **Require a new password** answers when the mail server refuses the reset email:
#: the password is shut out regardless, and pressing it again mails a fresh link.
CREDENTIAL_MAIL_REFUSED = (
    "The old password no longer works and every session is ended, but the mail server "
    "did not accept the reset email. "
    "A system administrator can see the attempt on the Sent emails page; "
    "press Require a new password again once it is fixed."
)


def signed_in_user(request: Request) -> User:
    """The account behind ``request``.

    For handlers whose permission classes have already turned an anonymous caller
    away.  Raises ``NotAuthenticated`` if one reaches it anyway; the project's
    exception handler renders that as 401, where DRF alone would answer 403 because
    session authentication offers no ``WWW-Authenticate`` challenge.
    """
    user = request.user
    if isinstance(user, AnonymousUser):
        raise NotAuthenticated
    return user


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    """``GET /auth/csrf`` -- 204, sets the ``csrftoken`` cookie."""

    permission_classes = [AllowAny]

    @extend_schema(
        request=None,
        responses={204: OpenApiResponse(description="The CSRF cookie is set; no body.")},
    )
    def get(self, request: Request) -> Response:
        """Answer 204 with no body, having set the CSRF cookie on the response.

        Open to anonymous callers: the SPA calls it once before its first unsafe
        request so it has a token to echo back.
        """
        get_token(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class RegisterView(APIView):
    """``POST /auth/register`` -- open an account, or tell the owner they have one."""

    permission_classes = [AllowAny]
    throttle_classes = [RegisterThrottle]

    @extend_schema(request=RegisterSerializer, responses={202: VerificationSentSerializer})
    def post(self, request: Request) -> Response:
        """Register the posted address and answer 202, the same way whoever holds it.

        The body carries ``email``, ``password``, ``first_name``, ``last_name``, and
        ``kind`` (``member``, the default, or ``friend``).  Every address that parses is
        answered 202 ``{"detail": "We sent a message to <address>. Follow the link in it
        to continue."}``, with nobody signed in, so the answer never says whether the
        address has an account.  What is done, and the message the address is mailed
        once the answer has gone, is :func:`apps.members.services.register_member`'s: a
        new account and its verification link, a donor's upgrade link, or word that the
        address already has an account.  A missing field, an address that does not
        parse, an unknown ``kind``, or a password Django's validators reject is a 400
        naming the field, judged from the body alone.  Open to anonymous callers and
        throttled under the ``auth_register`` scope.
        """
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        registration = register_member(
            email=data["email"],
            password=data["password"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            kind=AccountKind(data["kind"]),
        )
        response = Response(
            {"detail": registration_sent(data["email"])}, status=status.HTTP_202_ACCEPTED
        )
        send_after_response(
            response,
            registration.send,
            what=f"the registration message for account {registration.user.pk}",
        )
        return response


def registration_sent(email: str) -> str:
    """What a registration is answered with for ``email``, whoever holds the address."""
    return f"We sent a message to {email}. Follow the link in it to continue."


class LoginView(APIView):
    """``POST /auth/login`` -- session login by email + password."""

    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]

    @extend_schema(request=LoginSerializer, responses={200: UserSerializer})
    def post(self, request: Request) -> Response:
        """Sign in by ``email`` and ``password``, answering 200 with the ``user`` payload.

        Open to anonymous callers and throttled under the ``auth_login`` scope.  Wrong
        credentials are a 400 with "Incorrect email address or password."  A deactivated
        account is answered with that same 400 unless the password is correct, in which
        case it is a 403 ``{"detail": "This account is deactivated. You can reactivate
        it.", "code": "deactivated"}`` -- so only somebody who already knows the password
        learns that the address belongs to a deactivated account, and can then post the
        same credentials to ``/auth/reactivate``.  An account a user administrator has
        blocked from reactivating is instead a 403 ``{"detail": "This account has been
        closed. Contact <organization name> to reopen it."}``, again only once the
        password has matched, and carries no ``code``, so nothing offers reactivation.
        A donor cannot sign in at all: whatever the password, the answer is the same
        400 as wrong credentials.
        """
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]
        user = authenticate(request, username=email, password=password)
        if user is None:
            # `authenticate` also returns None for a deactivated account and for a
            # donor (`apps.accounts.backends`), so look up a deactivated account;
            # its password still has to match before we say so.
            deactivated = deactivated_account(email, password)
            if deactivated is not None and deactivated.reactivation_blocked:
                return _closed()
            if deactivated is not None:
                return Response(
                    {"detail": DEACTIVATED_MESSAGE, "code": DEACTIVATED_CODE},
                    status=status.HTTP_403_FORBIDDEN,
                )
            return Response(
                {"detail": WRONG_CREDENTIALS_MESSAGE},
                status=status.HTTP_400_BAD_REQUEST,
            )
        login(request, user)
        return Response(UserSerializer(user).data)


class LogoutView(APIView):
    """``POST /auth/logout`` -- 204."""

    permission_classes = [AllowAny]

    @extend_schema(
        request=None,
        responses={204: OpenApiResponse(description="The session is over; no body.")},
    )
    def post(self, request: Request) -> Response:
        """End the session and answer 204.

        Open to anonymous callers, and answers 204 just the same when nobody was
        signed in.
        """
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    """``GET /auth/me`` -- the signed-in user, 401 when anonymous."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: UserSerializer})
    def get(self, request: Request) -> Response:
        """The signed-in account as the ``user`` payload, 200.

        An anonymous caller gets 401.
        """
        return Response(UserSerializer(signed_in_user(request)).data)


#: The 401 a password change gets when the stored password moved under it.
CHANGED_ELSEWHERE = "This account's password was changed elsewhere. Sign in again."


class PasswordChangeView(APIView):
    """``POST /auth/password/change`` -- 204, session kept alive."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=PasswordChangeSerializer,
        responses={204: OpenApiResponse(description="The password is replaced; no body.")},
    )
    def post(self, request: Request) -> Response:
        """Replace the signed-in account's password and answer 204.

        The body carries ``current_password`` and ``new_password``.  A wrong current
        password or a new one Django's validators reject is a 400 naming the field.  The
        session survives the change, so the caller stays signed in, while every other
        session of the account ends.  An anonymous caller gets 401.  So does a change
        whose stored password moved after the request checked the current one (another
        change, a reset, or ``create_admin`` clearing it): nothing is written, the session
        is left as it was, and the 401 carries :data:`CHANGED_ELSEWHERE`.  A change that
        goes through is audited as ``account.password_change`` and the account's address
        is mailed a notice that the password was changed
        (:func:`apps.accounts.notices.send_password_changed_notice`); a mail server that
        refuses it is logged and the answer is unchanged.
        """
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = signed_in_user(request)
        if not replace_password(user, serializer.validated_data["new_password"]):
            raise NotAuthenticated(CHANGED_ELSEWHERE)
        # Rotating the password rotates the session auth hash; without this the
        # caller is logged out by their own request.
        update_session_auth_hash(request, user)
        audit.record(audit.ACCOUNT_PASSWORD_CHANGE, actor=user, target=user, reset=False)
        send_logging_refusal(
            lambda: send_password_changed_notice(user),
            what=f"the password change notice for account {user.pk}",
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetView(APIView):
    """``POST /auth/password/reset`` -- 204 always.

    The answer never depends on whether the address is registered, so the
    endpoint cannot be used to enumerate members.
    """

    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetThrottle]

    @extend_schema(
        request=PasswordResetSerializer,
        responses={204: OpenApiResponse(description="Answered the same way for any address.")},
    )
    def post(self, request: Request) -> Response:
        """Mail a reset link to the posted ``email`` and answer 204.

        Open to anonymous callers and throttled under the ``auth_password_reset`` scope.
        An unregistered address, a donor's, or one a user administrator has blocked from
        reactivating is answered 204 with no mail sent, so the endpoint cannot be used to
        enumerate members.  A deactivated account is mailed the link, since completing
        the reset reactivates it.  An account
        that has never set a password is mailed the link like any other.  A malformed
        address is a 400.  The message is rendered and sent only once the answer has gone
        (``caldart.mail.send_after_response``), so the time the request takes does not
        depend on whether there was anybody to mail.  A mail server that refuses the
        message changes nothing: the failed send is in the email log, and the refusal is
        logged.
        """
        serializer = PasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(email__iexact=serializer.validated_data["email"]).first()
        response = Response(status=status.HTTP_204_NO_CONTENT)
        if user is not None:
            send_after_response(
                response,
                lambda: send_password_reset_email(user, request=request),
                what=f"the password reset for account {user.pk}",
            )
        return response


class PasswordResetConfirmView(APIView):
    """``POST /auth/password/reset/confirm`` -- set the new password, 204."""

    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetThrottle]

    @extend_schema(
        request=PasswordResetConfirmSerializer,
        responses={204: OpenApiResponse(description="The new password is set; no body.")},
    )
    def post(self, request: Request) -> Response:
        """Set the new password the reset link authorizes, and answer 204.

        The body carries ``uid``, ``token``, and ``new_password``.  Open to anonymous
        callers and throttled under the ``auth_password_reset`` scope.  An unusable or
        spent link is a 400 under ``token``, and a password Django's validators reject a
        400 under ``new_password``.  The link was mailed to the account's address, so
        using it also marks an unverified address verified.  A deactivated account is
        reactivated exactly as ``/auth/reactivate`` does it -- the person proved the
        address and chose to come back -- though nobody is signed in: the new password
        does that.  A link for an account a user administrator has blocked from
        reactivating is a 400 under ``token`` with "This account has been closed. Contact
        <organization name> to reopen it.", and nothing changes.  A link whose account's
        password moved after the link was checked (another reset, or ``create_admin``
        clearing it) is spent: a 400 under ``token`` like any other spent link, and
        nothing changes.

        A reset that replaces a password the account already had is audited as
        ``account.password_change`` with ``reset=true``, and the account's address is
        mailed a notice that the password was changed; setting the first password of an
        account that had none, through an invitation or after an undone change of
        address, is neither.
        """
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        had_password = user.has_usable_password()
        try:
            with transaction.atomic():
                if not replace_password(user, serializer.validated_data["new_password"]):
                    return Response(
                        {"token": [PasswordResetConfirmSerializer.INVALID_LINK]},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                confirm_email_address(user)
                if not user.is_active:
                    reactivate(user)
                if had_password:
                    audit.record(audit.ACCOUNT_PASSWORD_CHANGE, actor=user, target=user, reset=True)
                    send_on_commit(
                        lambda: send_password_changed_notice(user),
                        what=f"the password change notice for account {user.pk}",
                    )
        except DomainError:
            # Blocked after the link was checked: the whole reset is rolled back.
            return Response(
                {"token": [closed_account_message()]}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------
# Deactivating and reactivating your own account
# --------------------------------------------------------------------------
def _closed() -> Response:
    """The 403 the owner of an account blocked from reactivating is answered with."""
    return Response({"detail": closed_account_message()}, status=status.HTTP_403_FORBIDDEN)


def _locked(user: User) -> User:
    """Lock ``user``'s row until the transaction ends, and read the whole of it afresh.

    Two requests racing to deactivate or reactivate one account run one after the
    other, and the second sees what the first wrote -- the active flag and the
    reactivation block alike, so a block set after ``user`` was read still holds.
    """
    return User.objects.select_for_update().get(pk=user.pk)


@transaction.atomic
def deactivate(user: User) -> None:
    """Deactivate ``user`` at their own request, withdrawing everything that runs on.

    The account is refused or deactivated by ``deactivate_own_account`` first, so a
    refusal changes nothing; then every mandate is canceled or discarded and every
    term with time left is suspended.  Raises the ``DomainError`` a refusal raises.
    An account already inactive when its row is locked is left alone.
    """
    locked = _locked(user)
    if not locked.is_active:
        return
    deactivate_own_account(locked)
    cancel_all_mandates(locked)
    suspend_terms(locked)


@transaction.atomic
def reactivate(user: User) -> bool:
    """Bring ``user``'s deactivated account back, with any membership still running.

    Kind and roles are untouched; each suspended term is active again, or expired if
    it ran out meanwhile.  Canceled mandates stay canceled.  ``False``, changing
    nothing, when the account is already active once its row is locked; ``True``
    otherwise, when ``user`` is read again so the caller holds the account as stored.
    The block is read from the locked row, so an account blocked after ``user`` was
    loaded is refused: raises the ``DomainError`` ``reactivate_own_account`` raises.
    """
    locked = _locked(user)
    if locked.is_active:
        return False
    reactivate_own_account(locked)
    restore_terms(locked)
    user.refresh_from_db()
    return True


class DeactivateView(APIView):
    """``POST /auth/deactivate`` -- deactivate your own account, 204."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=DeactivateSerializer,
        responses={204: OpenApiResponse(description="Deactivated and signed out; no body.")},
    )
    def post(self, request: Request) -> Response:
        """Deactivate the signed-in account, end the session, and answer 204.

        The body carries ``current_password``; a wrong one is a 400 under that field.
        Every automatic renewal and recurring donation is canceled (a pending one is
        discarded), every membership term with time left is suspended, the account is
        saved inactive, and the change is recorded as ``account.deactivate`` with
        ``self_service=true``.  A system administrator is a 400 ``{"detail": "A system
        administrator cannot deactivate their own account."}`` and a donor a 400 too;
        neither changes anything.  An anonymous caller gets 401.
        """
        serializer = DeactivateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        try:
            deactivate(signed_in_user(request))
        except DomainError as error:
            return Response({"detail": error.message}, status=status.HTTP_400_BAD_REQUEST)
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReactivateView(APIView):
    """``POST /auth/reactivate`` -- bring back a deactivated account and sign in, 200."""

    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]

    @extend_schema(request=LoginSerializer, responses={200: UserSerializer})
    def post(self, request: Request) -> Response:
        """Reactivate the account ``email`` and ``password`` name, sign it in, answer 200.

        Open to anonymous callers and throttled under the ``auth_login`` scope, like a
        sign-in.  Only a deactivated account whose password matches is reactivated: its
        kind and roles are as they were, each suspended membership term is active
        again (or expired, if it ran out meanwhile), the change is recorded as
        ``account.activate`` with ``self_service=true``, and an unverified address is
        mailed a verification link.  The answer is the ``user`` payload.  An account a
        user administrator has blocked from reactivating, whose password matched, is a
        403 ``{"detail": "This account has been closed. Contact <organization name> to
        reopen it."}`` and stays deactivated.  Anything else -- a wrong password, an
        active account, an unknown address, a donor -- is the 400 "Incorrect email
        address or password." a sign-in gives.
        """
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = deactivated_account(
            serializer.validated_data["email"], serializer.validated_data["password"]
        )
        if user is not None and user.reactivation_blocked:
            return _closed()
        try:
            is_reactivated = user is not None and reactivate(user)
        except DomainError:
            # Blocked between the read above and the row lock.
            return _closed()
        if user is None or not is_reactivated:
            return Response(
                {"detail": WRONG_CREDENTIALS_MESSAGE},
                status=status.HTTP_400_BAD_REQUEST,
            )
        login(request, user)
        return Response(UserSerializer(user).data)


# --------------------------------------------------------------------------
# Email verification and change
# --------------------------------------------------------------------------
def _verification_sent(user: User) -> Response:
    """The 202 naming ``user``'s address that a verification link was mailed to."""
    return Response(
        {"detail": f"Verification message sent to {user.email}."},
        status=status.HTTP_202_ACCEPTED,
    )


class EmailVerifyView(APIView):
    """``POST /auth/email/verify`` -- follow a verification link, 200."""

    permission_classes = [AllowAny]
    throttle_classes = [EmailVerifyThrottle]

    @extend_schema(request=EmailVerifySerializer, responses={200: EmailVerifiedSerializer})
    def post(self, request: Request) -> Response:
        """Follow the link the posted ``token`` came from, answering the address proved.

        Open to anonymous callers, since the link may be opened in a browser that is
        not signed in, and throttled under the ``auth_verify`` scope.  The answer is 200
        ``{"email": <address>, "changed": <bool>}``, also for a link followed a second
        time.  A verification link stamps the account verified; a link mailed to a new
        address completes that change of address
        (:func:`apps.accounts.email_change.complete_email_change`), and ``changed`` is
        then true.  A token that is forged, expired, for a deactivated or deleted
        account, for an address the account no longer holds, or for a change of address
        since replaced or undone is a 400 ``{"token": ["That verification link is invalid
        or has expired."]}``; a change whose address another account has taken meanwhile
        is a 400 ``{"token": ["Another account already uses that email address."]}``.

        A link that opens a donor's account also needs ``password``, the one the account
        will sign in with, chosen by whoever follows the link.  Without it the answer is
        400 ``{"password": ["Choose a password to finish opening your account."], "code":
        "password_required"}`` and nothing changes; a password Django's validators
        reject is a 400 ``{"password": [...]}``.  ``password`` is ignored for every other
        link.  Nobody is signed in either way.
        """
        serializer = EmailVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            followed = follow_verification_link(
                serializer.validated_data["token"],
                password=serializer.validated_data["password"],
            )
        except DonorPasswordRequiredError as error:
            return Response(
                {"password": [str(error)], "code": DONOR_UPGRADE_CODE},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DjangoValidationError as error:
            return Response({"password": list(error.messages)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(EmailVerifiedSerializer(followed).data)


class EmailVerifyResendView(APIView):
    """``POST /auth/email/resend`` -- mail the signed-in user a fresh link, 202."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [EmailVerifyResendThrottle]

    @extend_schema(request=None, responses={202: VerificationSentSerializer})
    def post(self, request: Request) -> Response:
        """Mail the signed-in account a fresh link and answer 202.

        While a change of address is waiting, the link that completes it goes to the
        pending address (:func:`apps.accounts.email_change.send_email_change_link`);
        otherwise a verification link goes to the account's own address.  The answer is
        ``{"detail": "Verification message sent to <address>."}``, naming the address
        mailed.  A verified address with no change waiting is a 400 with "Your email
        address is already verified." and nothing is mailed.  A mail server that refuses
        the message changes nothing in the answer: the failed send is in the email log,
        and the refusal is logged.  Throttled under the ``auth_verify_resend`` scope; an
        anonymous caller gets 401.
        """
        user = signed_in_user(request)
        if user.pending_email != "":
            send_logging_refusal(
                lambda: send_email_change_link(user, requested_by=user.pk),
                what=f"the email change link for account {user.pk}",
            )
            return Response(
                {"detail": f"Verification message sent to {user.pending_email}."},
                status=status.HTTP_202_ACCEPTED,
            )
        if user.email_verified:
            return Response(
                {"detail": "Your email address is already verified."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        send_logging_refusal(
            lambda: send_email_verification(user),
            what=f"the email verification for account {user.pk}",
        )
        return _verification_sent(user)


class EmailChangeView(APIView):
    """``POST /auth/email/change`` -- ask to change the caller's own address, 200."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [EmailChangeThrottle]

    @extend_schema(request=EmailChangeSerializer, responses={200: UserSerializer})
    def post(self, request: Request) -> Response:
        """Ask to move the signed-in account to the posted ``email``; answer the payload.

        The body carries ``email`` and ``current_password``.  A wrong password and the
        account's own address are each a 400 naming the field, the password checked
        first, and so, against ``email``, is any change while the account keeps a
        recovery address after a change of address.  Nothing about signing in changes
        yet: the address becomes the account's ``pending_email``, the new address is
        mailed a link that completes the change, and the current address, when verified
        (or the recovery address), a notice with a link that undoes it
        (:func:`apps.accounts.email_change.request_email_change`).  The answer is the
        ``user`` payload, ``email`` as it was and ``pending_email`` the address asked
        for.  An address another account holds is answered exactly the same way, so
        the endpoint cannot be used to find out who has an account, but nothing is
        stored and nothing is mailed.  The request is recorded in the audit log as the
        account's own ``account.email_change_request``.  Throttled under the
        ``auth_email_change`` scope; an anonymous caller gets 401.
        """
        serializer = EmailChangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = signed_in_user(request)
        address = serializer.validated_data["email"]
        request_email_change(user, user, address, quiet_if_taken=True)
        payload = dict(UserSerializer(user).data)
        payload["pending_email"] = address
        return Response(payload)


class EmailChangeUndoView(APIView):
    """``POST /auth/email/undo`` -- follow a link that undoes a change of address."""

    permission_classes = [AllowAny]
    throttle_classes = [EmailVerifyThrottle]

    @extend_schema(request=EmailChangeUndoSerializer, responses={200: EmailChangeUndoneSerializer})
    def post(self, request: Request) -> Response:
        """Undo the change of address the posted ``token`` was mailed about; answer 200.

        Open to anonymous callers, since the link is followed from the address the
        account had, and throttled under the ``auth_verify`` scope.  What is undone is
        :func:`apps.accounts.email_change.undo_email_change`'s: the address put back if
        it had changed, any change still waiting dropped, every session ended, the
        password made unusable, and a password reset link mailed to the address.  The
        answer is ``{"email": <the account's address>, "taken": <bool>}``; ``taken`` is
        true when another account held the address so it could not be put back, and the
        account was only secured.  A token that is forged, expired, for no account or a
        donor's, spent by an earlier undo, or mailed to an address other than the one
        the account keeps for recovery is a 400 ``{"token": ["That link is invalid, has
        expired, or has been used."]}``.
        """
        serializer = EmailChangeUndoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        undone = undo_email_change(serializer.validated_data["token"])
        user = undone["user"]
        if request.user.is_authenticated and request.user.pk == user.pk:
            logout(request)
        return Response({"email": user.email, "taken": undone["taken"]})


class RolesView(APIView):
    """``GET /roles`` -- the role catalog, for any authenticated caller."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: RoleSerializer(many=True)})
    def get(self, request: Request) -> Response:
        """Every role as ``{"slug", "description"}``, least privileged first, 200.

        Any authenticated caller may read it; an anonymous one gets 401.  The list is
        not paginated.
        """
        data = [{"slug": slug, "description": desc} for slug, desc in ROLE_DESCRIPTIONS.items()]
        # djangorestframework-stubs does not model `many=True`, which wraps this
        # serializer in a ListSerializer taking the whole list.
        return Response(RoleSerializer(data, many=True).data)  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# Users admin -- user_admin, and system_admin by implication
# --------------------------------------------------------------------------
def admin_user_queryset() -> QuerySet[User]:
    """Every user, with the rows the ``user`` payload needs already loaded.

    The membership annotations are worked out for the date this is called, so
    both views below build the queryset per request rather than once at import.
    """
    return with_membership(
        User.objects.select_related("profile", "profile__dart").prefetch_related("groups")
    )


class AdminUserListView(generics.ListAPIView[User]):
    """``GET /admin/users?search=&role=&is_active=&kind=&email_bounced=`` -- paginated."""

    permission_classes = [IsUserAdmin]
    serializer_class = AdminUserSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = UserFilter
    search_fields = ["first_name", "last_name", "email"]
    ordering_fields = ["last_name", "first_name", "email", "is_active", "created_at"]
    ordering = ["last_name", "first_name", "email"]

    def get_queryset(self) -> QuerySet[User]:
        """Every account, annotated for this request's date."""
        return admin_user_queryset()


class AdminUserDetailView(generics.RetrieveUpdateAPIView[User]):
    """``GET|PATCH /admin/users/{id}``."""

    permission_classes = [IsUserAdmin]
    serializer_class = AdminUserDetailSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self) -> QuerySet[User]:
        """Every account, annotated for this request's date."""
        return admin_user_queryset()

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """200 with the account as saved, or 400 for a tombstone whatever the body holds.

        A tombstone keeps a deleted member's payments under its own name, address, and
        lack of roles, so ``PATCH`` on one is 400 ``{"detail": "This record keeps a
        deleted member's payments in the books and cannot be changed."}``, audited as
        ``account.update`` with the reason ``tombstone``.  Any other account is DRF's
        partial update through ``AdminUserDetailSerializer``.
        """
        try:
            refuse_tombstone_change(
                signed_in_user(request), self.get_object(), audit.ACCOUNT_UPDATE
            )
        except DomainError as error:
            return Response({"detail": error.message}, status=status.HTTP_400_BAD_REQUEST)
        return super().update(request, *args, **kwargs)


def _mail_refused(what: str, refusal: MailRefusedError) -> Response:
    """Log ``refusal``, naming ``what``, and answer 503.

    The answer, ``{"detail": MAIL_REFUSED}``, is for a send the user administrator asked
    for, who must know it did not go.
    """
    log_refusal(what, refusal)
    return Response({"detail": MAIL_REFUSED}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class AdminUserHistoryView(generics.ListAPIView[AccountChange]):
    """``GET /admin/users/{id}/history`` -- the account's role and status changes."""

    permission_classes = [IsUserAdmin]
    serializer_class = AccountChangeSerializer
    pagination_class = None

    def get_queryset(self) -> QuerySet[AccountChange]:
        """The changes to the account in the URL, newest first, with each actor joined.

        Answers 404 when no account has that id, rather than an empty history.
        """
        user = generics.get_object_or_404(User, pk=self.kwargs["pk"])
        return user.account_changes.select_related("changed_by")


class AdminUserSendPasswordResetView(APIView):
    """``POST /admin/users/{id}/send-password-reset``."""

    permission_classes = [IsUserAdmin]

    @extend_schema(request=None, responses={200: SendPasswordResetResultSerializer})
    def post(self, request: Request, pk: int) -> Response:
        """Mail the account with id ``pk`` a reset link, and answer 200 with a message.

        Restricted to ``user_admin``, and to ``system_admin`` by implication; anyone
        else gets 403 and an unknown ``pk`` gets 404.  Refused with a 400, in this order
        and mailing nothing: a donor, who cannot sign in ("A donor cannot sign in, so no
        reset email was sent."); your own account (:data:`SELF_RESET_REFUSED`); an
        account holding roles you do not hold (:data:`RESET_ROLES_REFUSED`, the
        account-edit guard); and an account with nobody to mail, a deactivated one or one
        with no email address ("That account is deactivated, so no reset email was
        sent.").  Both the send and the refusals are recorded in the audit log, a refusal
        with the reason ``donor_account``, ``own_account``, ``roles_not_held``, or
        ``inactive_account``.  A mail server that refuses the
        message is a 503 with ``MAIL_REFUSED``: the failed send is in the email log, the
        refusal is logged, and nothing is recorded in the audit log.
        """
        actor = signed_in_user(request)
        user = generics.get_object_or_404(User, pk=pk)
        if is_donor(user):
            audit.refuse(
                audit.PASSWORD_RESET_ADMIN_SENT,
                actor=actor,
                target=user,
                reason=audit.REASON_DONOR_ACCOUNT,
            )
            return Response({"detail": DONOR_RESET_REFUSED}, status=status.HTTP_400_BAD_REQUEST)
        if user.pk == actor.pk:
            audit.refuse(
                audit.PASSWORD_RESET_ADMIN_SENT,
                actor=actor,
                target=user,
                reason=audit.REASON_OWN_ACCOUNT,
            )
            return Response({"detail": SELF_RESET_REFUSED}, status=status.HTTP_400_BAD_REQUEST)
        if not may_edit_protected_fields(actor, user):
            audit.refuse(
                audit.PASSWORD_RESET_ADMIN_SENT,
                actor=actor,
                target=user,
                reason=audit.REASON_ROLES_NOT_HELD,
            )
            return Response({"detail": RESET_ROLES_REFUSED}, status=status.HTTP_400_BAD_REQUEST)
        # A reset reactivates a deactivated account, which is the person's own choice
        # to make: the administrator's send stays refused for one.
        try:
            sent = user.is_active and send_password_reset_email(user, request=request)
        except MailRefusedError as refusal:
            return _mail_refused(f"the password reset for account {user.pk}", refusal)
        if not sent:
            audit.refuse(
                audit.PASSWORD_RESET_ADMIN_SENT,
                actor=actor,
                target=user,
                reason=audit.REASON_INACTIVE_ACCOUNT,
            )
            return Response(
                {"detail": "That account is deactivated, so no reset email was sent."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        audit.record(audit.PASSWORD_RESET_ADMIN_SENT, actor=actor, target=user)
        return Response({"detail": f"Password reset email sent to {user.email}."})


class AdminUserRequireNewPasswordView(APIView):
    """``POST /admin/users/{id}/require-new-password``."""

    permission_classes = [IsUserAdmin]

    @extend_schema(request=None, responses={200: SendPasswordResetResultSerializer})
    def post(self, request: Request, pk: int) -> Response:
        """Shut the account ``pk``'s password out, end its sessions, mail a reset link.

        Restricted to ``user_admin``, and to ``system_admin`` by implication; anyone
        else gets 403 and an unknown ``pk`` gets 404.  The account's password becomes
        unusable and every session signed in to it is ended
        (:func:`apps.accounts.api.account_actions.require_new_password_for`), so the old
        password neither signs in nor reactivates; then the reset email, in the wording
        that says an administrator required a new password, goes to the account's
        address.  The answer is 200 ``{"detail": "The old password no
        longer works and every session is ended. A password reset email went to
        <address>."}``.  A deactivated account stays deactivated and is mailed the
        link, which reactivates it when its owner chooses a password, as any reset
        does.  A blocked account is mailed nothing, since its link would be refused,
        and the detail ends "The account is blocked from reactivating, so no reset
        email was sent."  A donor (a tombstone among them), your own account, and an
        account holding roles you do not hold are each a 400 ``{"detail": ...}`` and
        change nothing.  A mail server that refuses the message is a 503 with
        :data:`CREDENTIAL_MAIL_REFUSED`: the password and sessions stay as the action
        left them, the failed send is in the email log, and the refusal is logged.
        """
        actor = signed_in_user(request)
        target = generics.get_object_or_404(User, pk=pk)
        try:
            user = require_new_password_for(actor, target)
        except DomainError as error:
            return Response({"detail": error.message}, status=status.HTTP_400_BAD_REQUEST)
        try:
            sent = send_password_reset_email(user, request=request, required=True)
        except MailRefusedError as refusal:
            log_refusal(f"the password reset for account {user.pk}", refusal)
            return Response(
                {"detail": CREDENTIAL_MAIL_REFUSED},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        if sent:
            outcome = f"A password reset email went to {user.email}."
        elif user.reactivation_blocked:
            outcome = "The account is blocked from reactivating, so no reset email was sent."
        else:
            outcome = "The account has no email address, so no reset email was sent."
        return Response({"detail": f"{CREDENTIAL_RESET_DONE} {outcome}"})


class AdminUserSendEmailVerificationView(APIView):
    """``POST /admin/users/{id}/send-email-verification``."""

    permission_classes = [IsUserAdmin]

    @extend_schema(request=None, responses={202: VerificationSentSerializer})
    def post(self, request: Request, pk: int) -> Response:
        """Mail the account with id ``pk`` a verification link, and answer 202.

        Restricted to ``user_admin``, and to ``system_admin`` by implication; anyone
        else gets 403 and an unknown ``pk`` gets 404.  The answer is ``{"detail":
        "Verification message sent to <address>."}``, and the send is recorded in the
        audit log as ``email_verification.admin_sent``.  An address that is already
        verified is a 400 with "That address is already verified.", and a deactivated
        account, whose link could never be used, a 400 with "That account is
        deactivated, so no verification message was sent."; a donor, who cannot sign
        in, a 400 with "A donor cannot sign in, so no verification message was sent.";
        none of them mails anything.  A mail server that refuses the message is a 503
        with ``MAIL_REFUSED``: the failed send is in the email log, the refusal is
        logged, and nothing is recorded in the audit log.
        """
        actor = signed_in_user(request)
        user = generics.get_object_or_404(User, pk=pk)
        if is_donor(user):
            return Response(
                {"detail": DONOR_VERIFICATION_REFUSED}, status=status.HTTP_400_BAD_REQUEST
            )
        if user.email_verified:
            return Response(
                {"detail": "That address is already verified."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not user.is_active:
            return Response(
                {"detail": "That account is deactivated, so no verification message was sent."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            send_email_verification(user)
        except MailRefusedError as refusal:
            return _mail_refused(f"the email verification for account {user.pk}", refusal)
        audit.record(audit.EMAIL_VERIFICATION_ADMIN_SENT, actor=actor, target=user)
        return _verification_sent(user)


# --------------------------------------------------------------------------
# Users admin -- the account's status
# --------------------------------------------------------------------------
#: One of the account actions in ``apps.accounts.api.account_actions``.
type AccountAction = Callable[[User, User], User]


def _admin_user_action(request: Request, pk: int, action: AccountAction) -> Response:
    """Run ``action`` by the signed-in user on the account ``pk``, answering the record.

    200 with the ``/admin/users/{id}`` payload as it stands afterwards; a refusal is a
    400 ``{"detail": <sentence>}`` and changes nothing; an unknown ``pk`` is a 404.
    """
    actor = signed_in_user(request)
    target = generics.get_object_or_404(User, pk=pk)
    try:
        action(actor, target)
    except DomainError as error:
        return Response({"detail": error.message}, status=status.HTTP_400_BAD_REQUEST)
    record = admin_user_queryset().get(pk=pk)
    return Response(AdminUserDetailSerializer(record, context={"request": request}).data)


class AdminUserDeactivateView(APIView):
    """``POST /admin/users/{id}/deactivate``."""

    permission_classes = [IsUserAdmin]

    @extend_schema(request=None, responses={200: AdminUserDetailSerializer})
    def post(self, request: Request, pk: int) -> Response:
        """Deactivate the account ``pk`` as its owner would deactivate it, answering 200.

        Every automatic renewal and recurring donation is canceled, every membership
        term with time left is suspended, every session signed in to the account is
        ended, and the change is recorded as ``account.deactivate`` under the caller.
        Your own account, a donor, an account holding roles you do not hold, and one
        already deactivated are each a 400 ``{"detail": ...}``.  Restricted to
        ``user_admin``, and to ``system_admin`` by implication.
        """
        return _admin_user_action(request, pk, deactivate_for)


class AdminUserReactivateView(APIView):
    """``POST /admin/users/{id}/reactivate``."""

    permission_classes = [IsUserAdmin]

    @extend_schema(request=None, responses={200: AdminUserDetailSerializer})
    def post(self, request: Request, pk: int) -> Response:
        """Reactivate the account ``pk`` as its owner would reactivate it, answering 200.

        Each suspended membership term is active again, or expired if it ran out
        meanwhile; the change is recorded as ``account.activate`` under the caller.  A
        donor, an account holding roles you do not hold, an account blocked from
        reactivating, and one already active are each a 400 ``{"detail": ...}``.
        Restricted to ``user_admin``, and to ``system_admin`` by implication.
        """
        return _admin_user_action(request, pk, reactivate_for)


class AdminUserBlockView(APIView):
    """``POST /admin/users/{id}/block``."""

    permission_classes = [IsUserAdmin]

    @extend_schema(request=None, responses={200: AdminUserDetailSerializer})
    def post(self, request: Request, pk: int) -> Response:
        """Block the account ``pk`` from reactivating, answering 200.

        An active account is deactivated first, exactly as ``/deactivate`` does it.
        While the block is set, sign-in, ``/auth/reactivate``, a password reset, and
        registering with the address all refuse with "This account has been closed.
        Contact <organization name> to reopen it.", and no administrator reactivates it.
        Recorded as ``account.block``.  Your own account, a donor, and an account
        holding roles you do not hold are each a 400 ``{"detail": ...}``.  Restricted to
        ``user_admin``, and to ``system_admin`` by implication.
        """
        return _admin_user_action(request, pk, block_for)


class AdminUserUnblockView(APIView):
    """``POST /admin/users/{id}/unblock``."""

    permission_classes = [IsUserAdmin]

    @extend_schema(request=None, responses={200: AdminUserDetailSerializer})
    def post(self, request: Request, pk: int) -> Response:
        """Lift the account ``pk``'s block, answering 200; it stays deactivated.

        Its owner may then reactivate it by signing in or resetting their password, and
        an administrator may reactivate it.  Recorded as ``account.unblock``.  The same
        refusals as ``/block`` apply.  Restricted to ``user_admin``, and to
        ``system_admin`` by implication.
        """
        return _admin_user_action(request, pk, unblock_for)


class AdminUserClearBounceView(APIView):
    """``POST /admin/users/{id}/clear-bounce``."""

    permission_classes = [IsUserAdmin]

    @extend_schema(request=None, responses={200: AdminUserDetailSerializer})
    def post(self, request: Request, pk: int) -> Response:
        """Clear the bounce recorded against the account ``pk``'s address, answering 200.

        For an address the user administrator has checked is good: ``email_bounced_at``
        and ``email_bounce_detail`` are emptied and the change is recorded as
        ``account.bounce_cleared`` under the caller.  An account with no bounce recorded
        is answered as it stands and nothing is recorded.  The answer is the
        ``/admin/users/{id}`` payload afterwards; an unknown ``pk`` is a 404.
        Restricted to ``user_admin``, and to ``system_admin`` by implication.
        """
        return _admin_user_action(request, pk, clear_email_bounce)
