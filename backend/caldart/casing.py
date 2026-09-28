"""Title-case normalization for street addresses and city names.

A street address or a city name is stored in title case, whatever case it was typed
in, so ``"123 main st"`` and ``"PALO ALTO"`` both read the way a human would write
them: ``"123 Main St"`` and ``"Palo Alto"``.
"""

import re

#: Internal runs of whitespace collapse to one space.
_WHITESPACE_RE = re.compile(r"\s+")

#: Where a word breaks into parts that each capitalize on their own.
_WORD_PART_RE = re.compile(r"([-'])")


def title_case_words(value: str) -> str:
    """Return ``value`` with every word capitalized, a word carrying a digit untouched.

    Leading and trailing whitespace is trimmed and internal runs of whitespace
    collapse to one space.  A word containing a digit -- a house number, a unit like
    ``3B``, or an ordinal like ``2nd`` -- is left exactly as it was typed.  Every
    other word is split on ``-`` and ``'`` and each part is capitalized (its first
    letter upper, the rest lower), so ``o'brien-smith LANE`` becomes
    ``O'Brien-Smith Lane`` and ``123 MAIN ST NE`` becomes ``123 Main St Ne``.  A
    blank value stays blank.
    """
    trimmed = _WHITESPACE_RE.sub(" ", value.strip())
    if not trimmed:
        return ""
    return " ".join(_title_case_word(word) for word in trimmed.split(" "))


def _title_case_word(word: str) -> str:
    """One word, split on ``-`` and ``'``, each part capitalized unless it has a digit."""
    if any(character.isdigit() for character in word):
        return word
    parts = _WORD_PART_RE.split(word)
    return "".join(part if part in ("-", "'") else part.capitalize() for part in parts)
