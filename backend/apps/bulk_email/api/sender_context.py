"""``GET /bulk-email/sender``: who the signed-in sender may send bulk email to.

The compose screen reads it before it opens a draft: CalDART management sends to
everyone, a DART leader to the DART on their own profile, and a DART leader whose profile
names no DART is shown why they cannot send instead of the form.
"""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bulk_email.api.common import BULK_EMAIL_PERMISSIONS
from apps.bulk_email.reply_to import default_reply_to
from apps.bulk_email.senders import SenderContext, sender_context
from apps.members.api.actors import acting_user


class BulkEmailSenderSerializer(serializers.Serializer[SenderContext]):
    """What the caller may send to.

    ``is_management`` is true for CalDART management and a system administrator, who
    send to everyone.  ``dart`` and ``dart_name`` are the id and name of the DART a
    DART leader sends to, null and blank for CalDART management and for a leader whose
    profile names none.  ``can_send`` is false when there is nobody to send to, and
    ``reason`` then says why, blank otherwise.  ``default_reply_to`` is where replies to
    the caller's email go when they choose no Reply-To address
    (``apps.bulk_email.reply_to.default_reply_to``).
    """

    is_management = serializers.BooleanField()
    can_send = serializers.BooleanField()
    reason = serializers.CharField(allow_blank=True)
    dart = serializers.SerializerMethodField()
    dart_name = serializers.SerializerMethodField()
    default_reply_to = serializers.SerializerMethodField()

    def get_dart(self, context: SenderContext) -> int | None:
        """The id of the DART the caller sends to, or null for none."""
        return context.dart.pk if context.dart is not None else None

    def get_dart_name(self, context: SenderContext) -> str:
        """The name of the DART the caller sends to, or ``""`` for none."""
        return str(context.dart.name) if context.dart is not None else ""

    def get_default_reply_to(self, context: SenderContext) -> str:
        """Where replies go when the caller chooses no Reply-To address."""
        return default_reply_to(context.user)


class SenderContextView(APIView):
    """``GET /bulk-email/sender`` -- who the caller may send bulk email to."""

    permission_classes = BULK_EMAIL_PERMISSIONS

    @extend_schema(responses={200: BulkEmailSenderSerializer})
    def get(self, request: Request) -> Response:
        """200 with whether the caller may send, and to which DART when to one alone."""
        return Response(BulkEmailSenderSerializer(sender_context(acting_user(request))).data)
