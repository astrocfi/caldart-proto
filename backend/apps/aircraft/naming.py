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
    "AEROPRO S R O": "Aeropro",
    "AIRBUS HELICOPTERS": "Airbus",
    "AIRBUS HELICOPTERS INC": "Airbus",
    "AMERICAN CHAMPION AIRCRAFT": "American Champion",
    "AMERICAN CHAMPION AIRCRAFT CORP": "American Champion",
    "AMERICAN GENERAL ACFT CORP": "Grumman American",
    "AVIAT AIRCRAFT INC": "Aviat",
    "BEECH": "Beechcraft",
    "BEECH AIRCRAFT CORP": "Beechcraft",
    "BEECHCRAFT CORP": "Beechcraft",
    "BELL HELICOPTER TEXTRON": "Bell",
    "BELL HELICOPTER TEXTRON INC": "Bell",
    "BELLANCA": "Bellanca",
    "CESSNA": "Cessna",
    "CESSNA AIRCRAFT CO": "Cessna",
    "CHAMPION": "American Champion",
    "CHAMPION AIRCRAFT CORP": "American Champion",
    "CIRRUS DESIGN CORP": "Cirrus",
    "CUBCRAFTERS": "CubCrafters",
    "CUBCRAFTERS INC": "CubCrafters",
    "DAHER AEROSPACE": "Daher",
    "DE HAVILLAND": "de Havilland",
    "DIAMOND AIRCRAFT IND GMBH": "Diamond",
    "DIAMOND AIRCRAFT IND INC": "Diamond",
    "EPIC AIRCRAFT LLC": "Epic",
    "EUROCOPTER": "Airbus",
    "FLIGHT DESIGN GMBH": "Flight Design",
    "GRUMMAN AMERICAN AVN CORP": "Grumman American",
    "HAWKER BEECHCRAFT CORP": "Beechcraft",
    "ICON AIRCRAFT INC": "Icon",
    "LAKE": "Lake",
    "LANCAIR": "Lancair",
    "MAULE": "Maule",
    "MAULE AEROSPACE TECHNOLOGY INC": "Maule",
    "MD HELICOPTERS INC": "MD Helicopters",
    "MOONEY": "Mooney",
    "MOONEY AIRCRAFT CORP": "Mooney",
    "MOONEY INTERNATIONAL CORP": "Mooney",
    "NEW PIPER AIRCRAFT INC": "Piper",
    "PILATUS AIRCRAFT LTD": "Pilatus",
    "PIPER": "Piper",
    "PIPER AIRCRAFT CORP": "Piper",
    "PIPER AIRCRAFT INC": "Piper",
    "PIPISTREL": "Pipistrel",
    "RAYTHEON AIRCRAFT COMPANY": "Beechcraft",
    "ROBINSON HELICOPTER": "Robinson",
    "ROBINSON HELICOPTER CO": "Robinson",
    "SIKORSKY": "Sikorsky",
    "SOCATA": "Daher",
    "TECNAM": "Tecnam",
    "VANS": "Van's",
    "VANS AIRCRAFT INC": "Van's",
}

#: The corporate words :func:`display_make` drops from a manufacturer it does not know.
CORPORATE_TOKENS: frozenset[str] = frozenset(
    {"INC", "CORP", "CO", "LLC", "LTD", "IND", "AVN", "ACFT", "MFG"}
)

#: ``S R O`` (a Czech company form), written as the FAA writes it, at the end of a name.
_SRO = re.compile(r"(?:^|\s)S R O$")

#: A model token kept as the FAA writes it when it is this short, even without a digit.
SHORT_TOKEN_LENGTH = 3


def display_make(faa_make: str) -> str:
    """Return the display name of the FAA manufacturer ``faa_make``.

    The string is stripped, its runs of spaces collapsed, and looked up in
    :data:`MAKE_NAMES` (``CESSNA AIRCRAFT CO`` is ``Cessna``, ``BEECH`` is
    ``Beechcraft``).  A spelling that is not listed loses a trailing ``S R O``, its full
    stops, and the words of :data:`CORPORATE_TOKENS`, and each remaining word is
    title-cased: ``FOO AIRCRAFT CORP`` is ``Foo Aircraft``.
    """
    spaced = " ".join(faa_make.upper().split())
    if spaced in MAKE_NAMES:
        return MAKE_NAMES[spaced]
    without_sro = _SRO.sub("", spaced.replace(".", ""))
    words = [word for word in without_sro.split() if word not in CORPORATE_TOKENS]
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
