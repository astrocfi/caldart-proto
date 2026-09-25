"""Aircraft register and the DART leader check."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from rest_framework.request import Request
    from rest_framework.serializers import BaseSerializer

from apps.accounts.permissions import HasAnyRole, IsAccountAdmin, user_has_any_role
from apps.accounts.roles import ACCOUNT_ADMIN, DART_LEADER
from apps.aircraft import services
from apps.aircraft.api.permissions import AircraftPermission
from apps.aircraft.api.serializers import (
    AircraftChangeSerializer,
    AircraftDetailSerializer,
    AircraftSerializer,
    LeaderSearchResultSerializer,
    LeaderStatusSerializer,
)
from apps.aircraft.filters import (
    DEFAULT_ORDERING,
    ORDERING_FIELDS,
    AircraftFilter,
    NullsLastOrderingFilter,
)
from apps.aircraft.models import Aircraft, AircraftChange, AircraftChangeKind, normalize_n_number
from apps.members.api.actors import acting_user
from caldart import audit

User = get_user_model()

#: The leader check is for leaders, and for the administrators who support
#: them; ``system_admin`` passes through ``user_has_any_role``.
IsLeader = HasAnyRole(DART_LEADER, ACCOUNT_ADMIN)

#: Roles that may see who flies an aircraft.
PILOT_ROLES: tuple[str, ...] = (DART_LEADER, ACCOUNT_ADMIN)


def aircraft_serializer_for(request: Request) -> type[AircraftSerializer]:
    """The register record, with ``pilots`` only for callers entitled to it.

    ``pilots`` carries other members' email addresses, membership state and
    medical currency -- exactly what the leader check gates behind ``dart_leader``.
    Returning it from the register to every signed-in member would walk
    straight around that gate, so plain members get the aircraft alone.
    """
    if user_has_any_role(request.user, PILOT_ROLES):
        return AircraftDetailSerializer
    return AircraftSerializer


class AircraftQuerysetMixin(generics.GenericAPIView[Aircraft]):
    """The register, filtered and ordered identically everywhere."""

    queryset = Aircraft.objects.all()
    filter_backends = [DjangoFilterBackend, NullsLastOrderingFilter]
    filterset_class = AircraftFilter
    ordering_fields = ORDERING_FIELDS
    ordering = DEFAULT_ORDERING


class AircraftListCreateView(AircraftQuerysetMixin, generics.ListCreateAPIView[Aircraft]):
    """``GET /aircraft`` (any member) and ``POST /aircraft`` (any member)."""

    serializer_class = AircraftSerializer
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def perform_create(self, serializer: BaseSerializer[Aircraft]) -> None:
        """Save the new aircraft, recording who added it in the history and the log.

        The record and its history row commit together: a failure writing the trail
        rolls the record back with it, so no aircraft can exist without a ``created``
        row naming who added it.
        """
        actor = acting_user(self.request)
        aircraft = serializer.save(created_by=actor)
        services.record_change(aircraft, actor=actor, kind=AircraftChangeKind.CREATED, fields=[])
        audit.record(audit.AIRCRAFT_CREATE, actor=actor, target=aircraft)


class AircraftDetailView(generics.RetrieveUpdateDestroyAPIView[Aircraft]):
    """``GET/PATCH/DELETE /aircraft/{id}`` with the register's object rules."""

    queryset = Aircraft.objects.all()
    permission_classes = [AircraftPermission]

    def get_serializer_class(self) -> type[AircraftSerializer]:
        """Return the serializer ``aircraft_serializer_for`` picks for this request.

        A DART leader or account admin gets ``AircraftDetailSerializer``, whose payload
        includes ``pilots``; every other signed-in member gets ``AircraftSerializer``,
        the same record without that field.
        """
        return aircraft_serializer_for(self.request)

    @transaction.atomic
    def perform_update(self, serializer: BaseSerializer[Aircraft]) -> None:
        """Save the edit, then record who made it and which columns moved.

        The field list is worked out before the save, while ``serializer.instance``
        still carries the stored values (a model serializer assigns the validated
        attributes during ``save()``), so a form that resends every field it shows
        names only the ones whose value actually changed.  The edit and its history
        row commit together, so no write can leave the trail behind.
        """
        instance = cast("Aircraft", serializer.instance)
        fields = services.changed_fields(instance, dict(serializer.validated_data))
        actor = acting_user(self.request)
        aircraft = serializer.save()
        services.record_change(
            aircraft, actor=actor, kind=AircraftChangeKind.UPDATED, fields=fields
        )
        audit.record(audit.AIRCRAFT_UPDATE, actor=actor, target=aircraft, fields=fields)

    def perform_destroy(self, instance: Aircraft) -> None:
        """Delete the record, its history with it, and log the deletion."""
        audit.record(audit.AIRCRAFT_DELETE, actor=acting_user(self.request), target=instance)
        instance.delete()


