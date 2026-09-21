"""The one-way dependency rule between the Django apps.

An ``ast`` pass over ``backend/apps`` and ``backend/caldart``, so the rule is checked
without importing anything and without a new dependency.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import NamedTuple

import pytest

from apps.members.models import Dart
from caldart.models import TimestampedModel

BACKEND_ROOT = Path(__file__).resolve().parents[1]

#: Every app and the layer it sits on.  A domain module may import its own app or an
#: app on a lower layer, never one on the same layer or a higher one, so ``aircraft``
#: and ``payments`` are siblings that cannot reach each other.
APP_LAYERS: dict[str, int] = {
    "accounts": 1,
    "members": 2,
    "aircraft": 3,
    "payments": 3,
    "reminders": 4,
    "cms": 5,
    "sysadmin": 5,
}

#: Directories that are composition points: they may import any app.  ``migrations``
#: is machine-written and describes state rather than behavior.
EXEMPT_DIRECTORIES = frozenset({"api", "management", "migrations"})

#: ``admin.py`` is a composition point too: it wires models into the Django admin.
EXEMPT_FILENAMES = frozenset({"admin.py"})

#: The project modules every app builds on.  They may import no app at all.
FOUNDATION_MODULES = ("models.py", "reports.py", "exceptions.py", "pagination.py")

#: The complete set of inline cross-app imports, as ``(importer, imported)`` pairs.
#: Each one breaks an app-level import cycle, and each carries a comment saying so.
SANCTIONED_INLINE_IMPORTS: frozenset[tuple[str, str]] = frozenset(
    {
        ("apps.accounts.models", "apps.members.models"),
        ("apps.accounts.models", "apps.members.services"),
        ("apps.accounts.services", "apps.cms.models"),
        ("apps.members.services", "apps.payments.models"),
        ("apps.reminders.services", "apps.cms.models"),
    }
)


class AppImport(NamedTuple):
    """One ``apps.*`` import found in a module, with where and how it appears."""

    target: str
    is_inline: bool
    lineno: int


def module_name(path: Path) -> str:
    """The dotted name of the module at ``path``, e.g. ``apps.members.services``."""
    return ".".join(path.relative_to(BACKEND_ROOT).with_suffix("").parts)


def app_of(dotted: str) -> str:
    """The app name in a dotted ``apps.<app>...`` path, or ``""`` for the bare package."""
    parts = dotted.split(".")
    return parts[1] if len(parts) > 1 else ""


def domain_modules() -> list[Path]:
    """Every app module the layering rule governs, sorted by path.

    A module under ``api/``, ``management/`` or ``migrations/``, and every ``admin.py``,
    is a composition point and is left out.
    """
    apps_root = BACKEND_ROOT / "apps"
    paths = []
    for path in sorted(apps_root.rglob("*.py")):
        parts = path.relative_to(apps_root).parts
        if len(parts) < 2:
            continue
        if path.name in EXEMPT_FILENAMES:
            continue
        if EXEMPT_DIRECTORIES.intersection(parts[1:-1]):
            continue
        paths.append(path)
    return paths


def app_imports(path: Path) -> list[AppImport]:
    """Every ``apps.*`` import in the file at ``path``, each naming the module it depends on.

    ``from apps import payments`` and ``from apps.accounts import api`` name their target
    by its last segment, so those records read ``apps.payments`` and ``apps.accounts.api``;
    a bare ``import apps`` is recorded as ``apps``.  An import is inline when it is not a
    direct child of the module body, which is how a function-local import to break a
    cycle appears.  Relative imports are not used in this codebase and are skipped.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    top_level = {id(node) for node in tree.body}
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level != 0 or node.module is None:
                continue
            targets = [_imported_module(node.module, alias.name) for alias in node.names]
        elif isinstance(node, ast.Import):
            targets = [alias.name for alias in node.names]
        else:
            continue
        for target in dict.fromkeys(targets):
            if target == "apps" or target.startswith("apps."):
                found.append(AppImport(target, id(node) not in top_level, node.lineno))
    return found


def _imported_module(module: str, name: str) -> str:
    """The module a ``from module import name`` statement depends on.

    ``apps`` and ``apps.<app>`` are packages, so ``name`` is the module being imported and
    is appended; anything deeper is a module and ``name`` is one of its symbols.
    """
    is_package = module == "apps" or (module.startswith("apps.") and module.count(".") == 1)
    return f"{module}.{name}" if is_package else module


def cross_app_imports(path: Path) -> list[AppImport]:
    """Every import in ``path`` that names an app other than the module's own."""
    own_app = app_of(module_name(path))
    return [record for record in app_imports(path) if app_of(record.target) != own_app]


