"""The developer guide keeps pace with the code it documents.

Each test walks one thing the code declares and looks for it on the page that
documents it: every API route on an ``docs/developer/api-*.rst`` page, every model
and field in ``data-model.rst``, every environment variable the settings read in
``configuration.rst``, every management command and ``make help`` target in
``setup.rst``, and every systemd unit in ``deployment.rst``.  A test fails naming
what the page is missing, so adding a route, field, variable, command, target, or
unit without documenting it fails the suite.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from django.apps import apps
from django.db.models import Model
from django.urls import URLPattern, URLResolver, get_resolver
from django.views import View

from tests.conftest import DEPLOY_DIR, REPO_ROOT

#: A URL pattern's view: a DRF view function carrying ``cls`` or ``actions``.
type ViewCallback = Callable[..., object]

#: The developer guide's source directory.
DEVELOPER_DOCS = REPO_ROOT / "docs" / "developer"

#: The backend's settings modules, whose environment reads ``configuration.rst`` lists.
SETTINGS_DIR = REPO_ROOT / "backend" / "caldart" / "settings"

#: The project's own Django apps, whose models and commands the guide documents.
APPS_DIR = REPO_ROOT / "backend" / "apps"

#: The HTTP methods an API route documents; ``OPTIONS`` and ``HEAD`` come with every view.
DOCUMENTED_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")

#: A route segment the resolver captures: ``<int:pk>`` or a regex's ``(?P<fmt>...)``.
ROUTE_PARAMETER = re.compile(r"<[^>]+>|\(\?P<\w+>[^)]*\)")

#: A placeholder as the guide writes one: ``{id}``, ``{user_id}``, or ``{csv,pdf}``.
DOC_PLACEHOLDER = re.compile(r"\{[^}]*\}")

#: ``METHOD /path`` in the guide, the path ending at whitespace, a query, or punctuation.
DOC_ENDPOINT = re.compile(rf"\b({'|'.join(DOCUMENTED_METHODS)})\s+(/[^\s`?,;)*]*)")

#: The prefix every API route is mounted under, which the guide may write or leave out.
API_PREFIX = "/api/v1"

#: A settings module reading one environment variable: ``env("X"``, ``env.int("X"``,
#: ``env.db(\n "X"``, and the throttle helper ``_throttle_rate("X"``.
ENV_READ = re.compile(r'\b(?:env(?:\.\w+)?|_throttle_rate)\(\s*"([A-Z][A-Z0-9_]*)"')

#: A Makefile target ``make help`` lists: the same pattern its recipe greps for.
MAKE_HELP_TARGET = re.compile(r"^([a-zA-Z0-9_-]+):.*?## ", re.MULTILINE)

#: The characters reStructuredText accepts for a section title's underline.
ADORNMENTS = "=-~^\"'`#*+_:.<>"

#: A double-backquoted inline literal.
LITERAL = re.compile(r"``([^`]+)``")


# -- helpers ------------------------------------------------------------------


def _walk_routes(
    patterns: list[URLPattern | URLResolver], *, prefix: str = ""
) -> Iterator[tuple[str, ViewCallback]]:
    """Yield ``(route, callback)`` for every URL pattern under ``patterns``, recursing."""
    for pattern in patterns:
        route = prefix + str(pattern.pattern)
        if isinstance(pattern, URLResolver):
            yield from _walk_routes(pattern.url_patterns, prefix=route)
        else:
            yield route, pattern.callback


def _view_methods(callback: ViewCallback) -> list[str]:
    """The documented HTTP methods a DRF view answers, upper case.

    A viewset's callback carries its method-to-action map; any other DRF view's
    callback carries its class, whose allowed methods are the handlers it defines.
    """
    actions: dict[str, str] | None = getattr(callback, "actions", None)
    if actions is not None:
        methods = [method.upper() for method in actions]
    else:
        view_class: type[View] = getattr(callback, "cls")  # noqa: B009 - DRF sets it; the type does not say so
        methods = [m.upper() for m in view_class.http_method_names if hasattr(view_class, m)]
    return [method for method in methods if method in DOCUMENTED_METHODS]


def _normalize_route(route: str) -> str:
    """A resolver route as ``/path`` with every captured segment written ``{}``."""
    bare = ROUTE_PARAMETER.sub("{}", route).removeprefix("^").removesuffix("$")
    return "/" + bare.replace("\\.", ".")


def _api_endpoints() -> list[str]:
    """Every ``METHOD /path`` the API answers, walked from ``caldart.api_urls``."""
    resolver = get_resolver("caldart.api_urls")
    return sorted(
        f"{method} {_normalize_route(route)}"
        for route, callback in _walk_routes(resolver.url_patterns)
        for method in _view_methods(callback)
    )


def _documented_endpoints() -> set[str]:
    """Every ``METHOD /path`` the API reference pages name, each placeholder as ``{}``."""
    found: set[str] = set()
    for page in sorted(DEVELOPER_DOCS.glob("api-*.rst")):
        text = DOC_PLACEHOLDER.sub("{}", page.read_text(encoding="utf-8"))
        for method, path in DOC_ENDPOINT.findall(text):
            found.add(f"{method} {path.removeprefix(API_PREFIX)}")
    return found


def _is_underline(candidate: str, title: str) -> bool:
    """True when ``candidate`` is a section underline at least as long as ``title``."""
    return len(candidate) >= len(title) and len(set(candidate)) == 1 and candidate[0] in ADORNMENTS


def _sections(text: str) -> list[tuple[str, str]]:
    """Every section of an rst page as ``(title, body)``.

    The body runs to the next title at the same or a higher level, so it includes the
    section's subsections.
    """
    lines = text.splitlines()
    titles: list[tuple[int, str, str]] = [
        (index, line.strip(), lines[index + 1][0])
        for index, line in enumerate(lines[:-1])
        if line.strip()
        and not line.startswith(" ")
        and _is_underline(lines[index + 1], line.strip())
    ]
    levels: list[str] = []
    for _, _, adornment in titles:
        if adornment not in levels:
            levels.append(adornment)
    sections: list[tuple[str, str]] = []
    for position, (start, title, adornment) in enumerate(titles):
        level = levels.index(adornment)
        end = next(
            (
                later_start
                for later_start, _, later_adornment in titles[position + 1 :]
                if levels.index(later_adornment) <= level
            ),
            len(lines),
        )
        sections.append((title, "\n".join(lines[start:end])))
    return sections


def _project_models() -> list[type[Model]]:
    """Every concrete, non-proxy model the project's own apps define."""
    return sorted(
        (
            model
            for model in apps.get_models()
            if model.__module__.startswith("apps.")
            and not model._meta.proxy
            and not model._meta.abstract
        ),
        key=lambda model: model._meta.label,
    )


