#!/usr/bin/env python3
"""Flag a negative object or a negative relative clause, and fail on any hit.

The project's prose rule puts a negation on the verb, never on its object, its
complement, or the object of a preposition: write "doesn't have a portal account",
"didn't take anything", "there isn't a payment", or "without a term", or a plain finding
such as "No payment found".  A negative subject reads naturally ("Nobody changes their
own roles", "Nothing is due") and is never flagged, except as the subject of a relative
clause hung off a noun, with or without "that" or "which", which reads as a puzzle: write
"a future date", "an unknown id", "a signed-out caller", "a corporate name not used by
anybody", or a few short sentences (``find_relative_clauses``, in
``scripts/wording_relative.py``).  After a verb of telling and its object, a negative
subject needs a "that": "tells the member that nothing is due".

A hit is a flagged word followed by ``no``, ``nothing``, ``nobody``, ``none``, ``no
one``, or ``nobody's`` or ``no one's`` as a determiner (``nobody's role``).  The
flagged words are every form in ``FLAGGED_VERBS`` (past participles such as ``given``
and ``sent`` included, after a form of "be" too), every word in ``FLAGGED_WORDS``
(the forms of "be" and the prepositions), a contraction of "be" or "have" in
``CONTRACTIONS`` (``there's``, ``we're``, ``you've``, ``they'd``), and any other word
ending in ``-ed`` (a past tense) outside ``ALLOWED_WORDS`` and ``NOT_PAST_TENSE``.  One
pronoun from ``PRONOUNS`` (an indirect object) or one adverb from ``ADVERBS`` may stand
between the two; a noun there (an indirect object such as "a donor") is a known gap.
The words are separated by a single space or tab, so a table's padding never joins two
cells; by one line break, after which the continuation may open with a comment leader
(``#``, ``#:``, ``//``, or ``*``), so a phrase wrapped in a docstring or a comment is
still found; or by the join between two string literals (a closing quote, an optional
``+``, an optional line break, and an opening quote), so a message split across literals
is read whole.  Bold or italic markup (``**``, ``*``, ``<b>``, ``<strong>``, ``<em>``,
or ``<i>``) around a word or the phrase counts as part of the space between words; an
inline literal (````none````) is a value, and never matches.  The match ignores case.
An underscore or a letter joins words into an identifier, so ``has_no_term`` and
``hasNoTerm`` never match, and an apostrophe between letters joins a contraction
("doesn't") into one word.  A quote that opens or closes a string literal, straight or
typographic, belongs to neither word beside it, so a phrase at the start or the end of a
literal (``it('offers ... reset')``, a docstring's opening quotes) is checked like any
other.  These are passed over:

* a negative that is a value or an answer: ``None`` spelled that way (Python's value),
  an all-caps negative after a verb that isn't all caps (``NONE``), a capitalized
  negative after a lower-case verb, followed by a lower-case word or none (a quoted
  message: "reads No insurance on file"), and ``no`` with punctuation right after it
  ("the member said no.");
* a negative that is the subject of a clause of its own: ``nothing``, ``nobody``,
  ``none``, or ``no one`` (past an ``else``) before a word in ``SUBJECT_AUXILIARIES``
  ("says nobody is signed in"), ``nothing`` or ``none`` before a word in
  ``SUBJECT_VERBS`` ("says nothing needs fixing"), and ``nobody's`` or ``no one's``
  meaning "nobody is" or "nobody has" ("says nobody's signed in");
* a verb form preceded by a determiner (``a``, ``the``, ``every``, ...), which makes it a
  noun (the "change" in "a change"), whose negative is then read as the subject of a
  relative clause;
* ``no`` followed by a word in ``NOT_OBJECTS`` (``longer``, ``matter``, ``later``,
  ``deeper``, ...), which makes it an adverb rather than an object;
* a line that carries the marker ``wording:ignore`` (in whatever comment the file type
  allows), and the line after one that carries ``wording:ignore-next-line``.  In
  reStructuredText, where a comment cannot end a line of prose, a comment line holding
  only ``.. wording:ignore-next-line``, followed by a blank line, covers the whole next
  paragraph.  Keep the markers for text that must stay verbatim, such as a third party's
  error message.

The word lists (``FLAGGED_VERBS``, ``ALLOWED_WORDS``, ``FLAGGED_WORDS``, and the small
tables beside them) live in ``scripts/wording_words.py``, and the way the check reads
text (the space between words, word boundaries, lines, markers, and ``Hit``) in
``scripts/wording_text.py``; this script imports both, and the relative-clause check,
from its own directory.

The scanned tree is the one ``make lint-spelling`` scans, as git lists it (tracked files,
plus untracked files ``.gitignore`` does not exclude), minus generated files, lock files,
and binaries.  Hits in the generated OpenAPI files are reported at their source, the
serializer and view docstrings.

A negative relative clause is a hit too: a determiner from ``RELATIVE_DETERMINERS``, at
most one adjective, and a noun, followed by ``no``, ``nothing``, ``nobody``, ``none``, or
``no one`` as the subject of a verb, such as "an id" followed by "no row has", or "a
claim" followed by "nobody finished".  The verb is a form of "be", a modal, a perfect
auxiliary, a listed verb's third-person, past, or participle form, a listed base form
after a plural noun, or an unlisted ``-ed`` word, and after a negative pronoun an
unlisted word ending in a single ``s`` ("awaits"), as it is after ``no`` and a singular
noun ("no account stands").  ``no`` may take up to three nouns before the verb ("no
active plan"), and the words in ``RELATIVE_FILLERS`` may stand between the negative and
the verb (``else``, ``ever``, and the adverbs).  A plural noun without a determiner, or
an indefinite pronoun such as ``everything``, may lead the clause too ("Types" followed
by "nobody may turn off"), unless it is a listed verb form, an unlisted ``-ed`` word, a
word in ``NOT_BARE_NOUNS`` (an unlisted verb such as ``decides``, or an adverb such as
``sometimes``), an ``-ly`` adverb, a word ending in ``ss`` or ``us``, or a word after a
subject pronoun ("As it stands" before a negative subject).

A full relative clause is a hit the same way: a noun followed by ``that``, ``which``,
``who``, or ``whom`` (or by a preposition and ``which`` or ``whom``), or a comma followed
by ``which``, ``who``, or ``whom`` after any word, then the negative subject and its
verb: "a corporate name" followed by "that nobody uses", or "Operational email," followed
by "which nobody may turn off".  The noun is read as above, after a determiner, or as a
bare noun without one.  Before ``that`` only, a noun after "so" or "such" ("so slow
that nobody waits"), a person after a verb of telling, and a noun from ``CONTENT_NOUNS``
whose clause goes on past its verb ("the note that nothing listens on port 25") are
passed over; a content noun's clause that stops at its verb has left the verb's object
out, and is a hit ("a note" followed by "that nobody else sees").  "who", "which", and
"whom" are never passed over after a verb of telling.

A verb of telling (``TELLING_VERBS``, in any form, or a verb in ``TELLING_TO_VERBS`` and
"to": "explain to"), a person as its object (a pronoun from ``PERSON_PRONOUNS``, or a
noun from ``PERSON_NOUNS`` after a determiner and at most one adjective, or bare), and a
negative subject with its verb is a hit too, whose suggestion puts "that" after the
object: "tells the caller" followed by "nothing changed".  "show" isn't a verb of
telling, and a verb of telling whose object is a thing hangs a relative clause off the
thing ("tells the story" followed by "nobody knows"), which is reported as one.

These are passed over:

* a word in ``NOT_OBJECTS`` after ``no``: "the link" followed by "no longer works";
* a noun that is a word opening a clause (``when``, ``and``, ...), a preposition, a form
  of "be" or "have", a pronoun, or another determiner, or that is a verb: a past form, or
  a third-person form after an adjective, as in "the page says nothing is hidden", or a
  verb of telling before ``that``;
* a noun from ``ADVERBIAL_NOUNS`` after any determiner but ``a`` or ``an``, which says
  when, how, or why, in a phrase that opens a sentence or a clause, or follows a comma or
  a preposition: "That way nothing is lost", "The day nothing is due".  As a verb's
  object the noun takes a relative clause like any other ("logs the reason" followed by
  "nobody gave");
* a negative that is a value or a quoted label: ``None``, an all-caps negative after a
  noun that isn't all caps, or a capitalized negative after a lower-case noun;
* a noun phrase that follows a preposition, where the preposition opens the text, a
  paragraph, a list item, or a comment, or follows a character that ends a sentence or
  opens a quote, an opening bracket or a colon when the preposition is capitalized, a word
  that opens a clause, or a coordinating conjunction after a comma: "On any failure
  nothing is written" leads in to a clause of its own, and so does a two-word preposition
  from ``COMPOUND_PREPOSITION_HEADS`` ("Thanks to the lock").  After a comma, a dash, or a
  bracket, or a conjunction without a comma, the phrase is read as part of the clause
  before it ("blank, for a category ...").

Run without a switch, the check prints every hit as ``path:line: text``, with a suggested
rewrite below it where the rewrite is simple, then the total and the remedy, and exits 1.
It exits 0 when it doesn't find a hit.  A relative clause is reported on the line its
determiner (or its noun, or the word before its comma) is on, once, with the suggestion
"rewrite as an adjective or 'that doesn't ...'", or for a full one "say it plainly (an
adjective, or 'not <verb>ed by anybody') or in short sentences".  A telling verb's hit is
reported on the verb's line.

Usage::

    scripts/check_wording.py [--path PATH]        fail on any hit
    scripts/check_wording.py --coordinated [--path PATH]
                                                  list "and/or/but no" for review

``--path`` (repeatable) limits the check, or ``--coordinated``, to a file or a subtree.

Known gaps, reviewed by hand:

* a noun between the verb and the negative (an indirect object such as "a donor");
* a coordinated object after ``and``, ``or``, or ``but`` ("gets 400 and" followed by a
  negative), which the rule covers but the check can't tell from a new negative subject;
  ``--coordinated`` lists every such candidate and always exits 0;
* text inside a literal or code-block body, which a marker can't reach without showing
  in the rendered page;
* ``nobody's`` before an ``-ing`` form, an ``-ed`` word, or a participle spelled like its
  base or its past, which is read from the one word after the participle: a noun there
  reads as a possessive, so a contraction with a noun object is flagged, and a
  preposition there reads as a contraction, so a possessive noun before one is missed;
* a contracted ``'s`` or ``'d``, read as "is" or "had", so a possessive before a
  negative is flagged as a contraction;
* a join between two string literals with a typographic quote or a backtick, which
  isn't read;
* a relative clause after a preposition that leads off a sentence, which is read as a
  lead-in, so "For a type" followed by "nobody may turn off" is passed over; one whose
  noun has two adjectives or a possessive; one whose subject is ``nobody's``; one after a
  bare noun that is also a listed verb form ("limits" followed by "that nobody
  recorded"), or after a bracket that stands between the noun and ``that``; a content
  noun whose clause leaves its verb's object out without stopping there ("a note that"
  followed by "nobody reads in time"); a person missing from ``PERSON_NOUNS``; and a
  verb of telling whose object is a name or has two adjectives.
"""

