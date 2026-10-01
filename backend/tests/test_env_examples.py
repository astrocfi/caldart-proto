"""Every environment variable the settings modules read is named in an example file.

``.env.example`` is the development template and ``deploy/caldart.env.example`` the
production one.  A variable is named when a line in either file, commented out or not,
assigns it, so an operator can find each knob without reading the settings.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SETTINGS_DIR = REPO_ROOT / "backend" / "caldart" / "settings"
EXAMPLE_FILES = [REPO_ROOT / ".env.example", REPO_ROOT / "deploy" / "caldart.env.example"]
ENV_READ = re.compile(r"\benv(?:\.\w+)?\(\s*\"([A-Z][A-Z0-9_]*)\"")
ASSIGNMENT = re.compile(r"^#?([A-Z][A-Z0-9_]*)=", re.MULTILINE)


def _settings_variables() -> set[str]:
    """Return the name of every variable a settings module reads through ``env``."""
    return {
        name
        for path in SETTINGS_DIR.glob("*.py")
        for name in ENV_READ.findall(path.read_text(encoding="utf-8"))
    }


def _assigned(path: Path) -> set[str]:
    """Return the variables an example file assigns, whether or not commented out."""
    return set(ASSIGNMENT.findall(path.read_text(encoding="utf-8")))


def test_the_settings_modules_read_variables() -> None:
    """The scan finds the variables, so the checks below are not vacuous."""
    assert "SECRET_KEY" in _settings_variables()


@pytest.mark.parametrize("name", sorted(_settings_variables()))
def test_every_settings_variable_appears_in_an_example_file(name: str) -> None:
    """Each variable the settings read is assigned in one of the two example files."""
    named = set().union(*(_assigned(path) for path in EXAMPLE_FILES))
    assert name in named


def test_the_production_example_names_the_mock_provider_switches() -> None:
    """The production template names both payment-mock variables."""
    assert {"PAYMENTS_MOCK_ENABLED", "PAYMENTS_MOCK_ENABLED_IN_PRODUCTION"} <= _assigned(
        EXAMPLE_FILES[1]
    )
