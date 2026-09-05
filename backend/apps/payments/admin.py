"""Django admin for payments."""

from django.contrib import admin

from apps.payments.models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        "created_at",
        "user",
        "plan",
        "amount_cents",
        "contribution_cents",
        "provider",
        "wallet",
        "status",
        "completed_at",
    ]
    list_filter = ["provider", "status", "wallet", "plan"]
    search_fields = ["user__email", "user__first_name", "user__last_name", "provider_ref"]
    autocomplete_fields = ["user"]
    date_hierarchy = "created_at"
    readonly_fields = ["created_at", "updated_at", "raw"]
