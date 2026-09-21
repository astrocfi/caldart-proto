"""Auth and users-admin endpoints."""

from __future__ import annotations

from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.models import AnonymousUser
from django.db.models import QuerySet
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django_filters.rest_framework import DjangoFilterBackend
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
    LoginSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetSerializer,
    RegisterSerializer,
    RoleSerializer,
    UserSerializer,
)
from apps.accounts.models import User
from apps.accounts.permissions import IsUserAdmin
from apps.accounts.roles import ROLE_DESCRIPTIONS
from apps.accounts.services import send_password_reset_email
from apps.accounts.throttling import LoginThrottle, PasswordResetThrottle, RegisterThrottle
from apps.members.services import register_member, with_membership
from caldart import audit


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
    """``GET /auth/csrf`` — 204, sets the ``csrftoken`` cookie."""

    permission_classes = [AllowAny]

    def get(self, request: Request) -> Response:
        """Answer 204 with no body, having set the CSRF cookie on the response.

        Open to anonymous callers: the SPA calls it once before its first unsafe
        request so it has a token to echo back.
        """
        get_token(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class RegisterView(APIView):
    """``POST /auth/register`` — create a member account and sign them in."""

    permission_classes = [AllowAny]
    throttle_classes = [RegisterThrottle]

    def post(self, request: Request) -> Response:
        """Create a member account from the posted fields, sign it in, and answer 201.

        The body carries ``email``, ``password``, ``first_name`` and ``last_name``; the
        response is the ``user`` payload.  Open to anonymous callers and throttled under
        the ``auth_register`` scope.  A taken address or a password Django's validators
        reject is a 400 naming the field.
        """
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = register_member(**serializer.validated_data)
        login(request, user)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """``POST /auth/login`` — session login by email + password."""

    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]

    def post(self, request: Request) -> Response:
        """Sign in by ``email`` and ``password``, answering 200 with the ``user`` payload.

        Open to anonymous callers and throttled under the ``auth_login`` scope.  Wrong
        credentials are a 400 with "Incorrect email address or password."; an address
        that belongs to a deactivated account is a 403 with "This account has been
        deactivated. Ask a CalDART administrator."
        """
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request,
            username=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        if user is None:
            # `authenticate` also returns None for a deactivated account, so
            # look one up to tell the two apart for the error message only.
            if User.objects.filter(
                email__iexact=serializer.validated_data["email"], is_active=False
            ).exists():
                return Response(
                    {"detail": "This account has been deactivated. Ask a CalDART administrator."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            return Response(
                {"detail": "Incorrect email address or password."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        login(request, user)
        return Response(UserSerializer(user).data)


class LogoutView(APIView):
    """``POST /auth/logout`` — 204."""

    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        """End the session and answer 204.

        Open to anonymous callers, and answers 204 just the same when nobody was
        signed in.
        """
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    """``GET /auth/me`` — the signed-in user, 401 when anonymous."""

    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        """The signed-in account as the ``user`` payload, 200.

        An anonymous caller gets 401.
        """
        return Response(UserSerializer(signed_in_user(request)).data)


class PasswordChangeView(APIView):
    """``POST /auth/password/change`` — 204, session kept alive."""

    permission_classes = [IsAuthenticated]

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
    """``POST /auth/password/reset`` — 204 always.

    The answer never depends on whether the address is registered, so the
    endpoint cannot be used to enumerate members.
    """

    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetThrottle]

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
    """``POST /auth/password/reset/confirm`` — set the new password, 204."""

    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetThrottle]

    def post(self, request: Request) -> Response:
        """Set the new password the reset link authorizes, and answer 204.

        The body carries ``uid``, ``token`` and ``new_password``.  Open to anonymous
        callers and throttled under the ``auth_password_reset`` scope.  An unusable or
        spent link is a 400 under ``token``, and a password Django's validators reject a
        400 under ``new_password``.
        """
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class RolesView(APIView):
    """``GET /roles`` — the role catalog, for any authenticated caller."""

    permission_classes = [IsAuthenticated]

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
# Users admin — user_admin, and system_admin by implication
# --------------------------------------------------------------------------
def admin_user_queryset() -> QuerySet[User]:
    """Every user, with the rows the ``user`` payload needs already loaded.

    The membership annotations are worked out for the date this is called, so
    both views below build the queryset per request rather than once at import.
    """
    return with_membership(User.objects.select_related("profile").prefetch_related("groups"))


class AdminUserListView(generics.ListAPIView[User]):
    """``GET /admin/users?search=&role=&is_active=`` — paginated ``[user]``."""

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
