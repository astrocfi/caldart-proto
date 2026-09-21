"""``make help`` lists every target declared in the Makefile's ``.PHONY`` line.

A target with no trailing ``## `` comment, or whose name the help regex fails to
match (digits included, since ``e2e`` is one), silently drops out of the listing
without breaking the build.  These tests make that a failure.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MAKEFILE = REPO_ROOT / "Makefile"

#: Strips the ANSI bold/reset codes `make help` wraps each target name in.
ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")

#: The resolved ``make`` executable, or ``None`` on a machine without one.
MAKE = shutil.which("make")


def _phony_targets() -> list[str]:
    """The target names declared on the Makefile's (possibly multi-line) ``.PHONY:`` rule.

    Returns the target names in declaration order.
    """
    text = MAKEFILE.read_text()
    match = re.search(r"^\.PHONY:(.*?)(?<!\\)\n(?!\t)", text, re.MULTILINE | re.DOTALL)
    assert match is not None, "Makefile has no .PHONY line"
    body = match.group(1).replace("\\\n", " ")
    return body.split()


@pytest.mark.skipif(MAKE is None, reason="make is not installed")
def test_make_help_lists_every_phony_target() -> None:
    """Each ``.PHONY`` target appears once in ``make help``, including ``e2e``."""
    assert MAKE is not None
    result = subprocess.run(
        [MAKE, "--no-print-directory", "help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    listed_names = [
        ANSI_ESCAPE.sub("", line).split()[0] for line in result.stdout.splitlines() if line.strip()
    ]
    assert sorted(listed_names) == sorted(_phony_targets())
