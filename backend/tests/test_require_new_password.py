"""The user record's **Require a new password**.

With ``POST /admin/users/{id}/require-new-password`` a user administrator replaces an
account's password with an unusable one, ends every session signed in to it, and mails
its address a reset link, so whoever knew the old password is shut out and the owner
chooses a new one.  The API contract is ``docs/developer/api-auth.rst``.
"""

from __future__ import annotations

import logging
import re

import pytest
from django.core import mail
from rest_framework.test import APIClient

from apps.accounts.models import AccountChangeKind, AccountKind, User
from apps.accounts.roles import SYSTEM_ADMIN, USER_ADMIN
from apps.accounts.services import make_reset_token
from apps.members.services import tombstone_for
from tests.conftest import (
    GOOD_PASSWORD,
    LOGIN_URL,
    ME_URL,
    RESET_CONFIRM_URL,
    audit_messages,
    role_matrix,
)
from tests.factories import DEFAULT_PASSWORD, UserFactory

pytestmark = pytest.mark.django_db

REACTIVATE_URL = "/api/v1/auth/reactivate"

DONOR_REFUSED = {"detail": "A donor cannot sign in, so there is no password to replace."}
SELF_REFUSED = {
    "detail": "You cannot require a new password for your own account. Use Change password instead."
}
ROLES_REFUSED = {
    "detail": "You cannot require a new password for an account that holds roles you do not hold."
}
MAIL_REFUSED = {
    "detail": "The old password no longer works and every session is ended, but the mail "
    "server did not accept the reset email. A system administrator can see the attempt "
    "on the Sent emails page; press Require a new password again once it is fixed."
}

#: The reset link a message carries, with its two query parameters.
RESET_LINK = re.compile(
    r"/portal/reset-password\?uid=(?P<uid>[^&\s]+)&(?:amp;)?token=(?P<token>\S+)"
)


def require_url(user: User) -> str:
    """The ``require-new-password`` endpoint for ``user``."""
    return f"/api/v1/admin/users/{user.pk}/require-new-password"


def fresh(user: User) -> User:
    """``user`` as the database now holds it."""
    user.refresh_from_db()
    return user


def deactivated(user: User, *, blocked: bool = False) -> User:
    """``user`` with the account deactivated, and blocked from reactivating if asked."""
    user.is_active = False
    user.reactivation_blocked = blocked
    user.save(update_fields=["is_active", "reactivation_blocked"])
    return user


def mailed_link(text: str) -> dict[str, str]:
    """The ``uid`` and ``token`` of the first reset link in ``text``."""
    match = RESET_LINK.search(text)
    assert match is not None, text
    return {"uid": match["uid"], "token": match["token"]}


@pytest.fixture
def target(db: None) -> User:
    """A plain member whose password somebody else may know."""
    return UserFactory(email="target@example.test", first_name="Tess", last_name="Arden")


@pytest.fixture
def user_admin_client(api_client: APIClient, user_admin: User) -> APIClient:
    """An API client signed in as the user administrator."""
    api_client.force_login(user_admin)
    return api_client


# --------------------------------------------------------------------------
# Who may call
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("role", "allowed"), role_matrix(USER_ADMIN, SYSTEM_ADMIN))
def test_only_a_user_administrator_requires_a_new_password(
    api_client: APIClient,
    all_role_users: dict[str, User],
    target: User,
    role: str,
    allowed: bool,
) -> None:
    """A user or system administrator may; every other role is 403."""
    api_client.force_login(all_role_users[role])
    assert api_client.post(require_url(target)).status_code == (200 if allowed else 403)


@pytest.mark.parametrize(("role", "allowed"), role_matrix(USER_ADMIN, SYSTEM_ADMIN))
def test_a_refused_role_leaves_the_password_alone(
    api_client: APIClient,
    all_role_users: dict[str, User],
    target: User,
    role: str,
    allowed: bool,
) -> None:
    """Only an allowed caller's request changes the password."""
    api_client.force_login(all_role_users[role])
    api_client.post(require_url(target))
    assert fresh(target).has_usable_password() is not allowed


def test_an_anonymous_caller_is_401(api_client: APIClient, target: User) -> None:
    """Nobody signed out may require a new password."""
    assert api_client.post(require_url(target)).status_code == 401


def test_an_unknown_account_is_404(user_admin_client: APIClient) -> None:
    """An id no account has is a 404."""
    assert (
        user_admin_client.post("/api/v1/admin/users/999999/require-new-password").status_code == 404
    )


# --------------------------------------------------------------------------
# What it does
# --------------------------------------------------------------------------
def test_the_answer_names_the_address_the_link_went_to(
    user_admin_client: APIClient, target: User
) -> None:
    """The 200 says every session is ended and where the reset email went."""
    response = user_admin_client.post(require_url(target))
    assert response.json() == {
        "detail": "The old password no longer works and every session is ended. "
        "A password reset email went to target@example.test."
    }


