"""An administrator's account actions: make a friend, deactivate, reactivate.

The member record's danger zone offers an account administrator
``POST /admin/members/{id}/friend``, ``/deactivate`` and ``/reactivate``; the user
record offers a user administrator ``POST /admin/users/{id}/deactivate`` and
``/reactivate``.  Each does what the person's own switch or deactivation does, with
the administrator recorded as the actor, and the active flag is no longer part of an
edit.  The API contracts are ``docs/developer/api-members.rst`` and
``docs/developer/api-auth.rst``.
"""

from __future__ import annotations

from datetime import timedelta
from importlib import import_module
from typing import Any

import pytest
from django.conf import settings
from django.contrib.sessions.models import Session
from django.utils import timezone
from pytest_django.fixtures import DjangoCaptureOnCommitCallbacks
from rest_framework.test import APIClient

from apps.accounts.models import AccountKind, User
from apps.accounts.roles import ACCOUNT_ADMIN, SYSTEM_ADMIN, USER_ADMIN
from apps.members.models import MembershipPlan, MembershipStatusChoices
from apps.members.services import membership_status
from apps.payments.models import MandateStatus, RenewalMandate
from tests.conftest import RecordedEvents, audit_messages, role_matrix
from tests.factories import (
    MembershipFactory,
    RenewalMandateFactory,
    UserFactory,
    grant_membership,
)

pytestmark = pytest.mark.django_db

#: The contribution the renewals in these tests carry, in cents.
CONTRIBUTION = 2500

SELF_REFUSED = {"detail": "You cannot deactivate your own account."}
ROLES_REFUSED = {
    "detail": "You cannot activate or deactivate an account that holds roles you do not hold."
}
DONOR_DEACTIVATE_REFUSED = {"detail": "A donor has no portal account to deactivate."}
DONOR_REACTIVATE_REFUSED = {"detail": "A donor has no portal account to reactivate."}
ALREADY_DEACTIVATED = {"detail": "That account is already deactivated."}
ALREADY_ACTIVE = {"detail": "That account is already active."}
KEEP_REQUIRED = {"keep_contribution": ["This field is required."]}
DONATION_HELD = {
    "keep_contribution": [
        "They already have a recurring donation, so the contribution cannot be kept as one."
    ]
}
ALREADY_FRIEND = {"detail": "You are already a friend of CalDART."}
LIFETIME_REFUSED = {"detail": "A lifetime member stays a member."}


def member_url(user: User, action: str) -> str:
    """The member record's ``action`` endpoint for ``user``."""
    return f"/api/v1/admin/members/{user.pk}/{action}"


def user_url(user: User, action: str) -> str:
    """The user record's ``action`` endpoint for ``user``."""
    return f"/api/v1/admin/users/{user.pk}/{action}"


def post(client: APIClient, url: str, **body: object) -> tuple[int, dict[str, Any]]:
    """Post ``body`` to ``url`` and return the status and the JSON."""
    response = client.post(url, body, format="json")
    return response.status_code, response.json()


def fresh(user: User) -> User:
    """``user`` as the database now holds it."""
    user.refresh_from_db()
    return user


def deactivated(user: User) -> User:
    """``user`` with the account's active flag cleared."""
    user.is_active = False
    user.save(update_fields=["is_active"])
    return user


def signed_in_session(user: User) -> str:
    """Store a database session signed in to ``user`` and return its key."""
    store = import_module(settings.SESSION_ENGINE).SessionStore()
    store["_auth_user_id"] = str(user.pk)
    store["_auth_user_backend"] = "django.contrib.auth.backends.ModelBackend"
    store["_auth_user_hash"] = user.get_session_auth_hash()
    store.create()
    key: str = store.session_key
    return key


@pytest.fixture
def user_admin_client(api_client: APIClient, user_admin: User) -> APIClient:
    """An API client signed in as the user administrator."""
    api_client.force_login(user_admin)
    return api_client


