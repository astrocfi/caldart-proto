"""The users-admin API: list, retrieve, PATCH, password reset.

Every endpoint is checked against the full role matrix, then against the
business rules: role slugs are validated, only a ``system_admin`` may move the
``system_admin`` role, and nobody may deactivate themselves.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core import mail

from apps.accounts.roles import (
    ACCOUNT_ADMIN,
    DART_LEADER,
    MEMBER,
    ROLE_SLUGS,
    SYSTEM_ADMIN,
    USER_ADMIN,
    WEBSITE_ADMIN,
)
from tests.factories import MembershipFactory, UserFactory

pytestmark = pytest.mark.django_db

User = get_user_model()

LIST = "/api/v1/admin/users"
ROLES = "/api/v1/roles"


def detail(user) -> str:
    return f"{LIST}/{user.pk}"


def send_reset(user) -> str:
    return f"{LIST}/{user.pk}/send-password-reset"


#: (role slug, may use the users-admin API).
ROLE_MATRIX = [
    (MEMBER, False),
    (DART_LEADER, False),
    (USER_ADMIN, True),
    (ACCOUNT_ADMIN, False),
    (WEBSITE_ADMIN, False),
    (SYSTEM_ADMIN, True),
]


# --------------------------------------------------------------------------
# Role matrix
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("slug", "allowed"), ROLE_MATRIX)
def test_list_role_matrix(api_client, all_role_users, slug, allowed):
    api_client.force_login(all_role_users[slug])
    assert (api_client.get(LIST).status_code == 200) is allowed


@pytest.mark.parametrize(("slug", "allowed"), ROLE_MATRIX)
def test_retrieve_role_matrix(api_client, all_role_users, slug, allowed, member):
    api_client.force_login(all_role_users[slug])
    assert (api_client.get(detail(member)).status_code == 200) is allowed


@pytest.mark.parametrize(("slug", "allowed"), ROLE_MATRIX)
def test_patch_role_matrix(api_client, all_role_users, slug, allowed, member):
    api_client.force_login(all_role_users[slug])
    response = api_client.patch(detail(member), {"first_name": "Renamed"})
    assert (response.status_code == 200) is allowed


@pytest.mark.parametrize(("slug", "allowed"), ROLE_MATRIX)
def test_send_password_reset_role_matrix(api_client, all_role_users, slug, allowed, member):
    api_client.force_login(all_role_users[slug])
    assert (api_client.post(send_reset(member)).status_code == 200) is allowed


@pytest.mark.parametrize("path", [LIST, ROLES])
def test_anonymous_gets_401_not_403(api_client, path):
    assert api_client.get(path).status_code == 401


def test_anonymous_cannot_patch(api_client, member):
    assert api_client.patch(detail(member), {"first_name": "X"}).status_code == 401


# --------------------------------------------------------------------------
# List: shape, search, filters, pagination
# --------------------------------------------------------------------------
def test_list_returns_the_user_payload(api_client, user_admin, member, annual_plan, today):
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


def test_list_is_ordered_by_name(api_client, user_admin):
    UserFactory(email="zeta@example.test", first_name="Ann", last_name="Zeta", roles=[MEMBER])
    UserFactory(email="alpha@example.test", first_name="Bo", last_name="Alpha", roles=[MEMBER])
    api_client.force_login(user_admin)

    names = [row["last_name"] for row in api_client.get(LIST).json()["results"]]
    assert names.index("Alpha") < names.index("Zeta")


def test_list_search_matches_email(api_client, user_admin, member):
    api_client.force_login(user_admin)
    body = api_client.get(LIST, {"search": member.email}).json()
    assert [row["email"] for row in body["results"]] == [member.email]


def test_list_search_matches_a_full_name(api_client, user_admin):
    UserFactory(email="ada@example.test", first_name="Ada", last_name="Lovelace", roles=[MEMBER])
    UserFactory(email="alan@example.test", first_name="Alan", last_name="Turing", roles=[MEMBER])
    api_client.force_login(user_admin)

    body = api_client.get(LIST, {"search": "Ada Lovelace"}).json()
    assert [row["email"] for row in body["results"]] == ["ada@example.test"]


def test_list_filters_by_role(api_client, all_role_users):
    api_client.force_login(all_role_users[USER_ADMIN])
    body = api_client.get(LIST, {"role": DART_LEADER}).json()
    assert [row["email"] for row in body["results"]] == [all_role_users[DART_LEADER].email]


def test_list_rejects_an_unknown_role(api_client, user_admin):
    api_client.force_login(user_admin)
    response = api_client.get(LIST, {"role": "wizard"})
    assert response.status_code == 400
    assert "role" in response.json()


def test_list_filters_by_is_active(api_client, user_admin, member):
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


def test_list_combines_search_and_filters(api_client, user_admin):
    match = UserFactory(
        email="hit@example.test", first_name="Rosa", last_name="Vega", roles=[MEMBER, DART_LEADER]
    )
    UserFactory(email="miss@example.test", first_name="Rosa", last_name="Ward", roles=[MEMBER])
    api_client.force_login(user_admin)

    body = api_client.get(LIST, {"search": "Rosa", "role": DART_LEADER}).json()
    assert [row["email"] for row in body["results"]] == [match.email]


def test_list_paginates(api_client, user_admin):
    for index in range(8):
        UserFactory(email=f"page{index}@example.test", roles=[MEMBER])
    api_client.force_login(user_admin)

    body = api_client.get(LIST, {"page_size": 3}).json()
    assert len(body["results"]) == 3
    assert body["count"] >= 9
    assert body["next"] is not None


def test_list_can_be_ordered(api_client, user_admin):
    api_client.force_login(user_admin)
    ascending = api_client.get(LIST, {"ordering": "email"}).json()["results"]
    descending = api_client.get(LIST, {"ordering": "-email"}).json()["results"]
    assert [r["email"] for r in ascending] == list(reversed([r["email"] for r in descending]))


# --------------------------------------------------------------------------
# Retrieve
# --------------------------------------------------------------------------
def test_retrieve_returns_one_user(api_client, user_admin, member):
    api_client.force_login(user_admin)
    body = api_client.get(detail(member)).json()
    assert body["id"] == member.pk
    assert body["email"] == member.email


def test_retrieve_404s_for_an_unknown_id(api_client, user_admin):
    api_client.force_login(user_admin)
    assert api_client.get(f"{LIST}/99999").status_code == 404


# --------------------------------------------------------------------------
# PATCH: names, email, is_active
# --------------------------------------------------------------------------
def test_patch_updates_names_and_email(api_client, user_admin, member):
    api_client.force_login(user_admin)
    response = api_client.patch(
        detail(member),
        {"first_name": "Marta", "last_name": "Reyes", "email": "marta.reyes@example.test"},
    )

    assert response.status_code == 200
    member.refresh_from_db()
    assert (member.first_name, member.last_name) == ("Marta", "Reyes")
    assert member.email == "marta.reyes@example.test"


def test_patch_rejects_an_email_another_account_uses(api_client, user_admin, member):
    api_client.force_login(user_admin)
    response = api_client.patch(detail(member), {"email": user_admin.email.upper()})
    assert response.status_code == 400
    assert "email" in response.json()
    member.refresh_from_db()
    assert member.email != user_admin.email


def test_patch_can_keep_the_same_email(api_client, user_admin, member):
    api_client.force_login(user_admin)
    assert api_client.patch(detail(member), {"email": member.email}).status_code == 200


def test_patch_deactivates_another_account(api_client, user_admin, member):
    api_client.force_login(user_admin)
    response = api_client.patch(detail(member), {"is_active": False})

    assert response.status_code == 200
    assert response.json()["is_active"] is False
    member.refresh_from_db()
    assert member.is_active is False


def test_a_user_cannot_deactivate_themselves(api_client, user_admin):
    api_client.force_login(user_admin)
    response = api_client.patch(detail(user_admin), {"is_active": False})

    assert response.status_code == 400
    assert "is_active" in response.json()
    user_admin.refresh_from_db()
    assert user_admin.is_active is True


def test_a_system_admin_cannot_deactivate_themselves_either(api_client, system_admin):
    api_client.force_login(system_admin)
    response = api_client.patch(detail(system_admin), {"is_active": False})
    assert response.status_code == 400
    system_admin.refresh_from_db()
    assert system_admin.is_active is True


def test_a_user_may_reactivate_themselves_noop(api_client, user_admin):
    """Sending ``is_active: true`` for yourself is harmless, not an error."""
    api_client.force_login(user_admin)
    assert api_client.patch(detail(user_admin), {"is_active": True}).status_code == 200


# --------------------------------------------------------------------------
# PATCH: roles
# --------------------------------------------------------------------------
def test_patch_sets_roles(api_client, user_admin, member):
    api_client.force_login(user_admin)
    response = api_client.patch(detail(member), {"roles": [MEMBER, DART_LEADER]})

    assert response.status_code == 200
    assert response.json()["roles"] == [MEMBER, DART_LEADER]
    member.refresh_from_db()
    assert member.roles == [MEMBER, DART_LEADER]


def test_patch_returns_roles_in_privilege_order(api_client, user_admin, member):
    api_client.force_login(user_admin)
    response = api_client.patch(detail(member), {"roles": [ACCOUNT_ADMIN, MEMBER, DART_LEADER]})
    assert response.json()["roles"] == [MEMBER, DART_LEADER, ACCOUNT_ADMIN]


def test_patch_can_revoke_every_role(api_client, user_admin, member):
    api_client.force_login(user_admin)
    response = api_client.patch(detail(member), {"roles": []})
    assert response.status_code == 200
    member.refresh_from_db()
    assert member.roles == []


def test_patch_rejects_an_unknown_role_slug(api_client, user_admin, member):
    api_client.force_login(user_admin)
    response = api_client.patch(detail(member), {"roles": [MEMBER, "wizard"]})

    assert response.status_code == 400
    assert "roles" in response.json()
    member.refresh_from_db()
    assert member.roles == [MEMBER]


def test_patch_leaves_non_role_groups_alone(api_client, user_admin, member):
    from django.contrib.auth.models import Group

    editors = Group.objects.create(name="wagtail-editors")
    member.groups.add(editors)
    api_client.force_login(user_admin)

    api_client.patch(detail(member), {"roles": [MEMBER, DART_LEADER]})
    assert editors in member.groups.all()


def test_a_user_admin_cannot_grant_system_admin(api_client, user_admin, member):
    api_client.force_login(user_admin)
    response = api_client.patch(detail(member), {"roles": [MEMBER, SYSTEM_ADMIN]})

    assert response.status_code == 400
    assert "roles" in response.json()
    member.refresh_from_db()
    assert SYSTEM_ADMIN not in member.roles


def test_a_user_admin_cannot_revoke_system_admin(api_client, user_admin, system_admin):
    api_client.force_login(user_admin)
    response = api_client.patch(detail(system_admin), {"roles": [MEMBER]})

    assert response.status_code == 400
    system_admin.refresh_from_db()
    assert SYSTEM_ADMIN in system_admin.roles


def test_a_user_admin_may_edit_other_roles_of_a_system_admin(api_client, user_admin, system_admin):
    """Leaving ``system_admin`` in place is allowed; moving it is not."""
    api_client.force_login(user_admin)
    response = api_client.patch(
        detail(system_admin), {"roles": [MEMBER, DART_LEADER, SYSTEM_ADMIN]}
    )

    assert response.status_code == 200
    system_admin.refresh_from_db()
    assert system_admin.roles == [MEMBER, DART_LEADER, SYSTEM_ADMIN]


def test_a_system_admin_can_grant_system_admin(api_client, system_admin, member):
    api_client.force_login(system_admin)
    response = api_client.patch(detail(member), {"roles": [MEMBER, SYSTEM_ADMIN]})

    assert response.status_code == 200
    member.refresh_from_db()
    assert SYSTEM_ADMIN in member.roles
    assert member.is_superuser is True
    assert member.is_staff is True


def test_revoking_system_admin_drops_the_superuser_flag(api_client, system_admin):
    target = UserFactory(email="ex-root@example.test", roles=[MEMBER, SYSTEM_ADMIN])
    target.is_superuser = target.is_staff = True
    target.save(update_fields=["is_superuser", "is_staff"])
    api_client.force_login(system_admin)

    response = api_client.patch(detail(target), {"roles": [MEMBER]})

    assert response.status_code == 200
    target.refresh_from_db()
    assert target.is_superuser is False
    assert target.is_staff is False


def test_website_admin_keeps_the_staff_flag(api_client, user_admin, member):
    """Wagtail access must survive an unrelated role edit."""
    api_client.force_login(user_admin)
    api_client.patch(detail(member), {"roles": [MEMBER, WEBSITE_ADMIN]})

    member.refresh_from_db()
    assert member.is_staff is True
    assert member.is_superuser is False


def test_patching_names_only_leaves_roles_untouched(api_client, user_admin, dart_leader):
    api_client.force_login(user_admin)
    api_client.patch(detail(dart_leader), {"first_name": "Priya"})
    dart_leader.refresh_from_db()
    assert dart_leader.roles == [MEMBER, DART_LEADER]


def test_patch_cannot_write_read_only_fields(api_client, user_admin, member):
    api_client.force_login(user_admin)
    original = member.pk
    response = api_client.patch(detail(member), {"id": 4242, "profile_complete": True})

    assert response.status_code == 200
    assert response.json()["id"] == original
    assert response.json()["profile_complete"] is False


def test_put_is_not_allowed(api_client, user_admin, member):
    api_client.force_login(user_admin)
    assert api_client.put(detail(member), {"first_name": "X"}).status_code == 405


def test_delete_is_not_allowed(api_client, user_admin, member):
    """Deleting members belongs to the account_admin API."""
    api_client.force_login(user_admin)
    assert api_client.delete(detail(member)).status_code == 405


# --------------------------------------------------------------------------
# Send password reset
# --------------------------------------------------------------------------
def test_send_password_reset_emails_the_member(api_client, user_admin, member):
    api_client.force_login(user_admin)
    response = api_client.post(send_reset(member))

    assert response.status_code == 200
    assert member.email in response.json()["detail"]
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [member.email]
    assert "/portal/reset-password?uid=" in mail.outbox[0].body


def test_send_password_reset_refuses_a_deactivated_account(api_client, user_admin, member):
    member.is_active = False
    member.save(update_fields=["is_active"])
    api_client.force_login(user_admin)

    response = api_client.post(send_reset(member))
    assert response.status_code == 400
    assert mail.outbox == []


def test_send_password_reset_404s_for_an_unknown_id(api_client, user_admin):
    api_client.force_login(user_admin)
    assert api_client.post(f"{LIST}/99999/send-password-reset").status_code == 404


# --------------------------------------------------------------------------
# GET /roles
# --------------------------------------------------------------------------
def test_roles_are_available_to_any_authenticated_user(api_client, member):
    api_client.force_login(member)
    body = api_client.get(ROLES).json()
    assert [row["slug"] for row in body] == list(ROLE_SLUGS)
    assert all(row["description"] for row in body)
