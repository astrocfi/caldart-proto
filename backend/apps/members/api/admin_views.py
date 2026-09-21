"""Account-administrator member management and reports.

Every view here is gated on ``account_admin``; ``system_admin`` passes through
:func:`apps.accounts.permissions.user_has_any_role`.  Anonymous callers get 401
from ``caldart.exceptions``, not 403.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAccountAdmin
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
from caldart.reports import csv_response, filter_summary, pdf_table_response

User = get_user_model()


class MemberAdminBaseView(generics.GenericAPIView):
    """Shared queryset, permission and filter configuration."""

    permission_classes = [IsAccountAdmin]
    filter_backends = [DjangoFilterBackend, MemberOrderingFilter]
    filterset_class = MemberAdminFilterSet
    ordering = ["name"]

    def get_queryset(self):
        return member_admin_queryset()


class MemberAdminListCreateView(MemberAdminBaseView, generics.ListCreateAPIView):
    """``GET /admin/members`` (filtered, ordered, paginated) and ``POST``."""

    def get_serializer_class(self):
        return MemberCreateSerializer if self.request.method == "POST" else MemberListSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        detail = MemberDetailSerializer(self.get_queryset().get(pk=user.pk))
        return Response(detail.data, status=status.HTTP_201_CREATED)


class MemberAdminDetailView(MemberAdminBaseView, generics.RetrieveUpdateDestroyAPIView):
    """``GET`` / ``PATCH`` / ``DELETE /admin/members/{user_id}``."""

    http_method_names = ["get", "patch", "delete", "head", "options"]
    filter_backends: list = []

    def get_serializer_class(self):
        return MemberUpdateSerializer if self.request.method == "PATCH" else MemberDetailSerializer

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = MemberUpdateSerializer(
            instance, data=request.data, partial=True, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(MemberDetailSerializer(self.get_queryset().get(pk=instance.pk)).data)

    def perform_destroy(self, instance):
        """Hard delete, refused three ways by ``members.services.delete_member``.

        Each refusal is a 403 carrying the sentence the service raised.
        """
        delete_member(self.request.user, instance)


class MemberMembershipGrantView(APIView):
    """``POST /admin/members/{user_id}/memberships`` — grant a term by hand."""

    permission_classes = [IsAccountAdmin]

    @transaction.atomic
    def post(self, request, pk: int):
        member = get_object_or_404(User, pk=pk)
        serializer = MembershipGrantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        term = activate_term(
            member,
            serializer.validated_data["plan"],
            source=MembershipSource.MANUAL,
            granted_by=request.user,
            starts_on=serializer.validated_data.get("starts_on") or None,
            note=serializer.validated_data.get("note", ""),
        )
        return Response(AdminMembershipSerializer(term).data, status=status.HTTP_201_CREATED)


class MembershipAdminDetailView(generics.UpdateAPIView):
    """``PATCH /admin/memberships/{id}`` — correct a term's end date or status."""

    permission_classes = [IsAccountAdmin]
    serializer_class = AdminMembershipSerializer
    http_method_names = ["patch", "head", "options"]
    queryset = Membership.objects.select_related("plan", "granted_by", "user")


# --------------------------------------------------------------------------
# Exports
# --------------------------------------------------------------------------
class MemberExportBaseView(MemberAdminBaseView):
    """The filtered member list, rendered as a downloadable report."""

    pagination_class = None
    serializer_class = MemberListSerializer

    def rows(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        return member_report_rows(queryset.iterator(chunk_size=200))

    def subtitle(self, request) -> str:
        return filter_summary(applied_filters(request))


class MemberExportCsvView(MemberExportBaseView):
    """``GET /admin/members/export.csv``."""

    def get(self, request, *args, **kwargs):
        return csv_response(member_report_filename("csv"), MEMBER_REPORT_HEADER, self.rows(request))


class MemberExportPdfView(MemberExportBaseView):
    """``GET /admin/members/export.pdf`` — landscape letter."""

    def get(self, request, *args, **kwargs):
        return pdf_table_response(
            member_report_filename("pdf"),
            title=REPORT_TITLE,
            subtitle=self.subtitle(request),
            header=MEMBER_REPORT_HEADER,
            rows=self.rows(request),
            landscape=True,
        )
