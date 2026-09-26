"""Scheduled-charge endpoints: the member's own mandates and the finance screens.

A person holds at most one automatic renewal and one recurring donation, so
``/me/renewal`` and ``/me/donation`` are singletons rather than collections: ``GET``
reads one or answers ``null``, ``POST /setup`` and ``POST /confirm`` turn it on,
``PATCH`` changes what it charges, and ``DELETE`` turns it off.  The two paths are
served by the same views, told which kind they serve by their ``donation`` flag.
The finance roles read every mandate of either kind and every attempt through
``/admin/renewals``, and can turn one off on a member's behalf.

Nothing here charges anybody: the scan in ``apps.payments.renewals`` is what
takes the money, and these endpoints only change what it will find.
"""

from __future__ import annotations

from typing import Any, cast

from django.db import transaction
from django.db.models import Q, QuerySet
from django.http import Http404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status as http_status
from rest_framework.exceptions import APIException, ValidationError
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
from apps.payments.renewals import (
    RENEWAL_CONTRIBUTION_CODE,
    MandateKind,
    RenewalContributionError,
    begin_mandate,
    cancel_mandate,
    check_renewable,
    refuse_renewal_contribution,
    save_method,
)

#: What ``DELETE /me/renewal``, ``/me/donation`` and ``/admin/renewals/{id}`` answer with.
DELETE_RESPONSE_DESCRIPTION = "The authority is off.  The body is empty."

#: What a caller is told when they ask about a mandate they do not have, by kind.
NO_MANDATE = "You have no automatic renewal to change."
NO_DONATION = "You have no recurring donation to change."


class RenewalContributionConflictError(APIException):
    """A recurring donation refused because the renewal already takes a contribution.

    Rendered as ``400 {"detail": <sentence>, "code": "renewal_contribution"}``: the
    ``code`` tells the portal to offer a **Continue** button that sends the request
    again with ``remove_renewal_contribution``.
    """

    status_code = http_status.HTTP_400_BAD_REQUEST

    def __init__(self, error: RenewalContributionError) -> None:
        """Build the body from the domain refusal ``error``."""
        super().__init__({"detail": error.message, "code": RENEWAL_CONTRIBUTION_CODE})


def signed_in_user(request: Request) -> User:
    """The member behind a request ``IsAuthenticated`` has let through.

    Every caller here runs after that permission, so the user is never anonymous;
    DRF types ``Request.user`` as either a user or ``AnonymousUser`` whatever the
    permissions say, which is what the cast records.
    """
    return cast(User, request.user)


def renewable_plan(slug: str) -> MembershipPlan:
    """The active plan named by ``slug``, or a 400 keyed by ``plan``."""
    plan = MembershipPlan.objects.filter(slug=slug, is_active=True).first()
    if plan is None:
        raise ValidationError({"plan": f"Unknown membership plan '{slug}'."})
    return plan


def own_mandate(request: Request, *, donation: bool) -> RenewalMandate | None:
    """The caller's own donation or renewal, or ``None`` when they hold none of that kind.

    ``donation`` picks the mandate that names no plan; otherwise the one that does.
    """
    return RenewalMandate.objects.filter(
        user=signed_in_user(request), plan__isnull=donation
    ).first()


