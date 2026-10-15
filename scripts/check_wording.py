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

``--update-baseline`` refuses (exit 1) to raise a count or add a file unless
``--accept-new`` is given.  It writes tracked files only: a file git doesn't track yet is
left out with a warning, so a scratch file never lands in the baseline.  Renaming a file
that has hits moves its count to a path the baseline doesn't list, so the rename needs
``--update-baseline --accept-new``, and a review of the baseline's diff to confirm that
the old path's count moved to the new one unchanged.  ``--all`` exits 1 when it lists a
hit, so it confirms that an area is clean; ``--path`` (repeatable) limits ``--all`` or the
check to a subtree, and is refused with ``--update-baseline``, since the baseline covers
the whole tree.
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

# The verbs the check flags, one family per string: base form, third person singular,
# simple past, past participle, and present participle.  The list was built by
# extracting every word that precedes ``no``, ``nothing``, ``nobody``, or ``none`` in the
# scanned tree and keeping each one that can act as a verb (possession or action), with
# its other forms, plus common verbs the tree doesn't use yet; an unlisted ``-ed`` word is
# flagged too (see ``NOT_PAST_TENSE``).  A word that is also a
# noun ("changes", "records", "names") is flagged anyway: a determiner before it already
# marks the plain noun use, and a rewrite costs less than a missed hit.  Linking verbs
# are flagged only where the phrase reads as a negative object, as "becomes" can.
# A table of short strings, packed several to a line; the formatter would give each its
# own line and more than double the module's length.
# fmt: off
FLAGGED_VERBS = (
    "accept accepts accepted accepted accepting",
    "accompany accompanies accompanied accompanied accompanying",
    "accrue accrues accrued accrued accruing", "activate activates activated activated activating",
    "add adds added added adding", "affect affects affected affected affecting",
    "alert alerts alerted alerted alerting", "allow allows allowed allowed allowing",
    "alter alters altered altered altering", "answer answers answered answered answering",
    "apply applies applied applied applying", "approve approves approved approved approving",
    "ask asks asked asked asking", "assert asserts asserted asserted asserting",
    "assign assigns assigned assigned assigning", "assume assumes assumed assumed assuming",
    "attach attaches attached attached attaching", "award awards awarded awarded awarding",
    "bear bears bore borne bearing", "become becomes became become becoming",
    "bill bills billed billed billing", "bind binds bound bound binding",
    "block blocks blocked blocked blocking", "break breaks broke broken breaking",
    "bring brings brought brought bringing", "build builds built built building",
    "buy buys bought bought buying", "call calls called called calling",
    "cancel cancels canceled canceled canceling", "cap caps capped capped capping",
    "capture captures captured captured capturing", "carry carries carried carried carrying",
    "catch catches caught caught catching", "cause causes caused caused causing",
    "change changes changed changed changing", "charge charges charged charged charging",
    "check checks checked checked checking", "choose chooses chose chosen choosing",
    "cite cites cited cited citing", "claim claims claimed claimed claiming",
    "clear clears cleared cleared clearing", "close closes closed closed closing",
    "collect collects collected collected collecting",
    "commit commits committed committed committing",
    "configure configures configured configured configuring",
    "confirm confirms confirmed confirmed confirming",
    "connect connects connected connected connecting",
    "consume consumes consumed consumed consuming",
    "contact contacts contacted contacted contacting",
    "contain contains contained contained containing",
    "contribute contributes contributed contributed contributing",
    "control controls controlled controlled controlling",
    "convert converts converted converted converting", "copy copies copied copied copying",
    "cost costs cost cost costing", "count counts counted counted counting",
    "cover covers covered covered covering", "create creates created created creating",
    "declare declares declared declared declaring", "decline declines declined declined declining",
    "define defines defined defined defining", "delete deletes deleted deleted deleting",
    "deliver delivers delivered delivered delivering", "deny denies denied denied denying",
    "deploy deploys deployed deployed deploying",
    "describe describes described described describing",
    "detect detects detected detected detecting", "disable disables disabled disabled disabling",
    "display displays displayed displayed displaying", "do does did done doing",
    "document documents documented documented documenting", "draw draws drew drawn drawing",
    "drop drops dropped dropped dropping",
    "duplicate duplicates duplicated duplicated duplicating", "earn earns earned earned earning",
    "edit edits edited edited editing", "email emails emailed emailed emailing",
    "emit emits emitted emitted emitting", "enable enables enabled enabled enabling",
    "encode encodes encoded encoded encoding", "end ends ended ended ending",
    "enforce enforces enforced enforced enforcing", "enter enters entered entered entering",
    "exclude excludes excluded excluded excluding", "execute executes executed executed executing",
    "exempt exempts exempted exempted exempting", "exist exists existed existed existing",
    "expand expands expanded expanded expanding", "expect expects expected expected expecting",
    "expire expires expired expired expiring", "export exports exported exported exporting",
    "expose exposes exposed exposed exposing", "extend extends extended extended extending",
    "fail fails failed failed failing", "fetch fetches fetched fetched fetching",
    "file files filed filed filing", "fill fills filled filled filling",
    "filter filters filtered filtered filtering", "find finds found found finding",
    "finish finishes finished finished finishing", "fire fires fired fired firing",
    "fit fits fitted fitted fitting", "flag flags flagged flagged flagging",
    "flip flips flipped flipped flipping", "fly flies flew flown flying",
    "follow follows followed followed following",
    "forward forwards forwarded forwarded forwarding",
    "gather gathers gathered gathered gathering",
    "generate generates generated generated generating", "get gets got gotten getting",
    "give gives gave given giving", "go goes went gone going",
    "grant grants granted granted granting", "handle handles handled handled handling",
    "have has had had having", "hear hears heard heard hearing",
    "help helps helped helped helping", "hide hides hid hidden hiding", "hit hits hit hit hitting",
    "hold holds held held holding", "host hosts hosted hosted hosting",
    "identify identifies identified identified identifying",
    "ignore ignores ignored ignored ignoring", "imply implies implied implied implying",
    "import imports imported imported importing", "impose imposes imposed imposed imposing",
    "include includes included included including", "incur incurs incurred incurred incurring",
    "infer infers inferred inferred inferring", "inherit inherits inherited inherited inheriting",
    "inject injects injected injected injecting",
    "install installs installed installed installing", "invite invites invited invited inviting",
    "involve involves involved involved involving", "issue issues issued issued issuing",
    "join joins joined joined joining", "keep keeps kept kept keeping",
    "kill kills killed killed killing", "know knows knew known knowing",
    "launch launches launched launched launching", "lay lays laid laid laying",
    "lead leads led led leading", "learn learns learned learned learning",
    "leave leaves left left leaving", "lend lends lent lent lending", "let lets let let letting",
    "lift lifts lifted lifted lifting", "limit limits limited limited limiting",
    "link links linked linked linking", "list lists listed listed listing",
    "load loads loaded loaded loading", "lock locks locked locked locking",
    "log logs logged logged logging", "look looks looked looked looking",
    "lose loses lost lost losing", "mail mails mailed mailed mailing",
    "make makes made made making", "manage manages managed managed managing",
    "mark marks marked marked marking", "match matches matched matched matching",
    "mean means meant meant meaning", "mention mentions mentioned mentioned mentioning",
    "modify modifies modified modified modifying", "mount mounts mounted mounted mounting",
    "move moves moved moved moving", "name names named named naming",
    "narrow narrows narrowed narrowed narrowing", "need needs needed needed needing",
    "notify notifies notified notified notifying", "obtain obtains obtained obtained obtaining",
    "occupy occupies occupied occupied occupying", "offer offers offered offered offering",
    "omit omits omitted omitted omitting", "open opens opened opened opening",
    "orchestrate orchestrates orchestrated orchestrated orchestrating",
    "order orders ordered ordered ordering", "outlive outlives outlived outlived outliving",
    "owe owes owed owed owing", "own owns owned owned owning",
    "paint paints painted painted painting", "parse parses parsed parsed parsing",
    "pass passes passed passed passing", "pay pays paid paid paying",
    "perform performs performed performed performing",
    "permit permits permitted permitted permitting", "pick picks picked picked picking",
    "pin pins pinned pinned pinning", "pipe pipes piped piped piping",
    "place places placed placed placing", "play plays played played playing",
    "pose poses posed posed posing", "post posts posted posted posting",
    "preserve preserves preserved preserved preserving",
    "prevent prevents prevented prevented preventing", "print prints printed printed printing",
    "process processes processed processed processing",
    "produce produces produced produced producing", "promise promises promised promised promising",
    "protect protects protected protected protecting", "prove proves proved proven proving",
    "provide provides provided provided providing",
    "publish publishes published published publishing", "pull pulls pulled pulled pulling",
    "push pushes pushed pushed pushing", "put puts put put putting",
    "queue queues queued queued queuing", "raise raises raised raised raising",
    "reach reaches reached reached reaching",
    "reactivate reactivates reactivated reactivated reactivating", "read reads read read reading",
    "receive receives received received receiving",
    "recognize recognizes recognized recognized recognizing",
    "record records recorded recorded recording",
    "redirect redirects redirected redirected redirecting",
    "reference references referenced referenced referencing",
    "refund refunds refunded refunded refunding", "refuse refuses refused refused refusing",
    "register registers registered registered registering",
    "reject rejects rejected rejected rejecting", "release releases released released releasing",
    "remain remains remained remained remaining", "remind reminds reminded reminded reminding",
    "remove removes removed removed removing", "render renders rendered rendered rendering",
    "renew renews renewed renewed renewing", "repeat repeats repeated repeated repeating",
    "replace replaces replaced replaced replacing", "report reports reported reported reporting",
    "request requests requested requested requesting",
    "require requires required required requiring",
    "resemble resembles resembled resembled resembling",
    "reserve reserves reserved reserved reserving", "reset resets reset reset resetting",
    "resolve resolves resolved resolved resolving",
    "respect respects respected respected respecting",
    "restore restores restored restored restoring",
    "restrict restricts restricted restricted restricting",
    "retain retains retained retained retaining", "retry retries retried retried retrying",
    "return returns returned returned returning", "reveal reveals revealed revealed revealing",
    "revoke revokes revoked revoked revoking", "rewrite rewrites rewrote rewritten rewriting",
    "run runs ran run running", "satisfy satisfies satisfied satisfied satisfying",
    "save saves saved saved saving", "say says said said saying",
    "schedule schedules scheduled scheduled scheduling",
    "search searches searched searched searching", "see sees saw seen seeing",
    "seed seeds seeded seeded seeding", "seek seeks sought sought seeking",
    "seem seems seemed seemed seeming", "select selects selected selected selecting",
    "sell sells sold sold selling", "send sends sent sent sending",
    "serve serves served served serving", "set sets set set setting",
    "settle settles settled settled settling", "share shares shared shared sharing",
    "ship ships shipped shipped shipping", "show shows showed shown showing",
    "sign signs signed signed signing", "signal signals signaled signaled signaling",
    "skip skips skipped skipped skipping", "spawn spawns spawned spawned spawning",
    "specify specifies specified specified specifying", "spend spends spent spent spending",
    "stack stacks stacked stacked stacking", "stamp stamps stamped stamped stamping",
    "start starts started started starting", "stay stays stayed stayed staying",
    "store stores stored stored storing", "strip strips stripped stripped stripping",
    "submit submits submitted submitted submitting",
    "suggest suggests suggested suggested suggesting",
    "supply supplies supplied supplied supplying",
    "support supports supported supported supporting",
    "surface surfaces surfaced surfaced surfacing", "tag tags tagged tagged tagging",
    "take takes took taken taking", "tell tells told told telling",
    "terminate terminates terminated terminated terminating", "test tests tested tested testing",
    "throw throws threw thrown throwing", "touch touches touched touched touching",
    "track tracks tracked tracked tracking",
    "transfer transfers transferred transferred transferring",
    "translate translates translated translated translating",
    "treat treats treated treated treating", "trigger triggers triggered triggered triggering",
    "trust trusts trusted trusted trusting",
    "unaffiliate unaffiliates unaffiliated unaffiliated unaffiliating",
    "undo undoes undid undone undoing", "unlock unlocks unlocked unlocked unlocking",
    "unsubscribe unsubscribes unsubscribed unsubscribed unsubscribing",
    "update updates updated updated updating", "upload uploads uploaded uploaded uploading",
    "use uses used used using", "validate validates validated validated validating",
    "verify verifies verified verified verifying", "want wants wanted wanted wanting",
    "warn warns warned warned warning", "work works worked worked working",
    "write writes wrote written writing", "yield yields yielded yielded yielding",
)
# fmt: on

