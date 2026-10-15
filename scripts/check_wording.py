#!/usr/bin/env python3
"""Flag a verb whose object is a negative, and hold the tree to a baseline of hits.

The project's prose rule puts a negation on the verb, never on its object, its
complement, or the object of a preposition: write "doesn't have a portal account",
"didn't take anything", "there isn't a payment", or "without a term", or a plain finding
such as "No payment found".  A negative subject reads naturally ("Nobody changes their
own roles", "Nothing is due") and is never flagged.

A hit is a flagged word followed by ``no``, ``nothing``, ``nobody``, ``none``, or ``no
one``.  The flagged words are every form in ``FLAGGED_VERBS``, every word in
``FLAGGED_WORDS`` (the forms of "be" and the prepositions), and any other word ending in
``-ed`` (a past tense) outside ``ALLOWED_WORDS`` and ``NOT_PAST_TENSE``.  One pronoun
from ``PRONOUNS`` (an indirect object) or one adverb from ``ADVERBS`` may stand between
the two; a noun there (an indirect object such as "a donor") is a known gap.  The words
are
separated by a single space or tab, so a table's padding never joins two cells, or by
one line break, after which the continuation may open with a comment leader (``#``,
``#:``, ``//``, or ``*``), so a phrase wrapped in a docstring or a comment is still found.
The match ignores case.  An underscore or a letter joins words into an identifier, so
``has_no_term`` and ``hasNoTerm`` never match.  These are passed over:

* a negative that is a value or an answer: ``None`` spelled that way (Python's value),
  an all-caps negative after a verb that isn't all caps (``NONE``), and ``no`` with
  punctuation right after it ("the member said no.");
* a verb form preceded by a determiner (``a``, ``the``, ``every``, ...), which makes it a
  noun ("a change nobody made");
* ``no`` followed by a word in ``NOT_OBJECTS`` (``longer``, ``matter``, ``later``,
  ``deeper``, ...), which makes it an adverb rather than an object;
* a line that carries the marker ``wording:ignore`` (in whatever comment the file type
  allows), and the line after one that carries ``wording:ignore-next-line``.  In
  reStructuredText, where a comment cannot end a line of prose, a comment line holding
  only ``.. wording:ignore-next-line``, followed by a blank line, covers the whole next
  paragraph.  Keep the markers for text that must stay verbatim, such as a third party's
  error message.

The word lists (``FLAGGED_VERBS``, ``ALLOWED_WORDS``, ``FLAGGED_WORDS``, and the small
tables beside them) live in ``scripts/wording_words.py``, which this script imports from
its own directory.

The scanned tree is the one ``make lint-spelling`` scans, as git lists it (tracked files,
plus untracked files ``.gitignore`` does not exclude), minus generated files, lock files,
and binaries.  Hits in the generated OpenAPI files are reported at their source, the
serializer and view docstrings.

``scripts/wording-baseline.txt`` records the accepted hits per file.  Run without a
switch, the check exits 1 when a file has more hits than its baseline (every hit in it is
printed, each with a suggested rewrite where the verb is simple), when a file outside the
baseline has any hit, or when a file has fewer hits than its baseline, so that a change
that rewrites hits lowers the baseline in the same commit.  Otherwise it exits 0.

Usage::

    scripts/check_wording.py                      check against the baseline
    scripts/check_wording.py --update-baseline    lower the baseline to the counts
    scripts/check_wording.py --update-baseline --accept-new
                                                  record every count, raised ones too
    scripts/check_wording.py --all [--path DIR]   list every hit, ignoring the baseline
    scripts/check_wording.py --coordinated [--path DIR]
                                                  list "and/or/but no" for review

``--update-baseline`` refuses (exit 1) to raise a count or add a file unless
``--accept-new`` is given.  It writes tracked files only: a file git doesn't track yet is
left out with a warning, so a scratch file never lands in the baseline.  Renaming a file
that has hits moves its count to a path the baseline doesn't list, so the rename needs
``--update-baseline --accept-new``, and a review of the baseline's diff to confirm that
the old path's count moved to the new one unchanged.  ``--all`` exits 1 when it lists a
hit, so it confirms that an area is clean; ``--path`` (repeatable) limits ``--all``,
``--coordinated``, or the check to a subtree, and is refused with ``--update-baseline``,
since the baseline covers the whole tree.

Known gaps, which the sweep reviews by hand:

* a noun between the verb and the negative (an indirect object such as "a donor");
* a coordinated object after ``and``, ``or``, or ``but`` ("gets 400 and" followed by a
  negative), which the rule covers but the check can't tell from a new negative subject;
  ``--coordinated`` lists every such candidate and always exits 0;
* text inside a literal or code-block body, which a marker can't reach without showing
  in the rendered page.
"""

