"""Account-administrator member management and reports.

Every view here is gated on ``account_admin``; ``system_admin`` passes through
:func:`apps.accounts.permissions.user_has_any_role`.  Anonymous callers get 401
from ``caldart.exceptions``, not 403.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from django.db import transaction
from django.db.models import QuerySet
from django.http import HttpResponse, StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import IsAccountAdmin
from apps.members.api.actors import acting_user
from apps.members.api.admin_filters import (
    MemberAdminFilterSet,
    MemberOrderingFilter,
    applied_filters,
    member_admin_queryset,
)
from apps.members.api.admin_serializers import (
    AdminMembershipSerializer,
    MemberCreateSerializer,
    MemberDetailSerializer,
    MemberListSerializer,
    MembershipGrantSerializer,
    MemberUpdateSerializer,
)
from apps.members.models import Membership, MembershipSource
from apps.members.reports import (
    MEMBER_REPORT_HEADER,
    REPORT_TITLE,
    member_report_filename,
    member_report_rows,
)
from apps.members.services import activate_term, delete_member
from caldart import audit
from caldart.reports import (
    CSV_MEDIA_TYPE,
    PDF_MEDIA_TYPE,
    csv_response,
    download_responses,
    filter_summary,
    pdf_table_response,
)

if TYPE_CHECKING:
    from apps.members.services import MemberRow


class MemberAdminBaseView(generics.GenericAPIView["MemberRow"]):
    """Shared queryset, permission and filter configuration."""

    permission_classes = [IsAccountAdmin]
    filter_backends = [DjangoFilterBackend, MemberOrderingFilter]
    filterset_class = MemberAdminFilterSet
    ordering = ["name"]

    def get_queryset(self) -> QuerySet[MemberRow]:
        """Every account, carrying the membership annotations the list reads."""
        return member_admin_queryset()


# The create handler answers with the whole member record rather than with the
# fields it accepted, so the response serializer is named here: the generic view's
# own ``serializer_class`` describes the request alone.
@extend_schema_view(
    post=extend_schema(request=MemberCreateSerializer, responses={201: MemberDetailSerializer})
)
class MemberAdminListCreateView(MemberAdminBaseView, generics.ListCreateAPIView["MemberRow"]):
    """``GET /admin/members`` (filtered, ordered, paginated) and ``POST``."""

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
    """``POST /admin/members/{user_id}/memberships`` — grant a term by hand."""

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
    """``PATCH /admin/memberships/{id}`` — correct a term's end date or status."""

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


# --------------------------------------------------------------------------
# Exports
# --------------------------------------------------------------------------
class MemberExportBaseView(MemberAdminBaseView):
    """The filtered member list, rendered as a downloadable report."""

    pagination_class = None
    serializer_class = MemberListSerializer

    def rows(self, request: Request) -> Iterator[list[str]]:
        """The report rows for the filtered list, streamed a chunk at a time."""
        queryset = self.filter_queryset(self.get_queryset())
        return member_report_rows(queryset.iterator(chunk_size=200))

    def subtitle(self, request: Request) -> str:
        """The filters the caller asked for, as one line under the report title."""
        return filter_summary(applied_filters(request))


class MemberExportCsvView(MemberExportBaseView):
    """``GET /admin/members/export.csv``."""

    @extend_schema(responses=download_responses(CSV_MEDIA_TYPE, "The member list as a CSV file."))
    def get(self, request: Request, *args: Any, **kwargs: Any) -> StreamingHttpResponse:
        """The filtered member list as a streamed CSV download."""
        return csv_response(member_report_filename("csv"), MEMBER_REPORT_HEADER, self.rows(request))


class MemberExportPdfView(MemberExportBaseView):
    """``GET /admin/members/export.pdf`` — landscape letter."""

    @extend_schema(responses=download_responses(PDF_MEDIA_TYPE, "The member list as a PDF file."))
    def get(self, request: Request, *args: Any, **kwargs: Any) -> HttpResponse:
        """The filtered member list as a landscape-letter PDF download."""
        return pdf_table_response(
            member_report_filename("pdf"),
            title=REPORT_TITLE,
            subtitle=self.subtitle(request),
            header=MEMBER_REPORT_HEADER,
            rows=self.rows(request),
            landscape=True,
        )
