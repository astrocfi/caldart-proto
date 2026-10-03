"""The batch endpoints: read it, add to it, remove one person, clear it, download it.

A change to an email that has started sending is a 409 ``{"detail": <sentence>}``.
"""

from __future__ import annotations

from django.http import Http404, HttpResponse
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bulk_email import batch
from apps.bulk_email.api.common import BULK_EMAIL_PERMISSIONS, email_for, refused
from apps.bulk_email.api.serializers import (
    BulkEmailAddResultSerializer,
    BulkEmailAddSerializer,
    BulkEmailBatchSerializer,
    batch_payload,
)
from apps.bulk_email.models import BulkEmailRecipient
from apps.members.api.actors import acting_user
from caldart.exceptions import DomainError
from caldart.reports import CSV_MEDIA_TYPE, download_responses, report_response

#: The answer to a change refused because the email has started sending.
CONFLICT = OpenApiResponse(description="The email has started sending; carries detail.")


class BatchView(APIView):
    """``GET/DELETE /bulk-email/{id}/batch`` -- the batch, or clear it."""

    permission_classes = BULK_EMAIL_PERMISSIONS

    @extend_schema(responses={200: BulkEmailBatchSerializer})
    def get(self, request: Request, pk: int) -> Response:
        """200 with the counts, the adds, and every person with their reason."""
        return Response(BulkEmailBatchSerializer(batch_payload(email_for(request, pk))).data)

    @extend_schema(responses={200: BulkEmailBatchSerializer, 409: CONFLICT})
    def delete(self, request: Request, pk: int) -> Response:
        """200 with the empty batch once everybody and every add is gone.

        A queued email goes back to a draft.
        """
        bulk = email_for(request, pk)
        try:
            batch.clear(bulk, actor=acting_user(request))
        except DomainError as error:
            return refused(error)
        return Response(BulkEmailBatchSerializer(batch_payload(bulk)).data)


class BatchAddView(APIView):
    """``POST /bulk-email/{id}/batch/add`` -- add everybody the filters choose."""

    permission_classes = BULK_EMAIL_PERMISSIONS

    @extend_schema(
        request=BulkEmailAddSerializer,
        responses={200: BulkEmailAddResultSerializer, 409: CONFLICT},
    )
    def post(self, request: Request, pk: int) -> Response:
        """200 with how many joined, how many were there already, and the batch's size.

        A filter the member list does not have, or a value it refuses, is a 400 keyed
        ``filters``.  A queued email goes back to a draft.
        """
        bulk = email_for(request, pk)
        payload = BulkEmailAddSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            result = batch.add_filters(
                bulk, payload.validated_data["filters"], actor=acting_user(request)
            )
        except DomainError as error:
            return refused(error)
        return Response(BulkEmailAddResultSerializer(result).data)


class BatchRowView(APIView):
    """``DELETE /bulk-email/{id}/batch/{rid}`` -- take one person out of the batch."""

    permission_classes = BULK_EMAIL_PERMISSIONS

    @extend_schema(
        operation_id="bulk_email_batch_row_destroy", responses={204: None, 409: CONFLICT}
    )
    def delete(self, request: Request, pk: int, rid: int) -> Response:
        """204 once the person is out of the batch; 404 for a row not in it.

        A queued email goes back to a draft.
        """
        bulk = email_for(request, pk)
        try:
            batch.remove(bulk, rid, actor=acting_user(request))
        except BulkEmailRecipient.DoesNotExist as missing:
            raise Http404 from missing
        except DomainError as error:
            return refused(error)
        return Response(status=status.HTTP_204_NO_CONTENT)


class BatchCsvView(APIView):
    """``GET /bulk-email/{id}/batch.csv`` -- the batch as a download."""

    permission_classes = BULK_EMAIL_PERMISSIONS

    @extend_schema(responses=download_responses(CSV_MEDIA_TYPE, "One email's batch."))
    def get(self, request: Request, pk: int) -> HttpResponse:
        """The CSV of everybody in the batch, with who will receive a copy and why not."""
        return report_response(batch.batch_document(email_for(request, pk)))
