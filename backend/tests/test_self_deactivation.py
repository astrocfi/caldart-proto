"""Deactivating your own account, and coming back.

``POST /auth/deactivate`` ends the caller's own account: every mandate is canceled,
the membership that still has time to run is suspended, and the session ends.
``POST /auth/reactivate`` brings a deactivated account back with its password, and
so does a password reset.  A suspended term counts for nothing while it is
suspended.  The API contract is ``docs/developer/api-auth.rst``.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.core.mail import EmailMessage
from django.utils import timezone
from pytest_django.fixtures import DjangoCaptureOnCommitCallbacks
from rest_framework.test import APIClient

from apps.accounts.api.views import deactivate as deactivate_account
from apps.accounts.api.views import reactivate as reactivate_account
from apps.accounts.models import AccountKind, User
from apps.accounts.services import make_reset_token
from apps.members.models import (
    Membership,
    MembershipPlan,
    MembershipState,
    MembershipStatusChoices,
)
from apps.members.services import membership_status, with_membership
from apps.payments.models import MandateStatus, RenewalMandate
from tests.conftest import GOOD_PASSWORD, LOGIN_URL, ME_URL, RESET_CONFIRM_URL, audit_messages
from tests.factories import MembershipFactory, RenewalMandateFactory, UserFactory

pytestmark = pytest.mark.django_db

DEACTIVATE_URL = "/api/v1/auth/deactivate"
REACTIVATE_URL = "/api/v1/auth/reactivate"

WRONG_CREDENTIALS = {"detail": "Incorrect email address or password."}
SYSTEM_ADMIN_REFUSED = {"detail": "A system administrator cannot deactivate their own account."}
DONOR_REFUSED = {"detail": "A donor has no portal account to deactivate."}

type OnCommit = DjangoCaptureOnCommitCallbacks


def term(user: User, plan: MembershipPlan, *, starts: int, ends: int | None) -> Membership:
    """An active term for ``user`` from ``starts`` days after today to ``ends`` days.

    Negative offsets are in the past; ``ends=None`` is a lifetime term.
    """
    today = timezone.localdate()
    return MembershipFactory(
        user=user,
        plan=plan,
        starts_on=today + timedelta(days=starts),
        ends_on=None if ends is None else today + timedelta(days=ends),
    )


def suspended(user: User, plan: MembershipPlan, *, ends_on: date | None) -> Membership:
    """A suspended term for ``user`` ending on ``ends_on`` (``None`` for lifetime)."""
    return MembershipFactory(
        user=user,
        plan=plan,
        starts_on=timezone.localdate() - timedelta(days=400),
        ends_on=ends_on,
        status=MembershipStatusChoices.SUSPENDED,
    )


def deactivated(user: User) -> User:
    """``user`` with the account's active flag cleared, as deactivation leaves it."""
    user.is_active = False
    user.save(update_fields=["is_active"])
    return user


@pytest.fixture
def member_client(api_client: APIClient, member: User) -> APIClient:
    """An API client signed in as the plain member."""
    api_client.force_login(member)
    return api_client


def deactivate(client: APIClient, password: str) -> int:
    """Post the deactivation with ``password`` and return the status code."""
    return client.post(DEACTIVATE_URL, {"current_password": password}, format="json").status_code


# --------------------------------------------------------------------------
# POST /auth/deactivate
# --------------------------------------------------------------------------
def test_an_anonymous_caller_cannot_deactivate(api_client: APIClient, password: str) -> None:
    """Somebody who is not signed in is a 401."""
    assert deactivate(api_client, password) == 401


def test_deactivating_answers_204(member_client: APIClient, password: str) -> None:
    """The right password deactivates the account with an empty 204."""
    assert deactivate(member_client, password) == 204


def test_deactivating_clears_the_active_flag(
    member_client: APIClient, member: User, password: str
) -> None:
    """The account is inactive afterwards."""
    deactivate(member_client, password)
    member.refresh_from_db()
    assert member.is_active is False


def test_deactivating_ends_the_session(member_client: APIClient, password: str) -> None:
    """The caller is signed out: ``/auth/me`` is a 401 on the same client."""
    deactivate(member_client, password)
    assert member_client.get(ME_URL).status_code == 401


def test_deactivating_keeps_the_kind_and_the_roles(
    api_client: APIClient, friend: User, password: str
) -> None:
    """A friend stays a friend holding the member role, only inactive."""
    api_client.force_login(friend)
    deactivate(api_client, password)
    friend.refresh_from_db()
    assert (friend.kind, friend.roles) == (AccountKind.FRIEND, ["member"])


