"""Django admin for bulk emails, their adds, and their recipients, read-only."""

from typing import TYPE_CHECKING

from django.contrib import admin

from apps.bulk_email.models import BatchAdd, BulkEmail, BulkEmailRecipient

if TYPE_CHECKING:
    # ModelAdmin is a real generic only for type checkers: subscripting it at
    # runtime raises, since Django itself does not implement __class_getitem__.
    _BulkEmailAdminBase = admin.ModelAdmin[BulkEmail]
    _RecipientInlineBase = admin.TabularInline[BulkEmailRecipient, BulkEmail]
    _AddInlineBase = admin.TabularInline[BatchAdd, BulkEmail]
else:
    _BulkEmailAdminBase = admin.ModelAdmin
    _RecipientInlineBase = admin.TabularInline
    _AddInlineBase = admin.TabularInline


class BatchAddInline(_AddInlineBase):
    """Each press of Add to batch, under the email."""

    model = BatchAdd
    fields = ["label", "filters", "group", "added_count", "already_count", "created_at"]
    readonly_fields = ["label", "filters", "group", "added_count", "already_count", "created_at"]
    extra = 0
    can_delete = False


class BulkEmailRecipientInline(_RecipientInlineBase):
    """Each person in the email's batch, and what became of their copy."""

    model = BulkEmailRecipient
    fields = ["name", "email", "kind", "dart_name", "status", "reason", "tried_at"]
    readonly_fields = ["name", "email", "kind", "dart_name", "status", "reason", "tried_at"]
    extra = 0
    can_delete = False


@admin.register(BulkEmail)
class BulkEmailAdmin(_BulkEmailAdminBase):
    """Admin list and search for ``BulkEmail``, with its adds and recipients inline."""

    list_display = ["subject", "status", "sender", "start_at", "sent_count", "failed_count"]
    list_filter = ["status"]
    search_fields = ["subject", "sender__email"]
    readonly_fields = [
        "subject",
        "body",
        "status",
        "sender",
        "start_at",
        "scheduled",
        "confirm_count",
        "created_at",
        "updated_at",
        "started_at",
        "sent_at",
        "stopped_at",
        "stopped_by",
        "stop_requested",
        "sent_count",
        "failed_count",
        "skipped_count",
    ]
    inlines = [BatchAddInline, BulkEmailRecipientInline]
