"""An account's history: who granted or took away its roles, and who changed its status.

Each change the user record's History card lists is kept as an ``AccountChange`` row
beside its audit line: an account an administrator created, a role change, and an
account deactivated, reactivated, blocked from reactivating, or allowed to reactivate.
``GET /admin/users/{id}/history`` reads them back for a user administrator.  The API
contract is ``docs/developer/api-auth.rst``.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import AccountChange, AccountChangeKind, User
from apps.accounts.roles import (
    DART_LEADER,
    MEMBER,
    SYSTEM_ADMIN,
    TREASURER,
    USER_ADMIN,
    VERIFIER,
)
from apps.accounts.services import update_account
from apps.accounts.status import (
    deactivate_account,
    deactivate_own_account,
    reactivate_account,
    reactivate_own_account,
    set_reactivation_blocked,
)
from apps.members.services import create_member
from caldart import audit
from tests.conftest import role_matrix
from tests.factories import UserFactory

pytestmark = pytest.mark.django_db

USERS_URL = "/api/v1/admin/users"


def history_url(user: User | int) -> str:
    """``/admin/users/{id}/history`` for ``user`` or a bare id."""
    pk = user if isinstance(user, int) else user.pk
    return f"{USERS_URL}/{pk}/history"


def kinds(user: User) -> list[str]:
    """The kinds of ``user``'s history entries, oldest first."""
    return list(user.account_changes.order_by("changed_at", "id").values_list("kind", flat=True))


# --------------------------------------------------------------------------
# What writes an entry
# --------------------------------------------------------------------------
def test_a_role_change_records_what_was_added_and_removed(user_admin: User, member: User) -> None:
    """Two roles granted, then one taken away, are two entries naming each role."""
    update_account(user_admin, member, {"roles": [MEMBER, TREASURER, VERIFIER]})
    update_account(user_admin, member, {"roles": [MEMBER, TREASURER]})
    first, second = member.account_changes.order_by("id")
    assert (first.kind, first.added, first.removed) == ("roles", [VERIFIER, TREASURER], [])
    assert (second.kind, second.added, second.removed) == ("roles", [], [VERIFIER])


def test_a_role_change_names_the_administrator_who_made_it(user_admin: User, member: User) -> None:
    """The entry's ``changed_by`` is the account that saved the roles."""
    update_account(user_admin, member, {"roles": [MEMBER, DART_LEADER]})
    assert member.account_changes.get().changed_by == user_admin


def test_an_edit_that_leaves_the_roles_alone_records_nothing(
    user_admin: User, member: User
) -> None:
    """A save that resends the roles the account holds writes no history."""
    update_account(user_admin, member, {"roles": [MEMBER], "first_name": "Robin"})
    assert member.account_changes.count() == 0


def test_a_command_role_change_is_recorded_under_no_account(member: User) -> None:
    """A management command's change is stored with no ``changed_by``."""
    update_account(audit.COMMAND_ACTOR, member, {"roles": [MEMBER, VERIFIER]})
    assert member.account_changes.get().changed_by is None


def test_a_command_role_change_is_marked_as_the_commands(member: User) -> None:
    """A command's change is told apart from a deleted actor's by ``by_command``."""
    update_account(audit.COMMAND_ACTOR, member, {"roles": [MEMBER, VERIFIER]})
    assert member.account_changes.get().by_command is True


def test_deactivating_and_reactivating_are_recorded(user_admin: User, member: User) -> None:
    """An administrator's deactivation and reactivation each write an entry."""
    deactivate_account(user_admin, member)
    reactivate_account(user_admin, member)
    assert kinds(member) == [AccountChangeKind.DEACTIVATED, AccountChangeKind.REACTIVATED]


def test_the_owners_own_deactivation_is_recorded_under_their_name(member: User) -> None:
    """A member who deactivates and reactivates their own account is the actor of both."""
    deactivate_own_account(member)
    reactivate_own_account(member)
    actors = set(member.account_changes.values_list("changed_by", flat=True))
    assert actors == {member.pk}


