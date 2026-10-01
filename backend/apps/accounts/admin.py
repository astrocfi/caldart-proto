"""Django admin for accounts."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User


# django-stubs types ModelAdmin as generic, but Django's own class carries no
# __class_getitem__ when the admin autodiscovery that imports this module runs, so
# naming the model here would raise TypeError on startup.
@admin.register(User)
class UserAdmin(DjangoUserAdmin):  # type: ignore[type-arg]
    """Django admin for the accounts, listing and searching them by name and address."""

    ordering = ["last_name", "first_name", "email"]
    list_display = [
        "email",
        "first_name",
        "last_name",
        "is_active",
        "reactivation_blocked",
        "role_list",
    ]
    list_filter = ["is_active", "is_staff", "is_superuser", "groups"]
    search_fields = ["email", "first_name", "last_name"]
    filter_horizontal = ["groups", "user_permissions"]
    readonly_fields = ["created_at", "updated_at", "last_login", "date_joined"]

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name")}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "reactivation_blocked",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (_("Dates"), {"fields": ("last_login", "date_joined", "created_at", "updated_at")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "first_name", "last_name", "password1", "password2"),
            },
        ),
    )

    def get_readonly_fields(self, request: HttpRequest, obj: User | None = None) -> list[str]:
        """The stamps, plus whichever flag could make an account active and blocked.

        While ``reactivation_blocked`` is set, ``is_active`` is read-only, so a blocked
        account cannot be switched back on here; while the account is active,
        ``reactivation_blocked`` is read-only, since blocking an active account must
        also deactivate it, cancel its mandates and suspend its membership, which the
        user record's **Block reactivation** does.  The add form shows neither.
        """
        fields = list(super().get_readonly_fields(request, obj))
        if obj is None:
            return fields
        if obj.reactivation_blocked:
            fields.append("is_active")
        elif obj.is_active:
            fields.append("reactivation_blocked")
        return fields

    @admin.display(description="roles")
    def role_list(self, obj: User) -> str:
        """The account's role slugs, comma separated, or a dash when it holds none."""
        return ", ".join(obj.roles) or "\u2014"
