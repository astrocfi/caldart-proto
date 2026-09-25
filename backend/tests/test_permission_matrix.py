"""Endpoint x role combinations no other test module covers.

Every case here pins down behavior that already exists: anonymous access to
seven endpoints, ``system_admin`` writes on the members-admin API, three
roles editing another member's aircraft, profile writes by every role, the
Wagtail admin for ``user_admin`` and ``account_admin``, and everything a
signed-in account with no roles at all may and may not reach.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from django.core.mail import EmailMessage
from django.test import Client
from pytest_django.fixtures import Settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import (
    DART_LEADER,
    MEMBER,
    ROLE_SLUGS,
    USER_ADMIN,
    WEBSITE_ADMIN,
)
from apps.aircraft.models import Aircraft
from apps.members.models import MemberProfile, Membership, MembershipPlan
from apps.payments.models import PaymentStatus
from tests.factories import AircraftFactory, MembershipFactory, PaymentFactory, UserFactory

pytestmark = pytest.mark.django_db

AIRCRAFT_LIST_URL = "/api/v1/aircraft"
BACKUPS_URL = "/api/v1/system/backups"
CHECKOUT_URL = "/api/v1/payments/checkout"
MOCK_COMPLETE_URL = "/api/v1/payments/mock/complete"
MEMBERS_LIST_URL = "/api/v1/admin/members"
USERS_LIST_URL = "/api/v1/admin/users"
PROFILE_URL = "/api/v1/me/profile"

#: The smallest body a profile ``PUT`` will accept.
MINIMAL_PROFILE_PUT = {"phone": "415-555-0100", "state": "CA"}

#: Self-service and public endpoints a role-less account can still reach.
NO_ROLE_ALLOWED_GETS = [
    "/api/v1/auth/me",
    "/api/v1/roles",
    "/api/v1/me/profile",
    "/api/v1/me/membership",
    "/api/v1/me/payments",
    "/api/v1/aircraft",
    "/api/v1/payments/config",
    "/api/v1/site/config",
]

#: Role-gated endpoints that a role-less account may not reach.
NO_ROLE_DENIED_GETS = [
    "/api/v1/leader/search",
    "/api/v1/admin/users",
    "/api/v1/admin/members",
    "/api/v1/reports/members/columns",
    "/api/v1/reports/aircraft/columns",
    "/api/v1/reports/payments/export.csv",
    "/api/v1/reports/members/column-sets",
    "/api/v1/reports/subscriptions",
    "/api/v1/reports/rosters",
    "/api/v1/admin/payments",
    "/api/v1/admin/reminders/log",
    "/api/v1/system/emails",
    "/api/v1/system/emails/purposes",
    "/api/v1/reports/emails/export.csv",
    "/api/v1/system/health",
]


def aircraft_url(aircraft: Aircraft) -> str:
    """``/aircraft/{id}`` for ``aircraft``."""
    return f"{AIRCRAFT_LIST_URL}/{aircraft.pk}"


def member_detail_url(user: User) -> str:
    """``/admin/members/{user_id}`` for ``user``."""
    return f"{MEMBERS_LIST_URL}/{user.pk}"


def member_grant_url(user: User) -> str:
    """``/admin/members/{user_id}/memberships``, where a term is granted to ``user``."""
    return f"{MEMBERS_LIST_URL}/{user.pk}/memberships"


def membership_url(term: Membership) -> str:
    """``/admin/memberships/{id}`` for one granted term."""
    return f"/api/v1/admin/memberships/{term.pk}"


def user_detail_url(user: User) -> str:
    """``/admin/users/{id}`` for ``user``."""
    return f"{USERS_LIST_URL}/{user.pk}"


def send_reset_url(user: User) -> str:
    """``/admin/users/{id}/send-password-reset`` for ``user``."""
    return f"{USERS_LIST_URL}/{user.pk}/send-password-reset"


@pytest.fixture(autouse=True)
def _mock_only(settings: Settings) -> None:
    """Default to "only the mock provider is configured"."""
    settings.PAYMENTS_MOCK_ENABLED = True
    settings.STRIPE_SECRET_KEY = ""
    settings.STRIPE_PUBLISHABLE_KEY = ""
    settings.PAYPAL_CLIENT_ID = ""
    settings.PAYPAL_CLIENT_SECRET = ""


@pytest.fixture
def other_aircraft() -> Aircraft:
    """An aircraft owned by a member other than any of the role fixtures."""
    owner = UserFactory(email="aircraft-owner@example.test", roles=[MEMBER])
    return AircraftFactory(n_number="N70PM", created_by=owner)


@pytest.fixture
def target_member(profile: MemberProfile, annual_plan: MembershipPlan) -> User:
    """A member with a profile and one membership term to write against."""
    MembershipFactory(user=profile.user, plan=annual_plan)
    return profile.user


# --------------------------------------------------------------------------
# Anonymous: 401 on seven endpoints, and nothing changes
# --------------------------------------------------------------------------
def test_anonymous_cannot_read_aircraft_detail(
    api_client: APIClient, other_aircraft: Aircraft
) -> None:
    """The aircraft register is signed-in only, detail rows included."""
    assert api_client.get(aircraft_url(other_aircraft)).status_code == 401


def test_anonymous_cannot_patch_aircraft(api_client: APIClient, other_aircraft: Aircraft) -> None:
    """A refused edit leaves the stored row alone."""
    response = api_client.patch(aircraft_url(other_aircraft), {"model": "hijacked"})
    assert response.status_code == 401
    other_aircraft.refresh_from_db()
    assert other_aircraft.model != "hijacked"


def test_anonymous_cannot_delete_aircraft(api_client: APIClient, other_aircraft: Aircraft) -> None:
    """A refused delete leaves the row in place."""
    response = api_client.delete(aircraft_url(other_aircraft))
    assert response.status_code == 401
    assert Aircraft.objects.filter(pk=other_aircraft.pk).exists()


def test_anonymous_cannot_complete_a_mock_payment(
    api_client: APIClient, payment_factory: type[PaymentFactory], annual_plan: MembershipPlan
) -> None:
    """The mock provider's completion hook needs a session, so the payment is pending."""
    payment = payment_factory(plan=annual_plan, status=PaymentStatus.PENDING)
    response = api_client.post(MOCK_COMPLETE_URL, {"payment_id": payment.pk, "outcome": "succeed"})
    assert response.status_code == 401
    payment.refresh_from_db()
    assert payment.status == PaymentStatus.PENDING


