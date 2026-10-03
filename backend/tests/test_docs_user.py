"""The user guide stays inside itself and keeps its voice.

The user guide under ``docs/user/`` is published on its own, to people who are not
programmers, so these tests hold every page to the rules the documentation page sets
for it: no reference leaves the guide, and no page names the developer guide; none of
the banned words and no contrast construction ("X, not Y"); no ``--``, at most two em
dashes, no line that begins with a comma, and no more than 250 lines.  The guide
describes every email a person can receive, so each email purpose label appears in it.
Because no reference leaves the guide, the Sphinx configuration needs no special case
for the guide build, and a test holds it to that too.  Every page a reader needs a role
for names those roles in a ``:roles:`` field, and the ``guide_roles`` extension turns the
fields into the ``roles.json`` the site reads.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from types import ModuleType

import pytest
from sphinx.cmd.build import build_main

from apps.accounts.roles import (
    ACCOUNT_ADMIN,
    DART_LEADER,
    MANAGEMENT,
    ROLE_SLUGS,
    SYSTEM_ADMIN,
    TREASURER,
    USER_ADMIN,
    VERIFIER,
    WEBSITE_ADMIN,
)
from apps.mail.purposes import PURPOSE_LABELS
from apps.reminders.models import ReminderSchedule
from tests.conftest import REPO_ROOT

#: The documentation tree, the full build's source root.
DOCS = REPO_ROOT / "docs"

#: The user guide's source tree, the guide build's source root.
USER_GUIDE = DOCS / "user"

#: The shared Sphinx configuration.
CONF_PY = DOCS / "conf.py"

#: Every page of the user guide, sorted.
USER_PAGES = sorted(USER_GUIDE.rglob("*.rst"))

#: The words the guide's voice leaves out, matched whole and in any case.
BANNED_WORDS = (
    "honest",
    "honestly",
    "load-bearing",
    "load bearing",
    "surface",
    "surfaces",
    "surfaced",
    "gate",
    "gates",
    "gated",
    "gating",
    "robust",
    "seamless",
    "leverage",
    "delve",
    "crucial",
)

EM_DASH = "\u2014"

#: The contrast construction: "X, not Y", "X \u2014 not Y", and "X rather than Y".
CONTRAST_PATTERNS = (r",\s+not\s", EM_DASH + r"\s*not\s", r"\brather than\b")

#: The most em dashes one page may carry.
MAX_EM_DASHES = 2

#: The longest a page may be, in lines.
MAX_PAGE_LINES = 250

#: A ``:doc:`` or ``:ref:`` role, with or without explicit link text.
CROSS_REFERENCE = re.compile(r":(doc|ref):`(?:[^`<]*<([^>`]+)>|([^`]+))`")

#: A label definition: ``.. _saved-column-sets:``.
LABEL = re.compile(r"^\.\. _([^:]+):\s*$", re.MULTILINE)

#: Inline strong and emphasis, which quote the software's own words: a button, a
#: screen, or a message exactly as the software shows it.
QUOTED_SOFTWARE_TEXT = re.compile(r"\*\*[^*]+\*\*|\*[^*\s][^*]*\*")

#: A directive whose indented body is code or a diagram, never prose.
CODE_DIRECTIVE = re.compile(r"^(\s*)\.\. (code-block|code|graphviz|highlight|literalinclude)::")


def _page_id(page: Path) -> str:
    """A page's path under ``docs/user/``, the id each parametrized case reports."""
    return page.relative_to(USER_GUIDE).as_posix()


def _prose_lines(page: Path) -> list[str]:
    """The page's lines with every code or diagram directive's body left out.

    A directive's body is every following line that is blank or indented deeper than
    the directive itself.  A line made only of ``-`` is a section adornment and is
    left out too.
    """
    lines = page.read_text(encoding="utf-8").splitlines()
    kept: list[str] = []
    body_indent: int | None = None
    for line in lines:
        if body_indent is not None:
            if line.strip() == "" or len(line) - len(line.lstrip()) > body_indent:
                continue
            body_indent = None
        directive = CODE_DIRECTIVE.match(line)
        if directive is not None:
            body_indent = len(directive.group(1))
            continue
        if re.fullmatch(r"-+", line.strip()):
            continue
        kept.append(line)
    return kept


