"""Shared pytest fixtures (PLAN §15).

Every Phase 2 branch builds on these, so add fixtures here rather than
duplicating them in app test packages.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.accounts.roles import (
    ACCOUNT_ADMIN,
    DART_LEADER,
    MEMBER,
    SYSTEM_ADMIN,
    USER_ADMIN,
    WEBSITE_ADMIN,
)
from tests.factories import (
    DEFAULT_PASSWORD,
    AircraftFactory,
    DartFactory,
    LifetimePlanFactory,
    MemberProfileFactory,
    MembershipFactory,
    MembershipPlanFactory,
    PaymentFactory,
    ReminderLogFactory,
    UserFactory,
    make_home_page,
    make_site_settings,
)

User = get_user_model()


@pytest.fixture(autouse=True)
def _roles(db):
    """Every test gets the role groups, exactly as ``migrate`` leaves them."""
    from apps.accounts.management.commands.seed_roles import seed_roles

    seed_roles()


@pytest.fixture
def api_client() -> APIClient:
    """An unauthenticated DRF client.  Use ``api_client.force_login(user)``."""
    return APIClient()


@pytest.fixture
def user_factory():
    """The ``UserFactory`` class, for tests that need many users."""
    return UserFactory


@pytest.fixture
def password() -> str:
    return DEFAULT_PASSWORD


@pytest.fixture
def anonymous_user(db):
    """A user with no roles at all."""
    return UserFactory(email="nobody@example.test", roles=[])


# -- one fixture per role --------------------------------------------------
def _role_fixture(slug: str, email: str):
    @pytest.fixture(name=slug if slug != MEMBER else "member")
    def _fixture(db):
        return UserFactory(email=email, roles=[MEMBER, slug] if slug != MEMBER else [MEMBER])

    return _fixture


member = _role_fixture(MEMBER, "member@example.test")
dart_leader = _role_fixture(DART_LEADER, "leader@example.test")
user_admin = _role_fixture(USER_ADMIN, "useradmin@example.test")
account_admin = _role_fixture(ACCOUNT_ADMIN, "accountadmin@example.test")
website_admin = _role_fixture(WEBSITE_ADMIN, "webadmin@example.test")
system_admin = _role_fixture(SYSTEM_ADMIN, "sysadmin@example.test")


@pytest.fixture
def leader(dart_leader):
    """Alias for ``dart_leader``, the name used in most tests."""
    return dart_leader


@pytest.fixture
def superuser(db):
    return UserFactory(
        email="root@example.test", roles=[SYSTEM_ADMIN], is_superuser=True, is_staff=True
    )


@pytest.fixture
def all_role_users(member, dart_leader, user_admin, account_admin, website_admin, system_admin):
    """Every role fixture keyed by slug, for allow/deny matrix tests."""
    return {
        MEMBER: member,
        DART_LEADER: dart_leader,
        USER_ADMIN: user_admin,
        ACCOUNT_ADMIN: account_admin,
        WEBSITE_ADMIN: website_admin,
        SYSTEM_ADMIN: system_admin,
    }


# -- domain fixtures -------------------------------------------------------
@pytest.fixture
def annual_plan(db) -> MembershipPlanFactory:
    return MembershipPlanFactory()


@pytest.fixture
def life_plan(db):
    return LifetimePlanFactory()


@pytest.fixture
def dart(db):
    return DartFactory(name="Palo Alto", airport_identifier="PAO", city="Palo Alto")


@pytest.fixture
def profile(member, dart):
    return MemberProfileFactory(user=member, dart=dart)


@pytest.fixture
def aircraft(db):
    return AircraftFactory()


@pytest.fixture
def payment_factory():
    return PaymentFactory


@pytest.fixture
def membership_factory():
    return MembershipFactory


@pytest.fixture
def reminder_log_factory():
    return ReminderLogFactory


@pytest.fixture
def aircraft_factory():
    return AircraftFactory


@pytest.fixture
def profile_factory():
    return MemberProfileFactory


@pytest.fixture
def home_page(db):
    return make_home_page()


@pytest.fixture
def site_settings(db):
    return make_site_settings()


@pytest.fixture
def today() -> date:
    from django.utils import timezone

    return timezone.localdate()


@pytest.fixture
def days():
    """``days(7)`` -> ``timedelta(days=7)``, to keep date maths readable."""
    return lambda n: timedelta(days=n)
