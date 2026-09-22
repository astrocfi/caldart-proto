"""The users-admin API: list, retrieve, PATCH, password reset.

Every endpoint is checked against the full role matrix, then against the
business rules: role slugs are validated, only a ``system_admin`` may move the
``system_admin`` role, and nobody may deactivate themselves.
"""

from __future__ import annotations

from datetime import date

import pytest
from django.core import mail
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.roles import (
    ACCOUNT_ADMIN,
    DART_LEADER,
    MEMBER,
    ROLE_SLUGS,
    SYSTEM_ADMIN,
    USER_ADMIN,
    WEBSITE_ADMIN,
)
from apps.members.models import MembershipPlan
from tests.conftest import role_matrix
from tests.factories import MembershipFactory, UserFactory

pytestmark = pytest.mark.django_db

LIST = "/api/v1/admin/users"
ROLES = "/api/v1/roles"


def detail(user: User) -> str:
    """``/admin/users/{id}`` for ``user``."""
    return f"{LIST}/{user.pk}"


def send_reset(user: User) -> str:
    """``/admin/users/{id}/send-password-reset`` for ``user``."""
    return f"{LIST}/{user.pk}/send-password-reset"


#: (role slug, may use the users-admin API).
USERS_ADMIN_MATRIX = role_matrix(USER_ADMIN, SYSTEM_ADMIN)


# --------------------------------------------------------------------------
# Role matrix
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("slug", "allowed"), USERS_ADMIN_MATRIX)
def test_list_role_matrix(
    api_client: APIClient, all_role_users: dict[str, User], slug: str, allowed: bool
) -> None:
    """``GET`` the list is 200 only for a user administrator or a system administrator."""
    api_client.force_login(all_role_users[slug])
    assert (api_client.get(LIST).status_code == 200) is allowed


@pytest.mark.parametrize(("slug", "allowed"), USERS_ADMIN_MATRIX)
def test_retrieve_role_matrix(
    api_client: APIClient, all_role_users: dict[str, User], slug: str, allowed: bool, member: User
) -> None:
    """``GET`` one user is 200 only for a user administrator or a system administrator."""
    api_client.force_login(all_role_users[slug])
    assert (api_client.get(detail(member)).status_code == 200) is allowed


@pytest.mark.parametrize(("slug", "allowed"), USERS_ADMIN_MATRIX)
def test_patch_role_matrix(
    api_client: APIClient, all_role_users: dict[str, User], slug: str, allowed: bool, member: User
) -> None:
    """``PATCH`` is 200 only for a user administrator or a system administrator."""
    api_client.force_login(all_role_users[slug])
    response = api_client.patch(detail(member), {"first_name": "Renamed"})
    assert (response.status_code == 200) is allowed


@pytest.mark.parametrize(("slug", "allowed"), USERS_ADMIN_MATRIX)
def test_send_password_reset_role_matrix(
    api_client: APIClient, all_role_users: dict[str, User], slug: str, allowed: bool, member: User
) -> None:
    """Sending a reset is 200 only for a user administrator or a system administrator."""
    api_client.force_login(all_role_users[slug])
    assert (api_client.post(send_reset(member)).status_code == 200) is allowed


@pytest.mark.parametrize("path", [LIST, ROLES])
def test_anonymous_gets_401_not_403(api_client: APIClient, path: str) -> None:
    """An anonymous ``GET`` on either endpoint is 401, not 403."""
    assert api_client.get(path).status_code == 401


def test_anonymous_cannot_patch(api_client: APIClient, member: User) -> None:
    """An anonymous ``PATCH`` is refused with 401."""
    assert api_client.patch(detail(member), {"first_name": "X"}).status_code == 401


# --------------------------------------------------------------------------
# List: shape, search, filters, pagination
# --------------------------------------------------------------------------
def test_list_returns_the_user_payload(
    api_client: APIClient,
    user_admin: User,
    member: User,
    annual_plan: MembershipPlan,
    today: date,
) -> None:
    """A list row carries the documented shape, including roles and membership status."""
    MembershipFactory(user=member, plan=annual_plan, starts_on=today)
    api_client.force_login(user_admin)

    body = api_client.get(LIST).json()
    assert set(body) == {"count", "next", "previous", "results"}
    row = next(r for r in body["results"] if r["email"] == member.email)
    assert set(row) == {
        "id",
        "email",
        "first_name",
        "last_name",
        "roles",
        "is_active",
        "membership",
        "profile_complete",
    }
    assert row["roles"] == [MEMBER]
    assert row["membership"]["status"] == "current"


