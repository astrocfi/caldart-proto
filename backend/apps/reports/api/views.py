"""The report endpoints: the reports, their columns, downloads, saved sets, and email.

One view per job serves every report in the registry: a report is found by the slug
in its URL, a slug the registry does not hold is a 404, and a caller whose roles the
report does not name is a 403.  An anonymous caller is a 401, from
``caldart.exceptions``.

The subscriptions are the finance roles' (``treasurer`` and ``account_admin``), and a
caller sees and touches only those for reports they may read; the DART rosters are
the account administrator's; the manual run is the system administrator's.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db.models import QuerySet
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAccountAdmin, IsFinance, IsSystemAdmin
from apps.darts.models import Dart
from apps.members.api.actors import acting_user
from apps.reports.api.serializers import (
    ReportRunRequestSerializer,
    ReportRunResultSerializer,
    ReportSubscriptionCreateSerializer,
    ReportSubscriptionSerializer,
    ReportSummaryDict,
    ReportSummarySerializer,
    RosterSerializer,
    SavedColumnSetSerializer,
)
from apps.reports.models import ReportSubscription, SavedColumnSet
from apps.reports.permissions import can_read_report
from apps.reports.registry import REPORTS, report_or_404
from apps.reports.services import (
    ReportRun,
    run_scheduled_reports,
    send_rosters_now,
    send_subscription_now,
)
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

if TYPE_CHECKING:
    from rest_framework.serializers import BaseSerializer


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
        """201 with the set saved under ``name``, replacing one of that name if any.

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


def visible_subscriptions(request: Request) -> QuerySet[ReportSubscription]:
    """The subscriptions for every report the caller may read, with their accounts."""
    user = acting_user(request)
    slugs = [slug for slug, spec in REPORTS.items() if can_read_report(user, spec)]
    return ReportSubscription.objects.filter(report__in=slugs).select_related(
        "recipient_user", "created_by"
    )


def run_response(run: ReportRun) -> Response:
    """200 with ``run`` as :class:`ReportRunResultSerializer` renders it."""
    return Response(ReportRunResultSerializer(run.as_dict()).data)


class SubscriptionListView(APIView):
    """``GET`` and ``POST /reports/subscriptions`` -- the reports sent by email."""

    permission_classes = [IsFinance]

    @extend_schema(responses={200: ReportSubscriptionSerializer(many=True)})
    def get(self, request: Request) -> Response:
        """200 with every subscription for a report the caller may read, unpaginated.

        Ordered by report, then by address.
        """
        rows = visible_subscriptions(request)
        return Response(ReportSubscriptionSerializer(rows, many=True).data)

    @extend_schema(
        request=ReportSubscriptionCreateSerializer, responses={201: ReportSubscriptionSerializer}
    )
    def post(self, request: Request) -> Response:
        """201 with the subscription set up; 400 for a body the serializer refuses.

        A report the caller may not read answers 403 before anything else is checked.
        """
        slug = request.data.get("report") if isinstance(request.data, dict) else None
        if isinstance(slug, str) and slug in REPORTS:
            readable_report(request, slug)
        serializer = ReportSubscriptionCreateSerializer(
            data=request.data, context={"creator": acting_user(request)}
        )
        serializer.is_valid(raise_exception=True)
        subscription = serializer.save()
        return Response(
            ReportSubscriptionSerializer(subscription).data, status=status.HTTP_201_CREATED
        )


class SubscriptionDetailView(generics.RetrieveUpdateDestroyAPIView[ReportSubscription]):
    """``GET``, ``PATCH`` and ``DELETE /reports/subscriptions/{id}``.

    A subscription for a report the caller may not read answers 404.
    """

    permission_classes = [IsFinance]
    serializer_class = ReportSubscriptionSerializer
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self) -> QuerySet[ReportSubscription]:
        """The subscriptions the caller may see."""
        return visible_subscriptions(self.request)

    def perform_update(self, serializer: BaseSerializer[ReportSubscription]) -> None:
        """Save the edit the serializer checked."""
        serializer.save()


class SubscriptionSendView(APIView):
    """``POST /reports/subscriptions/{id}/send`` -- send one subscription now."""

    permission_classes = [IsFinance]

    @extend_schema(request=None, responses={200: ReportRunResultSerializer})
    def post(self, request: Request, pk: int) -> Response:
        """200 with the run result of the one send, whatever the subscription's date.

        ``next_due_on`` stays where it is.  404 for a subscription for a report the
        caller may not read.
        """
        subscription = get_object_or_404(visible_subscriptions(request), pk=pk)
        return run_response(send_subscription_now(subscription, actor=acting_user(request)))


class RosterListView(generics.ListAPIView[Dart]):
    """``GET /reports/rosters`` -- every active DART's roster, by name."""

    permission_classes = [IsAccountAdmin]
    serializer_class = RosterSerializer
    pagination_class = None

    def get_queryset(self) -> QuerySet[Dart]:
        """Every active DART by name, with its people."""
        return Dart.objects.filter(is_active=True).prefetch_related("contacts").order_by("name")


class RosterSendView(APIView):
    """``POST /reports/rosters/send`` -- every DART's roster, now."""

    permission_classes = [IsAccountAdmin]

    @extend_schema(request=ReportRunRequestSerializer, responses={200: ReportRunResultSerializer})
    def post(self, request: Request) -> Response:
        """200 with the run result of every active DART's roster, sent whatever the date.

        With ``dry_run`` true nothing is sent and the result names who would be sent one.
        """
        payload = ReportRunRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        run = send_rosters_now(
            dry_run=payload.validated_data["dry_run"], actor=acting_user(request)
        )
        return run_response(run)


class ReportRunView(APIView):
    """``POST /system/reports/run`` -- the daily run of the sender, now."""

    permission_classes = [IsSystemAdmin]

    @extend_schema(request=ReportRunRequestSerializer, responses={200: ReportRunResultSerializer})
    def post(self, request: Request) -> Response:
        """200 with the run result of sending every subscription and roster that is due.

        With ``dry_run`` true nothing is sent or changed and the result names who would
        be sent what.  The caller is the audit actor.
        """
        payload = ReportRunRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        run = run_scheduled_reports(
            dry_run=payload.validated_data["dry_run"], actor=acting_user(request)
        )
        return run_response(run)
