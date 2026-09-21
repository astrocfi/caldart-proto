"""The annotation, docstring and mypy gates cover the whole backend, with no ratchet left.

The adoption ratchet in ``pyproject.toml`` (``ANN``/``D`` per-file ignores and
``ignore_errors`` mypy overrides, one per unit) was deleted unit by unit as the code
was typed and documented.  A merge conflict resolved by hand can bring an entry back
without any gate noticing, since the entry only switches checks off; these tests make
that a failure.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"

#: The rule sets the ratchet used to suspend; neither may be ignored anywhere.
RATCHETED_RULES = frozenset({"ANN", "D"})


def _config() -> dict[str, object]:
    """The parsed ``pyproject.toml``."""
    with PYPROJECT.open("rb") as handle:
        return tomllib.load(handle)


def test_no_file_is_exempt_from_the_annotation_or_docstring_rules() -> None:
    """``[tool.ruff.lint.per-file-ignores]`` carries no ``ANN`` or ``D`` entry."""
    ruff_lint = _config()["tool"]["ruff"]["lint"]  # type: ignore[index]
    per_file = ruff_lint.get("per-file-ignores", {})
    exempt = {
        pattern: sorted(codes)
        for pattern, codes in per_file.items()
        if any(code.rstrip("0123456789") in RATCHETED_RULES for code in codes)
    }
    assert exempt == {}


def test_no_mypy_override_ignores_errors() -> None:
    """No ``[[tool.mypy.overrides]]`` entry carries ``ignore_errors = true``."""
    overrides = _config()["tool"]["mypy"].get("overrides", [])  # type: ignore[index]
    ignored = [entry["module"] for entry in overrides if entry.get("ignore_errors") is True]
    assert ignored == []