def _prose(page: Path) -> str:
    """The page's prose, with the software's quoted words taken out."""
    return QUOTED_SOFTWARE_TEXT.sub("", "\n".join(_prose_lines(page)))


def _labels() -> set[str]:
    """Every label the user guide defines."""
    return {
        label for page in USER_PAGES for label in LABEL.findall(page.read_text(encoding="utf-8"))
    }


def _reference_cases() -> list[tuple[str, str, str]]:
    """``(page, role, target)`` for every ``:doc:`` and ``:ref:`` in the user guide."""
    cases: list[tuple[str, str, str]] = []
    for page in USER_PAGES:
        for role, explicit, bare in CROSS_REFERENCE.findall(page.read_text(encoding="utf-8")):
            cases.append((_page_id(page), role, (explicit or bare).strip()))
    return cases


def _doc_target(page: str, target: str) -> Path:
    """The source file a relative ``:doc:`` target on ``page`` names.

    The target is read from the page's own directory, as both builds read it.
    """
    return (USER_GUIDE / page).parent.joinpath(f"{target}.rst").resolve()


# -- references ---------------------------------------------------------------


def test_the_guide_has_references_to_check() -> None:
    """The reference scan finds the guide's links, so the cases below are real."""
    assert len(_reference_cases()) > 0


@pytest.mark.parametrize(("page", "role", "target"), _reference_cases())
def test_every_reference_stays_inside_the_user_guide(page: str, role: str, target: str) -> None:
    """Each ``:doc:`` names a page under ``docs/user/``; each ``:ref:`` a label there.

    A ``:doc:`` target must be relative: the full build reads an absolute one from
    ``docs/`` and the guide build from ``docs/user/``, so no absolute target resolves
    in both.
    """
    if role == "ref":
        assert target in _labels()
        return
    assert not target.startswith("/")
    resolved = _doc_target(page, target)
    assert resolved.is_relative_to(USER_GUIDE.resolve())
    assert resolved.is_file()


@pytest.mark.parametrize("page", USER_PAGES, ids=_page_id)
def test_no_page_mentions_the_developer_guide(page: Path) -> None:
    """No page links into ``/developer/`` or names the developer guide in words."""
    text = page.read_text(encoding="utf-8")
    assert "/developer/" not in text
    assert re.search(r"developer\s+guide", text, re.IGNORECASE) is None


# -- voice ----------------------------------------------------------------------


@pytest.mark.parametrize("page", USER_PAGES, ids=_page_id)
@pytest.mark.parametrize("word", BANNED_WORDS)
def test_no_page_uses_a_banned_word(page: Path, word: str) -> None:
    """None of the banned words appears in a page's prose, in any case, even quoted."""
    pattern = r"\b" + re.escape(word).replace(r"\ ", r"\s+") + r"\b"
    prose = "\n".join(_prose_lines(page))
    assert re.findall(pattern, prose, re.IGNORECASE) == []


@pytest.mark.parametrize("page", USER_PAGES, ids=_page_id)
@pytest.mark.parametrize("pattern", CONTRAST_PATTERNS)
def test_no_page_uses_the_contrast_construction(page: Path, pattern: str) -> None:
    """No page says "X, not Y" or "X rather than Y" outside the software's own words."""
    assert re.findall(pattern, _prose(page), re.IGNORECASE) == []


# -- typography and length ------------------------------------------------------


@pytest.mark.parametrize("page", USER_PAGES, ids=_page_id)
def test_no_prose_line_carries_a_double_hyphen(page: Path) -> None:
    """No prose line contains ``--``; a section underline of hyphens is not prose."""
    assert [line for line in _prose_lines(page) if "--" in line] == []


@pytest.mark.parametrize("page", USER_PAGES, ids=_page_id)
def test_no_page_carries_more_than_two_em_dashes(page: Path) -> None:
    """A page uses at most two em dashes; sentences end instead."""
    assert page.read_text(encoding="utf-8").count(EM_DASH) <= MAX_EM_DASHES


