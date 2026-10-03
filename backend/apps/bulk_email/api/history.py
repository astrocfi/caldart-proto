"""The sent list, and one send's results as a download."""

from __future__ import annotations

from django.db.models import F, QuerySet
from django.http import HttpResponse
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.bulk_email.api.common import BULK_EMAIL_PERMISSIONS, email_for
from apps.bulk_email.api.drafts import summary_queryset
from apps.bulk_email.api.serializers import BulkEmailSummarySerializer
from apps.bulk_email.batch import results_document
from apps.bulk_email.drafts import visible_to
from apps.bulk_email.models import BulkEmail, BulkEmailStatus
from apps.members.api.actors import acting_user
from caldart.reports import CSV_MEDIA_TYPE, download_responses, report_response


class SentListView(generics.ListAPIView[BulkEmail]):
    """``GET /bulk-email/sent`` -- every email sending, sent, or stopped, newest first."""

    permission_classes = BULK_EMAIL_PERMISSIONS
    serializer_class = BulkEmailSummarySerializer
    # Names the model for the schema, which reads it without a signed-in caller.
    queryset = BulkEmail.objects.none()
    # A handful of sends a month: the whole history is one short list.
    pagination_class = None

    def get_queryset(self) -> QuerySet[BulkEmail]:
        """Every started email the caller may open, the most recently started first."""
        emails = visible_to(acting_user(self.request)).filter(
            status__in=[BulkEmailStatus.SENDING, BulkEmailStatus.SENT, BulkEmailStatus.STOPPED]
        )
        return summary_queryset(emails).order_by(F("started_at").desc(nulls_last=True), "-id")


class RecipientsCsvView(APIView):
    """``GET /bulk-email/{id}/recipients.csv`` -- one send's results, as a download."""

    permission_classes = BULK_EMAIL_PERMISSIONS

    @extend_schema(responses=download_responses(CSV_MEDIA_TYPE, "One send's recipients."))
    def get(self, request: Request, pk: int) -> HttpResponse:
        """The CSV of every person in the batch, with each result; 404 if unknown."""
        return report_response(results_document(email_for(request, pk)))