def test_list_is_ordered_by_name(api_client: APIClient, user_admin: User) -> None:
    """The default list ordering is by name."""
    UserFactory(email="zeta@example.test", first_name="Ann", last_name="Zeta", roles=[MEMBER])
    UserFactory(email="alpha@example.test", first_name="Bo", last_name="Alpha", roles=[MEMBER])
    api_client.force_login(user_admin)

    names = [row["last_name"] for row in api_client.get(LIST).json()["results"]]
    assert names.index("Alpha") < names.index("Zeta")


def test_list_search_matches_email(api_client: APIClient, user_admin: User, member: User) -> None:
    """``search`` matches on the email address."""
    api_client.force_login(user_admin)
    body = api_client.get(LIST, {"search": member.email}).json()
    assert [row["email"] for row in body["results"]] == [member.email]


def test_list_search_matches_a_full_name(api_client: APIClient, user_admin: User) -> None:
    """``search`` matches a first-and-last-name query."""
    UserFactory(email="ada@example.test", first_name="Ada", last_name="Lovelace", roles=[MEMBER])
    UserFactory(email="alan@example.test", first_name="Alan", last_name="Turing", roles=[MEMBER])
    api_client.force_login(user_admin)

    body = api_client.get(LIST, {"search": "Ada Lovelace"}).json()
    assert [row["email"] for row in body["results"]] == ["ada@example.test"]


def test_list_filters_by_role(api_client: APIClient, all_role_users: dict[str, User]) -> None:
    """``role`` filters the list to accounts holding that role."""
    api_client.force_login(all_role_users[USER_ADMIN])
    body = api_client.get(LIST, {"role": DART_LEADER}).json()
    assert [row["email"] for row in body["results"]] == [all_role_users[DART_LEADER].email]


def test_list_rejects_an_unknown_role(api_client: APIClient, user_admin: User) -> None:
    """An unknown ``role`` value is refused with a 400, naming ``role``."""
    api_client.force_login(user_admin)
    response = api_client.get(LIST, {"role": "wizard"})
    assert response.status_code == 400
    assert "role" in response.json()


def test_list_filters_by_is_active(api_client: APIClient, user_admin: User, member: User) -> None:
    """``is_active`` filters the list to active or inactive accounts."""
    member.is_active = False
    member.save(update_fields=["is_active"])
    api_client.force_login(user_admin)

    inactive = api_client.get(LIST, {"is_active": "false"}).json()
    assert [row["email"] for row in inactive["results"]] == [member.email]

    active_emails = [
        row["email"] for row in api_client.get(LIST, {"is_active": "true"}).json()["results"]
    ]
    assert member.email not in active_emails
    assert user_admin.email in active_emails


def test_list_combines_search_and_filters(api_client: APIClient, user_admin: User) -> None:
    """``search`` and ``role`` combine to narrow the list further."""
    match = UserFactory(
        email="hit@example.test", first_name="Rosa", last_name="Vega", roles=[MEMBER, DART_LEADER]
    )
    UserFactory(email="miss@example.test", first_name="Rosa", last_name="Ward", roles=[MEMBER])
    api_client.force_login(user_admin)

    body = api_client.get(LIST, {"search": "Rosa", "role": DART_LEADER}).json()
    assert [row["email"] for row in body["results"]] == [match.email]


def test_list_paginates(api_client: APIClient, user_admin: User) -> None:
    """``page_size`` limits the page, and ``next`` is set when more rows remain."""
    for index in range(8):
        UserFactory(email=f"page{index}@example.test", roles=[MEMBER])
    api_client.force_login(user_admin)

    body = api_client.get(LIST, {"page_size": 3}).json()
    assert len(body["results"]) == 3
    assert body["count"] >= 9
    assert body["next"] is not None


