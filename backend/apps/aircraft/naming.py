"""Display names for the aircraft types: one way to write each manufacturer and model.

The FAA registry spells one manufacturer several ways (``CESSNA``, ``CESSNA AIRCRAFT
CO``) and writes everything in capitals.  Every screen, report, and email prints the
names these functions give, so a type always reads the same way wherever it appears.
"""

from __future__ import annotations

import re

#: The display name of each FAA manufacturer spelling a DART meets.  A spelling not
#: listed here is tidied by :func:`display_make` instead.
MAKE_NAMES: dict[str, str] = {
    "AERO COMMANDER": "Aero Commander",
    "AEROPRO CZ": "Aeropro",
    "AEROPRO CZ S R O": "Aeropro",
    "AEROPRO S R O": "Aeropro",
    "AIRBUS HELICOPTERS": "Airbus",
    "AIRBUS HELICOPTERS INC": "Airbus",
    "AMERICAN CHAMPION AIRCRAFT": "American Champion",
    "AMERICAN CHAMPION AIRCRAFT CORP": "American Champion",
    "AMERICAN EUROCOPTER CORP": "Airbus",
    "AMERICAN EUROCOPTER LLC": "Airbus",
    "AMERICAN GENERAL ACFT CORP": "Grumman American",
    "AVIAT AIRCRAFT INC": "Aviat",
    "AVIAT INC": "Aviat",
    "BEECH": "Beechcraft",
    "BEECH AIRCRAFT CORP": "Beechcraft",
    "BEECHCRAFT CORP": "Beechcraft",
    "BELL": "Bell",
    "BELL HELICOPTER TEXTRON": "Bell",
    "BELL HELICOPTER TEXTRON CANADA": "Bell",
    "BELL HELICOPTER TEXTRON INC": "Bell",
    "BELL TEXTRON CANADA LTD": "Bell",
    "BELL TEXTRON INC": "Bell",
    "BELLANCA": "Bellanca",
    "C A TECNAM SRL": "Tecnam",
    "CA TECNAM SRL": "Tecnam",
    "CESSNA": "Cessna",
    "CESSNA AIRCRAFT CO": "Cessna",
    "CHAMPION": "American Champion",
    "CHAMPION AIRCRAFT CORP": "American Champion",
    "CIRRUS DESIGN CORP": "Cirrus",
    "COMPAGNIE DAHER": "Daher",
    "COSTRUZIONI AERONAUTICHE TECNA": "Tecnam",
    "CUB CRAFTERS INC": "CubCrafters",
    "CUBCRAFTERS": "CubCrafters",
    "CUBCRAFTERS INC": "CubCrafters",
    "DAHER AEROSPACE": "Daher",
    "DAHER AIRCRAFT SAS": "Daher",
    "DE HAVILLAND": "de Havilland",
    "DEHAVILLAND": "de Havilland",
    "DEHAVILLAND CANADA": "de Havilland",
    "DIAMOND AIRCRAFT IND GMBH": "Diamond",
    "DIAMOND AIRCRAFT IND INC": "Diamond",
    "EADS SOCATA": "Daher",
    "EPIC AIRCRAFT LLC": "Epic",
    "EUROCOPTER": "Airbus",
    "EUROCOPTER DEUTSCHLAND GMBH": "Airbus",
    "EUROCOPTER FRANCE": "Airbus",
    "FLIGHT DESIGN GENERAL AVN GMBH": "Flight Design",
    "FLIGHT DESIGN GMBH": "Flight Design",
    "GRUMMAN AMERICAN AVN CORP": "Grumman American",
    "HAWKER BEECHCRAFT CORP": "Beechcraft",
    "HUGHES HELICOPTERS INC": "Hughes",
    "ICON AIRCRAFT INC": "Icon",
    "LAKE": "Lake",
    "LANCAIR": "Lancair",
    "LANCAIR COMPANY": "Lancair",
    "LANCAIR INTERNATIONAL INC": "Lancair",
    "LANCAIR INTL INC": "Lancair",
    "MAULE": "Maule",
    "MAULE AEROSPACE TECHNOLOGY INC": "Maule",
    "MCDONNELL DOUGLAS HELICOPTER": "MD Helicopters",
    "MD HELICOPTERS INC": "MD Helicopters",
    "MD HELICOPTERS LLC": "MD Helicopters",
    "MOONEY": "Mooney",
    "MOONEY AIRCRAFT CORP": "Mooney",
    "MOONEY AIRPLANE CO INC": "Mooney",
    "MOONEY INTERNATIONAL CORP": "Mooney",
    "NEW PIPER AIRCRAFT INC": "Piper",
    "PILATUS": "Pilatus",
    "PILATUS AIRCRAFT LTD": "Pilatus",
    "PIPER": "Piper",
    "PIPER AIRCRAFT CORP": "Piper",
    "PIPER AIRCRAFT INC": "Piper",
    "PIPISTREL": "Pipistrel",
    "PIPISTREL D O O": "Pipistrel",
    "PIPISTREL DOO AJDOVSCINA": "Pipistrel",
    "PIPISTREL ITALIA S R L": "Pipistrel",
    "PIPISTREL LSA S R L": "Pipistrel",
    "PIPISTREL LSA SRL": "Pipistrel",
    "RANS": "Rans",
    "RANS DESIGNS INC": "Rans",
    "RANS INC": "Rans",
    "RAYTHEON AIRCRAFT COMPANY": "Beechcraft",
    "ROBINSON HELICOPTER": "Robinson",
    "ROBINSON HELICOPTER CO": "Robinson",
    "ROBINSON HELICOPTER COMPANY": "Robinson",
    "SIKORSKY": "Sikorsky",
    "SOCATA": "Daher",
    "TECNAM": "Tecnam",
    "VANS": "Van's",
    "VANS ACFT INC": "Van's",
    "VANS AIRCRAFT": "Van's",
    "VANS AIRCRAFT INC": "Van's",
}