def test_the_password_becomes_unusable(user_admin_client: APIClient, target: User) -> None:
    """The account holds no usable password afterwards."""
    user_admin_client.post(require_url(target))
    assert fresh(target).has_usable_password() is False


def test_the_old_password_no_longer_signs_in(user_admin_client: APIClient, target: User) -> None:
    """Signing in with the password the account had is refused."""
    user_admin_client.post(require_url(target))
    response = APIClient().post(
        LOGIN_URL, {"email": target.email, "password": DEFAULT_PASSWORD}, format="json"
    )
    assert response.status_code == 400


def test_a_session_signed_in_before_no_longer_authenticates(
    user_admin_client: APIClient, target: User
) -> None:
    """A browser already signed in to the account is signed out at once."""
    theirs = APIClient()
    theirs.force_login(target)
    assert theirs.get(ME_URL).status_code == 200

    user_admin_client.post(require_url(target))

    assert theirs.get(ME_URL).status_code == 401


def test_the_administrators_own_session_survives(
    user_admin_client: APIClient, target: User
) -> None:
    """Only the target's sessions are ended."""
    user_admin_client.post(require_url(target))
    assert user_admin_client.get(ME_URL).status_code == 200


def test_the_account_is_mailed_a_reset_link(user_admin_client: APIClient, target: User) -> None:
    """One message, the ordinary reset email, goes to the account's address."""
    user_admin_client.post(require_url(target))
    assert [(message.to, message.subject) for message in mail.outbox] == [
        (["target@example.test"], "CalDART: reset your password")
    ]


def test_the_mailed_link_sets_the_new_password(user_admin_client: APIClient, target: User) -> None:
    """Following the link lets the owner choose a password, which then signs in."""
    user_admin_client.post(require_url(target))
    link = mailed_link(str(mail.outbox[0].body))
    APIClient().post(RESET_CONFIRM_URL, {**link, "new_password": GOOD_PASSWORD}, format="json")
    assert fresh(target).check_password(GOOD_PASSWORD) is True


def test_a_reset_link_issued_before_no_longer_works(
    user_admin_client: APIClient, target: User
) -> None:
    """A link made for the old password is spent once the password is replaced."""
    uid, token = make_reset_token(target)
    user_admin_client.post(require_url(target))
    response = APIClient().post(
        RESET_CONFIRM_URL,
        {"uid": uid, "token": token, "new_password": GOOD_PASSWORD},
        format="json",
    )
    assert response.status_code == 400


def test_the_change_is_audited_under_the_administrator(
    user_admin_client: APIClient,
    user_admin: User,
    target: User,
    audit_log: pytest.LogCaptureFixture,
) -> None:
    """One INFO line records who required the new password of which account."""
    user_admin_client.post(require_url(target))
    assert audit_messages(audit_log, logging.INFO) == [
        f"action=account.new_password actor={user_admin.pk} target={target.pk}"
    ]


def test_the_change_is_in_the_accounts_history(
    user_admin_client: APIClient, user_admin: User, target: User
) -> None:
    """The user record's History card lists it under the administrator."""
    user_admin_client.post(require_url(target))
    assert [(row.kind, row.changed_by) for row in target.account_changes.all()] == [
        (AccountChangeKind.NEW_PASSWORD, user_admin)
    ]


def test_it_can_be_required_again(user_admin_client: APIClient, target: User) -> None:
    """A second request answers 200 too, and mails a second link."""
    user_admin_client.post(require_url(target))
    response = user_admin_client.post(require_url(target))
    assert (response.status_code, len(mail.outbox)) == (200, 2)


# --------------------------------------------------------------------------
# A deactivated account
# --------------------------------------------------------------------------
def test_a_deactivated_account_stays_deactivated(
    user_admin_client: APIClient, target: User
) -> None:
    """Requiring a new password does not bring a deactivated account back."""
    user_admin_client.post(require_url(deactivated(target)))
    assert fresh(target).is_active is False


def test_a_deactivated_account_is_mailed_the_link(
    user_admin_client: APIClient, target: User
) -> None:
    """The owner of a deactivated account is mailed the reset link all the same."""
    user_admin_client.post(require_url(deactivated(target)))
    assert [message.to for message in mail.outbox] == [["target@example.test"]]


def test_the_old_password_no_longer_reactivates(user_admin_client: APIClient, target: User) -> None:
    """``/auth/reactivate`` with the password the account had is refused."""
    user_admin_client.post(require_url(deactivated(target)))
    response = APIClient().post(
        REACTIVATE_URL, {"email": target.email, "password": DEFAULT_PASSWORD}, format="json"
    )
    assert response.status_code == 400


