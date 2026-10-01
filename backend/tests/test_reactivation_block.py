"""Blocking an account from reactivating itself.

A user administrator sets ``reactivation_blocked`` with ``POST /admin/users/{id}/block``
and clears it with ``/unblock``.  While it is set the account stays deactivated:
signing in, ``POST /auth/reactivate``, a password reset, and registering again with
the address all tell the owner the account has been closed, and no administrator
reactivates it.  The API contract is ``docs/developer/api-auth.rst``.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.core import mail
from rest_framework.test import APIClient

from apps.accounts.models import AccountKind, User
from apps.accounts.roles import SYSTEM_ADMIN, USER_ADMIN
from apps.accounts.services import make_reset_token
from apps.cms.models import SiteSettings
from apps.members.models import MembershipPlan, MembershipStatusChoices
from tests.conftest import (
    GOOD_PASSWORD,
    LOGIN_URL,
    REGISTER_URL,
    RESET_CONFIRM_URL,
    RESET_URL,
    audit_messages,
    register_payload,
    role_matrix,
)
from tests.factories import DEFAULT_PASSWORD, UserFactory, grant_membership

pytestmark = pytest.mark.django_db

REACTIVATE_URL = "/api/v1/auth/reactivate"

CLOSED = "This account has been closed. Contact CalDART to reopen it."
WRONG_CREDENTIALS = {"detail": "Incorrect email address or password."}
ADMIN_BLOCKED = {
    "detail": "A user administrator has blocked this account from reactivating. "
    "Allow reactivation on its user record first."
}
SELF_BLOCK = {"detail": "You cannot block your own account."}
ROLES_BLOCK = {"detail": "You cannot block or unblock an account that holds roles you do not hold."}
DONOR_BLOCK = {"detail": "A donor has no portal account to block."}


def block_url(user: User, action: str = "block") -> str:
    """The user record's ``block`` or ``unblock`` endpoint for ``user``."""
    return f"/api/v1/admin/users/{user.pk}/{action}"


def post(client: APIClient, url: str, **body: object) -> tuple[int, dict[str, Any]]:
    """Post ``body`` to ``url`` and return the status and the JSON."""
    response = client.post(url, body, format="json")
    return response.status_code, response.json()


def fresh(user: User) -> User:
    """``user`` as the database now holds it."""
    user.refresh_from_db()
    return user


@pytest.fixture
def user_admin_client(api_client: APIClient, user_admin: User) -> APIClient:
    """An API client signed in as the user administrator."""
    api_client.force_login(user_admin)
    return api_client


@pytest.fixture
def target(db: None) -> User:
    """A plain member, signed in to nothing."""
    return UserFactory(email="target@example.test", first_name="Tess", last_name="Arden")


@pytest.fixture
def blocked(target: User) -> User:
    """``target``, deactivated and blocked from reactivating."""
    target.is_active = False
    target.reactivation_blocked = True
    target.save(update_fields=["is_active", "reactivation_blocked"])
    return target


# --------------------------------------------------------------------------
# Setting and clearing the block
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("role", "allowed"), role_matrix(USER_ADMIN, SYSTEM_ADMIN))
def test_only_a_user_administrator_blocks(
    api_client: APIClient,
    all_role_users: dict[str, User],
    target: User,
    role: str,
    allowed: bool,
) -> None:
    """The account administrator is refused too: blocking is the user administrator's."""
    api_client.force_login(all_role_users[role])
    status, _ = post(api_client, block_url(target))
    assert status == (200 if allowed else 403)


@pytest.mark.parametrize(("role", "allowed"), role_matrix(USER_ADMIN, SYSTEM_ADMIN))
def test_only_a_user_administrator_unblocks(
    api_client: APIClient,
    all_role_users: dict[str, User],
    blocked: User,
    role: str,
    allowed: bool,
) -> None:
    """Lifting the block is the user administrator's alone as well."""
    api_client.force_login(all_role_users[role])
    status, _ = post(api_client, block_url(blocked, "unblock"))
    assert status == (200 if allowed else 403)


def test_blocking_answers_the_user_record(user_admin_client: APIClient, target: User) -> None:
    """The answer is the user record, blocked."""
    status, body = post(user_admin_client, block_url(target))
    assert (status, body["reactivation_blocked"]) == (200, True)


