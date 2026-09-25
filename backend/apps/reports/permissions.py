"""Who may read a report."""

from __future__ import annotations

from django.contrib.auth.models import AnonymousUser

from apps.accounts.models import User
from apps.accounts.permissions import user_has_any_role
from caldart.reports import Report


def can_read_report(user: User | AnonymousUser | None, spec: Report) -> bool:
    """True when ``user`` holds one of the roles ``spec`` names.

    A system administrator and a Django superuser may read every report; an anonymous
    caller may read none.
    """
    return user_has_any_role(user, spec.roles)
