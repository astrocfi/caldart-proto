"""The report endpoints: the list, each report's columns, and its downloads.

One view per job serves every report in the registry: a report is found by the slug
in its URL, a slug the registry does not hold is a 404, and a caller whose roles the
report does not name is a 403.  An anonymous caller is a 401, from
``caldart.exceptions``.
"""

from __future__ import annotations

from django.http import HttpResponse
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.reports.api.serializers import ReportSummaryDict, ReportSummarySerializer
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
