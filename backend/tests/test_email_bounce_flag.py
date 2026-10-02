"""The bounce flag on an account: shown, filtered on, and cleared.

The bounce check sets ``email_bounced_at`` and ``email_bounce_detail`` on the account
whose address bounced.  The member record and the user record show them, ``GET
/admin/users?email_bounced=`` filters on them, and they clear when the address changes,
when the address is proved by a verification or password link, and by a user
administrator's ``POST /admin/users/{id}/clear-bounce``.  See
``docs/developer/api-auth.rst`` and ``docs/developer/api-members.rst``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import ACCOUNT_ADMIN, DART_LEADER, SYSTEM_ADMIN, USER_ADMIN
from apps.accounts.services import (
    clear_email_bounce,
    make_email_verification_token,
    make_reset_token,
    update_account,
    verify_email,
)
from apps.members.roles_report import ROLES_REPORT
from tests.conftest import GOOD_PASSWORD, RESET_CONFIRM_URL, audit_messages, role_matrix
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

DETAIL = "5.1.1 550 5.1.1 User unknown"
BOUNCED_AT = datetime(2026, 10, 1, 18, 0, tzinfo=UTC)
USERS_URL = "/api/v1/admin/users"


@pytest.fixture
def bounced(db: None) -> User:
    """A verified member whose address bounced on October 1st, 2026."""
    return UserFactory(
        email="gone@example.com",
        first_name="Dana",
        last_name="Doe",
        email_bounced_at=BOUNCED_AT,
        email_bounce_detail=DETAIL,
    )


@pytest.fixture
def user_admin_client(api_client: APIClient, user_admin: User) -> APIClient:
    """An API client signed in as the user administrator."""
    api_client.force_login(user_admin)
    return api_client


def _bounce(user: User) -> tuple[datetime | None, str]:
    """``user``'s bounce time and detail as the database holds them."""
    user.refresh_from_db()
    return user.email_bounced_at, user.email_bounce_detail


def _clear_url(user: User) -> str:
    """The user record's ``clear-bounce`` endpoint for ``user``."""
    return f"{USERS_URL}/{user.pk}/clear-bounce"


# --------------------------------------------------------------------------
# Clearing by itself
# --------------------------------------------------------------------------
def test_a_new_address_clears_the_bounce(bounced: User, user_admin: User) -> None:
    """The bounce belonged to the old address, so a new one starts clean."""
    update_account(user_admin, bounced, {"email": "dana@example.org"})

    assert _bounce(bounced) == (None, "")


def test_a_change_of_case_keeps_the_bounce(bounced: User, user_admin: User) -> None:
    """``Gone@Example.com`` is the same address, so it still bounces."""
    update_account(user_admin, bounced, {"email": "Gone@Example.com"})

    assert _bounce(bounced) == (BOUNCED_AT, DETAIL)


def test_an_edit_that_leaves_the_address_keeps_the_bounce(bounced: User, user_admin: User) -> None:
    """Correcting a name says nothing about the address."""
    update_account(user_admin, bounced, {"first_name": "Danielle"})

    assert _bounce(bounced) == (BOUNCED_AT, DETAIL)


def test_verifying_the_address_clears_the_bounce(bounced: User) -> None:
    """Following a verification link proves mail to the address arrives."""
    User.objects.filter(pk=bounced.pk).update(email_verified_at=None)

    verify_email(make_email_verification_token(bounced))

    assert _bounce(bounced) == (None, "")


def test_a_password_link_clears_the_bounce_of_a_verified_address(
    bounced: User, api_client: APIClient
) -> None:
    """A reset link followed on an already-verified account proves the address too."""
    uid, token = make_reset_token(bounced)

    api_client.post(
        RESET_CONFIRM_URL,
        {"uid": uid, "token": token, "new_password": GOOD_PASSWORD},
        format="json",
    )

    assert _bounce(bounced) == (None, "")


# --------------------------------------------------------------------------
# Clear bounce
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("role", "allowed"), role_matrix(USER_ADMIN, SYSTEM_ADMIN))
def test_only_a_user_administrator_clears_a_bounce(
    api_client: APIClient,
    all_role_users: dict[str, User],
    bounced: User,
    role: str,
    allowed: bool,
) -> None:
    """Clearing the flag is the user administrator's, as the rest of the record is."""
    api_client.force_login(all_role_users[role])

    response = api_client.post(_clear_url(bounced))

    assert response.status_code == (200 if allowed else 403)


