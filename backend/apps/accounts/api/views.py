"""Auth and users-admin endpoints."""

from __future__ import annotations

from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.models import AnonymousUser
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

from apps.accounts.api.filters import UserFilter
from apps.accounts.api.serializers import (
    AdminUserSerializer,
    EmailChangeSerializer,
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
from apps.accounts.models import User
from apps.accounts.permissions import IsUserAdmin
from apps.accounts.roles import ROLE_DESCRIPTIONS
from apps.accounts.services import (
    change_own_email,
    confirm_email_address,
    send_email_verification,
    send_password_reset_email,
    verify_email,
)
from apps.accounts.throttling import (
    EmailVerifyResendThrottle,
    EmailVerifyThrottle,
    LoginThrottle,
    PasswordResetThrottle,
    RegisterThrottle,
)
from apps.members.services import register_member, with_membership
from caldart import audit

#: What every refused login says.  It names neither half of the credentials, and
#: a deactivated account whose password was wrong is answered with it too, so a
#: guess can never be used to find out which addresses are registered.
WRONG_CREDENTIALS_MESSAGE = "Incorrect email address or password."

#: What a deactivated account is told, and only once its password has matched.
DEACTIVATED_MESSAGE = "This account has been deactivated. Ask a CalDART administrator."


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
    """``POST /auth/register`` -- create a member account and sign them in."""

    permission_classes = [AllowAny]
    throttle_classes = [RegisterThrottle]

    @extend_schema(request=RegisterSerializer, responses={201: UserSerializer})
    def post(self, request: Request) -> Response:
        """Create a member account from the posted fields, sign it in, and answer 201.

        The body carries ``email``, ``password``, ``first_name``, and ``last_name``; the
        response is the ``user`` payload, with ``email_verified`` false.  Once the account
        is committed its address is mailed a verification link.  Open to anonymous
        callers and throttled under the ``auth_register`` scope.  A taken address or a
        password Django's validators reject is a 400 naming the field.
        """
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = register_member(**serializer.validated_data)
        login(request, user)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


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
        case it is a 403 with "This account has been deactivated. Ask a CalDART
        administrator." -- so only somebody who already knows the password learns that
        the address belongs to a deactivated account.
        """
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]
        user = authenticate(request, username=email, password=password)
        if user is None:
            # `authenticate` also returns None for a deactivated account, so look
            # one up; its password still has to match before we say so.
            deactivated = User.objects.filter(email__iexact=email, is_active=False).first()
            if deactivated is not None and deactivated.check_password(password):
                return Response(
                    {"detail": DEACTIVATED_MESSAGE},
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
        session survives the change, so the caller stays signed in.  An anonymous caller
        gets 401.
        """
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = signed_in_user(request)
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password", "updated_at"])
        # Rotating the password rotates the session auth hash; without this the
        # caller is logged out by their own request.
        update_session_auth_hash(request, user)
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
        An unregistered or deactivated address is answered 204 with no mail sent, so the
        endpoint cannot be used to enumerate members.  An account that has never set a
        password is mailed the link like any other.  A malformed address is a 400.
        """
        serializer = PasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(email__iexact=serializer.validated_data["email"]).first()
        if user is not None:
            send_password_reset_email(user, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)


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
        using it also marks an unverified address verified.
        """
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password", "updated_at"])
        confirm_email_address(user)
        return Response(status=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------
# Email verification and change
# --------------------------------------------------------------------------
def _verification_sent(user: User) -> Response:
    """Mail ``user`` a verification link and answer 202 naming the address."""
    send_email_verification(user)
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
        """Mark the account the posted ``token`` names verified, answering its address.

        Open to anonymous callers, since the link may be opened in a browser that is
        not signed in, and throttled under the ``auth_verify`` scope.  The answer is 200
        ``{"email": <address>}``, also for a link followed a second time.  A token that
        is forged, expired, for a deactivated or deleted account, or for an address the
        account no longer holds is a 400 ``{"token": ["That verification link is invalid
        or has expired."]}``.
        """
        serializer = EmailVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = verify_email(serializer.validated_data["token"])
        return Response({"email": user.email})


class EmailVerifyResendView(APIView):
    """``POST /auth/email/resend`` -- mail the signed-in user a fresh link, 202."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [EmailVerifyResendThrottle]

    @extend_schema(request=None, responses={202: VerificationSentSerializer})
    def post(self, request: Request) -> Response:
        """Mail the signed-in account's address a verification link and answer 202.

        The answer is ``{"detail": "Verification message sent to <address>."}``.  An
        address that is already verified is a 400 with "Your email address is already
        verified." and nothing is mailed.  Throttled under the ``auth_verify_resend``
        scope; an anonymous caller gets 401.
        """
        user = signed_in_user(request)
        if user.email_verified:
            return Response(
                {"detail": "Your email address is already verified."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return _verification_sent(user)


class EmailChangeView(APIView):
    """``POST /auth/email/change`` -- change the signed-in user's own address, 200."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=EmailChangeSerializer, responses={200: UserSerializer})
    def post(self, request: Request) -> Response:
        """Move the signed-in account to the posted ``email``, answering the payload.

        The body carries ``email`` and ``current_password``.  A wrong password, the
        account's own address, and an address another account uses are each a 400
        naming the field, the password checked first.  The changed address is marked
        unverified (``email_verified`` is false in the answer) and mailed a
        verification link once the change commits; the session survives, so the caller
        stays signed in.  The change is recorded in the audit log as the account's own
        ``account.update`` of ``email``.  An anonymous caller gets 401.
        """
        serializer = EmailChangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = change_own_email(signed_in_user(request), email=serializer.validated_data["email"])
        return Response(UserSerializer(user).data)


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
    return with_membership(User.objects.select_related("profile").prefetch_related("groups"))


class AdminUserListView(generics.ListAPIView[User]):
    """``GET /admin/users?search=&role=&is_active=`` -- paginated ``[user]``."""

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
    serializer_class = AdminUserSerializer
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self) -> QuerySet[User]:
        """Every account, annotated for this request's date."""
        return admin_user_queryset()


class AdminUserSendPasswordResetView(APIView):
    """``POST /admin/users/{id}/send-password-reset``."""

    permission_classes = [IsUserAdmin]

    @extend_schema(request=None, responses={200: SendPasswordResetResultSerializer})
    def post(self, request: Request, pk: int) -> Response:
        """Mail the account with id ``pk`` a reset link, and answer 200 with a message.

        Restricted to ``user_admin``, and to ``system_admin`` by implication; anyone
        else gets 403 and an unknown ``pk`` gets 404.  An account with nobody to mail --
        a deactivated one, or one with no email address -- is a 400 with "That account
        is deactivated, so no reset email was sent."  Both the send and the refusal are
        recorded in the audit log.
        """
        actor = signed_in_user(request)
        user = generics.get_object_or_404(User, pk=pk)
        sent = send_password_reset_email(user, request=request)
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
        deactivated, so no verification message was sent."; neither mails anything.
        """
        actor = signed_in_user(request)
        user = generics.get_object_or_404(User, pk=pk)
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
        audit.record(audit.EMAIL_VERIFICATION_ADMIN_SENT, actor=actor, target=user)
        return _verification_sent(user)