import argparse
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import NamedTuple

from wording_relative import find_relative_clauses
from wording_text import (
    ALLOWED_FORMS,
    APOSTROPHES,
    CONTRACTION,
    FAMILY_OF,
    GAP,
    NEXT_WORD,
    PREPOSITION_FORMS,
    PREVIOUS_WORD,
    SEPARATOR,
    SUBJECT_AUXILIARIES,
    WORD_END,
    WORD_START,
    Hit,
    read_lines,
)
from wording_words import (
    ADVERBS,
    ANY_BEFORE,
    BE_FORMS,
    BOUNDS,
    CONTRACTED_AUXILIARIES,
    CONTRACTIONS,
    DETERMINERS,
    FLAGGED_VERBS,
    FLAGGED_WORDS,
    MODALS,
    NEGATED_WORDS,
    NOT_OBJECTS,
    NOT_PAST_TENSE,
    PARTICLES,
    PERFECT_AUXILIARIES,
    POSITIVES,
    PREPOSITIONS,
    PRONOUNS,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

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

#: A word after a negative that makes the negative a subject, once a pronoun stands
#: before it ("bet you nobody is coming"): a verb form, a form of "be", or a modal.
#: After a verb of telling ("tell them" and a negative subject), the missing "that" is a
#: hit of its own (``wording_relative``).
CLAUSE_VERBS = frozenset(
    [form for family in FLAGGED_VERBS for form in family.split()]
    + BE_FORMS.split()
    + MODALS.split()
)

#: A third-person present verb, which does the same after ``nothing`` or ``none`` alone
#: ("says nothing else needs fixing").  After ``nobody`` or ``no one`` the same word is
#: as often a plural noun after an indirect object (a verb, the negative, "emails"), so
#: it is flagged there.
SUBJECT_VERBS = frozenset(family.split()[1] for family in FLAGGED_VERBS)

#: The words after the participle in ``nobody's <participle>`` that make the ``'s`` "is"
#: or "has": a particle, a preposition, a pronoun, an adverb, or a determiner.
PARTICLE_FORMS = (
    PARTICLES
    | frozenset(word for group in PREPOSITIONS for word in group.split())
    | frozenset(PRONOUNS + ADVERBS)
    | DETERMINERS
)

#: A word after ``nobody's`` or ``no one's`` that makes the ``'s`` a contraction of "is"
#: or "has" ("nobody's here", "nobody's been charged"), not a possessive.  A past
#: participle, an ``-ing`` form, or an unlisted ``-ed`` word does the same.
CONTRACTION_COMPLEMENTS = frozenset((*BE_FORMS.split(), "here", "there"))

#: A character right after ``no`` that makes it an answer rather than a determiner:
#: "the member said no."
ANSWER_ENDINGS = frozenset(".,;:!?)]}\"'" + chr(0x2019) + chr(0x201D))

# A lookahead, so that every word start is tried and one candidate never hides the next.
_CANDIDATE = re.compile(
    WORD_START
    + rf"(?=(?P<verb>[A-Za-z]+(?:{CONTRACTION})?)"
    + GAP
    + rf"(?:(?P<middle>{'|'.join(PRONOUNS + ADVERBS)})"
    + GAP
    + ")?"
    + rf"(?P<negative>nobody[{APOSTROPHES}]s|no{SEPARATOR}one[{APOSTROPHES}]s"
    + r"|nothing|nobody|none|no)"
    + WORD_END
    + ")",
    re.IGNORECASE,
)

_THAN = re.compile(GAP + r"[A-Za-z]+" + GAP + r"than\b", re.IGNORECASE)

# A coordinating conjunction before a negative: "gets 400 and no message".  The rule
# covers a coordinated object, but the check can't tell one from a new negative subject
# ("and no email is sent"), so ``--coordinated`` only lists these for review by hand.
_COORDINATED = re.compile(
    WORD_START
    + r"(?=(?P<verb>and|but|or)"
    + SEPARATOR
    + r"(?P<negative>nothing|nobody|none|no)"
    + WORD_END
    + ")",
    re.IGNORECASE,
)

#: The family whose forms make a passive before a past participle: "gets paid".
_GET = FAMILY_OF["get"]

#: The forms of "be" that leave a past participle's rewrite to the reader: "has been
#: sent" moves the negation to ``has``, which the check doesn't see.
_UNNEGATED_BE = frozenset(("be", "been", "being"))


def find_hits(text: str, path: str) -> list[Hit]:
    """Return every hit in ``text``, the contents of the file at ``path``, in order.

    ``path`` is only recorded on each hit.  The hits are the negative objects and the
    negative relative clauses, sorted by line.  See the module docstring for what is
    flagged and what is passed over.
    """
    hits = _find(text, path, coordinated=False) + find_relative_clauses(text, path)
    return sorted(hits, key=lambda hit: hit.line)


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
    index = read_lines(text)
    hits = []
    for match in (_COORDINATED if coordinated else _CANDIDATE).finditer(text):
        verb, negative = match["verb"], match["negative"]
        middle = None if coordinated else match["middle"]
        if not coordinated and not _is_flagged(verb):
            continue
        next_match = NEXT_WORD.match(text, match.end("negative"))
        next_word = next_match[1] if next_match is not None else None
        if _is_not_an_object(text, match, next_word):
            continue
        is_adverb = next_word is not None and next_word.lower() in NOT_OBJECTS
        if negative.lower() == "no" and is_adverb:
            continue
        if middle is not None and _starts_a_clause(verb, middle, next_word):
            continue
        is_after_a_preposition = verb.lower() in PREPOSITION_FORMS
        if not is_after_a_preposition and _is_a_subject(text, match, next_word):
            continue
        verb_start = match.start("verb")
        previous_match = PREVIOUS_WORD.search(text, max(0, verb_start - 80), verb_start)
        previous = previous_match[1] if previous_match is not None else None
        if previous is not None and previous.lower() in DETERMINERS:
            continue
        phrase = _Phrase(
            verb,
            middle,
            negative,
            next_word=next_word,
            previous=previous,
            is_bound=_THAN.match(text, match.end("negative")) is not None,
        )
        span = (verb_start, match.start("negative"))
        hit = index.hit(path, span, None if coordinated else _suggestion(phrase))
        if hit is not None:
            hits.append(hit)
    return hits


def _starts_a_clause(verb: str, middle: str, next_word: str | None) -> bool:
    """Whether a pronoun between ``verb`` and the negative ends the phrase there.

    A pronoun after a preposition is that preposition's object ("without it nothing
    runs"), and a pronoun followed by a negative and then a verb, a form of "be", or a
    modal is an object whose own clause has a negative subject ("bet you nobody is
    coming"), which ``wording_relative`` reports as a missing "that" after a verb of
    telling.  An adverb in between never ends the phrase.
    """
    if middle.lower() not in PRONOUNS:
        return False
    if verb.lower() in PREPOSITION_FORMS:
        return True
    return next_word is not None and next_word.lower() in CLAUSE_VERBS


def _is_a_subject(text: str, match: re.Match[str], next_word: str | None) -> bool:
    """Whether the matched negative is a subject rather than an object.

    The caller asks only after a word other than a preposition, whose object a negative
    always is, even before a verb.  ``nothing``, ``nobody``, ``none``, or ``no one``
    followed (past an ``else``) by a word in ``SUBJECT_AUXILIARIES`` starts a clause of
    its own ("says nobody is signed in"), and so do ``nothing`` and ``none`` before a
    word in ``SUBJECT_VERBS`` ("says nothing needs fixing").  ``nobody's`` or ``no
    one's`` is a contraction of "is" or "has", never a possessive, by the test
    ``_is_a_contraction`` describes.
    """
    lower = match["negative"].lower()
    words = _words_after(text, match.end("negative"), 3)
    if lower.endswith("s"):
        return _is_a_contraction(words)
    if lower == "no":
        if len(words) == 0 or words[0] != "one":
            return False
        words = words[1:]
    if len(words) > 0 and words[0] == "else":
        words = words[1:]
    if len(words) == 0:
        return False
    if words[0] in SUBJECT_AUXILIARIES:
        return True
    return lower in ("nothing", "none") and words[0] in SUBJECT_VERBS


def _is_a_contraction(words: list[str]) -> bool:
    """Whether the ``words`` after ``nobody's`` make the ``'s`` mean "is" or "has".

    The first word does when it is in ``CONTRACTION_COMPLEMENTS`` ("nobody's here") or a
    past participle spelled unlike its base form and its past ("nobody's given").  An
    ``-ing`` form, an ``-ed`` word, or a participle spelled like its base or its past
    does when nothing follows it, or a word in ``PARTICLE_FORMS`` does ("nobody's
    signed in", "nobody's set up yet"); a noun after it makes ``nobody's`` a possessive
    ("nobody's billing address").
    """
    if len(words) == 0:
        return False
    first = words[0]
    if first in CONTRACTION_COMPLEMENTS:
        return True
    family = FAMILY_OF.get(first)
    is_participle = family is not None and first == family.participle
    if is_participle and family is not None and first not in (family.base, family.past):
        return True
    if not (is_participle or first.endswith(("ing", "ed"))):
        return False
    return len(words) == 1 or words[1] in PARTICLE_FORMS


def _words_after(text: str, end: int, count: int) -> list[str]:
    """Up to ``count`` lower-case words after ``end``, with only separators between."""
    words: list[str] = []
    position = end
    while len(words) < count:
        found = NEXT_WORD.match(text, position)
        if found is None:
            break
        words.append(found[1].lower())
        position = found.end()
    return words


def _is_flagged(word: str) -> bool:
    """Whether ``word`` is a listed form, a contraction, or an unlisted past tense."""
    lower = word.lower()
    if _contraction(lower) is not None or lower in FLAGGED_FORMS:
        return True
    return lower.endswith("ed") and lower not in ALLOWED_FORMS and lower not in NOT_PAST_TENSE


def _contraction(word: str) -> tuple[str, str] | None:
    """``word`` split into its base and its contracted ending, if it is a contraction."""
    for apostrophe in APOSTROPHES:
        if apostrophe in word:
            base, ending = word.split(apostrophe, 1)
            return (base, ending) if ending in CONTRACTIONS else None
    return None


def _is_not_an_object(text: str, match: re.Match[str], next_word: str | None) -> bool:
    """Whether the matched negative is a value or an answer rather than an object.

    That is ``None`` spelled that way (Python's value), an all-caps negative after a verb
    that isn't all caps (``NONE``, a constant), a capitalized negative after a lower-case
    verb with a lower-case word or none after it (a quoted label or message: "reads No
    insurance on file"), and ``no`` with punctuation right after it ("said no.").  A
    capitalized word after the negative reads as a title, which is flagged.
    """
    verb, negative = match["verb"], match["negative"]
    if negative == "None":
        return True
    if negative.isupper() and not verb.isupper():
        return True
    is_lower_after = next_word is None or next_word[0].islower()
    if negative[0].isupper() and verb[0].islower() and is_lower_after:
        return True
    end = match.end("negative")
    is_answer = end < len(text) and text[end] in ANSWER_ENDINGS
    return negative.lower() == "no" and is_answer


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
    participle after an auxiliary that auxiliary's negative: ``has``, ``have``, and
    ``had`` (``hasn't sent``), ``is``, ``are``, ``was``, ``were``, and ``am`` (``isn't
    sent``), and ``get``, ``gets``, and ``got`` (``doesn't get paid``).  A word in
    ``NEGATED_WORDS`` takes its negated form (``is`` -> ``isn't``, ``with`` ->
    ``without``); a pronoun before the negative stays where it is.  ``no`` is rewritten
    with ``anyone`` before ``one``, ``any`` before a plural or a word in ``ANY_BEFORE``,
    and ``a`` or ``an`` otherwise; the word after ``no`` is shown on both sides, and
    ``nobody's`` or ``no one's`` becomes ``anybody's`` or ``anyone's``.  A bound keeps
    its meaning without the negative: ``no more than`` becomes ``at most``, and ``no
    fewer than`` or ``no less than`` becomes ``at least``, after any flagged word.
    Returns ``None`` for any other word or form, for a past participle after ``be``,
    ``been``, or ``being``, and for a phrase with an adverb in it.
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
    contraction = _contraction(form)
    if contraction is not None:
        base, ending = contraction
        return f"{verb} {objects} -> {_like(verb, base)} {CONTRACTIONS[ending]} {positive}"
    if form not in FAMILY_OF:
        return None
    family = FAMILY_OF[form]
    if previous is not None and form == family.participle:
        lead = previous.lower()
        if lead in _UNNEGATED_BE:
            return None
        negated = _negated_auxiliary(lead)
        if negated is not None:
            return f"{previous} {verb} {objects} -> {_like(previous, negated)} {form} {positive}"
    if form == family.third:
        auxiliary = "doesn't"
    elif form == family.past and family.past != family.base:
        auxiliary = "didn't"
    else:
        return None
    return f"{verb} {objects} -> {_like(verb, auxiliary)} {family.base} {positive}"


def _negated_auxiliary(word: str) -> str | None:
    """The negative of ``word`` as an auxiliary before a past participle, if it is one."""
    contraction = _contraction(word)
    if contraction is not None:
        return f"{contraction[0]} {CONTRACTED_AUXILIARIES[contraction[1]]}"
    if word in PERFECT_AUXILIARIES:
        return f"{word}n't"
    if word in BE_FORMS.split() and word in NEGATED_WORDS:
        return NEGATED_WORDS[word]
    if word == _GET.third:
        return f"doesn't {_GET.base}"
    if word == _GET.past:
        return f"didn't {_GET.base}"
    if word == _GET.base:
        return f"don't {_GET.base}"
    return None


def _objects(negative: str, next_word: str | None) -> tuple[str, str]:
    """The negative object as written, and its positive rewrite."""
    lower = negative.lower()
    if lower in POSITIVES:
        return negative, POSITIVES[lower]
    if lower.endswith("s"):
        return _possessive(negative, next_word)
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


def _possessive(negative: str, next_word: str | None) -> tuple[str, str]:
    """``nobody's`` or ``no one's`` as written, with the word after it, and its rewrite.

    A line break inside ``no one's`` is written as a space.
    """
    ending = negative[-2:]
    if negative.lower().startswith("nobody"):
        written, positive = negative, f"anybody{ending}"
    else:
        written, positive = f"{negative[:2]} one{ending}", f"anyone{ending}"
    if next_word is None:
        return written, positive
    return f"{written} {next_word}", f"{positive} {next_word}"


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


def main(argv: Sequence[str] | None = None, *, root: Path = REPO_ROOT) -> int:
    """Run the check against the tree at ``root``; return the exit status.

    ``argv`` defaults to the command line.  An invalid switch exits 2 through
    ``argparse``.
    """
    args = _parser().parse_args(argv)
    roots = [path.strip("/").removeprefix("./") for path in args.path]
    if args.coordinated:
        return _list_coordinated(scan(root, paths=roots, finder=find_coordinated))
    return _report(scan(root, paths=roots))


def _parser() -> argparse.ArgumentParser:
    """The parser for the switches the module docstring lists."""
    parser = argparse.ArgumentParser(
        prog="check_wording.py",
        description="Flag a verb whose object is a negative.",
    )
    parser.add_argument(
        "--coordinated",
        action="store_true",
        help="list every 'and', 'or', or 'but' before a negative, for review by hand",
    )
    parser.add_argument(
        "--path",
        action="append",
        default=[],
        metavar="PATH",
        help="limit the check or --coordinated to this file or directory (repeatable)",
    )
    return parser


def _report(hits: dict[str, list[Hit]]) -> int:
    """Print every hit and a total, with the remedy; 1 when there is any hit, else 0."""
    for path in sorted(hits):
        _print_hits(hits[path])
    total = sum(len(found) for found in hits.values())
    if total == 0:
        _out("Wording check passed.\n")
        return 0
    _out(
        f"{_plural(total, 'hit')} in {_plural(len(hits), 'file')}.  Put the negation on the "
        "verb, or rewrite a negative relative clause, as each suggestion shows, or end a "
        "line that must stay verbatim with a wording:ignore comment.\n"
    )
    return 1


def _list_coordinated(candidates: dict[str, list[Hit]]) -> int:
    """Print every conjunction candidate and a total; always 0, since none is a hit."""
    for path in sorted(candidates):
        _print_hits(candidates[path])
    total = sum(len(found) for found in candidates.values())
    _out(f"{_plural(total, 'candidate')} in {_plural(len(candidates), 'file')}\n")
    return 0


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
