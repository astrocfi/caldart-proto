"""Switching between a member and a friend of CalDART, from the portal.

``POST /me/kind/friend`` asks to become a friend: a member whose term is current
becomes one the day after it runs out, and one with no current term becomes one at
once.  The automatic renewal is canceled either way, and a contribution it carried can
be kept as a yearly recurring donation.  ``DELETE /me/kind/friend`` undoes a pending
change.  The API contract is ``docs/developer/api-profile.rst``.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest
from django.core import mail
from django.utils import timezone
from pytest_django.fixtures import DjangoCaptureOnCommitCallbacks
from rest_framework.test import APIClient

from apps.accounts.models import AccountKind, User
from apps.members.models import MembershipPlan, MembershipState
from apps.members.services import account_kind, membership_status
from apps.payments.models import MandateCadence, MandateStatus, RenewalMandate
from tests.conftest import audit_messages
from tests.factories import (
    MembershipFactory,
    RenewalMandateFactory,
    UserFactory,
    expire_membership,
    grant_membership,
)

pytestmark = pytest.mark.django_db

FRIEND_URL = "/api/v1/me/kind/friend"

LIFETIME_REFUSED = {"detail": "A lifetime member stays a member."}
NO_PENDING_CHANGE = {"detail": "You have no pending change."}
ALREADY_FRIEND = {"detail": "You are already a friend of CalDART."}
DONOR_REFUSED = {"detail": "A donor becomes a member or a friend only by registering."}
KEEP_REQUIRED = {"keep_contribution": ["This field is required."]}
DONATION_HELD = {
    "keep_contribution": ["You already have a recurring donation. Change it on the Donate screen."]
}

#: The contribution the renewal in these tests carries, in cents.
CONTRIBUTION = 2500


@pytest.fixture
def member_client(api_client: APIClient, member: User) -> APIClient:
    """An API client signed in as the plain member."""
    api_client.force_login(member)
    return api_client


@pytest.fixture
def current_member(member: User, annual_plan: MembershipPlan) -> User:
    """The plain member, holding a term that runs 200 more days."""
    grant_membership(member, annual_plan, days_left=200)
    return member


def renewal(user: User, plan: MembershipPlan, **fields: object) -> RenewalMandate:
    """An active automatic renewal of ``plan`` for ``user``, charged on its expiry.

    ``fields`` override the factory's, ``next_charge_on`` included.
    """
    expires_on = membership_status(user)["expires_on"]
    fields.setdefault("next_charge_on", expires_on or timezone.localdate())
    return RenewalMandateFactory(
        user=user,
        plan=plan,
        provider="stripe",
        customer_ref="cus_123",
        method_ref="pm_456",
        **fields,
    )


def become_friend(client: APIClient, **body: object) -> tuple[int, dict[str, Any]]:
    """Post ``body`` to ``POST /me/kind/friend`` and return the status and the JSON."""
    response = client.post(FRIEND_URL, body, format="json")
    return response.status_code, response.json()


def fresh(user: User) -> User:
    """``user`` as the database now holds it."""
    user.refresh_from_db()
    return user


# --------------------------------------------------------------------------
# POST /me/kind/friend: who may ask
# --------------------------------------------------------------------------
def test_an_anonymous_caller_cannot_become_a_friend(api_client: APIClient) -> None:
    """Somebody who is not signed in is a 401."""
    assert api_client.post(FRIEND_URL, {}, format="json").status_code == 401


def test_a_lifetime_member_is_refused(
    member_client: APIClient, member: User, life_plan: MembershipPlan
) -> None:
    """A life member stays a member: 400 with the sentence."""
    MembershipFactory(user=member, plan=life_plan, ends_on=None)
    assert become_friend(member_client) == (400, LIFETIME_REFUSED)


def test_a_refused_lifetime_member_keeps_their_kind(
    member_client: APIClient, member: User, life_plan: MembershipPlan
) -> None:
    """The refusal writes nothing: no pending date."""
    MembershipFactory(user=member, plan=life_plan, ends_on=None)
    become_friend(member_client)
    assert fresh(member).friend_on is None


def test_a_friend_is_told_they_already_are_one(api_client: APIClient, friend: User) -> None:
    """A friend asking again is a 400."""
    api_client.force_login(friend)
    assert become_friend(api_client) == (400, ALREADY_FRIEND)


def test_a_donor_is_refused(api_client: APIClient) -> None:
    """A donor never switches kinds by hand, even with a session."""
    donor = UserFactory(kind=AccountKind.DONOR, roles=[])
    api_client.force_login(donor)
    assert become_friend(api_client) == (400, DONOR_REFUSED)


# --------------------------------------------------------------------------
# A member with a current term
# --------------------------------------------------------------------------
def test_a_current_member_becomes_a_friend_the_day_after_the_term_ends(
    member_client: APIClient, current_member: User, today: date
) -> None:
    """``friend_on`` is the day after the membership runs out."""
    become_friend(member_client)
    assert fresh(current_member).friend_on == today + timedelta(days=201)


def test_the_answer_is_the_user_payload_with_the_pending_date(
    member_client: APIClient, current_member: User, today: date
) -> None:
    """The 200 carries the user payload, ``friend_on`` set and the kind still member."""
    status, body = become_friend(member_client)
    assert (status, body["kind"], body["friend_on"]) == (
        200,
        "member",
        str(today + timedelta(days=201)),
    )


def test_a_current_member_stays_current_until_then(
    member_client: APIClient, current_member: User
) -> None:
    """The membership is still current after asking."""
    become_friend(member_client)
    assert membership_status(fresh(current_member))["status"] == MembershipState.CURRENT


def test_the_date_follows_an_early_renewal(
    member_client: APIClient, current_member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """A renewal bought early carries the coverage on, and the change waits for it."""
    MembershipFactory(
        user=current_member,
        plan=annual_plan,
        starts_on=today + timedelta(days=201),
        ends_on=today + timedelta(days=565),
    )
    become_friend(member_client)
    assert fresh(current_member).friend_on == today + timedelta(days=566)


def test_a_pending_member_may_ask_again(
    member_client: APIClient, current_member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """Asking again while a change is pending works the date out afresh."""
    become_friend(member_client)
    MembershipFactory(
        user=current_member,
        plan=annual_plan,
        starts_on=today + timedelta(days=201),
        ends_on=today + timedelta(days=565),
    )
    status, body = become_friend(member_client)
    assert (status, body["friend_on"]) == (200, str(today + timedelta(days=566)))


def test_the_pending_friend_becomes_a_friend_on_the_day(
    member_client: APIClient, current_member: User, today: date
) -> None:
    """On ``friend_on`` the effective kind is friend."""
    become_friend(member_client)
    assert account_kind(fresh(current_member), today + timedelta(days=201)) == AccountKind.FRIEND


def test_the_change_is_audited_with_its_date(
    member_client: APIClient,
    current_member: User,
    today: date,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """One ``account.kind`` record names the new kind and the day it takes effect."""
    become_friend(member_client)
    assert audit_messages(audit_log) == [
        f"action=account.kind actor={current_member.pk} target={current_member.pk} "
        f"to=friend on={today + timedelta(days=201)}"
    ]


# --------------------------------------------------------------------------
# A member with no current term
# --------------------------------------------------------------------------
def test_an_expired_member_becomes_a_friend_at_once(
    member_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A member whose term ran out is stored as a friend straight away."""
    expire_membership(member, annual_plan)
    become_friend(member_client)
    assert (fresh(member).kind, member.friend_on) == (AccountKind.FRIEND, None)


