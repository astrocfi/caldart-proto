"""The user guide stays inside itself and keeps its voice.

The user guide under ``docs/user/`` is published on its own, to people who are not
programmers, so these tests hold every page to the rules the documentation page sets
for it: no reference leaves the guide, and no page names the developer guide; none of
the banned words and no contrast construction ("X, not Y"); no ``--``, at most two em
dashes, no line that begins with a comma, and no more than 250 lines.  The guide
describes every email a person can receive, so each email purpose label appears in it.
Because no reference leaves the guide, the Sphinx configuration needs no special case
for the guide build, and a test holds it to that too.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from apps.mail.purposes import PURPOSE_LABELS
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


@pytest.mark.parametrize("label", PURPOSE_LABELS.values())
def test_every_email_purpose_is_described_in_the_guide(label: str) -> None:
    """Each email purpose label, as the email log shows it, appears in the user guide."""
    assert label in _guide_text()


# -- the guide build ------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    ["_unpublished_developer_reference", "_developer_titles", "missing-reference"],
)
def test_the_sphinx_configuration_has_no_developer_guide_special_case(name: str) -> None:
    """``docs/conf.py`` carries no handler that renders links into the developer guide."""
    assert name not in CONF_PY.read_text(encoding="utf-8")