def _model_section(model: type[Model], sections: list[tuple[str, str]]) -> str | None:
    """The body of the ``data-model.rst`` section whose title names ``model``."""
    for title, body in sections:
        if model.__name__ in LITERAL.findall(title):
            return body
    return None


def _model_field_cases() -> list[tuple[str, str]]:
    """``(model label, field name)`` for every field each project model declares itself.

    A field inherited through multi-table inheritance (a Wagtail page's ``title``)
    belongs to its parent's section; one inherited from an abstract base (a user's
    ``password``) is the model's own column and belongs to its section.
    """
    return [
        (model._meta.label, field.name)
        for model in _project_models()
        for field in [*model._meta.local_concrete_fields, *model._meta.local_many_to_many]
    ]


def _settings_variables() -> list[str]:
    """Every environment variable the settings modules read, sorted."""
    names: set[str] = set()
    for module in SETTINGS_DIR.glob("*.py"):
        names.update(ENV_READ.findall(module.read_text(encoding="utf-8")))
    return sorted(names)


def _defines_command(module: Path) -> bool:
    """True when ``module`` defines a top-level class named ``Command``."""
    tree = ast.parse(module.read_text(encoding="utf-8"))
    return any(isinstance(node, ast.ClassDef) and node.name == "Command" for node in tree.body)


