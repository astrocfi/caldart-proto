"""``POST /bulk-email/{id}/preview``: one person's copy, filled in, as it will go."""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bulk_email.api.common import BULK_EMAIL_PERMISSIONS, email_for
from apps.bulk_email.preview import Preview, preview
from apps.members.api.actors import acting_user


class BulkEmailPreviewRequestSerializer(serializers.Serializer[dict[str, Any]]):
    """The body of a preview: the batch row to preview, null or left out for the first."""

    recipient_id = serializers.IntegerField(required=False, allow_null=True)


class BulkEmailPreviewRecipientSerializer(serializers.Serializer[Preview]):
    """Whose copy a preview is: the batch row (null for the sender's own), and who."""

    id = serializers.IntegerField(source="recipient_id", allow_null=True)
    name = serializers.CharField()
    email = serializers.CharField()


class BulkEmailPreviewSerializer(serializers.Serializer[Preview]):
    """One person's copy: its subject and two bodies, and where they stand in the batch.

    ``html`` is the whole HTML email and ``text`` the plain-text one.  ``position`` is
    the person's place, from 1, among the ``count`` who receive a copy, 0 for the
    sender's own; ``previous_id`` and ``next_id`` are the rows either side.
    """

    subject = serializers.CharField(source="copy.subject")
    html = serializers.CharField(source="copy.html")
    text = serializers.CharField(source="copy.text")
    recipient = BulkEmailPreviewRecipientSerializer(source="*")
    position = serializers.IntegerField()
    count = serializers.IntegerField()
    previous_id = serializers.IntegerField(allow_null=True)
    next_id = serializers.IntegerField(allow_null=True)


class PreviewView(APIView):
    """``POST /bulk-email/{id}/preview`` -- one person's copy of the saved message."""

    permission_classes = BULK_EMAIL_PERMISSIONS

    @extend_schema(
        request=BulkEmailPreviewRequestSerializer,
        responses={200: BulkEmailPreviewSerializer},
    )
    def post(self, request: Request, pk: int) -> Response:
        """200 with the copy of the batch row ``recipient_id``, or of the first person.

        Nothing is sent or stored.  A 400 keyed ``subject`` or ``body`` names a token
        that cannot be filled in, and one keyed ``recipient_id`` a row not in the
        batch; 404 for an email the caller may not open.
        """
        bulk = email_for(request, pk)
        payload = BulkEmailPreviewRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        built = preview(
            bulk,
            recipient_id=payload.validated_data.get("recipient_id"),
            viewer=acting_user(request),
        )
        return Response(BulkEmailPreviewSerializer(built).data)
