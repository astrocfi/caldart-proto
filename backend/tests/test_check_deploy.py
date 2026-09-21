"""Tests for the ``make check-deploy`` gate.

``check-deploy`` runs Django's deployment-only checks against
``caldart.settings.prod``, with a throwaway environment set inline in the Makefile
recipe.  These tests read that recipe (``make -n`` prints it without running it) and
then run the same command directly, so a failure names the exact warning without
parsing ``make``'s own output, and neither the environment nor the tag list under test
can drift from the recipe.

The command runs in an environment built from scratch -- the recipe's own assignments
plus only the variables the interpreter needs to start -- so an ambient ``DEBUG``,
``ALLOWED_HOSTS`` or ``SECURE_*`` export in the shell running pytest cannot change the
result.
"""

from __future__ import annotations

import functools
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Final

from django.core.checks.registry import registry

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

# The only variables carried into the child: what a Python interpreter needs to start
# and locate its environment.  Everything else the check reads comes from the recipe.
INTERPRETER_VARIABLES: Final[tuple[str, ...]] = (
    "HOME",
    "LANG",
    "PATH",
    "PYTHONPATH",
    "VIRTUAL_ENV",
)

#: The command the recipe runs, used to pick its line out of the printed recipe.
CHECK_COMMAND: Final[str] = "check --deploy"


def make_environment() -> dict[str, str]:
    """Return this process's environment without the variables ``make`` itself sets.

    ``make -n`` needs a working environment to find its own tools; only make's
    recursion variables are dropped, because a nested make that inherits them warns
    about a jobserver it cannot reach.
    """
    return {key: value for key, value in os.environ.items() if key not in MAKE_VARIABLES}


@functools.cache
def recipe_tokens() -> tuple[str, ...]:
    """Return the shell tokens of the single command the ``check-deploy`` recipe runs.

    ``make -n`` prints the recipe without running it.  The printed command begins with
    the throwaway environment assignments and ends with the management command and its
    arguments.
    """
    result = subprocess.run(  # noqa: S603 - resolved executable, arguments are test constants
        [MAKE, "-n", "check-deploy"],
        cwd=REPO_ROOT,
        env=make_environment(),
        capture_output=True,
        text=True,
        check=True,
    )
    folded = result.stdout.replace("\\\n", " ")
    lines = [line for line in folded.splitlines() if CHECK_COMMAND in line]
    assert len(lines) == 1, f"expected one {CHECK_COMMAND} line, got {lines}"
    return tuple(shlex.split(lines[0]))


def recipe_environment() -> dict[str, str]:
    """Return the ``NAME=value`` assignments the ``check-deploy`` recipe sets inline.

    The assignments lead the command, so reading stops at the first token that is not
    one.
    """
    assignments: dict[str, str] = {}
    for token in recipe_tokens():
        name, separator, value = token.partition("=")
        if separator != "=" or not name.isidentifier():
            break
        assignments[name] = value
    return assignments


def recipe_tags() -> set[str]:
    """Return the check tags the ``check-deploy`` recipe names with ``--tag``."""
    words = recipe_tokens()
    return {words[index + 1] for index, word in enumerate(words) if word == "--tag"}


def deployment_check_tags() -> set[str]:
    """Return every tag carried by a check Django runs only under ``--deploy``."""
    return {tag for check in registry.deployment_checks for tag in check.tags}


def run_check_deploy(overrides: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run the recipe's deployment check directly, under a from-scratch environment.

    The child environment is the recipe's own assignments plus the handful of variables
    the interpreter needs, so nothing the shell running pytest exports reaches the
    settings module.  ``overrides`` is applied last, so a test can flip one setting
    while keeping the rest fixed.  Returns the completed process without raising, so a
    test can assert on a non-zero exit status.
    """
    environment = {name: os.environ[name] for name in INTERPRETER_VARIABLES if name in os.environ}
    environment.update({key: value for key, value in os.environ.items() if key.startswith("LC_")})
    environment.update(recipe_environment())
    environment.update(overrides)

    arguments = ["check", "--deploy"]
    for tag in sorted(recipe_tags()):
        arguments += ["--tag", tag]
    arguments += ["--fail-level", "WARNING", "--settings", "caldart.settings.prod"]

    return subprocess.run(  # noqa: S603 - resolved interpreter and script, fixed arguments
        [sys.executable, str(MANAGE_PY), *arguments],
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


def test_the_recipe_runs_every_deployment_only_check() -> None:
    """The recipe's tags cover every check Django adds under ``--deploy``.

    Narrowing to one tag would drop the others silently, so the gate would stop
    reporting whole families of deployment findings.
    """
    assert recipe_tags() == deployment_check_tags()


def test_check_deploy_is_clean_under_the_throwaway_environment() -> None:
    """The gate passes on prod's own defaults, and ``security.W019`` stays silenced.

    ``X_FRAME_OPTIONS`` is deliberately ``"SAMEORIGIN"`` rather than ``"DENY"``, so the
    warning about it must not reach the output.
    """
    result = run_check_deploy({})

    assert result.returncode == 0
    assert "security.W019" not in result.stderr


def test_check_deploy_fails_on_w008_when_ssl_redirect_is_off() -> None:
    """Turning ``SECURE_SSL_REDIRECT`` off makes the gate fail on ``security.W008``."""
    result = run_check_deploy({"SECURE_SSL_REDIRECT": "false"})

    assert result.returncode != 0
    assert "security.W008" in result.stderr
