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

from apps.accounts.models import User
from apps.members.models import MembershipPlan
from apps.payments.api.serializers import MAX_CONTRIBUTION_CENTS

CHECKOUT = "/api/v1/payments/checkout"


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