def missing_mandate(*, donation: bool) -> Http404:
    """The 404 for a caller who holds no mandate of the kind they asked about."""
    return Http404(NO_DONATION if donation else NO_MANDATE)


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
    """``GET | PATCH | DELETE /me/renewal`` and ``/me/donation`` -- the caller's own.

    ``donation`` says which of the two authorities this view serves: the renewal,
    which names a plan, or the recurring donation, which names none.
    """

    permission_classes = [IsAuthenticated]
    donation = False

    @extend_schema(responses={200: RenewalEnvelopeSerializer})
    def get(self, request: Request) -> Response:
        """200 with the ``{"mandate": ...}`` envelope; ``mandate`` is ``null`` when none.

        A canceled or paused mandate is still returned, with its status, so the
        portal can offer to turn it on again and show why it stopped.
        """
        return Response(mandate_body(own_mandate(request, donation=self.donation)))

    @extend_schema(request=RenewalPatchSerializer, responses={200: RenewalEnvelopeSerializer})
    def patch(self, request: Request) -> Response:
        """200 with the mandate after changing what it charges, how often, and when.

        ``contribution_cents`` is the contribution from now on.  For the renewal,
        ``plan`` names the plan that renews from now on and leaving it out leaves the
        plan alone; for the donation, ``cadence`` changes how often it charges and
        leaving it out leaves it alone.  ``next_charge_on`` moves the day of the next
        charge, leaving the stored day alone when it is absent.  A charge already
        scheduled keeps the day it was written for, which is the day the answer
        carries; ``_record_success`` overwrites the stored day after every charge, to
        the term the charge bought for a renewal or one cadence on for a donation, so
        a day chosen while a charge is scheduled only lasts until that charge
        completes.

        404 when the caller holds no mandate of this kind; 400 naming
        ``contribution_cents`` for an amount outside what a checkout would accept, and
        for a contribution on a renewal while the caller holds a recurring donation;
        400 naming ``next_charge_on`` for a day that has already gone by, ``plan`` for
        a plan that is not on offer, ``cadence`` for a renewal on any cadence but
        yearly, and ``auto_renew`` for anything the authority could not charge again
        -- a donation of nothing, a life member's plan, a plan that never expires --
        which is the same rule the setup endpoint applies.  The dues themselves are
        not settable: they are the plan's price at the time of each charge.
        """
        mandate = own_mandate(request, donation=self.donation)
        if mandate is None:
            raise missing_mandate(donation=self.donation)
        payload = RenewalPatchSerializer(data=request.data, context={"donation": self.donation})
        payload.is_valid(raise_exception=True)
        user = signed_in_user(request)
        contribution_cents = payload.validated_data["contribution_cents"]
        slug = payload.validated_data["plan"]
        # An absent slug leaves the plan alone, so what the mandate would hold
        # afterwards is what the rule is applied to either way.
        wanted = renewable_plan(slug) if slug else mandate.plan
        fields = ["contribution_cents", "updated_at"]
        chosen = payload.validated_data["next_charge_on"]
        if chosen is not None:
            mandate.next_charge_on = chosen
            fields.append("next_charge_on")
        cadence = payload.validated_data["cadence"]
        if cadence is not None:
            mandate.cadence = cadence
            fields.append("cadence")
        mandate.plan = check_renewable(
            wanted, mandate.provider, user=user, contribution_cents=contribution_cents
        )
        if not self.donation:
            refuse_renewal_contribution(user, contribution_cents)
        if slug:
            fields.insert(0, "plan")
        mandate.contribution_cents = contribution_cents
        mandate.save(update_fields=fields)
        return Response(mandate_body(mandate))

    @extend_schema(
        responses={204: OpenApiResponse(description=DELETE_RESPONSE_DESCRIPTION)},
    )
    def delete(self, request: Request) -> Response:
        """204 once the authority is off, whatever state it was in.

        Every scheduled charge is dropped and the member is emailed that it is
        off.  The other kind of authority, if the caller holds one, is untouched.
        404 when the caller holds no mandate of this kind.
        """
        mandate = own_mandate(request, donation=self.donation)
        if mandate is None:
            raise missing_mandate(donation=self.donation)
        cancel_mandate(mandate, actor=signed_in_user(request))
        return Response(status=http_status.HTTP_204_NO_CONTENT)


