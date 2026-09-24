"""DART routes: the public catalog, and the administrator's screen."""

from django.urls import path

from apps.darts.api import views

app_name = "darts"

urlpatterns = [
    path("darts", views.DartListView.as_view(), name="darts"),
    path("admin/darts", views.DartAdminListCreateView.as_view(), name="admin-darts"),
    path("admin/darts/<int:pk>", views.DartAdminDetailView.as_view(), name="admin-dart-detail"),
]
