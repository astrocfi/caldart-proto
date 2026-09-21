"""DRF permission classes for role checks.

``system_admin`` always passes.  Use them either as classes built by the
factory helpers or by subclassing::

    permission_classes = [HasRole("dart_leader")]
    permission_classes = [HasAnyRole("account_admin", "user_admin")]
"""

from __future__ import annotations

from django.contrib.auth.models import AnonymousUser
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.roles import ACCOUNT_ADMIN, SYSTEM_ADMIN, USER_ADMIN


def user_has_any_role(user: User | AnonymousUser | None, slugs: tuple[str, ...]) -> bool:
    """True when ``user`` holds at least one of ``slugs``.

    ``None`` and an anonymous user are False rather than an error.  A Django
    superuser and a ``system_admin`` are True whatever ``slugs`` names; everyone else
    needs one of the slugs among their own roles.  An empty ``slugs`` is therefore
    False for an ordinary account.
    """
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

    def has_permission(self, request: Request, view: APIView) -> bool:
        """True when the request's user holds one of ``required_roles``.

        A Django superuser and a ``system_admin`` pass whatever ``required_roles``
        names, and an anonymous caller is always False.
        """
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
