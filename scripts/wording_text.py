"""How the wording check reads text: words, the space between them, lines, and hits.

``scripts/check_wording.py`` and ``scripts/wording_relative.py`` share these pieces, so a
negative object and a negative relative clause are read the same way: the same space
between words (a space or a tab, one line break with its comment leader, a join between
two string literals, and bold or italic markup), the same word boundaries, the same
verb families, and the same markers.
"""

import bisect
import re
from dataclasses import dataclass
from typing import NamedTuple

from wording_words import (
    ALLOWED_WORDS,
    BE_FORMS,
    CONTRACTIONS,
    FLAGGED_VERBS,
    MODALS,
    PERFECT_AUXILIARIES,
    PREPOSITIONS,
)

#: Every deliberately allowed word, lower case.
ALLOWED_FORMS = frozenset(word for group in ALLOWED_WORDS for word in group.split())

#: The prepositions, lower case: a pronoun after one is its object, never read past.
PREPOSITION_FORMS = frozenset(word for group in PREPOSITIONS for word in group.split())

#: A word after ``nothing``, ``nobody``, ``none``, or ``no one`` (past an ``else``) that
#: makes the negative the subject of a clause of its own ("says nobody is signed in",
#: "says nothing has gone"): a form of "be", a modal, or a perfect auxiliary.
SUBJECT_AUXILIARIES = frozenset(BE_FORMS.split() + MODALS.split() + list(PERFECT_AUXILIARIES))

# Where one string literal ends and the next begins: a closing quote, an optional ``+``,
# an optional line break with its indentation, and an opening quote ('x ' + 'y').  A
# space must stand on one side of the quotes, inside one literal or the other, or the
# two words would run together.
_JOIN = r"[ \t]*\+?[ \t]*(?:\r?\n[ \t]*\+?[ \t]*)?"
_LITERAL_JOIN = rf"(?:[ \t]+[\"']{_JOIN}[\"']|[\"']{_JOIN}[\"'][ \t]+)"

# A single space or tab, so that a table's padding never joins two cells; one line
# break, with the continuation's indentation and comment leader; or a literal join.
SEPARATOR = r"(?:[ \t]|[ \t]*\r?\n[ \t]*(?:(?:\#:?|//|\*)[ \t]*)?|" + _LITERAL_JOIN + ")"

# Emphasis may close before a separator and open after it ("**x** y", "<em>x</em> y"),
# so that bold or italic text is checked like plain text.
OPEN_EMPHASIS = r"(?:\*\*?|<(?:b|strong|em|i)>)"
_CLOSE_EMPHASIS = r"(?:\*\*?|</(?:b|strong|em|i)>)"
GAP = rf"{_CLOSE_EMPHASIS}?{SEPARATOR}{OPEN_EMPHASIS}?"

#: The apostrophes that join a contraction into one word: straight and typographic.
APOSTROPHES = "'" + chr(0x2019)

# A word starts after anything but a letter, a digit, or an underscore, and after an
# apostrophe only when no letter stands before it: an opening quote ("it('sends") starts a
# word, while the apostrophe inside a contraction ("doesn't") joins its letters into one.
WORD_START = rf"(?<!\w)(?<!\w[{APOSTROPHES}])"

# A word ends before anything but a letter, a digit, an underscore, or a hyphen, and
# before an apostrophe only when no letter follows it: a closing quote ("it('is done')")
# ends a word, while one inside a contraction or a possessive ("none's") joins the next.
WORD_END = rf"(?![\w-])(?![{APOSTROPHES}]\w)"

# A contraction of "be" or "have" ("there's", "we're", "you've", "they'd") is one word,
# flagged before a negative like the form it stands for.
CONTRACTION = rf"[{APOSTROPHES}](?:{'|'.join(sorted(CONTRACTIONS))})"

#: The word after a position, with only the space between words before it.
NEXT_WORD = re.compile(GAP + r"([A-Za-z]+)", re.IGNORECASE)

#: The word before a position, with only the space between words after it.
PREVIOUS_WORD = re.compile(
    rf"(?<![\w{APOSTROPHES}])([A-Za-z]+(?:{CONTRACTION})?)" + GAP + r"\Z", re.IGNORECASE
)

#: The marker that keeps a line verbatim, and the start of the next-line marker.
MARKER = "wording:ignore"

_SAME_LINE_MARKER = re.compile(r"wording:ignore(?!-next-line)")

_NEXT_LINE_MARKER = "wording:ignore-next-line"

# A reStructuredText comment that holds only the next-line marker.
_PARAGRAPH_MARKER = re.compile(r"\s*\.\.\s+wording:ignore-next-line\s*")


class Family(NamedTuple):
    """The five forms of one flagged verb, in ``FLAGGED_VERBS`` order."""

    base: str
    third: str
    past: str
    participle: str
    present_participle: str


def _families() -> dict[str, Family]:
    """Map each flagged form to its family; a family with other than five forms raises."""
    families = {}
    for line in FLAGGED_VERBS:
        family = Family(*line.split())
        for form in family:
            families[form] = family
    return families


FAMILY_OF = _families()


@dataclass(frozen=True)
class Hit:
    """One flagged phrase: where it is, its line's text, and a rewrite if one is simple.

    ``line`` is the 1-based line the verb is on, or for a relative clause the line its
    determiner is on.  ``text`` is that line stripped, joined with the next line when the
    phrase wraps.  A relative clause's ``suggestion`` reads ``"<determiner, noun,
    negative, and verb> -> rewrite as an adjective or 'that doesn't ...'"``.  A negative
    object's ``suggestion`` reads ``"<phrase> ->
    <rewrite>"`` for a third-person present form, a simple past that differs from the
    base form, or a past participle after ``has``, ``have``, ``had``, ``is``, ``are``,
    ``was``, ``were``, ``am``, ``get``, ``gets``, or ``got``, each with at most a pronoun
    before the negative, and for ``is``, ``are``, ``was``, ``were``, ``am``, and
    ``with`` (``NEGATED_WORDS``).  It is ``None`` for every other hit (a base form, an
    ``-ing`` form, an unlisted ``-ed`` word, a past participle after ``be``, ``been``, or
    ``being``, any other word from ``FLAGGED_WORDS``, or a phrase with an adverb in it),
    whose rewrite depends on the words around it.
    """

    path: str
    line: int
    text: str
    suggestion: str | None


class Lines(NamedTuple):
    """A text's lines, the offset each starts at, and the line numbers a marker covers."""

    lines: list[str]
    starts: list[int]
    silenced: set[int]

    def hit(self, path: str, span: tuple[int, int], suggestion: str | None) -> Hit | None:
        """The hit on the lines ``span`` covers, or ``None`` when a marker covers one."""
        first = bisect.bisect_right(self.starts, span[0])
        last = bisect.bisect_right(self.starts, span[1])
        if any(number in self.silenced for number in range(first, last + 1)):
            return None
        text = " ".join(self.lines[number - 1].strip() for number in range(first, last + 1))
        return Hit(path=path, line=first, text=text, suggestion=suggestion)


def read_lines(text: str) -> Lines:
    """Split ``text`` into its lines, with their offsets and the lines a marker covers."""
    lines = text.split("\n")
    starts = [0]
    for line in lines[:-1]:
        starts.append(starts[-1] + len(line) + 1)
    silenced = _silenced_lines(lines) if MARKER in text else set()
    return Lines(lines, starts, silenced)


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
