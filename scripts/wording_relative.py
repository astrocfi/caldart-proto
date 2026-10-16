"""Flag a negative relative clause hung off a noun: people don't talk that way.

A noun followed by ``no``, ``nothing``, ``nobody``, ``none``, or ``no one`` as the
subject of its own verb, as in "an id" followed by "no row has", reads as a puzzle.
Write a plain adjective or a plain statement ("an unknown id", "a future date", "a
signed-out caller"), or a positive relative clause ("an id that doesn't match a row").
``scripts/check_wording.py`` reports these with its other hits; its module docstring
lists what is flagged and what is passed over.
"""

import re

from wording_text import (
    ALLOWED_FORMS,
    FAMILY_OF,
    GAP,
    OPEN_EMPHASIS,
    PREPOSITION_FORMS,
    PREVIOUS_WORD,
    SUBJECT_AUXILIARIES,
    WORD_END,
    WORD_START,
    Hit,
    read_lines,
)
from wording_words import (
    BE_FORMS,
    CLAUSE_OPENERS,
    NOT_OBJECTS,
    NOT_PAST_TENSE,
    PERFECT_AUXILIARIES,
    PRONOUNS,
    RELATIVE_DETERMINERS,
    RELATIVE_FILLERS,
)

# A determiner, an optional adjective, and a noun, then a negative that may be the
# subject of a relative clause hung off the noun.  ``_relative_clause`` decides from the
# words around it.
_WORD = r"[A-Za-z][A-Za-z-]*"
_RELATIVE = re.compile(
    WORD_START
    + rf"(?=(?P<determiner>{'|'.join(sorted(RELATIVE_DETERMINERS))})"
    + GAP
    + rf"(?:(?P<adjective>{_WORD}){GAP})?"
    + rf"(?P<noun>{_WORD}){GAP}"
    + r"(?P<negative>nothing|nobody|none|no)"
    + WORD_END
    + ")",
    re.IGNORECASE,
)

# The next word, which may be hyphenated ("no signed-in account made").
_NEXT_HYPHENATED_WORD = re.compile(GAP + rf"({_WORD})", re.IGNORECASE)

#: Words that can't be the noun a relative clause hangs from: a word that opens a clause,
#: a preposition, a form of "be" or "have", a pronoun, or another determiner.
_NOT_NOUNS = (
    ALLOWED_FORMS
    | PREPOSITION_FORMS
    | frozenset(BE_FORMS.split())
    | PERFECT_AUXILIARIES
    | frozenset(PRONOUNS)
    | (RELATIVE_DETERMINERS - {"one"})
    | frozenset(("did", "do", "does", "not"))
)

#: The words that open a clause, after which a phrase led by a preposition is a lead-in.
_OPENER_FORMS = frozenset(word for group in CLAUSE_OPENERS for word in group.split())

#: The characters that end a sentence or a clause, or open a quote, a bracket, a list
#: item, or a comment, so that a preposition after one leads in to a clause of its own
#: ("On any failure nothing is written").  A comma, a closing bracket, or a backtick is
#: as often followed by a phrase that finishes the clause ("blank, for a category ...").
_CLAUSE_BOUNDARIES = frozenset(".;:!?([{\"'->" + chr(0x2018) + chr(0x201C))

# What stands between the word before a preposition and the preposition itself: spaces,
# or a line break with the continuation's indentation and comment leader, then any bold
# or italic markup that opens on the preposition ("(*On any failure ...").
_LEAD_IN_TAIL = re.compile(
    r"[ \t]*(?:\r?\n[ \t]*(?:(?:\#:?|//|\*)[ \t]*)?)?" + rf"{OPEN_EMPHASIS}?\Z"
)

#: The remedy a relative-clause hit suggests.
_RELATIVE_REMEDY = "rewrite as an adjective or 'that doesn't ...'"


def find_relative_clauses(text: str, path: str) -> list[Hit]:
    """Every negative relative clause hung off a noun in ``text``, in order.

    That is a determiner, at most one adjective, and a noun, followed by a negative
    subject and its verb, as the module docstring describes.  ``_relative_clause``
    holds the tests; a marker silences a hit as it silences any other.  A clause is
    reported once, from its first determiner: "the one cell", read as "the" and the
    adjective "one", hides the same clause read from "one".
    """
    index = read_lines(text)
    hits = []
    negatives = set()
    for match in _RELATIVE.finditer(text):
        if match.start("negative") in negatives:
            continue
        words = _relative_clause(text, match)
        if words is None:
            continue
        negatives.add(match.start("negative"))
        span = (match.start("determiner"), match.start("negative"))
        hit = index.hit(path, span, f"{' '.join(words)} -> {_RELATIVE_REMEDY}")
        if hit is not None:
            hits.append(hit)
    return hits