def test_list_can_be_ordered(api_client: APIClient, user_admin: User) -> None:
    """``ordering`` reverses the list when prefixed with ``-``."""
    api_client.force_login(user_admin)
    ascending = api_client.get(LIST, {"ordering": "email"}).json()["results"]
    descending = api_client.get(LIST, {"ordering": "-email"}).json()["results"]
    assert [r["email"] for r in ascending] == list(reversed([r["email"] for r in descending]))


# --------------------------------------------------------------------------
# Retrieve
# --------------------------------------------------------------------------
def test_retrieve_returns_one_user(api_client: APIClient, user_admin: User, member: User) -> None:
    """``GET`` one user returns that user's id and email."""
    api_client.force_login(user_admin)
    body = api_client.get(detail(member)).json()
    assert body["id"] == member.pk
    assert body["email"] == member.email


def test_retrieve_404s_for_an_unknown_id(api_client: APIClient, user_admin: User) -> None:
    """``GET`` an id with no matching user is 404."""
    api_client.force_login(user_admin)
    assert api_client.get(f"{LIST}/99999").status_code == 404


# --------------------------------------------------------------------------
# PATCH: names, email, is_active
# --------------------------------------------------------------------------
def test_patch_updates_names_and_email(
    api_client: APIClient, user_admin: User, member: User
) -> None:
    """A ``PATCH`` updates the names and the email in one request."""
    api_client.force_login(user_admin)
    response = api_client.patch(
        detail(member),
        {"first_name": "Marta", "last_name": "Reyes", "email": "marta.reyes@example.test"},
    )

    assert response.status_code == 200
    member.refresh_from_db()
    assert (member.first_name, member.last_name) == ("Marta", "Reyes")
    assert member.email == "marta.reyes@example.test"


def test_patch_rejects_an_email_another_account_uses(
    api_client: APIClient, user_admin: User, member: User
) -> None:
    """An email already used by another account is refused, naming ``email``."""
    api_client.force_login(user_admin)
    response = api_client.patch(detail(member), {"email": user_admin.email.upper()})
    assert response.status_code == 400
    assert "email" in response.json()
    member.refresh_from_db()
    assert member.email != user_admin.email


def test_patch_can_keep_the_same_email(
    api_client: APIClient, user_admin: User, member: User
) -> None:
    """Resending the account's own email is accepted."""
    api_client.force_login(user_admin)
    assert api_client.patch(detail(member), {"email": member.email}).status_code == 200


def test_patch_deactivates_another_account(
    api_client: APIClient, user_admin: User, member: User
) -> None:
    """A ``PATCH`` can deactivate an account other than the caller's own."""
    api_client.force_login(user_admin)
    response = api_client.patch(detail(member), {"is_active": False})

    assert response.status_code == 200
    assert response.json()["is_active"] is False
    member.refresh_from_db()
    assert member.is_active is False


def test_a_user_cannot_deactivate_themselves(api_client: APIClient, user_admin: User) -> None:
    """A user administrator cannot deactivate their own account."""
    api_client.force_login(user_admin)
    response = api_client.patch(detail(user_admin), {"is_active": False})

    assert response.status_code == 400
    assert "is_active" in response.json()
    user_admin.refresh_from_db()
    assert user_admin.is_active is True


def test_a_system_admin_cannot_deactivate_themselves_either(
    api_client: APIClient, system_admin: User
) -> None:
    """The self-deactivation guard applies to a system administrator too."""
    api_client.force_login(system_admin)
    response = api_client.patch(detail(system_admin), {"is_active": False})
    assert response.status_code == 400
    system_admin.refresh_from_db()
    assert system_admin.is_active is True


def test_a_user_may_reactivate_themselves_noop(api_client: APIClient, user_admin: User) -> None:
    """Sending ``is_active: true`` for yourself is harmless, not an error."""
    api_client.force_login(user_admin)
    assert api_client.patch(detail(user_admin), {"is_active": True}).status_code == 200


