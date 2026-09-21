"""The one-way dependency rule between the Django apps.

An ``ast`` pass over ``backend/apps`` and ``backend/caldart``, so the rule is checked
without importing anything and without a new dependency.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import NamedTuple

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
    """The app name in a dotted ``apps.<app>...`` path."""
    return dotted.split(".")[1]


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
    """Every ``apps.*`` import in the file at ``path``.

    An import is inline when it is not a direct child of the module body, which is how
    a function-local import to break a cycle appears.  Relative imports are not used in
    this codebase and are skipped.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    top_level = {id(node) for node in tree.body}
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level != 0 or node.module is None:
                continue
            targets = [node.module]
        elif isinstance(node, ast.Import):
            targets = [alias.name for alias in node.names]
        else:
            continue
        for target in targets:
            if target == "apps" or target.startswith("apps."):
                found.append(AppImport(target, id(node) not in top_level, node.lineno))
    return found


def cross_app_imports(path: Path) -> list[AppImport]:
    """Every import in ``path`` that names an app other than the module's own."""
    own_app = app_of(module_name(path))
    return [record for record in app_imports(path) if app_of(record.target) != own_app]


def test_domain_modules_import_only_their_own_app_or_a_lower_layer() -> None:
    """No top-level import in a domain module reaches sideways or upward."""
    upward = []
    for path in domain_modules():
        module = module_name(path)
        layer = APP_LAYERS[app_of(module)]
        for record in cross_app_imports(path):
            if record.is_inline:
                continue
            if APP_LAYERS[app_of(record.target)] >= layer:
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
    """Each inline cross-app import says, on the line above it, which cycle it avoids."""
    uncommented = []
    for path in domain_modules():
        module = module_name(path)
        lines = path.read_text(encoding="utf-8").splitlines()
        for record in cross_app_imports(path):
            if not record.is_inline:
                continue
            above = [line.strip() for line in lines[: record.lineno - 1]]
            preceding = next((line for line in reversed(above) if line != ""), "")
            if not preceding.startswith("#"):
                uncommented.append(f"{module}:{record.lineno} imports {record.target}")
    assert sorted(uncommented) == []


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
