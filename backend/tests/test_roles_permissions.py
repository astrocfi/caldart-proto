"""Roles, ``User`` helpers and the DRF permission classes."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, timedelta

import pytest
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.models import AnonymousUser, Group
from django.utils import timezone
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from apps.accounts.management.commands.seed_roles import seed_roles
from apps.accounts.models import User
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
from apps.members.models import MembershipPlan
from tests.factories import MembershipFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_role_slugs_are_the_six_documented_roles() -> None:
    """``ROLE_SLUGS`` lists the six roles least privileged first."""
    assert ROLE_SLUGS == (
        MEMBER,
        DART_LEADER,
        USER_ADMIN,
        ACCOUNT_ADMIN,
        WEBSITE_ADMIN,
        SYSTEM_ADMIN,
    )


def test_staff_roles_are_every_role_but_member() -> None:
    """``STAFF_ROLE_SLUGS`` is ``ROLE_SLUGS`` with ``member`` removed."""
    assert set(STAFF_ROLE_SLUGS) == set(ROLE_SLUGS) - {MEMBER}


def test_seed_roles_is_idempotent() -> None:
    """Running ``seed_roles`` twice still leaves exactly one group per role."""
    seed_roles()
    seed_roles()
    assert Group.objects.filter(name__in=ROLE_SLUGS).count() == len(ROLE_SLUGS)


def test_roles_property_is_in_privilege_order(member: User) -> None:
    """``User.roles`` lists the held roles in privilege order, not grant order."""
    member.add_role(ACCOUNT_ADMIN)
    member.add_role(DART_LEADER)
    assert member.roles == [MEMBER, DART_LEADER, ACCOUNT_ADMIN]


def test_has_role_is_exact_for_ordinary_roles(member: User) -> None:
    """``has_role`` is true only for a role the account actually holds."""
    assert member.has_role(MEMBER)
    assert not member.has_role(ACCOUNT_ADMIN)


def test_system_admin_implies_every_role(system_admin: User) -> None:
    """A system administrator's ``has_role``/``has_any_role`` are true for every slug."""
    for slug in ROLE_SLUGS:
        assert system_admin.has_role(slug)
    assert system_admin.has_any_role(WEBSITE_ADMIN)


def test_set_roles_replaces_only_role_groups(member: User) -> None:
    """``set_roles`` replaces the role groups but leaves a non-role group alone."""
    other = Group.objects.create(name="wagtail-editors")
    member.groups.add(other)
    member.set_roles([MEMBER, USER_ADMIN])
    assert member.roles == [MEMBER, USER_ADMIN]
    assert other in member.groups.all()


def test_remove_role_drops_only_the_named_role(member: User) -> None:
    """``remove_role`` drops exactly the named role."""
    member.add_role(DART_LEADER)
    member.remove_role(DART_LEADER)
    assert member.roles == [MEMBER]


@pytest.mark.parametrize("slug", ROLE_SLUGS)
def test_can_access_members_content_for_each_role(slug: str, today: date) -> None:
    """Every role but a plain member can access members content with no membership."""
    user = UserFactory(email=f"{slug}@roles.test", roles=[slug])
    expected = slug != MEMBER
    assert user.can_access_members_content is expected


def test_member_with_current_membership_can_access_members_content(
    member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """A plain member with a current membership can access members-only content."""
    MembershipFactory(user=member, plan=annual_plan, starts_on=today)
    assert member.can_access_members_content is True


def test_member_with_expired_membership_cannot_access_members_content(
    member: User, annual_plan: MembershipPlan, today: date
) -> None:
    """A plain member with an expired membership cannot access members-only content."""
    MembershipFactory(
        user=member,
        plan=annual_plan,
        starts_on=today - timedelta(days=400),
        ends_on=today - timedelta(days=35),
    )
    assert member.can_access_members_content is False


def test_a_user_is_named_by_their_full_name(member: User) -> None:
    """``str(user)`` and ``display_name`` are both the account's full name."""
    member.first_name = "Ada"
    member.last_name = "Lovelace"
    assert str(member) == "Ada Lovelace"
    assert member.display_name == "Ada Lovelace"


def test_a_user_with_no_name_is_named_by_their_email(member: User) -> None:
    """With neither name filled in, ``str(user)`` falls back to the email address."""
    member.first_name = ""
    member.last_name = ""
    assert str(member) == member.email


def test_email_login_is_case_insensitive(member: User, password: str) -> None:
    """``authenticate`` accepts the email in any case."""
    assert authenticate(username=member.email.upper(), password=password) == member


def test_user_manager_requires_email() -> None:
    """``create_user`` with a blank email raises ``ValueError``."""
    with pytest.raises(ValueError, match="email"):
        get_user_model().objects.create_user(email="", password="x")  # noqa: S106 - test fixture


def test_create_superuser_sets_flags() -> None:
    """``create_superuser`` sets both ``is_superuser`` and ``is_staff``."""
    user = get_user_model().objects.create_superuser(
        email="su@example.test",
        password="pw",  # noqa: S106 - test fixture
        first_name="S",
    )
    assert user.is_superuser
    assert user.is_staff


# -- permission classes ----------------------------------------------------
def _view_for(permission_class: type[BasePermission]) -> Callable[..., Response]:
    """A minimal ``APIView`` guarded by ``permission_class``."""

    class _View(APIView):
        permission_classes = [permission_class]

        def get(self, request: Request) -> Response:
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
def test_has_role_matrix(slug: str, allowed: bool, all_role_users: dict[str, User]) -> None:
    """``HasRole(dart_leader)`` allows only a dart leader or a system administrator."""
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
def test_has_any_role_matrix(slug: str, allowed: bool, all_role_users: dict[str, User]) -> None:
    """``HasAnyRole(user_admin, account_admin)`` admits either admin, or system admin."""
    view = _view_for(HasAnyRole(USER_ADMIN, ACCOUNT_ADMIN))
    request = APIRequestFactory().get("/")
    request.user = all_role_users[slug]
    assert (view(request).status_code == 200) is allowed


def test_permission_denies_anonymous() -> None:
    """An anonymous request is refused with 401 or 403, never let through."""
    view = _view_for(HasRole(MEMBER))
    request = APIRequestFactory().get("/")
    request.user = AnonymousUser()
    assert view(request).status_code in (401, 403)


def test_has_any_role_requires_at_least_one_slug() -> None:
    """Constructing ``HasAnyRole`` with no slugs raises ``ValueError``."""
    with pytest.raises(ValueError, match="at least one role"):
        HasAnyRole()


def test_user_has_any_role_helper(member: User, superuser: User) -> None:
    """``user_has_any_role`` checks membership; true for a superuser, false for None."""
    assert user_has_any_role(member, (MEMBER,)) is True
    assert user_has_any_role(member, (ACCOUNT_ADMIN,)) is False
    assert user_has_any_role(superuser, (ACCOUNT_ADMIN,)) is True
    assert user_has_any_role(AnonymousUser(), (MEMBER,)) is False
    assert user_has_any_role(None, (MEMBER,)) is False


def test_allow_any_still_works() -> None:
    """``AllowAny`` still admits an anonymous request."""
    view = _view_for(AllowAny)
    request = APIRequestFactory().get("/")
    request.user = AnonymousUser()
    assert view(request).status_code == 200


def test_membership_status_property_delegates(member: User, annual_plan: MembershipPlan) -> None:
    """``User.membership_status`` reports the status of the current membership."""
    MembershipFactory(user=member, plan=annual_plan, starts_on=timezone.localdate())
    assert member.membership_status["status"] == "current"
