"""The DART catalog, and the account administrator's DART screen.

``GET /darts`` is public: the join form and every "which DART?" box read it.
Everything else is gated on ``account_admin``; ``system_admin`` passes through
:func:`apps.accounts.permissions.user_has_any_role`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Count, QuerySet
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny

from apps.accounts.permissions import IsAccountAdmin
from apps.darts.api.serializers import DartAdminSerializer, DartSerializer
from apps.darts.models import Dart
from apps.members.api.actors import acting_user
from caldart import audit

if TYPE_CHECKING:
    from rest_framework.serializers import BaseSerializer


def dart_in_use_message(members: int, pages: int) -> str:
    """Why a DART cannot be deleted, counting what still points at it.

    Names the members on the DART, the website pages linked to it, or both,
    and says what to do instead.
    """
    parts = []
    if members:
        parts.append(f"{members} member{'s' if members != 1 else ''}")
    if pages:
        parts.append(f"{pages} website page{'s' if pages != 1 else ''}")
    return (
        f"This DART still has {' and '.join(parts)}. "
        "Move them first, or turn off 'Accepting members' to retire it."
    )


class DartListView(generics.ListAPIView[Dart]):
    """``GET /darts`` -- public, active DARTs in their configured order."""

    serializer_class = DartSerializer
    permission_classes = [AllowAny]
    pagination_class = None
    queryset = Dart.objects.filter(is_active=True).prefetch_related("contacts")


class DartAdminBaseView(generics.GenericAPIView[Dart]):
    """Every DART, with the counts and the people each screen shows."""

    permission_classes = [IsAccountAdmin]
    serializer_class = DartAdminSerializer
    pagination_class = None

    def get_queryset(self) -> QuerySet[Dart]:
        """Every DART by name, with its people and the two counts.

        The ordering is named here rather than left to the model: a queryset
        that groups by a count does not carry ``Meta.ordering`` through.
        """
        return (
            Dart.objects.annotate(
                member_count=Count("members", distinct=True),
                page_count=Count("pages", distinct=True),
            )
            .prefetch_related("contacts")
            .order_by("name")
        )


class DartAdminListCreateView(DartAdminBaseView, generics.ListCreateAPIView[Dart]):
    """``GET /admin/darts`` (every DART, active or not) and ``POST``."""

    def perform_create(self, serializer: BaseSerializer[Dart]) -> None:
        """Save the DART and write one audit line naming it."""
        dart = serializer.save()
        audit.record(audit.DART_CREATE, actor=acting_user(self.request), target=dart)


class DartAdminDetailView(DartAdminBaseView, generics.RetrieveUpdateDestroyAPIView[Dart]):
    """``GET`` / ``PATCH`` / ``DELETE /admin/darts/{id}``."""

    http_method_names = ["get", "patch", "delete", "head", "options"]

    def perform_update(self, serializer: BaseSerializer[Dart]) -> None:
        """Save the edit and write one audit line naming the DART."""
        dart = serializer.save()
        audit.record(audit.DART_UPDATE, actor=acting_user(self.request), target=dart)

    def perform_destroy(self, instance: Dart) -> None:
        """Delete a DART nothing points at, and refuse one that is in use.

        A member's profile and a website page both point at a DART with
        ``SET_NULL``, so deleting one in use would quietly empty those fields.
        The answer is a 400 naming what would be left behind, and the screen
        offers "not accepting members" instead, which keeps the history.
        """
        members = instance.members.count()
        pages = instance.pages.count()
        if members or pages:
            audit.refuse(
                audit.DART_DELETE,
                actor=acting_user(self.request),
                target=instance,
                reason=audit.REASON_DART_IN_USE,
            )
            raise ValidationError({"detail": dart_in_use_message(members, pages)})
        audit.record(audit.DART_DELETE, actor=acting_user(self.request), target=instance)
        instance.delete()
