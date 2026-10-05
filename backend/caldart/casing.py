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

#: A name part split on what may separate its pieces: an apostrophe, straight or
#: typographic (U+2019), or the period after an initial.  The capture keeps each
#: separator, so it is written back as it was typed.
_NAME_SEPARATOR_RE = re.compile("(['\u2019.])")

#: The vowels whose absence marks a part as initials (``TJ``) rather than a name.
_VOWELS = frozenset("aeiouy")

#: The words a business name keeps upper case when it is title-cased: the legal forms
#: and the trade abbreviations a registered aircraft owner's name carries.
BUSINESS_ABBREVIATIONS = frozenset({"llc", "llp", "lp", "pc", "fbo", "usa", "faa", "cap"})

#: The longest word of a business name that may be an abbreviation kept in capitals.
SHORT_ABBREVIATION_LENGTH = 4

#: An airport's ICAO identifier leading a business name, such as ``KPAO``, in capitals.
_AIRPORT_IDENTIFIER_RE = re.compile(r"K[A-Z]{3}")

#: Words of a K and three letters that lead a business name as words, not airport codes.
K_WORDS = frozenset(
    {
        "keel",
        "keen",
        "keep",
        "kemp",
        "kent",
        "kern",
        "keys",
        "kids",
        "kind",
        "king",
        "kirk",
        "kite",
        "kiwi",
        "knob",
        "knot",
        "know",
    }
)

#: Words that mark a registered name as a business's, so a leading ``K`` and three
#: letters in it reads as an airport code rather than a person's name (``KATE SMITH``).
BUSINESS_MARKERS = frozenset(
    {
        "aero",
        "air",
        "aircraft",
        "aviation",
        "club",
        "co",
        "company",
        "corp",
        "fbo",
        "flight",
        "flyers",
        "flying",
        "group",
        "inc",
        "jet",
        "jets",
        "llc",
        "llp",
        "lp",
        "partners",
        "services",
    }
)

#: Short words with no vowel that are abbreviations read as words, title-cased as any
#: word: ``St``, ``Mt``, ``Mr``, ``Dr``, ``Ctr``, and the like.
SHORT_WORD_ABBREVIATIONS = frozenset(
    {"ct", "ctr", "dr", "ft", "hwy", "jr", "ln", "mr", "mrs", "mt", "pl", "rd", "sr", "st", "tr"}
)

