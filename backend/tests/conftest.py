"""Shared pytest fixtures.

Every test module can use these, so add shared fixtures here rather than
duplicating them.
"""

from __future__ import annotations

import base64
import copy
import csv
import io
import json
import os
import re
import shutil
import tempfile
import zlib
from collections.abc import Callable, Iterator
from datetime import date, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, cast

import freezegun
import pytest
import respx
from django.conf import settings as django_settings
from django.contrib.auth import get_user_model
from django.http import HttpResponseBase, StreamingHttpResponse
from django.utils import timezone
from django_vite.core.asset_loader import DjangoViteAssetLoader
from pytest_django import Settings
from rest_framework.test import APIClient

from apps.accounts.roles import (
    ACCOUNT_ADMIN,
    DART_LEADER,
    MEMBER,
    ROLE_SLUGS,
    SYSTEM_ADMIN,
    USER_ADMIN,
    WEBSITE_ADMIN,
)
from apps.sysadmin import services
from caldart.settings.test import STATIC_ROOT_PREFIX
from tests.factories import (
    DEFAULT_PASSWORD,
    AircraftFactory,
    DartFactory,
    LifetimePlanFactory,
    MemberProfileFactory,
    MembershipPlanFactory,
    PaymentFactory,
    UserFactory,
    make_home_page,
    make_site_settings,
)

if TYPE_CHECKING:
    from apps.accounts.models import User as UserModel
    from apps.aircraft.models import Aircraft
    from apps.cms.models import HomePage, SiteSettings
    from apps.members.models import Dart, MemberProfile, MembershipPlan

User = get_user_model()

# freezegun patches every call to the standard library's clock, which would
# otherwise also freeze pytest's own timing (durations, `--durations`, and
# similar instrumentation) for the rest of a test session that ever freezes
# time. Excluding pytest's own modules keeps the clock real for pytest itself.
freezegun.configure(extend_ignore_list=["_pytest", "pluggy"])

#: The endpoint that issues the ``csrftoken`` cookie, used by ``csrf_headers``.
CSRF_URL = "/api/v1/auth/csrf"


# --------------------------------------------------------------------------
# Vite manifest
#
# `templates/base.html` and `templates/portal.html` call `{% vite_asset %}`,
# which raises when the entry is missing from the manifest django-vite loads.
# Backend tests must not depend on `npm run build` having been run -- CI runs
# the two suites in separate jobs.
#
# `caldart.settings.test` resolves `DJANGO_VITE`'s manifest_path from the
# `DJANGO_VITE_MANIFEST_PATH` environment variable, which CI's backend job
# points at a real build before running pytest (docs/developer/testing.rst).
# That resolution happens while Django starts up, before this module is even
# imported -- pytest-django sets Django up in its own `pytest_load_initial_
# conftests` hook, which runs before any conftest.py is collected -- so a
# local run with nothing built falls through to `pytest_configure` below,
# which builds a stub manifest outside the checkout, overrides the already-
# loaded `DJANGO_VITE` setting to point there, and forces django-vite to
# re-read it (its `AppConfig.ready()` cached the -- then empty -- loader
# during `django.setup()`).  Nothing is written under `frontend/dist`.
# --------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[2]

#: The deployment templates the packaging tests read: gunicorn, systemd, Apache, nginx.
DEPLOY_DIR = REPO_ROOT / "deploy"

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

#: Set by ``pytest_configure`` when it falls back to the stub manifest, so
#: ``pytest_unconfigure`` and the ``needs_frontend_build`` guard know.
_stub_manifest_dir: Path | None = None
_stub_manifest_path: Path | None = None

#: The manifest ``pytest_configure`` looked for before falling back, named in
#: the skip or failure reason: ``DJANGO_VITE_MANIFEST_PATH`` can point it
#: somewhere other than ``frontend/dist``, and then "not built" alone would
#: mislead.
_missing_manifest_path: Path | None = None

#: Set to a non-empty value by the CI runner (GitHub Actions sets ``CI=true``).
#: It is what tells ``pytest_runtest_setup`` that a missing frontend build is a
#: broken job rather than an unbuilt checkout.
CI_ENV_VAR = "CI"


def _reload_vite_loader() -> None:
    """Make django-vite re-read the manifest.

    Its ``AppConfig.ready()`` parses the manifest once and caches the loader
    during ``django.setup()``, before this hook runs, so an override made here
    would otherwise be ignored.
    """
    DjangoViteAssetLoader._instance = None
    DjangoViteAssetLoader.instance()