def test_anonymous_cannot_create_a_backup(
    api_client: APIClient, tmp_path: Path, settings: Settings
) -> None:
    """The refusal comes before any dump is written."""
    settings.BACKUP_DIR = tmp_path / "backups"
    response = api_client.post(BACKUPS_URL)
    assert response.status_code == 401
    assert not (tmp_path / "backups").exists()


def test_anonymous_cannot_read_a_user_detail(api_client: APIClient, target_member: User) -> None:
    """The users-admin API answers 401 rather than leaking an account."""
    assert api_client.get(user_detail_url(target_member)).status_code == 401


def test_anonymous_cannot_send_a_password_reset(
    api_client: APIClient, target_member: User, mailoutbox: list[EmailMessage]
) -> None:
    """The administrator's reset route sends nothing to an anonymous caller."""
    response = api_client.post(send_reset_url(target_member))
    assert response.status_code == 401
    assert len(mailoutbox) == 0


# --------------------------------------------------------------------------
# system_admin writes on the members-admin API
# --------------------------------------------------------------------------
def test_system_admin_may_create_a_member(api_client: APIClient, system_admin: User) -> None:
    """A system administrator holds the account administrator's write access too."""
    api_client.force_login(system_admin)
    response = api_client.post(MEMBERS_LIST_URL, {"email": "newmember@example.test"})
    assert response.status_code == 201


