"""Seeding a server through ``deploy/install.sh --seed-demo``.

``docs/developer/deployment.rst`` and ``deploy/README.rst`` describe
``--seed-demo``: it runs ``manage.py seed_demo`` in the database step, after
``seed_roles`` and before ``--seed-content``'s ``seed_content``, and the
installer's summary names the shared demo password when it ran.  This module
is a sibling of ``test_deploy_scripts.py`` rather than a new section of it,
which is already at its line budget; it duplicates the small amount of dry-run
test scaffolding that module defines instead of importing it, since
``test_lint_config.py`` fixes the test modules allowed to import a sibling and
this pair is not among them.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

REPO_ROOT: Final = Path(__file__).resolve().parents[2]
DEPLOY_DIR: Final = REPO_ROOT / "deploy"
MANAGE_PY: Final = REPO_ROOT / "backend" / "manage.py"

_bash = shutil.which("bash")
if _bash is None:  # pragma: no cover - the dev environment always has bash installed.
    raise RuntimeError("bash is not on PATH")
BASH: Final[str] = _bash

#: The flags a first install needs with the default web server and certbot.
FIRST_INSTALL: Final = (
    "--hostname",
    "caldart.test",
    "--certbot-email",
    "ops@caldart.test",
    "--email-url",
    "smtp://localhost:25",
    "--admin-email",
    "ops@caldart.test",
)

#: The smallest environment ``caldart.settings.prod`` boots with; only the
#: syntax of ``DATABASE_URL`` matters here, since ``--help`` never connects.
PROD_ENV: Final = {
    "SECRET_KEY": "prod-secret-not-a-real-key",
    "ALLOWED_HOSTS": "caldart.example.org",
    "SITE_URL": "https://caldart.example.org",
    "EMAIL_URL": "smtp://caldart%40example.org:hunter2@smtp.example.org:587",
    "DATABASE_URL": "postgres://caldart:caldart@db.example.org:5432/caldart",
}


@pytest.fixture
def etc(tmp_path: Path) -> Path:
    """An empty directory standing in for ``/etc/caldart``."""
    path = tmp_path / "etc"
    path.mkdir()
    return path


def _os_release(tmp_path: Path) -> Path:
    """Write an Ubuntu ``os-release`` under ``tmp_path`` and return its path."""
    path = tmp_path / "os-release-ubuntu"
    path.write_text('NAME="Ubuntu"\nID=ubuntu\nID_LIKE=debian\nVERSION_CODENAME=noble\n')
    return path


def _env(etc: Path, **extra: str) -> dict[str, str]:
    """A clean environment for a script: the interpreter's basics plus ``CALDART_ETC``."""
    base = {key: os.environ[key] for key in ("PATH", "HOME", "LANG") if key in os.environ}
    return {**base, "CALDART_ETC": str(etc), **extra}


def _machine_path(tmp_path: Path) -> str:
    """A ``PATH`` whose ``ss`` and ``docker`` describe a machine with nothing running.

    ``postgres_check_port`` and the gunicorn equivalent run ``ss`` and ``docker
    container inspect`` even in a dry run, so a real listener on this host's
    5432 or 8001 must not reach the test.
    """
    shims = tmp_path / "machine"
    shims.mkdir(exist_ok=True)
    (shims / "ss").write_text("#!/bin/sh\n")
    (shims / "docker").write_text("#!/bin/sh\nexit 1\n")
    for shim in shims.iterdir():
        shim.chmod(0o755)
    return f"{shims}:{os.environ['PATH']}"