# --------------------------------------------------------------------------
# PATCH updates roles
# --------------------------------------------------------------------------
def test_patch_sets_roles(api_client: APIClient, user_admin: User, member: User) -> None:
    """A ``PATCH`` with a ``roles`` list replaces the account's role groups."""
    api_client.force_login(user_admin)
    response = api_client.patch(detail(member), {"roles": [MEMBER, DART_LEADER]})

    assert response.status_code == 200
    assert response.json()["roles"] == [MEMBER, DART_LEADER]
    member.refresh_from_db()
    assert member.roles == [MEMBER, DART_LEADER]


def test_patch_returns_roles_in_privilege_order(
    api_client: APIClient, user_admin: User, member: User
) -> None:
    """The response's ``roles`` list is reordered to the fixed privilege order."""
    api_client.force_login(user_admin)
    response = api_client.patch(detail(member), {"roles": [ACCOUNT_ADMIN, MEMBER, DART_LEADER]})
    assert response.json()["roles"] == [MEMBER, DART_LEADER, ACCOUNT_ADMIN]


def test_patch_can_revoke_every_role(api_client: APIClient, user_admin: User, member: User) -> None:
    """An empty ``roles`` list clears every role from the account."""
    api_client.force_login(user_admin)
    response = api_client.patch(detail(member), {"roles": []})
    assert response.status_code == 200
    member.refresh_from_db()
    assert member.roles == []


def test_patch_rejects_an_unknown_role_slug(
    api_client: APIClient, user_admin: User, member: User
) -> None:
    """An unrecognized role slug is refused, naming ``roles``, and nothing is written."""
    api_client.force_login(user_admin)
    response = api_client.patch(detail(member), {"roles": [MEMBER, "wizard"]})

    assert response.status_code == 400
    assert "roles" in response.json()
    member.refresh_from_db()
    assert member.roles == [MEMBER]


def test_patch_leaves_non_role_groups_alone(
    api_client: APIClient, user_admin: User, member: User
) -> None:
    """A ``roles`` write leaves a non-role Django group on the account untouched."""
    from django.contrib.auth.models import Group

    editors = Group.objects.create(name="wagtail-editors")
    member.groups.add(editors)
    api_client.force_login(user_admin)

    api_client.patch(detail(member), {"roles": [MEMBER, DART_LEADER]})
    assert editors in member.groups.all()


def test_a_user_admin_cannot_grant_system_admin(
    api_client: APIClient, user_admin: User, member: User
) -> None:
    """A user administrator cannot grant the ``system_admin`` role through PATCH."""
    api_client.force_login(user_admin)
    response = api_client.patch(detail(member), {"roles": [MEMBER, SYSTEM_ADMIN]})

    assert response.status_code == 400
    assert "roles" in response.json()
    member.refresh_from_db()
    assert SYSTEM_ADMIN not in member.roles


def test_a_user_admin_cannot_revoke_system_admin(
    api_client: APIClient, user_admin: User, system_admin: User
) -> None:
    """A user administrator cannot revoke the ``system_admin`` role through PATCH."""
    api_client.force_login(user_admin)
    response = api_client.patch(detail(system_admin), {"roles": [MEMBER]})

    assert response.status_code == 400
    system_admin.refresh_from_db()
    assert SYSTEM_ADMIN in system_admin.roles


def test_a_user_admin_may_edit_other_roles_of_a_system_admin(
    api_client: APIClient, user_admin: User, system_admin: User
) -> None:
    """Leaving ``system_admin`` in place is allowed; moving it is not."""
    api_client.force_login(user_admin)
    response = api_client.patch(
        detail(system_admin), {"roles": [MEMBER, DART_LEADER, SYSTEM_ADMIN]}
    )

    assert response.status_code == 200
    system_admin.refresh_from_db()
    assert system_admin.roles == [MEMBER, DART_LEADER, SYSTEM_ADMIN]


def test_a_system_admin_can_grant_system_admin(
    api_client: APIClient, system_admin: User, member: User
) -> None:
    """A system administrator granting ``system_admin`` also sets superuser and staff."""
    api_client.force_login(system_admin)
    response = api_client.patch(detail(member), {"roles": [MEMBER, SYSTEM_ADMIN]})

    assert response.status_code == 200
    member.refresh_from_db()
    assert SYSTEM_ADMIN in member.roles
    assert member.is_superuser is True
    assert member.is_staff is True


