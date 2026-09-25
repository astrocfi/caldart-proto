"""Django admin for the email log, read-only."""

from typing import TYPE_CHECKING

from django.contrib import admin
from django.http import HttpRequest

from apps.mail.models import EmailLog

if TYPE_CHECKING:
    # ModelAdmin is a real generic only for type checkers: subscripting it at
    # runtime raises, since Django itself does not implement __class_getitem__.
    _EmailLogAdminBase = admin.ModelAdmin[EmailLog]
else:
    _EmailLogAdminBase = admin.ModelAdmin


@admin.register(EmailLog)
class EmailLogAdmin(_EmailLogAdminBase):
    """Admin list and search for ``EmailLog``, filterable by purpose and status.

    Nothing here may be added, changed or deleted: the log is what the mail
    funnel wrote, and an edited record would answer the operator's question
    dishonestly.
    """

    list_display = ["sent_at", "purpose", "to_email", "user", "status", "subject"]
    list_filter = ["purpose", "status"]
    search_fields = ["to_email", "subject", "user__email"]
    date_hierarchy = "sent_at"
    readonly_fields = [
        "to_email",
        "user",
        "purpose",
        "subject",
        "sent_at",
        "status",
        "error",
        "attachments",
        "created_at",
        "updated_at",
    ]

    def has_add_permission(self, request: HttpRequest) -> bool:
        """Return False: rows are written by the mail funnel, never by hand."""
        return False

    def has_change_permission(self, request: HttpRequest, obj: EmailLog | None = None) -> bool:
        """Return False: the log records what went out and is not editable."""
        return False

    def has_delete_permission(self, request: HttpRequest, obj: EmailLog | None = None) -> bool:
        """Return False: the log is kept whole."""
        return False
