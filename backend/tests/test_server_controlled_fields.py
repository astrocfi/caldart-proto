"""Request bodies cannot set the fields the server controls.

Roles, the Django ``is_staff`` and ``is_superuser`` flags, ownership, a
membership term's provenance and dates, and a payment's status and amount are
all computed by the server.  Each test here sends a valid body with those keys
added, then reloads the row and asserts the server's own values survived.

Unknown keys are ignored rather than rejected: the portal's forms send whole
objects back, including fields they only read, so a strict 400 would break
them.  Every case therefore asserts the success status as well as the stored
values.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import TYPE_CHECKING

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.accounts.roles import MEMBER, SYSTEM_ADMIN
from apps.members.models import MemberProfile, MembershipSource, MembershipStatusChoices
from apps.payments.models import Payment, PaymentStatus
from tests.factories import PaymentFactory, UserFactory

if TYPE_CHECKING:
    from pytest_django.fixtures import Settings

    from apps.accounts.models import User as UserModel
    from apps.members.models import MembershipPlan

pytestmark = pytest.mark.django_db

User = get_user_model()

REGISTER = "/api/v1/auth/register"
MEMBERS = "/api/v1/admin/members"
USERS = "/api/v1/admin/users"
PROFILE = "/api/v1/me/profile"
CHECKOUT = "/api/v1/payments/checkout"

GOOD_PASSWORD = "Sierra-Foothills-2027"  # noqa: S105 - test fixture

#: The keys an attacker would add to an account body to escalate privilege.
ESCALATION_FIELDS: dict[str, object] = {
    "roles": [MEMBER, SYSTEM_ADMIN],
    "is_staff": True,
    "is_superuser": True,
}


@pytest.fixture(autouse=True)
def _mock_provider(settings: Settings) -> None:
    """The checkout case needs a configured provider; the mock is enough."""
    settings.PAYMENTS_MOCK_ENABLED = True


@pytest.fixture
def other_member(db: None) -> UserModel:
    """Return a second account, used as the identity a forged body tries to name."""
    return UserFactory(email="other.member@example.test", roles=[MEMBER])


# --------------------------------------------------------------------------
# Accounts: roles and the Django flags
# --------------------------------------------------------------------------
def test_registration_ignores_roles_and_the_django_flags(api_client: APIClient) -> None:
    """A visitor cannot sign themselves up as a system administrator."""
    response = api_client.post(
        REGISTER,
        {
            "email": "new.member@example.test",
            "password": GOOD_PASSWORD,
            "first_name": "Nora",
            "last_name": "Bright",
            "is_active": False,
            **ESCALATION_FIELDS,
        },
        format="json",
    )
    assert response.status_code == 201

    user = User.objects.get(email="new.member@example.test")
    assert user.roles == [MEMBER]
    assert user.is_staff is False
    assert user.is_superuser is False
    assert user.is_active is True


def test_member_creation_ignores_roles_and_the_django_flags(
    api_client: APIClient, account_admin: UserModel
) -> None:
    """An account administrator cannot mint an administrator through the member form."""
    api_client.force_login(account_admin)
    response = api_client.post(
        MEMBERS,
        {
            "email": "granted@example.test",
            "first_name": "Ada",
            "last_name": "Vance",
            **ESCALATION_FIELDS,
        },
        format="json",
    )
    assert response.status_code == 201

    user = User.objects.get(email="granted@example.test")
    assert user.roles == [MEMBER]
    assert user.is_staff is False
    assert user.is_superuser is False


def test_member_update_applies_the_name_and_nothing_else(
    api_client: APIClient, account_admin: UserModel, member: UserModel
) -> None:
    """The member form edits names; roles and the flags are not its to change."""
    api_client.force_login(account_admin)
    response = api_client.patch(
        f"{MEMBERS}/{member.pk}",
        {"first_name": "Priya", **ESCALATION_FIELDS},
        format="json",
    )
    assert response.status_code == 200

    member.refresh_from_db()
    assert member.first_name == "Priya"
    assert member.roles == [MEMBER]
    assert member.is_staff is False
    assert member.is_superuser is False


def test_user_update_ignores_the_django_flags(
    api_client: APIClient, user_admin: UserModel, member: UserModel
) -> None:
    """The users-admin endpoint edits roles, and derives the flags from them."""
    api_client.force_login(user_admin)
    response = api_client.patch(
        f"{USERS}/{member.pk}",
        {"is_staff": True, "is_superuser": True},
        format="json",
    )
    assert response.status_code == 200

    member.refresh_from_db()
    assert member.is_staff is False
    assert member.is_superuser is False


# --------------------------------------------------------------------------
# Ownership
# --------------------------------------------------------------------------
def test_profile_update_cannot_reassign_the_profile(
    api_client: APIClient, member: UserModel, profile: MemberProfile, other_member: UserModel
) -> None:
    """``/me/profile`` always writes the caller's own row."""
    api_client.force_login(member)
    response = api_client.patch(PROFILE, {"user": other_member.pk}, format="json")
    assert response.status_code == 200

    profile.refresh_from_db()
    assert profile.user == member
    assert MemberProfile.objects.filter(user=other_member).exists() is False


# --------------------------------------------------------------------------
# Membership provenance
# --------------------------------------------------------------------------
def test_manual_grant_ignores_provenance_dates_and_status(
    api_client: APIClient,
    account_admin: UserModel,
    member: UserModel,
    other_member: UserModel,
    annual_plan: MembershipPlan,
    payment_factory: type[PaymentFactory],
    today: date,
) -> None:
    """A granted term records the real grantor, and the plan's own arithmetic."""
    payment = payment_factory(user=member, plan=annual_plan)
    api_client.force_login(account_admin)
    response = api_client.post(
        f"{MEMBERS}/{member.pk}/memberships",
        {
            "plan": annual_plan.slug,
            "source": MembershipSource.PAYMENT,
            "granted_by": other_member.pk,
            "ends_on": "2099-01-01",
            "status": MembershipStatusChoices.CANCELED,
            "payment": payment.pk,
        },
        format="json",
    )
    assert response.status_code == 201

    term = member.memberships.get()
    assert term.source == MembershipSource.MANUAL
    assert term.granted_by == account_admin
    assert annual_plan.duration_days is not None
    assert term.ends_on == today + timedelta(days=annual_plan.duration_days - 1)
    assert term.status == MembershipStatusChoices.ACTIVE
    assert term.payment_id is None


# --------------------------------------------------------------------------
# Payment owner, status and amount
# --------------------------------------------------------------------------
def test_checkout_ignores_the_owner_status_and_amount(
    api_client: APIClient, member: UserModel, other_member: UserModel, annual_plan: MembershipPlan
) -> None:
    """A checkout is the caller's, starts pending, and costs what the plan costs."""
    api_client.force_login(member)
    response = api_client.post(
        CHECKOUT,
        {
            "plan": annual_plan.slug,
            "contribution_cents": 0,
            "provider": "mock",
            "user": other_member.pk,
            "status": PaymentStatus.SUCCEEDED,
            "amount_cents": 1,
        },
        format="json",
    )
    assert response.status_code == 201

    payment = Payment.objects.get(pk=response.data["payment_id"])
    assert payment.user == member
    assert payment.status == PaymentStatus.PENDING
    assert payment.amount_cents == annual_plan.price_cents
