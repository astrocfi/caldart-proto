"""Aircraft register and the DART leader check."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from django.contrib.auth import get_user_model
from django.db import transaction
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from rest_framework.request import Request
    from rest_framework.serializers import BaseSerializer

from apps.accounts.permissions import HasAnyRole, IsAccountAdmin, IsVerifier, user_has_any_role
from apps.accounts.roles import DART_LEADER, USER_ADMIN, VERIFY_ROLES
from apps.accounts.services import set_verifier
from apps.aircraft import registry, services
from apps.aircraft.api.permissions import AircraftPermission
from apps.aircraft.api.serializers import (
    AircraftChangeSerializer,
    AircraftDetailSerializer,
    AircraftSerializer,
    AircraftTypeCreateSerializer,
    AircraftTypeSerializer,
    InsuranceVerificationSerializer,
    LeaderSearchResultSerializer,
    LeaderStatusSerializer,
    MemberVerificationSerializer,
    RegistrationSerializer,
    RegistryStatusSerializer,
    VerifierGrantSerializer,
)
from apps.aircraft.filters import (
    DEFAULT_ORDERING,
    ORDERING_FIELDS,
    AircraftFilter,
    NullsLastOrderingFilter,
)
from apps.aircraft.models import (
    Aircraft,
    AircraftChange,
    Registration,
    RegistryImport,
    normalize_n_number,
)
from apps.aircraft.types import search_types
from apps.aircraft.verification import verify_insurance
from apps.members.api.actors import acting_user
from apps.members.models import MemberProfile
from apps.members.verification import verify_member

User = get_user_model()

#: The member check and the aircraft check are for every role that verifies: the
#: verifier, the DART leader, and the user and account administrators who support
#: them; ``system_admin`` passes through ``user_has_any_role``.
IsLeader = HasAnyRole(*VERIFY_ROLES)

#: Roles that may see who flies an aircraft: the same roles the checks open to.
PILOT_ROLES: tuple[str, ...] = VERIFY_ROLES

#: Roles that may grant or revoke the verifier role from the member check.
CanGrantVerifier = HasAnyRole(DART_LEADER, USER_ADMIN)


def aircraft_serializer_for(request: Request) -> type[AircraftSerializer]:
    """The register record, with ``pilots`` only for callers entitled to it.

    ``pilots`` carries other members' email addresses, membership state and
    medical currency -- exactly what the leader check gates behind the verifying roles.
    Returning it from the register to every signed-in member would walk
    straight around that gate, so plain members get the aircraft alone.
    """
    if user_has_any_role(request.user, PILOT_ROLES):
        return AircraftDetailSerializer
    return AircraftSerializer


class AircraftQuerysetMixin(generics.GenericAPIView[Aircraft]):
    """The register, filtered and ordered identically everywhere.

    The insurance verifier and the aircraft type are joined, so naming who verified each
    row, and its make and model, costs no query.
    """

    queryset = Aircraft.objects.select_related("insurance_verified_by", "type")
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
        """Save the new aircraft, and record who added it through ``record_added``.

        The record and its history row commit together: a failure writing the trail
        rolls the record back with it, so no aircraft can exist without a ``created``
        row naming who added it.
        """
        actor = acting_user(self.request)
        aircraft = serializer.save(created_by=actor)
        services.record_added(aircraft, actor=actor)


class AircraftDetailView(generics.RetrieveUpdateDestroyAPIView[Aircraft]):
    """``GET/PATCH/DELETE /aircraft/{id}`` with the register's object rules."""

    queryset = Aircraft.objects.select_related("type")
    permission_classes = [AircraftPermission]

    def get_serializer_class(self) -> type[AircraftSerializer]:
        """Return the serializer ``aircraft_serializer_for`` picks for this request.

        A holder of a verifying role gets ``AircraftDetailSerializer``, whose payload
        includes ``pilots``; every other signed-in member gets ``AircraftSerializer``,
        the same record without that field.
        """
        return aircraft_serializer_for(self.request)

    @transaction.atomic
    def perform_update(self, serializer: BaseSerializer[Aircraft]) -> None:
        """Save the edit, then record who made it and which columns moved.

        The row is re-read with ``select_for_update`` before anything else, so a save
        racing this one -- a verifier stamping the insurance on the same record --
        waits for this transaction to finish rather than being read here as though it
        had not happened.  The field list is worked out before the save, against that
        locked read (a model serializer assigns the validated attributes during
        ``save()``), so a form that resends every field it shows names only the ones
        whose value actually changed.  The edit and its history row commit together,
        so no write can leave the trail behind.
        """
        instance = cast("Aircraft", serializer.instance)
        instance = Aircraft.objects.select_for_update().get(pk=instance.pk)
        serializer.instance = instance
        fields = services.changed_fields(instance, dict(serializer.validated_data))
        actor = acting_user(self.request)
        aircraft = serializer.save()
        services.record_updated(aircraft, actor=actor, fields=fields)

    def perform_destroy(self, instance: Aircraft) -> None:
        """Delete the record and its history through ``services.delete_aircraft``."""
        services.delete_aircraft(instance, actor=acting_user(self.request))


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
        aircraft = get_object_or_404(Aircraft.objects.select_related("type"), n_number=n_number)
        serializer_class = aircraft_serializer_for(request)
        return Response(serializer_class(aircraft).data)


