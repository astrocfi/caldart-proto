"""Bulk email API routes."""

from django.urls import path

from apps.bulk_email.api import batch, drafts, groups, history, preview, richtext, sender, templates

app_name = "bulk_email"

urlpatterns = [
    path("bulk-email/fields", richtext.FieldsView.as_view(), name="fields"),
    path("bulk-email/images", richtext.ImageUploadView.as_view(), name="images"),
    path("bulk-email/drafts", drafts.DraftListCreateView.as_view(), name="drafts"),
    path("bulk-email/sent", history.SentListView.as_view(), name="sent"),
    path("bulk-email/templates", templates.TemplateListCreateView.as_view(), name="templates"),
    path(
        "bulk-email/templates/<int:pk>",
        templates.TemplateDetailView.as_view(),
        name="template-detail",
    ),
    path("bulk-email/groups", groups.GroupListCreateView.as_view(), name="groups"),
    path("bulk-email/groups/people", groups.PeopleSearchView.as_view(), name="group-people"),
    path("bulk-email/groups/<int:pk>", groups.GroupDetailView.as_view(), name="group-detail"),
    path(
        "bulk-email/groups/<int:pk>/members",
        groups.GroupPeopleView.as_view(),
        name="group-members",
    ),
    path(
        "bulk-email/groups/<int:pk>/members.csv",
        groups.GroupPeopleCsvView.as_view(),
        name="group-members-csv",
    ),
    path(
        "bulk-email/groups/<int:pk>/members/<int:user_id>",
        groups.GroupMemberView.as_view(),
        name="group-member",
    ),
    path(
        "bulk-email/groups/<int:pk>/filters",
        groups.GroupFiltersView.as_view(),
        name="group-filters",
    ),
    path(
        "bulk-email/groups/<int:pk>/filters/<int:fid>",
        groups.GroupFilterView.as_view(),
        name="group-filter",
    ),
    path("bulk-email/<int:pk>", drafts.BulkEmailDetailView.as_view(), name="detail"),
    path("bulk-email/<int:pk>/send", drafts.SendView.as_view(), name="send"),
    path("bulk-email/<int:pk>/cancel", drafts.CancelView.as_view(), name="cancel"),
    path("bulk-email/<int:pk>/stop", drafts.StopView.as_view(), name="stop"),
    path("bulk-email/<int:pk>/resume", drafts.ResumeView.as_view(), name="resume"),
    path("bulk-email/<int:pk>/preview", preview.PreviewView.as_view(), name="preview"),
    path("bulk-email/<int:pk>/batch", batch.BatchView.as_view(), name="batch"),
    path("bulk-email/<int:pk>/batch.csv", batch.BatchCsvView.as_view(), name="batch-csv"),
    path("bulk-email/<int:pk>/batch/add", batch.BatchAddView.as_view(), name="batch-add"),
    path("bulk-email/<int:pk>/batch/<int:rid>", batch.BatchRowView.as_view(), name="batch-row"),
    path(
        "bulk-email/<int:pk>/batch/add-group", groups.AddGroupView.as_view(), name="batch-add-group"
    ),
    path("bulk-email/<int:pk>/save-group", groups.SaveGroupView.as_view(), name="save-group"),
    path(
        "bulk-email/<int:pk>/apply-template",
        templates.ApplyTemplateView.as_view(),
        name="apply-template",
    ),
    path("bulk-email/<int:pk>/duplicate", templates.DuplicateView.as_view(), name="duplicate"),
    path(
        "bulk-email/<int:pk>/recipients.csv",
        history.RecipientsCsvView.as_view(),
        name="recipients-csv",
    ),
    path("system/bulk-email/run", sender.SenderRunView.as_view(), name="sender-run"),
]