#: A manufacturer spelling the FAA uses for two makes, mapped to the model prefixes that
#: belong to the first make, that make, and the make every other model belongs to.
#: Textron Aviation holds both the Cessna and the Beechcraft type certificates and
#: registers both under one name: the Beechcraft models are the King Airs (``B200``,
#: ``B300``, ``C90``), the Bonanza (``G36``), the Baron (``G58``), the Debonair
#: (``F33``), and the T-6 trainers (``AT6``, ``3000``).
SHARED_MAKES: dict[str, tuple[tuple[str, ...], str, str]] = {
    "TEXTRON AVIATION INC": (
        ("3000", "AT-6", "AT6", "B200", "B300", "C90", "F33", "G36", "G58"),
        "Beechcraft",
        "Cessna",
    ),
}

#: The corporate words :func:`display_make` drops from a manufacturer it does not know.
CORPORATE_TOKENS: frozenset[str] = frozenset(
    {"INC", "CORP", "CO", "LLC", "LTD", "IND", "AVN", "ACFT", "MFG"}
)

#: ``S R O`` (a Czech company form), written as the FAA writes it, at the end of a name.
_SRO = re.compile(r"(?:^|\s)S R O$")

#: A model token kept as the FAA writes it when it is this short, even without a digit.
SHORT_TOKEN_LENGTH = 3


def display_make(faa_make: str, faa_model: str = "") -> str:
    """Return the display name of the FAA manufacturer ``faa_make``.

    The string is upper-cased, stripped, its runs of spaces collapsed, and its full
    stops dropped.  A spelling of :data:`SHARED_MAKES` is told apart by ``faa_model``:
    ``TEXTRON AVIATION INC`` is ``Beechcraft`` for a model starting ``G36``, ``B200``,
    or another of its Beechcraft prefixes, and ``Cessna`` for any other model,
    ``faa_model`` omitted included.  Otherwise the spelling is looked up in
    :data:`MAKE_NAMES` (``CESSNA AIRCRAFT CO`` is ``Cessna``, ``BEECH`` is
    ``Beechcraft``, ``MOONEY AIRCRAFT CORP.`` is ``Mooney``).  A spelling that is not
    listed loses a trailing ``S R O`` and the words of :data:`CORPORATE_TOKENS`, and
    each remaining word is title-cased: ``FOO AIRCRAFT CORP`` is ``Foo Aircraft``.
    """
    spaced = " ".join(faa_make.upper().replace(".", "").split())
    if spaced in SHARED_MAKES:
        prefixes, first, other = SHARED_MAKES[spaced]
        return first if faa_model.strip().upper().startswith(prefixes) else other
    if spaced in MAKE_NAMES:
        return MAKE_NAMES[spaced]
    words = [word for word in _SRO.sub("", spaced).split() if word not in CORPORATE_TOKENS]
    return " ".join(_title(word) for word in words)


def display_model(faa_model: str) -> str:
    """Return the display name of the FAA model ``faa_model``.

    Each space-separated token that holds a digit, or is at most three characters, is
    kept as it is (``172S``, ``PA-28-181``, ``DA 40``); any longer token of letters is
    title-cased, each hyphenated part on its own (``SKYHAWK`` is ``Skyhawk``,
    ``TRI-PACER`` is ``Tri-Pacer``).  Runs of spaces collapse to one.
    """
    return " ".join(_model_token(token) for token in faa_model.split())


def _model_token(token: str) -> str:
    """One token of a model name, kept or title-cased by :func:`display_model`'s rule."""
    if any(character.isdigit() for character in token) or len(token) <= SHORT_TOKEN_LENGTH:
        return token
    return _title(token)


def _title(word: str) -> str:
    """``word`` with each hyphenated part capitalized: ``TRI-PACER`` is ``Tri-Pacer``."""
    return "-".join(part.capitalize() for part in word.split("-"))