class AircraftTypeSearchView(APIView):
    """``GET /aircraft/types?q=`` (any member) and ``POST /aircraft/types`` (admin).

    ``GET`` answers the aircraft types matching ``q``, best first; ``POST`` adds a type
    the FAA has never registered.
    """

    def get_permissions(self) -> list[BasePermission]:
        """Any signed-in user may search; only an account administrator may add."""
        if self.request.method == "POST":
            return [IsAccountAdmin()]
        return [IsAuthenticated()]

    @extend_schema(
        parameters=[
            OpenApiParameter("q", str, description="What was typed: a name, a designator.")
        ],
        responses={200: AircraftTypeSerializer(many=True)},
    )
    def get(self, request: Request) -> Response:
        """Return up to ten aircraft types ``search_types`` finds for ``q``.

        A missing or blank ``q`` answers an empty list.
        """
        found = search_types(request.query_params.get("q", ""))
        return Response(AircraftTypeSerializer(found, many=True).data)

    @extend_schema(request=AircraftTypeCreateSerializer, responses={201: AircraftTypeSerializer})
    def post(self, request: Request) -> Response:
        """Add a custom aircraft type and return it with status 201.

        Answers 400 for a body ``AircraftTypeCreateSerializer`` refuses, a make and
        model already listed among them.
        """
        serializer = AircraftTypeCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        created = serializer.save()
        return Response(AircraftTypeSerializer(created).data, status=status.HTTP_201_CREATED)