def pytest_configure(config: pytest.Config) -> None:
    """Fall back to a stub Vite manifest when no real one is configured."""
    global _stub_manifest_dir, _stub_manifest_path, _missing_manifest_path
    configured = Path(django_settings.DJANGO_VITE["default"]["manifest_path"])
    if configured.is_file():
        return
    _missing_manifest_path = configured
    _stub_manifest_dir = Path(tempfile.mkdtemp(prefix="caldart-vite-manifest-"))
    _stub_manifest_path = _stub_manifest_dir / "manifest.json"
    _stub_manifest_path.write_text(json.dumps(STUB_MANIFEST, indent=2))
    overridden = copy.deepcopy(django_settings.DJANGO_VITE)
    overridden["default"]["manifest_path"] = _stub_manifest_path
    django_settings.DJANGO_VITE = overridden
    _reload_vite_loader()


def pytest_unconfigure(config: pytest.Config) -> None:
    """Remove the temporary directories the session leaves behind.

    Those are the stub manifest directory ``pytest_configure`` created, when it
    created one, and the ``STATIC_ROOT`` that ``caldart.settings.test`` makes on
    import so WhiteNoise never warns about a missing directory.  A ``STATIC_ROOT``
    whose name does not carry that module's prefix is left alone, so a run under
    other settings cannot delete a real one.
    """
    if _stub_manifest_dir is not None:
        shutil.rmtree(_stub_manifest_dir, ignore_errors=True)
    static_root = Path(django_settings.STATIC_ROOT)
    if static_root.name.startswith(STATIC_ROOT_PREFIX):
        shutil.rmtree(static_root, ignore_errors=True)


def pytest_runtest_setup(item: pytest.Item) -> None:
    """Skip a ``needs_frontend_build`` test with no real bundle, or fail it in CI.

    The marker states the requirement declaratively and this hook enforces it.
    A developer who has not run ``make build`` gets a skip naming the manifest
    that was missing.  CI builds the frontend as part of the backend job, so
    there a missing manifest means the job is silently not running these tests
    at all: fail them instead, naming the same path.
    """
    if item.get_closest_marker("needs_frontend_build") is None:
        return
    if _stub_manifest_path is None:
        return
    reason = f"no Vite build at {_missing_manifest_path} (run `make build`)"
    if os.environ.get(CI_ENV_VAR, "") != "":
        pytest.fail(reason, pytrace=False)
    pytest.skip(reason)


# --------------------------------------------------------------------------
# Live HTTP guard
#
# The payment providers are the only code that talks to a third party, so the
# payment test modules are the only ones that can leave the machine.  Arming a
# respx router around each of their tests turns a call no route matches into an
# ``AllMockedAssertionError`` instead of a request: a test that forgets a mock
# fails loudly rather than depending on the network.
# --------------------------------------------------------------------------
#: Filename prefix of the test modules the guard covers.
PAYMENT_MODULE_PREFIX = "test_payments"


@pytest.fixture(autouse=True)
def _no_live_http(request: pytest.FixtureRequest) -> Iterator[None]:
    """Refuse any unmocked ``httpx`` call made by a payment test module.

    Tests outside those modules run untouched.  The router asserts nothing about
    which routes were used, so a test may register more routes than it exercises,
    and it nests inside the ``respx.mock`` router an individual test starts, so
    routes that test registers still answer.
    """
    if not request.path.name.startswith(PAYMENT_MODULE_PREFIX):
        yield
        return
    with respx.mock(assert_all_mocked=True, assert_all_called=False):
        yield


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
    """The plaintext password a ``UserFactory`` user gets unless one is passed."""
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
def superuser(db: None) -> UserModel:
    """Return a Django superuser holding the system-admin role."""
    return UserFactory(
        email="root@example.test", roles=[SYSTEM_ADMIN], is_superuser=True, is_staff=True
    )


#: The roles an allow/deny matrix covers: every role slug, least privileged first.
#: ``role_matrix`` turns it into one parametrized case per role.
ROLE_MATRIX: tuple[str, ...] = ROLE_SLUGS


def role_matrix(*allowed: str) -> list[tuple[str, bool]]:
    """Return ``(slug, allowed)`` for every role, for an allow/deny parametrization.

    ``allowed`` names the role slugs the endpoint under test admits; every other slug
    in ``ROLE_MATRIX`` is paired with ``False``.  The cases come back in privilege
    order, so ``role_matrix(ACCOUNT_ADMIN, SYSTEM_ADMIN)`` is
    ``[("member", False), ("dart_leader", False), ("user_admin", False),
    ("account_admin", True), ("website_admin", False), ("system_admin", True)]``
    and collects as ``[member-False]`` ... ``[system_admin-True]``.  Pair it with the
    ``all_role_users`` fixture to sign the matching user in.
    """
    return [(slug, slug in allowed) for slug in ROLE_MATRIX]


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


