"""How ``AUTH_THROTTLE_*`` environment values become throttle rates.

``caldart/settings/base.py`` is executed here as a throwaway module, so each
case sees a genuine settings import rather than a helper called in isolation,
and the live ``django.conf.settings`` is left alone.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
from django.core.exceptions import ImproperlyConfigured
from pytest_django import Settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.throttling import LOGIN_SCOPE, LoginThrottle
from tests.conftest import LOGIN_URL

pytestmark = pytest.mark.django_db


BASE_SETTINGS = Path(__file__).resolve().parents[1] / "caldart" / "settings" / "base.py"

#: ``(environment variable, throttle scope, shipped default)`` for each rate.
RATE_VARIABLES = [
    ("AUTH_THROTTLE_LOGIN", "auth_login", "20/min"),
    ("AUTH_THROTTLE_REGISTER", "auth_register", "10/hour"),
    ("AUTH_THROTTLE_PASSWORD_RESET", "auth_password_reset", "10/hour"),
]


def import_base_settings() -> ModuleType:
    """Execute ``settings/base.py`` as a fresh module and return it.

    It is loaded outside ``sys.modules`` under its own name, so importing it
    repeatedly costs nothing beyond the execution and cannot disturb the
    settings the rest of the suite runs under.
    """
    spec = importlib.util.spec_from_file_location("caldart_base_settings_probe", BASE_SETTINGS)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(("variable", "scope", "default"), RATE_VARIABLES)
def test_an_unset_variable_uses_the_shipped_default(
    monkeypatch: pytest.MonkeyPatch, variable: str, scope: str, default: str
) -> None:
    """With no environment variable set, the shipped default rate is used."""
    monkeypatch.delenv(variable, raising=False)

    assert import_base_settings().AUTH_THROTTLE_RATES[scope] == default


@pytest.mark.parametrize(("variable", "scope", "default"), RATE_VARIABLES)
def test_an_empty_variable_turns_the_throttle_off(
    monkeypatch: pytest.MonkeyPatch, variable: str, scope: str, default: str
) -> None:
    """An empty environment variable turns the corresponding throttle off."""
    monkeypatch.setenv(variable, "")

    assert import_base_settings().AUTH_THROTTLE_RATES[scope] is None


@pytest.mark.parametrize(("variable", "scope", "default"), RATE_VARIABLES)
def test_a_blank_variable_turns_the_throttle_off(
    monkeypatch: pytest.MonkeyPatch, variable: str, scope: str, default: str
) -> None:
    """A whitespace-only environment variable also turns the throttle off."""
    monkeypatch.setenv(variable, "   ")

    assert import_base_settings().AUTH_THROTTLE_RATES[scope] is None


@pytest.mark.parametrize(("variable", "scope", "default"), RATE_VARIABLES)
def test_a_configured_rate_is_kept(
    monkeypatch: pytest.MonkeyPatch, variable: str, scope: str, default: str
) -> None:
    """A well-formed rate from the environment is stored exactly as given."""
    monkeypatch.setenv(variable, "5/second")

    assert import_base_settings().AUTH_THROTTLE_RATES[scope] == "5/second"


def test_surrounding_whitespace_is_stripped_from_a_rate(monkeypatch: pytest.MonkeyPatch) -> None:
    """Leading and trailing whitespace around a configured rate is stripped."""
    monkeypatch.setenv("AUTH_THROTTLE_LOGIN", "  30/min  ")

    assert import_base_settings().AUTH_THROTTLE_RATES["auth_login"] == "30/min"


@pytest.mark.parametrize(
    "rate",
    ["lots", "20", "20min", "/min", "20/", "20/x", "twenty/min", "-5/min", "20/min/hour"],
)
@pytest.mark.parametrize(("variable", "scope", "default"), RATE_VARIABLES)
def test_a_malformed_rate_stops_start_up(
    monkeypatch: pytest.MonkeyPatch, variable: str, scope: str, default: str, rate: str
) -> None:
    """A rate that does not match ``<count>/<period>`` raises ``ImproperlyConfigured``."""
    monkeypatch.setenv(variable, rate)

    with pytest.raises(ImproperlyConfigured) as excinfo:
        import_base_settings()

    assert variable in str(excinfo.value)
    assert repr(rate) in str(excinfo.value)


def test_an_empty_rate_makes_the_throttle_inert(settings: Settings) -> None:
    """An empty configured rate makes ``get_rate`` return ``None``."""
    settings.AUTH_THROTTLE_RATES = {LOGIN_SCOPE: ""}
    assert LoginThrottle().get_rate() is None


def test_an_empty_rate_leaves_login_unlimited(
    api_client: APIClient, member: User, settings: Settings
) -> None:
    """An empty configured rate is off, not a 500 from an unparseable rate."""
    settings.AUTH_THROTTLE_RATES = {LOGIN_SCOPE: ""}
    statuses = {
        api_client.post(LOGIN_URL, {"email": member.email, "password": "wrong"}).status_code
        for _ in range(25)
    }

    assert statuses == {400}
