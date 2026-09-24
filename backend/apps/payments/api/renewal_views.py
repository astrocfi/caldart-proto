"""Automatic-renewal endpoints: the member's own mandate and the finance screens.

A member owns exactly one mandate, so ``/me/renewal`` is a singleton rather than
a collection: ``GET`` reads it or answers ``null``, ``POST /setup`` and ``POST
/confirm`` turn it on, ``PATCH`` changes the contribution, and ``DELETE`` turns
it off.  The finance roles read every mandate and every attempt through
``/admin/renewals``, and can turn one off on a member's behalf.

Nothing here charges anybody: the scan in ``apps.payments.renewals`` is what
takes the money, and these endpoints only change what it will find.
"""

from __future__ import annotations

from typing import Any, cast

from django.db.models import QuerySet
from django.http import Http404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status as http_status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import IsFinance
from apps.members.models import MembershipPlan
from apps.payments.api.serializers import (
    RenewalAttemptSerializer,
    RenewalConfirmSerializer,
    RenewalEnvelopeSerializer,
    RenewalMandateSerializer,
    RenewalPatchSerializer,
    RenewalSetupResponseSerializer,
    RenewalSetupSerializer,
    RenewalStatusFilterSerializer,
)
from apps.payments.models import RenewalAttempt, RenewalMandate, RenewalOutcome
from apps.payments.providers.base import PaymentError, get_provider
from apps.payments.renewals import begin_mandate, cancel_mandate, save_method

#: What ``DELETE /me/renewal`` and ``DELETE /admin/renewals/{id}`` answer with.
DELETE_RESPONSE_DESCRIPTION = "Automatic renewal is off.  The body is empty."

#: What a caller is told when they ask about a mandate they do not have.
NO_MANDATE = "You have no automatic renewal to change."


def signed_in_user(request: Request) -> User:
    """The member behind a request ``IsAuthenticated`` has let through.

    Every caller here runs after that permission, so the user is never anonymous;
    DRF types ``Request.user`` as either a user or ``AnonymousUser`` whatever the
    permissions say, which is what the cast records.
    """
    return cast(User, request.user)


def own_mandate(request: Request) -> RenewalMandate | None:
    """The caller's own mandate, or ``None`` when they have never turned one on."""
    return RenewalMandate.objects.filter(user=signed_in_user(request)).first()


def mandate_body(mandate: RenewalMandate | None) -> dict[str, Any]:
    """The ``{"mandate": ...}`` envelope ``/me/renewal`` answers with.

    ``mandate`` is ``null`` for a member who has never turned automatic renewal
    on.  The envelope is what carries that null: DRF renders a bare ``None`` as
    an empty body, which a browser cannot tell from a failure.
    """
    if mandate is None:
        return {"mandate": None}
    return {"mandate": dict(RenewalMandateSerializer(mandate).data)}


class MyRenewalView(APIView):
    """``GET | PATCH | DELETE /me/renewal`` -- the caller's own standing authority."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: RenewalEnvelopeSerializer})
    def get(self, request: Request) -> Response:
        """200 with the ``{"mandate": ...}`` envelope; ``mandate`` is ``null`` when none.

        A canceled or paused mandate is still returned, with its status, so the
        portal can offer to turn it on again and show why it stopped.
        """
        return Response(mandate_body(own_mandate(request)))

    @extend_schema(request=RenewalPatchSerializer, responses={200: RenewalEnvelopeSerializer})
    def patch(self, request: Request) -> Response:
        """200 with the mandate after changing the contribution renewed with the dues.

        404 when the caller has no mandate, and 400 naming ``contribution_cents``
        for an amount outside what a checkout would accept.  The dues themselves
        are not settable: they are the plan's price at the time of each charge.
        """
        mandate = own_mandate(request)
        if mandate is None:
            raise Http404(NO_MANDATE)
        payload = RenewalPatchSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        mandate.contribution_cents = payload.validated_data["contribution_cents"]
        mandate.save(update_fields=["contribution_cents", "updated_at"])
        return Response(mandate_body(mandate))

    @extend_schema(
        responses={204: OpenApiResponse(description=DELETE_RESPONSE_DESCRIPTION)},
    )
    def delete(self, request: Request) -> Response:
        """204 once automatic renewal is off, whatever state the mandate was in.

        Every scheduled charge is dropped and the member is emailed that it is
        off.  404 when the caller has no mandate at all.
        """
        mandate = own_mandate(request)
        if mandate is None:
            raise Http404(NO_MANDATE)
        cancel_mandate(mandate, actor=signed_in_user(request))
        return Response(status=http_status.HTTP_204_NO_CONTENT)


class MyRenewalSetupView(APIView):
    """``POST /me/renewal/setup`` -- start saving a payment method."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=RenewalSetupSerializer, responses={200: RenewalSetupResponseSerializer})
    def post(self, request: Request) -> Response:
        """200 with ``{provider, client}`` for the browser to collect a method with.

        Creates or resets the caller's ``pending`` mandate over the plan,
        contribution and provider asked for, then asks the provider for whatever
        the browser needs -- a Stripe SetupIntent's client secret, a PayPal setup
        token, nothing at all for the mock provider.  No money moves.

        400 naming ``plan`` for a plan that is not on offer, naming ``auto_renew``
        for one that never expires, and naming ``detail`` when the provider
        refuses to start.
        """
        payload = RenewalSetupSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        provider_slug = payload.validated_data["provider"]

        slug = payload.validated_data["plan"]
        plan = MembershipPlan.objects.filter(slug=slug, is_active=True).first()
        if plan is None:
            raise ValidationError({"plan": f"Unknown membership plan '{slug}'."})

        mandate = begin_mandate(
            signed_in_user(request),
            plan=plan,
            contribution_cents=payload.validated_data["contribution_cents"],
            provider=provider_slug,
        )
        try:
            client = get_provider(provider_slug).start_mandate(mandate)
        except PaymentError as exc:
            raise ValidationError({"detail": str(exc)}) from exc
        return Response({"provider": provider_slug, "client": client})