def test_domain_modules_import_only_their_own_app_or_a_lower_layer() -> None:
    """No top-level import in a domain module reaches sideways, upward or to bare ``apps``."""
    upward = []
    for path in domain_modules():
        module = module_name(path)
        layer = APP_LAYERS[app_of(module)]
        for record in cross_app_imports(path):
            if record.is_inline:
                continue
            target_layer = APP_LAYERS.get(app_of(record.target))
            if target_layer is None or target_layer >= layer:
                upward.append(f"{module} imports {record.target}")
    assert sorted(upward) == []


def test_no_domain_module_imports_an_api_module() -> None:
    """The API layer is a composition point: domain code never reads from it."""
    offenders = []
    for path in domain_modules():
        module = module_name(path)
        for record in app_imports(path):
            if record.target.split(".")[2:3] == ["api"]:
                offenders.append(f"{module} imports {record.target}")
    assert sorted(offenders) == []


def test_every_inline_cross_app_import_is_sanctioned() -> None:
    """An inline import that is not on the list is an undeclared upward edge."""
    unsanctioned = []
    for path in domain_modules():
        module = module_name(path)
        for record in cross_app_imports(path):
            if record.is_inline and (module, record.target) not in SANCTIONED_INLINE_IMPORTS:
                unsanctioned.append(f"{module} imports {record.target}")
    assert sorted(unsanctioned) == []


def test_every_sanctioned_inline_import_still_exists() -> None:
    """The list carries no entry the code has stopped needing."""
    present = {
        (module_name(path), record.target)
        for path in domain_modules()
        for record in cross_app_imports(path)
        if record.is_inline
    }
    assert sorted(SANCTIONED_INLINE_IMPORTS - present) == []


def test_every_sanctioned_inline_import_carries_a_comment() -> None:
    """Each inline cross-app import sits directly under a comment block opening ``# Inline:``.

    The block says which cycle the inline placement avoids; an unrelated comment such as
    a lint pragma does not count.
    """
    uncommented = []
    for path in domain_modules():
        module = module_name(path)
        lines = path.read_text(encoding="utf-8").splitlines()
        for record in cross_app_imports(path):
            if not record.is_inline:
                continue
            if not _comment_block_above(lines, record.lineno).startswith("# Inline:"):
                uncommented.append(f"{module}:{record.lineno} imports {record.target}")
    assert sorted(uncommented) == []


def _comment_block_above(lines: list[str], lineno: int) -> str:
    """The first line of the comment block ending right above 1-based ``lineno``, or ``""``.

    The block is the unbroken run of comment lines directly above the line; a blank line
    or code between them ends it.
    """
    block = []
    for line in reversed(lines[: lineno - 1]):
        stripped = line.strip()
        if not stripped.startswith("#"):
            break
        block.append(stripped)
    return block[-1] if block else ""


def test_short_import_forms_name_the_module_they_depend_on(tmp_path: Path) -> None:
    """``from apps import x`` and ``from apps.<app> import y`` resolve to the real target."""
    probe = tmp_path / "probe.py"
    probe.write_text(
        "from apps import payments\n"
        "from apps.accounts import api\n"
        "import apps\n"
        "from apps.members.services import first, second\n",
        encoding="utf-8",
    )
    assert [record.target for record in app_imports(probe)] == [
        "apps.payments",
        "apps.accounts.api",
        "apps",
        "apps.members.services",
    ]


def test_the_bare_package_names_no_app() -> None:
    """``import apps`` has no app for the layer table, so the layer test rejects it."""
    assert app_of("apps") == ""


@pytest.mark.parametrize(
    ("lines", "expected"),
    [
        (
            ["x = 1", "# Inline: why", "# and more", "from apps.cms.models import y"],
            "# Inline: why",
        ),
        (["# Inline: why", "", "from apps.cms.models import y"], ""),
        (["# noqa: F401", "from apps.cms.models import y"], "# noqa: F401"),
    ],
    ids=["block-first-line", "blank-line-breaks-the-block", "pragma-is-not-an-inline-comment"],
)
def test_the_comment_block_is_read_from_its_first_line(lines: list[str], expected: str) -> None:
    """Only a block that opens with ``# Inline:`` satisfies the comment rule."""
    assert _comment_block_above(lines, len(lines)) == expected


def test_project_foundation_modules_import_nothing_from_apps() -> None:
    """``caldart`` models, reports, exceptions and pagination sit below every app."""
    offenders = []
    for filename in FOUNDATION_MODULES:
        path = BACKEND_ROOT / "caldart" / filename
        for record in app_imports(path):
            offenders.append(f"caldart.{path.stem} imports {record.target}")
    assert sorted(offenders) == []


def test_timestamped_model_lives_in_the_project_package() -> None:
    """The shared abstract base is a project module, not a module of a domain app."""
    assert TimestampedModel.__module__ == "caldart.models"


def test_domain_models_inherit_the_project_timestamped_model() -> None:
    """A domain model picks up ``created_at``/``updated_at`` from ``caldart.models``."""
    assert Dart.__mro__[1] is TimestampedModel
