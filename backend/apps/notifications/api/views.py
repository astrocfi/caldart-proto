"""The notification endpoints: the event catalog and the subscriptions.

Every endpoint is the account administrator's, and a system administrator passes as
always; anybody else is a 403, and an anonymous caller a 401 from
``caldart.exceptions``.
"""

from __future__ import annotations

from django.db.models import QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAccountAdmin
from apps.members.api.actors import acting_user
from apps.notifications.api.serializers import (
    NotificationEventDict,
    NotificationEventSerializer,
    NotificationSubscriptionCreateSerializer,
    NotificationSubscriptionSerializer,
)
from apps.notifications.events import EVENTS
from apps.notifications.models import NotificationSubscription


def subscriptions() -> QuerySet[NotificationSubscription]:
    """Every subscription, by address, with its recipient and its creator."""
    return NotificationSubscription.objects.select_related("recipient_user", "created_by")


class EventListView(APIView):
    """``GET /notifications/events`` -- every event an address may subscribe to."""

    permission_classes = [IsAccountAdmin]

    @extend_schema(responses={200: NotificationEventSerializer(many=True)})
    def get(self, request: Request) -> Response:
        """200 with one entry per event, in catalog order."""
        rows: list[NotificationEventDict] = [
            {
                "slug": event.slug,
                "label": event.label,
                "category": event.category,
                "description": event.description,
                "roles": list(event.roles),
            }
            for event in EVENTS.values()
        ]
        # The stubs take the instance type from the single-object parameter, so
        # they do not widen it to a list when ``many`` is set.
        serializer = NotificationEventSerializer(rows, many=True)  # type: ignore[arg-type]
        return Response(serializer.data)


class SubscriptionListView(APIView):
    """``GET`` and ``POST /notifications/subscriptions`` -- who hears about what."""

    permission_classes = [IsAccountAdmin]

    @extend_schema(responses={200: NotificationSubscriptionSerializer(many=True)})
    def get(self, request: Request) -> Response:
        """200 with every subscription, unpaginated, ordered by address."""
        return Response(NotificationSubscriptionSerializer(subscriptions(), many=True).data)

    @extend_schema(
        request=NotificationSubscriptionCreateSerializer,
        responses={201: NotificationSubscriptionSerializer},
    )
    def post(self, request: Request) -> Response:
        """201 with the subscription set up; 400 for a body the serializer refuses."""
        serializer = NotificationSubscriptionCreateSerializer(
            data=request.data, context={"creator": acting_user(request)}
        )
        serializer.is_valid(raise_exception=True)
        subscription = serializer.save()
        return Response(
            NotificationSubscriptionSerializer(subscription).data, status=status.HTTP_201_CREATED
        )


class SubscriptionDetailView(generics.RetrieveUpdateDestroyAPIView[NotificationSubscription]):
    """``GET``, ``PATCH`` and ``DELETE /notifications/subscriptions/{id}``.

    ``PATCH`` changes ``events`` and ``is_active``; ``DELETE`` answers 204.  An id no
    subscription carries is a 404, and ``PUT`` a 405.
    """

    permission_classes = [IsAccountAdmin]
    serializer_class = NotificationSubscriptionSerializer
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self) -> QuerySet[NotificationSubscription]:
        """Every subscription."""
        return subscriptions()
