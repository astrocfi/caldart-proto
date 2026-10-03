"""Bulk email API routes."""

from django.urls import path

from apps.bulk_email.api import batch, drafts, history, richtext, sender

app_name = "bulk_email"

urlpatterns = [
    path("bulk-email/fields", richtext.FieldsView.as_view(), name="fields"),
    path("bulk-email/images", richtext.ImageUploadView.as_view(), name="images"),
    path("bulk-email/drafts", drafts.DraftListCreateView.as_view(), name="drafts"),
    path("bulk-email/sent", history.SentListView.as_view(), name="sent"),
    path("bulk-email/<int:pk>", drafts.BulkEmailDetailView.as_view(), name="detail"),
    path("bulk-email/<int:pk>/send", drafts.SendView.as_view(), name="send"),
    path("bulk-email/<int:pk>/cancel", drafts.CancelView.as_view(), name="cancel"),
    path("bulk-email/<int:pk>/stop", drafts.StopView.as_view(), name="stop"),
    path("bulk-email/<int:pk>/resume", drafts.ResumeView.as_view(), name="resume"),
    path("bulk-email/<int:pk>/batch", batch.BatchView.as_view(), name="batch"),
    path("bulk-email/<int:pk>/batch.csv", batch.BatchCsvView.as_view(), name="batch-csv"),
    path("bulk-email/<int:pk>/batch/add", batch.BatchAddView.as_view(), name="batch-add"),
    path("bulk-email/<int:pk>/batch/<int:rid>", batch.BatchRowView.as_view(), name="batch-row"),
    path(
        "bulk-email/<int:pk>/recipients.csv",
        history.RecipientsCsvView.as_view(),
        name="recipients-csv",
    ),
    path("system/bulk-email/run", sender.SenderRunView.as_view(), name="sender-run"),
]