@pytest.mark.parametrize("page", USER_PAGES, ids=_page_id)
def test_no_line_begins_with_a_comma(page: Path) -> None:
    """No line of a page begins with a comma once its indentation is set aside."""
    lines = page.read_text(encoding="utf-8").splitlines()
    assert [line for line in lines if line.lstrip().startswith(",")] == []


@pytest.mark.parametrize("page", USER_PAGES, ids=_page_id)
def test_no_page_is_longer_than_250_lines(page: Path) -> None:
    """Each page is at most 250 lines long."""
    assert len(page.read_text(encoding="utf-8").splitlines()) <= MAX_PAGE_LINES


# -- emails ---------------------------------------------------------------------


def _guide_text() -> str:
    """The whole user guide as one string, every run of whitespace a single space."""
    return " ".join(" ".join(page.read_text(encoding="utf-8").split()) for page in USER_PAGES)


@pytest.mark.parametrize(
    "label", [*ReminderSchedule().purpose_labels().values(), *PURPOSE_LABELS.values()]
)
def test_every_email_purpose_is_described_in_the_guide(label: str) -> None:
    """Each email purpose label, as the email log shows it, appears in the user guide.

    The renewal reminders are labeled from the reminder schedule, so the guide names
    them as the default schedule words them.
    """
    assert label in _guide_text()


# -- the guide build ------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    ["_unpublished_developer_reference", "_developer_titles", "missing-reference"],
)
def test_the_sphinx_configuration_has_no_developer_guide_special_case(name: str) -> None:
    """``docs/conf.py`` carries no handler that renders links into the developer guide."""
    assert name not in CONF_PY.read_text(encoding="utf-8")


# -- roles ----------------------------------------------------------------------

#: The local Sphinx extension that reads each page's ``:roles:`` field.
GUIDE_ROLES_EXTENSION = DOCS / "_ext" / "guide_roles.py"

#: A ``:roles:`` field at the head of a page, before its title.
ROLES_FIELD = re.compile(r"\A:roles:[ \t]*(.*)$", re.MULTILINE)

#: The directories whose pages each need a role.
RESTRICTED_DIRECTORIES = ("admin", "bulk-email", "finance", "website")

#: The roles that reach each leader and administrator screen, as the portal's menu grants
#: them.
ADMIN_PAGE_ROLES: dict[str, frozenset[str]] = {
    "admin/member-check": frozenset({DART_LEADER, ACCOUNT_ADMIN, USER_ADMIN, VERIFIER}),
    "admin/aircraft-check": frozenset({DART_LEADER, ACCOUNT_ADMIN, USER_ADMIN, VERIFIER}),
    "admin/members": frozenset({ACCOUNT_ADMIN, DART_LEADER}),
    "admin/new-member": frozenset({ACCOUNT_ADMIN, DART_LEADER}),
    "admin/member-record": frozenset({ACCOUNT_ADMIN, DART_LEADER}),
    "admin/aircraft-register": frozenset({ACCOUNT_ADMIN}),
    "admin/aircraft-record": frozenset({ACCOUNT_ADMIN}),
    "admin/darts": frozenset({ACCOUNT_ADMIN}),
    "admin/reminders": frozenset({ACCOUNT_ADMIN}),
    "admin/notifications": frozenset({ACCOUNT_ADMIN}),
    "admin/subscriptions": frozenset({ACCOUNT_ADMIN, TREASURER}),
    "admin/users": frozenset({USER_ADMIN}),
    "admin/user-record": frozenset({USER_ADMIN}),
    "admin/health-database": frozenset({SYSTEM_ADMIN}),
    "admin/sent-emails": frozenset({SYSTEM_ADMIN}),
    "admin/scheduled": frozenset({SYSTEM_ADMIN}),
    "bulk-email/compose": frozenset({MANAGEMENT, DART_LEADER}),
    "bulk-email/drafts": frozenset({MANAGEMENT, DART_LEADER}),
    "bulk-email/sent": frozenset({MANAGEMENT, DART_LEADER}),
    "bulk-email/dart-leaders": frozenset({DART_LEADER}),
    "bulk-email/templates": frozenset({MANAGEMENT}),
    "bulk-email/groups": frozenset({MANAGEMENT}),
    "bulk-email/mail-delivery": frozenset({MANAGEMENT}),
    "bulk-email/email-types": frozenset({SYSTEM_ADMIN}),
}

