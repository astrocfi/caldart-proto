"""The email log endpoint.

``GET /system/emails`` is ``system_admin`` only: it carries every address the
installation has written to, which is operations work rather than membership
work.
"""

from __future__ import annotations

import django_filters
from django.db.models import Q, QuerySet
from rest_framework.generics import ListAPIView

from apps.accounts.permissions import IsSystemAdmin
from apps.mail.api.serializers import EmailLogSerializer
from apps.mail.models import EmailLog, EmailStatus
from caldart.pagination import StandardPagination


class EmailLogFilterSet(django_filters.FilterSet):
    """``?purpose=&status=&from=&to=&q=``, where the dates bound ``sent_at``.

    ``q`` matches the address written to and the recipient account's first and
    last name, case-insensitively.
    """

    purpose = django_filters.CharFilter()
    status = django_filters.ChoiceFilter(choices=EmailStatus.choices)
    to = django_filters.DateFilter(field_name="sent_at", lookup_expr="date__lte")
    q = django_filters.CharFilter(method="filter_q")

    class Meta:
        model = EmailLog
        fields = ["purpose", "status"]

    def filter_q(
        self, queryset: QuerySet[EmailLog], name: str, value: str
    ) -> QuerySet[EmailLog]:
        """Narrow ``queryset`` to rows whose address or recipient name contains ``value``."""
        return queryset.filter(
            Q(to_email__icontains=value)
            | Q(user__first_name__icontains=value)
            | Q(user__last_name__icontains=value)
        )


# ``from`` is a Python keyword, so this one filter cannot be a class attribute.
EmailLogFilterSet.base_filters["from"] = django_filters.DateFilter(
    field_name="sent_at", lookup_expr="date__gte"
)


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
