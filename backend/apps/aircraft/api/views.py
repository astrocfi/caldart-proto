"""Aircraft register, exports, and the DART leader check."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.http import HttpResponse, StreamingHttpResponse
    from rest_framework.request import Request
    from rest_framework.serializers import BaseSerializer

from apps.accounts.permissions import HasAnyRole, IsAccountAdmin, user_has_any_role
from apps.accounts.roles import ACCOUNT_ADMIN, DART_LEADER
from apps.aircraft import reports as aircraft_reports
from apps.aircraft import services
from apps.aircraft.api.filters import AircraftFilter, NullsLastOrderingFilter
from apps.aircraft.api.permissions import AircraftPermission
from apps.aircraft.api.serializers import (
    AircraftChangeSerializer,
    AircraftDetailSerializer,
    AircraftSerializer,
    LeaderSearchResultSerializer,
    LeaderStatusSerializer,
)
from apps.aircraft.models import Aircraft, AircraftChange, AircraftChangeKind, normalize_n_number
from apps.members.api.actors import acting_user
from caldart import audit
from caldart.reports import (
    CSV_MEDIA_TYPE,
    PDF_MEDIA_TYPE,
    ReportColumn,
    ReportColumnSerializer,
    chosen_columns,
    column_payload,
    csv_response,
    download_responses,
    filter_summary,
    pdf_table_response,
)

User = get_user_model()

#: The leader check is for leaders, and for the administrators who support
#: them; ``system_admin`` passes through ``user_has_any_role``.
IsLeader = HasAnyRole(DART_LEADER, ACCOUNT_ADMIN)

#: The first three are the core sorts; ``model`` and ``owner_name`` are here so
#: every column of the admin table is genuinely sortable.
ORDERING_FIELDS = ["n_number", "make", "insurance_expiration", "model", "owner_name"]

#: Roles that may see who flies an aircraft.
PILOT_ROLES: tuple[str, ...] = (DART_LEADER, ACCOUNT_ADMIN)


def aircraft_serializer_for(request: Request) -> type[AircraftSerializer]:
    """The register record, with ``pilots`` only for callers entitled to it.

    ``pilots`` carries other members' email addresses, membership state and
    medical currency -- exactly what the leader check gates behind ``dart_leader``.
    Returning it from the register to every signed-in member would walk
    straight around that gate, so plain members get the aircraft alone.
    """
    if user_has_any_role(request.user, PILOT_ROLES):
        return AircraftDetailSerializer
    return AircraftSerializer


class AircraftQuerysetMixin(generics.GenericAPIView[Aircraft]):
    """The register, filtered and ordered identically everywhere."""

    queryset = Aircraft.objects.all()
    filter_backends = [DjangoFilterBackend, NullsLastOrderingFilter]
    filterset_class = AircraftFilter
    ordering_fields = ORDERING_FIELDS
    ordering = ["n_number"]


class AircraftListCreateView(AircraftQuerysetMixin, generics.ListCreateAPIView[Aircraft]):
    """``GET /aircraft`` (any member) and ``POST /aircraft`` (any member)."""

    serializer_class = AircraftSerializer
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def perform_create(self, serializer: BaseSerializer[Aircraft]) -> None:
        """Save the new aircraft, recording who added it in the history and the log.

        The record and its history row commit together: a failure writing the trail
        rolls the record back with it, so no aircraft can exist without a ``created``
        row naming who added it.
        """
        actor = acting_user(self.request)
        aircraft = serializer.save(created_by=actor)
        services.record_change(aircraft, actor=actor, kind=AircraftChangeKind.CREATED, fields=[])
        audit.record(audit.AIRCRAFT_CREATE, actor=actor, target=aircraft)


class AircraftDetailView(generics.RetrieveUpdateDestroyAPIView[Aircraft]):
    """``GET/PATCH/DELETE /aircraft/{id}`` with the register's object rules."""

    queryset = Aircraft.objects.all()
    permission_classes = [AircraftPermission]

    def get_serializer_class(self) -> type[AircraftSerializer]:
        """Return the serializer ``aircraft_serializer_for`` picks for this request.

        A DART leader or account admin gets ``AircraftDetailSerializer``, whose payload
        includes ``pilots``; every other signed-in member gets ``AircraftSerializer``,
        the same record without that field.
        """
        return aircraft_serializer_for(self.request)

    @transaction.atomic
    def perform_update(self, serializer: BaseSerializer[Aircraft]) -> None:
        """Save the edit, then record who made it and which columns moved.

        The field list is worked out before the save, while ``serializer.instance``
        still carries the stored values (a model serializer assigns the validated
        attributes during ``save()``), so a form that resends every field it shows
        names only the ones whose value actually changed.  The edit and its history
        row commit together, so no write can leave the trail behind.
        """
        instance = cast("Aircraft", serializer.instance)
        fields = services.changed_fields(instance, dict(serializer.validated_data))
        actor = acting_user(self.request)
        aircraft = serializer.save()
        services.record_change(
            aircraft, actor=actor, kind=AircraftChangeKind.UPDATED, fields=fields
        )
        audit.record(audit.AIRCRAFT_UPDATE, actor=actor, target=aircraft, fields=fields)

    def perform_destroy(self, instance: Aircraft) -> None:
        """Delete the record, its history with it, and log the deletion."""
        audit.record(audit.AIRCRAFT_DELETE, actor=acting_user(self.request), target=instance)
        instance.delete()