#: The roles that reach every page of a group other than ``admin/``.
GROUP_ROLES: dict[str, frozenset[str]] = {
    "finance": frozenset({TREASURER, ACCOUNT_ADMIN}),
    "website": frozenset({WEBSITE_ADMIN}),
}


def _roles_field(page: Path) -> list[str] | None:
    """The slugs a page's ``:roles:`` field names, or ``None`` when it has no field."""
    match = ROLES_FIELD.search(page.read_text(encoding="utf-8"))
    if match is None:
        return None
    return [slug.strip() for slug in match.group(1).split(",")]


def _slug(page: Path) -> str:
    """A page's slug: its path under ``docs/user/`` without ``.rst``."""
    return page.relative_to(USER_GUIDE).with_suffix("").as_posix()


def _is_index(page: Path) -> bool:
    """True for a group's ``index.rst`` and the guide's own."""
    return page.name == "index.rst"


#: Every page of the restricted groups, index pages left out.
RESTRICTED_PAGES = [
    page
    for page in USER_PAGES
    if page.relative_to(USER_GUIDE).parts[0] in RESTRICTED_DIRECTORIES and not _is_index(page)
]

#: Every page open to any signed-in reader: the member screens, the top-level pages, and
#: every index page.
OPEN_PAGES = [page for page in USER_PAGES if page not in RESTRICTED_PAGES]


def _expected_roles(page: Path) -> frozenset[str]:
    """The roles the portal's menu gives the screen ``page`` describes."""
    slug = _slug(page)
    group = slug.split("/")[0]
    if group in GROUP_ROLES:
        return GROUP_ROLES[group]
    return ADMIN_PAGE_ROLES[slug]


@pytest.fixture(scope="module")
def guide_roles() -> ModuleType:
    """The ``guide_roles`` Sphinx extension, imported from ``docs/_ext``."""
    spec = importlib.util.spec_from_file_location("guide_roles", GUIDE_ROLES_EXTENSION)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_guide_has_restricted_pages_to_check() -> None:
    """The scan finds the administrator, bulk email, treasurer, and website pages."""
    assert len(RESTRICTED_PAGES) > 0


@pytest.mark.parametrize("page", RESTRICTED_PAGES, ids=_page_id)
def test_every_administrator_page_names_the_roles_that_reach_it(page: Path) -> None:
    """Each restricted page of the guide names the roles that reach it.

    The groups are ``admin/``, ``bulk-email/``, ``finance/``, and ``website/``.
    The field is the page's first line, so Sphinx reads it as the page's metadata, and
    it names exactly the roles the portal's menu gives the screen.
    """
    roles = _roles_field(page)
    assert roles is not None
    assert frozenset(roles) == _expected_roles(page)


@pytest.mark.parametrize("page", OPEN_PAGES, ids=_page_id)
def test_a_page_for_every_reader_carries_no_roles(page: Path) -> None:
    """A member page, a top-level page, and an index page carry no ``:roles:`` field.

    An index page's roles are computed from the pages under it.
    """
    assert _roles_field(page) is None


@pytest.mark.parametrize("page", RESTRICTED_PAGES, ids=_page_id)
def test_every_slug_in_a_roles_field_is_a_role(page: Path) -> None:
    """Every slug a ``:roles:`` field names is one of the site's roles."""
    assert set(_roles_field(page) or []) <= set(ROLE_SLUGS)


def test_the_extension_knows_the_sites_roles(guide_roles: ModuleType) -> None:
    """The extension's own list of role slugs is the site's, in the same order."""
    assert guide_roles.ROLE_SLUGS == ROLE_SLUGS