class RegistryStatusView(APIView):
    """``GET /aircraft/registry`` -- the date the registry is as of, and the last run."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: RegistryStatusSerializer})
    def get(self, request: Request) -> Response:
        """Return ``{as_of, running, last}`` for the FAA registry import."""
        payload = {
            "as_of": registry.as_of(),
            "running": registry.is_running(),
            "last": RegistryImport.objects.order_by("-started_at", "-id").first(),
        }
        return Response(RegistryStatusSerializer(payload).data)


class RegistrationLookupView(APIView):
    """``GET /aircraft/registry/{n_number}`` -- one N-number in the FAA registry."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: RegistrationSerializer})
    def get(self, request: Request, n_number: str) -> Response:
        """Return the registration for the normalized ``n_number``.

        Answers 400 when ``n_number`` normalizes to nothing, and 404 with
        ``No registration for <N-number> in the registry.`` when the registry does not
        hold it.
        """
        normalized = normalize_n_number(n_number)
        if not normalized:
            return Response({"n_number": "Enter a registration, for example N12345."}, status=400)
        found = Registration.objects.select_related("type").filter(n_number=normalized).first()
        if found is None:
            raise NotFound(f"No registration for {normalized} in the registry.")
        return Response(RegistrationSerializer(found).data)


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

        Answers 404 when no such member exists, and for a deactivated account or a
        donor, which the member check never shows.
        """
        user = get_object_or_404(
            services.checkable_people().select_related("profile", "profile__dart"), pk=user_id
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
        aircraft = get_object_or_404(Aircraft.objects.select_related("type"), n_number=n_number)
        return Response(AircraftDetailSerializer(aircraft).data)


def _status_card(user_id: int) -> Response:
    """The status card for the checkable person ``user_id``, fetched afresh."""
    user = get_object_or_404(
        services.checkable_people().select_related("profile", "profile__dart"), pk=user_id
    )
    return Response(LeaderStatusSerializer(services.leader_status(user)).data)


class LeaderMemberVerificationView(APIView):
    """``PUT /leader/members/{user_id}/verification`` -- verify a member's documents."""

    permission_classes = [IsVerifier]

    @extend_schema(request=MemberVerificationSerializer, responses={200: LeaderStatusSerializer})
    def put(self, request: Request, user_id: int) -> Response:
        """Write the covered fields and the verified items, and return the status card.

        Answers 404 for anyone the member check never shows (an unknown id, a donor, a
        deactivated account), and 400 for a body the serializer refuses.  The write goes
        through :func:`apps.members.verification.verify_member` under the caller.
        """
        target = get_object_or_404(services.checkable_people(), pk=user_id)
        profile = MemberProfile.objects.filter(user=target).first()
        serializer = MemberVerificationSerializer(data=request.data, context={"profile": profile})
        serializer.is_valid(raise_exception=True)
        changes = dict(serializer.validated_data)
        verified = changes.pop("verified")
        verify_member(acting_user(request), target, changes=changes, verified=verified)
        return _status_card(user_id)


class LeaderMemberVerifierView(APIView):
    """``PUT /leader/members/{user_id}/verifier`` -- grant or revoke the verifier role."""

    permission_classes = [CanGrantVerifier]

    @extend_schema(request=VerifierGrantSerializer, responses={200: LeaderStatusSerializer})
    def put(self, request: Request, user_id: int) -> Response:
        """Give the member the verifier role, or take it away, and return the status card.

        Answers 404 for anyone the member check never shows, and 400 when ``verifier``
        is missing or not a boolean.  The role list is written through
        :func:`apps.accounts.services.set_verifier` under the caller.
        """
        target = get_object_or_404(services.checkable_people(), pk=user_id)
        serializer = VerifierGrantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        set_verifier(acting_user(request), target, wanted=serializer.validated_data["verifier"])
        return _status_card(user_id)


class LeaderAircraftVerificationView(APIView):
    """``PUT /leader/aircraft/{id}/verification`` -- verify an aircraft's insurance."""

    permission_classes = [IsVerifier]

    @extend_schema(
        request=InsuranceVerificationSerializer, responses={200: AircraftDetailSerializer}
    )
    def put(self, request: Request, pk: int) -> Response:
        """Write the insurance fields and the verdict, and return the aircraft record.

        Answers 404 when no aircraft has that id, and 400 for a body the serializer
        refuses.  The write goes through
        :func:`apps.aircraft.verification.verify_insurance` under the caller.
        """
        aircraft = get_object_or_404(Aircraft, pk=pk)
        serializer = InsuranceVerificationSerializer(aircraft, data=request.data)
        serializer.is_valid(raise_exception=True)
        changes = dict(serializer.validated_data)
        verified = bool(changes.pop("verified"))
        verify_insurance(aircraft, actor=acting_user(request), changes=changes, verified=verified)
        aircraft.refresh_from_db()
        return Response(AircraftDetailSerializer(aircraft).data)
