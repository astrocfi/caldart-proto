"""The Callouts screens: every mission callout, one callout's answers, remind, and close.

Every endpoint is CalDART management's and a DART leader's (``IsBulkSender``); a system
administrator passes as for every role.  A caller reaches only the callouts
``apps.bulk_email.callouts.visible_callouts`` gives them: every one for CalDART
management, and for a DART leader the ones they sent or that went to the DART on their
own profile.  Any other id is a 404.  A refusal that comes from the callout's state is a
409 ``{"detail": <sentence>}``.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django.db.models import F, QuerySet
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_field
from rest_framework import generics, serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.aircraft.api.serializers import LeaderGoNoGoSerializer
from apps.bulk_email import callouts
from apps.bulk_email.api.common import BULK_EMAIL_PERMISSIONS, refused
from apps.bulk_email.api.serializers import sender_name
from apps.bulk_email.callouts import CalloutCounts, CalloutRow, Reminder
from apps.bulk_email.models import BulkEmail, CalloutAnswerKind
from apps.members.api.actors import acting_user
from caldart.exceptions import DomainError
from caldart.reports import CSV_MEDIA_TYPE, download_responses, report_response

#: The answer to a refusal that comes from the callout's state.
CONFLICT = OpenApiResponse(description="The callout's state does not allow it; carries detail.")


class CalloutCountsSerializer(serializers.Serializer[CalloutCounts]):
    """How many people a callout reached, and how many gave each answer or none."""

    reached = serializers.IntegerField()
    available = serializers.IntegerField()
    limited = serializers.IntegerField()
    unavailable = serializers.IntegerField()
    no_answer = serializers.IntegerField()


class CalloutReminderSerializer(serializers.Serializer[Reminder]):
    """One round of **Remind non-responders**: its number, its time, and its count."""

    round = serializers.IntegerField()
    requested_at = serializers.DateTimeField()
    count = serializers.IntegerField()


class CalloutRecipientSerializer(serializers.Serializer[CalloutRow]):
    """One person the callout reached: their answer and what the member check shows.

    ``answer`` is ``available``, ``limited``, or ``unavailable``, null before they answer;
    ``note`` and ``answered_at`` go with it, blank and null then.  ``dart_name``,
    ``home_airport``, ``aircraft`` (N-numbers), and ``go_no_go`` (the member check's
    three verdicts) read the account as it is now.
    """

    user_id = serializers.IntegerField(source="account.pk")
    name = serializers.CharField(source="account.display_name")
    email = serializers.CharField(source="account.email")
    answer = serializers.ChoiceField(
        source="answer.answer", choices=CalloutAnswerKind.choices, allow_null=True
    )
    note = serializers.SerializerMethodField()
    answered_at = serializers.SerializerMethodField()
    dart_name = serializers.CharField()
    home_airport = serializers.CharField()
    aircraft = serializers.ListField(child=serializers.CharField())
    go_no_go = LeaderGoNoGoSerializer(source="go")

    def get_note(self, row: CalloutRow) -> str:
        """The note with the person's answer, or ``""``."""
        return "" if row.answer is None else row.answer.note

    def get_answered_at(self, row: CalloutRow) -> datetime | None:
        """When the person last answered, in the site's time zone; null before."""
        return None if row.answer is None else timezone.localtime(row.answer.answered_at)


class CalloutSummarySerializer(serializers.ModelSerializer[BulkEmail]):
    """One callout as the Callouts list shows it.

    ``subject`` is the subject as written, its recipient field tokens such as
    ``{first_name}`` left in, since the list is about the callout rather than one copy.
    ``sender`` is the sender's display name, blank once the account is gone, and
    ``dart_name`` the DART a DART leader's callout went to, blank for CalDART
    management's.  ``closes_at`` is when answers close, ``closed_at`` when **Close now**
    closed it sooner (null otherwise), and ``is_open`` whether it takes answers now.
    ``counts`` counts the people it reached by answer.
    """

    sender = serializers.SerializerMethodField()
    dart_name = serializers.SerializerMethodField()
    closes_at = serializers.SerializerMethodField()
    closed_at = serializers.SerializerMethodField()
    is_open = serializers.SerializerMethodField()
    counts = serializers.SerializerMethodField()

    class Meta:
        model = BulkEmail
        fields = [
            "id",
            "subject",
            "status",
            "sender",
            "dart_name",
            "started_at",
            "sent_at",
            "closes_at",
            "closed_at",
            "is_open",
            "counts",
        ]
        read_only_fields = fields

    def get_sender(self, bulk: BulkEmail) -> str:
        """The sender's display name, or ``""`` once the account is gone."""
        return sender_name(bulk)

    def get_dart_name(self, bulk: BulkEmail) -> str:
        """The DART the callout went to, or ``""`` for CalDART management's."""
        return str(bulk.dart.name) if bulk.dart is not None else ""

    def get_closes_at(self, bulk: BulkEmail) -> datetime:
        """When the callout's answers close, in the site's time zone."""
        return timezone.localtime(bulk.callout.closes_at)

    def get_closed_at(self, bulk: BulkEmail) -> datetime | None:
        """When **Close now** closed it, in the site's time zone; null when nobody did."""
        closed = bulk.callout.closed_at
        return None if closed is None else timezone.localtime(closed)

    def get_is_open(self, bulk: BulkEmail) -> bool:
        """True while the callout takes answers."""
        return callouts.is_open(bulk.callout)

    @extend_schema_field(CalloutCountsSerializer)
    def get_counts(self, bulk: BulkEmail) -> dict[str, int]:
        """The people the callout reached, counted by answer."""
        return dict(CalloutCountsSerializer(callouts.counts_for(bulk)).data)


