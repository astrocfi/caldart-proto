"""The report endpoints: the list, each report's columns, and its downloads.

One view per job serves every report in the registry: a report is found by the slug
in its URL, a slug the registry does not hold is a 404, and a caller whose roles the
report does not name is a 403.  An anonymous caller is a 401, from
``caldart.exceptions``.
"""

from __future__ import annotations

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.members.api.actors import acting_user
from apps.reports.api.serializers import (
    ReportSummaryDict,
    ReportSummarySerializer,
    SavedColumnSetSerializer,
)
from apps.reports.models import SavedColumnSet
from apps.reports.permissions import can_read_report
from apps.reports.registry import REPORTS, report_or_404
from caldart.reports import (
    CSV_MEDIA_TYPE,
    PDF_MEDIA_TYPE,
    Report,
    ReportColumnSerializer,
    ReportFormat,
    build_report,
    download_responses,
    report_response,
)


def readable_report(request: Request, slug: str) -> Report:
    """The report ``slug`` names, when the caller may read it.

    Raises ``Http404`` for a slug no report carries, whoever asks, and DRF's
    ``PermissionDenied`` for a caller the report's roles do not admit.
    """
    spec = report_or_404(slug)
    if not can_read_report(request.user, spec):
        raise PermissionDenied
    return spec


class ReportListView(APIView):
    """``GET /reports`` -- the reports the caller may read."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: ReportSummarySerializer(many=True)})
    def get(self, request: Request) -> Response:
        """200 with one entry per report the caller may read, in registry order.

        Any signed-in user may ask; a member who may read no report gets an empty
        list.
        """
        rows: list[ReportSummaryDict] = [
            {
                "slug": spec.slug,
                "title": spec.title,
                "choosable": spec.choosable,
                "periods": spec.periods,
            }
            for spec in REPORTS.values()
            if can_read_report(request.user, spec)
        ]
        # The stubs take the instance type from the single-object parameter, so
        # they do not widen it to a list when ``many`` is set.
        serializer = ReportSummarySerializer(rows, many=True)  # type: ignore[arg-type]
        return Response(serializer.data)


class ReportColumnsView(APIView):
    """``GET /reports/{slug}/columns`` -- what the report's downloads can carry."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: ReportColumnSerializer(many=True)})
    def get(self, request: Request, slug: str) -> Response:
        """200 with every column of the report, in export order.

        Each entry carries the ``key`` ``?columns=`` accepts, the ``label`` both
        formats print, and whether it is one of the ``default`` columns; every column
        of a fixed report is a default.  404 for an unknown report, 403 for a caller
        who may not read it.
        """
        spec = readable_report(request, slug)
        # As above: the stubs do not widen the instance type to a list for ``many``.
        serializer = ReportColumnSerializer(spec.column_choices(), many=True)  # type: ignore[arg-type]
        return Response(serializer.data)


class ReportExportView(APIView):
    """``GET /reports/{slug}/export.csv`` and ``export.pdf`` -- the report as a file."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={
            **download_responses(CSV_MEDIA_TYPE, "The report as a CSV file."),
            **download_responses(PDF_MEDIA_TYPE, "The report as a PDF file."),
        }
    )
    def get(self, request: Request, slug: str, fmt: ReportFormat) -> HttpResponse:
        """200 with the report as a dated ``<stem>-<YYYY-MM-DD>.<fmt>`` attachment.

        The query string carries the report's own filters, ``ordering``, ``columns``
        and, for a dated report, ``period``; they are applied exactly as the report's
        list applies them.  400 for a parameter the report refuses, keyed by that
        parameter; 404 for an unknown report; 403 for a caller who may not read it.
        """
        spec = readable_report(request, slug)
        document = build_report(spec, request.query_params.dict(), fmt=fmt)
        return report_response(document)


class ColumnSetListView(APIView):
    """``GET`` and ``POST /reports/{slug}/column-sets`` -- the caller's saved sets."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: SavedColumnSetSerializer(many=True)})
    def get(self, request: Request, slug: str) -> Response:
        """200 with the caller's own sets of the report's columns, by name.

        Another account's sets, and the caller's sets for other reports, are never
        listed.  404 for an unknown report, 403 for a caller who may not read it.
        """
        spec = readable_report(request, slug)
        sets = SavedColumnSet.objects.filter(user=acting_user(request), report=spec.slug)
        return Response(SavedColumnSetSerializer(sets, many=True).data)

    @extend_schema(request=SavedColumnSetSerializer, responses={201: SavedColumnSetSerializer})
    def post(self, request: Request, slug: str) -> Response:
        """201 with the set saved under ``name``: created, or replaced if the name is in use.

        Saving under a name the caller already uses for this report replaces that
        set's columns and keeps its id.  400 for a name or columns the serializer
        refuses; 404 and 403 as for ``GET``.
        """
        spec = readable_report(request, slug)
        serializer = SavedColumnSetSerializer(data=request.data, context={"spec": spec})
        serializer.is_valid(raise_exception=True)
        saved, _created = SavedColumnSet.objects.update_or_create(
            user=acting_user(request),
            report=spec.slug,
            name=serializer.validated_data["name"],
            defaults={"columns": serializer.validated_data["columns"]},
        )
        return Response(SavedColumnSetSerializer(saved).data, status=status.HTTP_201_CREATED)


class ColumnSetDetailView(APIView):
    """``DELETE /reports/{slug}/column-sets/{id}`` -- remove one of the caller's sets."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={204: None})
    def delete(self, request: Request, slug: str, pk: int) -> Response:
        """204 once the caller's own set is gone.

        A set that belongs to another account, or to another report, answers 404
        and is left alone.  404 for an unknown report, 403 for a caller who may not
        read it.
        """
        spec = readable_report(request, slug)
        saved = get_object_or_404(
            SavedColumnSet, pk=pk, user=acting_user(request), report=spec.slug
        )
        saved.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
