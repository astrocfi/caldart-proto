"""Django admin for notification subscriptions."""

from typing import TYPE_CHECKING

from django.contrib import admin

from apps.notifications.models import NotificationSubscription

if TYPE_CHECKING:
    # ModelAdmin is a real generic only for type checkers: subscripting it at
    # runtime raises, since Django itself does not implement __class_getitem__.
    _SubscriptionAdminBase = admin.ModelAdmin[NotificationSubscription]
else:
    _SubscriptionAdminBase = admin.ModelAdmin


@admin.register(NotificationSubscription)
class NotificationSubscriptionAdmin(_SubscriptionAdminBase):
    """Admin list and search for ``NotificationSubscription``, filterable by state."""

    list_display = ["recipient_email", "recipient_user", "is_active", "updated_at"]
    list_filter = ["is_active"]
    search_fields = ["recipient_email", "recipient_user__email"]
    autocomplete_fields = ["recipient_user", "created_by"]
    readonly_fields = ["created_at", "updated_at"]
