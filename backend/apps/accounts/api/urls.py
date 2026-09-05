"""Accounts API routes (PLAN §6.1, §6.2).  Owned by ``feat/auth-portal``."""

from django.urls import path

from apps.accounts.api import views

app_name = "accounts"

urlpatterns = [
    path("auth/csrf", views.CsrfView.as_view(), name="csrf"),
    path("auth/login", views.LoginView.as_view(), name="login"),
    path("auth/logout", views.LogoutView.as_view(), name="logout"),
    path("auth/me", views.MeView.as_view(), name="me"),
    path("roles", views.RolesView.as_view(), name="roles"),
]
