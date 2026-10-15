#!/usr/bin/env python3
"""Flag a verb whose object is a negative, and hold the tree to a baseline of hits.

The project's prose rule puts a negation on the verb, never on its object: write "doesn't
have a portal account" or "didn't take anything", or a plain finding such as "No payment
found".  A negative subject reads naturally ("Nobody changes their own roles", "Nothing
is due") and is never flagged.

A hit is a word from ``FLAGGED_VERBS`` followed, across whitespace alone, by ``no``,
``nothing``, ``nobody``, ``none``, or ``no one``.  The match ignores case, except that
``None`` spelled that way is Python's value.  Whitespace may include one line break, and
the continuation line may open with a comment leader (``#``, ``#:``, ``//``, or ``*``),
so a phrase wrapped in a docstring or a comment is still found.  An underscore or a letter
joins words into an identifier, so ``has_no_term`` and ``hasNoTerm`` never match.  These
are passed over:

* a verb form preceded by a determiner (``a``, ``the``, ``every``, ...), which makes it a
  noun: "a change nobody made";
* ``no`` followed by ``longer``, ``matter``, ``later``, ``earlier``, ``sooner``,
  ``faster``, or ``slower``, which is an adverb rather than an object;
* a line that carries the marker ``wording:ignore`` (in whatever comment the file type
  allows), and the line after one that carries ``wording:ignore-next-line``.  Keep the
  markers for text that must stay verbatim, such as a third party's error message.

The scanned tree is the one ``make lint-spelling`` scans, as git lists it (tracked files,
plus untracked files ``.gitignore`` does not exclude), minus generated files, lock files,
and binaries.  Hits in the generated OpenAPI files are reported at their source, the
serializer and view docstrings.

``scripts/wording-baseline.txt`` records the accepted hits per file.  With no switch, the
check exits 1 when a file has more hits than its baseline (every hit in it is printed,
each with a suggested rewrite where the verb is simple), when a file outside the baseline
has any hit, or when a file has fewer hits than its baseline, so that a change that
rewrites hits lowers the baseline in the same commit.  Otherwise it exits 0.

Usage::

    scripts/check_wording.py                      check against the baseline
    scripts/check_wording.py --update-baseline    lower the baseline to the counts
    scripts/check_wording.py --update-baseline --accept-new
                                                  record every count, raised ones too
    scripts/check_wording.py --all [--path DIR]   list every hit, ignoring the baseline

``--update-baseline`` refuses (exit 1) to raise a count or add a file unless
``--accept-new`` is given.  ``--all`` exits 1 when it lists a hit, so it confirms that an
area is clean; ``--path`` (repeatable) limits ``--all`` or the check to a subtree, and is
refused with ``--update-baseline``, since the baseline covers the whole tree.
"""

import argparse
import bisect
import re
import shutil
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

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

