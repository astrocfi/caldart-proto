"""DRF permission classes for role checks.

``system_admin`` always passes.  Use them either as classes built by the
factory helpers or by subclassing::

    permission_classes = [HasRole("dart_leader")]
    permission_classes = [HasAnyRole("account_admin", "user_admin")]
"""

from __future__ import annotations

from rest_framework.permissions import BasePermission

from apps.accounts.roles import ACCOUNT_ADMIN, SYSTEM_ADMIN, USER_ADMIN


def user_has_any_role(user, slugs: tuple[str, ...]) -> bool:
    """Role test that is safe for anonymous users."""
    if user is None or not user.is_authenticated:
        return False
    if getattr(user, "is_superuser", False):
        return True
    held = set(user.roles)
    if SYSTEM_ADMIN in held:
        return True
    return bool(held & set(slugs))


class _RolePermission(BasePermission):
    """Base for the generated role permission classes."""

    required_roles: tuple[str, ...] = ()

    def has_permission(self, request, view) -> bool:
        return user_has_any_role(request.user, self.required_roles)


def HasAnyRole(*slugs: str) -> type[_RolePermission]:  # noqa: N802 - DRF style
    """Permission class granting access to holders of *any* of ``slugs``."""
    if not slugs:
        raise ValueError("HasAnyRole() requires at least one role slug")
    name = "HasAnyRole_" + "_".join(slugs)
    return type(name, (_RolePermission,), {"required_roles": tuple(slugs)})


def HasRole(slug: str) -> type[_RolePermission]:  # noqa: N802 - DRF style
    """Permission class granting access to holders of ``slug``."""
    return type(f"HasRole_{slug}", (_RolePermission,), {"required_roles": (slug,)})


# Convenience classes for the roles used across the API.
IsUserAdmin = HasRole(USER_ADMIN)
IsAccountAdmin = HasRole(ACCOUNT_ADMIN)
IsSystemAdmin = HasRole(SYSTEM_ADMIN)