def test_the_owner_reactivates_by_following_the_link(
    user_admin_client: APIClient, target: User
) -> None:
    """Choosing a password from the link reactivates the account, as any reset does."""
    user_admin_client.post(require_url(deactivated(target)))
    link = mailed_link(str(mail.outbox[0].body))
    APIClient().post(RESET_CONFIRM_URL, {**link, "new_password": GOOD_PASSWORD}, format="json")
    assert fresh(target).is_active is True


def test_a_blocked_account_is_answered_without_a_mail(
    user_admin_client: APIClient, target: User
) -> None:
    """A blocked account's password is replaced, and the answer says no email went."""
    response = user_admin_client.post(require_url(deactivated(target, blocked=True)))
    assert response.json() == {
        "detail": "The old password no longer works and every session is ended. "
        "The account is blocked from reactivating, so no reset email was sent."
    }


def test_a_blocked_account_is_sent_nothing(user_admin_client: APIClient, target: User) -> None:
    """No reset link goes to a blocked account, which could not use it."""
    user_admin_client.post(require_url(deactivated(target, blocked=True)))
    assert mail.outbox == []


def test_a_blocked_accounts_password_is_replaced(
    user_admin_client: APIClient, target: User
) -> None:
    """Lifting the block later does not bring the old password back."""
    user_admin_client.post(require_url(deactivated(target, blocked=True)))
    assert fresh(target).has_usable_password() is False


# --------------------------------------------------------------------------
# Refusals
# --------------------------------------------------------------------------
def test_a_donor_is_refused(user_admin_client: APIClient) -> None:
    """A donor cannot sign in, so there is nothing to replace."""
    donor = UserFactory(email="giver@example.test", kind=AccountKind.DONOR, roles=[])
    response = user_admin_client.post(require_url(donor))
    assert (response.status_code, response.json()) == (400, DONOR_REFUSED)


def test_a_tombstone_is_refused(user_admin_client: APIClient, target: User) -> None:
    """The account that keeps a deleted member's payments is a donor, and refused."""
    tombstone = tombstone_for(target)
    response = user_admin_client.post(require_url(tombstone))
    assert (response.status_code, response.json()) == (400, DONOR_REFUSED)


def test_your_own_account_is_refused(user_admin_client: APIClient, user_admin: User) -> None:
    """An administrator changes their own password on Change password."""
    response = user_admin_client.post(require_url(user_admin))
    assert (response.status_code, response.json()) == (400, SELF_REFUSED)


def test_an_account_holding_roles_you_lack_is_refused(
    user_admin_client: APIClient, account_admin: User
) -> None:
    """The account-edit guard applies: the caller holds every role the target holds."""
    response = user_admin_client.post(require_url(account_admin))
    assert (response.status_code, response.json()) == (400, ROLES_REFUSED)


def test_a_refusal_changes_nothing(user_admin_client: APIClient, account_admin: User) -> None:
    """A refused request leaves the password and sends no mail."""
    user_admin_client.post(require_url(account_admin))
    assert (fresh(account_admin).has_usable_password(), mail.outbox) == (True, [])


def test_a_system_administrator_may_act_on_anybody(
    system_admin_client: APIClient, account_admin: User
) -> None:
    """A system administrator holds every role, so the guard always passes."""
    assert system_admin_client.post(require_url(account_admin)).status_code == 200


@pytest.mark.parametrize(
    ("who", "reason"),
    [("donor", "donor_account"), ("self", "own_account"), ("roles", "roles_not_held")],
)
def test_each_refusal_is_audited_with_its_reason(
    user_admin_client: APIClient,
    user_admin: User,
    account_admin: User,
    audit_log: pytest.LogCaptureFixture,
    who: str,
    reason: str,
) -> None:
    """A refusal writes one WARNING line naming the rule that refused it."""
    subject = {
        "donor": UserFactory(email="giver@example.test", kind=AccountKind.DONOR, roles=[]),
        "self": user_admin,
        "roles": account_admin,
    }[who]
    user_admin_client.post(require_url(subject))
    assert audit_messages(audit_log, logging.WARNING) == [
        f"action=account.new_password actor={user_admin.pk} target={subject.pk} reason={reason}"
    ]


# --------------------------------------------------------------------------
# A mail server that refuses
# --------------------------------------------------------------------------
@pytest.mark.usefixtures("refusing_mail_server")
def test_a_refused_mail_is_a_503(user_admin_client: APIClient, target: User) -> None:
    """The administrator is told the email did not go, and how to try again."""
    response = user_admin_client.post(require_url(target))
    assert (response.status_code, response.json()) == (503, MAIL_REFUSED)


@pytest.mark.usefixtures("refusing_mail_server")
def test_a_refused_mail_still_shuts_the_old_password_out(
    user_admin_client: APIClient, target: User
) -> None:
    """The password is replaced whether or not the email went."""
    user_admin_client.post(require_url(target))
    assert fresh(target).has_usable_password() is False
