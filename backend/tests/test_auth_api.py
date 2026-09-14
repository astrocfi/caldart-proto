"""The minimal auth surface the portal shell needs."""

from __future__ import annotations

import pytest

from apps.accounts.roles import MEMBER, ROLE_SLUGS
from tests.factories import MembershipFactory

pytestmark = pytest.mark.django_db


def test_csrf_endpoint_sets_the_cookie(api_client):
    response = api_client.get("/api/v1/auth/csrf")
    assert response.status_code == 204
    assert "csrftoken" in response.cookies


def test_me_is_401_when_anonymous(api_client):
    assert api_client.get("/api/v1/auth/me").status_code == 401


def test_login_returns_the_user_payload(api_client, member, password, annual_plan, today):
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
    }


def test_login_is_case_insensitive_on_email(api_client, member, password):
    response = api_client.post(
        "/api/v1/auth/login", {"email": member.email.upper(), "password": password}
    )
    assert response.status_code == 200


def test_login_with_a_bad_password(api_client, member):
    response = api_client.post("/api/v1/auth/login", {"email": member.email, "password": "wrong"})
    assert response.status_code == 400
    assert "detail" in response.json()


def test_login_rejects_a_deactivated_account(api_client, member, password):
    member.is_active = False
    member.save(update_fields=["is_active"])
    response = api_client.post("/api/v1/auth/login", {"email": member.email, "password": password})
    assert response.status_code in (400, 403)


def test_login_validates_the_payload(api_client):
    response = api_client.post("/api/v1/auth/login", {"email": "not-an-email"})
    assert response.status_code == 400


def test_me_after_login(api_client, member, password):
    api_client.post("/api/v1/auth/login", {"email": member.email, "password": password})
    response = api_client.get("/api/v1/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == member.email


def test_logout_clears_the_session(api_client, member, password):
    api_client.post("/api/v1/auth/login", {"email": member.email, "password": password})
    assert api_client.post("/api/v1/auth/logout").status_code == 204
    assert api_client.get("/api/v1/auth/me").status_code == 401


def test_profile_complete_flag(api_client, member, password, profile):
    api_client.post("/api/v1/auth/login", {"email": member.email, "password": password})
    assert api_client.get("/api/v1/auth/me").json()["profile_complete"] is True


def test_roles_endpoint_requires_authentication(api_client):
    assert api_client.get("/api/v1/roles").status_code == 401


def test_roles_endpoint_lists_every_role(api_client, member):
    api_client.force_login(member)
    response = api_client.get("/api/v1/roles")
    assert response.status_code == 200
    slugs = [row["slug"] for row in response.json()]
    assert slugs == list(ROLE_SLUGS)
    assert all(row["description"] for row in response.json())


def test_site_config_is_public(api_client, site_settings):
    response = api_client.get("/api/v1/site/config")
    assert response.status_code == 200
    data = response.json()
    assert set(data) >= {"org_name", "theme", "contact_email", "nav", "members_pages"}
    assert data["theme"] == "sierra"
