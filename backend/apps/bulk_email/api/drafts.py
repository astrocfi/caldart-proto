"""The draft endpoints: open a draft, read and change one, send, cancel, stop, resume.

A refusal that comes from the email's state, such as changing an email that has started
sending, is a 409 ``{"detail": <sentence>}``.  A refusal of the input is a 400 keyed by
the field.
"""

from __future__ import annotations

from typing import Any

from django.db.models import Count, Q, QuerySet
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bulk_email import drafts
from apps.bulk_email.api.common import BULK_EMAIL_PERMISSIONS, email_for, refused
from apps.bulk_email.api.serializers import (
    BulkEmailDetailSerializer,
    BulkEmailSendSerializer,
    BulkEmailSummarySerializer,
    BulkEmailUpdateSerializer,
)
from apps.bulk_email.models import BulkEmail, BulkEmailStatus, RecipientStatus
from apps.members.api.actors import acting_user
from caldart.exceptions import DomainError, DomainValidationError

#: The answer to a refusal that comes from the email's state.
CONFLICT = OpenApiResponse(description="The email's state does not allow it; carries detail.")


def summary_queryset(emails: QuerySet[BulkEmail]) -> QuerySet[BulkEmail]:
    """``emails`` annotated with ``batch_count`` and ``remaining`` for the lists."""
    return emails.annotate(
        batch_count=Count("recipients", filter=Q(recipients__round=0), distinct=True),
        remaining=Count(
            "recipients",
            filter=Q(recipients__status=RecipientStatus.PENDING),
            distinct=True,
        ),
    )


def _detail(bulk: BulkEmail, *, code: int = status.HTTP_200_OK) -> Response:
    """``bulk`` read afresh, as ``GET /bulk-email/{id}`` answers it."""
    fresh = BulkEmail.objects.select_related("sender", "stopped_by").get(pk=bulk.pk)
    return Response(BulkEmailDetailSerializer(fresh).data, status=code)


class DraftListCreateView(generics.ListAPIView[BulkEmail]):
    """``GET/POST /bulk-email/drafts`` -- the drafts and queued emails; open a draft."""

    permission_classes = BULK_EMAIL_PERMISSIONS
    serializer_class = BulkEmailSummarySerializer
    # Names the model for the schema, which reads it without a signed-in caller.
    queryset = BulkEmail.objects.none()
    # A sender keeps a handful of drafts: the whole list is one short page.
    pagination_class = None

    def get_queryset(self) -> QuerySet[BulkEmail]:
        """Every draft and queued email the caller may open, the latest edited first."""
        emails = drafts.visible_to(acting_user(self.request)).filter(
            status__in=[BulkEmailStatus.DRAFT, BulkEmailStatus.QUEUED]
        )
        return summary_queryset(emails).order_by("-updated_at", "-id")

    @extend_schema(
        request=None,
        responses={201: BulkEmailDetailSerializer, 200: BulkEmailDetailSerializer},
    )
    def post(self, request: Request) -> Response:
        """The caller's empty draft (200), or a fresh one when they have none (201)."""
        opened = drafts.open_draft(acting_user(request))
        return _detail(
            opened.bulk, code=status.HTTP_201_CREATED if opened.created else status.HTTP_200_OK
        )


class BulkEmailDetailView(APIView):
    """``GET/PATCH/DELETE /bulk-email/{id}`` -- one bulk email."""

    permission_classes = BULK_EMAIL_PERMISSIONS

    @extend_schema(responses={200: BulkEmailDetailSerializer})
    def get(self, request: Request, pk: int) -> Response:
        """200 with the email, its batch counts, and its progress; 404 if unknown."""
        return _detail(email_for(request, pk))

    @extend_schema(
        request=BulkEmailUpdateSerializer,
        responses={200: BulkEmailDetailSerializer, 409: CONFLICT},
    )
    def patch(self, request: Request, pk: int) -> Response:
        """200 with the email once the given fields are saved.

        A queued email keeps its start time.  409 once it has started sending.
        """
        bulk = email_for(request, pk)
        payload = BulkEmailUpdateSerializer(data=request.data, partial=True)
        payload.is_valid(raise_exception=True)
        changes: dict[str, Any] = dict(payload.validated_data)
        try:
            saved = drafts.update(bulk, changes)
        except DomainError as error:
            return refused(error)
        return _detail(saved)

    @extend_schema(responses={204: None, 409: CONFLICT})
    def delete(self, request: Request, pk: int) -> Response:
        """204 once the draft and its batch are gone; 409 for any email but a draft."""
        bulk = email_for(request, pk)
        try:
            drafts.delete_draft(bulk)
        except DomainError as error:
            return refused(error)
        return Response(status=status.HTTP_204_NO_CONTENT)


class SendView(APIView):
    """``POST /bulk-email/{id}/send`` -- queue the email: **Send** or **Schedule**."""

    permission_classes = BULK_EMAIL_PERMISSIONS

    @extend_schema(
        request=BulkEmailSendSerializer,
        responses={200: BulkEmailDetailSerializer, 409: CONFLICT},
    )
    def post(self, request: Request, pk: int) -> Response:
        """200 with the queued email; nothing is sent in the request.

        A 400 keyed ``subject``, ``body``, ``batch``, ``confirm_count``, or ``start_at``
        says why it cannot go; a 409 says it has started sending already.
        """
        bulk = email_for(request, pk)
        payload = BulkEmailSendSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            queued = drafts.queue(
                bulk,
                confirm_count=payload.validated_data.get("confirm_count"),
                start_at=payload.validated_data.get("start_at"),
                actor=acting_user(request),
            )
        except DomainValidationError:
            raise
        except DomainError as error:
            return refused(error)
        return _detail(queued)


class CancelView(APIView):
    """``POST /bulk-email/{id}/cancel`` -- take a queued email back to a draft."""

    permission_classes = BULK_EMAIL_PERMISSIONS

    @extend_schema(request=None, responses={200: BulkEmailDetailSerializer, 409: CONFLICT})
    def post(self, request: Request, pk: int) -> Response:
        """200 with the draft; 409 *This email has started sending.* once it has."""
        try:
            canceled = drafts.cancel(email_for(request, pk), actor=acting_user(request))
        except DomainError as error:
            return refused(error)
        return _detail(canceled)


class StopView(APIView):
    """``POST /bulk-email/{id}/stop`` -- stop a send part way."""

    permission_classes = BULK_EMAIL_PERMISSIONS

    @extend_schema(request=None, responses={200: BulkEmailDetailSerializer, 409: CONFLICT})
    def post(self, request: Request, pk: int) -> Response:
        """200 with the email, ``stop_requested`` set; 409 when it is not sending.

        The sender stops between copies, so the email reads ``stopped`` a moment later.
        """
        try:
            stopping = drafts.stop(email_for(request, pk), actor=acting_user(request))
        except DomainError as error:
            return refused(error)
        return _detail(stopping)


class ResumeView(APIView):
    """``POST /bulk-email/{id}/resume`` -- **Send the rest** of a stopped send."""

    permission_classes = BULK_EMAIL_PERMISSIONS

    @extend_schema(request=None, responses={200: BulkEmailDetailSerializer, 409: CONFLICT})
    def post(self, request: Request, pk: int) -> Response:
        """200 with the email queued to start now; 409 unless it was stopped."""
        try:
            resumed = drafts.resume(email_for(request, pk), actor=acting_user(request))
        except DomainError as error:
            return refused(error)
        return _detail(resumed)
