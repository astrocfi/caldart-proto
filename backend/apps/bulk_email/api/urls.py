"""Bulk email API routes."""

from django.urls import path

from apps.bulk_email.api import views

app_name = "bulk_email"

urlpatterns = [
    path("bulk-email", views.BulkEmailListView.as_view(), name="list"),
    path("bulk-email/preview", views.PreviewView.as_view(), name="preview"),
    path("bulk-email/preview.csv", views.PreviewCsvView.as_view(), name="preview-csv"),
    path("bulk-email/send", views.SendView.as_view(), name="send"),
    path("bulk-email/<int:pk>", views.BulkEmailDetailView.as_view(), name="detail"),
    path(
        "bulk-email/<int:pk>/recipients.csv",
        views.RecipientsCsvView.as_view(),
        name="recipients-csv",
    ),
]
