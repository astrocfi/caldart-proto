"""The minimal auth surface the portal shell needs."""

from __future__ import annotations

from datetime import date

import pytest
from rest_framework.test import APIClient

from apps.accounts.api.views import DEACTIVATED_MESSAGE, WRONG_CREDENTIALS_MESSAGE
from apps.accounts.models import User
from apps.accounts.roles import MEMBER
from apps.members.models import MembershipPlan
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db


def test_csrf_endpoint_sets_the_cookie(api_client: APIClient) -> None:
    """``GET /auth/csrf`` returns 204 and leaves a ``csrftoken`` cookie on the client."""
    response = api_client.get("/api/v1/auth/csrf")
    assert response.status_code == 204
    assert "csrftoken" in response.cookies


def test_me_is_401_when_anonymous(api_client: APIClient) -> None:
    """``GET /auth/me`` is 401 for a client with no session."""
    assert api_client.get("/api/v1/auth/me").status_code == 401


def test_login_returns_the_user_payload(
    api_client: APIClient, member: User, password: str, annual_plan: MembershipPlan, today: date
) -> None:
    """A successful login returns the documented user payload, membership included."""
    MembershipFactory(user=member, plan=annual_plan, starts_on=today)
    response = api_client.post("/api/v1/auth/login", {"email": member.email, "password": password})
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == member.email
    assert data["roles"] == [MEMBER]
    assert data["is_active"] is True
    assert data["membership"]["status"] == "current"
    assert set(data) == {
        "id",
        "email",
        "first_name",
        "last_name",
        "roles",
        "is_active",
        "membership",
        "profile_complete",
        "email_verified",
    }


def test_login_is_case_insensitive_on_email(
    api_client: APIClient, member: User, password: str
) -> None:
    """A login submitted with the email in a different case still succeeds."""
    response = api_client.post(
        "/api/v1/auth/login", {"email": member.email.upper(), "password": password}
    )
    assert response.status_code == 200


def test_login_with_a_bad_password(api_client: APIClient, member: User) -> None:
    """A wrong password is refused with a 400 naming neither half of the credentials."""
    response = api_client.post("/api/v1/auth/login", {"email": member.email, "password": "wrong"})
    assert response.status_code == 400
    assert response.json()["detail"] == WRONG_CREDENTIALS_MESSAGE


def test_login_rejects_a_deactivated_account(
    api_client: APIClient, member: User, password: str
) -> None:
    """A deactivated account is told so, but only once its password has matched."""
    member.is_active = False
    member.save(update_fields=["is_active"])
    response = api_client.post("/api/v1/auth/login", {"email": member.email, "password": password})
    assert response.status_code == 403
    assert response.json()["detail"] == DEACTIVATED_MESSAGE


def test_login_validates_the_payload(api_client: APIClient) -> None:
    """A login missing the password field is refused with a 400 naming ``password``."""
    response = api_client.post("/api/v1/auth/login", {"email": "someone@example.test"})
    assert response.status_code == 400
    assert response.json()["password"] == ["This field is required."]


def test_me_reports_the_member_who_just_logged_in(
    api_client: APIClient, member: User, password: str
) -> None:
    """``GET /auth/me`` reports the signed-in member once login has succeeded."""
    api_client.post("/api/v1/auth/login", {"email": member.email, "password": password})
    response = api_client.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == member.email


def test_logout_clears_the_session(api_client: APIClient, member: User, password: str) -> None:
    """Logging out ends the session, so ``/auth/me`` is 401 again."""
    api_client.post("/api/v1/auth/login", {"email": member.email, "password": password})
    assert api_client.post("/api/v1/auth/logout").status_code == 204
    assert api_client.get("/api/v1/auth/me").status_code == 401


def test_roles_endpoint_requires_authentication(api_client: APIClient) -> None:
    """``GET /roles`` is 401 for a client with no session."""
    assert api_client.get("/api/v1/roles").status_code == 401