class AircraftChangesView(generics.ListAPIView[AircraftChange]):
    """``GET /aircraft/{id}/changes`` -- who changed one record, newest first."""

    serializer_class = AircraftChangeSerializer
    permission_classes = [IsAccountAdmin]
    pagination_class = None

    def get_queryset(self) -> QuerySet[AircraftChange]:
        """The changes to the aircraft in the URL, newest first, with each actor joined.

        Answers 404 when no aircraft has that id, rather than an empty history.
        """
        aircraft = get_object_or_404(Aircraft, pk=self.kwargs["pk"])
        return aircraft.changes.select_related("changed_by")


class AircraftLookupView(APIView):
    """``GET /aircraft/lookup?n_number=`` -- exact match after normalization."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: AircraftDetailSerializer})
    def get(self, request: Request) -> Response:
        """Look up the aircraft with the normalized ``n_number``.

        Answers 400 when ``n_number`` is missing or normalizes to nothing, and 404 when
        no aircraft matches.
        """
        n_number = normalize_n_number(request.query_params.get("n_number", ""))
        if not n_number:
            return Response({"n_number": "Enter a registration, for example N12345."}, status=400)
        aircraft = get_object_or_404(Aircraft, n_number=n_number)
        serializer_class = aircraft_serializer_for(request)
        return Response(serializer_class(aircraft).data)


# --------------------------------------------------------------------------
# Exports -- account_admin
# --------------------------------------------------------------------------
class AircraftColumnsView(APIView):
    """``GET /admin/aircraft/columns`` -- what the register exports can carry."""

    permission_classes = [IsAccountAdmin]

    @extend_schema(responses={200: ReportColumnSerializer(many=True)})
    def get(self, request: Request) -> Response:
        """200 with every export column, in export order, for an account administrator.

        Each entry carries the ``key`` ``?columns=`` accepts, the ``label`` both
        exports print, and whether it is one of the ``default`` columns.
        """
        rows = column_payload(aircraft_reports.AIRCRAFT_REPORT_COLUMNS)
        # The stubs take the instance type from the single-object parameter, so
        # they do not widen it to a list when ``many`` is set.
        serializer = ReportColumnSerializer(rows, many=True)  # type: ignore[arg-type]
        return Response(serializer.data)


class AircraftExportMixin(AircraftQuerysetMixin):
    """Shared plumbing: same filters as the list, account_admin only."""

    permission_classes = [IsAccountAdmin]
    serializer_class = AircraftSerializer

    def columns(self) -> list[ReportColumn[aircraft_reports.AircraftRow]]:
        """The columns ``?columns=`` asks for, or the default ones."""
        return chosen_columns(
            aircraft_reports.AIRCRAFT_REPORT_COLUMNS,
            self.request.query_params.get("columns", ""),
        )

    def export_queryset(self) -> QuerySet[Aircraft]:
        """Return the filtered register with the pilot join prefetched for export."""
        return aircraft_reports.export_queryset(self.filter_queryset(self.get_queryset()))

    def applied_filters(self) -> dict[str, str]:
        """Every filter the list accepts, so the PDF says what it left out."""
        wanted = (
            "search",
            "make",
            "owner_type",
            "insurance",
            "expiring_within",
            "is_active",
            "ordering",
        )
        return {key: self.request.query_params.get(key, "") for key in wanted}

    def filename(self, suffix: str) -> str:
        """Return today's export filename with the given extension, e.g. ``...csv``."""
        return f"caldart-aircraft-{timezone.localdate().isoformat()}.{suffix}"


