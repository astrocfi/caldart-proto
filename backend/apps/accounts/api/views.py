"""Auth endpoints the portal shell needs to be usable (PLAN §6.1).

``feat/auth-portal`` owns this module and extends it with registration,
password change/reset and the users-admin endpoints.
"""

from __future__ import annotations

from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api.serializers import LoginSerializer, RoleSerializer, UserSerializer
from apps.accounts.roles import ROLE_DESCRIPTIONS


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    """``GET /auth/csrf`` — 204, sets the ``csrftoken`` cookie."""

    permission_classes = [AllowAny]

    def get(self, request):
        get_token(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class LoginView(APIView):
    """``POST /auth/login`` — session login by email + password."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request,
            username=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        if user is None:
            return Response(
                {"detail": "Incorrect email address or password."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not user.is_active:
            return Response(
                {"detail": "This account has been deactivated."},
                status=status.HTTP_403_FORBIDDEN,
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


class RolesView(APIView):
    """``GET /roles`` — the role catalogue, for any authenticated caller."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        data = [{"slug": slug, "description": desc} for slug, desc in ROLE_DESCRIPTIONS.items()]
        return Response(RoleSerializer(data, many=True).data)
