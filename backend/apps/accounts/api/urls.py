"""Accounts API routes (PLAN §6.1, §6.2).  Owned by ``feat/auth-portal``."""

from django.urls import path

from apps.accounts.api import views

app_name = "accounts"

urlpatterns = [
    # -- auth (PLAN §6.1) --------------------------------------------------
    path("auth/csrf", views.CsrfView.as_view(), name="csrf"),
    path("auth/register", views.RegisterView.as_view(), name="register"),
    path("auth/login", views.LoginView.as_view(), name="login"),
    path("auth/logout", views.LogoutView.as_view(), name="logout"),
    path("auth/me", views.MeView.as_view(), name="me"),
    path("auth/password/change", views.PasswordChangeView.as_view(), name="password-change"),
    path("auth/password/reset", views.PasswordResetView.as_view(), name="password-reset"),
    path(
        "auth/password/reset/confirm",
        views.PasswordResetConfirmView.as_view(),
        name="password-reset-confirm",
    ),
    # -- users admin (PLAN §6.2) ------------------------------------------
    path("admin/users", views.AdminUserListView.as_view(), name="admin-user-list"),
    path("admin/users/<int:pk>", views.AdminUserDetailView.as_view(), name="admin-user-detail"),
    path(
        "admin/users/<int:pk>/send-password-reset",
        views.AdminUserSendPasswordResetView.as_view(),
        name="admin-user-send-password-reset",
    ),
    path("roles", views.RolesView.as_view(), name="roles"),
]