def test_system_admin_may_update_a_member(
    api_client: APIClient, system_admin: User, target_member: User
) -> None:
    """The edit lands on the stored record."""
    api_client.force_login(system_admin)
    response = api_client.patch(member_detail_url(target_member), {"first_name": "Updated"})
    assert response.status_code == 200
    target_member.refresh_from_db()
    assert target_member.first_name == "Updated"


def test_system_admin_may_grant_a_membership(
    api_client: APIClient, system_admin: User, target_member: User
) -> None:
    """Granting a term by hand is open to a system administrator."""
    api_client.force_login(system_admin)
    response = api_client.post(member_grant_url(target_member), {"plan": "annual"})
    assert response.status_code == 201


def test_system_admin_may_correct_a_term(
    api_client: APIClient, system_admin: User, target_member: User
) -> None:
    """A correction to a granted term is stored."""
    api_client.force_login(system_admin)
    term = target_member.memberships.first()
    assert term is not None
    response = api_client.patch(membership_url(term), {"note": "corrected"})
    assert response.status_code == 200
    term.refresh_from_db()
    assert term.note == "corrected"


# --------------------------------------------------------------------------
# dart_leader, user_admin, website_admin may not patch another member's
# aircraft
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    "role",
    [DART_LEADER, USER_ADMIN, WEBSITE_ADMIN],
    ids=["dart_leader", "user_admin", "website_admin"],
)
def test_role_may_not_patch_another_members_aircraft(
    api_client: APIClient, all_role_users: dict[str, User], other_aircraft: Aircraft, role: str
) -> None:
    """Aircraft belong to the member who entered them, whatever else the role opens."""
    api_client.force_login(all_role_users[role])
    response = api_client.patch(aircraft_url(other_aircraft), {"model": "hijacked"})
    assert response.status_code == 403
    other_aircraft.refresh_from_db()
    assert other_aircraft.model != "hijacked"


def test_the_creator_of_an_aircraft_may_not_read_its_history(
    api_client: APIClient, member: User
) -> None:
    """Editing a record is not the same right as seeing who else has edited it."""
    own = AircraftFactory(n_number="N71PM", created_by=member)
    api_client.force_login(member)
    assert api_client.get(f"{aircraft_url(own)}/changes").status_code == 403


def test_a_dart_leader_may_not_read_an_aircraft_history(
    api_client: APIClient, dart_leader: User, other_aircraft: Aircraft
) -> None:
    """A leader reads the insurance card, not the trail of who changed it."""
    api_client.force_login(dart_leader)
    assert api_client.get(f"{aircraft_url(other_aircraft)}/changes").status_code == 403


def test_anonymous_cannot_read_an_aircraft_history(
    api_client: APIClient, other_aircraft: Aircraft
) -> None:
    """The history answers 401 rather than naming the accounts that wrote the record."""
    assert api_client.get(f"{aircraft_url(other_aircraft)}/changes").status_code == 401


# --------------------------------------------------------------------------
# Every role may PUT and PATCH its own profile
# --------------------------------------------------------------------------
@pytest.mark.parametrize("role", ROLE_SLUGS)
def test_role_may_put_its_own_profile(
    api_client: APIClient, all_role_users: dict[str, User], role: str
) -> None:
    """A full profile replacement is self-service for every role."""
    api_client.force_login(all_role_users[role])
    response = api_client.put(PROFILE_URL, MINIMAL_PROFILE_PUT, format="json")
    assert response.status_code == 200


@pytest.mark.parametrize("role", ROLE_SLUGS)
def test_role_may_patch_its_own_profile(
    api_client: APIClient, all_role_users: dict[str, User], role: str
) -> None:
    """A partial profile edit is self-service for every role."""
    api_client.force_login(all_role_users[role])
    response = api_client.patch(PROFILE_URL, {"phone": "415-555-0199"}, format="json")
    assert response.status_code == 200