def test_a_wrong_password_is_refused(member_client: APIClient, member: User) -> None:
    """A wrong current password is a 400 on ``current_password``."""
    response = member_client.post(
        DEACTIVATE_URL, {"current_password": "not-the-password"}, format="json"
    )
    assert response.status_code == 400
    assert response.json() == {"current_password": ["That is not your current password."]}


def test_a_wrong_password_leaves_the_account_active(member_client: APIClient, member: User) -> None:
    """A refused deactivation changes nothing."""
    deactivate(member_client, "not-the-password")
    member.refresh_from_db()
    assert member.is_active is True


def test_a_missing_password_is_refused(member_client: APIClient) -> None:
    """The current password is required."""
    response = member_client.post(DEACTIVATE_URL, {}, format="json")
    assert response.json() == {"current_password": ["This field is required."]}


@pytest.mark.parametrize("fixture", ["system_admin", "superuser"])
def test_a_system_administrator_cannot_deactivate_themselves(
    api_client: APIClient, request: pytest.FixtureRequest, password: str, fixture: str
) -> None:
    """The system_admin role, or a Django superuser, is refused with a sentence."""
    admin: User = request.getfixturevalue(fixture)
    api_client.force_login(admin)
    response = api_client.post(DEACTIVATE_URL, {"current_password": password}, format="json")
    assert response.status_code == 400
    assert response.json() == SYSTEM_ADMIN_REFUSED


def test_a_refused_system_administrator_stays_active(
    api_client: APIClient, system_admin: User, password: str
) -> None:
    """The refusal leaves the account as it was."""
    api_client.force_login(system_admin)
    deactivate(api_client, password)
    system_admin.refresh_from_db()
    assert system_admin.is_active is True


@pytest.fixture
def donor(api_client: APIClient) -> User:
    """A donor, somehow holding the usual password, signed in on ``api_client``."""
    giver: User = UserFactory(email="giver@example.test", kind=AccountKind.DONOR)
    api_client.force_login(giver)
    return giver


def test_a_donor_cannot_deactivate(api_client: APIClient, donor: User, password: str) -> None:
    """A donor has no portal account, so is refused with a sentence."""
    response = api_client.post(DEACTIVATE_URL, {"current_password": password}, format="json")
    assert (response.status_code, response.json()) == (400, DONOR_REFUSED)


def test_a_refused_donor_stays_active(api_client: APIClient, donor: User, password: str) -> None:
    """The refusal leaves the donor's account as it was."""
    deactivate(api_client, password)
    donor.refresh_from_db()
    assert donor.is_active is True


def test_a_refused_donor_is_recorded(
    api_client: APIClient, donor: User, password: str, audit_log: pytest.LogCaptureFixture
) -> None:
    """The refusal is written to the audit log with the ``donor_account`` reason."""
    deactivate(api_client, password)
    assert audit_messages(audit_log) == [
        f"action=account.deactivate actor={donor.pk} target={donor.pk} reason=donor_account"
    ]


