"""Member self-service endpoints, including attaching and detaching aircraft.

Every ``/me/...`` view works on ``request.user`` alone — there is no object id
to tamper with, so the only permission check needed is "is anybody signed in".
``/darts`` and ``/plans`` are the two public catalogs the join wizard reads
before the visitor has an account.
"""

from __future__ import annotations

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.aircraft.models import Aircraft
from apps.members.api.profile_serializers import (
    AircraftAttachSerializer,
    AircraftSummarySerializer,
    DartSerializer,
    MembershipTermSerializer,
    PaymentSummarySerializer,
    ProfileSerializer,
)
from apps.members.api.serializers import PlanSerializer
from apps.members.models import Dart, MemberProfile, MembershipPlan
from apps.members.services import membership_status


def get_or_create_profile(user) -> MemberProfile:
    """The caller's profile, created empty the first time they ask for it.

    Registration creates one, but a member imported or seeded
    without one must still be able to fill it in.
    """
    MemberProfile.objects.get_or_create(user=user)
    return MemberProfile.objects.select_related("dart").prefetch_related("aircraft").get(user=user)


class MyProfileView(RetrieveUpdateAPIView):
    """``GET /me/profile``, ``PUT`` for a full update, ``PATCH`` for a partial."""

    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self) -> MemberProfile:
        return get_or_create_profile(self.request.user)


class MyMembershipView(APIView):
    """``GET /me/membership`` — the status dict plus every term, newest first."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        terms = request.user.memberships.select_related("plan").all()
        data = dict(membership_status(request.user))
        data["history"] = MembershipTermSerializer(terms, many=True).data
        return Response(data)


class MyPaymentsView(APIView):
    """``GET /me/payments`` — the caller's payments, newest first."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        payments = request.user.payments.select_related("plan").order_by("-created_at", "-id")
        return Response(PaymentSummarySerializer(payments, many=True).data)


class MyProfileAircraftView(APIView):
    """``POST /me/profile/aircraft`` — attach an aircraft to the caller."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AircraftAttachSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        aircraft = get_object_or_404(Aircraft, pk=serializer.validated_data["aircraft_id"])

        profile = get_or_create_profile(request.user)
        # `add` is a no-op when the row is already there, so this is idempotent.
        profile.aircraft.add(aircraft)
        return Response(_attached(profile), status=status.HTTP_200_OK)


class MyProfileAircraftDetailView(APIView):
    """``DELETE /me/profile/aircraft/{aircraft_id}`` — detach it again."""

    permission_classes = [IsAuthenticated]

    def delete(self, request, aircraft_id: int):
        aircraft = get_object_or_404(Aircraft, pk=aircraft_id)
        profile = get_or_create_profile(request.user)
        profile.aircraft.remove(aircraft)
        return Response(status=status.HTTP_204_NO_CONTENT)


def _attached(profile: MemberProfile) -> dict:
    """The aircraft list the client should now show."""
    return {"aircraft": AircraftSummarySerializer(profile.aircraft.all(), many=True).data}


class DartListView(ListAPIView):
    """``GET /darts`` — public, active DARTs in their configured order."""

    serializer_class = DartSerializer
    permission_classes = [AllowAny]
    pagination_class = None
    queryset = Dart.objects.filter(is_active=True)


class PlanListView(ListAPIView):
    """``GET /plans`` — public, active membership plans in their order."""

    serializer_class = PlanSerializer
    permission_classes = [AllowAny]
    pagination_class = None
    queryset = MembershipPlan.objects.filter(is_active=True)