class MyRenewalConfirmView(APIView):
    """``POST /me/renewal/confirm`` -- save the method the browser just collected."""

    permission_classes = [IsAuthenticated]

    @extend_schema(request=RenewalConfirmSerializer, responses={200: RenewalEnvelopeSerializer})
    def post(self, request: Request) -> Response:
        """200 with the mandate, now active, once the provider confirms the method.

        The body carries the provider's handle on what the browser did:
        ``setup_intent_id`` for Stripe, ``setup_token`` for PayPal, neither for
        the mock provider.  404 when the caller started no setup, and 400 naming
        ``detail`` when the provider will not confirm what it is given.
        """
        payload = RenewalConfirmSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        mandate = own_mandate(request)
        if mandate is None:
            raise Http404("You have not started saving a payment method.")

        try:
            method = get_provider(mandate.provider).confirm_mandate(
                mandate, **payload.validated_data
            )
        except PaymentError as exc:
            raise ValidationError({"detail": str(exc)}) from exc

        save_method(mandate, method, actor=signed_in_user(request))
        return Response(mandate_body(mandate))


# --------------------------------------------------------------------------
# Finance
# --------------------------------------------------------------------------
class AdminRenewalListView(ListAPIView[RenewalMandate]):
    """``GET /admin/renewals`` -- every mandate, newest first, paginated."""

    permission_classes = [IsAuthenticated, IsFinance]
    serializer_class = RenewalMandateSerializer
    search_fields = ["user__email", "user__first_name", "user__last_name", "method_label"]
    ordering_fields = ["created_at", "status", "last_charged_at"]

    def get_queryset(self) -> QuerySet[RenewalMandate]:
        """Every mandate, narrowed by ``?status=`` when one is given.

        Raises DRF's ``ValidationError`` keyed by ``status`` for a status outside
        the mandate states.  Only a treasurer or an account administrator reaches
        this.

        The attempts and the member's terms are prefetched, because the serializer
        reads the next charge date and the last decline out of them: without that
        the page costs three further queries for every row it answers.
        """
        query = RenewalStatusFilterSerializer(data=self.request.query_params)
        query.is_valid(raise_exception=True)
        queryset = RenewalMandate.objects.select_related("user", "plan").prefetch_related(
            "attempts", "user__memberships"
        )
        wanted = query.validated_data["status"]
        if wanted:
            queryset = queryset.filter(status=wanted)
        return queryset


class AdminRenewalDetailView(APIView):
    """``GET | DELETE /admin/renewals/{id}`` -- one member's standing authority."""

    permission_classes = [IsAuthenticated, IsFinance]

    def load(self, mandate_id: int) -> RenewalMandate:
        """The mandate named by ``mandate_id``, or ``Http404``."""
        mandate = (
            RenewalMandate.objects.filter(pk=mandate_id).select_related("user", "plan").first()
        )
        if mandate is None:
            raise Http404("No such renewal.")
        return mandate

    @extend_schema(responses={200: RenewalMandateSerializer})
    def get(self, request: Request, pk: int) -> Response:
        """200 with the mandate, including the reason its last charge failed."""
        return Response(RenewalMandateSerializer(self.load(pk)).data)

    @extend_schema(responses={204: OpenApiResponse(description=DELETE_RESPONSE_DESCRIPTION)})
    def delete(self, request: Request, pk: int) -> Response:
        """204 once the member's automatic renewal is off, and they have been told.

        Every scheduled charge is dropped.  The audit record names the
        administrator who turned it off, so it is never mistaken for the member's
        own decision.
        """
        cancel_mandate(self.load(pk), actor=signed_in_user(request))
        return Response(status=http_status.HTTP_204_NO_CONTENT)


class AdminRenewalAttemptListView(ListAPIView[RenewalAttempt]):
    """``GET /admin/renewals/attempts`` -- the scheduled charges, newest first."""

    permission_classes = [IsAuthenticated, IsFinance]
    serializer_class = RenewalAttemptSerializer
    search_fields = ["mandate__user__email", "mandate__user__last_name", "error"]
    ordering_fields = ["scheduled_on", "outcome"]

    def get_queryset(self) -> QuerySet[RenewalAttempt]:
        """Every attempt with its mandate and member loaded, latest scheduled first.

        ``?outcome=`` narrows to one outcome; anything outside the attempt
        outcomes is a 400 keyed by ``outcome``.
        """
        queryset = RenewalAttempt.objects.select_related("mandate", "mandate__user")
        wanted = (self.request.query_params.get("outcome") or "").strip()
        if not wanted:
            return queryset
        if wanted not in RenewalOutcome.values:
            raise ValidationError({"outcome": f"Unknown outcome '{wanted}'."})
        return queryset.filter(outcome=wanted)
