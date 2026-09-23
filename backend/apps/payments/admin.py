"""Django admin for payments."""

from django.contrib import admin

from apps.payments.models import Payment


@admin.register(Payment)
# django-stubs makes ModelAdmin generic in the model, but Django's own class is
# not subscriptable at runtime, so the parameter cannot be written here.
class PaymentAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Browse the payment ledger: its money and status columns, with a date drill-down.

    ``created_at``, ``updated_at``, and the provider's ``raw`` payload are shown but
    cannot be edited, and the list is filtered by provider, status, wallet, and plan
    and searched by the member's name, email address or provider reference.
    """

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