def test_clear_bounce_answers_the_cleared_user_record(
    user_admin_client: APIClient, bounced: User
) -> None:
    """The answer is the ``/admin/users/{id}`` payload with the bounce gone."""
    body = user_admin_client.post(_clear_url(bounced)).json()

    assert (body["id"], body["email_bounced_at"], body["email_bounce_detail"]) == (
        bounced.pk,
        None,
        "",
    )


def test_clear_bounce_clears_the_stored_flag(user_admin_client: APIClient, bounced: User) -> None:
    """The account's bounce time and detail are emptied."""
    user_admin_client.post(_clear_url(bounced))

    assert _bounce(bounced) == (None, "")


def test_clear_bounce_is_audited(
    bounced: User, user_admin: User, audit_log: pytest.LogCaptureFixture
) -> None:
    """Clearing writes one ``account.bounce_cleared`` line naming actor and account."""
    clear_email_bounce(user_admin, bounced)

    assert audit_messages(audit_log) == [
        f"action=account.bounce_cleared actor={user_admin.pk} target={bounced.pk}"
    ]


def test_clearing_no_bounce_records_nothing(
    user_admin: User, member: User, audit_log: pytest.LogCaptureFixture
) -> None:
    """An account with nothing to clear is left alone, and no line is written."""
    clear_email_bounce(user_admin, member)

    assert audit_messages(audit_log) == []


def test_clearing_an_unknown_account_is_a_404(user_admin_client: APIClient) -> None:
    """An id no account has is not found."""
    response = user_admin_client.post(f"{USERS_URL}/999999/clear-bounce")

    assert response.status_code == 404


# --------------------------------------------------------------------------
# Showing and filtering
# --------------------------------------------------------------------------
def test_the_user_record_shows_the_bounce(user_admin_client: APIClient, bounced: User) -> None:
    """``GET /admin/users/{id}`` carries when and why the address bounced."""
    body = user_admin_client.get(f"{USERS_URL}/{bounced.pk}").json()

    assert (body["email_bounced_at"], body["email_bounce_detail"]) == (
        "2026-10-01T11:00:00-07:00",
        DETAIL,
    )


def test_the_member_record_shows_the_bounce(
    api_client: APIClient, all_role_users: dict[str, User], bounced: User
) -> None:
    """``GET /admin/members/{id}`` carries the same two fields."""
    api_client.force_login(all_role_users[ACCOUNT_ADMIN])

    body = api_client.get(f"/api/v1/admin/members/{bounced.pk}").json()

    assert (body["email_bounced_at"], body["email_bounce_detail"]) == (
        "2026-10-01T11:00:00-07:00",
        DETAIL,
    )


def test_a_user_administrator_cannot_patch_the_bounce(
    user_admin_client: APIClient, bounced: User
) -> None:
    """The flag is read-only on the user record: only the action clears it."""
    user_admin_client.patch(
        f"{USERS_URL}/{bounced.pk}",
        {"email_bounced_at": None, "email_bounce_detail": ""},
        format="json",
    )

    assert _bounce(bounced) == (BOUNCED_AT, DETAIL)


def _listed(client: APIClient, **query: Any) -> list[str]:
    """The addresses ``GET /admin/users`` lists for ``query``."""
    return [row["email"] for row in client.get(USERS_URL, query).json()["results"]]


@pytest.mark.parametrize(
    ("value", "expected"),
    [("true", ["gone@example.com"]), ("false", ["fine@example.com"])],
    ids=["bounced", "not-bounced"],
)
def test_the_users_list_filters_on_a_bounced_address(
    user_admin_client: APIClient, bounced: User, value: str, expected: list[str]
) -> None:
    """``email_bounced=true`` lists the bounced accounts, ``false`` the rest."""
    UserFactory(email="fine@example.com")

    listed = _listed(user_admin_client, email_bounced=value, search="example.com")

    assert listed == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [("true", ["gone@example.com"]), ("false", ["fine@example.com"])],
    ids=["bounced", "not-bounced"],
)
def test_the_roles_report_filters_on_a_bounced_address(
    bounced: User, value: str, expected: list[str]
) -> None:
    """The roles report's ``email_bounced`` keeps the same accounts the list does."""
    bounced.add_role(DART_LEADER)
    UserFactory(email="fine@example.com", roles=[DART_LEADER])

    rows = ROLES_REPORT.query({"email_bounced": value, "role": DART_LEADER}).rows

    assert [row.user.email for row in rows] == expected