import argparse
import bisect
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from wording_words import (
    ADVERBS,
    ALLOWED_WORDS,
    ANY_BEFORE,
    BE_FORMS,
    BOUNDS,
    DETERMINERS,
    FLAGGED_VERBS,
    FLAGGED_WORDS,
    MODALS,
    NEGATED_WORDS,
    NOT_OBJECTS,
    NOT_PAST_TENSE,
    PERFECT_AUXILIARIES,
    POSITIVES,
    PREPOSITIONS,
    PRONOUNS,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

#: The accepted hits per file, relative to the root the check runs from.
BASELINE = "scripts/wording-baseline.txt"

#: What the check scans: the same tree ``make lint-spelling`` hands codespell.
SCANNED_PATHS = (
    "README.rst",
    "CLAUDE.md",
    "docs",
    "backend",
    "frontend/src",
    "frontend/e2e",
    "frontend/scripts",
    "scripts",
    ".github",
    "deploy",
    ".claude",
)

#: Directories inside the scanned tree that hold build output, generated text (the golden
#: files a test compares its output with), or nested checkouts of this repository.
SKIPPED_PREFIXES = (
    ".claude/worktrees/",
    "backend/htmlcov/",
    "backend/staticfiles/",
    "backend/tests/golden/",
    "docs/_build/",
    "frontend/dist/",
    "frontend/e2e/.mail/",
)

#: Generated files.  The OpenAPI description and its snapshot repeat the serializer and
#: view docstrings, which the check reads at their source.
SKIPPED_FILES = (
    BASELINE,
    "backend/openapi.json",
    "backend/tests/snapshots/openapi-components.json",
    "frontend/e2e/seed-facts.json",
    "frontend/src/portal/api/schema.d.ts",
)

#: Lock files and binary formats, skipped by name before they are read.
SKIPPED_SUFFIXES = (
    ".gif",
    ".gz",
    ".ico",
    ".jpeg",
    ".jpg",
    ".lock",
    ".otf",
    ".pdf",
    ".png",
    ".svg",
    ".ttf",
    ".webp",
    ".woff",
    ".woff2",
    ".zip",
    "package-lock.json",
)

#: Every flagged form, lower case: each verb form, plus ``FLAGGED_WORDS``.
FLAGGED_FORMS = frozenset(
    [form for family in FLAGGED_VERBS for form in family.split()]
    + [word for group in FLAGGED_WORDS for word in group.split()]
)

#: Every deliberately allowed word, lower case.
ALLOWED_FORMS = frozenset(word for group in ALLOWED_WORDS for word in group.split())

#: The prepositions, lower case: a pronoun after one is its object, never read past.
PREPOSITION_FORMS = frozenset(word for group in PREPOSITIONS for word in group.split())

#: A word after a negative that makes the negative a subject, once a pronoun stands
#: before it ("tell them nobody is coming"): a verb form, a form of "be", or a modal.
CLAUSE_VERBS = frozenset(
    [form for family in FLAGGED_VERBS for form in family.split()]
    + BE_FORMS.split()
    + MODALS.split()
)

#: A character right after ``no`` that makes it an answer rather than a determiner:
#: "the member said no."
ANSWER_ENDINGS = frozenset(".,;:!?)]}\"'" + chr(0x2019) + chr(0x201D))

# A single space or tab, so that a table's padding never joins two cells; or one line
# break, with the continuation's indentation and comment leader.
_SEPARATOR = r"(?:[ \t]|[ \t]*\r?\n[ \t]*(?:(?:\#:?|//|\*)[ \t]*)?)"

#: The apostrophes that join a contraction into one word: straight and typographic.
_APOSTROPHES = "'" + chr(0x2019)

# A lookahead, so that every word start is tried and one candidate never hides the next.
_CANDIDATE = re.compile(
    rf"(?<![\w{_APOSTROPHES}])(?=(?P<verb>[A-Za-z]+)"
    + _SEPARATOR
    + rf"(?:(?P<middle>{'|'.join(PRONOUNS + ADVERBS)})"
    + _SEPARATOR
    + ")?"
    + rf"(?P<negative>nothing|nobody|none|no)(?![\w{_APOSTROPHES}-]))",
    re.IGNORECASE,
)

_NEXT_WORD = re.compile(_SEPARATOR + r"([A-Za-z]+)")

_THAN = re.compile(_SEPARATOR + r"[A-Za-z]+" + _SEPARATOR + r"than\b", re.IGNORECASE)

# A coordinating conjunction before a negative: "gets 400 and no message".  The rule
# covers a coordinated object, but the check can't tell one from a new negative subject
# ("and no email is sent"), so ``--coordinated`` only lists these for review by hand.
_COORDINATED = re.compile(
    rf"(?<![\w{_APOSTROPHES}])(?=(?P<verb>and|but|or)"
    + _SEPARATOR
    + rf"(?P<negative>nothing|nobody|none|no)(?![\w{_APOSTROPHES}-]))",
    re.IGNORECASE,
)

_PREVIOUS_WORD = re.compile(rf"(?<![\w{_APOSTROPHES}])([A-Za-z]+)" + _SEPARATOR + r"\Z")

_MARKER = "wording:ignore"

_SAME_LINE_MARKER = re.compile(r"wording:ignore(?!-next-line)")

_NEXT_LINE_MARKER = "wording:ignore-next-line"

# A reStructuredText comment that holds only the next-line marker.
_PARAGRAPH_MARKER = re.compile(r"\s*\.\.\s+wording:ignore-next-line\s*")

_BASELINE_HEADER = (
    "# The hits scripts/check_wording.py accepts per file: a path and its count, sorted.\n"
    "# Rewrite a hit, then lower this file with scripts/check_wording.py --update-baseline\n"
    "# in the same change.\n"
)


class _Family(NamedTuple):
    """The five forms of one flagged verb, in ``FLAGGED_VERBS`` order."""

    base: str
    third: str
    past: str
    participle: str
    present_participle: str


def _families() -> dict[str, _Family]:
    """Map each flagged form to its family; a family with other than five forms raises."""
    families = {}
    for line in FLAGGED_VERBS:
        family = _Family(*line.split())
        for form in family:
            families[form] = family
    return families


_FAMILY_OF = _families()


@dataclass(frozen=True)
class Hit:
    """One flagged phrase: where it is, its line's text, and a rewrite if one is simple.

    ``line`` is the 1-based line the verb is on.  ``text`` is that line stripped, joined
    with the next line when the phrase wraps.  ``suggestion`` reads ``"<phrase> ->
    <rewrite>"`` for a third-person present form, a simple past that differs from the
    base form, or a past participle after ``has``, ``have``, or ``had``, each with at
    most a pronoun before the negative, and for ``is``, ``are``, ``was``, ``were``,
    ``am``, and ``with`` (``NEGATED_WORDS``).  It is ``None`` for every other hit (a base
    form, an ``-ing`` form, an unlisted ``-ed`` word, any other word from
    ``FLAGGED_WORDS``, or a phrase with an adverb in it), whose rewrite depends on the
    words around it.
    """

    path: str
    line: int
    text: str
    suggestion: str | None


@dataclass(frozen=True)
class Comparison:
    """The files whose hit count is above, or below, their baseline count.

    A file the baseline does not list counts as a baseline of 0, and a listed file that
    holds fewer hits, or is gone, as below it.  Both lists are sorted.
    """

    over: list[str]
    under: list[str]


def find_hits(text: str, path: str) -> list[Hit]:
    """Return every hit in ``text``, the contents of the file at ``path``, in order.

    ``path`` is only recorded on each hit.  See the module docstring for what is flagged
    and what is passed over.
    """
    return _find(text, path, coordinated=False)


def find_coordinated(text: str, path: str) -> list[Hit]:
    """Return every ``and``, ``or``, or ``but`` before a negative in ``text``, in order.

    These are candidates for review by hand, never hits: "gets 400 and no message" puts
    the negation on a coordinated object, which the rule forbids, but "and no email is
    sent" starts a clause with a negative subject, which it allows.  The exemptions and
    markers that apply to a hit apply here too; ``suggestion`` is always ``None``.
    """
    return _find(text, path, coordinated=True)


def _find(text: str, path: str, *, coordinated: bool) -> list[Hit]:
    """The hits, or with ``coordinated`` the conjunction candidates, in ``text``."""
    lines = text.split("\n")
    line_starts = [0]
    for line in lines[:-1]:
        line_starts.append(line_starts[-1] + len(line) + 1)
    silenced = _silenced_lines(lines) if _MARKER in text else set()
    hits = []
    for match in (_COORDINATED if coordinated else _CANDIDATE).finditer(text):
        verb, negative = match["verb"], match["negative"]
        middle = None if coordinated else match["middle"]
        if not coordinated and not _is_flagged(verb):
            continue
        if _is_not_an_object(text, match):
            continue
        next_match = _NEXT_WORD.match(text, match.end("negative"))
        next_word = next_match[1] if next_match is not None else None
        is_adverb = next_word is not None and next_word.lower() in NOT_OBJECTS
        if negative.lower() == "no" and is_adverb:
            continue
        if middle is not None and _starts_a_clause(verb, middle, next_word):
            continue
        verb_start = match.start("verb")
        previous_match = _PREVIOUS_WORD.search(text, max(0, verb_start - 80), verb_start)
        previous = previous_match[1] if previous_match is not None else None
        if previous is not None and previous.lower() in DETERMINERS:
            continue
        first = bisect.bisect_right(line_starts, verb_start)
        last = bisect.bisect_right(line_starts, match.start("negative"))
        if any(number in silenced for number in range(first, last + 1)):
            continue
        phrase = _Phrase(
            verb,
            middle,
            negative,
            next_word=next_word,
            previous=previous,
            is_bound=_THAN.match(text, match.end("negative")) is not None,
        )
        hits.append(
            Hit(
                path=path,
                line=first,
                text=" ".join(lines[number - 1].strip() for number in range(first, last + 1)),
                suggestion=None if coordinated else _suggestion(phrase),
            )
        )
    return hits


def _starts_a_clause(verb: str, middle: str, next_word: str | None) -> bool:
    """Whether a pronoun between ``verb`` and the negative ends the phrase there.

    A pronoun after a preposition is that preposition's object ("without it nothing
    runs"), and a pronoun followed by a negative and then a verb, a form of "be", or a
    modal is an object whose own clause has a negative subject ("tell them nobody is
    coming").  An adverb in between never ends the phrase.
    """
    if middle.lower() not in PRONOUNS:
        return False
    if verb.lower() in PREPOSITION_FORMS:
        return True
    return next_word is not None and next_word.lower() in CLAUSE_VERBS


def _is_flagged(word: str) -> bool:
    """Whether ``word`` is a listed form, or an unlisted word that reads as past tense."""
    lower = word.lower()
    if lower in FLAGGED_FORMS:
        return True
    return lower.endswith("ed") and lower not in ALLOWED_FORMS and lower not in NOT_PAST_TENSE


def _is_not_an_object(text: str, match: re.Match[str]) -> bool:
    """Whether the matched negative is a value or an answer rather than an object.

    That is ``None`` spelled that way (Python's value), an all-caps negative after a verb
    that isn't all caps (``NONE``, a constant), and ``no`` with punctuation right after
    it ("said no.").
    """
    verb, negative = match["verb"], match["negative"]
    if negative == "None":
        return True
    if negative.isupper() and not verb.isupper():
        return True
    end = match.end("negative")
    is_answer = end < len(text) and text[end] in ANSWER_ENDINGS
    return negative.lower() == "no" and is_answer


def _silenced_lines(lines: list[str]) -> set[int]:
    """The 1-based numbers of the lines a marker covers.

    A line carrying ``wording:ignore`` covers itself, and one carrying
    ``wording:ignore-next-line`` covers the line after it.  A reStructuredText comment
    that holds only the next-line marker (``.. wording:ignore-next-line``, which a blank
    line must follow) covers the whole next paragraph: it skips the blank lines
    after it, then covers every line through the next blank one.
    """
    silenced = set()
    for index, line in enumerate(lines):
        number = index + 1
        if _SAME_LINE_MARKER.search(line) is not None:
            silenced.add(number)
        if _PARAGRAPH_MARKER.fullmatch(line) is not None:
            following = index + 1
            while following < len(lines) and lines[following].strip() == "":
                following += 1
            while following < len(lines) and lines[following].strip() != "":
                silenced.add(following + 1)
                following += 1
        elif _NEXT_LINE_MARKER in line:
            silenced.add(number + 1)
    return silenced


class _Phrase(NamedTuple):
    """A hit's words: the verb, what stands between it and the negative, and around it."""

    verb: str
    middle: str | None
    negative: str
    next_word: str | None
    previous: str | None
    is_bound: bool


def _suggestion(phrase: _Phrase) -> str | None:
    """The rewrite of the phrase with the negation on the verb, if one is simple.

    A third-person present form takes ``doesn't``, a simple past ``didn't``, and a past
    participle after ``has``, ``have``, or ``had`` that auxiliary's negative, and a word
    in ``NEGATED_WORDS`` its negated form (``is`` -> ``isn't``, ``with`` -> ``without``);
    a pronoun before the negative stays where it is.  ``no`` is rewritten with ``anyone``
    before ``one``, ``any`` before a plural or a word in ``ANY_BEFORE``, and ``a`` or
    ``an`` otherwise; the word after ``no`` is shown on both sides.  A bound keeps its
    meaning without the negative: ``no more than`` becomes ``at most``, and ``no fewer
    than`` or ``no less than`` becomes ``at least``, after any flagged word.  Returns
    ``None`` for any other word or form, and for a phrase with an adverb in it.
    """
    verb, middle, previous = phrase.verb, phrase.middle, phrase.previous
    form = verb.lower()
    if middle is not None and middle.lower() in ADVERBS:
        return None
    next_word = phrase.next_word
    if phrase.is_bound and next_word is not None and next_word.lower() in BOUNDS:
        lead = verb if middle is None else f"{verb} {middle}"
        bound = BOUNDS[next_word.lower()]
        return f"{lead} {phrase.negative} {next_word} than -> {lead} {bound}"
    objects, positive = _objects(phrase.negative, phrase.next_word)
    if middle is not None:
        objects, positive = f"{middle} {objects}", f"{middle} {positive}"
    if form in NEGATED_WORDS:
        return f"{verb} {objects} -> {_like(verb, NEGATED_WORDS[form])} {positive}"
    if form not in _FAMILY_OF:
        return None
    family = _FAMILY_OF[form]
    if (
        previous is not None
        and previous.lower() in PERFECT_AUXILIARIES
        and form == family.participle
    ):
        negated = _like(previous, f"{previous.lower()}n't")
        return f"{previous} {verb} {objects} -> {negated} {form} {positive}"
    if form == family.third:
        auxiliary = "doesn't"
    elif form == family.past and family.past != family.base:
        auxiliary = "didn't"
    else:
        return None
    return f"{verb} {objects} -> {_like(verb, auxiliary)} {family.base} {positive}"


def _objects(negative: str, next_word: str | None) -> tuple[str, str]:
    """The negative object as written, and its positive rewrite."""
    lower = negative.lower()
    if lower in POSITIVES:
        return negative, POSITIVES[lower]
    if next_word is None:
        return negative, "any"
    phrase = f"{negative} {next_word}"
    word = next_word.lower()
    if word == "one":
        return phrase, "anyone"
    if word in ANY_BEFORE or (word.endswith("s") and not word.endswith("ss")):
        return phrase, f"any {next_word}"
    article = "an" if word[0] in "aeiou" else "a"
    return phrase, f"{article} {next_word}"


def _like(model: str, word: str) -> str:
    """``word`` capitalized when ``model`` is, so a rewrite keeps its sentence case."""
    return word[0].upper() + word[1:] if model[0].isupper() else word


def scan(
    root: Path,
    *,
    paths: Sequence[str] = (),
    finder: Callable[[str, str], list[Hit]] = find_hits,
) -> dict[str, list[Hit]]:
    """Return the hits in every scanned file under ``root`` that has any, by path.

    ``paths`` limits the scan to those files and directories (relative to ``root``); an
    empty sequence scans the whole tree.  ``finder`` reads each file's text and path:
    ``find_hits`` by default, or ``find_coordinated``.  A file holding a NUL byte, or one
    that is not UTF-8, is skipped as binary.
    """
    found = {}
    for path in scanned_files(root):
        if len(paths) > 0 and not _is_under(path, paths):
            continue
        data = (root / path).read_bytes()
        if b"\0" in data:
            continue
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            continue
        hits = finder(text, path)
        if len(hits) > 0:
            found[path] = hits
    return found


def scanned_files(root: Path) -> list[str]:
    """Every file the check reads under the git checkout at ``root``, sorted.

    Git lists the tracked files and the untracked ones ``.gitignore`` does not exclude,
    under ``SCANNED_PATHS``; the skipped prefixes, files, and suffixes are then dropped,
    as is any path that isn't a regular file (a deleted file or a nested checkout).
    """
    paths = _git_files(root, "--cached", "--others", "--exclude-standard")
    return sorted(path for path in paths if not _is_skipped(path) and (root / path).is_file())


def tracked_files(root: Path) -> set[str]:
    """Every path under ``SCANNED_PATHS`` that git tracks (or has staged) at ``root``."""
    return _git_files(root, "--cached")


def _git_files(root: Path, *options: str) -> set[str]:
    """The paths ``git ls-files`` lists under ``SCANNED_PATHS`` with ``options``."""
    git = shutil.which("git")
    if git is None:
        raise SystemExit("check_wording: git is not installed")
    listing = subprocess.run(  # noqa: S603 - fixed argv, git is a resolved path
        [git, "ls-files", "-z", *options, "--", *SCANNED_PATHS],
        cwd=root,
        capture_output=True,
        check=True,
    )
    return {path for path in listing.stdout.decode("utf-8").split("\0") if path != ""}


def _is_skipped(path: str) -> bool:
    """Whether ``path`` is build output, generated, a lock file, or binary by name."""
    return (
        path.startswith(SKIPPED_PREFIXES)
        or path in SKIPPED_FILES
        or path.endswith(SKIPPED_SUFFIXES)
        or "/node_modules/" in f"/{path}"
    )


def _is_under(path: str, roots: Sequence[str]) -> bool:
    """Whether ``path`` is one of ``roots`` or inside one of them."""
    return any(path == root or path.startswith(f"{root}/") for root in roots)


def read_baseline(path: Path) -> dict[str, int]:
    """The baseline at ``path`` as a map of file path to count; empty when it is missing.

    Each line is a path and a count separated by a space; blank lines and lines starting
    with ``#`` are skipped.
    """
    if not path.is_file():
        return {}
    baseline = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() == "" or line.startswith("#"):
            continue
        file_path, count = line.rsplit(" ", 1)
        baseline[file_path] = int(count)
    return baseline


def write_baseline(path: Path, counts: dict[str, int]) -> None:
    """Write ``counts`` to ``path`` under a comment header, sorted, leaving out zeros."""
    entries = "".join(f"{file_path} {counts[file_path]}\n" for file_path in sorted(counts))
    path.write_text(_BASELINE_HEADER + entries, encoding="utf-8")


def compare(counts: dict[str, int], baseline: dict[str, int]) -> Comparison:
    """Compare the hit count per file with the baseline's (see ``Comparison``)."""
    every_path = sorted(set(counts) | set(baseline))
    return Comparison(
        over=[path for path in every_path if counts.get(path, 0) > baseline.get(path, 0)],
        under=[path for path in every_path if counts.get(path, 0) < baseline.get(path, 0)],
    )


def main(argv: Sequence[str] | None = None, *, root: Path = REPO_ROOT) -> int:
    """Run the check against the tree at ``root``; return the exit status.

    ``argv`` defaults to the command line.  An invalid combination of switches exits 2
    through ``argparse``.
    """
    parser = _parser()
    args = parser.parse_args(argv)
    roots = [path.strip("/").removeprefix("./") for path in args.path]
    if args.update_baseline and len(roots) > 0:
        parser.error("--path cannot be combined with --update-baseline")
    if args.accept_new and not args.update_baseline:
        parser.error("--accept-new needs --update-baseline")
    if args.coordinated:
        return _list_coordinated(scan(root, paths=roots, finder=find_coordinated))
    hits = scan(root, paths=roots)
    if args.all:
        return _list_all(hits)
    counts = {path: len(found) for path, found in hits.items()}
    baseline = read_baseline(root / BASELINE)
    if len(roots) > 0:
        baseline = {path: count for path, count in baseline.items() if _is_under(path, roots)}
    if args.update_baseline:
        return _update(root, hits, baseline, accept_new=args.accept_new)
    return _report(hits, counts, baseline, compare(counts, baseline))


def _parser() -> argparse.ArgumentParser:
    """The parser for the switches the module docstring lists."""
    parser = argparse.ArgumentParser(
        prog="check_wording.py",
        description="Flag a verb whose object is a negative, against a per-file baseline.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--all", action="store_true", help="list every hit, ignoring the baseline")
    mode.add_argument(
        "--coordinated",
        action="store_true",
        help="list every 'and', 'or', or 'but' before a negative, for review by hand",
    )
    mode.add_argument(
        "--update-baseline",
        action="store_true",
        help="lower the baseline to the current counts",
    )
    parser.add_argument(
        "--accept-new",
        action="store_true",
        help="with --update-baseline, also record raised counts and new files",
    )
    parser.add_argument(
        "--path",
        action="append",
        default=[],
        metavar="PATH",
        help="limit the check, --all, or --coordinated to this file or directory (repeatable)",
    )
    return parser


def _list_all(hits: dict[str, list[Hit]]) -> int:
    """Print every hit and a total; 1 when there is any hit, else 0."""
    for path in sorted(hits):
        _print_hits(hits[path])
    total = sum(len(found) for found in hits.values())
    _out(f"{_plural(total, 'hit')} in {_plural(len(hits), 'file')}\n")
    return 1 if total > 0 else 0


def _list_coordinated(candidates: dict[str, list[Hit]]) -> int:
    """Print every conjunction candidate and a total; always 0, since none is a hit."""
    for path in sorted(candidates):
        _print_hits(candidates[path])
    total = sum(len(found) for found in candidates.values())
    _out(f"{_plural(total, 'candidate')} in {_plural(len(candidates), 'file')}\n")
    return 0


def _update(
    root: Path, hits: dict[str, list[Hit]], baseline: dict[str, int], *, accept_new: bool
) -> int:
    """Write the tracked files' counts as the baseline; refuse a raised one by default.

    A file with hits that git doesn't track is left out, with a warning naming it.
    Without ``accept_new``, a count above the baseline (or a file outside it) refuses the
    update, and the baseline is left as it was.
    """
    tracked = tracked_files(root)
    for path in sorted(set(hits) - tracked):
        _out(
            f"Left out of the baseline, since git doesn't track it yet: {path} "
            f"({_plural(len(hits[path]), 'hit')})\n"
        )
    counts = {path: len(found) for path, found in hits.items() if path in tracked}
    comparison = compare(counts, baseline)
    if len(comparison.over) > 0 and not accept_new:
        for path in comparison.over:
            _print_hits(hits[path])
        _out(
            f"Refused: {_plural(len(comparison.over), 'file')} over the baseline.  Rewrite "
            "the hits, or pass --accept-new to record them.\n"
        )
        return 1
    write_baseline(root / BASELINE, counts)
    _out(
        f"Wrote {BASELINE}: {_plural(sum(counts.values()), 'hit')} in "
        f"{_plural(len(counts), 'file')}.\n"
    )
    return 0


def _report(
    hits: dict[str, list[Hit]],
    counts: dict[str, int],
    baseline: dict[str, int],
    comparison: Comparison,
) -> int:
    """Print the files over and under the baseline; 1 when there is either, else 0."""
    for path in comparison.over:
        _print_hits(hits[path])
        allowed = baseline.get(path, 0)
        _out(f"{path}: {_plural(counts[path], 'hit')}, over the baseline's {allowed}\n")
    for path in comparison.under:
        _out(
            f"{path}: {_plural(counts.get(path, 0), 'hit')}, under the baseline's "
            f"{baseline[path]}; lower it with scripts/check_wording.py --update-baseline\n"
        )
    if len(comparison.over) + len(comparison.under) == 0:
        _out(
            f"Wording check: {_plural(sum(counts.values()), 'hit')} in "
            f"{_plural(len(counts), 'file')}, within the baseline.\n"
        )
        return 0
    if len(comparison.over) > 0:
        _out(
            "Put the negation on the verb, as each suggestion shows, or end a line that "
            "must stay verbatim with a wording:ignore comment.\n"
        )
    return 1


def _print_hits(hits: list[Hit]) -> None:
    """Print each hit as ``path:line: text``, with its suggestion indented below it."""
    for hit in hits:
        _out(f"{hit.path}:{hit.line}: {hit.text}\n")
        if hit.suggestion is not None:
            _out(f"    {hit.suggestion}\n")


def _plural(count: int, noun: str) -> str:
    """``count`` and ``noun``, with an ``s`` unless the count is 1."""
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def _out(text: str) -> None:
    """Write ``text`` to standard output."""
    sys.stdout.write(text)


if __name__ == "__main__":
    sys.exit(main())