@pytest.fixture
def account_admin_client(api_client: APIClient, account_admin: UserModel) -> APIClient:
    """Return a DRF client already signed in as an account administrator.

    The name says which administrator: pytest-django's own ``admin_client`` is a plain
    Django client signed in as a superuser, which is a different caller entirely.
    """
    api_client.force_login(account_admin)
    return api_client


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


#: An aircraft register keyed by insurance scenario, as ``register`` builds it.
RegisterDict = dict[str, "Aircraft"]


@pytest.fixture
def register(db: None) -> RegisterDict:
    """Return a four-aircraft register covering every insurance state.

    ``current`` is N172SP, a Cessna 172S owned by a flying club, insured by Avemco for
    $1,000,000 per occurrence, $100,000 per person and a $145,000 hull, expiring in 200
    days.  ``expiring`` is N9021K, a Piper Archer owned by Marta Reyes, whose cover
    expires in 10 days.  ``expired`` is N33MM, a Mooney M20J owned by Owen Delgado,
    whose cover expired 5 days ago.  ``missing`` is N44BE, a Beechcraft Bonanza owned by
    an FBO, with no carrier, no amounts and no expiration on file.  ``expiring`` and
    ``expired`` carry the factory's default carrier and amounts.
    """
    today = timezone.localdate()
    return {
        "current": AircraftFactory(
            n_number="N172SP",
            make="Cessna",
            model="172S Skyhawk",
            owner_name="Palo Alto Flying Club",
            owner_type="club",
            insurance_carrier="Avemco",
            insurance_liability_per_occurrence_cents=100_000_000,
            insurance_liability_per_person_cents=10_000_000,
            insurance_hull_cents=14_500_000,
            insurance_expiration=today + timedelta(days=200),
        ),
        "expiring": AircraftFactory(
            n_number="N9021K",
            make="Piper",
            model="PA-28-181 Archer",
            owner_name="Marta Reyes",
            owner_type="individual",
            insurance_expiration=today + timedelta(days=10),
        ),
        "expired": AircraftFactory(
            n_number="N33MM",
            make="Mooney",
            model="M20J",
            owner_name="Owen Delgado",
            owner_type="individual",
            insurance_expiration=today - timedelta(days=5),
        ),
        "missing": AircraftFactory(
            n_number="N44BE",
            make="Beechcraft",
            model="A36 Bonanza",
            owner_name="Hayward Aviation Services",
            owner_type="fbo",
            insurance_carrier="",
            insurance_liability_per_occurrence_cents=0,
            insurance_liability_per_person_cents=0,
            insurance_hull_cents=None,
            insurance_expiration=None,
        ),
    }


@pytest.fixture
def backup_dir(tmp_path: Path, settings: Settings) -> Path:
    """Point ``BACKUP_DIR`` at a throwaway directory under ``tmp_path`` and create it.

    Returns the directory itself, so a test can write a dump into it or read back what
    the backup services left there.  Nothing ever touches the repository's own
    ``BACKUP_DIR``.
    """
    settings.BACKUP_DIR = tmp_path / "backups"
    return services.backup_dir()


@pytest.fixture
def payment_factory() -> type[PaymentFactory]:
    """Return the ``PaymentFactory`` class, for tests that need many payments."""
    return PaymentFactory


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
def today() -> Iterator[date]:
    """Freeze the clock at the current local date, and return that date.

    A test that requests this fixture computes its expected dates against a
    clock that cannot advance mid-test, rather than reading
    ``timezone.localdate()`` again at an arbitrary moment later in the run.
    """
    # Freezing a bare date freezes midnight UTC, which ``timezone.localdate()``
    # reads back as the day before in a negative-offset timezone; freezing the
    # exact current instant keeps the local date the fixture already returns.
    now = timezone.now()
    with freezegun.freeze_time(now):
        yield timezone.localdate()


@pytest.fixture
def days() -> Callable[[int], timedelta]:
    """``days(7)`` -> ``timedelta(days=7)``, to keep date math readable."""
    return lambda n: timedelta(days=n)


# --------------------------------------------------------------------------
# PDF text
#
# The reports are drawn by reportlab, which writes one compressed content
# stream per page.  Reading the strings back out of those streams costs nothing
# but ``zlib`` and ``base64``, and it lets a PDF test assert on the words the
# document actually shows instead of on its length.
# --------------------------------------------------------------------------
#: A content stream together with the ``/Filter`` entry that describes it.
_PDF_STREAM_RE = re.compile(
    rb"/Filter\s*(?P<filters>/\w+|\[[^\]]*\]).{0,400}?stream\r?\n(?P<data>.*?)\s*endstream",
    re.DOTALL,
)

