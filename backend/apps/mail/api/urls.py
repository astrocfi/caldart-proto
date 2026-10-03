"""Mail API routes: email log, bounces, delivery check, email types, preferences."""

from django.urls import path

from apps.mail.api import email_types, views

app_name = "mail"

urlpatterns = [
    path("system/emails", views.EmailLogListView.as_view(), name="emails"),
    path("system/emails/purposes", views.EmailPurposeListView.as_view(), name="purposes"),
    path("mail/delivery-check", views.MailDeliveryCheckView.as_view(), name="delivery-check"),
    path("system/bounces/run", views.BounceRunView.as_view(), name="bounces-run"),
    path("email-types", email_types.EmailTypeListView.as_view(), name="email-types"),
    path(
        "email-types/sendable",
        email_types.SendableEmailTypeListView.as_view(),
        name="email-types-sendable",
    ),
    path(
        "email-types/<int:pk>",
        email_types.EmailTypeDetailView.as_view(),
        name="email-type-detail",
    ),
    path(
        "me/email-preferences",
        email_types.MyEmailPreferencesView.as_view(),
        name="me-email-preferences",
    ),
    path(
        "admin/members/<int:pk>/email-preferences",
        email_types.MemberEmailPreferencesView.as_view(),
        name="admin-member-email-preferences",
    ),
]
