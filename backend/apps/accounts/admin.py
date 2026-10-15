"""Django admin for accounts.

The role groups are not on the Django admin at all: Django's own group screens are
unregistered, so no role group is renamed, deleted, or given permissions there.  A role
changes only on the portal's user record, through
:func:`apps.accounts.services.update_account`, which audits it and raises
``roles_changed``.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User

#: The fields a role write sets, which only the user record changes, and the per-user
#: permissions, which CalDART grants only through roles.
ROLE_FIELDS: tuple[str, ...] = ("groups", "is_superuser", "is_staff", "user_permissions")

admin.site.unregister(Group)


# django-stubs types ModelAdmin as generic, but Django's own class doesn't carry a
# __class_getitem__ when the admin autodiscovery that imports this module runs, so
# naming the model here would raise TypeError on startup.
@admin.register(User)
class UserAdmin(DjangoUserAdmin):  # type: ignore[type-arg]
    """Django admin for the accounts, listing and searching them by name and address.

    No administrator chooses or sets anybody's password here: the change form doesn't
    show a password, the add form is closed (an account is added on the portal's New
    member, which mails the person an invitation to choose their own), and the
    change-password page Django's own ``UserAdmin`` offers answers 403.
    """

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
        (None, {"fields": ("email",)}),
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

    def get_readonly_fields(self, request: HttpRequest, obj: User | None = None) -> list[str]:
        """The stamps, the address, the roles, and the flag that would leave it blocked.

        The address is never edited here: a change of address waits for its new owner
        and tells the old address (``apps.accounts.email_change``), which this form
        would bypass.  Nor are the roles (``groups``), the superuser and staff flags
        they set, or ``user_permissions``: a role changes on the portal's user record,
        through :func:`apps.accounts.services.update_account`, which refuses a change to
        your own roles, audits the change, and raises ``roles_changed``.

        While ``reactivation_blocked`` is set, ``is_active`` is read-only, so a blocked
        account cannot be switched back on here; while the account is active,
        ``reactivation_blocked`` is read-only, since blocking an active account must
        also deactivate it, cancel its mandates and suspend its membership, which the
        user record's **Block reactivation** does.  The add form shows neither.
        """
        fields = list(super().get_readonly_fields(request, obj))
        if obj is None:
            return fields
        fields.extend(["email", *ROLE_FIELDS])
        if obj.reactivation_blocked:
            fields.append("is_active")
        elif obj.is_active:
            fields.append("reactivation_blocked")
        return fields

    def has_add_permission(self, request: HttpRequest) -> bool:
        """Never: an account is added on New member, which invites the person by email."""
        return False

    def user_change_password(
        self,
        request: HttpRequest,
        id: str,  # noqa: A002 - Django's URL pattern passes the account as ``id``
        form_url: str = "",
    ) -> HttpResponse:
        """Refuse the page that sets another account's password, with 403, for anybody.

        Raises ``PermissionDenied``.  A forgotten password is the owner's own reset, and
        an account somebody else may have the password to is the user record's
        **Require a new password**.
        """
        raise PermissionDenied

    @admin.display(description="roles")
    def role_list(self, obj: User) -> str:
        """Role slugs, comma separated, or a dash for an account without a role."""
        return ", ".join(obj.roles) or "\u2014"