# The words found before a negative that are deliberately left alone, one group per
# string.  Modals ("may no longer") always wait for a verb.  Conjunctions, relative words,
# and adverbs introduce a negative subject ("so no reset email was sent", "when nobody
# is signed in"), which the rule allows.  ``than`` compares with zero ("more than
# nothing").  A pronoun ("it", "them", "you") isn't a verb; the check reads past one to
# the verb before it.  A word in neither tuple is left alone too: this one records the
# decisions.  To flag a word listed here, move it to ``FLAGGED_WORDS``.
ALLOWED_WORDS = (
    # Modals.
    "can could may might must shall should will would",
    # Conjunctions, relative words, and adverbs, which introduce a negative subject.
    "after alone although and because before but deliberately else here if nor once only",
    "or otherwise possibly simply since so that then there though until when where",
    "whereas whether which while who whom why yet",
    # Comparison with zero.
    "than",
    # Pronouns, articles, and the rest.
    "it not sure the them true you",
)

# Words that are not verb families but are flagged all the same, one group per string.
# A form of "be" puts the negation on its complement, and a preposition on its object,
# as these phrases do, one example per line:
#     is no help; there is no payment; were none  # wording:ignore
#     with no term; for no reason; of no use; at no cost; in no case  # wording:ignore
# Write "isn't any help", "there isn't a payment", or "without a term", or move the
# negation to the verb.
FLAGGED_WORDS = (
    # Forms of "be".
    "am are be been being is was were",
    # Prepositions.
    "about against as at by during for from in into like of on onto over per plus",
    "through to toward towards under upon via with within without",
)