class AircraftExportCsvView(AircraftExportMixin, generics.GenericAPIView[Aircraft]):
    """``GET /admin/aircraft/export.csv?<filters>``."""

    @extend_schema(
        responses=download_responses(CSV_MEDIA_TYPE, "The aircraft register as a CSV file.")
    )
    def get(self, request: Request) -> StreamingHttpResponse:
        """Return the filtered register as a CSV file for download.

        ``?columns=`` chooses which columns appear and in what order; an unknown
        or repeated key is a 400 keyed ``columns``.  The header row is the column
        labels, and insured amounts are plain numbers a spreadsheet sums.
        """
        columns = self.columns()
        return csv_response(
            self.filename("csv"),
            [column.label for column in columns],
            aircraft_reports.aircraft_rows(self.export_queryset(), columns),
        )


class AircraftExportPdfView(AircraftExportMixin, generics.GenericAPIView[Aircraft]):
    """``GET /admin/aircraft/export.pdf?<filters>`` -- landscape letter."""

    @extend_schema(
        responses=download_responses(PDF_MEDIA_TYPE, "The aircraft register as a PDF file.")
    )
    def get(self, request: Request) -> HttpResponse:
        """Return the filtered register as a landscape-letter PDF for download.

        The same ``?columns=`` as the CSV applies, each chosen column takes the
        share of the page its registry width asks for, and insured amounts are
        rendered as dollars for a reader.
        """
        columns = self.columns()
        return pdf_table_response(
            self.filename("pdf"),
            title=aircraft_reports.REPORT_TITLE,
            subtitle=filter_summary(self.applied_filters()),
            header=[column.label for column in columns],
            rows=aircraft_reports.aircraft_rows(self.export_queryset(), columns, currency=True),
            widths=[column.width for column in columns],
        )


# --------------------------------------------------------------------------
# Leader check -- dart_leader
# --------------------------------------------------------------------------
class LeaderSearchView(APIView):
    """``GET /leader/search?q=<name|email|n-number>`` -- at most 20 people."""

    permission_classes = [IsLeader]

    @extend_schema(responses={200: LeaderSearchResultSerializer(many=True)})
    def get(self, request: Request) -> Response:
        """Return up to 20 members matching ``q`` by name, email, or N-number."""
        query = request.query_params.get("q", "")
        results = [services.search_result(user) for user in services.search_members(query)]
        return Response(LeaderSearchResultSerializer(results, many=True).data)


class LeaderMemberStatusView(APIView):
    """``GET /leader/members/{user_id}/status`` -- the pre-flight status card."""

    permission_classes = [IsLeader]

    @extend_schema(responses={200: LeaderStatusSerializer})
    def get(self, request: Request, user_id: int) -> Response:
        """Return the pre-flight status card for the member with primary key ``user_id``.

        Answers 404 when no such member exists.
        """
        user = get_object_or_404(
            User.objects.select_related("profile", "profile__dart"), pk=user_id
        )
        return Response(LeaderStatusSerializer(services.leader_status(user)).data)


class LeaderAircraftView(APIView):
    """``GET /leader/aircraft?n_number=`` -- the insurance card for one plane."""

    permission_classes = [IsLeader]

    @extend_schema(responses={200: AircraftDetailSerializer})
    def get(self, request: Request) -> Response:
        """Return the insurance card for the aircraft with the normalized ``n_number``.

        Answers 400 when ``n_number`` is missing or normalizes to nothing, and 404 when
        no aircraft matches.
        """
        n_number = normalize_n_number(request.query_params.get("n_number", ""))
        if not n_number:
            return Response({"n_number": "Enter a registration, for example N12345."}, status=400)
        aircraft = get_object_or_404(Aircraft, n_number=n_number)
        return Response(AircraftDetailSerializer(aircraft).data)
