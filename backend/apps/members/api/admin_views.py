"""Account-administrator member and membership management.

Every view here is gated on ``account_admin`` but one: reading the member list,
``GET /admin/members``, also admits a ``dart_leader``, who sees the whole
membership.  ``system_admin`` passes through
:func:`apps.accounts.permissions.user_has_any_role`.  Anonymous callers get 401
from ``caldart.exceptions``, not 403.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.db import transaction
from django.db.models import QuerySet
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, status
from rest_framework.permissions import SAFE_METHODS, BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import HasAnyRole, IsAccountAdmin
from apps.accounts.roles import ACCOUNT_ADMIN, DART_LEADER
from apps.members.api.actors import acting_user
from apps.members.api.admin_serializers import (
    AdminMembershipSerializer,
    MemberCreateSerializer,
    MemberDetailSerializer,
    MemberListSerializer,
    MembershipGrantSerializer,
    MemberUpdateSerializer,
)
from apps.members.filters import (
    MemberAdminFilterSet,
    MemberOrderingFilter,
    member_admin_queryset,
)
from apps.members.models import Membership, MembershipSource
from apps.members.services import activate_term, delete_member
from caldart import audit

if TYPE_CHECKING:
    from apps.members.services import MemberRow

#: Who may read the member list: a DART leader as well as an account administrator.
MemberListReader = HasAnyRole(DART_LEADER, ACCOUNT_ADMIN)


class MemberAdminBaseView(generics.GenericAPIView["MemberRow"]):
    """Shared queryset, permission, and filter configuration."""

    permission_classes = [IsAccountAdmin]
    filter_backends = [DjangoFilterBackend, MemberOrderingFilter]
    filterset_class = MemberAdminFilterSet
    ordering = ["name"]

    def get_queryset(self) -> QuerySet[MemberRow]:
        """Every member and friend (never a donor), with the list's annotations."""
        return member_admin_queryset()


# The create handler answers with the whole member record rather than with the
# fields it accepted, so the response serializer is named here: the generic view's
# own ``serializer_class`` describes the request alone.
@extend_schema_view(
    post=extend_schema(request=MemberCreateSerializer, responses={201: MemberDetailSerializer})
)
class MemberAdminListCreateView(MemberAdminBaseView, generics.ListCreateAPIView["MemberRow"]):
    """``GET /admin/members`` (filtered, ordered, paginated) and ``POST``."""

    def get_permissions(self) -> list[BasePermission]:
        """A DART leader or an account administrator to read; only the latter to create.

        A leader reads the whole membership to find people for a mission, but
        adding somebody to it stays with the account administrator.
        """
        if self.request.method in SAFE_METHODS:
            return [MemberListReader()]
        return [IsAccountAdmin()]

    def get_serializer_class(self) -> type[BaseSerializer[Any]]:
        """The create serializer for a POST, the list row serializer otherwise."""
        return MemberCreateSerializer if self.request.method == "POST" else MemberListSerializer

    def create(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """201 with the created member, in the same shape ``GET`` of one returns.

        A body the create serializer refuses is a field-keyed 400 and writes
        nothing.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        detail = MemberDetailSerializer(self.get_queryset().get(pk=user.pk))
        return Response(detail.data, status=status.HTTP_201_CREATED)


# A PATCH answers with the whole member record too, however few fields it carried.
@extend_schema_view(
    patch=extend_schema(request=MemberUpdateSerializer, responses={200: MemberDetailSerializer})
)
class MemberAdminDetailView(
    MemberAdminBaseView, generics.RetrieveUpdateDestroyAPIView["MemberRow"]
):
    """``GET`` / ``PATCH`` / ``DELETE /admin/members/{user_id}``."""

    http_method_names = ["get", "patch", "delete", "head", "options"]
    filter_backends = []

    def get_queryset(self) -> QuerySet[MemberRow]:
        """Every account, a donor's included: the list leaves donors out, not the record.

        An administrator never reaches a donor from the member list, but a request
        naming one is answered from the record, so an edit that would make a donor a
        member or a friend is refused with the reason rather than a 404.
        """
        return member_admin_queryset(include_donors=True)

    def get_serializer_class(self) -> type[BaseSerializer[Any]]:
        """The update serializer for a PATCH, the detail serializer otherwise."""
        return MemberUpdateSerializer if self.request.method == "PATCH" else MemberDetailSerializer

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """200 with the whole member record, however few fields the PATCH carried.

        The edit is always partial, and a refused one is a field-keyed 400 that
        leaves both the account and the profile as they were.
        """
        instance = self.get_object()
        serializer = MemberUpdateSerializer(
            instance, data=request.data, partial=True, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(MemberDetailSerializer(self.get_queryset().get(pk=instance.pk)).data)

    def perform_destroy(self, instance: MemberRow) -> None:
        """Hard delete, refused three ways by ``members.services.delete_member``.

        Each refusal is a 403 carrying the sentence the service raised.
        """
        delete_member(acting_user(self.request), instance)


class MemberMembershipGrantView(APIView):
    """``POST /admin/members/{user_id}/memberships`` -- grant a term by hand."""

    permission_classes = [IsAccountAdmin]

    @extend_schema(request=MembershipGrantSerializer, responses={201: AdminMembershipSerializer})
    @transaction.atomic
    def post(self, request: Request, pk: int) -> Response:
        """201 with the granted term, recorded in the audit log.

        ``plan`` is a plan slug and must be an active plan; ``starts_on`` and
        ``note`` are optional, and a missing start date lets the service place
        the term after any coverage the member already has.  An unknown member
        is a 404 and a body the serializer refuses a field-keyed 400.
        """
        member = get_object_or_404(User, pk=pk)
        serializer = MembershipGrantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        term = activate_term(
            member,
            serializer.validated_data["plan"],
            source=MembershipSource.MANUAL,
            granted_by=acting_user(request),
            starts_on=serializer.validated_data.get("starts_on") or None,
            note=serializer.validated_data.get("note", ""),
        )
        audit.record(
            audit.MEMBERSHIP_GRANT,
            actor=acting_user(request),
            target=member,
            plan=term.plan.slug,
            term=term.pk,
        )
        return Response(AdminMembershipSerializer(term).data, status=status.HTTP_201_CREATED)


class MembershipAdminDetailView(generics.UpdateAPIView[Membership]):
    """``PATCH /admin/memberships/{id}`` -- correct a term's end date or status."""

    permission_classes = [IsAccountAdmin]
    serializer_class = AdminMembershipSerializer
    http_method_names = ["patch", "head", "options"]
    queryset = Membership.objects.select_related("plan", "granted_by", "user")

    def perform_update(self, serializer: BaseSerializer[Membership]) -> None:
        """Save the correction and record which of the term's fields it rewrote.

        The names are worked out before the save and cover only the fields whose
        value really changes, so a form that resends the whole term records the
        one field the administrator touched.
        """
        term = serializer.instance
        # ``UpdateModelMixin.update`` binds the row it loaded before calling this,
        # so the serializer always carries one here.
        assert term is not None  # noqa: S101 - mypy strict narrowing, not test code
        changed = [
            name
            for name, value in serializer.validated_data.items()
            if getattr(term, name) != value
        ]
        serializer.save()
        audit.record(
            audit.MEMBERSHIP_CORRECT,
            actor=acting_user(self.request),
            target=term.user,
            term=term.pk,
            fields=changed,
        )
