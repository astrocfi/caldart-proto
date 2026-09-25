"""The email log endpoints.

``GET /system/emails`` and ``GET /system/emails/purposes`` are ``system_admin``
only: the log carries every address the installation has written to, which is
operations work rather than membership work.  The filters live in
``apps.mail.filters``, which the ``emails`` report shares.
"""

from __future__ import annotations

from django.db.models import QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsSystemAdmin
from apps.mail.api.serializers import EmailLogSerializer, EmailPurposeSerializer
from apps.mail.filters import EmailLogFilterSet
from apps.mail.models import EmailLog
from apps.mail.purposes import PURPOSE_LABELS
from apps.mail.reports import order_email_log
from caldart.pagination import StandardPagination


class EmailLogListView(ListAPIView[EmailLog]):
    """``GET /system/emails`` -- paginated, newest first."""

    permission_classes = [IsSystemAdmin]
    serializer_class = EmailLogSerializer
    filterset_class = EmailLogFilterSet
    pagination_class = StandardPagination
    ordering_fields = ["sent_at"]

    def get_queryset(self) -> QuerySet[EmailLog]:
        """Return every email log row with its recipient account preloaded."""
        return EmailLog.objects.select_related("user").all()

    def filter_queryset[R](self, queryset: QuerySet[EmailLog, R]) -> QuerySet[EmailLog, R]:
        """Narrow ``queryset`` by the filters and put it in the download's order.

        Newest ``sent_at`` first unless ``?ordering=sent_at`` asks for oldest first;
        any other ``ordering`` is ignored.  Sends in the same instant follow their
        ``id`` in the same direction, so the pages and the ``emails`` report agree
        row for row.
        """
        # DRF's OrderingFilter (kept so the schema documents ``ordering``) replaces
        # ``EmailLog``'s ``-id`` tiebreak with the bare term; the report's order
        # puts it back.
        narrowed = super().filter_queryset(queryset)
        return order_email_log(narrowed, self.request.query_params.get("ordering", ""))


class EmailPurposeListView(APIView):
    """``GET /system/emails/purposes`` -- the purposes the log's filter offers."""

    permission_classes = [IsSystemAdmin]

    @extend_schema(responses={200: EmailPurposeSerializer(many=True)})
    def get(self, request: Request) -> Response:
        """200 with one ``{value, label}`` per labeled purpose, in the filter's order.

        Unpaginated.  ``value`` is what ``?purpose=`` takes and ``label`` the words
        the portal shows for it.
        """
        rows = [{"value": value, "label": label} for value, label in PURPOSE_LABELS.items()]
        # The stubs take the instance type from the single-object parameter, so
        # they do not widen it to a list when ``many`` is set.
        serializer = EmailPurposeSerializer(rows, many=True)  # type: ignore[arg-type]
        return Response(serializer.data)
