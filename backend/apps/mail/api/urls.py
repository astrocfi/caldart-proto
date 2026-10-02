"""Email log and bounce check API routes."""

from django.urls import path

from apps.mail.api import views

app_name = "mail"

urlpatterns = [
    path("system/emails", views.EmailLogListView.as_view(), name="emails"),
    path("system/emails/purposes", views.EmailPurposeListView.as_view(), name="purposes"),
    path("system/bounces/run", views.BounceRunView.as_view(), name="bounces-run"),
]
