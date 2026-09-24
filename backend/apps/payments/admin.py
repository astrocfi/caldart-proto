"""Django admin for payments."""

from django.contrib import admin

from apps.payments.models import Payment, Refund, RenewalAttempt, RenewalMandate


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


@admin.register(Refund)
# django-stubs makes ModelAdmin generic in the model, but Django's own class is
# not subscriptable at runtime, so the parameter cannot be written here.
class RefundAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Browse the refunds: what was given back, why, and whether it went through.

    ``created_at``, ``updated_at`` and the provider's ``raw`` payload are shown but
    cannot be edited, the list is filtered by status and reason, and it is searched
    by the payer's name or email address and by either provider reference.
    """

    list_display = ["created_at", "payment", "amount_cents", "reason", "status", "refunded_at"]
    list_filter = ["status", "reason"]
    search_fields = [
        "payment__user__email",
        "payment__user__first_name",
        "payment__user__last_name",
        "provider_ref",
        "payment__provider_ref",
    ]
    date_hierarchy = "created_at"
    readonly_fields = ["created_at", "updated_at", "raw"]


@admin.register(RenewalMandate)
# django-stubs makes ModelAdmin generic in the model, but Django's own class is
# not subscriptable at runtime, so the parameter cannot be written here.
class RenewalMandateAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Browse the standing authorities to renew: member, method, plan and status.

    ``created_at``, ``updated_at`` and the provider's ``raw`` payload are shown but
    cannot be edited, the list is filtered by status, provider and plan, and it is
    searched by the member's name or email address and the method reference.
    """

    list_display = [
        "user",
        "plan",
        "method_label",
        "provider",
        "status",
        "failure_count",
        "last_charged_at",
    ]
    list_filter = ["status", "provider", "plan"]
    search_fields = ["user__email", "user__first_name", "user__last_name", "method_ref"]
    autocomplete_fields = ["user"]
    readonly_fields = ["created_at", "updated_at", "raw"]


@admin.register(RenewalAttempt)
# django-stubs makes ModelAdmin generic in the model, but Django's own class is
# not subscriptable at runtime, so the parameter cannot be written here.
class RenewalAttemptAdmin(admin.ModelAdmin):  # type: ignore[type-arg]
    """Browse the scheduled renewal charges: when each is due and how it went.

    ``created_at`` and ``updated_at`` are shown but cannot be edited, the list is
    filtered by outcome, drilled down by the scheduled date, and searched by the
    member's name or email address.
    """

    list_display = ["scheduled_on", "mandate", "outcome", "payment", "attempted_at", "error"]
    list_filter = ["outcome"]
    search_fields = [
        "mandate__user__email",
        "mandate__user__first_name",
        "mandate__user__last_name",
    ]
    date_hierarchy = "scheduled_on"
    readonly_fields = ["created_at", "updated_at"]