#: The negated form a flagged word other than a verb takes in a suggestion.
NEGATED_WORDS = {
    "am": "am not",
    "are": "aren't",
    "is": "isn't",
    "was": "wasn't",
    "were": "weren't",
    "with": "without",
}

# The small word tables below are packed by hand, as ``FLAGGED_VERBS`` is.
# fmt: off

#: A word ending in ``-ed`` reads as a past tense and is flagged even when no family
#: lists it, except these, which only end in the same letters.
NOT_PAST_TENSE = frozenset((
    "bed", "embed", "exceed", "feed", "hundred", "indeed", "proceed", "red", "shed", "speed",
    "succeed",
))

#: The words the check reads past between the verb and the negative: an indirect object
#: ("costs you nothing") or an adverb ("has almost no room").  # wording:ignore
PRONOUNS = ("her", "him", "it", "me", "them", "us", "you")
ADVERBS = (
    "absolutely", "almost", "also", "deliberately", "hardly", "nearly", "practically",
    "really", "simply", "still", "then", "virtually",
)

#: A word before the verb form that makes it a noun: "a change nobody made".
DETERMINERS = frozenset((
    "a", "an", "any", "each", "every", "her", "his", "its", "my", "our", "some", "the",
    "their", "whose", "your",
))

#: A word after ``no`` that makes it an adverb rather than an object: "no longer", "no
#: deeper than".
NOT_OBJECTS = frozenset((
    "bigger", "closer", "deeper", "earlier", "faster", "greater", "higher", "larger", "later",
    "longer", "lower", "matter", "slower", "smaller", "sooner", "wider",
))

