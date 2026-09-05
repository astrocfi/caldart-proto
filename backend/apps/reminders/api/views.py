"""Reminder log and manual run endpoints (PLAN §6.9).

``GET /admin/reminders/log`` is readable by ``account_admin`` (they answer the
"did the member ever get told?" question) as well as ``system_admin``; kicking
off a scan by hand is ``system_admin`` only.
"""

from __future__ import annotations

import django_filters
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasAnyRole, IsSystemAdmin
from apps.accounts.roles import ACCOUNT_ADMIN, SYSTEM_ADMIN
from apps.reminders.api.serializers import (
    ReminderLogSerializer,
    ReminderRunRequestSerializer,
    ReminderRunResultSerializer,
)
from apps.reminders.models import ReminderKind, ReminderLog
from apps.reminders.services import send_renewal_reminders


class ReminderLogFilterSet(django_filters.FilterSet):
    """``?kind=&from=&to=`` (PLAN §6.9), where the dates bound ``sent_at``."""

    kind = django_filters.ChoiceFilter(choices=ReminderKind.choices)
    to = django_filters.DateFilter(field_name="sent_at", lookup_expr="date__lte")

    class Meta:
        model = ReminderLog
        fields = ["kind"]


# ``from`` is a Python keyword, so this one filter cannot be a class attribute.
ReminderLogFilterSet.base_filters["from"] = django_filters.DateFilter(
    field_name="sent_at", lookup_expr="date__gte"
)


class ReminderLogListView(ListAPIView):
    """``GET /admin/reminders/log`` — paginated, newest first."""

    permission_classes = [HasAnyRole(ACCOUNT_ADMIN, SYSTEM_ADMIN)]
    serializer_class = ReminderLogSerializer
    filterset_class = ReminderLogFilterSet
    ordering_fields = ["sent_at", "kind"]
    search_fields = ["to_email", "user__email", "user__last_name", "user__first_name"]

    def get_queryset(self):
        return ReminderLog.objects.select_related("user").all()


class ReminderRunView(APIView):
    """``POST /system/reminders/run`` — run the scan now (PLAN §12)."""

    permission_classes = [IsSystemAdmin]

    def post(self, request):
        payload = ReminderRunRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        run = send_renewal_reminders(dry_run=payload.validated_data["dry_run"])
        return Response(ReminderRunResultSerializer(run.as_dict()).data, status=status.HTTP_200_OK)
