"""``/messages``: the bulk emails the signed-in person received, as their own copies.

Every signed-in person reads their own messages here, whatever their roles; nobody reads
another's.  An anonymous caller is a 401.  See ``apps.bulk_email.archive``.
"""

from __future__ import annotations

from django.http import Http404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bulk_email.archive import Message, OpenedMessage, message_for, messages_for
from apps.bulk_email.batch import email_type_name
from apps.bulk_email.models import BulkEmailRecipient
from apps.members.api.actors import acting_user


class BulkEmailMessageSerializer(serializers.Serializer[Message]):
    """One message the reader received, as the Messages list shows it.

    ``id`` is the bulk email's.  ``subject`` is the subject as the reader's copy had it,
    ``sent_at`` when their copy went, ``from_name`` who sent it (the organization's
    name once the sender's account is gone), and ``email_type_name`` the kind of email
    it is, blank for none.  ``answer_url`` is the reader's own answer page for a mission
    callout, blank for any other email.
    """

    id = serializers.IntegerField(source="bulk.pk")
    subject = serializers.CharField()
    sent_at = serializers.DateTimeField(source="recipient.tried_at")
    from_name = serializers.CharField()
    email_type_name = serializers.SerializerMethodField()
    answer_url = serializers.CharField()

    def get_email_type_name(self, message: Message) -> str:
        """The kind of email it is, or ``""`` for none."""
        return email_type_name(message.bulk)


class BulkEmailMessageDetailSerializer(serializers.Serializer[OpenedMessage]):
    """One message as the reader received it: the list's fields and the copy itself.

    ``html`` is the whole HTML email and ``text`` the plain-text one, filled in from the
    values stored on the reader's own row when it went.  ``answer_url`` is the reader's
    own answer page for a mission callout, blank for any other email.
    """

    id = serializers.IntegerField(source="message.bulk.pk")
    subject = serializers.CharField(source="message.subject")
    sent_at = serializers.DateTimeField(source="message.recipient.tried_at")
    from_name = serializers.CharField(source="message.from_name")
    email_type_name = serializers.SerializerMethodField()
    answer_url = serializers.CharField(source="message.answer_url")
    html = serializers.CharField(source="copy.html")
    text = serializers.CharField(source="copy.text")

    def get_email_type_name(self, opened: OpenedMessage) -> str:
        """The kind of email it is, or ``""`` for none."""
        return email_type_name(opened.message.bulk)


class MessageListView(APIView):
    """``GET /messages`` -- every bulk email the caller received, newest first."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: BulkEmailMessageSerializer(many=True)})
    def get(self, request: Request) -> Response:
        """200 with the caller's messages; unpaginated, since a few go out a month."""
        messages = messages_for(acting_user(request))
        # The stubs type a plain Serializer's instance as one object, even with many=True.
        return Response(BulkEmailMessageSerializer(messages, many=True).data)  # type: ignore[arg-type]


class MessageDetailView(APIView):
    """``GET /messages/{id}`` -- one bulk email, as the caller's own copy."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: BulkEmailMessageDetailSerializer})
    def get(self, request: Request, pk: int) -> Response:
        """200 with the caller's copy; 404 for one they did not receive, or one hidden."""
        try:
            opened = message_for(acting_user(request), pk)
        except BulkEmailRecipient.DoesNotExist as missing:
            raise Http404 from missing
        return Response(BulkEmailMessageDetailSerializer(opened).data)
