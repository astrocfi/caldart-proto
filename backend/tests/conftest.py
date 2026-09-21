"""Shared pytest fixtures.

Every test module can use these, so add shared fixtures here rather than
duplicating them.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from pytest import Config

    from apps.accounts.models import User as UserModel
    from apps.aircraft.models import Aircraft
    from apps.cms.models import HomePage, SiteSettings
    from apps.members.models import Dart, MemberProfile, MembershipPlan

User = get_user_model()

#: The endpoint that issues the ``csrftoken`` cookie, used by ``csrf_headers``.
CSRF_URL = "/api/v1/auth/csrf"


# --------------------------------------------------------------------------
# Vite manifest
#
# `templates/base.html` and `templates/portal.html` call `{% vite_asset %}`,
# which raises when the entry is missing from `frontend/dist/.vite/manifest.json`.
# Backend tests must not depend on `npm run build` having been run — CI runs the
# two suites in separate jobs — so stub the manifest when there is no real build
# and remember that we did, for the tests that assert on the real bundle.
# --------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]
VITE_MANIFEST = REPO_ROOT / "frontend" / "dist" / ".vite" / "manifest.json"

STUB_MANIFEST = {
    "src/site/main.ts": {
        "file": "assets/site-stub.js",
        "src": "src/site/main.ts",
        "isEntry": True,
        "css": ["assets/index-stub.css"],
    },
    "src/portal/main.tsx": {
        "file": "assets/portal-stub.js",
        "src": "src/portal/main.tsx",
        "isEntry": True,
        "css": ["assets/index-stub.css", "assets/portal-stub.css"],
    },
}

_stubbed_manifest = False


def _reload_vite_loader() -> None:
    """Make django-vite re-read the manifest.

    Its ``AppConfig.ready()`` parses the manifest once and caches the loader,
    and that ran during ``django.setup()`` — before this hook — so a manifest
    written here would otherwise be ignored.
    """
    from django_vite.core.asset_loader import DjangoViteAssetLoader

    DjangoViteAssetLoader._instance = None
    DjangoViteAssetLoader.instance()


def pytest_configure(config: Config) -> None:
    """Write the stub Vite manifest when no real frontend build is present.

    Sets the module-level ``_stubbed_manifest`` flag so ``pytest_unconfigure`` knows
    whether to remove the file it wrote, and reloads django-vite's cached loader so it
    picks up the manifest this hook just wrote or found.
    """
    global _stubbed_manifest
    if not VITE_MANIFEST.is_file():
        VITE_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        VITE_MANIFEST.write_text(json.dumps(STUB_MANIFEST, indent=2))
        _stubbed_manifest = True
    _reload_vite_loader()


def pytest_unconfigure(config: Config) -> None:
    """Leave the tree as we found it."""
    if not _stubbed_manifest:
        return
    VITE_MANIFEST.unlink(missing_ok=True)
    for directory in (VITE_MANIFEST.parent, VITE_MANIFEST.parent.parent):
        if directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()


@pytest.fixture(scope="session")
def frontend_is_built() -> bool:
    """Return ``False`` when the manifest is the stub above rather than a real build."""
    return not _stubbed_manifest


@pytest.fixture(autouse=True)
def _roles(db: None) -> None:
    """Every test gets the role groups, exactly as ``migrate`` leaves them."""
    from apps.accounts.management.commands.seed_roles import seed_roles

    seed_roles()


@pytest.fixture
def api_client() -> APIClient:
    """An unauthenticated DRF client.  Use ``api_client.force_login(user)``."""
    return APIClient()


@pytest.fixture
def csrf_client() -> APIClient:
    """An unauthenticated DRF client that enforces CSRF, as a browser does.

    ``api_client`` skips the check, which is what most tests want.  Reach for
    this one to show that an unsafe method really is refused without a token,
    and pair it with ``csrf_headers`` to send a good one.
    """
    return APIClient(enforce_csrf_checks=True)


@pytest.fixture
def csrf_headers() -> Callable[[APIClient], dict[str, str]]:
    """``csrf_headers(client)`` -> the header kwargs an unsafe method needs.

    Calling it issues ``GET /api/v1/auth/csrf``, which leaves the ``csrftoken``
    cookie on the client, and returns ``{"HTTP_X_CSRFTOKEN": <cookie value>}``
    to splat into the next request -- the bootstrap the portal's fetch wrapper
    performs in the browser.
    """

    def bootstrap(client: APIClient) -> dict[str, str]:
        client.get(CSRF_URL)
        return {"HTTP_X_CSRFTOKEN": client.cookies["csrftoken"].value}

    return bootstrap


@pytest.fixture
def user_factory() -> type[UserFactory]:
    """Return the ``UserFactory`` class, for tests that need many users."""
    return UserFactory


@pytest.fixture
def password() -> str:
    """Return the plaintext password every ``UserFactory`` user is created with."""
    return DEFAULT_PASSWORD


@pytest.fixture
def no_role_user(db: None) -> UserModel:
    """Return a signed-in user with no roles at all."""
    return UserFactory(email="nobody@example.test", roles=[])


# -- one fixture per role --------------------------------------------------
def _role_fixture(slug: str, email: str) -> Callable[..., UserModel]:
    """Return a pytest fixture function that creates a user holding role ``slug``.

    ``MEMBER`` gets only the member role; every other role also carries member, since
    every non-member role in this application implies membership.
    """

    @pytest.fixture(name=slug if slug != MEMBER else "member")
    def _fixture(db: None) -> UserModel:
        return UserFactory(email=email, roles=[MEMBER, slug] if slug != MEMBER else [MEMBER])

    return _fixture


member = _role_fixture(MEMBER, "member@example.test")
dart_leader = _role_fixture(DART_LEADER, "leader@example.test")
user_admin = _role_fixture(USER_ADMIN, "useradmin@example.test")
account_admin = _role_fixture(ACCOUNT_ADMIN, "accountadmin@example.test")
website_admin = _role_fixture(WEBSITE_ADMIN, "webadmin@example.test")
system_admin = _role_fixture(SYSTEM_ADMIN, "sysadmin@example.test")


@pytest.fixture
def leader(dart_leader: UserModel) -> UserModel:
    """Return ``dart_leader``, under the name used in most tests."""
    return dart_leader


@pytest.fixture
def superuser(db: None) -> UserModel:
    """Return a Django superuser holding the system-admin role."""
    return UserFactory(
        email="root@example.test", roles=[SYSTEM_ADMIN], is_superuser=True, is_staff=True
    )


@pytest.fixture
def all_role_users(
    member: UserModel,
    dart_leader: UserModel,
    user_admin: UserModel,
    account_admin: UserModel,
    website_admin: UserModel,
    system_admin: UserModel,
) -> dict[str, UserModel]:
    """Return every role fixture's user keyed by its role slug, for allow/deny tests."""
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
def annual_plan(db: None) -> MembershipPlan:
    """Return a saved annual ``MembershipPlan`` built by ``MembershipPlanFactory``."""
    return MembershipPlanFactory()