def test_blocking_an_active_account_deactivates_it(
    user_admin_client: APIClient, target: User
) -> None:
    """A block is never set on an account that can still sign in."""
    post(user_admin_client, block_url(target))
    assert fresh(target).is_active is False


def test_blocking_an_active_account_suspends_its_membership(
    user_admin_client: APIClient, target: User, annual_plan: MembershipPlan
) -> None:
    """The deactivation is the whole of one, terms included."""
    covering = grant_membership(target, annual_plan)
    post(user_admin_client, block_url(target))
    covering.refresh_from_db()
    assert covering.status == MembershipStatusChoices.SUSPENDED


def test_blocking_is_recorded(
    user_admin_client: APIClient,
    user_admin: User,
    target: User,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """The deactivation and the block are each a line under the administrator."""
    post(user_admin_client, block_url(target))
    assert audit_messages(audit_log) == [
        f"action=account.deactivate actor={user_admin.pk} target={target.pk}",
        f"action=account.block actor={user_admin.pk} target={target.pk}",
    ]


def test_blocking_a_blocked_account_records_nothing(
    user_admin_client: APIClient, blocked: User, audit_log: pytest.LogCaptureFixture
) -> None:
    """Asking twice changes nothing."""
    post(user_admin_client, block_url(blocked))
    assert audit_messages(audit_log) == []


def test_unblocking_clears_the_flag(user_admin_client: APIClient, blocked: User) -> None:
    """The answer is the user record, no longer blocked."""
    status, body = post(user_admin_client, block_url(blocked, "unblock"))
    assert (status, body["reactivation_blocked"]) == (200, False)


def test_unblocking_leaves_the_account_deactivated(
    user_admin_client: APIClient, blocked: User
) -> None:
    """Reopening it is the owner's to do."""
    post(user_admin_client, block_url(blocked, "unblock"))
    assert fresh(blocked).is_active is False


def test_unblocking_is_recorded(
    user_admin_client: APIClient,
    user_admin: User,
    blocked: User,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """``account.unblock`` names the administrator."""
    post(user_admin_client, block_url(blocked, "unblock"))
    assert audit_messages(audit_log) == [
        f"action=account.unblock actor={user_admin.pk} target={blocked.pk}"
    ]


def test_an_administrator_cannot_block_themselves(
    user_admin_client: APIClient, user_admin: User
) -> None:
    """Your own account is refused."""
    assert post(user_admin_client, block_url(user_admin)) == (400, SELF_BLOCK)


def test_an_account_holding_roles_you_lack_cannot_be_blocked(
    user_admin_client: APIClient, account_admin: User
) -> None:
    """The account-edit guard holds: an account administrator is beyond a user one."""
    assert post(user_admin_client, block_url(account_admin)) == (400, ROLES_BLOCK)


def test_a_refused_block_is_recorded(
    user_admin_client: APIClient,
    user_admin: User,
    account_admin: User,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """The refusal is written with the ``roles_not_held`` reason."""
    post(user_admin_client, block_url(account_admin))
    assert audit_messages(audit_log) == [
        f"action=account.block actor={user_admin.pk} target={account_admin.pk} "
        "reason=roles_not_held"
    ]


def test_a_refused_block_leaves_the_account_active(
    user_admin_client: APIClient, account_admin: User
) -> None:
    """Nothing is deactivated when the block is refused."""
    post(user_admin_client, block_url(account_admin))
    assert fresh(account_admin).is_active is True


def test_a_donor_cannot_be_blocked(user_admin_client: APIClient) -> None:
    """A donor has no portal account."""
    giver = UserFactory(email="giver@example.test", kind=AccountKind.DONOR, roles=[])
    assert post(user_admin_client, block_url(giver)) == (400, DONOR_BLOCK)


# --------------------------------------------------------------------------
# What the owner of a blocked account meets
# --------------------------------------------------------------------------
def test_signing_in_is_told_the_account_is_closed(api_client: APIClient, blocked: User) -> None:
    """The right password gets the closed sentence, with no offer to reactivate."""
    assert post(api_client, LOGIN_URL, email=blocked.email, password=DEFAULT_PASSWORD) == (
        403,
        {"detail": CLOSED},
    )


def test_a_wrong_password_learns_nothing(api_client: APIClient, blocked: User) -> None:
    """Without the password the answer is the ordinary refusal."""
    guess = {"email": blocked.email, "password": "not-it"}
    assert post(api_client, LOGIN_URL, **guess) == (400, WRONG_CREDENTIALS)


def test_the_closed_sentence_names_the_organization(
    api_client: APIClient, blocked: User, site_settings: SiteSettings
) -> None:
    """The name comes from the site settings."""
    site_settings.org_name = "Sierra DART"
    site_settings.save()
    _, body = post(api_client, LOGIN_URL, email=blocked.email, password=DEFAULT_PASSWORD)
    assert body == {"detail": "This account has been closed. Contact Sierra DART to reopen it."}


def test_reactivating_is_refused(api_client: APIClient, blocked: User) -> None:
    """``/auth/reactivate`` gives the closed sentence."""
    assert post(api_client, REACTIVATE_URL, email=blocked.email, password=DEFAULT_PASSWORD) == (
        403,
        {"detail": CLOSED},
    )


def test_a_refused_reactivation_leaves_the_account_deactivated(
    api_client: APIClient, blocked: User
) -> None:
    """Nothing changes."""
    post(api_client, REACTIVATE_URL, email=blocked.email, password=DEFAULT_PASSWORD)
    assert fresh(blocked).is_active is False


def test_a_reset_request_sends_no_mail(api_client: APIClient, blocked: User) -> None:
    """The answer is the usual 204, and nothing is mailed."""
    response = api_client.post(RESET_URL, {"email": blocked.email}, format="json")
    assert (response.status_code, len(mail.outbox)) == (204, 0)


def test_completing_an_earlier_reset_link_is_refused(api_client: APIClient, blocked: User) -> None:
    """A link mailed before the block is told the account is closed."""
    uid, token = make_reset_token(blocked)
    status, body = post(
        api_client, RESET_CONFIRM_URL, uid=uid, token=token, new_password=GOOD_PASSWORD
    )
    assert (status, body) == (400, {"token": [CLOSED]})


def test_a_refused_reset_sets_no_password(api_client: APIClient, blocked: User) -> None:
    """The old password still holds, and the account stays deactivated."""
    uid, token = make_reset_token(blocked)
    post(api_client, RESET_CONFIRM_URL, uid=uid, token=token, new_password=GOOD_PASSWORD)
    blocked = fresh(blocked)
    assert (blocked.check_password(DEFAULT_PASSWORD), blocked.is_active) == (True, False)


def test_registering_again_is_refused(api_client: APIClient, blocked: User) -> None:
    """The address is refused with the closed sentence and no reactivation code."""
    status, body = post(
        api_client, REGISTER_URL, **register_payload(email=blocked.email, password=GOOD_PASSWORD)
    )
    assert (status, body) == (400, {"email": [CLOSED]})


def test_an_account_administrator_cannot_reactivate_it(
    api_client: APIClient, account_admin: User, blocked: User
) -> None:
    """The member record's reactivation is refused while the block holds."""
    api_client.force_login(account_admin)
    status, body = post(api_client, f"/api/v1/admin/members/{blocked.pk}/reactivate")
    assert (status, body) == (400, ADMIN_BLOCKED)


def test_a_refused_administrator_reactivation_is_recorded(
    api_client: APIClient,
    account_admin: User,
    blocked: User,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """The refusal is written with the ``reactivation_blocked`` reason."""
    api_client.force_login(account_admin)
    api_client.post(f"/api/v1/admin/members/{blocked.pk}/reactivate")
    assert audit_messages(audit_log) == [
        f"action=account.activate actor={account_admin.pk} target={blocked.pk} "
        "reason=reactivation_blocked"
    ]


def test_once_unblocked_the_owner_is_offered_reactivation(
    user_admin_client: APIClient, blocked: User
) -> None:
    """Signing in after the block is lifted is the ordinary deactivated answer."""
    post(user_admin_client, block_url(blocked, "unblock"))
    user_admin_client.logout()
    status, body = post(
        user_admin_client, LOGIN_URL, email=blocked.email, password=DEFAULT_PASSWORD
    )
    assert (status, body["code"]) == (403, "deactivated")
