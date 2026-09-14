"""Object-level rules for the aircraft register.

Anyone signed in may read the register and add an airframe they fly.  The
member who created a record may keep it up to date; only an account
administrator may edit someone else's record or delete one.
``system_admin`` passes every check, as everywhere else.
"""

from __future__ import annotations

from rest_framework.permissions import SAFE_METHODS, BasePermission

from apps.accounts.permissions import user_has_any_role
from apps.accounts.roles import ACCOUNT_ADMIN

ADMIN_ROLES: tuple[str, ...] = (ACCOUNT_ADMIN,)


class AircraftPermission(BasePermission):
    """Read: any member.  Write: the creator or an account administrator."""

    message = "Only the member who added this aircraft, or an administrator, can change it."

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj) -> bool:
        if request.method in SAFE_METHODS:
            return True
        if user_has_any_role(request.user, ADMIN_ROLES):
            return True
        if request.method == "DELETE":
            # Deleting an aircraft can orphan another member's profile entry.
            self.message = "Only an account administrator can delete an aircraft."
            return False
        return obj.created_by_id is not None and obj.created_by_id == request.user.id