#: One literal string shown by ``Tj``, or a whole ``TJ`` array of them.
_PDF_SHOW_RE = re.compile(
    rb"(?P<single>\((?:\\.|[^\\()])*\))\s*Tj"
    rb"|\[(?P<array>(?:\((?:\\.|[^\\()])*\)|[^\[\]])*)\]\s*TJ",
    re.DOTALL,
)

#: One literal string anywhere, used to pull the pieces out of a ``TJ`` array.
_PDF_STRING_RE = re.compile(rb"\((?P<body>(?:\\.|[^\\()])*)\)", re.DOTALL)

#: The escapes a PDF literal string may carry, besides ``\\ooo`` octal.
_PDF_ESCAPES = {
    b"n": b"\n",
    b"r": b"\r",
    b"t": b"\t",
    b"b": b"\b",
    b"f": b"\f",
    b"(": b"(",
    b")": b")",
    b"\\": b"\\",
}

_PDF_ESCAPE_RE = re.compile(rb"\\(?P<octal>[0-7]{1,3})|\\(?P<char>.)", re.DOTALL)


def _unescape_pdf_string(body: bytes) -> str:
    r"""Decode the body of one PDF literal string into text.

    Resolves the ``\n``-style escapes and ``\ooo`` octal escapes, then reads the
    result as Latin-1, which is what the fonts' WinAnsi encoding uses for every
    character the reports draw -- ``\267``, for instance, is the middle dot that
    separates the parts of a subtitle.
    """

    def replace(match: re.Match[bytes]) -> bytes:
        octal = match.group("octal")
        if octal is not None:
            return bytes([int(octal, 8)])
        char = match.group("char")
        return _PDF_ESCAPES.get(char, char)

    return _PDF_ESCAPE_RE.sub(replace, body).decode("latin-1")


def pdf_page_text(pdf: bytes) -> list[list[str]]:
    """Return every string a rendered PDF draws, one list per page.

    ``pdf`` is the document's raw bytes.  Each ``FlateDecode`` content stream is
    inflated (through an ``ASCII85Decode`` prefilter when one is declared) and
    scanned for the strings its ``Tj`` and ``TJ`` text operators show, in the order
    they are drawn; a ``TJ`` array joins into the single string it renders.
    reportlab writes one content stream per page in page order, so the outer list
    is the document's pages: ``pdf_page_text(body)[0]`` is the first page, and
    ``len(pdf_page_text(body))`` its page count.  Streams carrying any other filter
    are skipped, since they hold no text.
    """
    pages: list[list[str]] = []
    for stream in _PDF_STREAM_RE.finditer(pdf):
        filters = stream.group("filters")
        if b"FlateDecode" not in filters:
            continue
        data = stream.group("data")
        if b"ASCII85Decode" in filters:
            data = base64.a85decode(data, adobe=True)
        content = zlib.decompress(data)
        strings: list[str] = []
        for shown in _PDF_SHOW_RE.finditer(content):
            single = shown.group("single")
            if single is not None:
                strings.append(_unescape_pdf_string(single[1:-1]))
                continue
            pieces = _PDF_STRING_RE.finditer(shown.group("array"))
            strings.append("".join(_unescape_pdf_string(p.group("body")) for p in pieces))
        pages.append(strings)
    return pages


#: The type of the ``pdf_text`` fixture: body bytes in, one list of strings per page out.
PdfText = Callable[[bytes], list[list[str]]]


@pytest.fixture
def pdf_text() -> PdfText:
    """``pdf_text(body)`` -> the strings a rendered PDF draws, one list per page."""
    return pdf_page_text


#: One ``/Type /Page`` object, which the ``/Pages`` catalog entry must not match.
_PDF_PAGE_RE = re.compile(rb"/Type\s*/Page[^s]")


def pdf_page_count(pdf: bytes) -> int:
    """Return the number of pages in a rendered PDF, from its ``/Type /Page`` objects."""
    return len(_PDF_PAGE_RE.findall(pdf))


def read_csv(response: HttpResponseBase) -> list[list[str]]:
    """Return the rows of a streamed CSV download, each a list of string cells.

    ``response`` must be the ``StreamingHttpResponse`` that ``csv_response`` returns;
    any other response type fails the assertion rather than an attribute lookup.  The
    body is parsed with ``csv.reader``, so a quoted cell holding a comma, a newline or
    an embedded quote comes back as the single cell it is, and the header is row 0.
    """
    assert isinstance(response, StreamingHttpResponse)
    # A synchronous StreamingHttpResponse yields bytes; the async branch of the
    # declared union cannot occur here.
    chunks = cast(Iterator[bytes], response.streaming_content)
    body = b"".join(chunks).decode()
    return list(csv.reader(io.StringIO(body)))