def _relative_clause(text: str, match: re.Match[str]) -> list[str] | None:
    """The words from the determiner to the verb, if the match is a relative clause.

    The noun must read as one (``_is_a_noun``); the negative must not be a value or a
    quoted label (``None``, an all-caps negative after a noun that isn't all caps, or a
    capitalized negative after a lower-case noun); the noun phrase must not lead in to a
    clause after a preposition (``_is_a_lead_in``); and a verb must follow the negative
    subject (``_subject_and_verb``).
    """
    noun, negative, adjective = match["noun"], match["negative"], match["adjective"]
    if not _is_a_noun(noun, adjective):
        return None
    if negative == "None" or (negative.isupper() and not noun.isupper()):
        return None
    if negative[0].isupper() and noun[0].islower():
        return None
    if _is_a_lead_in(text, match.start("determiner")):
        return None
    subject = _subject_and_verb(text, match.end("negative"), negative.lower())
    if subject is None:
        return None
    lead = [match["determiner"], *([] if adjective is None else [adjective]), noun]
    return [*lead, negative, *subject]


def _is_a_noun(noun: str, adjective: str | None) -> bool:
    """Whether ``noun``, after ``adjective`` if there is one, reads as a noun.

    Neither word may be in ``_NOT_NOUNS``.  A past tense or a past participle spelled
    unlike its base (``found``, an unlisted ``-ed`` word) is a verb, and so is a
    third-person present form after an adjective, which is then the verb's subject
    ("the page says nothing is hidden").
    """
    lower = noun.lower()
    if lower in _NOT_NOUNS or (adjective is not None and adjective.lower() in _NOT_NOUNS):
        return False
    family = FAMILY_OF.get(lower)
    if family is None:
        return not (lower.endswith("ed") and lower not in NOT_PAST_TENSE)
    if lower != family.base and lower in (family.past, family.participle):
        return False
    return adjective is None or lower != family.third


def _is_a_lead_in(text: str, start: int) -> bool:
    """Whether the noun phrase at ``start`` follows a preposition that opens a clause.

    A preposition opens one after the start of the text, a character in
    ``_CLAUSE_BOUNDARIES`` (a full stop, a colon, an opening quote, ...), or a word in
    ``CLAUSE_OPENERS``, past a line break and its comment leader and any markup that
    opens on the preposition: "On any failure nothing is written" leads in to a clause
    with a negative subject.
    """
    previous = PREVIOUS_WORD.search(text, max(0, start - 80), start)
    if previous is None or previous[1].lower() not in PREPOSITION_FORMS:
        return False
    before = text[max(0, previous.start(1) - 80) : previous.start(1)]
    tail = _LEAD_IN_TAIL.search(before)
    if tail is not None:
        before = before[: tail.start()]
    if before == "" or before[-1] in _CLAUSE_BOUNDARIES:
        return True
    opener = PREVIOUS_WORD.search(before + " ")
    return opener is not None and opener[1].lower() in _OPENER_FORMS


def _subject_and_verb(text: str, end: int, negative: str) -> list[str] | None:
    """The rest of the negative subject after ``end`` and its verb, if a verb follows.

    After ``nothing``, ``nobody``, ``none``, or ``no one``, past the words in
    ``RELATIVE_FILLERS``, the next word must be a verb (``_is_clause_verb``).  After
    ``no`` and a noun, one or two more nouns may stand before the verb ("no active plan
    carries"); a word in ``NOT_OBJECTS`` after ``no`` makes it an adverb ("no longer").
    """
    words = _words_as_written(text, end, 5)
    lower = [word.lower() for word in words]
    if negative == "no" and (len(lower) == 0 or lower[0] in NOT_OBJECTS):
        return None
    if negative != "no" or lower[0] == "one":
        first = 0 if negative != "no" else 1
        verbs = [
            index for index in range(first, len(lower)) if lower[index] not in RELATIVE_FILLERS
        ]
        if len(verbs) == 0 or not _is_clause_verb(lower[verbs[0]], after_pronoun=True):
            return None
        return words[: verbs[0] + 1]
    for index in range(1, min(len(lower), 4)):
        previous = lower[index - 1]
        after_plural = previous.endswith("s") and not previous.endswith("ss")
        if _is_clause_verb(lower[index], after_plural=after_plural):
            return words[: index + 1]
        if lower[index] in _NOT_NOUNS:
            return None
    return None


def _is_clause_verb(word: str, *, after_pronoun: bool = False, after_plural: bool = False) -> bool:
    """Whether ``word``, after a negative subject, reads as that subject's verb.

    A form of "be", a modal, or a perfect auxiliary does, and so does a listed verb's
    third-person, past, or participle form, its base form after a plural noun
    (``after_plural``), and an unlisted ``-ed`` word.  After a negative pronoun
    (``after_pronoun``: ``nobody``, ``nothing``, ``none``, or ``no one``), an unlisted
    word ending in a single ``s`` reads as a present verb ("nothing awaits").
    """
    if word in SUBJECT_AUXILIARIES:
        return True
    family = FAMILY_OF.get(word)
    if family is not None:
        is_finite = word in (family.third, family.past, family.participle)
        return is_finite or (after_plural and word == family.base)
    if word in _NOT_NOUNS:
        return False
    if word.endswith("ed"):
        return word not in NOT_PAST_TENSE
    return after_pronoun and word.endswith("s") and not word.endswith("ss")


def _words_as_written(text: str, end: int, count: int) -> list[str]:
    """Up to ``count`` words after ``end``, as written, with only separators between."""
    words: list[str] = []
    position = end
    while len(words) < count:
        found = _NEXT_HYPHENATED_WORD.match(text, position)
        if found is None:
            break
        words.append(found[1])
        position = found.end()
    return words