def test_a_member_who_never_paid_becomes_a_friend_at_once(
    member_client: APIClient, member: User
) -> None:
    """A member with no term at all becomes a friend at once too."""
    status, body = become_friend(member_client)
    assert (status, body["kind"], body["membership"]["status"]) == (200, "friend", "friend")


def test_an_immediate_change_is_audited_with_today(
    member_client: APIClient, member: User, today: date, audit_log: pytest.LogCaptureFixture
) -> None:
    """The record's ``on`` is today."""
    become_friend(member_client)
    assert audit_messages(audit_log) == [
        f"action=account.kind actor={member.pk} target={member.pk} to=friend on={today}"
    ]


# --------------------------------------------------------------------------
# The automatic renewal
# --------------------------------------------------------------------------
def test_the_renewal_is_canceled(
    member_client: APIClient, current_member: User, annual_plan: MembershipPlan
) -> None:
    """The member's automatic renewal is canceled under their own name."""
    mandate = renewal(current_member, annual_plan)
    become_friend(member_client)
    mandate.refresh_from_db()
    assert (mandate.status, mandate.canceled_by) == (MandateStatus.CANCELED, current_member)


def test_an_expired_members_renewal_is_canceled_too(
    member_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A renewal still waiting to catch a lapsed term up is canceled with the change."""
    expire_membership(member, annual_plan, days_ago=5)
    mandate = renewal(member, annual_plan)
    become_friend(member_client)
    mandate.refresh_from_db()
    assert mandate.status == MandateStatus.CANCELED


def test_a_pending_renewal_is_thrown_away(
    member_client: APIClient, current_member: User, annual_plan: MembershipPlan
) -> None:
    """A renewal never confirmed is deleted rather than canceled."""
    renewal(current_member, annual_plan, status=MandateStatus.PENDING)
    become_friend(member_client)
    assert not RenewalMandate.objects.filter(user=current_member).exists()


def test_a_renewal_without_a_contribution_needs_no_answer(
    member_client: APIClient, current_member: User, annual_plan: MembershipPlan
) -> None:
    """``keep_contribution`` is not asked for when there is nothing to keep."""
    renewal(current_member, annual_plan)
    status, _ = become_friend(member_client)
    assert status == 200


def test_a_renewal_without_a_contribution_leaves_no_donation(
    member_client: APIClient, current_member: User, annual_plan: MembershipPlan
) -> None:
    """Keeping nothing creates nothing, whatever the body says."""
    renewal(current_member, annual_plan)
    become_friend(member_client, keep_contribution=True)
    assert not RenewalMandate.objects.filter(user=current_member, plan__isnull=True).exists()


def test_a_contribution_needs_an_answer(
    member_client: APIClient, current_member: User, annual_plan: MembershipPlan
) -> None:
    """A renewal that carries a contribution makes ``keep_contribution`` required."""
    renewal(current_member, annual_plan, contribution_cents=CONTRIBUTION)
    assert become_friend(member_client) == (400, KEEP_REQUIRED)


def test_an_unanswered_contribution_changes_nothing(
    member_client: APIClient, current_member: User, annual_plan: MembershipPlan
) -> None:
    """The refusal leaves the renewal on and the kind as it was."""
    mandate = renewal(current_member, annual_plan, contribution_cents=CONTRIBUTION)
    become_friend(member_client)
    mandate.refresh_from_db()
    assert (mandate.status, fresh(current_member).friend_on) == (MandateStatus.ACTIVE, None)


def test_stopping_the_contribution_leaves_no_donation(
    member_client: APIClient, current_member: User, annual_plan: MembershipPlan
) -> None:
    """``keep_contribution: false`` cancels the renewal and gives nothing more."""
    renewal(current_member, annual_plan, contribution_cents=CONTRIBUTION)
    become_friend(member_client, keep_contribution=False)
    assert not RenewalMandate.objects.filter(user=current_member, plan__isnull=True).exists()


def test_keeping_the_contribution_makes_a_yearly_recurring_donation(
    member_client: APIClient, current_member: User, annual_plan: MembershipPlan
) -> None:
    """The kept contribution is an active yearly donation for the same amount."""
    renewal(current_member, annual_plan, contribution_cents=CONTRIBUTION)
    become_friend(member_client, keep_contribution=True)
    donation = RenewalMandate.objects.get(user=current_member, plan__isnull=True)
    assert (donation.status, donation.cadence, donation.contribution_cents) == (
        MandateStatus.ACTIVE,
        MandateCadence.YEARLY,
        CONTRIBUTION,
    )


def test_the_kept_donation_is_first_charged_on_the_renewals_date(
    member_client: APIClient, current_member: User, annual_plan: MembershipPlan
) -> None:
    """The donation's first charge falls where the renewal's next one would have."""
    mandate = renewal(current_member, annual_plan, contribution_cents=CONTRIBUTION)
    become_friend(member_client, keep_contribution=True)
    donation = RenewalMandate.objects.get(user=current_member, plan__isnull=True)
    assert donation.next_charge_on == mandate.next_charge_on


def test_the_kept_donation_uses_the_renewals_saved_method(
    member_client: APIClient, current_member: User, annual_plan: MembershipPlan
) -> None:
    """The provider, the customer, and the card are the renewal's own."""
    renewal(current_member, annual_plan, contribution_cents=CONTRIBUTION)
    become_friend(member_client, keep_contribution=True)
    donation = RenewalMandate.objects.get(user=current_member, plan__isnull=True)
    assert (
        donation.provider,
        donation.customer_ref,
        donation.method_ref,
        donation.method_last4,
        donation.method_exp_year,
    ) == ("stripe", "cus_123", "pm_456", "4242", 2030)


def test_keeping_the_contribution_still_cancels_the_renewal(
    member_client: APIClient, current_member: User, annual_plan: MembershipPlan
) -> None:
    """The dues stop; only the contribution carries on."""
    mandate = renewal(current_member, annual_plan, contribution_cents=CONTRIBUTION)
    become_friend(member_client, keep_contribution=True)
    mandate.refresh_from_db()
    assert mandate.status == MandateStatus.CANCELED


def test_a_kept_contribution_reuses_a_canceled_donation(
    member_client: APIClient, current_member: User, annual_plan: MembershipPlan
) -> None:
    """A donation turned off long ago is the row that comes back on."""
    old = RenewalMandateFactory(
        user=current_member,
        plan=None,
        contribution_cents=1000,
        status=MandateStatus.CANCELED,
    )
    renewal(current_member, annual_plan, contribution_cents=CONTRIBUTION)
    become_friend(member_client, keep_contribution=True)
    old.refresh_from_db()
    assert (old.status, old.contribution_cents) == (MandateStatus.ACTIVE, CONTRIBUTION)


def test_keeping_the_contribution_emails_both_changes(
    member_client: APIClient,
    current_member: User,
    annual_plan: MembershipPlan,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    """The member hears that renewal is off and that the recurring donation is on."""
    renewal(current_member, annual_plan, contribution_cents=CONTRIBUTION)
    with django_capture_on_commit_callbacks(execute=True):
        become_friend(member_client, keep_contribution=True)
    assert sorted(message.subject for message in mail.outbox) == [
        "CalDART: automatic renewal is off",
        "CalDART: your recurring donation is on",
    ]


def test_keeping_beside_a_live_donation_is_refused(
    member_client: APIClient, current_member: User, annual_plan: MembershipPlan
) -> None:
    """A member who already gives by recurring donation cannot keep a second one."""
    RenewalMandateFactory(user=current_member, plan=None, contribution_cents=1000)
    renewal(current_member, annual_plan, contribution_cents=CONTRIBUTION)
    assert become_friend(member_client, keep_contribution=True) == (400, DONATION_HELD)


def test_a_refused_keep_changes_nothing(
    member_client: APIClient, current_member: User, annual_plan: MembershipPlan
) -> None:
    """The refusal leaves the renewal on, the donation as it was, and the kind alone."""
    held = RenewalMandateFactory(user=current_member, plan=None, contribution_cents=1000)
    mandate = renewal(current_member, annual_plan, contribution_cents=CONTRIBUTION)
    become_friend(member_client, keep_contribution=True)
    mandate.refresh_from_db()
    held.refresh_from_db()
    assert (mandate.status, held.contribution_cents, fresh(current_member).friend_on) == (
        MandateStatus.ACTIVE,
        1000,
        None,
    )


def test_a_kept_contribution_from_a_lapsed_renewal_is_first_charged_today(
    member_client: APIClient, member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """A renewal whose charge day has gone by gives a donation first charged today."""
    expire_membership(member, annual_plan, days_ago=5)
    renewal(
        member,
        annual_plan,
        contribution_cents=CONTRIBUTION,
        next_charge_on=today - timedelta(days=5),
    )
    become_friend(member_client, keep_contribution=True)
    donation = RenewalMandate.objects.get(user=member, plan__isnull=True)
    assert donation.next_charge_on == today


def test_a_paused_renewals_contribution_needs_no_answer(
    member_client: APIClient, current_member: User, annual_plan: MembershipPlan
) -> None:
    """A paused renewal's contribution is not offered, so no answer is asked for."""
    renewal(
        current_member,
        annual_plan,
        contribution_cents=CONTRIBUTION,
        status=MandateStatus.PAUSED,
    )
    status, _ = become_friend(member_client)
    assert status == 200


def test_a_paused_renewal_is_canceled_and_leaves_no_donation(
    member_client: APIClient, current_member: User, annual_plan: MembershipPlan
) -> None:
    """A paused renewal is canceled and its contribution stops, whatever the body says."""
    mandate = renewal(
        current_member,
        annual_plan,
        contribution_cents=CONTRIBUTION,
        status=MandateStatus.PAUSED,
    )
    become_friend(member_client, keep_contribution=True)
    mandate.refresh_from_db()
    assert (
        mandate.status,
        RenewalMandate.objects.filter(user=current_member, plan__isnull=True).exists(),
    ) == (MandateStatus.CANCELED, False)


# --------------------------------------------------------------------------
# DELETE /me/kind/friend: the Undo
# --------------------------------------------------------------------------
def test_an_anonymous_caller_cannot_undo(api_client: APIClient) -> None:
    """Somebody who is not signed in is a 401."""
    assert api_client.delete(FRIEND_URL).status_code == 401


def test_undo_clears_the_pending_date(
    member_client: APIClient, current_member: User, today: date
) -> None:
    """The member stays a member with nothing pending, and the payload says so."""
    current_member.friend_on = today + timedelta(days=201)
    current_member.save(update_fields=["friend_on"])
    response = member_client.delete(FRIEND_URL)
    assert (
        response.status_code,
        response.json()["friend_on"],
        fresh(current_member).friend_on,
    ) == (
        200,
        None,
        None,
    )


def test_undo_restores_no_canceled_renewal(
    member_client: APIClient, current_member: User, annual_plan: MembershipPlan
) -> None:
    """The renewal the change canceled stays canceled."""
    mandate = renewal(current_member, annual_plan)
    become_friend(member_client)
    member_client.delete(FRIEND_URL)
    mandate.refresh_from_db()
    assert mandate.status == MandateStatus.CANCELED


def test_undo_is_audited(
    member_client: APIClient,
    current_member: User,
    today: date,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """One ``account.kind`` record says the member stays a member."""
    current_member.friend_on = today + timedelta(days=201)
    current_member.save(update_fields=["friend_on"])
    member_client.delete(FRIEND_URL)
    assert audit_messages(audit_log) == [
        f"action=account.kind actor={current_member.pk} target={current_member.pk} "
        "to=member undo=true"
    ]


def test_undo_without_a_pending_change_is_refused(member_client: APIClient) -> None:
    """Nothing pending is a 400."""
    response = member_client.delete(FRIEND_URL)
    assert (response.status_code, response.json()) == (400, NO_PENDING_CHANGE)


def test_undo_after_the_day_has_come_is_refused(
    member_client: APIClient, member: User, today: date
) -> None:
    """A change whose day has come is not pending, even before it is written down."""
    member.friend_on = today
    member.save(update_fields=["friend_on"])
    response = member_client.delete(FRIEND_URL)
    assert (response.status_code, response.json()) == (400, NO_PENDING_CHANGE)


def test_undo_for_a_friend_is_refused(api_client: APIClient, friend: User) -> None:
    """A friend has nothing pending to undo."""
    api_client.force_login(friend)
    response = api_client.delete(FRIEND_URL)
    assert (response.status_code, response.json()) == (400, NO_PENDING_CHANGE)
