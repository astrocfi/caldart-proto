"""The bulk email endpoints: preview, send, the history, and the recipient lists.

Every endpoint is CalDART management's (``management``); a system administrator
passes as for every role.  An anonymous caller is a 401, from
``caldart.exceptions``.
"""

from __future__ import annotations

from django.db.models import QuerySet
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsManagement
from apps.bulk_email.api.serializers import (
    BulkEmailDetailSerializer,
    BulkEmailMessageSerializer,
    BulkEmailSerializer,
    PreviewSerializer,
    checked_filters,
    preview_payload,
)
from apps.bulk_email.models import BulkEmail
from apps.bulk_email.services import (
    build_recipients,
    preview_document,
    results_document,
    send_bulk_email,
)
from apps.members.api.actors import acting_user
from caldart.reports import CSV_MEDIA_TYPE, download_responses, report_response


class PreviewView(APIView):
    """``POST /bulk-email/preview`` -- who a message would reach, sending nothing."""

    permission_classes = [IsManagement]

    @extend_schema(request=BulkEmailMessageSerializer, responses={200: PreviewSerializer})
    def post(self, request: Request) -> Response:
        """200 with the recipients and the skips the filters select, now.

        The message is checked as a send checks it, and a 400 names each field it
        refuses.  Nothing is sent or stored.
        """
        payload = BulkEmailMessageSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        chosen = build_recipients(payload.validated_data["filters"])
        return Response(PreviewSerializer(preview_payload(chosen)).data)


class PreviewCsvView(APIView):
    """``GET /bulk-email/preview.csv`` -- the preview's list, as a download."""

    permission_classes = [IsManagement]

    @extend_schema(responses=download_responses(CSV_MEDIA_TYPE, "The preview's recipients."))
    def get(self, request: Request) -> HttpResponse:
        """The CSV of who the query's filters would reach, then who they skip.

        The query parameters are the member list's filters.  A filter the list does
        not have, or a value it refuses, is a 400 under ``filters``.
        """
        filters = request.query_params.dict()
        try:
            checked_filters(filters)
        except ValidationError as exc:
            raise ValidationError({"filters": exc.detail}) from exc
        document = preview_document(
            build_recipients(filters), today_iso=timezone.localdate().isoformat()
        )
        return report_response(document)


class SendView(APIView):
    """``POST /bulk-email/send`` -- send a message to everybody the filters select."""

    permission_classes = [IsManagement]

    @extend_schema(request=BulkEmailMessageSerializer, responses={201: BulkEmailDetailSerializer})
    def post(self, request: Request) -> Response:
        """201 with the stored send and every person's result.

        The list is rebuilt now, so it may differ from the preview.  The message is
        checked as a preview checks it; a 400 on ``filters`` says when nobody would
        be sent a copy.  The caller is the sender and the audit actor.
        """
        payload = BulkEmailMessageSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        bulk = send_bulk_email(
            subject=payload.validated_data["subject"],
            body=payload.validated_data["body"],
            filters=payload.validated_data["filters"],
            sender=acting_user(request),
        )
        return Response(BulkEmailDetailSerializer(bulk).data, status=status.HTTP_201_CREATED)


class BulkEmailListView(generics.ListAPIView[BulkEmail]):
    """``GET /bulk-email`` -- every bulk email sent, the most recent first."""

    permission_classes = [IsManagement]
    serializer_class = BulkEmailSerializer
    # A handful of sends a month: the whole history is one short list.
    pagination_class = None

    def get_queryset(self) -> QuerySet[BulkEmail]:
        """Every send, newest first, with its sender."""
        return BulkEmail.objects.select_related("sender").order_by("-created_at", "-id")


class BulkEmailDetailView(generics.RetrieveAPIView[BulkEmail]):
    """``GET /bulk-email/{id}`` -- one send with every person's result."""

    permission_classes = [IsManagement]
    serializer_class = BulkEmailDetailSerializer

    def get_queryset(self) -> QuerySet[BulkEmail]:
        """Every send, with its sender and its recipients."""
        return BulkEmail.objects.select_related("sender").prefetch_related("recipients")


class RecipientsCsvView(APIView):
    """``GET /bulk-email/{id}/recipients.csv`` -- one send's results, as a download."""

    permission_classes = [IsManagement]

    @extend_schema(responses=download_responses(CSV_MEDIA_TYPE, "One send's recipients."))
    def get(self, request: Request, pk: int) -> HttpResponse:
        """The CSV of every person the send selected, with each result; 404 if unknown."""
        bulk = get_object_or_404(BulkEmail, pk=pk)
        return report_response(results_document(bulk))
