"""Email log API routes."""

from django.urls import path

from apps.mail.api import views

app_name = "mail"

urlpatterns = [
    path("system/emails", views.EmailLogListView.as_view(), name="emails"),
]