def test_revoking_system_admin_drops_the_superuser_flag(
    api_client: APIClient, system_admin: User
) -> None:
    """Revoking ``system_admin`` clears both ``is_superuser`` and ``is_staff``."""
    target = UserFactory(email="ex-root@example.test", roles=[MEMBER, SYSTEM_ADMIN])
    target.is_superuser = target.is_staff = True
    target.save(update_fields=["is_superuser", "is_staff"])
    api_client.force_login(system_admin)

    response = api_client.patch(detail(target), {"roles": [MEMBER]})

    assert response.status_code == 200
    target.refresh_from_db()
    assert target.is_superuser is False
    assert target.is_staff is False


def test_website_admin_keeps_the_staff_flag(
    api_client: APIClient, user_admin: User, member: User
) -> None:
    """Wagtail access must survive an unrelated role edit."""
    api_client.force_login(user_admin)
    api_client.patch(detail(member), {"roles": [MEMBER, WEBSITE_ADMIN]})

    member.refresh_from_db()
    assert member.is_staff is True
    assert member.is_superuser is False


def test_patching_names_only_leaves_roles_untouched(
    api_client: APIClient, user_admin: User, dart_leader: User
) -> None:
    """A ``PATCH`` that omits ``roles`` leaves the account's roles untouched."""
    api_client.force_login(user_admin)
    api_client.patch(detail(dart_leader), {"first_name": "Priya"})
    dart_leader.refresh_from_db()
    assert dart_leader.roles == [MEMBER, DART_LEADER]


def test_patch_cannot_write_read_only_fields(
    api_client: APIClient, user_admin: User, member: User
) -> None:
    """The read-only ``id`` and ``profile_complete`` fields are silently ignored."""
    api_client.force_login(user_admin)
    original = member.pk
    response = api_client.patch(detail(member), {"id": 4242, "profile_complete": True})

    assert response.status_code == 200
    assert response.json()["id"] == original
    assert response.json()["profile_complete"] is False


def test_put_is_not_allowed(api_client: APIClient, user_admin: User, member: User) -> None:
    """``PUT`` is refused with 405; only ``PATCH`` is supported."""
    api_client.force_login(user_admin)
    assert api_client.put(detail(member), {"first_name": "X"}).status_code == 405


def test_delete_is_not_allowed(api_client: APIClient, user_admin: User, member: User) -> None:
    """Deleting members belongs to the account_admin API."""
    api_client.force_login(user_admin)
    assert api_client.delete(detail(member)).status_code == 405


# --------------------------------------------------------------------------
# Send password reset
# --------------------------------------------------------------------------
def test_send_password_reset_emails_the_member(
    api_client: APIClient, user_admin: User, member: User
) -> None:
    """Sending a reset emails the member and names them in the response detail."""
    api_client.force_login(user_admin)
    response = api_client.post(send_reset(member))

    assert response.status_code == 200
    assert member.email in response.json()["detail"]
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [member.email]
    assert "/portal/reset-password?uid=" in mail.outbox[0].body


def test_send_password_reset_refuses_a_deactivated_account(
    api_client: APIClient, user_admin: User, member: User
) -> None:
    """Sending a reset for a deactivated account is refused, and no email is sent."""
    member.is_active = False
    member.save(update_fields=["is_active"])
    api_client.force_login(user_admin)

    response = api_client.post(send_reset(member))
    assert response.status_code == 400
    assert mail.outbox == []


def test_send_password_reset_404s_for_an_unknown_id(
    api_client: APIClient, user_admin: User
) -> None:
    """Sending a reset for an unknown id is 404."""
    api_client.force_login(user_admin)
    assert api_client.post(f"{LIST}/99999/send-password-reset").status_code == 404


# --------------------------------------------------------------------------
# GET /roles
# --------------------------------------------------------------------------
def test_roles_are_available_to_any_authenticated_user(api_client: APIClient, member: User) -> None:
    """Any signed-in user, including a plain member, can list the role catalog."""
    api_client.force_login(member)
    body = api_client.get(ROLES).json()
    assert [row["slug"] for row in body] == list(ROLE_SLUGS)
    assert all(row["description"] for row in body)
