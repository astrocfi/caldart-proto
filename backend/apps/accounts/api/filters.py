"""django-filter filter sets for the users-admin list (PLAN §6.2)."""

from __future__ import annotations

import django_filters
from django.contrib.auth import get_user_model

from apps.accounts.roles import ROLE_SLUGS

User = get_user_model()


class UserFilter(django_filters.FilterSet):
    """``?role=&is_active=`` on ``GET /admin/users``.

    ``role`` matches the Django ``Group`` a role is stored as, so an unknown
    slug is a 400 rather than an empty page.
    """

    role = django_filters.ChoiceFilter(
        field_name="groups__name",
        choices=[(slug, slug) for slug in ROLE_SLUGS],
        label="Role slug",
    )
    is_active = django_filters.BooleanFilter(field_name="is_active")

    class Meta:
        model = User
        fields = ["role", "is_active"]