def test_deactivating_is_recorded_as_self_service(
    member_client: APIClient,
    member: User,
    password: str,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """``account.deactivate`` names the member as both actor and target."""
    deactivate(member_client, password)
    assert (
        f"action=account.deactivate actor={member.pk} target={member.pk} self_service=true"
        in audit_messages(audit_log)
    )


def test_a_refused_system_administrator_is_recorded(
    api_client: APIClient,
    system_admin: User,
    password: str,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """The refusal is written to the audit log at warning."""
    api_client.force_login(system_admin)
    deactivate(api_client, password)
    assert audit_messages(audit_log) == [
        f"action=account.deactivate actor={system_admin.pk} target={system_admin.pk} "
        "reason=system_admin_target"
    ]


# -- the membership --------------------------------------------------------
def test_deactivating_suspends_the_covering_term(
    member_client: APIClient, member: User, annual_plan: MembershipPlan, password: str
) -> None:
    """The term covering today is suspended."""
    covering = term(member, annual_plan, starts=-30, ends=200)
    deactivate(member_client, password)
    covering.refresh_from_db()
    assert covering.status == MembershipStatusChoices.SUSPENDED


def test_deactivating_suspends_a_lifetime_term(
    member_client: APIClient, member: User, life_plan: MembershipPlan, password: str
) -> None:
    """A lifetime term is suspended like any other."""
    lifetime = term(member, life_plan, starts=-30, ends=None)
    deactivate(member_client, password)
    lifetime.refresh_from_db()
    assert lifetime.status == MembershipStatusChoices.SUSPENDED


def test_deactivating_suspends_a_renewal_that_has_not_started(
    member_client: APIClient, member: User, annual_plan: MembershipPlan, password: str
) -> None:
    """A term already paid for that starts after the covering one is suspended too."""
    term(member, annual_plan, starts=-30, ends=200)
    renewal = term(member, annual_plan, starts=201, ends=565)
    deactivate(member_client, password)
    renewal.refresh_from_db()
    assert renewal.status == MembershipStatusChoices.SUSPENDED


def test_deactivating_leaves_a_lapsed_term_alone(
    member_client: APIClient, member: User, annual_plan: MembershipPlan, password: str
) -> None:
    """A term that has already run out stays expired."""
    lapsed = MembershipFactory(
        user=member,
        plan=annual_plan,
        starts_on=timezone.localdate() - timedelta(days=400),
        ends_on=timezone.localdate() - timedelta(days=35),
        status=MembershipStatusChoices.EXPIRED,
    )
    deactivate(member_client, password)
    lapsed.refresh_from_db()
    assert lapsed.status == MembershipStatusChoices.EXPIRED


def test_suspending_a_term_is_recorded(
    member_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    password: str,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """Each suspended term is a ``membership.correct`` under the member."""
    covering = term(member, annual_plan, starts=-30, ends=200)
    deactivate(member_client, password)
    assert (
        f"action=membership.correct actor={member.pk} target={covering.pk} status=suspended"
        in audit_messages(audit_log)
    )


# -- the mandates -----------------------------------------------------------
def test_deactivating_cancels_an_active_mandate(
    member_client: APIClient, member: User, annual_plan: MembershipPlan, password: str
) -> None:
    """Automatic renewal is turned off, by the member."""
    mandate = RenewalMandateFactory(user=member, plan=annual_plan)
    deactivate(member_client, password)
    mandate.refresh_from_db()
    assert (mandate.status, mandate.canceled_by_id) == (MandateStatus.CANCELED, member.pk)


def test_deactivating_cancels_a_paused_mandate(
    member_client: APIClient, member: User, annual_plan: MembershipPlan, password: str
) -> None:
    """A paused mandate is canceled too, so nothing can resume it."""
    mandate = RenewalMandateFactory(user=member, plan=annual_plan, status=MandateStatus.PAUSED)
    deactivate(member_client, password)
    mandate.refresh_from_db()
    assert mandate.status == MandateStatus.CANCELED


def test_deactivating_discards_a_pending_mandate(
    member_client: APIClient, member: User, annual_plan: MembershipPlan, password: str
) -> None:
    """A mandate set up but never confirmed is thrown away."""
    RenewalMandateFactory(user=member, plan=annual_plan, status=MandateStatus.PENDING)
    deactivate(member_client, password)
    assert RenewalMandate.objects.filter(user=member).exists() is False


def test_deactivating_tells_the_member_renewal_is_off(
    member_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    password: str,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: OnCommit,
) -> None:
    """The canceled mandate sends its usual email once the change commits."""
    RenewalMandateFactory(user=member, plan=annual_plan)
    with django_capture_on_commit_callbacks(execute=True):
        deactivate(member_client, password)
    assert [message.to for message in mailoutbox] == [[member.email]]


def test_deactivating_is_recorded_as_a_self_service_cancellation(
    member_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    password: str,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """The mandate's ``renewal.cancel`` carries ``self_service=true``."""
    RenewalMandateFactory(user=member, plan=annual_plan)
    deactivate(member_client, password)
    assert (
        f"action=renewal.cancel actor={member.pk} target={member.pk} provider=mock "
        "self_service=true" in audit_messages(audit_log)
    )


# --------------------------------------------------------------------------
# Suspended terms count for nothing
# --------------------------------------------------------------------------
def test_a_suspended_term_does_not_make_a_member_current(
    member: User, annual_plan: MembershipPlan
) -> None:
    """A suspended term running past today does not cover: the member reads as friend."""
    suspended(member, annual_plan, ends_on=timezone.localdate() + timedelta(days=100))
    assert membership_status(member)["status"] == MembershipState.FRIEND


def test_a_suspended_term_does_not_count_as_past(member: User, annual_plan: MembershipPlan) -> None:
    """A suspended term that has run out does not make a member expired."""
    suspended(member, annual_plan, ends_on=timezone.localdate() - timedelta(days=10))
    assert membership_status(member)["status"] == MembershipState.FRIEND


@pytest.mark.parametrize("days_left", [100, -10], ids=["running", "run-out"])
def test_the_list_annotations_agree_on_a_suspended_term(
    member: User, annual_plan: MembershipPlan, days_left: int
) -> None:
    """The SQL rule reads a suspended-only history as neither current nor expired."""
    suspended(member, annual_plan, ends_on=timezone.localdate() + timedelta(days=days_left))
    row = with_membership(User.objects.filter(pk=member.pk)).get()
    assert (row.covers_today, row.has_started_term) == (False, False)


# --------------------------------------------------------------------------
# POST /auth/reactivate
# --------------------------------------------------------------------------
def reactivate(client: APIClient, email: str, password: str) -> tuple[int, dict[str, object]]:
    """Post the reactivation and return the status code and the body."""
    response = client.post(REACTIVATE_URL, {"email": email, "password": password}, format="json")
    return response.status_code, response.json()


def test_reactivating_answers_the_user_payload(
    api_client: APIClient, member: User, password: str
) -> None:
    """The right password answers 200 with the account, active again."""
    deactivated(member)
    code, body = reactivate(api_client, member.email, password)
    assert (code, body["id"], body["is_active"]) == (200, member.pk, True)


def test_reactivating_signs_the_person_in(
    api_client: APIClient, member: User, password: str
) -> None:
    """The same client is signed in afterwards."""
    deactivated(member)
    reactivate(api_client, member.email, password)
    assert api_client.get(ME_URL).json()["id"] == member.pk


def test_reactivating_matches_the_address_in_any_case(
    api_client: APIClient, member: User, password: str
) -> None:
    """The address is compared as a sign-in compares it."""
    deactivated(member)
    code, _body = reactivate(api_client, member.email.upper(), password)
    assert code == 200


def test_reactivating_keeps_the_kind_and_roles(
    api_client: APIClient, friend: User, password: str
) -> None:
    """A friend comes back a friend holding the member role."""
    deactivated(friend)
    _code, body = reactivate(api_client, friend.email, password)
    assert (body["kind"], body["roles"]) == ("friend", ["member"])


@pytest.mark.parametrize(
    ("setup", "password_given"),
    [
        ("inactive", "not-the-password"),
        ("active", None),
        ("unknown", None),
    ],
    ids=["wrong-password", "active-account", "unknown-address"],
)
def test_reactivating_anything_else_is_the_generic_refusal(
    api_client: APIClient,
    member: User,
    password: str,
    setup: str,
    password_given: str | None,
) -> None:
    """A wrong password, an active account, and an unknown address are one 400."""
    email = member.email
    if setup == "inactive":
        deactivated(member)
    if setup == "unknown":
        email = "nobody@example.test"
    code, body = reactivate(api_client, email, password_given or password)
    assert (code, body) == (400, WRONG_CREDENTIALS)


def test_a_donor_is_refused_as_wrong_credentials(api_client: APIClient) -> None:
    """A deactivated donor, even with a password somehow set, cannot come back here."""
    donor = UserFactory(email="giver@example.test", kind=AccountKind.DONOR, is_active=False)
    code, body = reactivate(api_client, donor.email, GOOD_PASSWORD)
    assert (code, body) == (400, WRONG_CREDENTIALS)


def test_a_refused_reactivation_leaves_the_account_inactive(
    api_client: APIClient, member: User
) -> None:
    """A wrong password changes nothing."""
    deactivated(member)
    reactivate(api_client, member.email, "not-the-password")
    member.refresh_from_db()
    assert member.is_active is False


def test_reactivating_is_recorded_as_self_service(
    api_client: APIClient, member: User, password: str, audit_log: pytest.LogCaptureFixture
) -> None:
    """``account.activate`` names the member as both actor and target."""
    deactivated(member)
    reactivate(api_client, member.email, password)
    assert (
        f"action=account.activate actor={member.pk} target={member.pk} self_service=true"
        in audit_messages(audit_log)
    )


def test_reactivating_mails_an_unverified_address(
    api_client: APIClient,
    member: User,
    password: str,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: OnCommit,
) -> None:
    """An account that never proved its address is sent the verification message."""
    deactivated(member)
    with django_capture_on_commit_callbacks(execute=True):
        reactivate(api_client, member.email, password)
    assert [message.subject for message in mailoutbox] == ["CalDART: verify your email address"]


def test_reactivating_mails_nothing_to_a_verified_address(
    api_client: APIClient,
    member: User,
    password: str,
    mailoutbox: list[EmailMessage],
    django_capture_on_commit_callbacks: OnCommit,
) -> None:
    """A verified account is sent nothing."""
    member.email_verified_at = timezone.now()
    member.save(update_fields=["email_verified_at"])
    deactivated(member)
    with django_capture_on_commit_callbacks(execute=True):
        reactivate(api_client, member.email, password)
    assert mailoutbox == []


# -- the membership comes back ----------------------------------------------
@pytest.mark.parametrize(
    ("days_left", "expected"),
    [
        (100, MembershipStatusChoices.ACTIVE),
        (0, MembershipStatusChoices.ACTIVE),
        (-1, MembershipStatusChoices.EXPIRED),
        (None, MembershipStatusChoices.ACTIVE),
    ],
    ids=["running", "last-day", "run-out", "lifetime"],
)
def test_reactivating_restores_a_suspended_term(
    api_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    password: str,
    days_left: int | None,
    expected: str,
) -> None:
    """A term with time left is active again; one that ran out meanwhile is expired."""
    ends_on = None if days_left is None else timezone.localdate() + timedelta(days=days_left)
    held = suspended(deactivated(member), annual_plan, ends_on=ends_on)
    reactivate(api_client, member.email, password)
    held.refresh_from_db()
    assert held.status == expected


def test_restoring_a_term_is_recorded(
    api_client: APIClient,
    member: User,
    annual_plan: MembershipPlan,
    password: str,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """Each restored term is a ``membership.correct`` under the member."""
    held = suspended(
        deactivated(member), annual_plan, ends_on=timezone.localdate() + timedelta(days=9)
    )
    reactivate(api_client, member.email, password)
    assert (
        f"action=membership.correct actor={member.pk} target={held.pk} status=active"
        in audit_messages(audit_log)
    )


def test_a_membership_resumes_through_its_old_date(
    member_client: APIClient, member: User, annual_plan: MembershipPlan, password: str
) -> None:
    """Deactivating and coming back before the term ends leaves the member current."""
    covering = term(member, annual_plan, starts=-30, ends=200)
    deactivate(member_client, password)
    _code, body = reactivate(member_client, member.email, password)
    assert body["membership"] == {
        "status": "current",
        "expires_on": covering.ends_on.isoformat() if covering.ends_on else None,
        "plan": annual_plan.name,
        "is_lifetime": False,
    }


# --------------------------------------------------------------------------
# Sign-in and password reset for a deactivated account
# --------------------------------------------------------------------------
def test_signing_in_to_a_deactivated_account_offers_reactivation(
    api_client: APIClient, member: User, password: str
) -> None:
    """The right password is a 403 carrying the ``deactivated`` code."""
    deactivated(member)
    response = api_client.post(LOGIN_URL, {"email": member.email, "password": password})
    assert (response.status_code, response.json()) == (
        403,
        {"detail": "This account is deactivated. You can reactivate it.", "code": "deactivated"},
    )


def reset_confirm(client: APIClient, user: User) -> int:
    """Complete a password reset for ``user`` with a fresh link, returning the status."""
    uid, token = make_reset_token(user)
    response = client.post(
        RESET_CONFIRM_URL,
        {"uid": uid, "token": token, "new_password": GOOD_PASSWORD},
        format="json",
    )
    return response.status_code


def test_a_password_reset_reactivates_the_account(api_client: APIClient, member: User) -> None:
    """Completing a reset for a deactivated account makes it active again."""
    deactivated(member)
    assert reset_confirm(api_client, member) == 204
    member.refresh_from_db()
    assert member.is_active is True


def test_a_password_reset_restores_a_suspended_term(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The reset brings the membership back exactly as the endpoint does."""
    held = suspended(
        deactivated(member), annual_plan, ends_on=timezone.localdate() + timedelta(days=30)
    )
    reset_confirm(api_client, member)
    held.refresh_from_db()
    assert held.status == MembershipStatusChoices.ACTIVE


def test_a_password_reset_records_a_self_service_reactivation(
    api_client: APIClient, member: User, audit_log: pytest.LogCaptureFixture
) -> None:
    """The reset writes the same ``account.activate`` the endpoint does."""
    deactivated(member)
    reset_confirm(api_client, member)
    assert (
        f"action=account.activate actor={member.pk} target={member.pk} self_service=true"
        in audit_messages(audit_log)
    )


def test_a_password_reset_of_an_active_account_records_no_reactivation(
    api_client: APIClient, member: User, audit_log: pytest.LogCaptureFixture
) -> None:
    """An ordinary reset is not a reactivation."""
    reset_confirm(api_client, member)
    assert not any("account.activate" in line for line in audit_messages(audit_log))


def test_the_administrator_still_cannot_mail_a_deactivated_account_a_reset(
    api_client: APIClient, user_admin: User, member: User, mailoutbox: list[EmailMessage]
) -> None:
    """The user administrator's send stays refused; only the person may come back."""
    deactivated(member)
    api_client.force_login(user_admin)
    response = api_client.post(f"/api/v1/admin/users/{member.pk}/send-password-reset")
    assert (response.status_code, mailoutbox) == (400, [])


def test_reactivating_an_active_account_changes_nothing(
    member: User, annual_plan: MembershipPlan, audit_log: pytest.LogCaptureFixture
) -> None:
    """A second, concurrent reactivation finds the account active and does nothing."""
    suspended(member, annual_plan, ends_on=timezone.localdate() + timedelta(days=30))
    assert (reactivate_account(member), audit_messages(audit_log)) == (False, [])


def test_deactivating_an_inactive_account_changes_nothing(
    member: User, annual_plan: MembershipPlan, audit_log: pytest.LogCaptureFixture
) -> None:
    """A second, concurrent deactivation finds the account inactive and does nothing."""
    covering = term(deactivated(member), annual_plan, starts=-30, ends=200)
    deactivate_account(member)
    covering.refresh_from_db()
    assert (covering.status, audit_messages(audit_log)) == (MembershipStatusChoices.ACTIVE, [])


# --------------------------------------------------------------------------
# An administrator reactivating the account
# --------------------------------------------------------------------------
USERS_URL = "/api/v1/admin/users"
MEMBERS_URL = "/api/v1/admin/members"


@pytest.mark.parametrize("base_url", [USERS_URL, MEMBERS_URL], ids=["users", "members"])
@pytest.mark.parametrize(
    ("days_left", "expected"),
    [(100, MembershipStatusChoices.ACTIVE), (-1, MembershipStatusChoices.EXPIRED)],
    ids=["running", "run-out"],
)
def test_an_administrator_reactivating_restores_a_suspended_term(
    api_client: APIClient,
    system_admin: User,
    member: User,
    annual_plan: MembershipPlan,
    base_url: str,
    days_left: int,
    expected: str,
) -> None:
    """Ticking Account is active again brings the membership back, or lets it expire."""
    ends_on = timezone.localdate() + timedelta(days=days_left)
    held = suspended(deactivated(member), annual_plan, ends_on=ends_on)
    api_client.force_login(system_admin)
    response = api_client.patch(f"{base_url}/{member.pk}", {"is_active": True}, format="json")
    held.refresh_from_db()
    assert (response.status_code, held.status) == (200, expected)


def test_an_administrator_reactivating_is_recorded_under_the_administrator(
    api_client: APIClient,
    system_admin: User,
    member: User,
    annual_plan: MembershipPlan,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """The restored term's ``membership.correct`` names the administrator."""
    ends_on = timezone.localdate() + timedelta(days=30)
    held = suspended(deactivated(member), annual_plan, ends_on=ends_on)
    api_client.force_login(system_admin)
    api_client.patch(f"{USERS_URL}/{member.pk}", {"is_active": True}, format="json")
    assert (
        f"action=membership.correct actor={system_admin.pk} target={held.pk} status=active"
        in audit_messages(audit_log)
    )


def test_an_administrator_edit_of_an_active_account_restores_nothing(
    api_client: APIClient, system_admin: User, member: User, annual_plan: MembershipPlan
) -> None:
    """Only the change from inactive to active brings a suspended term back."""
    held = suspended(member, annual_plan, ends_on=timezone.localdate() + timedelta(days=30))
    api_client.force_login(system_admin)
    api_client.patch(f"{USERS_URL}/{member.pk}", {"is_active": True}, format="json")
    held.refresh_from_db()
    assert held.status == MembershipStatusChoices.SUSPENDED
