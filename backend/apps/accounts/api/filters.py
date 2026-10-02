"""django-filter filter sets for the users-admin list."""

from __future__ import annotations

import django_filters
from django.contrib.auth import get_user_model

from apps.accounts.models import AccountKind
from apps.accounts.roles import ROLE_SLUGS

User = get_user_model()


class UserFilter(django_filters.FilterSet):
    """``?role=&is_active=&kind=&email_bounced=`` on ``GET /admin/users``.

    ``role`` matches the Django ``Group`` a role is stored as, so an unknown
    slug is a 400 rather than an empty page.  ``kind`` matches the stored kind --
    ``member``, ``friend``, or ``donor`` -- and an unknown one is a 400 too.
    ``email_bounced=true`` keeps the accounts whose address has a bounce recorded and
    ``false`` those without one.
    """

    role = django_filters.ChoiceFilter(
        field_name="groups__name",
        choices=[(slug, slug) for slug in ROLE_SLUGS],
        label="Role slug",
    )
    is_active = django_filters.BooleanFilter(field_name="is_active")
    kind = django_filters.ChoiceFilter(choices=AccountKind.choices, label="Kind of account")
    # ``isnull`` excluded: true leaves the rows whose bounce time is set.
    email_bounced = django_filters.BooleanFilter(
        field_name="email_bounced_at", lookup_expr="isnull", exclude=True, label="Email bounced"
    )

    class Meta:
        model = User
        fields = ["role", "is_active", "kind", "email_bounced"]