def _run(
    script: Path, *args: str, env: dict[str, str], cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    """Run ``script`` with ``bash`` and capture its output."""
    return subprocess.run(  # noqa: S603 - fixed argv, BASH is a resolved path
        [BASH, str(script), *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        cwd=cwd,
    )


def _commands(result: subprocess.CompletedProcess[str]) -> list[str]:
    """The commands a dry run printed, in order, without their ``+ `` prefix."""
    return [line[2:] for line in result.stdout.splitlines() if line.startswith("+ ")]


def _position(commands: list[str], fragment: str) -> int:
    """The index of the first command containing ``fragment``; fails when none does."""
    for index, command in enumerate(commands):
        if fragment in command:
            return index
    pytest.fail(f"no command contains {fragment!r}")


def _install_dry_run(tmp_path: Path, etc: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    """The dry run of a first ``install.sh`` on Ubuntu, plus the ``extra`` flags."""
    env = _env(
        etc,
        CALDART_OS_RELEASE=str(_os_release(tmp_path)),
        PATH=_machine_path(tmp_path),
    )
    return _run(DEPLOY_DIR / "install.sh", "--dry-run", *FIRST_INSTALL, *extra, env=env)


# -- the database step ---------------------------------------------------------------


def test_seed_demo_is_absent_without_the_flag(tmp_path: Path, etc: Path) -> None:
    """Without ``--seed-demo`` the database step never runs ``seed_demo``."""
    commands = _commands(_install_dry_run(tmp_path, etc, "--seed-content"))
    assert not any("manage.py seed_demo" in command for command in commands)


def test_seed_demo_runs_between_the_roles_and_the_content(tmp_path: Path, etc: Path) -> None:
    """``--seed-demo --seed-content`` runs the seeders in the order ``make seed`` does."""
    commands = _commands(_install_dry_run(tmp_path, etc, "--seed-demo", "--seed-content"))
    assert (
        _position(commands, "manage.py seed_roles")
        < _position(commands, "manage.py seed_demo")
        < _position(commands, "manage.py seed_content")
    )


def test_seed_demo_alone_runs_after_the_roles(tmp_path: Path, etc: Path) -> None:
    """``--seed-demo`` alone still runs and loads no example pages."""
    commands = _commands(_install_dry_run(tmp_path, etc, "--seed-demo"))
    assert _position(commands, "manage.py seed_roles") < _position(commands, "manage.py seed_demo")
    assert not any("manage.py seed_content" in command for command in commands)


@pytest.mark.parametrize(
    ("flags", "expect_present"),
    [(("--seed-demo",), True), ((), False)],
    ids=["with-the-flag", "without-the-flag"],
)
def test_the_summary_names_the_demo_password_only_with_the_flag(
    flags: tuple[str, ...], expect_present: bool, tmp_path: Path, etc: Path
) -> None:
    """The caution about the shared demo password appears only when it was seeded."""
    output = _install_dry_run(tmp_path, etc, *flags).stdout
    sentence = (
        "Demo accounts seeded: their shared password is the one README.rst "
        "documents; this is a demonstration server."
    )
    assert (sentence in output) is expect_present


# -- bootstrap.sh ---------------------------------------------------------------------


def test_bootstrap_passes_seed_demo_through(tmp_path: Path) -> None:
    """``--seed-demo`` reaches ``install.sh``, as ``--seed-content`` does."""
    env = _env(tmp_path, CALDART_ROOT=str(tmp_path / "srv"))
    result = _run(
        DEPLOY_DIR / "bootstrap.sh", "--dry-run", "--repo", "/nowhere", "--seed-demo", env=env
    )
    assert _commands(result)[-1] == f"bash {tmp_path}/srv/deploy/install.sh --dry-run --seed-demo"


# -- production settings ---------------------------------------------------------------


@pytest.mark.parametrize("command", ["seed_demo", "seed_content"])
def test_seed_commands_import_under_production_settings(command: str) -> None:
    """``--settings caldart.settings.prod`` loads the command without error.

    ``--help`` exits before ``handle()`` runs, so this needs no database; it
    proves the command and the seed modules it imports carry no assumption
    ``caldart.settings.prod`` does not meet, such as reading ``DEBUG``.
    """
    base = {key: os.environ[key] for key in ("PATH", "HOME", "LANG") if key in os.environ}
    result = subprocess.run(  # noqa: S603 - fixed argv, sys.executable is this interpreter
        [sys.executable, str(MANAGE_PY), command, "--help", "--settings", "caldart.settings.prod"],
        capture_output=True,
        text=True,
        check=False,
        env={**base, **PROD_ENV},
    )
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout


def test_no_seed_module_reads_debug() -> None:
    """The seed command and every app seeder it runs read no ``DEBUG`` setting.

    ``manage.sh`` always runs under ``caldart.settings.prod``, where ``DEBUG``
    is off; a seeder that branched on it would behave differently than a
    developer running ``make seed`` sees.
    """
    command = REPO_ROOT / "backend/apps/accounts/management/commands/seed_demo.py"
    seed_apps = (
        "accounts",
        "members",
        "aircraft",
        "payments",
        "reports",
        "notifications",
        "cms",
    )
    seeders = [REPO_ROOT / f"backend/apps/{app}/seed.py" for app in seed_apps]
    for source in [command, *seeders]:
        assert "DEBUG" not in source.read_text(), f"{source} reads DEBUG"