class MyRenewalSetupView(APIView):
    """``POST /me/renewal/setup`` and ``/me/donation/setup`` -- start saving a method."""

    permission_classes = [IsAuthenticated]
    donation = False

    @extend_schema(request=RenewalSetupSerializer, responses={200: RenewalSetupResponseSerializer})
    def post(self, request: Request) -> Response:
        """200 with ``{provider, client}`` for the browser to collect a method with.

        Creates or resets the caller's ``pending`` mandate of this kind over what was
        asked for, then asks the provider for whatever the browser needs -- a Stripe
        SetupIntent's client secret, a PayPal setup token, nothing at all for the
        mock provider.  No money moves.

        For the renewal, ``plan`` names the plan to renew, once a year.  For the
        donation, ``plan`` is not read, and ``contribution_cents`` is given on
        ``cadence``.  ``next_charge_on`` is the day of the first charge; left out,
        it is the day the membership runs out for a renewal, and today for a
        donation.

        400 naming ``plan`` for a plan that is not on offer, ``next_charge_on`` for
        a day that has already gone by, ``cadence`` for a renewal that is not
        yearly, ``contribution_cents`` for a contribution on a renewal while the
        caller holds a recurring donation, ``auto_renew`` for a renewal with no plan
        or with one that never expires, for a life member who names a plan, and for
        a donation of nothing, and ``detail`` when the provider refuses to start, in
        which case nothing is written.
        A donation asked for while the caller's renewal takes a contribution is
        ``400 {"detail": ..., "code": "renewal_contribution"}`` unless the body
        carries ``remove_renewal_contribution: true``, which takes that contribution
        off the renewal first.
        """
        payload = RenewalSetupSerializer(data=request.data, context={"donation": self.donation})
        payload.is_valid(raise_exception=True)
        provider_slug = payload.validated_data["provider"]

        slug = payload.validated_data["plan"]
        plan = renewable_plan(slug) if slug else None

        # One transaction, so a provider that refuses to start leaves the caller's
        # mandates -- and any contribution moved off the renewal -- as they were.
        with transaction.atomic():
            try:
                mandate = begin_mandate(
                    signed_in_user(request),
                    plan=plan,
                    contribution_cents=payload.validated_data["contribution_cents"],
                    provider=provider_slug,
                    next_charge_on=payload.validated_data["next_charge_on"],
                    cadence=payload.validated_data["cadence"],
                    remove_renewal_contribution=payload.validated_data[
                        "remove_renewal_contribution"
                    ],
                )
            except RenewalContributionError as exc:
                raise RenewalContributionConflictError(exc) from exc
            try:
                client = get_provider(provider_slug).start_mandate(mandate)
            except PaymentError as exc:
                raise ValidationError({"detail": str(exc)}) from exc
        return Response({"provider": provider_slug, "client": client})


class MyRenewalConfirmView(APIView):
    """``POST /me/renewal/confirm`` and ``/me/donation/confirm`` -- save the method."""

    permission_classes = [IsAuthenticated]
    donation = False

    @extend_schema(request=RenewalConfirmSerializer, responses={200: RenewalEnvelopeSerializer})
    def post(self, request: Request) -> Response:
        """200 with the mandate, now active, once the provider confirms the method.

        The body carries the provider's handle on what the browser did:
        ``setup_intent_id`` for Stripe, ``setup_token`` for PayPal, neither for
        the mock provider.  404 when the caller started no setup of this kind, and
        400 naming ``detail`` when the provider will not confirm what it is given.
        """
        payload = RenewalConfirmSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        mandate = own_mandate(request, donation=self.donation)
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
#: How each mandate kind narrows the finance list.
KIND_FILTERS: dict[str, Q] = {
    MandateKind.CONTRIBUTION: Q(plan__isnull=True),
    MandateKind.BOTH: Q(plan__isnull=False, contribution_cents__gt=0),
    MandateKind.RENEWAL: Q(plan__isnull=False, contribution_cents=0),
}


class AdminRenewalListView(ListAPIView[RenewalMandate]):
    """``GET /admin/renewals`` -- every mandate of either kind, newest first."""

    permission_classes = [IsAuthenticated, IsFinance]
    serializer_class = RenewalMandateSerializer
    search_fields = ["user__email", "user__first_name", "user__last_name", "method_label"]
    ordering_fields = ["created_at", "status", "last_charged_at"]

    def get_queryset(self) -> QuerySet[RenewalMandate]:
        """Every mandate, narrowed by ``?status=`` and ``?kind=`` when they are given.

        ``kind`` is ``renewal``, ``both`` or ``contribution`` (a recurring
        donation), the values each row's ``kind`` carries.  Raises DRF's
        ``ValidationError`` keyed by ``status`` for a status outside the mandate
        states, and by ``kind`` for any other kind.  Only a treasurer or an account
        administrator reaches this.

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
        kind = query.validated_data["kind"]
        if kind:
            queryset = queryset.filter(KIND_FILTERS[kind])
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
