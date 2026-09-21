"""Production configuration fails closed rather than borrowing development values.

Three defaults carry the weight.  ``prod.py`` reads the process environment
alone, so a repository ``.env`` cannot fill in a missing variable or switch the
mock payment provider on.  The WSGI and ASGI entry points insist on being told
which settings module to load rather than guessing at one.  And the production
environment template ships its required values commented out, so an unedited
copy refuses to start instead of serving with a guessed value.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import environ
import pytest
from django.core.exceptions import ImproperlyConfigured

from tests.test_sysadmin_settings import (
    DEPLOY,
    MINIMAL_ENV,
    REPO_ROOT,
    UNSET,
    apply_production_environment,
    import_prod,
)

DOTENV_PATH = REPO_ROOT / ".env"
PRODUCTION_TEMPLATE = DEPLOY / "caldart.env.example"
WEB_UNIT = DEPLOY / "systemd" / "caldart-web.service"

#: The key ``base.py`` defaults to and ``.env.example`` ships.  It is published
#: in the repository, so a box still running it can have its sessions and
#: password-reset links forged by anyone who has read the source.
DEVELOPMENT_SECRET_KEY = "dev-insecure-secret-key-change-me"  # noqa: S105 - already public

SETTINGS_PACKAGE = "caldart.settings"

#: Settings submodules these tests re-import, dependents first.
RELOADABLE = ("prod", "dev", "test", "_dotenv")


def forget(submodule: str) -> None:
    """Make the next import of a settings submodule execute it again.

    Dropping it from ``sys.modules`` is not enough on its own: ``from . import
    _dotenv`` is answered from the package's attributes, which outlive the
    entry, and the module's side effects would be skipped.
    """
    sys.modules.pop(f"{SETTINGS_PACKAGE}.{submodule}", None)
    package = sys.modules.get(SETTINGS_PACKAGE)
    if package is not None and hasattr(package, submodule):
        delattr(package, submodule)


def import_prod_over_a_fresh_base() -> ModuleType:
    """Import production settings with ``base`` re-executed as well.

    The whole suite runs with ``base`` already imported, so its module-level
    reads happened long ago.  Re-executing it is what makes a ``.env`` read
    anywhere in the production import chain observable.  The base module the
    suite is running against is put back afterwards.
    """
    original = sys.modules.get("caldart.settings.base")
    sys.modules.pop("caldart.settings.base", None)
    try:
        return import_prod()
    finally:
        if original is not None:
            sys.modules["caldart.settings.base"] = original


def uncommented_variables(template: Path) -> dict[str, str]:
    """The ``KEY=VALUE`` assignments an unedited copy of a template would export."""
    values: dict[str, str] = {}
    for raw in template.read_text().splitlines():
        line = raw.strip()
        if len(line) == 0 or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


@pytest.fixture
def fresh_settings() -> Iterator[None]:
    """Re-import the settings submodules from scratch, and leave them clean."""
    for submodule in RELOADABLE:
        forget(submodule)
    yield
    for submodule in RELOADABLE:
        forget(submodule)


@pytest.fixture
def read_env_calls(monkeypatch: pytest.MonkeyPatch) -> list[Path | None]:
    """Record every ``environ.Env.read_env`` call instead of touching the file."""
    calls: list[Path | None] = []

    def record(env_file: Path | None = None, **overrides: object) -> None:
        calls.append(env_file)

    monkeypatch.setattr(environ.Env, "read_env", record)
    return calls


@pytest.fixture
def prod_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """A minimal production environment; the module is not imported yet."""
    apply_production_environment(monkeypatch)
    yield
    sys.modules.pop("caldart.settings.prod", None)


@pytest.fixture
def bare_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """No CalDART variable set at all, whatever the developer's shell holds."""
    for key in [*MINIMAL_ENV, *UNSET]:
        monkeypatch.delenv(key, raising=False)


# --------------------------------------------------------------- the .env file
def test_production_settings_never_read_the_dotenv_file(
    prod_env: None, read_env_calls: list[Path | None]
) -> None:
    """A stray ``.env`` beside the checkout must not fill in a missing variable."""
    import_prod_over_a_fresh_base()

    assert read_env_calls == []


def test_development_settings_read_the_dotenv_file(
    fresh_settings: None, read_env_calls: list[Path | None]
) -> None:
    """Development settings read the repository ``.env`` file exactly once."""
    importlib.import_module("caldart.settings.dev")

    assert read_env_calls == [DOTENV_PATH]


