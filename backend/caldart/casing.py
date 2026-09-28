"""Title-case normalization for street addresses and city names.

A street address or a city name is stored in title case, whatever case it was typed
in, so ``"123 main st"`` and ``"PALO ALTO"`` both read the way a human would write
them: ``"123 Main St"`` and ``"Palo Alto"``.
"""

import re
from itertools import pairwise

#: Internal runs of whitespace collapse to one space.
_WHITESPACE_RE = re.compile(r"\s+")


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
