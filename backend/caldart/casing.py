"""Case normalization for street addresses, city names, and people's names.

A street address or a city name is stored in title case, whatever case it was typed
in, so ``"123 main st"`` and ``"PALO ALTO"`` both read the way a human would write
them: ``"123 Main St"`` and ``"Palo Alto"``.  A person's name typed entirely in one
case is title-cased with the exceptions names need (``"MCDONALD"`` reads
``"McDonald"``); one typed in mixed case is kept as its owner spelled it.
"""

import re
from itertools import pairwise

#: Internal runs of whitespace collapse to one space.
_WHITESPACE_RE = re.compile(r"\s+")

#: The particles a name keeps lower case when they are not its first word.
NAME_PARTICLES = frozenset(
    {"van", "von", "der", "den", "de", "del", "della", "da", "di", "du", "la", "le"}
)

#: The generational suffixes a name keeps upper case when they are not its first word.
NAME_SUFFIXES = frozenset({"ii", "iii", "iv"})

#: The prefix whose next letter is capitalized too.  ``Mac`` is deliberately absent:
#: ``Macarthur`` and ``Mackey`` are as common as ``MacArthur``, so it cannot be guessed.
_MC_PREFIX = "Mc"


def title_case_words(value: str) -> str:
    """Return ``value`` with every word capitalized, a word carrying a digit untouched.

    Leading and trailing whitespace is trimmed and internal runs of whitespace
    collapse to one space.  A word containing a digit -- a house number, a unit like
    ``3B``, or an ordinal like ``2nd`` -- is left exactly as it was typed.  Every
    other word is split on ``-`` and each part is capitalized (its first letter
    upper, the rest lower).  After an apostrophe, a part capitalizes only when what
    precedes the apostrophe is a single letter, so a name keeps its capital and a
    possessive stays lower: ``o'brien-smith LANE`` becomes ``O'Brien-Smith Lane``,
    ``KING'S rd`` becomes ``King's Rd``, and ``123 MAIN ST NE`` becomes
    ``123 Main St Ne``.  A blank value stays blank.
    """
    trimmed = _WHITESPACE_RE.sub(" ", value.strip())
    if not trimmed:
        return ""
    return " ".join(_title_case_word(word) for word in trimmed.split(" "))


def person_name(value: str) -> str:
    """Return the first or last name ``value`` as it is stored.

    Leading and trailing whitespace is trimmed and internal runs of whitespace collapse
    to one space, always.  A name with any letter in each case -- ``DeAnna``,
    ``MacArthur``, ``van Dyke`` -- is a deliberate spelling and is otherwise kept as
    typed.  A name typed entirely in upper or entirely in lower case is title-cased word
    by word: each ``-`` part capitalized (``smith-jones`` -> ``Smith-Jones``), the letter
    after a one-letter prefix and an apostrophe capitalized (``o'brien`` ->
    ``O'Brien``), and the letter after a leading ``Mc`` capitalized (``MCDONALD`` ->
    ``McDonald``; ``Mac`` is left alone).  Past the first word, the particles in
    ``NAME_PARTICLES`` stay lower case (``VAN DER BERG`` -> ``Van der Berg``) and the
    suffixes in ``NAME_SUFFIXES`` upper case (``smith iii`` -> ``Smith III``).  A blank
    value stays blank.
    """
    trimmed = _WHITESPACE_RE.sub(" ", value.strip())
    if trimmed not in {trimmed.upper(), trimmed.lower()}:
        return trimmed
    words = trimmed.split(" ")
    return " ".join(_name_word(word, first=index == 0) for index, word in enumerate(words))


def _name_word(word: str, *, first: bool) -> str:
    """One word of a one-case name, cased by the rules :func:`person_name` lists."""
    lowered = word.lower()
    if not first and lowered in NAME_PARTICLES:
        return lowered
    if not first and lowered in NAME_SUFFIXES:
        return word.upper()
    return "-".join(_name_part(part) for part in word.split("-"))


def _name_part(part: str) -> str:
    """One hyphen-free part of a name: capitalized, with ``Mc`` and ``O'`` honored."""
    cased = _title_case_part(part)
    if cased.startswith(_MC_PREFIX) and len(cased) > len(_MC_PREFIX):
        rest = cased[len(_MC_PREFIX) :]
        return f"{_MC_PREFIX}{rest[0].upper()}{rest[1:]}"
    return cased


def _title_case_word(word: str) -> str:
    """One word, each ``-`` part capitalized, unless the word carries a digit."""
    if any(character.isdigit() for character in word):
        return word
    return "-".join(_title_case_part(part) for part in word.split("-"))


def _title_case_part(part: str) -> str:
    """One hyphen-free part, capitalized; after an apostrophe, only past a lone letter."""
    pieces = part.split("'")
    cased = [pieces[0].capitalize()]
    for before, piece in pairwise(pieces):
        cased.append(piece.capitalize() if len(before) == 1 else piece.lower())
    return "'".join(cased)