def test_test_settings_read_the_dotenv_file(
    fresh_settings: None, read_env_calls: list[Path | None]
) -> None:
    """``pytest`` picks its per-worktree ``DATABASE_URL`` out of ``.env``."""
    importlib.import_module("caldart.settings.test")

    assert read_env_calls == [DOTENV_PATH]


def test_the_dotenv_module_reads_the_repository_env_file(fresh_settings: None) -> None:
    """The one file involved, and the reason production must not import it."""
    dotenv = importlib.import_module(f"{SETTINGS_PACKAGE}._dotenv")

    assert dotenv.DOTENV_PATH == DOTENV_PATH


def test_a_missing_secret_key_is_a_start_up_error(
    prod_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No file is consulted, so nothing can fill the gap in."""
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(ImproperlyConfigured, match="SECRET_KEY"):
        import_prod_over_a_fresh_base()


def test_production_refuses_the_published_development_secret_key(
    prod_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Production refuses to start with the published development secret key."""
    monkeypatch.setenv("SECRET_KEY", DEVELOPMENT_SECRET_KEY)

    with pytest.raises(ImproperlyConfigured, match="SECRET_KEY"):
        import_prod()


# --------------------------------------------------------------- mock payments
def test_production_ignores_the_development_mock_payments_flag(
    prod_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An ``.env`` copied onto the server would otherwise hand out memberships."""
    monkeypatch.setenv("PAYMENTS_MOCK_ENABLED", "true")

    prod = import_prod()
    assert prod.PAYMENTS_MOCK_ENABLED is False


def test_production_mock_payments_need_their_own_variable(
    prod_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Production enables mock payments only via its own dedicated variable."""
    monkeypatch.setenv("PAYMENTS_MOCK_ENABLED_IN_PRODUCTION", "true")

    prod = import_prod()
    assert prod.PAYMENTS_MOCK_ENABLED is True


# --------------------------------------------------------------- entry points
@pytest.mark.parametrize("entry_point", ["caldart.wsgi", "caldart.asgi"])
def test_the_application_servers_require_the_settings_module(
    monkeypatch: pytest.MonkeyPatch, entry_point: str
) -> None:
    """WSGI and ASGI refuse to start without ``DJANGO_SETTINGS_MODULE`` set."""
    monkeypatch.delenv("DJANGO_SETTINGS_MODULE", raising=False)
    sys.modules.pop(entry_point, None)

    with pytest.raises(ImproperlyConfigured, match="DJANGO_SETTINGS_MODULE"):
        importlib.import_module(entry_point)


def test_manage_py_still_defaults_to_the_development_settings() -> None:
    """A local ``manage.py`` call needs no ceremony; a server is told explicitly."""
    source = (REPO_ROOT / "backend" / "manage.py").read_text()

    assert 'setdefault("DJANGO_SETTINGS_MODULE", "caldart.settings.dev")' in source


# ---------------------------------------------------------- the env template
def test_the_production_template_is_shipped() -> None:
    """``deploy/caldart.env.example`` exists in the repository."""
    assert PRODUCTION_TEMPLATE.is_file()


def test_the_production_template_sets_no_secret_key() -> None:
    """The production environment template leaves ``SECRET_KEY`` commented out."""
    assert "SECRET_KEY" not in uncommented_variables(PRODUCTION_TEMPLATE)


def test_the_production_template_turns_debug_off() -> None:
    """The production environment template sets ``DEBUG=false``."""
    assert uncommented_variables(PRODUCTION_TEMPLATE)["DEBUG"] == "false"


def test_the_production_template_enables_no_mock_payments() -> None:
    """The production environment template leaves every ``MOCK`` variable unset."""
    enabled = [key for key in uncommented_variables(PRODUCTION_TEMPLATE) if "MOCK" in key]

    assert enabled == []


def test_an_unedited_production_template_refuses_to_start(
    bare_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exporting the template's uncommented values as-is still fails on ``SECRET_KEY``."""
    for key, value in uncommented_variables(PRODUCTION_TEMPLATE).items():
        monkeypatch.setenv(key, value)

    with pytest.raises(ImproperlyConfigured, match="SECRET_KEY"):
        import_prod()


def test_the_web_unit_installs_the_production_template() -> None:
    """The web systemd unit installs the template to ``/etc/caldart/caldart.env``."""
    assert "deploy/caldart.env.example /etc/caldart/caldart.env" in WEB_UNIT.read_text()