def test_blocking_and_allowing_reactivation_are_recorded(user_admin: User, member: User) -> None:
    """Setting and lifting the block each write an entry."""
    deactivate_account(user_admin, member)
    set_reactivation_blocked(user_admin, member, blocked=True)
    set_reactivation_blocked(user_admin, member, blocked=False)
    assert kinds(member) == [
        AccountChangeKind.DEACTIVATED,
        AccountChangeKind.BLOCKED,
        AccountChangeKind.UNBLOCKED,
    ]


def test_a_block_already_set_records_nothing_more(user_admin: User, member: User) -> None:
    """Blocking an account already blocked changes nothing and writes no second entry."""
    deactivate_account(user_admin, member)
    set_reactivation_blocked(user_admin, member, blocked=True)
    set_reactivation_blocked(user_admin, member, blocked=True)
    assert kinds(member).count(AccountChangeKind.BLOCKED) == 1


def test_an_account_an_administrator_creates_starts_with_a_created_entry(
    account_admin: User,
) -> None:
    """New member records who created the account."""
    user = create_member(account_admin, email="new@example.test", first_name="A", last_name="B")
    entry = user.account_changes.get()
    assert (entry.kind, entry.changed_by) == (AccountChangeKind.CREATED, account_admin)


# --------------------------------------------------------------------------
# The history endpoint
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("slug", "allowed"), role_matrix(USER_ADMIN, SYSTEM_ADMIN))
def test_history_role_matrix(
    api_client: APIClient, all_role_users: dict[str, User], slug: str, allowed: bool
) -> None:
    """Only a user or system administrator may read an account's history."""
    api_client.force_login(all_role_users[slug])
    target = all_role_users[MEMBER]
    assert (api_client.get(history_url(target)).status_code == 200) is allowed


def test_history_lists_the_newest_change_first(
    api_client: APIClient, user_admin: User, member: User
) -> None:
    """The entries come back newest first, each with its actor's id and name."""
    deactivate_account(user_admin, member)
    update_account(user_admin, member, {"roles": [MEMBER, VERIFIER]})
    api_client.force_login(user_admin)
    body = api_client.get(history_url(member)).json()
    assert [(row["kind"], row["changed_by"]) for row in body] == [
        ("roles", {"id": user_admin.pk, "name": "Sam Pryor"}),
        ("deactivated", {"id": user_admin.pk, "name": "Sam Pryor"}),
    ]


def test_history_carries_the_roles_a_change_granted(
    api_client: APIClient, user_admin: User, member: User
) -> None:
    """A roles entry carries the slugs it added and removed."""
    update_account(user_admin, member, {"roles": [MEMBER, VERIFIER]})
    api_client.force_login(user_admin)
    (row,) = api_client.get(history_url(member)).json()
    assert (row["added"], row["removed"]) == ([VERIFIER], [])


def test_a_command_entry_has_no_actor(
    api_client: APIClient, user_admin: User, member: User
) -> None:
    """An entry a management command wrote reads ``changed_by: null``."""
    update_account(audit.COMMAND_ACTOR, member, {"roles": [MEMBER, VERIFIER]})
    api_client.force_login(user_admin)
    (row,) = api_client.get(history_url(member)).json()
    assert (row["changed_by"], row["by_command"]) == (None, True)


def test_an_account_with_no_changes_has_an_empty_history(
    api_client: APIClient, user_admin: User, member: User
) -> None:
    """An account nothing has changed answers an empty list."""
    api_client.force_login(user_admin)
    assert api_client.get(history_url(member)).json() == []


def test_history_of_an_unknown_account_is_404(api_client: APIClient, user_admin: User) -> None:
    """An id no account has answers 404 rather than an empty history."""
    api_client.force_login(user_admin)
    assert api_client.get(history_url(999_999)).status_code == 404


def test_an_actor_since_deleted_leaves_the_entry_behind(member: User) -> None:
    """Deleting the administrator keeps the entry, with no actor."""
    actor = UserFactory(email="gone@example.test", roles=[MEMBER, USER_ADMIN])
    update_account(actor, member, {"roles": [MEMBER, VERIFIER]})
    actor.delete()
    entry = AccountChange.objects.get(user=member)
    assert (entry.changed_by, entry.by_command) == (None, False)
