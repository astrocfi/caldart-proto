"""The DART catalog, and the account administrator's DART screen.

``GET /darts`` is public: the join form and every "which DART?" box read it.
Everything else is gated on ``account_admin``; ``system_admin`` passes through
:func:`apps.accounts.permissions.user_has_any_role`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import Count, QuerySet
from rest_framework import generics
from rest_framework.permissions import AllowAny

from apps.accounts.permissions import IsAccountAdmin
from apps.darts.api.serializers import DartAdminSerializer, DartSerializer
from apps.darts.models import Dart
from apps.members.api.actors import acting_user
from caldart import audit

if TYPE_CHECKING:
    from rest_framework.serializers import BaseSerializer


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
        """Delete the DART, whatever still points at it, and count what that was.

        A member's profile and a website page both point at a DART with
        ``SET_NULL``: the members on it become unaffiliated and keep everything
        else about their record, and a linked page keeps its content and loses
        its DART.  The audit line carries the ``members`` and ``pages`` counts,
        because nothing here can be undone.
        """
        members = instance.members.count()
        pages = instance.pages.count()
        audit.record(
            audit.DART_DELETE,
            actor=acting_user(self.request),
            target=instance,
            members=members,
            pages=pages,
        )
        instance.delete()