def _management_commands() -> list[str]:
    """The name of every management command module the project's apps define."""
    return sorted(
        module.stem
        for module in APPS_DIR.glob("*/management/commands/*.py")
        if _defines_command(module)
    )


def _make_help_targets() -> list[str]:
    """Every target ``make help`` lists: each one whose rule carries a ``##`` summary."""
    return MAKE_HELP_TARGET.findall((REPO_ROOT / "Makefile").read_text(encoding="utf-8"))


def _table_names(page: str, section_title: str) -> set[str]:
    """The first word of the first literal in each row of a section's list tables.

    ``* - ``db_backup [--name NAME]``'' yields ``db_backup``.
    """
    text = (DEVELOPER_DOCS / page).read_text(encoding="utf-8")
    body = next(body for title, body in _sections(text) if title == section_title)
    return {
        match.group(1).split()[0]
        for match in re.finditer(r"^\s*\* - ``([^`]+)``", body, re.MULTILINE)
    }


def _systemd_units() -> list[str]:
    """The file name of every unit under ``deploy/systemd/``."""
    return sorted(unit.name for unit in (DEPLOY_DIR / "systemd").iterdir() if unit.is_file())


# -- the API reference --------------------------------------------------------


def test_the_api_walk_finds_the_routes() -> None:
    """The resolver walk sees the routes, so the parametrized cases below are real."""
    assert "GET /auth/me" in _api_endpoints()


@pytest.mark.parametrize("endpoint", _api_endpoints())
def test_every_api_route_is_documented_on_an_api_page(endpoint: str) -> None:
    """Each ``METHOD /path`` the API answers appears on some ``api-*.rst`` page."""
    assert endpoint in _documented_endpoints()


# -- the data model -----------------------------------------------------------

DATA_MODEL_SECTIONS = _sections((DEVELOPER_DOCS / "data-model.rst").read_text(encoding="utf-8"))


@pytest.mark.parametrize("model", _project_models(), ids=lambda model: model._meta.label)
def test_every_model_has_a_section_in_the_data_model(model: type[Model]) -> None:
    """Each concrete project model has a ``data-model.rst`` section named for it."""
    assert _model_section(model, DATA_MODEL_SECTIONS) is not None


@pytest.mark.parametrize(("label", "field"), _model_field_cases())
def test_every_model_field_appears_in_its_section(label: str, field: str) -> None:
    """Each field a model declares appears as a literal within that model's section."""
    section = _model_section(apps.get_model(label), DATA_MODEL_SECTIONS) or ""
    assert field in LITERAL.findall(section)


# -- configuration ------------------------------------------------------------


def test_the_settings_scan_finds_the_variables() -> None:
    """The settings scan sees multi-line reads, so the cases below are complete."""
    assert "DATABASE_URL" in _settings_variables()


@pytest.mark.parametrize("variable", _settings_variables())
def test_every_environment_variable_is_documented(variable: str) -> None:
    """Each environment variable the settings read appears in ``configuration.rst``."""
    page = (DEVELOPER_DOCS / "configuration.rst").read_text(encoding="utf-8")
    assert variable in LITERAL.findall(page)


# -- setup: commands and make targets -----------------------------------------


@pytest.mark.parametrize("command", _management_commands())
def test_every_management_command_is_in_the_command_table(command: str) -> None:
    """Each management command the apps define has a row in ``setup.rst``'s table."""
    assert command in _table_names("setup.rst", "Management commands")


@pytest.mark.parametrize("target", _make_help_targets())
def test_every_make_target_is_in_the_target_table(target: str) -> None:
    """Each target ``make help`` lists has a row in ``setup.rst``'s target table."""
    assert target in _table_names("setup.rst", "Make targets")


# -- deployment ---------------------------------------------------------------


@pytest.mark.parametrize("unit", _systemd_units())
def test_every_systemd_unit_is_named_in_the_deployment_guide(unit: str) -> None:
    """Each unit under ``deploy/systemd/`` is named in ``deployment.rst``.

    The name may sit in prose or in the commands that install the unit.
    """
    page = (DEVELOPER_DOCS / "deployment.rst").read_text(encoding="utf-8")
    assert unit in page
