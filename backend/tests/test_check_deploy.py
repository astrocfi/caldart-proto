"""Tests for the ``make check-deploy`` gate.

``check-deploy`` runs Django's production security checks
(``manage.py check --deploy --tag security``) against ``caldart.settings.prod``, with a
throwaway environment set inline in the Makefile recipe. These tests run that same
command directly against a copy of the throwaway environment, so a failure names the
exact warning without parsing ``make``'s own output.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Final

REPO_ROOT = Path(__file__).resolve().parents[2]
MANAGE_PY = REPO_ROOT / "backend" / "manage.py"

#: The throwaway environment ``make check-deploy`` sets inline, reproduced here so a
#: test can vary one variable at a time without touching the Makefile.
THROWAWAY_ENVIRONMENT: Final[dict[str, str]] = {
    "SECRET_KEY": "throwaway-check-deploy-key-not-a-real-secret-0123456789",
    "ALLOWED_HOSTS": "check-deploy.example.com",
    "DATABASE_URL": "postgres://caldart:caldart@localhost:5432/caldart",
    "SITE_URL": "https://check-deploy.example.com",
    "EMAIL_URL": "smtp://localhost:1025",
    "SECURE_SSL_REDIRECT": "true",
}


def run_check_deploy(overrides: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run ``manage.py check --deploy --tag security`` under the throwaway environment.

    ``overrides`` replaces entries of :data:`THROWAWAY_ENVIRONMENT` before the command
    runs, so a test can flip one setting while keeping the rest fixed. Returns the
    completed process without raising, so a test can assert on a non-zero exit status.
    """
    environment = dict(os.environ)
    environment.update(THROWAWAY_ENVIRONMENT)
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


def test_check_deploy_passes_under_the_throwaway_environment() -> None:
    """The gate is clean when every secure flag is on, as ``check-deploy`` sets it."""
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
