"""``scripts/check_wording.py``, the wording check ``make lint-wording`` runs.

The check flags a verb whose object is a negative (``no``, ``nothing``, ``nobody``,
``none``, or ``no one``), the wording the project's prose rule forbids, and holds the
repository to a committed per-file baseline of hits.  Each flagged example below ends
its line with the ignore marker, so the check passes over this file itself.
"""

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_wording.py"
MAKEFILE = REPO_ROOT / "Makefile"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"

#: The resolved ``git``, or ``None`` on a machine without one.
GIT = shutil.which("git")

#: The baseline's path relative to the root the check runs from.
BASELINE = "scripts/wording-baseline.txt"

#: The same-line marker, split so that this line itself is still checked.
MARKER = "wording" + ":ignore"

#: The page every ``tree`` starts with: two hits, which its baseline allows.
PAGE = "It has no token.\nIt sends nothing.\n"  # wording:ignore

#: The same page with a third hit.
PAGE_WITH_THREE = PAGE + "It took none.\n"  # wording:ignore

#: The same page with its first hit rewritten.
PAGE_WITH_ONE = "It doesn't have a token.\nIt sends nothing.\n"  # wording:ignore


def _load_checker() -> ModuleType:
    """Import ``check_wording.py`` from its path, since ``scripts`` isn't a package.

    The module is registered in ``sys.modules`` first, as a normal import would, so its
    dataclasses can resolve their own module.
    """
    spec = importlib.util.spec_from_file_location("caldart_check_wording", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


checker = _load_checker()


def _hit_count(text: str) -> int:
    """How many hits the check finds in ``text``, read as a file named ``page.rst``."""
    return len(checker.find_hits(text, "page.rst"))


# -- what is flagged -------------------------------------------------------------

FLAGGED = {
    "has-no": "A donor has no portal account.",  # wording:ignore
    "holds-no": "The dashboard holds no charge.",  # wording:ignore
    "took-nothing": "It took nothing.",  # wording:ignore
    "charges-nobody": "The run charges nobody.",  # wording:ignore
    "sends-nothing": "The form sends nothing.",  # wording:ignore
    "offers-none": "The plan offers none.",  # wording:ignore
    "changes-nothing": "The request changes nothing.",  # wording:ignore
    "does-nothing": "The link does nothing.",  # wording:ignore
    "did-nothing": "Clicking it did nothing.",  # wording:ignore
    "do-nothing": "Then do nothing.",  # wording:ignore
    "found-no-one": "The scan found no one to charge.",  # wording:ignore
    "upper-case": "A Member HAS NO term.",  # wording:ignore
    "participle-after-has": "The renewal has sent nothing.",  # wording:ignore
    "after-a-hyphen": "The scan re-sends nothing.",  # wording:ignore
}


@pytest.mark.parametrize("text", list(FLAGGED.values()), ids=list(FLAGGED))
def test_a_verb_with_a_negative_object_is_flagged(text: str) -> None:
    """Each phrase puts the negation on a verb's object, so it is one hit."""
    assert _hit_count(text) == 1


ALLOWED = {
    "there-is-no": "There is no payment.",
    "no-payment-found": "No payment found.",
    "nobody-as-subject": "Nobody changes their own roles.",
    "nothing-as-subject": "Nothing is due.",
    "are-no": "The reminders are no help.",
    "was-no": "It was no surprise.",
    "be-no": "It will be no trouble.",
    "with-no": "A member with no term is a friend.",
    "for-no-one": "It is for no one in particular.",
    "of-no": "A gift of no value.",
    "no-longer": "The link may no longer work.",
    "no-matter": "It runs no matter what.",
    "noun-before-nobody": "A field nobody has filled in is blank.",
    "noun-before-no": "An address no account holds is counted.",
    "determiner-before-a-verb-form": "A change nobody is signed in for.",
    "the-before-a-plural-noun": "The records nobody edited stay.",
    "python-none": "It returns None when the row is missing.",
    "than-nothing": "More than nothing but less than the minimum.",
    "or-no": "A yes or no answer.",
}


@pytest.mark.parametrize("text", list(ALLOWED.values()), ids=list(ALLOWED))
def test_wording_the_rule_allows_is_not_flagged(text: str) -> None:
    """A negative subject, a linking verb, a preposition, or a noun isn't a hit."""
    assert _hit_count(text) == 0


IDENTIFIERS = {
    "snake-case": "def has_no_term(member):",
    "camel-case": "const hasNoTerm = true;",
    "snake-case-nothing": "holds_nothing = False",
    "is-none": "if value is None:",
    "flag": "send --no-input",
    "hyphen": "Cache-Control: has no-store",
    "quoted": "takes 'none' as its value",
}


@pytest.mark.parametrize("text", list(IDENTIFIERS.values()), ids=list(IDENTIFIERS))
def test_an_identifier_or_a_quoted_value_never_matches(text: str) -> None:
    """Only whitespace-separated words count, so code identifiers stay out."""
    assert _hit_count(text) == 0


def test_a_phrase_wrapped_across_two_lines_is_flagged_on_the_verb_line() -> None:
    """A docstring that breaks between the verb and the negative is still one hit."""
    hits = checker.find_hits("First line.\nThe donor has\n    no account.\n", "page.rst")
    assert [hit.line for hit in hits] == [2]


def test_a_phrase_wrapped_across_two_comment_lines_is_flagged() -> None:
    """The continuation's comment leader counts as whitespace between the two words."""
    assert _hit_count("# The check holds\n# nothing back.\n") == 1


def test_the_hit_carries_its_path() -> None:
    """A hit names the file it was found in."""
    hit = checker.find_hits("The run charges nobody.\n", "docs/x.rst")[0]  # wording:ignore
    assert hit.path == "docs/x.rst"


def test_the_hit_carries_the_text_of_its_line_stripped() -> None:
    """A hit carries its line's text without the surrounding whitespace."""
    hit = checker.find_hits("  The run charges nobody.\n", "docs/x.rst")[0]  # wording:ignore
    assert hit.text == "The run charges nobody."  # wording:ignore


def test_the_flagged_and_allowed_words_are_disjoint() -> None:
    """No word is both flagged and deliberately allowed."""
    assert checker.FLAGGED_FORMS.isdisjoint(checker.ALLOWED_FORMS)


def test_no_allowed_word_is_listed_twice() -> None:
    """Each allowed word is written down once."""
    words = [word for group in checker.ALLOWED_WORDS for word in group.split()]
    assert len(words) == len(set(words))


def test_every_verb_family_has_five_forms() -> None:
    """Base, third person, past, past participle, and present participle, in order."""
    assert {len(family.split()) for family in checker.FLAGGED_VERBS} == {5}


def test_no_verb_form_belongs_to_two_families() -> None:
    """Each flagged form appears in one family, so its suggestion is unambiguous."""
    forms = [form for family in checker.FLAGGED_VERBS for form in set(family.split())]
    assert len(forms) == len(set(forms))


# -- the ignore markers ----------------------------------------------------------


def test_the_ignore_marker_on_the_same_line_silences_it() -> None:
    """The marker anywhere on the line keeps the phrase verbatim."""
    assert _hit_count(f"The API has no token.  # {MARKER}\n") == 0  # wording:ignore


def test_the_ignore_marker_on_either_line_of_a_wrapped_phrase_silences_it() -> None:
    """The continuation line can carry the marker too."""
    assert _hit_count(f"The API has\nno token.  # {MARKER}\n") == 0  # wording:ignore


def test_the_next_line_marker_silences_the_following_line() -> None:
    """The next-line marker keeps the next line, where a trailing comment cannot go."""
    text = f"<!-- {MARKER}-next-line -->\nThe API has no token.\n"  # wording:ignore
    assert _hit_count(text) == 0


def test_the_next_line_marker_leaves_its_own_line_flagged() -> None:
    """The next-line marker doesn't silence its own line."""
    text = f"It has no token. <!-- {MARKER}-next-line -->\n\n"  # wording:ignore
    assert _hit_count(text) == 1


# -- suggestions -----------------------------------------------------------------

SUGGESTIONS = {
    "a": ("It has no portal.", "has no portal -> doesn't have a portal"),  # wording:ignore
    "an": ("It has no address.", "has no address -> doesn't have an address"),  # wording:ignore
    "any-plural": ("It has no terms.", "has no terms -> doesn't have any terms"),  # wording:ignore
    "anything": ("It sends nothing.", "sends nothing -> doesn't send anything"),  # wording:ignore
    "past": ("It took nothing.", "took nothing -> didn't take anything"),  # wording:ignore
    "anybody": ("It charges nobody.", "charges nobody -> doesn't charge anybody"),  # wording:ignore
    "anyone": ("It found no one.", "found no one -> didn't find anyone"),  # wording:ignore
    "any": ("It offers none.", "offers none -> doesn't offer any"),  # wording:ignore
    "do": ("It does nothing.", "does nothing -> doesn't do anything"),  # wording:ignore
    "after-has": ("It has sent none.", "has sent none -> hasn't sent any"),  # wording:ignore
    "capital": ("Has no fee.", "Has no fee -> Doesn't have a fee"),  # wording:ignore
}


@pytest.mark.parametrize(("text", "suggestion"), list(SUGGESTIONS.values()), ids=list(SUGGESTIONS))
def test_a_simple_verb_carries_a_suggested_rewrite(text: str, suggestion: str) -> None:
    """A present or simple-past verb gets the rewrite with the negation on the verb."""
    assert checker.find_hits(text, "page.rst")[0].suggestion == suggestion


def test_a_base_form_has_a_suggestion_of_none() -> None:
    """An infinitive such as ``to change`` followed by a negative gets ``None``."""
    hit = checker.find_hits("Asked to change nothing.", "page.rst")[0]  # wording:ignore
    assert hit.suggestion is None


# -- the command line and the baseline --------------------------------------------


def _write(path: Path, text: str) -> None:
    """Write ``text`` to ``path``, creating its directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _baseline(root: Path) -> list[str]:
    """The baseline's entries under ``root``, without its comment lines."""
    lines = (root / BASELINE).read_text(encoding="utf-8").splitlines()
    return [line for line in lines if not line.startswith("#")]


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A throwaway git checkout with one scanned page holding two hits, both allowed."""
    if GIT is None:
        pytest.skip("git is not installed")
    subprocess.run(  # noqa: S603 - fixed argv, GIT is a resolved path
        [GIT, "init", "-q", str(tmp_path)], check=True
    )
    _write(tmp_path / "docs" / "page.rst", PAGE)
    _write(tmp_path / BASELINE, "docs/page.rst 2\n")
    return tmp_path


def test_a_tree_within_its_baseline_passes(tree: Path) -> None:
    """Two hits against a baseline of two is a pass."""
    assert checker.main([], root=tree) == 0


def test_a_file_over_its_baseline_fails(tree: Path) -> None:
    """A third hit in the page fails the check."""
    _write(tree / "docs" / "page.rst", PAGE_WITH_THREE)
    assert checker.main([], root=tree) == 1


def test_a_file_over_its_baseline_prints_each_hit_with_a_suggestion(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The failure names the line and suggests the rewrite."""
    _write(tree / "docs" / "page.rst", PAGE_WITH_THREE)
    checker.main([], root=tree)
    expected = "docs/page.rst:3: It took none.\n    took none -> didn't take any"  # wording:ignore
    assert expected in capsys.readouterr().out


def test_a_file_missing_from_the_baseline_fails(tree: Path) -> None:
    """A hit in a file the baseline does not list fails the check."""
    _write(tree / "frontend" / "src" / "Page.tsx", "<p>It holds no charge.</p>\n")  # wording:ignore
    assert checker.main([], root=tree) == 1


def test_a_file_under_its_baseline_fails(tree: Path) -> None:
    """A rewrite that lowers a file's count must lower the baseline in the same change."""
    _write(tree / "docs" / "page.rst", PAGE_WITH_ONE)
    assert checker.main([], root=tree) == 1


def test_a_file_under_its_baseline_names_the_update_switch(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The failure says how to lower the baseline."""
    _write(tree / "docs" / "page.rst", PAGE_WITH_ONE)
    checker.main([], root=tree)
    assert "--update-baseline" in capsys.readouterr().out


def test_update_baseline_lowers_a_count(tree: Path) -> None:
    """``--update-baseline`` writes the lower count."""
    _write(tree / "docs" / "page.rst", PAGE_WITH_ONE)
    checker.main(["--update-baseline"], root=tree)
    assert _baseline(tree) == ["docs/page.rst 1"]


def test_update_baseline_passes_once_lowered(tree: Path) -> None:
    """After the update, the check passes against the lowered baseline."""
    _write(tree / "docs" / "page.rst", PAGE_WITH_ONE)
    checker.main(["--update-baseline"], root=tree)
    assert checker.main([], root=tree) == 0


def test_update_baseline_drops_a_cleared_file(tree: Path) -> None:
    """A file without a hit left leaves the baseline."""
    _write(tree / "docs" / "page.rst", "No token found.\n")
    checker.main(["--update-baseline"], root=tree)
    assert _baseline(tree) == []


def test_update_baseline_refuses_to_raise_a_count(tree: Path) -> None:
    """A new hit is rewritten, not recorded, so the update fails."""
    _write(tree / "docs" / "page.rst", PAGE_WITH_THREE)
    assert checker.main(["--update-baseline"], root=tree) == 1


def test_a_refused_update_leaves_the_baseline_as_it_was(tree: Path) -> None:
    """The refused update doesn't change the baseline."""
    _write(tree / "docs" / "page.rst", PAGE_WITH_THREE)
    checker.main(["--update-baseline"], root=tree)
    assert _baseline(tree) == ["docs/page.rst 2"]


def test_update_baseline_with_accept_new_records_every_hit(tree: Path) -> None:
    """``--accept-new`` records the counts as they stand, new files included, sorted."""
    _write(tree / "backend" / "a.py", '"""It took none."""\n')  # wording:ignore
    checker.main(["--update-baseline", "--accept-new"], root=tree)
    assert _baseline(tree) == ["backend/a.py 1", "docs/page.rst 2"]


def test_all_lists_every_hit_ignoring_the_baseline(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--all`` prints the two hits the baseline allows."""
    checker.main(["--all"], root=tree)
    out = capsys.readouterr().out
    listed = [line.split(":")[1] for line in out.splitlines() if line.startswith("docs/")]
    assert listed == ["1", "2"]


def test_all_fails_while_any_hit_remains(tree: Path) -> None:
    """``--all`` exits 1 when it lists a hit, so a sweep can confirm a clean area."""
    assert checker.main(["--all"], root=tree) == 1


def test_all_with_path_limits_the_listing_to_a_subtree(
    tree: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """``--path`` narrows ``--all`` to the files under it."""
    _write(tree / "backend" / "a.py", '"""It took none."""\n')  # wording:ignore
    checker.main(["--all", "--path", "backend"], root=tree)
    assert "docs/page.rst" not in capsys.readouterr().out


def test_all_with_path_passes_for_a_clean_subtree(tree: Path) -> None:
    """A subtree without a hit exits 0, even while another holds some."""
    _write(tree / "backend" / "a.py", '"""No token found."""\n')
    assert checker.main(["--all", "--path", "backend"], root=tree) == 0


SKIPPED = {
    "plans": "plans/2026-10-15-sweep.md",
    "critiques": "critiques/2026-10-15-review.md",
    "generated-schema": "frontend/src/portal/api/schema.d.ts",
    "openapi-snapshot": "backend/tests/snapshots/openapi-components.json",
    "lock-file": "frontend/package-lock.json",
}


@pytest.mark.parametrize("relative", list(SKIPPED.values()), ids=list(SKIPPED))
def test_a_skipped_file_is_never_counted(tree: Path, relative: str) -> None:
    """A file outside the scanned tree, a generated file, or a lock file is skipped."""
    _write(tree / relative, "It took nothing.\n")  # wording:ignore
    assert checker.main([], root=tree) == 0


def test_a_binary_file_is_never_counted(tree: Path) -> None:
    """A file holding a NUL byte is skipped, whatever text it also holds."""
    (tree / "docs" / "image.dat").write_bytes(b"\x00It took nothing.\n")  # wording:ignore
    assert checker.main([], root=tree) == 0


def test_update_baseline_refuses_path(tree: Path) -> None:
    """The baseline covers the whole tree, so a subtree never rewrites it."""
    with pytest.raises(SystemExit, match="2"):
        checker.main(["--update-baseline", "--path", "docs"], root=tree)


# -- the wiring ------------------------------------------------------------------


def test_make_lint_runs_the_wording_check() -> None:
    """``make lint`` depends on ``lint-wording``."""
    text = MAKEFILE.read_text(encoding="utf-8")
    lint_line = next(line for line in text.splitlines() if line.startswith("lint:"))
    assert "lint-wording" in lint_line.split("##")[0]


def test_ci_runs_the_wording_check() -> None:
    """CI lists its lint targets one by one, so it names ``lint-wording`` itself."""
    assert "run: make lint-wording" in CI_WORKFLOW.read_text(encoding="utf-8")


def test_the_script_is_executable() -> None:
    """The committed file carries its executable bit, so ``./scripts/...`` runs it."""
    assert os.access(SCRIPT, os.X_OK)
