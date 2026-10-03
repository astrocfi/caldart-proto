"""Email log, bounce check, and mail delivery check API routes."""

from django.urls import path

from apps.mail.api import views

app_name = "mail"

urlpatterns = [
    path("system/emails", views.EmailLogListView.as_view(), name="emails"),
    path("system/emails/purposes", views.EmailPurposeListView.as_view(), name="purposes"),
    path("mail/delivery-check", views.MailDeliveryCheckView.as_view(), name="delivery-check"),
    path("system/bounces/run", views.BounceRunView.as_view(), name="bounces-run"),
]
