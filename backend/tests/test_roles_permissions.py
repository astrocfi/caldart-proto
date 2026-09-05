"""Roles, ``User`` helpers and the DRF permission classes (PLAN §4.1, §5)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth.models import Group
from django.utils import timezone
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from apps.accounts.permissions import HasAnyRole, HasRole, user_has_any_role
from apps.accounts.roles import (
    ACCOUNT_ADMIN,
    DART_LEADER,
    MEMBER,
    ROLE_SLUGS,
    STAFF_ROLE_SLUGS,
    SYSTEM_ADMIN,
    USER_ADMIN,
    WEBSITE_ADMIN,
)
from tests.factories import MembershipFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_role_slugs_are_the_six_from_the_plan():
    assert ROLE_SLUGS == (
        MEMBER,
        DART_LEADER,
        USER_ADMIN,
        ACCOUNT_ADMIN,
        WEBSITE_ADMIN,
        SYSTEM_ADMIN,
    )
    assert MEMBER not in STAFF_ROLE_SLUGS
    assert set(STAFF_ROLE_SLUGS) == set(ROLE_SLUGS) - {MEMBER}


def test_seed_roles_is_idempotent():
    from apps.accounts.management.commands.seed_roles import seed_roles

    seed_roles()
    seed_roles()
    assert Group.objects.filter(name__in=ROLE_SLUGS).count() == len(ROLE_SLUGS)


def test_roles_property_is_in_privilege_order(member):
    member.add_role(ACCOUNT_ADMIN)
    member.add_role(DART_LEADER)
    assert member.roles == [MEMBER, DART_LEADER, ACCOUNT_ADMIN]


def test_has_role_is_exact_for_ordinary_roles(member):
    assert member.has_role(MEMBER)
    assert not member.has_role(ACCOUNT_ADMIN)


def test_system_admin_implies_every_role(system_admin):
    for slug in ROLE_SLUGS:
        assert system_admin.has_role(slug)
    assert system_admin.has_any_role(WEBSITE_ADMIN)


def test_set_roles_replaces_only_role_groups(member):
    other = Group.objects.create(name="wagtail-editors")
    member.groups.add(other)
    member.set_roles([MEMBER, USER_ADMIN])
    assert member.roles == [MEMBER, USER_ADMIN]
    assert other in member.groups.all()


def test_remove_role(member):
    member.add_role(DART_LEADER)
    member.remove_role(DART_LEADER)
    assert member.roles == [MEMBER]


@pytest.mark.parametrize("slug", ROLE_SLUGS)
def test_can_access_members_content_for_each_role(slug, today):
    user = UserFactory(email=f"{slug}@roles.test", roles=[slug])
    expected = slug != MEMBER
    assert user.can_access_members_content is expected


def test_member_with_current_membership_can_access_members_content(member, annual_plan, today):
    MembershipFactory(user=member, plan=annual_plan, starts_on=today)
    assert member.can_access_members_content is True


def test_member_with_expired_membership_cannot_access_members_content(member, annual_plan, today):
    MembershipFactory(
        user=member,
        plan=annual_plan,
        starts_on=today - timedelta(days=400),
        ends_on=today - timedelta(days=35),
    )
    assert member.can_access_members_content is False


def test_str_and_display_name(member):
    member.first_name = "Ada"
    member.last_name = "Lovelace"
    assert str(member) == "Ada Lovelace"
    assert member.display_name == "Ada Lovelace"
    member.first_name = member.last_name = ""
    assert str(member) == member.email


def test_email_login_is_case_insensitive(member, password):
    from django.contrib.auth import authenticate

    assert authenticate(username=member.email.upper(), password=password) == member


def test_user_manager_requires_email():
    from django.contrib.auth import get_user_model

    with pytest.raises(ValueError, match="email"):
        get_user_model().objects.create_user(email="", password="x")


def test_create_superuser_sets_flags():
    from django.contrib.auth import get_user_model

    user = get_user_model().objects.create_superuser(
        email="su@example.test", password="pw", first_name="S"
    )
    assert user.is_superuser and user.is_staff


# -- permission classes ----------------------------------------------------
def _view_for(permission_class):
    class _View(APIView):
        permission_classes = [permission_class]

        def get(self, request):
            return Response({"ok": True})

    return _View.as_view()


@pytest.mark.parametrize(
    ("slug", "allowed"),
    [
        (MEMBER, False),
        (DART_LEADER, True),
        (USER_ADMIN, False),
        (ACCOUNT_ADMIN, False),
        (WEBSITE_ADMIN, False),
        (SYSTEM_ADMIN, True),
    ],
)
def test_has_role_matrix(slug, allowed, all_role_users):
    view = _view_for(HasRole(DART_LEADER))
    request = APIRequestFactory().get("/")
    request.user = all_role_users[slug]
    assert (view(request).status_code == 200) is allowed


@pytest.mark.parametrize(
    ("slug", "allowed"),
    [
        (MEMBER, False),
        (DART_LEADER, False),
        (USER_ADMIN, True),
        (ACCOUNT_ADMIN, True),
        (WEBSITE_ADMIN, False),
        (SYSTEM_ADMIN, True),
    ],
)
def test_has_any_role_matrix(slug, allowed, all_role_users):
    view = _view_for(HasAnyRole(USER_ADMIN, ACCOUNT_ADMIN))
    request = APIRequestFactory().get("/")
    request.user = all_role_users[slug]
    assert (view(request).status_code == 200) is allowed


def test_permission_denies_anonymous():
    from django.contrib.auth.models import AnonymousUser

    view = _view_for(HasRole(MEMBER))
    request = APIRequestFactory().get("/")
    request.user = AnonymousUser()
    assert view(request).status_code in (401, 403)


def test_has_any_role_requires_at_least_one_slug():
    with pytest.raises(ValueError, match="at least one role"):
        HasAnyRole()


def test_user_has_any_role_helper(member, superuser):
    from django.contrib.auth.models import AnonymousUser

    assert user_has_any_role(member, (MEMBER,)) is True
    assert user_has_any_role(member, (ACCOUNT_ADMIN,)) is False
    assert user_has_any_role(superuser, (ACCOUNT_ADMIN,)) is True
    assert user_has_any_role(AnonymousUser(), (MEMBER,)) is False
    assert user_has_any_role(None, (MEMBER,)) is False


def test_allow_any_still_works():
    view = _view_for(AllowAny)
    from django.contrib.auth.models import AnonymousUser

    request = APIRequestFactory().get("/")
    request.user = AnonymousUser()
    assert view(request).status_code == 200


def test_membership_status_property_delegates(member, annual_plan):
    MembershipFactory(user=member, plan=annual_plan, starts_on=timezone.localdate())
    assert member.membership_status["status"] == "current"