# fmt: on

#: Every flagged form, lower case: each verb form, plus ``FLAGGED_WORDS``.
FLAGGED_FORMS = frozenset(
    [form for family in FLAGGED_VERBS for form in family.split()]
    + [word for group in FLAGGED_WORDS for word in group.split()]
)

#: Every deliberately allowed word, lower case.
ALLOWED_FORMS = frozenset(word for group in ALLOWED_WORDS for word in group.split())

#: A character right after ``no`` that makes it an answer rather than a determiner:
#: "the member said no."
ANSWER_ENDINGS = frozenset(".,;:!?)]}\"'" + chr(0x2019) + chr(0x201D))

#: A word after ``no`` that takes ``any`` in the rewrite whatever its number.
ANY_BEFORE = frozenset(("further", "less", "more", "other", "such"))

#: The negative's positive counterpart in a rewrite; ``no`` depends on the next word.
POSITIVES = {"nothing": "anything", "nobody": "anybody", "none": "any"}

#: The perfect auxiliaries a past participle is rewritten with.
PERFECT_AUXILIARIES = frozenset(("had", "has", "have"))

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
    lines = text.split("\n")
    line_starts = [0]
    for line in lines[:-1]:
        line_starts.append(line_starts[-1] + len(line) + 1)
    silenced = _silenced_lines(lines) if _MARKER in text else set()
    hits = []
    for match in _CANDIDATE.finditer(text):
        verb, middle, negative = match["verb"], match["middle"], match["negative"]
        if not _is_flagged(verb) or _is_not_an_object(text, match):
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
        first = bisect.bisect_right(line_starts, verb_start)
        last = bisect.bisect_right(line_starts, match.start("negative"))
        if any(number in silenced for number in range(first, last + 1)):
            continue
        phrase = _Phrase(verb, middle, negative, next_word=next_word, previous=previous)
        hits.append(
            Hit(
                path=path,
                line=first,
                text=" ".join(lines[number - 1].strip() for number in range(first, last + 1)),
                suggestion=_suggestion(phrase),
            )
        )
    return hits


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


def _suggestion(phrase: _Phrase) -> str | None:
    """The rewrite of the phrase with the negation on the verb, if one is simple.

    A third-person present form takes ``doesn't``, a simple past ``didn't``, and a past
    participle after ``has``, ``have``, or ``had`` that auxiliary's negative, and a word
    in ``NEGATED_WORDS`` its negated form (``is`` -> ``isn't``, ``with`` -> ``without``);
    a pronoun before the negative stays where it is.  ``no`` is rewritten with ``anyone``
    before ``one``, ``any`` before a plural or a word in ``ANY_BEFORE``, and ``a`` or
    ``an`` otherwise; the word after ``no`` is shown on both sides.  Returns ``None`` for
    any other word or form, and for a phrase with an adverb in it.
    """
    verb, middle, previous = phrase.verb, phrase.middle, phrase.previous
    form = verb.lower()
    if middle is not None and middle.lower() in ADVERBS:
        return None
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
