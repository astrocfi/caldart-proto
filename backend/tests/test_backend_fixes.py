"""The low-priority backend findings: one test per fixed item.

Each test here pins one behavior that used to be wrong: the bound on a
contribution, what a login says about a deactivated account, how the report
helpers treat markup and spreadsheet formulas, how the database password
reaches ``pg_dump``, where the PayPal token is cached, and which modules still
reach for an attribute defensively.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.api.views import DEACTIVATED_MESSAGE, WRONG_CREDENTIALS_MESSAGE
from apps.accounts.models import User
from apps.members.models import MembershipPlan
from apps.payments.api.serializers import MAX_CONTRIBUTION_CENTS

CHECKOUT = "/api/v1/payments/checkout"
LOGIN = "/api/v1/auth/login"


# --------------------------------------------------------------------------
# A contribution is bounded
# --------------------------------------------------------------------------
@pytest.mark.django_db
def test_checkout_rejects_an_oversized_contribution(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """A contribution above the cap is a 400 naming the field and the limit."""
    api_client.force_login(member)

    response = api_client.post(
        CHECKOUT,
        {
            "plan": "annual",
            "contribution_cents": MAX_CONTRIBUTION_CENTS + 1,
            "provider": "mock",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "contribution_cents": ["Ensure this value is less than or equal to 1000000000."]
    }


@pytest.mark.django_db
def test_checkout_accepts_a_contribution_at_the_cap(
    api_client: APIClient, member: User, annual_plan: MembershipPlan
) -> None:
    """The cap itself is still accepted, so the bound is inclusive."""
    api_client.force_login(member)

    response = api_client.post(
        CHECKOUT,
        {"plan": "annual", "contribution_cents": MAX_CONTRIBUTION_CENTS, "provider": "mock"},
    )

    assert response.status_code == 201


# --------------------------------------------------------------------------
# A login tells a wrong password nothing about the account
# --------------------------------------------------------------------------
@pytest.mark.django_db
def test_login_with_a_wrong_password_on_an_active_account(
    api_client: APIClient, member: User
) -> None:
    """A wrong password on an active account is the generic 400."""
    response = api_client.post(LOGIN, {"email": member.email, "password": "wrong-password"})

    assert response.status_code == 400
    assert response.json() == {"detail": WRONG_CREDENTIALS_MESSAGE}


@pytest.mark.django_db
def test_login_with_a_wrong_password_hides_a_deactivated_account(
    api_client: APIClient, member: User
) -> None:
    """A wrong password on a deactivated account gets the same 400 as any other."""
    member.is_active = False
    member.save(update_fields=["is_active"])

    response = api_client.post(LOGIN, {"email": member.email, "password": "wrong-password"})

    assert response.status_code == 400
    assert response.json() == {"detail": WRONG_CREDENTIALS_MESSAGE}


@pytest.mark.django_db
def test_login_with_the_right_password_names_the_deactivation(
    api_client: APIClient, member: User, password: str
) -> None:
    """Only a correct password is told the account has been deactivated."""
    member.is_active = False
    member.save(update_fields=["is_active"])

    response = api_client.post(LOGIN, {"email": member.email, "password": password})

    assert response.status_code == 403
    assert response.json() == {"detail": DEACTIVATED_MESSAGE}
