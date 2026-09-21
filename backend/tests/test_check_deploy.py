"""Tests for the ``make check-deploy`` gate.

``check-deploy`` runs Django's production security checks
(``manage.py check --deploy --tag security``) against ``caldart.settings.prod``, with a
throwaway environment set inline in the Makefile recipe.  These tests read that
environment out of the recipe itself (``make -n`` prints it without running it) and then
run the same command directly, so a failure names the exact warning without parsing
``make``'s own output, and the environment under test cannot drift from the recipe.
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Final

REPO_ROOT = Path(__file__).resolve().parents[2]
MANAGE_PY = REPO_ROOT / "backend" / "manage.py"

_make = shutil.which("make")
if _make is None:  # pragma: no cover - the dev environment always has make installed.
    raise RuntimeError("make is not on PATH")
MAKE: Final[str] = _make

# A nested make that inherits its parent's flags warns about the unavailable jobserver,
# so drop make's own environment before printing the recipe.
MAKE_VARIABLES: Final[tuple[str, ...]] = (
    "MAKEFLAGS",
    "MFLAGS",
    "MAKELEVEL",
    "MAKE_TERMOUT",
    "MAKE_TERMERR",
)

#: The command the recipe runs, used to pick its line out of the printed recipe.
CHECK_COMMAND: Final[str] = "check --deploy"


def clean_environment() -> dict[str, str]:
    """Return this process's environment without make's variables or any secure flag.

    Dropping every ``SECURE_*`` variable is what makes these tests measure
    ``caldart.settings.prod``'s own defaults rather than whatever the shell running
    pytest happens to export.
    """
    return {
        key: value
        for key, value in os.environ.items()
        if key not in MAKE_VARIABLES and not key.startswith("SECURE_")
    }


def recipe_environment() -> dict[str, str]:
    """Return the ``NAME=value`` assignments the ``check-deploy`` recipe sets inline.

    ``make -n`` prints the recipe without running it.  The printed command begins with
    the throwaway environment and ends with the management command, so the leading
    assignments are the environment the gate actually runs under.
    """
    result = subprocess.run(  # noqa: S603 - resolved executable, arguments are test constants
        [MAKE, "-n", "check-deploy"],
        cwd=REPO_ROOT,
        env=clean_environment(),
        capture_output=True,
        text=True,
        check=True,
    )
    folded = result.stdout.replace("\\\n", " ")
    lines = [line for line in folded.splitlines() if CHECK_COMMAND in line]
    assert len(lines) == 1, f"expected one {CHECK_COMMAND} line, got {lines}"

    assignments: dict[str, str] = {}
    for token in shlex.split(lines[0]):
        name, separator, value = token.partition("=")
        if separator != "=" or not name.isidentifier():
            break
        assignments[name] = value
    return assignments


def run_check_deploy(overrides: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run ``manage.py check --deploy --tag security`` under the recipe's environment.

    ``overrides`` is applied after the recipe's own assignments, so a test can flip one
    setting while keeping the rest fixed.  Returns the completed process without
    raising, so a test can assert on a non-zero exit status.
    """
    environment = clean_environment()
    environment.update(recipe_environment())
    environment.update(overrides)
    return subprocess.run(  # noqa: S603 - resolved interpreter and script, fixed arguments
        [
            sys.executable,
            str(MANAGE_PY),
            "check",
            "--deploy",
            "--tag",
            "security",
            "--fail-level",
            "WARNING",
            "--settings",
            "caldart.settings.prod",
        ],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_the_recipe_pins_no_secure_flag() -> None:
    """The recipe sets no ``SECURE_*`` variable, so prod's own defaults are checked.

    A pinned flag would answer the check with the recipe's value, and a regression that
    turned that default off would pass the gate.
    """
    pinned = sorted(name for name in recipe_environment() if name.startswith("SECURE_"))

    assert pinned == []


def test_check_deploy_passes_under_the_throwaway_environment() -> None:
    """The gate is clean under ``caldart.settings.prod``'s own secure defaults."""
    result = run_check_deploy({})

    assert result.returncode == 0


def test_check_deploy_fails_on_w008_when_ssl_redirect_is_off() -> None:
    """Turning ``SECURE_SSL_REDIRECT`` off makes the gate fail on ``security.W008``."""
    result = run_check_deploy({"SECURE_SSL_REDIRECT": "false"})

    assert result.returncode != 0
    assert "security.W008" in result.stderr


def test_check_deploy_does_not_report_the_silenced_frame_options_warning() -> None:
    """``security.W019`` stays silenced: ``X_FRAME_OPTIONS`` is deliberately not DENY."""
    result = run_check_deploy({})

    assert "security.W019" not in result.stderr