# --------------------------------------------------------------------------
# The Wagtail admin for user_admin, account_admin and a role-less user
# --------------------------------------------------------------------------
@pytest.mark.parametrize("fixture_name", ["user_admin", "account_admin", "no_role_user"])
def test_wagtail_admin_redirects_to_login(
    client: Client, request: pytest.FixtureRequest, fixture_name: str
) -> None:
    """Only the website administrator's staff account gets past the Wagtail login."""
    user = request.getfixturevalue(fixture_name)
    client.force_login(user)
    response = client.get("/admin/")
    assert response.status_code == 302
    assert response["Location"] == "/admin/login/?next=/admin/"


# --------------------------------------------------------------------------
# A signed-in account with no roles at all
# --------------------------------------------------------------------------
@pytest.mark.parametrize("url", NO_ROLE_ALLOWED_GETS)
def test_no_role_user_reaches_self_service_endpoints(
    api_client: APIClient, no_role_user: User, url: str
) -> None:
    """Its own records, the aircraft register and the public configuration stay open."""
    api_client.force_login(no_role_user)
    assert api_client.get(url).status_code == 200


def test_no_role_user_may_check_out(
    api_client: APIClient, no_role_user: User, annual_plan: MembershipPlan
) -> None:
    """Buying the first membership is how a role-less account becomes a member."""
    api_client.force_login(no_role_user)
    response = api_client.post(
        CHECKOUT_URL, {"plan": "annual", "contribution_cents": 0, "provider": "mock"}
    )
    assert response.status_code == 201


@pytest.mark.parametrize("url", NO_ROLE_DENIED_GETS)
def test_no_role_user_is_refused_role_gated_endpoints(
    api_client: APIClient, no_role_user: User, url: str
) -> None:
    """Role-gated endpoints answer 403, not 401: the session is real, the role is not."""
    api_client.force_login(no_role_user)
    assert api_client.get(url).status_code == 403


# --------------------------------------------------------------------------
# The treasurer: the money, and nothing else
# --------------------------------------------------------------------------
#: Role-gated endpoints outside the finance area, which a treasurer may not reach.
TREASURER_DENIED_GETS = [
    MEMBERS_LIST_URL,
    USERS_LIST_URL,
    "/api/v1/reports/members/export.csv",
    "/api/v1/reports/members/columns",
    "/api/v1/reports/aircraft/export.csv",
    "/api/v1/reports/aircraft/columns",
    "/api/v1/reports/members/column-sets",
    "/api/v1/reports/rosters",
    "/api/v1/admin/darts",
    "/api/v1/admin/reminders/log",
    "/api/v1/leader/search",
    "/api/v1/system/emails",
    "/api/v1/system/emails/purposes",
    "/api/v1/reports/emails/export.csv",
    "/api/v1/system/health",
]


@pytest.mark.parametrize("url", TREASURER_DENIED_GETS)
def test_treasurer_is_refused_every_endpoint_outside_the_finance_area(
    treasurer_client: APIClient, url: str
) -> None:
    """The finance role carries the money screens only: everything else answers 403."""
    assert treasurer_client.get(url).status_code == 403


def test_treasurer_reaches_the_finance_reports(treasurer_client: APIClient) -> None:
    """The payment summary is finance's own, so the treasurer reads it."""
    assert treasurer_client.get("/api/v1/admin/payments/summary").status_code == 200


@pytest.mark.parametrize(
    "url",
    [
        "/api/v1/reports/payments/export.csv",
        "/api/v1/reports/reconciliation/export.pdf",
        "/api/v1/reports/contributions/columns",
    ],
)
def test_treasurer_downloads_the_money_reports(treasurer_client: APIClient, url: str) -> None:
    """The payments, reconciliation and contributions reports are finance's own."""
    assert treasurer_client.get(url).status_code == 200


def test_a_member_is_offered_no_report(api_client: APIClient, member: User) -> None:
    """``GET /reports`` answers a member who may read nothing with an empty list."""
    api_client.force_login(member)
    assert api_client.get("/api/v1/reports").json() == []


def test_treasurer_manages_the_report_subscriptions(treasurer_client: APIClient) -> None:
    """The subscription list is finance's own, so the treasurer reads it."""
    assert treasurer_client.get("/api/v1/reports/subscriptions").status_code == 200
