"""Auth and users-admin endpoints (PLAN §6.1, §6.2)."""

from __future__ import annotations

from django.contrib.auth import (
    authenticate,
    get_user_model,
    login,
    logout,
    update_session_auth_hash,
)
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, status
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import AllowAny, IsAuthenticated
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
from apps.accounts.permissions import IsUserAdmin
from apps.accounts.roles import ROLE_DESCRIPTIONS
from apps.accounts.services import register_user, send_password_reset_email
from apps.accounts.throttling import LoginThrottle, PasswordResetThrottle, RegisterThrottle

User = get_user_model()


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    """``GET /auth/csrf`` — 204, sets the ``csrftoken`` cookie."""

    permission_classes = [AllowAny]

    def get(self, request):
        get_token(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class RegisterView(APIView):
    """``POST /auth/register`` — create a member account and sign them in."""

    permission_classes = [AllowAny]
    throttle_classes = [RegisterThrottle]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = register_user(**serializer.validated_data)
        login(request, user)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """``POST /auth/login`` — session login by email + password."""

    permission_classes = [AllowAny]
    throttle_classes = [LoginThrottle]

    def post(self, request):
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

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    """``GET /auth/me`` — the signed-in user, 401 when anonymous."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class PasswordChangeView(APIView):
    """``POST /auth/password/change`` — 204, session kept alive."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = request.user
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password", "updated_at"])
        # Rotating the password rotates the session auth hash; without this the
        # caller is logged out by their own request.
        update_session_auth_hash(request, user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetView(APIView):
    """``POST /auth/password/reset`` — 204 always (PLAN §6.1).

    The answer never depends on whether the address is registered, so the
    endpoint cannot be used to enumerate members.
    """

    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetThrottle]

    def post(self, request):
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

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class RolesView(APIView):
    """``GET /roles`` — the role catalogue, for any authenticated caller."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = [{"slug": slug, "description": desc} for slug, desc in ROLE_DESCRIPTIONS.items()]
        return Response(RoleSerializer(data, many=True).data)


# --------------------------------------------------------------------------
# Users admin (PLAN §6.2) — user_admin, and system_admin by implication
# --------------------------------------------------------------------------
def admin_user_queryset():
    """Every user, with the rows the ``user`` payload needs already loaded."""
    return User.objects.select_related("profile").prefetch_related("groups").all()


class AdminUserListView(generics.ListAPIView):
    """``GET /admin/users?search=&role=&is_active=`` — paginated ``[user]``."""

    permission_classes = [IsUserAdmin]
    serializer_class = AdminUserSerializer
    queryset = admin_user_queryset()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = UserFilter
    search_fields = ["first_name", "last_name", "email"]
    ordering_fields = ["last_name", "first_name", "email", "is_active", "created_at"]
    ordering = ["last_name", "first_name", "email"]


class AdminUserDetailView(generics.RetrieveUpdateAPIView):
    """``GET|PATCH /admin/users/{id}``."""

    permission_classes = [IsUserAdmin]
    serializer_class = AdminUserSerializer
    queryset = admin_user_queryset()
    http_method_names = ["get", "patch", "head", "options"]


class AdminUserSendPasswordResetView(APIView):
    """``POST /admin/users/{id}/send-password-reset``."""

    permission_classes = [IsUserAdmin]

    def post(self, request, pk: int):
        user = generics.get_object_or_404(User, pk=pk)
        sent = send_password_reset_email(user, request=request)
        if not sent:
            return Response(
                {"detail": "That account is deactivated, so no reset email was sent."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"detail": f"Password reset email sent to {user.email}."})
