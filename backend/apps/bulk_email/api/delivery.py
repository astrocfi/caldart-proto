"""The delivery report's actions: retry the failed copies, read one copy, hide or show.

``POST /bulk-email/{id}/retry`` and ``GET /bulk-email/{id}/recipients/{rid}/copy`` are
the bulk email senders' like the rest of the Sent page.  ``POST /bulk-email/{id}/hide``,
which keeps an email off the recipients' **Messages** page, is CalDART management's.
A refusal that comes from the email's state is a 409 ``{"detail": <sentence>}``.
"""

from __future__ import annotations

from typing import Any

from django.http import Http404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsManagement
from apps.bulk_email import delivery
from apps.bulk_email.api.common import (
    BULK_EMAIL_PERMISSIONS,
    email_for,
    readable_email_for,
    refused,
)
from apps.bulk_email.api.serializers import BulkEmailDetailSerializer
from apps.bulk_email.delivery import RecipientCopy
from apps.bulk_email.models import BulkEmailRecipient, RecipientStatus
from apps.members.api.actors import acting_user
from caldart.exceptions import DomainError

#: The answer to a refusal that comes from the email's state.
CONFLICT = OpenApiResponse(description="The email's state does not allow it; carries detail.")


class BulkEmailCopySerializer(serializers.Serializer[RecipientCopy]):
    """One person's copy as it went: who it went to, its result, and the copy itself.

    ``id`` is the recipient row, and ``name`` and ``email`` who the copy went to.
    ``status`` is the copy's result and ``tried_at`` when it was last tried.  ``subject``
    is its subject line, ``html`` the whole HTML email, and ``text`` the plain-text one,
    each filled in with the values stored when the copy went.
    """

    id = serializers.IntegerField(source="recipient.pk")
    name = serializers.CharField(source="recipient.name")
    email = serializers.CharField(source="recipient.email")
    status = serializers.ChoiceField(source="recipient.status", choices=RecipientStatus.choices)
    tried_at = serializers.DateTimeField(source="recipient.tried_at")
    subject = serializers.CharField(source="copy.subject")
    html = serializers.CharField(source="copy.html")
    text = serializers.CharField(source="copy.text")


class BulkEmailHideSerializer(serializers.Serializer[dict[str, Any]]):
    """``POST /bulk-email/{id}/hide``'s body: ``hidden``, true to hide, false to show."""

    hidden = serializers.BooleanField()


class RetryView(APIView):
    """``POST /bulk-email/{id}/retry`` -- **Retry failed**: the failed copies again."""

    permission_classes = BULK_EMAIL_PERMISSIONS

    @extend_schema(request=None, responses={200: BulkEmailDetailSerializer, 409: CONFLICT})
    def post(self, request: Request, pk: int) -> Response:
        """200 with the email, queued to send its failed copies again now.

        409 for an email that has not finished sending, or has no failed copy.
        """
        bulk = email_for(request, pk)
        try:
            delivery.retry_failed(bulk, actor=acting_user(request))
        except DomainError as error:
            return refused(error)
        return Response(BulkEmailDetailSerializer(email_for(request, pk)).data)


class RecipientCopyView(APIView):
    """``GET /bulk-email/{id}/recipients/{rid}/copy`` -- one person's copy, as it went."""

    permission_classes = BULK_EMAIL_PERMISSIONS

    @extend_schema(responses={200: BulkEmailCopySerializer, 409: CONFLICT})
    def get(self, request: Request, pk: int, rid: int) -> Response:
        """200 with the copy, filled in with the values stored when it went.

        404 for a row of another email; 409 for a person whose copy was never tried.
        """
        bulk = readable_email_for(request, pk)
        try:
            copy = delivery.recipient_copy(bulk, rid)
        except BulkEmailRecipient.DoesNotExist as missing:
            raise Http404 from missing
        except DomainError as error:
            return refused(error)
        return Response(BulkEmailCopySerializer(copy).data)


class HideView(APIView):
    """``POST /bulk-email/{id}/hide`` -- keep an email off Messages, or show it again."""

    # Choosing what every recipient may read again is CalDART management's alone,
    # whoever sent the email.
    permission_classes = [IsManagement]

    @extend_schema(
        request=BulkEmailHideSerializer,
        responses={200: BulkEmailDetailSerializer, 409: CONFLICT},
    )
    def post(self, request: Request, pk: int) -> Response:
        """200 with the email, ``hidden_from_archive`` as asked.

        Nothing else changes.  409 for an email that has never started sending.
        """
        bulk = email_for(request, pk)
        payload = BulkEmailHideSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        try:
            delivery.set_hidden(
                bulk, hidden=payload.validated_data["hidden"], actor=acting_user(request)
            )
        except DomainError as error:
            return refused(error)
        return Response(BulkEmailDetailSerializer(email_for(request, pk)).data)
