"""Reminder log, schedule and manual run endpoints.

``GET /admin/reminders/log`` and ``GET /admin/reminders/schedule`` are readable by
``account_admin`` (they answer the "did the member ever get told, and when?"
question) as well as ``system_admin``; changing the schedule and kicking off a scan
by hand are ``system_admin`` only.
"""

from __future__ import annotations

import django_filters
from django.db.models import QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import ListAPIView
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasAnyRole, IsSystemAdmin
from apps.accounts.roles import ACCOUNT_ADMIN, SYSTEM_ADMIN
from apps.members.api.actors import acting_user
from apps.reminders.api.serializers import (
    ReminderLogSerializer,
    ReminderRunRequestSerializer,
    ReminderRunResultSerializer,
    ReminderScheduleSerializer,
)
from apps.reminders.models import ReminderKind, ReminderLog, ReminderSchedule
from apps.reminders.services import send_renewal_reminders


class ReminderLogFilterSet(django_filters.FilterSet):
    """``?kind=&from=&to=``, where the dates bound ``sent_at``."""

    kind = django_filters.ChoiceFilter(choices=ReminderKind.choices)
    to = django_filters.DateFilter(field_name="sent_at", lookup_expr="date__lte")

    class Meta:
        model = ReminderLog
        fields = ["kind"]


# ``from`` is a Python keyword, so this one filter cannot be a class attribute.
ReminderLogFilterSet.base_filters["from"] = django_filters.DateFilter(
    field_name="sent_at", lookup_expr="date__gte"
)


class ReminderLogListView(ListAPIView[ReminderLog]):
    """``GET /admin/reminders/log`` -- paginated, newest first."""

    permission_classes = [HasAnyRole(ACCOUNT_ADMIN, SYSTEM_ADMIN)]
    serializer_class = ReminderLogSerializer
    filterset_class = ReminderLogFilterSet
    ordering_fields = ["sent_at", "kind"]
    search_fields = ["to_email", "user__email", "user__last_name", "user__first_name"]

    def get_queryset(self) -> QuerySet[ReminderLog]:
        """Return every reminder log row with its user preloaded.

        The rows come back in ``ReminderLog``'s default ordering, newest ``sent_at``
        first, unless the request asks for another ``ordering``.
        """
        return ReminderLog.objects.select_related("user").all()


class ReminderScheduleView(APIView):
    """``GET /admin/reminders/schedule`` (account and system administrators) and ``PUT``.

    The one schedule saying how many days before expiry the first, second and final
    reminders go and how many days after it the lapsed one does.  Only a system
    administrator changes it.
    """

    def get_permissions(self) -> list[BasePermission]:
        """Account and system administrators read the schedule; only the latter write."""
        if self.request.method == "PUT":
            return [IsSystemAdmin()]
        return [HasAnyRole(ACCOUNT_ADMIN, SYSTEM_ADMIN)()]

    @extend_schema(responses={200: ReminderScheduleSerializer})
    def get(self, request: Request) -> Response:
        """Return the schedule, the defaults (60, 30, 7, 30) before any is saved."""
        return Response(ReminderScheduleSerializer(ReminderSchedule.load()).data)

    @extend_schema(request=ReminderScheduleSerializer, responses={200: ReminderScheduleSerializer})
    def put(self, request: Request) -> Response:
        """Replace the schedule with the body, recording the caller, and return it.

        Answers 400, keyed by field, for a body ``ReminderScheduleSerializer``
        refuses, and changes nothing then.  The new days apply from the next scan; a
        stage a member was already sent is never sent again for the same term.
        """
        serializer = ReminderScheduleSerializer(ReminderSchedule.load(), data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=acting_user(request))
        return Response(serializer.data)


class ReminderRunView(APIView):
    """``POST /system/reminders/run`` -- run the scan now."""

    permission_classes = [IsSystemAdmin]

    @extend_schema(
        request=ReminderRunRequestSerializer, responses={200: ReminderRunResultSerializer}
    )
    def post(self, request: Request) -> Response:
        """Run the renewal scan and return its counts and the members behind them.

        Validates the body against ``ReminderRunRequestSerializer`` (``dry_run``,
        defaulting to ``False``) and responds ``200`` with the serialized
        ``ReminderRunResultSerializer`` payload: ``sent``, ``skipped``,
        ``failed``, a ``skipped_by_reason`` count per reason that occurred, and
        one ``actions`` entry naming each member a reminder went to, or -- in a
        dry run -- would have gone to. ``request.user`` is recorded as the
        audit actor; raises ``PermissionDenied`` if it is somehow anonymous, which
        ``IsSystemAdmin`` never lets through.
        """
        if not request.user.is_authenticated:
            raise PermissionDenied
        payload = ReminderRunRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        run = send_renewal_reminders(dry_run=payload.validated_data["dry_run"], actor=request.user)
        return Response(ReminderRunResultSerializer(run.as_dict()).data, status=status.HTTP_200_OK)