@pytest.fixture
def target(db: None) -> User:
    """A plain member the administrators act on."""
    return UserFactory(email="target@example.test", first_name="Tess", last_name="Arden")


def renewal(user: User, plan: MembershipPlan, **fields: object) -> RenewalMandate:
    """An active automatic renewal of ``plan`` for ``user``, charged on its expiry."""
    expires_on = membership_status(user)["expires_on"]
    fields.setdefault("next_charge_on", expires_on or timezone.localdate())
    return RenewalMandateFactory(
        user=user, plan=plan, provider="stripe", customer_ref="cus_1", method_ref="pm_1", **fields
    )


# --------------------------------------------------------------------------
# Who may call
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("role", "allowed"), role_matrix(ACCOUNT_ADMIN, SYSTEM_ADMIN))
def test_only_an_account_administrator_deactivates_from_the_member_record(
    api_client: APIClient,
    all_role_users: dict[str, User],
    target: User,
    role: str,
    allowed: bool,
) -> None:
    """The member record's deactivation admits the account administrator alone."""
    api_client.force_login(all_role_users[role])
    status, _ = post(api_client, member_url(target, "deactivate"))
    assert status == (200 if allowed else 403)


@pytest.mark.parametrize(("role", "allowed"), role_matrix(ACCOUNT_ADMIN, SYSTEM_ADMIN))
def test_only_an_account_administrator_makes_a_friend(
    api_client: APIClient,
    all_role_users: dict[str, User],
    target: User,
    role: str,
    allowed: bool,
) -> None:
    """The member record's switch to friend admits the account administrator alone."""
    api_client.force_login(all_role_users[role])
    status, _ = post(api_client, member_url(target, "friend"))
    assert status == (200 if allowed else 403)


@pytest.mark.parametrize(("role", "allowed"), role_matrix(USER_ADMIN, SYSTEM_ADMIN))
def test_only_a_user_administrator_deactivates_from_the_user_record(
    api_client: APIClient,
    all_role_users: dict[str, User],
    target: User,
    role: str,
    allowed: bool,
) -> None:
    """The user record's deactivation admits the user administrator alone."""
    api_client.force_login(all_role_users[role])
    status, _ = post(api_client, user_url(target, "deactivate"))
    assert status == (200 if allowed else 403)


@pytest.mark.parametrize(("role", "allowed"), role_matrix(USER_ADMIN, SYSTEM_ADMIN))
def test_only_a_user_administrator_reactivates_from_the_user_record(
    api_client: APIClient,
    all_role_users: dict[str, User],
    target: User,
    role: str,
    allowed: bool,
) -> None:
    """The user record's reactivation admits the user administrator alone."""
    deactivated(target)
    api_client.force_login(all_role_users[role])
    status, _ = post(api_client, user_url(target, "reactivate"))
    assert status == (200 if allowed else 403)


def test_an_anonymous_caller_cannot_deactivate(api_client: APIClient, target: User) -> None:
    """Somebody who is not signed in is a 401."""
    status, _ = post(api_client, member_url(target, "deactivate"))
    assert status == 401


def test_an_unknown_member_is_a_404(account_admin_client: APIClient) -> None:
    """No account has that id."""
    response = account_admin_client.post("/api/v1/admin/members/999999/deactivate")
    assert response.status_code == 404


# --------------------------------------------------------------------------
# Deactivating
# --------------------------------------------------------------------------
def test_deactivating_answers_the_member_record(
    account_admin_client: APIClient, target: User
) -> None:
    """The answer is the member record, showing the account inactive."""
    status, body = post(account_admin_client, member_url(target, "deactivate"))
    assert (status, body["id"], body["is_active"]) == (200, target.pk, False)


def test_deactivating_clears_the_active_flag(account_admin_client: APIClient, target: User) -> None:
    """The account cannot sign in afterwards."""
    post(account_admin_client, member_url(target, "deactivate"))
    assert fresh(target).is_active is False