def _write_project(root: Path, pages: dict[str, str]) -> tuple[Path, Path]:
    """A tiny Sphinx project under ``root`` using the extension; its source and output."""
    source = root / "source"
    for name, text in pages.items():
        path = source / f"{name}.rst"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    (source / "conf.py").write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(GUIDE_ROLES_EXTENSION.parent)!r})\n"
        "extensions = ['guide_roles']\n"
        "html_theme = 'basic'\n",
        encoding="utf-8",
    )
    return source, root / "out"


def _toctree(*entries: str) -> str:
    """A toctree directive listing ``entries``."""
    return ".. toctree::\n\n" + "".join(f"   {entry}\n" for entry in entries)


def _page(title: str, roles: str | None = None, body: str = "") -> str:
    """A page titled ``title``, headed by a ``:roles:`` field when ``roles`` is given."""
    field = "" if roles is None else f":roles: {roles}\n\n"
    return f"{field}{title}\n{'=' * len(title)}\n\n{body}"


#: A guide whose front page lists an open page and a group of two restricted pages.
SAMPLE_GUIDE = {
    "index": _page("Guide", body=_toctree("open", "admin/index")),
    "open": _page("Open"),
    "admin/index": _page("Admin", body=_toctree("members", "money")),
    "admin/members": _page("Members", roles="dart_leader, account_admin"),
    "admin/money": _page("Money", roles="treasurer"),
}


def test_the_extension_writes_each_restricted_page_and_its_roles(tmp_path: Path) -> None:
    """``roles.json`` names each restricted page, and a group's index gets the union.

    Slugs come back in privilege order; the open page and the front page, which lists
    it, are left out.
    """
    source, out = _write_project(tmp_path, SAMPLE_GUIDE)
    assert build_main(["-q", "-W", "-b", "dirhtml", str(source), str(out)]) == 0
    assert json.loads((out / "roles.json").read_text(encoding="utf-8")) == {
        "admin/index": [DART_LEADER, TREASURER, ACCOUNT_ADMIN],
        "admin/members": [DART_LEADER, ACCOUNT_ADMIN],
        "admin/money": [TREASURER],
    }


def test_the_extension_moves_roles_json_into_place_whole(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``roles.json`` is written beside itself and renamed over, never written in place.

    A request reading it mid-build finds the old file or the new one, never half.
    """
    renamed: list[str] = []
    original_replace = Path.replace

    def record_replace(self: Path, target: str | Path) -> Path:
        renamed.append(Path(target).name)
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", record_replace)
    source, out = _write_project(tmp_path, SAMPLE_GUIDE)
    assert build_main(["-q", "-W", "-b", "dirhtml", str(source), str(out)]) == 0
    assert "roles.json" in renamed


def test_the_extension_leaves_no_temporary_file_behind(tmp_path: Path) -> None:
    """Only ``roles.json`` is left in the output directory, no half-written copy."""
    source, out = _write_project(tmp_path, SAMPLE_GUIDE)
    assert build_main(["-q", "-W", "-b", "dirhtml", str(source), str(out)]) == 0
    assert sorted(path.name for path in out.glob("roles*")) == ["roles.json"]


def test_an_index_with_an_open_page_under_it_is_open(tmp_path: Path) -> None:
    """A group index that lists any page without roles is every reader's."""
    pages = {
        **SAMPLE_GUIDE,
        "admin/index": _page("Admin", body=_toctree("members", "money", "help")),
        "admin/help": _page("Help"),
    }
    source, out = _write_project(tmp_path, pages)
    assert build_main(["-q", "-W", "-b", "dirhtml", str(source), str(out)]) == 0
    assert "admin/index" not in json.loads((out / "roles.json").read_text(encoding="utf-8"))


def test_an_unknown_role_fails_the_build(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A ``:roles:`` slug that is not a role is a warning, so ``-W`` fails the build."""
    pages = {**SAMPLE_GUIDE, "admin/money": _page("Money", roles="treasurer, bookkeeper")}
    source, out = _write_project(tmp_path, pages)
    assert build_main(["-q", "-W", "-b", "dirhtml", str(source), str(out)]) != 0
    assert "unknown role 'bookkeeper'" in capsys.readouterr().err