class AircraftChangesView(generics.ListAPIView[AircraftChange]):
    """``GET /aircraft/{id}/changes`` -- who changed one record, newest first."""

    serializer_class = AircraftChangeSerializer
    permission_classes = [IsAccountAdmin]
    pagination_class = None

    def get_queryset(self) -> QuerySet[AircraftChange]:
        """The changes to the aircraft in the URL, newest first, with each actor joined.

        Answers 404 when no aircraft has that id, rather than an empty history.
        """
        aircraft = get_object_or_404(Aircraft, pk=self.kwargs["pk"])
        return aircraft.changes.select_related("changed_by")


class AircraftLookupView(APIView):
    """``GET /aircraft/lookup?n_number=`` -- exact match after normalization."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: AircraftDetailSerializer})
    def get(self, request: Request) -> Response:
        """Look up the aircraft with the normalized ``n_number``.

        Answers 400 when ``n_number`` is missing or normalizes to nothing, and 404 when
        no aircraft matches.
        """
        n_number = normalize_n_number(request.query_params.get("n_number", ""))
        if not n_number:
            return Response({"n_number": "Enter a registration, for example N12345."}, status=400)
        aircraft = get_object_or_404(Aircraft, n_number=n_number)
        serializer_class = aircraft_serializer_for(request)
        return Response(serializer_class(aircraft).data)


# --------------------------------------------------------------------------
# Leader check -- dart_leader
# --------------------------------------------------------------------------
class LeaderSearchView(APIView):
    """``GET /leader/search?q=<name|email|n-number>`` -- at most 20 people."""

    permission_classes = [IsLeader]

    @extend_schema(responses={200: LeaderSearchResultSerializer(many=True)})
    def get(self, request: Request) -> Response:
        """Return up to 20 members matching ``q`` by name, email, or N-number."""
        query = request.query_params.get("q", "")
        results = [services.search_result(user) for user in services.search_members(query)]
        return Response(LeaderSearchResultSerializer(results, many=True).data)


class LeaderMemberStatusView(APIView):
    """``GET /leader/members/{user_id}/status`` -- the pre-flight status card."""

    permission_classes = [IsLeader]

    @extend_schema(responses={200: LeaderStatusSerializer})
    def get(self, request: Request, user_id: int) -> Response:
        """Return the pre-flight status card for the member with primary key ``user_id``.

        Answers 404 when no such member exists.
        """
        user = get_object_or_404(
            User.objects.select_related("profile", "profile__dart"), pk=user_id
        )
        return Response(LeaderStatusSerializer(services.leader_status(user)).data)


class LeaderAircraftView(APIView):
    """``GET /leader/aircraft?n_number=`` -- the insurance card for one plane."""

    permission_classes = [IsLeader]

    @extend_schema(responses={200: AircraftDetailSerializer})
    def get(self, request: Request) -> Response:
        """Return the insurance card for the aircraft with the normalized ``n_number``.

        Answers 400 when ``n_number`` is missing or normalizes to nothing, and 404 when
        no aircraft matches.
        """
        n_number = normalize_n_number(request.query_params.get("n_number", ""))
        if not n_number:
            return Response({"n_number": "Enter a registration, for example N12345."}, status=400)
        aircraft = get_object_or_404(Aircraft, n_number=n_number)
        return Response(AircraftDetailSerializer(aircraft).data)
