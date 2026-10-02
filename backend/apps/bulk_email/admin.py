"""Django admin for bulk emails and their recipients, read-only."""

from typing import TYPE_CHECKING

from django.contrib import admin

from apps.bulk_email.models import BulkEmail, BulkEmailRecipient

if TYPE_CHECKING:
    # ModelAdmin is a real generic only for type checkers: subscripting it at
    # runtime raises, since Django itself does not implement __class_getitem__.
    _BulkEmailAdminBase = admin.ModelAdmin[BulkEmail]
    _RecipientInlineBase = admin.TabularInline[BulkEmailRecipient, BulkEmail]
else:
    _BulkEmailAdminBase = admin.ModelAdmin
    _RecipientInlineBase = admin.TabularInline


class BulkEmailRecipientInline(_RecipientInlineBase):
    """Each person a bulk email reached, under the email."""

    model = BulkEmailRecipient
    fields = ["name", "email", "status", "reason"]
    readonly_fields = ["name", "email", "status", "reason"]
    extra = 0
    can_delete = False


@admin.register(BulkEmail)
class BulkEmailAdmin(_BulkEmailAdminBase):
    """Admin list and search for ``BulkEmail``, with its recipients inline."""

    list_display = ["subject", "sender", "created_at", "sent_count", "failed_count"]
    search_fields = ["subject", "sender__email"]
    readonly_fields = [
        "subject",
        "body",
        "filters",
        "sender",
        "created_at",
        "updated_at",
        "sent_at",
        "sent_count",
        "failed_count",
        "skipped_count",
    ]
    inlines = [BulkEmailRecipientInline]
