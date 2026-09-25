"""Django admin for saved column sets and report subscriptions."""

from typing import TYPE_CHECKING

from django.contrib import admin

from apps.reports.models import ReportSubscription, SavedColumnSet

if TYPE_CHECKING:
    # ModelAdmin is a real generic only for type checkers: subscripting it at
    # runtime raises, since Django itself does not implement __class_getitem__.
    _ColumnSetAdminBase = admin.ModelAdmin[SavedColumnSet]
    _SubscriptionAdminBase = admin.ModelAdmin[ReportSubscription]
else:
    _ColumnSetAdminBase = admin.ModelAdmin
    _SubscriptionAdminBase = admin.ModelAdmin


@admin.register(SavedColumnSet)
class SavedColumnSetAdmin(_ColumnSetAdminBase):
    """Admin list and search for ``SavedColumnSet``, filterable by report."""

    list_display = ["name", "report", "user", "updated_at"]
    list_filter = ["report"]
    search_fields = ["name", "user__email"]
    autocomplete_fields = ["user"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(ReportSubscription)
class ReportSubscriptionAdmin(_SubscriptionAdminBase):
    """Admin list and search for ``ReportSubscription``, by report, cadence and state."""

    list_display = ["report", "recipient_email", "cadence", "formats", "is_active", "next_due_on"]
    list_filter = ["report", "cadence", "is_active"]
    search_fields = ["recipient_email", "recipient_user__email"]
    autocomplete_fields = ["recipient_user", "created_by"]
    readonly_fields = ["created_at", "updated_at", "last_sent_at"]
