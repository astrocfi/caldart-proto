"""Tests for the on/off switches the Makefile passes to management commands.

``YES`` on ``make restore`` and ``DRY_RUN`` on ``make reminders`` are switches:
``1``, ``yes`` and ``true`` turn the option on, ``0``, ``no``, ``false``, an empty
value and an unset variable leave it off, and any other value stops ``make``.  Each
test runs ``make -n``, which prints the recipe without running it, so nothing here
touches the database, the mail server or a backup file.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Final

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Resolved once so every ``run_make`` call passes an absolute path, not a bare name
#: `PATH` would otherwise have to resolve on each subprocess launch.
_make = shutil.which("make")
if _make is None:  # pragma: no cover - the dev environment always has make installed.
    raise RuntimeError("make is not on PATH")
MAKE: Final[str] = _make

# `make test` runs pytest from inside make, and a nested make that inherits its
# parent's flags warns about the unavailable jobserver on stderr.  Drop make's own
# environment, and the switches under test, so the subprocess starts clean.
UNSET_VARIABLES = ("MAKEFLAGS", "MFLAGS", "MAKELEVEL", "MAKE_TERMOUT", "MAKE_TERMERR")

ON_VALUES = ("1", "yes", "true")
OFF_VALUES = ("0", "no", "false", "")

# Each case is a target, the arguments it needs, its switch, and the option that
# switch controls in the printed recipe.
SWITCH_CASES = (
    pytest.param("restore", ["FILE=x"], "YES", "db_restore", "--yes", id="restore-yes"),
    pytest.param(
        "reminders", [], "DRY_RUN", "send_renewal_reminders", "--dry-run", id="reminders-dry-run"
    ),
)


def run_make(*arguments: str) -> subprocess.CompletedProcess[str]:
    """Run ``make -n`` with the given arguments in the repository root.

    The recipe is printed rather than run.  Returns the completed process without
    raising, so a test can assert on a non-zero exit status.
    """
    environment = {key: value for key, value in os.environ.items() if key not in UNSET_VARIABLES}
    environment.pop("YES", None)
    environment.pop("DRY_RUN", None)
    return subprocess.run(  # noqa: S603 - resolved executable, arguments are test constants
        [MAKE, "-n", *arguments],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def command_line(stdout: str, command: str) -> str:
    """Return the single printed recipe line that invokes the named command.

    Backslash continuations are folded into one line first, so a recipe split over
    several source lines reads as the one shell command ``make`` would run.  Fails
    the test when the command appears other than exactly once.
    """
    folded = stdout.replace("\\\n", " ")
    matches = [line for line in folded.splitlines() if command in line]
    assert len(matches) == 1, f"expected one {command} line, got {matches}"
    return matches[0]


@pytest.mark.parametrize(("target", "arguments", "variable", "command", "option"), SWITCH_CASES)
@pytest.mark.parametrize("value", ON_VALUES)
def test_switch_adds_the_option_when_on(
    target: str, arguments: list[str], variable: str, command: str, option: str, value: str
) -> None:
    """``1``, ``yes`` and ``true`` pass the option to the management command."""
    result = run_make(target, *arguments, f"{variable}={value}")

    assert option in command_line(result.stdout, command)


@pytest.mark.parametrize(("target", "arguments", "variable", "command", "option"), SWITCH_CASES)
@pytest.mark.parametrize("value", OFF_VALUES)
def test_switch_omits_the_option_when_off(
    target: str, arguments: list[str], variable: str, command: str, option: str, value: str
) -> None:
    """``0``, ``no``, ``false`` and an empty value leave the option off."""
    result = run_make(target, *arguments, f"{variable}={value}")

    assert option not in command_line(result.stdout, command)


@pytest.mark.parametrize(("target", "arguments", "variable", "command", "option"), SWITCH_CASES)
def test_switch_omits_the_option_when_unset(
    target: str, arguments: list[str], variable: str, command: str, option: str
) -> None:
    """A switch nobody sets leaves the option off."""
    result = run_make(target, *arguments)

    assert option not in command_line(result.stdout, command)


@pytest.mark.parametrize(("target", "arguments", "variable", "command", "option"), SWITCH_CASES)
def test_switch_stops_make_on_an_unknown_value(
    target: str, arguments: list[str], variable: str, command: str, option: str
) -> None:
    """Any other value stops ``make`` with a message naming the variable."""
    result = run_make(target, *arguments, f"{variable}=maybe")

    assert result.returncode != 0
    assert f"{variable}=maybe" in result.stderr


@pytest.mark.parametrize(("target", "arguments", "variable", "command", "option"), SWITCH_CASES)
def test_unknown_value_runs_nothing(
    target: str, arguments: list[str], variable: str, command: str, option: str
) -> None:
    """The error comes before the recipe, so no command is printed to run."""
    result = run_make(target, *arguments, f"{variable}=maybe")

    assert command not in result.stdout
