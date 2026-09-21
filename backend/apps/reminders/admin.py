"""Django admin for reminder logs."""

from typing import TYPE_CHECKING

from django.contrib import admin

from apps.reminders.models import ReminderLog

if TYPE_CHECKING:
    # ModelAdmin is a real generic only for type checkers: subscripting it at
    # runtime raises, since Django itself does not implement __class_getitem__.
    _ReminderLogAdminBase = admin.ModelAdmin[ReminderLog]
else:
    _ReminderLogAdminBase = admin.ModelAdmin


@admin.register(ReminderLog)
class ReminderLogAdmin(_ReminderLogAdminBase):
    """Admin list and search for ``ReminderLog``, filterable by kind."""

    list_display = ["sent_at", "user", "kind", "to_email", "membership"]
    list_filter = ["kind"]
    search_fields = ["user__email", "to_email"]
    autocomplete_fields = ["user"]
    date_hierarchy = "sent_at"
    readonly_fields = ["created_at", "updated_at"]