@pytest.fixture
def life_plan(db: None) -> MembershipPlan:
    """Return a saved lifetime ``MembershipPlan`` built by ``LifetimePlanFactory``."""
    return LifetimePlanFactory()


@pytest.fixture
def dart(db: None) -> Dart:
    """Return a saved ``Dart`` named "Palo Alto" with airport identifier ``PAO``."""
    return DartFactory(name="Palo Alto", airport_identifier="PAO", city="Palo Alto")


@pytest.fixture
def profile(member: UserModel, dart: Dart) -> MemberProfile:
    """Return a saved ``MemberProfile`` for the ``member`` fixture's user at ``dart``."""
    return MemberProfileFactory(user=member, dart=dart)


@pytest.fixture
def aircraft(db: None) -> Aircraft:
    """Return a saved ``Aircraft`` built by ``AircraftFactory``."""
    return AircraftFactory()


@pytest.fixture
def payment_factory() -> type[PaymentFactory]:
    """Return the ``PaymentFactory`` class, for tests that need many payments."""
    return PaymentFactory


@pytest.fixture
def membership_factory() -> type[MembershipFactory]:
    """Return the ``MembershipFactory`` class, for tests that need many memberships."""
    return MembershipFactory


@pytest.fixture
def reminder_log_factory() -> type[ReminderLogFactory]:
    """Return the ``ReminderLogFactory`` class, for tests that need many reminder logs."""
    return ReminderLogFactory


@pytest.fixture
def aircraft_factory() -> type[AircraftFactory]:
    """Return the ``AircraftFactory`` class, for tests that need many aircraft."""
    return AircraftFactory


@pytest.fixture
def profile_factory() -> type[MemberProfileFactory]:
    """Return the ``MemberProfileFactory`` class, for tests that need many profiles."""
    return MemberProfileFactory


@pytest.fixture
def home_page(db: None) -> HomePage:
    """Return the site's ``HomePage``, created under the Wagtail tree root if needed."""
    return make_home_page()


@pytest.fixture
def site_settings(db: None) -> SiteSettings:
    """Return the default site's ``SiteSettings`` row, created if it does not exist."""
    return make_site_settings()


@pytest.fixture
def today() -> date:
    """Return the current local date."""
    from django.utils import timezone

    return timezone.localdate()


@pytest.fixture
def days() -> Callable[[int], timedelta]:
    """``days(7)`` -> ``timedelta(days=7)``, to keep date math readable."""
    return lambda n: timedelta(days=n)