class CalloutDetailSerializer(CalloutSummarySerializer):
    """One callout with everything its screen shows.

    On top of the list's fields: ``closed_by``, who pressed **Close now** (blank when
    nobody did or the account is gone); ``reminders``, each round of **Remind
    non-responders**, oldest first; ``recipients``, one row per person it reached, in
    surname order; and ``closed_skipped``, how many copies were not sent because the
    callout had closed by then.
    """

    closed_by = serializers.SerializerMethodField()
    closed_skipped = serializers.SerializerMethodField()
    reminders = serializers.SerializerMethodField()
    recipients = serializers.SerializerMethodField()

    class Meta(CalloutSummarySerializer.Meta):
        fields = [
            *CalloutSummarySerializer.Meta.fields,
            "closed_by",
            "closed_skipped",
            "reminders",
            "recipients",
        ]
        read_only_fields = fields

    def get_closed_by(self, bulk: BulkEmail) -> str:
        """Who pressed **Close now**, or ``""`` when nobody did or the account is gone."""
        closer = bulk.callout.closed_by
        return "" if closer is None else closer.display_name

    def get_closed_skipped(self, bulk: BulkEmail) -> int:
        """How many copies were skipped because the callout had closed."""
        return bulk.recipients.filter(reason=callouts.CLOSED_REASON).count()

    @extend_schema_field(CalloutReminderSerializer(many=True))
    def get_reminders(self, bulk: BulkEmail) -> list[dict[str, Any]]:
        """Each round of reminders, oldest first."""
        rounds = callouts.reminders(bulk)
        # The stubs type a plain Serializer's instance as one object, even with many=True.
        return list(CalloutReminderSerializer(rounds, many=True).data)  # type: ignore[arg-type]

    @extend_schema_field(CalloutRecipientSerializer(many=True))
    def get_recipients(self, bulk: BulkEmail) -> list[dict[str, Any]]:
        """One row per person the callout reached, in surname order."""
        rows = callouts.callout_rows(bulk)
        # The stubs type a plain Serializer's instance as one object, even with many=True.
        return list(CalloutRecipientSerializer(rows, many=True).data)  # type: ignore[arg-type]


def callout_for(request: Request, pk: int) -> BulkEmail:
    """The callout ``pk`` the caller may open; ``Http404`` for any other."""
    return get_object_or_404(callouts.visible_callouts(acting_user(request)), pk=pk)


def _detail(request: Request, pk: int) -> Response:
    """The callout ``pk`` read afresh, as ``GET /bulk-email/callouts/{id}`` answers it."""
    return Response(CalloutDetailSerializer(callout_for(request, pk)).data)


class CalloutListView(generics.ListAPIView[BulkEmail]):
    """``GET /bulk-email/callouts`` -- every callout the caller may open, newest first."""

    permission_classes = BULK_EMAIL_PERMISSIONS
    serializer_class = CalloutSummarySerializer
    # Names the model for the schema, which reads it without a signed-in caller.
    queryset = BulkEmail.objects.none()
    # A callout goes out a few times a year: the whole list is one short page.
    pagination_class = None

    def get_queryset(self) -> QuerySet[BulkEmail]:
        """Every callout the caller may open that has started sending, latest first."""
        return callouts.visible_callouts(acting_user(self.request)).order_by(
            F("started_at").desc(nulls_last=True), "-id"
        )


class CalloutDetailView(APIView):
    """``GET /bulk-email/callouts/{id}`` -- one callout, its counts, and every answer."""

    permission_classes = BULK_EMAIL_PERMISSIONS

    @extend_schema(responses={200: CalloutDetailSerializer})
    def get(self, request: Request, pk: int) -> Response:
        """200 with the callout and one row per person it reached; 404 if unknown."""
        return _detail(request, pk)


class CalloutAnswersCsvView(APIView):
    """``GET /bulk-email/callouts/{id}/answers.csv`` -- every answer, as a download."""

    permission_classes = BULK_EMAIL_PERMISSIONS

    @extend_schema(responses=download_responses(CSV_MEDIA_TYPE, "One callout's answers."))
    def get(self, request: Request, pk: int) -> HttpResponse:
        """The CSV of everybody the callout reached, with each answer; 404 if unknown."""
        return report_response(callouts.answers_document(callout_for(request, pk)))


class CalloutRemindView(APIView):
    """``POST /bulk-email/callouts/{id}/remind`` -- **Remind non-responders**."""

    permission_classes = BULK_EMAIL_PERMISSIONS

    @extend_schema(request=None, responses={200: CalloutDetailSerializer, 409: CONFLICT})
    def post(self, request: Request, pk: int) -> Response:
        """200 with the callout, its reminders queued to send now.

        409 for a callout that has not finished sending, has closed, or has nobody left
        to remind.
        """
        bulk = callout_for(request, pk)
        try:
            callouts.remind(bulk, actor=acting_user(request))
        except DomainError as error:
            return refused(error)
        return _detail(request, pk)


class CalloutCloseView(APIView):
    """``POST /bulk-email/callouts/{id}/close`` -- **Close now**: take no more answers."""

    permission_classes = BULK_EMAIL_PERMISSIONS

    @extend_schema(request=None, responses={200: CalloutDetailSerializer, 409: CONFLICT})
    def post(self, request: Request, pk: int) -> Response:
        """200 with the callout, closed; 409 for one already closed."""
        bulk = callout_for(request, pk)
        try:
            callouts.close(bulk, actor=acting_user(request))
        except DomainError as error:
            return refused(error)
        return _detail(request, pk)
