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
from caldart.pagination import StandardPagination


class EmailLogListView(ListAPIView[EmailLog]):
    """``GET /system/emails`` -- paginated, newest first."""

    permission_classes = [IsSystemAdmin]
    serializer_class = EmailLogSerializer
    filterset_class = EmailLogFilterSet
    pagination_class = StandardPagination
    ordering_fields = ["sent_at"]

    def get_queryset(self) -> QuerySet[EmailLog]:
        """Return every email log row with its recipient account preloaded.

        The rows come back in ``EmailLog``'s default ordering, newest ``sent_at``
        first, unless the request asks for another ``ordering``.
        """
        return EmailLog.objects.select_related("user").all()


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
