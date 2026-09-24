"""``scripts/read-docs.sh`` builds through the Makefile and is wired into it.

The script exists to spare a reader the ``sphinx-build`` invocation, so the one
thing it must not do is carry a second copy of that invocation: it builds by
calling ``make docs``, the single source of truth for how the documentation is
built.  These tests hold it to that, and to being runnable.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "read-docs.sh"
MAKEFILE = REPO_ROOT / "Makefile"

#: The resolved ``bash``, or ``None`` on a machine without one.
BASH = shutil.which("bash")


def test_the_script_is_executable() -> None:
    """The committed file carries its executable bit, so ``./scripts/...`` runs it."""
    assert os.access(SCRIPT, os.X_OK)


def test_the_script_builds_through_the_makefile() -> None:
    """It shells out to ``make docs`` rather than running ``sphinx-build`` itself."""
    assert re.search(r'"\$MAKE" docs', SCRIPT.read_text()) is not None


def test_the_script_does_not_invoke_sphinx_directly() -> None:
    """No second copy of the build command can drift from the Makefile's."""
    assert "sphinx-build" not in SCRIPT.read_text()


def test_the_makefile_offers_it_as_a_target() -> None:
    """``make read-docs`` runs the script, so ``make help`` advertises it."""
    assert "read-docs: ##" in MAKEFILE.read_text()


@pytest.mark.skipif(BASH is None, reason="bash is not installed")
def test_an_unknown_switch_is_refused() -> None:
    """An argument the script does not know exits 2 with a usage line."""
    assert BASH is not None
    result = subprocess.run(  # noqa: S603 - fixed argv, BASH is a resolved path
        [BASH, str(SCRIPT), "--nonsense"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "Usage:" in result.stderr
