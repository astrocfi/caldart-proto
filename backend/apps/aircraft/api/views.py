"""Aircraft register, exports and the DART leader check (PLAN §6.5, §6.6)."""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasAnyRole, IsAccountAdmin
from apps.accounts.roles import ACCOUNT_ADMIN, DART_LEADER
from apps.aircraft import reports as aircraft_reports
from apps.aircraft import services
from apps.aircraft.api.filters import AircraftFilter, NullsLastOrderingFilter
from apps.aircraft.api.permissions import AircraftPermission
from apps.aircraft.api.serializers import (
    AircraftDetailSerializer,
    AircraftSerializer,
    LeaderSearchResultSerializer,
    LeaderStatusSerializer,
)
from apps.aircraft.models import Aircraft, normalize_n_number
from caldart.reports import csv_response, filter_summary, pdf_table_response

User = get_user_model()

#: The leader check is for leaders, and for the administrators who support
#: them; ``system_admin`` passes through ``user_has_any_role`` (PLAN §5).
IsLeader = HasAnyRole(DART_LEADER, ACCOUNT_ADMIN)

ORDERING_FIELDS = ["n_number", "make", "insurance_expiration"]


class AircraftQuerysetMixin:
    """The register, filtered and ordered identically everywhere (PLAN §6.5)."""

    queryset = Aircraft.objects.all()
    filter_backends = [DjangoFilterBackend, NullsLastOrderingFilter]
    filterset_class = AircraftFilter
    ordering_fields = ORDERING_FIELDS
    ordering = ["n_number"]


class AircraftListCreateView(AircraftQuerysetMixin, generics.ListCreateAPIView):
    """``GET /aircraft`` (any member) and ``POST /aircraft`` (any member)."""

    serializer_class = AircraftSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer) -> None:
        serializer.save(created_by=self.request.user)


class AircraftDetailView(generics.RetrieveUpdateDestroyAPIView):
    """``GET/PATCH/DELETE /aircraft/{id}`` with the object rules of §6.5."""

    queryset = Aircraft.objects.all()
    serializer_class = AircraftDetailSerializer
    permission_classes = [AircraftPermission]


class AircraftLookupView(APIView):
    """``GET /aircraft/lookup?n_number=`` — exact match after normalisation."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        n_number = normalize_n_number(request.query_params.get("n_number", ""))
        if not n_number:
            return Response({"n_number": "Enter a registration, for example N12345."}, status=400)
        aircraft = get_object_or_404(Aircraft, n_number=n_number)
        return Response(AircraftDetailSerializer(aircraft).data)


# --------------------------------------------------------------------------
# Exports (PLAN §11) — account_admin
# --------------------------------------------------------------------------
class AircraftExportMixin(AircraftQuerysetMixin):
    """Shared plumbing: same filters as the list, account_admin only."""

    permission_classes = [IsAccountAdmin]
    serializer_class = AircraftSerializer

    def export_queryset(self):
        return aircraft_reports.export_queryset(self.filter_queryset(self.get_queryset()))

    def applied_filters(self) -> dict[str, str]:
        wanted = ("search", "make", "owner_type", "insurance", "expiring_within", "ordering")
        return {key: self.request.query_params.get(key, "") for key in wanted}

    def filename(self, suffix: str) -> str:
        return f"caldart-aircraft-{timezone.localdate().isoformat()}.{suffix}"


class AircraftExportCsvView(AircraftExportMixin, generics.GenericAPIView):
    """``GET /admin/aircraft/export.csv?<filters>``."""

    def get(self, request):
        return csv_response(
            self.filename("csv"),
            aircraft_reports.HEADER,
            aircraft_reports.aircraft_rows(self.export_queryset()),
        )


class AircraftExportPdfView(AircraftExportMixin, generics.GenericAPIView):
    """``GET /admin/aircraft/export.pdf?<filters>`` — landscape letter."""

    def get(self, request):
        return pdf_table_response(
            self.filename("pdf"),
            title="CalDART aircraft register",
            subtitle=filter_summary(self.applied_filters()),
            header=aircraft_reports.PDF_HEADER,
            rows=aircraft_reports.aircraft_rows(self.export_queryset(), currency=True),
        )


# --------------------------------------------------------------------------
# Leader check (PLAN §6.6) — dart_leader
# --------------------------------------------------------------------------
class LeaderSearchView(APIView):
    """``GET /leader/search?q=<name|email|n-number>`` — at most 20 people."""

    permission_classes = [IsLeader]

    def get(self, request):
        query = request.query_params.get("q", "")
        results = [services.search_result(user) for user in services.search_members(query)]
        return Response(LeaderSearchResultSerializer(results, many=True).data)


class LeaderMemberStatusView(APIView):
    """``GET /leader/members/{user_id}/status`` — the pre-flight status card."""

    permission_classes = [IsLeader]

    def get(self, request, user_id: int):
        user = get_object_or_404(
            User.objects.select_related("profile", "profile__dart"), pk=user_id
        )
        return Response(LeaderStatusSerializer(services.leader_status(user)).data)


class LeaderAircraftView(APIView):
    """``GET /leader/aircraft?n_number=`` — the insurance card for one plane."""

    permission_classes = [IsLeader]

    def get(self, request):
        n_number = normalize_n_number(request.query_params.get("n_number", ""))
        if not n_number:
            return Response({"n_number": "Enter a registration, for example N12345."}, status=400)
        aircraft = get_object_or_404(Aircraft, n_number=n_number)
        return Response(AircraftDetailSerializer(aircraft).data)