#: The short words a business name keeps lower case when they are not its first word.
BUSINESS_SMALL_WORDS = frozenset({"of", "the", "and", "at", "for", "in", "on"})

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
    after a one-letter prefix and an apostrophe, straight or typographic, capitalized
    (``o'brien`` -> ``O'Brien``), the letter after each period capitalized (``a.j.`` ->
    ``A.J.``), and the letter after a leading ``Mc`` capitalized (``MCDONALD`` ->
    ``McDonald``; ``Mac`` is left alone).  A part with no vowel (``a``, ``e``, ``i``,
    ``o``, ``u``, ``y``) is a run of initials and is upper-cased whole (``tj`` ->
    ``TJ``, ``DJ`` stays ``DJ``).  Past the first word, the particles in
    ``NAME_PARTICLES`` stay lower case (``VAN DER BERG`` -> ``Van der Berg``) and the
    suffixes in ``NAME_SUFFIXES`` upper case (``smith iii`` -> ``Smith III``).  A blank
    value stays blank.
    """
    trimmed = _WHITESPACE_RE.sub(" ", value.strip())
    if trimmed not in {trimmed.upper(), trimmed.lower()}:
        return trimmed
    words = trimmed.split(" ")
    return " ".join(_name_word(word, first=index == 0) for index, word in enumerate(words))


def business_name(value: str) -> str:
    """Return a business's name ``value``, as the FAA registry wrote it, in title case.

    The registry writes every name in capitals, so this is for a name filled from it,
    never for one a person typed.  Leading and trailing whitespace is trimmed and
    internal runs of whitespace collapse to one space, always.  A name with any letter in
    each case (``SkyWest Aviation``) is kept as it is.  A name in one case is title-cased
    word by word by :func:`title_case_words`, except that some words stay upper case: the
    abbreviations in ``BUSINESS_ABBREVIATIONS``, a word holding a period (``L.L.C.``),
    and a word of at most ``SHORT_ABBREVIATION_LENGTH`` letters written in capitals that
    reads as an abbreviation rather than a word: one with no vowel (``JB``, ``NTSB``)
    other than the word abbreviations in ``SHORT_WORD_ABBREVIATIONS`` (``ST``, ``MR``,
    ``CTR``), or, as the name's first word, an airport identifier, ``K`` and three
    letters (``KPAO``) that is not one of the ``K_WORDS`` (``KING``, ``KIDS``), in a name
    whose other words include one of the ``BUSINESS_MARKERS`` (``INC``, ``FBO``,
    ``AVIATION``), so ``KATE SMITH`` reads ``Kate Smith``.  The words
    in ``BUSINESS_SMALL_WORDS`` stay lower case past the first: ``SKYWAYS AVIATION OF NAPA
    LLC`` becomes ``Skyways Aviation of Napa LLC``, and ``KPAO FBO INC`` becomes ``KPAO
    FBO Inc``.  A blank value stays blank.
    """
    trimmed = _WHITESPACE_RE.sub(" ", value.strip())
    if trimmed not in {trimmed.upper(), trimmed.lower()}:
        return trimmed
    registered = trimmed.split(" ")
    words = title_case_words(trimmed).split(" ")
    # A leading airport code needs the rest of the name to read as a business's.
    leads_business = any(word.lower().strip(".,") in BUSINESS_MARKERS for word in registered[1:])
    return " ".join(
        _business_word(
            word, registered[index], first=index == 0, may_be_code=index == 0 and leads_business
        )
        for index, word in enumerate(words)
    )


def _business_word(word: str, registered: str, *, first: bool, may_be_code: bool) -> str:
    """One title-cased word of a business name, as :func:`business_name` lists.

    ``registered`` is the word as the registry wrote it, which decides whether a short
    word was an abbreviation in capitals; ``may_be_code`` whether it may be an airport
    code, which only the first word of a business's name may be.
    """
    lowered = word.lower()
    if lowered in BUSINESS_ABBREVIATIONS or "." in word:
        return word.upper()
    if not first and lowered in BUSINESS_SMALL_WORDS:
        return lowered
    if _is_short_abbreviation(registered, may_be_code=may_be_code):
        return registered
    return word


def _is_short_abbreviation(registered: str, *, may_be_code: bool) -> bool:
    """True when the registry's word is a short abbreviation, kept in its capitals.

    That is a word of letters alone, at most ``SHORT_ABBREVIATION_LENGTH`` long, written
    in capitals, and either with no vowel and not one of ``SHORT_WORD_ABBREVIATIONS``,
    or, when it ``may_be_code`` (the first word of a business's name), in the form of an
    airport identifier (``K`` and three letters) and not one of ``K_WORDS``.
    """
    if not registered.isalpha() or not registered.isupper():
        return False
    if len(registered) > SHORT_ABBREVIATION_LENGTH:
        return False
    lowered = registered.lower()
    if not any(character in _VOWELS for character in lowered):
        return lowered not in SHORT_WORD_ABBREVIATIONS
    is_identifier = _AIRPORT_IDENTIFIER_RE.fullmatch(registered) is not None
    return may_be_code and is_identifier and lowered not in K_WORDS


def _name_word(word: str, *, first: bool) -> str:
    """One word of a one-case name, cased by the rules :func:`person_name` lists."""
    lowered = word.lower()
    if not first and lowered in NAME_PARTICLES:
        return lowered
    if not first and lowered in NAME_SUFFIXES:
        return word.upper()
    return "-".join(_name_part(part) for part in word.split("-"))


def _name_part(part: str) -> str:
    """One hyphen-free part of a name, cased by the rules :func:`person_name` lists."""
    if not any(character in _VOWELS for character in part.lower()):
        return part.upper()
    tokens = _NAME_SEPARATOR_RE.split(part)
    cased = [tokens[0].capitalize()]
    for index in range(1, len(tokens), 2):
        separator, before, piece = tokens[index], tokens[index - 1], tokens[index + 1]
        capitalize = separator == "." or len(before) == 1
        cased.extend([separator, piece.capitalize() if capitalize else piece.lower()])
    joined = "".join(cased)
    if joined.startswith(_MC_PREFIX) and len(joined) > len(_MC_PREFIX):
        rest = joined[len(_MC_PREFIX) :]
        return f"{_MC_PREFIX}{rest[0].upper()}{rest[1:]}"
    return joined


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
