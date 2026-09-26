"""The email log's filters, shared by its list endpoint and its report.

``GET /system/emails`` and the ``emails`` report narrow the log with this one
filter set, so a download carries exactly the rows the list shows.
"""

from __future__ import annotations

import django_filters
from django.db.models import Q, QuerySet

from apps.mail.models import EmailLog, EmailStatus


class EmailLogFilterSet(django_filters.FilterSet):
    """``?purpose=&status=&from=&to=&q=``, where the dates bound ``sent_at``.

    ``purpose`` is an exact template name; one no row carries matches nothing.
    ``status`` is ``sent`` or ``failed``, and anything else is refused.  ``from`` and
    ``to`` are ``YYYY-MM-DD`` and compare with the local date part of ``sent_at``,
    inclusively.  ``q`` matches the address written to, the name recorded at send
    time, and the recipient account's first and last name, case-insensitively.
    """

    purpose = django_filters.CharFilter()
    status = django_filters.ChoiceFilter(choices=EmailStatus.choices)
    to = django_filters.DateFilter(field_name="sent_at", lookup_expr="date__lte")
    q = django_filters.CharFilter(method="filter_q")

    class Meta:
        model = EmailLog
        fields = ["purpose", "status"]

    def filter_q(self, queryset: QuerySet[EmailLog], name: str, value: str) -> QuerySet[EmailLog]:
        """Narrow ``queryset`` to rows whose address or recipient name holds ``value``."""
        return queryset.filter(
            Q(to_email__icontains=value)
            | Q(to_name__icontains=value)
            | Q(user__first_name__icontains=value)
            | Q(user__last_name__icontains=value)
        )


# ``from`` is a Python keyword, so this one filter cannot be a class attribute.
EmailLogFilterSet.base_filters["from"] = django_filters.DateFilter(
    field_name="sent_at", lookup_expr="date__gte"
)