def test_deactivating_suspends_the_membership(
    account_admin_client: APIClient,
    account_admin: User,
    target: User,
    annual_plan: MembershipPlan,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """The term with time left is suspended, recorded under the administrator."""
    covering = grant_membership(target, annual_plan)
    post(account_admin_client, member_url(target, "deactivate"))
    assert (
        f"action=membership.correct actor={account_admin.pk} target={covering.pk} "
        "status=suspended" in audit_messages(audit_log)
    )


def test_deactivating_cancels_the_renewal_under_the_administrator(
    account_admin_client: APIClient,
    account_admin: User,
    target: User,
    annual_plan: MembershipPlan,
) -> None:
    """Automatic renewal is turned off, signed for by the administrator."""
    mandate = RenewalMandateFactory(user=target, plan=annual_plan)
    post(account_admin_client, member_url(target, "deactivate"))
    mandate.refresh_from_db()
    assert (mandate.status, mandate.canceled_by_id) == (MandateStatus.CANCELED, account_admin.pk)


def test_deactivating_cancels_a_recurring_donation(
    account_admin_client: APIClient, target: User
) -> None:
    """A recurring donation is withdrawn too."""
    donation = RenewalMandateFactory(user=target, plan=None, contribution_cents=CONTRIBUTION)
    post(account_admin_client, member_url(target, "deactivate"))
    donation.refresh_from_db()
    assert donation.status == MandateStatus.CANCELED


def test_deactivating_ends_every_session_of_the_account(
    account_admin_client: APIClient, target: User
) -> None:
    """A session signed in to the account is deleted."""
    key = signed_in_session(target)
    post(account_admin_client, member_url(target, "deactivate"))
    assert Session.objects.filter(session_key=key).exists() is False


def test_deactivating_leaves_other_sessions_alone(
    account_admin_client: APIClient, target: User, member: User
) -> None:
    """Somebody else's session survives."""
    key = signed_in_session(member)
    post(account_admin_client, member_url(target, "deactivate"))
    assert Session.objects.filter(session_key=key).exists() is True


def test_deactivating_is_recorded_under_the_administrator(
    account_admin_client: APIClient,
    account_admin: User,
    target: User,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """``account.deactivate`` names the administrator as actor."""
    post(account_admin_client, member_url(target, "deactivate"))
    assert f"action=account.deactivate actor={account_admin.pk} target={target.pk}" in (
        audit_messages(audit_log)
    )


def test_deactivating_raises_the_event_naming_the_administrator(
    account_admin_client: APIClient,
    account_admin: User,
    target: User,
    recorded_events: RecordedEvents,
) -> None:
    """``account_deactivated`` carries the administrator as its actor."""
    post(account_admin_client, member_url(target, "deactivate"))
    assert ("account_deactivated", {"user": target, "actor": account_admin}) in recorded_events


def test_deactivating_keeps_the_kind_and_the_roles(
    account_admin_client: APIClient, friend: User
) -> None:
    """A friend stays a friend holding the member role, only inactive."""
    post(account_admin_client, member_url(friend, "deactivate"))
    friend = fresh(friend)
    assert (friend.kind, friend.roles) == (AccountKind.FRIEND, ["member"])


def test_an_administrator_cannot_deactivate_themselves(
    account_admin_client: APIClient, account_admin: User
) -> None:
    """Your own account is refused with a sentence."""
    assert post(account_admin_client, member_url(account_admin, "deactivate")) == (
        400,
        SELF_REFUSED,
    )


def test_deactivating_yourself_is_recorded(
    account_admin_client: APIClient,
    account_admin: User,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """The refusal is written with the ``self_deactivation`` reason."""
    post(account_admin_client, member_url(account_admin, "deactivate"))
    assert audit_messages(audit_log) == [
        f"action=account.deactivate actor={account_admin.pk} target={account_admin.pk} "
        "reason=self_deactivation"
    ]


@pytest.mark.parametrize("fixture", ["user_admin", "system_admin", "superuser"])
def test_an_account_holding_roles_you_lack_is_refused(
    account_admin_client: APIClient, request: pytest.FixtureRequest, fixture: str
) -> None:
    """A user or system administrator's account is beyond an account administrator."""
    other: User = request.getfixturevalue(fixture)
    assert post(account_admin_client, member_url(other, "deactivate")) == (400, ROLES_REFUSED)


def test_a_refused_deactivation_changes_nothing(
    account_admin_client: APIClient, user_admin: User
) -> None:
    """The guarded account stays active."""
    post(account_admin_client, member_url(user_admin, "deactivate"))
    assert fresh(user_admin).is_active is True


def test_a_refused_deactivation_is_recorded(
    account_admin_client: APIClient,
    account_admin: User,
    user_admin: User,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """The refusal is written with the ``roles_not_held`` reason."""
    post(account_admin_client, member_url(user_admin, "deactivate"))
    assert audit_messages(audit_log) == [
        f"action=account.deactivate actor={account_admin.pk} target={user_admin.pk} "
        "reason=roles_not_held"
    ]


def test_a_system_administrator_may_deactivate_another(
    system_admin_client: APIClient,
) -> None:
    """A system administrator holds every role, so another one is within reach."""
    other = UserFactory(email="root2@example.test", roles=[SYSTEM_ADMIN])
    status, body = post(system_admin_client, member_url(other, "deactivate"))
    assert (status, body["is_active"]) == (200, False)


def test_a_donor_cannot_be_deactivated(account_admin_client: APIClient) -> None:
    """A donor has no portal account."""
    giver = UserFactory(email="giver@example.test", kind=AccountKind.DONOR, roles=[])
    assert post(account_admin_client, member_url(giver, "deactivate")) == (
        400,
        DONOR_DEACTIVATE_REFUSED,
    )


def test_deactivating_twice_is_refused(account_admin_client: APIClient, target: User) -> None:
    """An account already deactivated is told so."""
    deactivated(target)
    assert post(account_admin_client, member_url(target, "deactivate")) == (
        400,
        ALREADY_DEACTIVATED,
    )


def test_the_user_record_deactivates_as_the_member_record_does(
    user_admin_client: APIClient, user_admin: User, target: User, annual_plan: MembershipPlan
) -> None:
    """The user administrator's deactivation also suspends the membership."""
    covering = grant_membership(target, annual_plan)
    post(user_admin_client, user_url(target, "deactivate"))
    covering.refresh_from_db()
    assert covering.status == MembershipStatusChoices.SUSPENDED


def test_the_user_record_answers_its_own_payload(
    user_admin_client: APIClient, target: User
) -> None:
    """The answer is the user record, with the flag and the block."""
    status, body = post(user_admin_client, user_url(target, "deactivate"))
    assert (status, body["is_active"], body["reactivation_blocked"]) == (200, False, False)


# --------------------------------------------------------------------------
# The active flag is not an edit
# --------------------------------------------------------------------------
def test_a_member_record_edit_ignores_the_active_flag(
    account_admin_client: APIClient, target: User
) -> None:
    """``is_active`` in a ``PATCH`` is not a field the edit accepts."""
    response = account_admin_client.patch(
        f"/api/v1/admin/members/{target.pk}", {"is_active": False}, format="json"
    )
    assert response.status_code == 200
    assert fresh(target).is_active is True


def test_a_user_record_edit_ignores_the_active_flag(
    user_admin_client: APIClient, target: User
) -> None:
    """``is_active`` is read-only on ``/admin/users/{id}``."""
    response = user_admin_client.patch(
        f"/api/v1/admin/users/{target.pk}", {"is_active": False}, format="json"
    )
    assert response.status_code == 200
    assert fresh(target).is_active is True


# --------------------------------------------------------------------------
# Reactivating
# --------------------------------------------------------------------------
def test_reactivating_answers_the_member_record(
    account_admin_client: APIClient, target: User
) -> None:
    """The answer is the member record, showing the account active."""
    deactivated(target)
    status, body = post(account_admin_client, member_url(target, "reactivate"))
    assert (status, body["is_active"]) == (200, True)


def test_reactivating_restores_a_suspended_term(
    account_admin_client: APIClient, target: User, annual_plan: MembershipPlan
) -> None:
    """A suspended term with time left is active again."""
    deactivated(target)
    held = MembershipFactory(
        user=target,
        plan=annual_plan,
        starts_on=timezone.localdate(),
        ends_on=None,
        status=MembershipStatusChoices.SUSPENDED,
    )
    post(account_admin_client, member_url(target, "reactivate"))
    held.refresh_from_db()
    assert held.status == MembershipStatusChoices.ACTIVE


def test_reactivating_is_recorded_under_the_administrator(
    account_admin_client: APIClient,
    account_admin: User,
    target: User,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """``account.activate`` names the administrator as actor."""
    deactivated(target)
    post(account_admin_client, member_url(target, "reactivate"))
    assert f"action=account.activate actor={account_admin.pk} target={target.pk}" in (
        audit_messages(audit_log)
    )


def test_reactivating_raises_the_event_naming_the_administrator(
    account_admin_client: APIClient,
    account_admin: User,
    target: User,
    recorded_events: RecordedEvents,
) -> None:
    """``account_reactivated`` carries the administrator as its actor."""
    deactivated(target)
    post(account_admin_client, member_url(target, "reactivate"))
    assert ("account_reactivated", {"user": target, "actor": account_admin}) in recorded_events


def test_reactivating_an_unverified_account_mails_a_link(
    account_admin_client: APIClient,
    target: User,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    mailoutbox: list[Any],
) -> None:
    """An address never verified is mailed a link, as the owner's reactivation does."""
    target.email_verified_at = None
    target.save(update_fields=["email_verified_at"])
    deactivated(target)
    with django_capture_on_commit_callbacks(execute=True):
        post(account_admin_client, member_url(target, "reactivate"))
    assert [message.to for message in mailoutbox] == [[target.email]]


def test_reactivating_an_active_account_is_refused(
    account_admin_client: APIClient, target: User
) -> None:
    """An account already active is told so."""
    assert post(account_admin_client, member_url(target, "reactivate")) == (400, ALREADY_ACTIVE)


def test_reactivating_an_account_holding_roles_you_lack_is_refused(
    account_admin_client: APIClient, user_admin: User
) -> None:
    """The same guard holds in this direction."""
    deactivated(user_admin)
    assert post(account_admin_client, member_url(user_admin, "reactivate")) == (
        400,
        ROLES_REFUSED,
    )


def test_a_donor_cannot_be_reactivated(account_admin_client: APIClient) -> None:
    """A donor has no portal account, even a deactivated one."""
    giver = UserFactory(email="giver@example.test", kind=AccountKind.DONOR, roles=[])
    deactivated(giver)
    assert post(account_admin_client, member_url(giver, "reactivate")) == (
        400,
        DONOR_REACTIVATE_REFUSED,
    )


# --------------------------------------------------------------------------
# Making a friend
# --------------------------------------------------------------------------
def test_a_member_with_nothing_current_becomes_a_friend_at_once(
    account_admin_client: APIClient, target: User
) -> None:
    """The answer is the member record, the kind now friend."""
    status, body = post(account_admin_client, member_url(target, "friend"))
    assert (status, body["kind"]) == (200, AccountKind.FRIEND)


def test_a_current_member_becomes_a_friend_the_day_after(
    account_admin_client: APIClient, target: User, annual_plan: MembershipPlan
) -> None:
    """The membership is kept to its end, as the person's own switch keeps it."""
    term = grant_membership(target, annual_plan)
    post(account_admin_client, member_url(target, "friend"))
    assert term.ends_on is not None
    assert fresh(target).friend_on == term.ends_on + timedelta(days=1)


def test_making_a_friend_is_recorded_under_the_administrator(
    account_admin_client: APIClient,
    account_admin: User,
    target: User,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """``account.kind`` names the administrator as actor."""
    post(account_admin_client, member_url(target, "friend"))
    assert (
        f"action=account.kind actor={account_admin.pk} target={target.pk} to=friend "
        f"on={timezone.localdate()}" in audit_messages(audit_log)
    )


def test_making_a_friend_says_an_administrator_did_it(
    account_admin_client: APIClient, target: User, recorded_events: RecordedEvents
) -> None:
    """``became_friend`` is raised with ``how="administrator"``."""
    post(account_admin_client, member_url(target, "friend"))
    assert ("became_friend", {"user": target, "how": "administrator"}) in recorded_events


def test_making_a_friend_cancels_the_renewal_under_the_administrator(
    account_admin_client: APIClient,
    account_admin: User,
    target: User,
    annual_plan: MembershipPlan,
) -> None:
    """The automatic renewal ends, signed for by the administrator."""
    grant_membership(target, annual_plan)
    mandate = renewal(target, annual_plan)
    post(account_admin_client, member_url(target, "friend"))
    mandate.refresh_from_db()
    assert (mandate.status, mandate.canceled_by_id) == (MandateStatus.CANCELED, account_admin.pk)


def test_a_contribution_needs_an_answer(
    account_admin_client: APIClient, target: User, annual_plan: MembershipPlan
) -> None:
    """A renewal carrying a contribution makes ``keep_contribution`` required."""
    grant_membership(target, annual_plan)
    renewal(target, annual_plan, contribution_cents=CONTRIBUTION)
    assert post(account_admin_client, member_url(target, "friend")) == (400, KEEP_REQUIRED)


def test_keeping_the_contribution_makes_a_recurring_donation(
    account_admin_client: APIClient, target: User, annual_plan: MembershipPlan
) -> None:
    """``keep_contribution: true`` carries the contribution on as a donation."""
    grant_membership(target, annual_plan)
    renewal(target, annual_plan, contribution_cents=CONTRIBUTION)
    post(account_admin_client, member_url(target, "friend"), keep_contribution=True)
    donation = RenewalMandate.objects.get(user=target, plan__isnull=True)
    assert (donation.status, donation.contribution_cents) == (MandateStatus.ACTIVE, CONTRIBUTION)


def test_keeping_beside_a_held_donation_is_refused_in_the_administrators_words(
    account_admin_client: APIClient, target: User, annual_plan: MembershipPlan
) -> None:
    """The refusal talks about the member, not to them."""
    grant_membership(target, annual_plan)
    renewal(target, annual_plan, contribution_cents=CONTRIBUTION)
    RenewalMandateFactory(
        user=target, plan=None, contribution_cents=1000, status=MandateStatus.PAUSED
    )
    assert post(account_admin_client, member_url(target, "friend"), keep_contribution=True) == (
        400,
        DONATION_HELD,
    )


def test_a_friend_cannot_be_made_a_friend(account_admin_client: APIClient, friend: User) -> None:
    """The refusal is drawn as the person's own switch draws it."""
    assert post(account_admin_client, member_url(friend, "friend")) == (400, ALREADY_FRIEND)


def test_a_life_member_cannot_be_made_a_friend(
    account_admin_client: APIClient, target: User, life_plan: MembershipPlan
) -> None:
    """A current life member stays a member."""
    MembershipFactory(user=target, plan=life_plan, ends_on=None)
    assert post(account_admin_client, member_url(target, "friend")) == (400, LIFETIME_REFUSED)