#: Directories inside the scanned tree that hold build output, generated text, or nested
#: checkouts of this repository.
SKIPPED_PREFIXES = (
    ".claude/worktrees/",
    "backend/htmlcov/",
    "backend/staticfiles/",
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

# The verbs the check flags, one family per string: base form, third person singular,
# simple past, past participle, and present participle.  The list was built by
# extracting every word that precedes ``no``, ``nothing``, ``nobody``, or ``none`` in the
# scanned tree and keeping each one that can act as a verb (possession or action), with
# its other forms, plus common verbs the tree does not use yet.  A word that is also a
# noun ("changes", "records", "names") is flagged anyway: a determiner before it already
# marks the plain noun use, and a rewrite costs less than a missed hit.  Linking verbs
# are flagged only where the phrase reads as a negative object, as "becomes" can.
FLAGGED_VERBS = (
    "accept accepts accepted accepted accepting",
    "accompany accompanies accompanied accompanied accompanying",
    "activate activates activated activated activating",
    "add adds added added adding",
    "affect affects affected affected affecting",
    "allow allows allowed allowed allowing",
    "alter alters altered altered altering",
    "answer answers answered answered answering",
    "apply applies applied applied applying",
    "ask asks asked asked asking",
    "assert asserts asserted asserted asserting",
    "attach attaches attached attached attaching",
    "become becomes became become becoming",
    "bring brings brought brought bringing",
    "build builds built built building",
    "buy buys bought bought buying",
    "call calls called called calling",
    "cap caps capped capped capping",
    "carry carries carried carried carrying",
    "catch catches caught caught catching",
    "cause causes caused caused causing",
    "change changes changed changed changing",
    "charge charges charged charged charging",
    "check checks checked checked checking",
    "choose chooses chose chosen choosing",
    "cite cites cited cited citing",
    "claim claims claimed claimed claiming",
    "clear clears cleared cleared clearing",
    "close closes closed closed closing",
    "collect collects collected collected collecting",
    "confirm confirms confirmed confirmed confirming",
    "connect connects connected connected connecting",
    "contact contacts contacted contacted contacting",
    "contain contains contained contained containing",
    "contribute contributes contributed contributed contributing",
    "convert converts converted converted converting",
    "copy copies copied copied copying",
    "cost costs cost cost costing",
    "count counts counted counted counting",
    "cover covers covered covered covering",
    "create creates created created creating",
    "declare declares declared declared declaring",
    "delete deletes deleted deleted deleting",
    "deliver delivers delivered delivered delivering",
    "do does did done doing",
    "draw draws drew drawn drawing",
    "drop drops dropped dropped dropping",
    "duplicate duplicates duplicated duplicated duplicating",
    "earn earns earned earned earning",
    "email emails emailed emailed emailing",
    "emit emits emitted emitted emitting",
    "end ends ended ended ending",
    "enter enters entered entered entering",
    "exclude excludes excluded excluded excluding",
    "exempt exempts exempted exempted exempting",
    "expand expands expanded expanded expanding",
    "expect expects expected expected expecting",
    "expire expires expired expired expiring",
    "export exports exported exported exporting",
    "expose exposes exposed exposed exposing",
    "extend extends extended extended extending",
    "fail fails failed failed failing",
    "fetch fetches fetched fetched fetching",
    "file files filed filed filing",
    "fill fills filled filled filling",
    "filter filters filtered filtered filtering",
    "find finds found found finding",
    "finish finishes finished finished finishing",
    "fit fits fitted fitted fitting",
    "flag flags flagged flagged flagging",
    "flip flips flipped flipped flipping",
    "follow follows followed followed following",
    "generate generates generated generated generating",
    "get gets got gotten getting",
    "give gives gave given giving",
    "go goes went gone going",
    "grant grants granted granted granting",
    "have has had had having",
    "hear hears heard heard hearing",
    "help helps helped helped helping",
    "hide hides hid hidden hiding",
    "hold holds held held holding",
    "identify identifies identified identified identifying",
    "import imports imported imported importing",
    "include includes included included including",
    "inject injects injected injected injecting",
    "install installs installed installed installing",
    "involve involves involved involved involving",
    "issue issues issued issued issuing",
    "join joins joined joined joining",
    "keep keeps kept kept keeping",
    "know knows knew known knowing",
    "launch launches launched launched launching",
    "lay lays laid laid laying",
    "lead leads led led leading",
    "learn learns learned learned learning",
    "leave leaves left left leaving",
    "let lets let let letting",
    "limit limits limited limited limiting",
    "link links linked linked linking",
    "list lists listed listed listing",
    "load loads loaded loaded loading",
    "log logs logged logged logging",
    "look looks looked looked looking",
    "lose loses lost lost losing",
    "mail mails mailed mailed mailing",
    "make makes made made making",
    "manage manages managed managed managing",
    "mark marks marked marked marking",
    "match matches matched matched matching",
    "mean means meant meant meaning",
    "mention mentions mentioned mentioned mentioning",
    "move moves moved moved moving",
    "name names named named naming",
    "narrow narrows narrowed narrowed narrowing",
    "need needs needed needed needing",
    "obtain obtains obtained obtained obtaining",
    "offer offers offered offered offering",
    "open opens opened opened opening",
    "orchestrate orchestrates orchestrated orchestrated orchestrating",
    "order orders ordered ordered ordering",
    "outlive outlives outlived outlived outliving",
    "owe owes owed owed owing",
    "paint paints painted painted painting",
    "pass passes passed passed passing",
    "pay pays paid paid paying",
    "permit permits permitted permitted permitting",
    "pick picks picked picked picking",
    "pin pins pinned pinned pinning",
    "play plays played played playing",
    "post posts posted posted posting",
    "print prints printed printed printing",
    "process processes processed processed processing",
    "produce produces produced produced producing",
    "promise promises promised promised promising",
    "protect protects protected protected protecting",
    "prove proves proved proven proving",
    "provide provides provided provided providing",
    "publish publishes published published publishing",
    "put puts put put putting",
    "queue queues queued queued queuing",
    "raise raises raised raised raising",
    "reach reaches reached reached reaching",
    "reactivate reactivates reactivated reactivated reactivating",
    "read reads read read reading",
    "receive receives received received receiving",
    "record records recorded recorded recording",
    "refund refunds refunded refunded refunding",
    "refuse refuses refused refused refusing",
    "remove removes removed removed removing",
    "render renders rendered rendered rendering",
    "renew renews renewed renewed renewing",
    "report reports reported reported reporting",
    "require requires required required requiring",
    "reset resets reset reset resetting",
    "resemble resembles resembled resembled resembling",
    "restore restores restored restored restoring",
    "restrict restricts restricted restricted restricting",
    "retain retains retained retained retaining",
    "return returns returned returned returning",
    "reveal reveals revealed revealed revealing",
    "rewrite rewrites rewrote rewritten rewriting",
    "run runs ran run running",
    "save saves saved saved saving",
    "say says said said saying",
    "schedule schedules scheduled scheduled scheduling",
    "see sees saw seen seeing",
    "seed seeds seeded seeded seeding",
    "select selects selected selected selecting",
    "sell sells sold sold selling",
    "send sends sent sent sending",
    "serve serves served served serving",
    "set sets set set setting",
    "settle settles settled settled settling",
    "share shares shared shared sharing",
    "ship ships shipped shipped shipping",
    "show shows showed shown showing",
    "sign signs signed signed signing",
    "skip skips skipped skipped skipping",
    "spend spends spent spent spending",
    "stack stacks stacked stacked stacking",
    "stamp stamps stamped stamped stamping",
    "start starts started started starting",
    "store stores stored stored storing",
    "submit submits submitted submitted submitting",
    "supply supplies supplied supplied supplying",
    "take takes took taken taking",
    "tell tells told told telling",
    "terminate terminates terminated terminated terminating",
    "touch touches touched touched touching",
    "transfer transfers transferred transferred transferring",
    "trigger triggers triggered triggered triggering",
    "trust trusts trusted trusted trusting",
    "unaffiliate unaffiliates unaffiliated unaffiliated unaffiliating",
    "undo undoes undid undone undoing",
    "unsubscribe unsubscribes unsubscribed unsubscribed unsubscribing",
    "update updates updated updated updating",
    "use uses used used using",
    "verify verifies verified verified verifying",
    "want wants wanted wanted wanting",
    "work works worked worked working",
    "write writes wrote written writing",
    "yield yields yielded yielded yielding",
)

# The words found before a negative that are deliberately left alone, one group per
# string.  Linking and existential verbs ("there is no payment", "it was no surprise")
# and modals ("may no longer") state a fact, not an action on an object.  Prepositions
# ("with no term", "for no one", "more than nothing"), conjunctions, relative words, and
# adverbs introduce a negative subject or a noun phrase.  A pronoun or an article ("sends
# it no more", "the No answer") puts the verb out of reach.  A word in neither tuple is
# left alone too: this one records the decisions.
ALLOWED_WORDS = (
    # Linking and existential verbs.
    "am are be been being exist existed exists is remain remained remains seem seemed",
    "seems stay stayed stays was were",
    # Modals.
    "can could may might must shall should will would",
    # Prepositions.
    "about after against at before by during for from in into of on onto over per plus",
    "since than through to toward towards under until upon via with within without",
    # Conjunctions, relative words, and adverbs.
    "almost alone although and because but deliberately else here if nor once only or",
    "otherwise possibly simply so that then there though when where whereas whether",
    "which while who whom why yet",
    # Pronouns, articles, and the rest.
    "it not sure the them true you",
)

#: Every flagged verb form, lower case.
FLAGGED_FORMS = frozenset(form for family in FLAGGED_VERBS for form in family.split())

#: Every deliberately allowed word, lower case.
ALLOWED_FORMS = frozenset(word for group in ALLOWED_WORDS for word in group.split())

#: A word before the verb form that makes it a noun: "a change nobody made".
DETERMINERS = frozenset(
    (
        "a",
        "an",
        "any",
        "each",
        "every",
        "her",
        "his",
        "its",
        "my",
        "our",
        "some",
        "the",
        "their",
        "whose",
        "your",
    )
)

#: A word after ``no`` that makes it an adverb rather than an object: "no longer".
NOT_OBJECTS = frozenset(("earlier", "faster", "later", "longer", "matter", "slower", "sooner"))

#: A word after ``no`` that takes ``any`` in the rewrite whatever its number.
ANY_BEFORE = frozenset(("further", "less", "more", "other", "such"))

#: The negative's positive counterpart in a rewrite; ``no`` depends on the next word.
POSITIVES = {"nothing": "anything", "nobody": "anybody", "none": "any"}

#: The perfect auxiliaries a past participle is rewritten with.
PERFECT_AUXILIARIES = frozenset(("had", "has", "have"))

_SEPARATOR = r"(?:[ \t]+|[ \t]*\r?\n[ \t]*(?:(?:\#:?|//|\*)[ \t]*)?)"

#: The apostrophes that join a contraction into one word: straight and typographic.
_APOSTROPHES = "'" + chr(0x2019)

# A lookahead, so that every word start is tried and one candidate never hides the next.
_CANDIDATE = re.compile(
    rf"(?<![\w{_APOSTROPHES}])(?=(?P<verb>[A-Za-z]+)"
    + _SEPARATOR
    + rf"(?P<negative>nothing|nobody|none|no)(?![\w{_APOSTROPHES}-]))",
    re.IGNORECASE,
)

_NEXT_WORD = re.compile(_SEPARATOR + r"([A-Za-z]+)")

_PREVIOUS_WORD = re.compile(rf"(?<![\w{_APOSTROPHES}])([A-Za-z]+)" + _SEPARATOR + r"\Z")

_SAME_LINE_MARKER = re.compile(r"wording:ignore(?!-next-line)")

_NEXT_LINE_MARKER = "wording:ignore-next-line"

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
    <rewrite>"``, or is ``None`` for a base form or an ``-ing`` form, whose rewrite
    depends on the words around it.
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
    lines = text.split("\n")
    line_starts = [0]
    for line in lines[:-1]:
        line_starts.append(line_starts[-1] + len(line) + 1)
    hits = []
    for match in _CANDIDATE.finditer(text):
        verb, negative = match["verb"], match["negative"]
        if negative == "None" or verb.lower() not in FLAGGED_FORMS:
            continue
        next_match = _NEXT_WORD.match(text, match.end("negative"))
        next_word = next_match[1] if next_match is not None else None
        is_adverb = next_word is not None and next_word.lower() in NOT_OBJECTS
        if negative.lower() == "no" and is_adverb:
            continue
        verb_start = match.start("verb")
        previous_match = _PREVIOUS_WORD.search(text, max(0, verb_start - 80), verb_start)
        previous = previous_match[1] if previous_match is not None else None
        if previous is not None and previous.lower() in DETERMINERS:
            continue
        first = bisect.bisect_right(line_starts, match.start("verb"))
        last = bisect.bisect_right(line_starts, match.start("negative"))
        if _is_silenced(lines, first, last):
            continue
        hits.append(
            Hit(
                path=path,
                line=first,
                text=" ".join(lines[number - 1].strip() for number in range(first, last + 1)),
                suggestion=_suggestion(verb, negative, next_word=next_word, previous=previous),
            )
        )
    return hits


def _is_silenced(lines: list[str], first: int, last: int) -> bool:
    """Whether a marker covers the phrase on 1-based lines ``first`` to ``last``."""
    for number in range(first, last + 1):
        if _SAME_LINE_MARKER.search(lines[number - 1]) is not None:
            return True
        if number > 1 and _NEXT_LINE_MARKER in lines[number - 2]:
            return True
    return False


def _suggestion(
    verb: str, negative: str, *, next_word: str | None, previous: str | None
) -> str | None:
    """The rewrite of ``verb negative`` with the negation on the verb, if one is simple.

    A third-person present form takes ``doesn't``, a simple past ``didn't``, and a past
    participle after ``has``, ``have``, or ``had`` that auxiliary's negative.  ``no`` is
    rewritten with ``anyone`` before ``one``, ``any`` before a plural or a word in
    ``ANY_BEFORE``, and ``a`` or ``an`` otherwise; the word after ``no`` is shown on both
    sides.  Returns ``None`` for any other form.
    """
    family = _FAMILY_OF[verb.lower()]
    form = verb.lower()
    phrase, positive = _objects(negative, next_word)
    if (
        previous is not None
        and previous.lower() in PERFECT_AUXILIARIES
        and form == family.participle
    ):
        negated = _like(previous, f"{previous.lower()}n't")
        return f"{previous} {verb} {phrase} -> {negated} {form} {positive}"
    if form == family.third:
        auxiliary = "doesn't"
    elif form == family.past and family.past != family.base:
        auxiliary = "didn't"
    else:
        return None
    return f"{verb} {phrase} -> {_like(verb, auxiliary)} {family.base} {positive}"


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


def scan(root: Path, *, paths: Sequence[str] = ()) -> dict[str, list[Hit]]:
    """Return the hits in every scanned file under ``root`` that has any, by path.

    ``paths`` limits the scan to those files and directories (relative to ``root``); an
    empty sequence scans the whole tree.  A file holding a NUL byte, or one that is not
    UTF-8, is skipped as binary.
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
        hits = find_hits(text, path)
        if len(hits) > 0:
            found[path] = hits
    return found


def scanned_files(root: Path) -> list[str]:
    """Every file the check reads under the git checkout at ``root``, sorted.

    Git lists the tracked files and the untracked ones ``.gitignore`` does not exclude,
    under ``SCANNED_PATHS``; the skipped prefixes, files, and suffixes are then dropped,
    as is any path that isn't a regular file (a deleted file or a nested checkout).
    """
    git = shutil.which("git")
    if git is None:
        raise SystemExit("check_wording: git is not installed")
    listing = subprocess.run(  # noqa: S603 - fixed argv, git is a resolved path
        [git, "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", *SCANNED_PATHS],
        cwd=root,
        capture_output=True,
        check=True,
    )
    paths = {path for path in listing.stdout.decode("utf-8").split("\0") if path != ""}
    return sorted(path for path in paths if not _is_skipped(path) and (root / path).is_file())


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
    hits = scan(root, paths=roots)
    if args.all:
        return _list_all(hits)
    counts = {path: len(found) for path, found in hits.items()}
    baseline = read_baseline(root / BASELINE)
    if len(roots) > 0:
        baseline = {path: count for path, count in baseline.items() if _is_under(path, roots)}
    comparison = compare(counts, baseline)
    if args.update_baseline:
        return _update(root, hits, counts, comparison, accept_new=args.accept_new)
    return _report(hits, counts, baseline, comparison)


def _parser() -> argparse.ArgumentParser:
    """The parser for ``--all``, ``--path``, ``--update-baseline``, ``--accept-new``."""
    parser = argparse.ArgumentParser(
        prog="check_wording.py",
        description="Flag a verb whose object is a negative, against a per-file baseline.",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--all", action="store_true", help="list every hit, ignoring the baseline")
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
        help="limit the check or --all to this file or directory (repeatable)",
    )
    return parser


def _list_all(hits: dict[str, list[Hit]]) -> int:
    """Print every hit and a total; 1 when there is any hit, else 0."""
    for path in sorted(hits):
        _print_hits(hits[path])
    total = sum(len(found) for found in hits.values())
    _out(f"{_plural(total, 'hit')} in {_plural(len(hits), 'file')}\n")
    return 1 if total > 0 else 0


def _update(
    root: Path,
    hits: dict[str, list[Hit]],
    counts: dict[str, int],
    comparison: Comparison,
    *,
    accept_new: bool,
) -> int:
    """Write ``counts`` as the baseline; without ``accept_new``, refuse a raised count."""
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
