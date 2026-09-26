"""Member self-service endpoints, including attaching and detaching aircraft.

Every ``/me/...`` view works on ``request.user`` alone -- there is no object id
to tamper with, so the only permission check needed is "is anybody signed in".
``/darts`` and ``/plans`` are the two public catalogs the join wizard reads
before the visitor has an account.
"""

from __future__ import annotations

from typing import Any

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api.serializers import UserSerializer
from apps.accounts.models import User
from apps.aircraft.api.serializers import AircraftSummarySerializer
from apps.aircraft.models import Aircraft
from apps.members.api.actors import acting_user
from apps.members.api.profile_serializers import (
    AircraftAttachSerializer,
    AttachedAircraftSerializer,
    BecomeFriendSerializer,
    MembershipDetailSerializer,
    MembershipTermSerializer,
    PaymentSummarySerializer,
    ProfileSerializer,
)
from apps.members.api.serializers import PlanSerializer
from apps.members.models import MemberProfile, MembershipPlan
from apps.members.services import membership_status, touch_profile, undo_become_friend
from apps.payments.renewals import switch_to_friend
from caldart.exceptions import DomainError, DomainValidationError


def get_or_create_profile(user: User) -> MemberProfile:
    """The caller's profile, created empty the first time they ask for it.

    Registration creates one, but a member imported or seeded
    without one must still be able to fill it in.  The row comes back with its
    DART and aircraft already fetched, so serializing it costs no more queries.
    """
    MemberProfile.objects.get_or_create(user=user)
    return MemberProfile.objects.select_related("dart").prefetch_related("aircraft").get(user=user)


class MyProfileView(RetrieveUpdateAPIView[MemberProfile]):
    """``GET /me/profile``, ``PUT`` for a full update, ``PATCH`` for a partial."""

    serializer_class = ProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self) -> MemberProfile:
        """The caller's own profile, whatever id the URL might have carried."""
        return get_or_create_profile(acting_user(self.request))


class MyMembershipView(APIView):
    """``GET /me/membership`` -- the status dict plus every term, newest first."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: MembershipDetailSerializer})
    def get(self, request: Request) -> Response:
        """200 with the membership status, plus ``history`` over every term.

        The four status keys are the ones ``members.services.membership_status``
        answers, and ``history`` lists the caller's terms newest first, each as
        ``MembershipTermSerializer`` renders it.
        """
        caller = acting_user(request)
        terms = caller.memberships.select_related("plan").all()
        data: dict[str, Any] = dict(membership_status(caller))
        data["history"] = MembershipTermSerializer(terms, many=True).data
        return Response(data)


class MyPaymentsView(APIView):
    """``GET /me/payments`` -- the caller's payments, newest first."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: PaymentSummarySerializer(many=True)})
    def get(self, request: Request) -> Response:
        """200 with the caller's own payments, newest first."""
        payments = (
            acting_user(request)
            .payments.select_related("plan", "membership")
            .prefetch_related("refunds")
            .order_by("-created_at", "-id")
        )
        return Response(PaymentSummarySerializer(payments, many=True).data)


class MyProfileAircraftView(APIView):
    """``POST /me/profile/aircraft`` -- attach an aircraft to the caller."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=AircraftAttachSerializer, responses={200: AttachedAircraftSerializer})
    def post(self, request: Request) -> Response:
        """200 with the caller's aircraft list once ``aircraft_id`` is attached.

        A body without an integer ``aircraft_id`` is a 400, and an id no
        aircraft has is a 404.  Attaching an aircraft already attached changes
        nothing and still answers 200.  The profile's ``profile_updated_at``
        is stamped either way.
        """
        serializer = AircraftAttachSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        aircraft = get_object_or_404(Aircraft, pk=serializer.validated_data["aircraft_id"])

        profile = get_or_create_profile(acting_user(request))
        # `add` is a no-op when the row is already there, so this is idempotent.
        profile.aircraft.add(aircraft)
        touch_profile(profile)
        return Response(_attached(profile), status=status.HTTP_200_OK)


class MyProfileAircraftDetailView(APIView):
    """``DELETE /me/profile/aircraft/{aircraft_id}`` -- detach it again."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={204: OpenApiResponse(description="The aircraft is detached; no body.")},
    )
    def delete(self, request: Request, aircraft_id: int) -> Response:
        """204 once the aircraft is off the caller's profile.

        An id no aircraft has is a 404; one the caller never attached is still a
        204, and the aircraft record itself is left alone either way.  The
        profile's ``profile_updated_at`` is stamped either way too.
        """
        aircraft = get_object_or_404(Aircraft, pk=aircraft_id)
        profile = get_or_create_profile(acting_user(request))
        profile.aircraft.remove(aircraft)
        touch_profile(profile)
        return Response(status=status.HTTP_204_NO_CONTENT)


def _attached(profile: MemberProfile) -> dict[str, Any]:
    """The aircraft list the client should show, under the key ``aircraft``."""
    return {"aircraft": AircraftSummarySerializer(profile.aircraft.all(), many=True).data}


class PlanListView(ListAPIView[MembershipPlan]):
    """``GET /plans`` -- public, active membership plans in their order."""

    serializer_class = PlanSerializer
    permission_classes = [AllowAny]
    pagination_class = None
    queryset = MembershipPlan.objects.filter(is_active=True)


class MyKindFriendView(APIView):
    """``POST /me/kind/friend`` to become a friend, ``DELETE`` to take that back."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=BecomeFriendSerializer, responses={200: UserSerializer})
    def post(self, request: Request) -> Response:
        """200 with the ``user`` payload once the caller has asked to become a friend.

        A member whose membership is current becomes a friend the day after it runs out
        (``friend_on``); anybody else becomes one at once (``kind`` is ``friend``).  The
        automatic renewal is canceled either way.  When it takes a contribution the body
        must carry ``keep_contribution``: true keeps the contribution as a yearly
        recurring donation charged on the renewal's next charge day, false lets it stop,
        and leaving it out is 400 ``{"keep_contribution": ["This field is required."]}``.
        A lifetime member, a friend, and a donor are each a 400 ``{"detail": ...}``;
        nothing changes on any refusal.  An anonymous caller gets 401.
        """
        serializer = BecomeFriendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        keep = serializer.validated_data.get("keep_contribution")
        try:
            user = switch_to_friend(acting_user(request), keep_contribution=keep)
        except DomainValidationError:
            raise
        except DomainError as error:
            return Response({"detail": error.message}, status=status.HTTP_400_BAD_REQUEST)
        return Response(UserSerializer(user).data)

    @extend_schema(request=None, responses={200: UserSerializer})
    def delete(self, request: Request) -> Response:
        """200 with the ``user`` payload once a pending change to friend is taken back.

        ``friend_on`` is cleared, so the caller stays a member; a renewal the change
        canceled stays canceled.  With nothing pending -- no date, a date that has come,
        or a caller who is a friend -- the answer is 400 ``{"detail": "You have no
        pending change."}``.  An anonymous caller gets 401.
        """
        try:
            user = undo_become_friend(acting_user(request))
        except DomainError as error:
            return Response({"detail": error.message}, status=status.HTTP_400_BAD_REQUEST)
        return Response(UserSerializer(user).data)
