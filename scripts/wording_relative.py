"""Flag a negative clause hung off a noun, and a telling verb without its "that".

People don't talk that way.  A noun followed by ``no``, ``nothing``, ``nobody``,
``none``, or ``no one`` as the subject of its own verb reads as a puzzle, with or without
a "that" or a "which" between them: "an id" followed by "no row has", or "a corporate
name" followed by "that nobody uses".  Write a plain adjective or a plain statement ("an
unknown id", "a corporate name not used by anybody"), or break the sentence into short
ones.  And a verb of telling needs its "that" before a negative subject: "tells the
member that nothing is due".  ``scripts/check_wording.py`` reports these with its other
hits; its module docstring lists what is flagged and what is passed over.
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
    Lines,
    read_lines,
)
from wording_words import (
    ADVERBIAL_NOUNS,
    BE_FORMS,
    CLAUSE_OPENERS,
    CONTENT_NOUNS,
    NOT_BARE_NOUNS,
    NOT_OBJECTS,
    NOT_PAST_TENSE,
    PERFECT_AUXILIARIES,
    PRONOUNS,
    RELATIVE_DETERMINERS,
    RELATIVE_FILLERS,
    TELLING_VERBS,
)

_WORD = r"[A-Za-z][A-Za-z-]*"
_NEGATIVE = r"(?P<negative>nothing|nobody|none|no)" + WORD_END

# A determiner, an optional adjective, and a noun, then a negative that may be the
# subject of a relative clause hung off the noun.  ``_relative_clause`` decides from the
# words around it.
_RELATIVE = re.compile(
    WORD_START
    + rf"(?=(?P<determiner>{'|'.join(sorted(RELATIVE_DETERMINERS))})"
    + GAP
    + rf"(?:(?P<adjective>{_WORD}){GAP})?"
    + rf"(?P<noun>{_WORD}){GAP}"
    + _NEGATIVE
    + ")",
    re.IGNORECASE,
)

# A plural noun without a determiner, or an indefinite pronoun, then a negative: "Types"
# followed by "nobody may turn off", "everything" followed by "nobody has verified".
_BARE_PLURAL = re.compile(
    WORD_START
    + r"(?=(?P<noun>(?:any|every|some)(?:body|one|thing)|[A-Za-z][A-Za-z-]*[A-Za-z]s)"
    + GAP
    + _NEGATIVE
    + ")",
    re.IGNORECASE,
)

# A noun, then "that", "which", "who", or "whom" (or a preposition and "which" or
# "whom"), then a negative: "a corporate name" followed by "that nobody uses".
_FULL_CLAUSE = re.compile(
    WORD_START
    + rf"(?=(?P<noun>{_WORD}){GAP}"
    + rf"(?:(?P<preposition>{_WORD}){GAP})?"
    + rf"(?P<relative>that|which|who|whom){GAP}"
    + _NEGATIVE
    + ")",
    re.IGNORECASE,
)

# A comma, "which", "who", or "whom" (or a preposition and "which" or "whom"), then a
# negative: "Operational email," followed by "which nobody may turn off".
_COMMA_CLAUSE = re.compile(
    rf"(?<=\S)(?=,{GAP}"
    + rf"(?:(?P<preposition>{_WORD}){GAP})?"
    + rf"(?P<relative>which|who|whom){GAP}"
    + _NEGATIVE
    + ")",
    re.IGNORECASE,
)

#: Every form of the verbs of telling, lower case.
_TELLING_FORMS = frozenset(form for base in TELLING_VERBS for form in FAMILY_OF[base])

# A verb of telling, a pronoun, and a negative: "Tell them" followed by "nobody can".
_TELLING = re.compile(
    WORD_START
    + rf"(?=(?P<verb>{'|'.join(sorted(_TELLING_FORMS))}){GAP}"
    + rf"(?P<object>{'|'.join(PRONOUNS)}){GAP}"
    + _NEGATIVE
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

#: The coordinating conjunctions, which open a clause only after a comma or a boundary:
#: "It stops, and on a failure nothing is kept".
_CONJUNCTIONS = frozenset(("and", "but", "nor", "or", "so", "yet"))

#: The characters that end a sentence or open a quote, so that a preposition after one
#: leads in to a clause of its own ("On any failure nothing is written").  A comma, a
#: closing bracket, a dash, or a backtick is as often followed by a phrase that finishes
#: the clause ("blank, for a category ..."); an opening bracket or a colon is too,
#: unless the preposition is capitalized.
_CLAUSE_BOUNDARIES = frozenset(".;!?[{\"'>\n" + chr(0x2018) + chr(0x201C))
_CAPITALIZED_BOUNDARIES = frozenset("(:")

# What stands between the word before a preposition and the preposition itself: spaces,
# or a line break with the continuation's indentation and comment leader, then any bold
# or italic markup that opens on the preposition ("(*On any failure ...").
_LEAD_IN_TAIL = re.compile(
    r"[ \t]*(?:\r?\n[ \t]*(?:(?:\#:?|//|\*)[ \t]*)?)?" + rf"{OPEN_EMPHASIS}?\Z"
)

# The start of a line up to a list item's text: indentation, a comment leader, and a
# bullet or an enumerator, then any markup that opens on the item's first word.
_LIST_ITEM = re.compile(
    r"[ \t]*(?:(?:\#:?|//)[ \t]*)?(?:[-*+]|\d+\.|\#\.)[ \t]+" + rf"{OPEN_EMPHASIS}?"
)

#: The remedy a reduced relative clause suggests.
_RELATIVE_REMEDY = "rewrite as an adjective or 'that doesn't ...'"

#: The remedy a full relative clause suggests.
_FULL_REMEDY = "say it plainly ('not used by anybody') or in short sentences"


def find_relative_clauses(text: str, path: str) -> list[Hit]:
    """Every negative clause hung off a noun, and every telling verb missing its "that".

    In order of position: a reduced relative clause after a determiner and a noun, or
    after a bare plural or an indefinite pronoun ("Types" followed by "nobody may"); a
    full one after "that", "which", "who", or "whom", after a noun or a comma; and a verb
    of telling whose object is followed by a negative subject and its verb.  The module
    docstring of ``scripts/check_wording.py`` describes each test; a marker silences a hit
    as it silences any other.  A clause is reported once, from its first determiner: "the
    one cell", read as "the" and the adjective "one", hides the same clause read from
    "one".
    """
    index = read_lines(text)
    found: dict[int, tuple[int, int, str]] = {}
    for match in _RELATIVE.finditer(text):
        if match.start("negative") not in found:
            _add(found, _reduced_clause(text, match))
    for match in _BARE_PLURAL.finditer(text):
        if match.start("negative") not in found:
            _add(found, _bare_clause(text, match))
    for match in _FULL_CLAUSE.finditer(text):
        _add(found, _full_clause(text, match))
    for match in _COMMA_CLAUSE.finditer(text):
        _add(found, _comma_clause(text, match))
    for match in _TELLING.finditer(text):
        _add(found, _telling_clause(text, match))
    return _hits(index, path, found)


def _add(found: dict[int, tuple[int, int, str]], hit: tuple[int, int, str] | None) -> None:
    """Record ``hit`` (its start, its negative's start, and its suggestion), if any."""
    if hit is not None:
        found[hit[1]] = hit


def _hits(index: Lines, path: str, found: dict[int, tuple[int, int, str]]) -> list[Hit]:
    """The recorded hits in order, minus those a marker covers."""
    hits = []
    for start, negative, suggestion in sorted(found.values()):
        hit = index.hit(path, (start, negative), suggestion)
        if hit is not None:
            hits.append(hit)
    return hits


def _reduced_clause(text: str, match: re.Match[str]) -> tuple[int, int, str] | None:
    """The hit for a determiner, a noun, and a negative subject, if it is one.

    The noun must read as one (``_is_a_noun``) and must not say when, how, or why
    (``_is_adverbial``: "That way nothing is lost"); the negative must not be a value
    or a quoted label (``_is_a_value``); the noun phrase must not lead in to a clause
    after a preposition (``_is_a_lead_in``); and a verb must follow the negative subject
    (``_subject_and_verb``).  After a verb of telling the hit asks for a "that" instead.
    """
    noun, negative, adjective = match["noun"], match["negative"], match["adjective"]
    if not _is_a_noun(noun, adjective) or _is_adverbial(match["determiner"], noun):
        return None
    if _is_a_value(noun, negative):
        return None
    start = match.start("determiner")
    if _is_a_lead_in(text, start):
        return None
    subject = _subject_and_verb(text, match.end("negative"), negative.lower())
    if subject is None:
        return None
    lead = [match["determiner"], *([] if adjective is None else [adjective]), noun]
    if _follows_telling(text, start):
        verb = PREVIOUS_WORD.search(text, max(0, start - 80), start)
        assert verb is not None  # noqa: S101 - _follows_telling found it
        told = [verb[1], *lead]
        return _missing_that(verb.start(1), told, [negative, *subject], match.start("negative"))
    suggestion = f"{' '.join([*lead, negative, *subject])} -> {_RELATIVE_REMEDY}"
    return (start, match.start("negative"), suggestion)


def _bare_clause(text: str, match: re.Match[str]) -> tuple[int, int, str] | None:
    """The hit for a bare plural or an indefinite pronoun and a negative subject, if any.

    The plural (or ``everything``, ``anyone``, ``somebody``, ...) must not follow a
    determiner, nor a determiner and one more word (those are read as
    ``_reduced_clause`` reads them), must read as a bare noun (``_is_a_bare_noun``), and
    must not lead in to a clause after a preposition; a verb must follow the negative
    subject.
    """
    noun, negative = match["noun"], match["negative"]
    start = match.start("noun")
    if _determiner_before(text, start) is not None or not _is_a_bare_noun(noun):
        return None
    if _is_a_value(noun, negative) or _is_a_lead_in(text, start):
        return None
    subject = _subject_and_verb(text, match.end("negative"), negative.lower())
    if subject is None:
        return None
    suggestion = f"{' '.join([noun, negative, *subject])} -> {_RELATIVE_REMEDY}"
    return (start, match.start("negative"), suggestion)


def _full_clause(text: str, match: re.Match[str]) -> tuple[int, int, str] | None:
    """The hit for a noun, a relative word, and a negative subject, if it is one.

    "that", "which", "who", or "whom" follows the noun, or a preposition and "which" or
    "whom" do ("a DART to which" followed by "nobody may be added").  After a
    determiner (and at most one adjective) the noun must read as one (``_is_a_noun``),
    and without one as a bare noun (``_is_a_bare_noun``).  A noun that states the
    content of a "that" clause (``CONTENT_NOUNS``: "the note that nothing listens") or
    says when, how, or why (``_is_adverbial``) is passed over, and so is a verb of
    telling in the noun's slot or before its determiner ("tells the member that nothing
    is due"); a verb must follow the negative subject.
    """
    noun, relative, negative = match["noun"], match["relative"].lower(), match["negative"]
    if not _is_a_relative(match["preposition"], relative):
        return None
    lower = noun.lower()
    if lower in _TELLING_FORMS or (relative == "that" and lower in CONTENT_NOUNS):
        return None
    start = match.start("noun")
    determiner = _determiner_before(text, start)
    if determiner is None:
        is_noun = _is_a_bare_noun(noun) and lower not in ADVERBIAL_NOUNS
    else:
        start, adjective = determiner
        is_noun = _is_a_noun(noun, adjective)
        is_noun = is_noun and not _is_adverbial(text[start:].split()[0], noun)
    if not is_noun or _is_a_value(noun, negative) or _follows_telling(text, start):
        return None
    subject = _subject_and_verb(text, match.end("negative"), negative.lower())
    if subject is None:
        return None
    lead = [word for word in text[start : match.end("relative")].split() if _is_word(word)]
    suggestion = f"{' '.join([*lead, negative, *subject])} -> {_FULL_REMEDY}"
    return (start, match.start("negative"), suggestion)


def _comma_clause(text: str, match: re.Match[str]) -> tuple[int, int, str] | None:
    """The hit for a comma, "which", "who", or "whom", and a negative subject, if any.

    Whatever stands before the comma, the clause hangs a negative subject off it:
    "Operational email," followed by "which nobody may turn off".  A preposition may
    stand before "which" or "whom"; the negative must not be a value, and a verb must
    follow it.
    """
    relative, negative = match["relative"].lower(), match["negative"]
    if not _is_a_relative(match["preposition"], relative):
        return None
    if negative == "None" or negative.isupper():
        return None
    subject = _subject_and_verb(text, match.end("negative"), negative.lower())
    if subject is None:
        return None
    start = match.start()
    previous = PREVIOUS_WORD.search(text, max(0, start - 80), start)
    if previous is not None:
        start = previous.start(1)
    lead = [word for word in text[start : match.end("relative")].split() if _is_word(word)]
    suggestion = f"{' '.join([*lead, negative, *subject])} -> {_FULL_REMEDY}"
    return (start, match.start("negative"), suggestion)


def _is_a_relative(preposition: str | None, relative: str) -> bool:
    """Whether ``preposition`` (if any) and ``relative`` open a relative clause.

    Only "which" and "whom" follow a preposition, and the word before them must be one.
    """
    if preposition is None:
        return True
    return relative in ("which", "whom") and preposition.lower() in PREPOSITION_FORMS


def _telling_clause(text: str, match: re.Match[str]) -> tuple[int, int, str] | None:
    """The hit for a verb of telling, a pronoun, and a negative subject without "that"."""
    negative = match["negative"]
    if _is_a_value(match["verb"], negative):
        return None
    subject = _subject_and_verb(text, match.end("negative"), negative.lower())
    if subject is None:
        return None
    told = [match["verb"], match["object"]]
    clause = [negative, *subject]
    return _missing_that(match.start("verb"), told, clause, match.start("negative"))


def _missing_that(
    start: int, told: list[str], clause: list[str], negative: int
) -> tuple[int, int, str]:
    """The hit asking for "that" between a telling verb's object and its clause.

    ``told`` is the verb and its object, from ``start``; ``clause`` the negative subject
    and its verb, from ``negative``.
    """
    lead, said = " ".join(told), " ".join(clause)
    return (start, negative, f"{lead} {said} -> {lead} that {said}")


def _is_adverbial(determiner: str, noun: str) -> bool:
    """Whether ``determiner`` and ``noun`` say when, how, or why, as an adverb would.

    The noun is in ``ADVERBIAL_NOUNS`` and the determiner isn't ``a`` or ``an``: "That
    way", "Every time", "The day", or "The reason" before a negative subject starts a
    clause of its own, while "a day" before one hangs a relative clause off the noun.
    """
    return noun.lower() in ADVERBIAL_NOUNS and determiner.lower() not in ("a", "an")


def _is_word(token: str) -> bool:
    """Whether ``token``, split from the text on spaces, holds a word, not a leader."""
    return any(character.isalnum() for character in token)


def _follows_telling(text: str, start: int) -> bool:
    """Whether the word before ``start`` is a verb of telling, with its object after."""
    verb = PREVIOUS_WORD.search(text, max(0, start - 80), start)
    return verb is not None and verb[1].lower() in _TELLING_FORMS


def _determiner_before(text: str, start: int) -> tuple[int, str | None] | None:
    """The start of a determiner before ``start``, and the adjective between, if any.

    The determiner is the word right before ``start``, or the one before that, with one
    word (the adjective) between it and ``start``.
    """
    previous = PREVIOUS_WORD.search(text, max(0, start - 80), start)
    if previous is None:
        return None
    if previous[1].lower() in RELATIVE_DETERMINERS:
        return (previous.start(1), None)
    before = PREVIOUS_WORD.search(text, max(0, previous.start(1) - 80), previous.start(1))
    if before is not None and before[1].lower() in RELATIVE_DETERMINERS:
        return (before.start(1), previous[1])
    return None


def _is_a_value(noun: str, negative: str) -> bool:
    """Whether the negative is a value or a quoted label rather than a subject.

    That is ``None``, an all-caps negative after a word that isn't all caps, or a
    capitalized negative after a lower-case word.
    """
    if negative == "None" or (negative.isupper() and not noun.isupper()):
        return True
    return negative[0].isupper() and noun[0].islower()


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


def _is_a_bare_noun(noun: str) -> bool:
    """Whether ``noun``, without a determiner before it, reads as a noun.

    Any form of a listed verb reads as that verb ("says", "check"), and so does an
    unlisted ``-ed`` word; so do the words in ``_NOT_NOUNS`` and ``NOT_BARE_NOUNS``
    (``explains``, ``except``, ``sometimes``), a word ending in ``-ly`` (an adverb), and
    one ending in ``ss`` or ``us``, which isn't a plural.
    """
    lower = noun.lower()
    if lower in _NOT_NOUNS or lower in NOT_BARE_NOUNS or lower in FAMILY_OF:
        return False
    if lower.endswith(("ly", "ss", "us")):
        return False
    return not (lower.endswith("ed") and lower not in NOT_PAST_TENSE)


def _is_a_lead_in(text: str, start: int) -> bool:
    """Whether the noun phrase at ``start`` follows a preposition that opens a clause.

    A preposition opens one at the start of the text, of a paragraph, or of a list item;
    after a character in ``_CLAUSE_BOUNDARIES`` (a full stop, a semicolon, an opening
    quote, ...); after an opening bracket or a colon when it is capitalized; after a
    word in ``CLAUSE_OPENERS``, or a coordinating conjunction that itself follows a
    comma or a boundary.  A line break and its comment leader, and markup that opens on
    the preposition, are read past: "On any failure nothing is written" leads in to a
    clause with a negative subject.
    """
    previous = PREVIOUS_WORD.search(text, max(0, start - 80), start)
    if previous is None or previous[1].lower() not in PREPOSITION_FORMS:
        return False
    position = previous.start(1)
    line_start = text.rfind("\n", 0, position) + 1
    if _LIST_ITEM.fullmatch(text, line_start, position) is not None:
        return True
    before = _strip_tail(text[max(0, position - 80) : position])
    if before == "" or before[-1] in _CLAUSE_BOUNDARIES:
        return True
    if before[-1] in _CAPITALIZED_BOUNDARIES:
        return previous[1][0].isupper()
    opener = PREVIOUS_WORD.search(before + " ")
    if opener is None or opener[1].lower() not in _OPENER_FORMS:
        return False
    if opener[1].lower() not in _CONJUNCTIONS:
        return True
    ahead = _strip_tail(before[: opener.start(1)])
    return ahead == "" or ahead[-1] in _CLAUSE_BOUNDARIES or ahead[-1] == ","


def _strip_tail(before: str) -> str:
    """``before`` without the spaces, line break, and markup ``_LEAD_IN_TAIL`` matches."""
    tail = _LEAD_IN_TAIL.search(before)
    return before if tail is None else before[: tail.start()]


def _subject_and_verb(text: str, end: int, negative: str) -> list[str] | None:
    """The rest of the negative subject after ``end`` and its verb, if a verb follows.

    After ``nothing``, ``nobody``, ``none``, or ``no one``, past the words in
    ``RELATIVE_FILLERS``, the next word must be a verb (``_is_clause_verb``).  After
    ``no`` and a noun, one or two more nouns may stand before the verb ("no active plan
    carries", "no account stands"); a word in ``NOT_OBJECTS`` after ``no`` makes it an
    adverb ("no longer").
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
        if len(verbs) == 0 or not _is_clause_verb(lower[verbs[0]], after_singular=True):
            return None
        return words[: verbs[0] + 1]
    for index in range(1, min(len(lower), 4)):
        previous = lower[index - 1]
        after_plural = previous.endswith("s") and not previous.endswith("ss")
        is_verb = _is_clause_verb(
            lower[index], after_singular=not after_plural, after_plural=after_plural
        )
        if is_verb:
            return words[: index + 1]
        if lower[index] in _NOT_NOUNS:
            return None
    return None


def _is_clause_verb(word: str, *, after_singular: bool = False, after_plural: bool = False) -> bool:
    """Whether ``word``, after a negative subject, reads as that subject's verb.

    A form of "be", a modal, or a perfect auxiliary does, and so does a listed verb's
    third-person, past, or participle form, its base form after a plural noun
    (``after_plural``), and an unlisted ``-ed`` word.  After a singular subject
    (``after_singular``: ``nobody``, ``nothing``, ``none``, ``no one``, or ``no`` and a
    singular noun), an unlisted word ending in a single ``s`` reads as a present verb
    ("nothing awaits", "no account stands").
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
    return after_singular and word.endswith("s") and not word.endswith("ss")


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
