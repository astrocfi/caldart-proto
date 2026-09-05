"""Django admin for reminder logs."""

from django.contrib import admin

from apps.reminders.models import ReminderLog


@admin.register(ReminderLog)
class ReminderLogAdmin(admin.ModelAdmin):
    list_display = ["sent_at", "user", "kind", "to_email", "membership"]
    list_filter = ["kind"]
    search_fields = ["user__email", "to_email"]
    autocomplete_fields = ["user"]
    date_hierarchy = "sent_at"
    readonly_fields = ["created_at", "updated_at"]
