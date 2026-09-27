"""The names people search the aircraft types by: ICAO designators and popular names.

Nobody types ``172S`` when they mean a Skyhawk; they type ``c172`` or ``skyhawk``.
:data:`ALIASES` maps each such name to the display make and the start of the display
model it means, and :func:`write_aliases` points each one at the aircraft type that
matches, so the type search can answer an alias exactly.
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.db.models.functions import Length

from apps.aircraft.models import AircraftType, AircraftTypeAlias

log = logging.getLogger(__name__)

#: A lower-case alias, mapped to the display ``(make, model prefix)`` of the type it
#: names.  The designators are ICAO DOC 8643's for the light aircraft a DART flies.
ALIASES: dict[str, tuple[str, str]] = {
    # -- Cessna ---------------------------------------------------------------
    "c150": ("Cessna", "150"),
    "c152": ("Cessna", "152"),
    "c162": ("Cessna", "162"),
    "skycatcher": ("Cessna", "162"),
    "c170": ("Cessna", "170"),
    "c172": ("Cessna", "172"),
    "skyhawk": ("Cessna", "172"),
    "c175": ("Cessna", "175"),
    "skylark": ("Cessna", "175"),
    "c177": ("Cessna", "177"),
    "cardinal": ("Cessna", "177"),
    "c180": ("Cessna", "180"),
    "skywagon": ("Cessna", "180"),
    "c182": ("Cessna", "182"),
    "skylane": ("Cessna", "182"),
    "c185": ("Cessna", "185"),
    "c188": ("Cessna", "188"),
    "ag wagon": ("Cessna", "188"),
    "c195": ("Cessna", "195"),
    "businessliner": ("Cessna", "195"),
    "c206": ("Cessna", "206"),
    "stationair": ("Cessna", "206"),
    "c207": ("Cessna", "207"),
    "c208": ("Cessna", "208"),
    "caravan": ("Cessna", "208"),
    "c210": ("Cessna", "210"),
    "centurion": ("Cessna", "210"),
    "c310": ("Cessna", "310"),
    "c337": ("Cessna", "337"),
    "skymaster": ("Cessna", "337"),
    "c340": ("Cessna", "340"),
    "c414": ("Cessna", "414"),
    "chancellor": ("Cessna", "414"),
    "c421": ("Cessna", "421"),
    "golden eagle": ("Cessna", "421"),
    "c425": ("Cessna", "425"),
    "c441": ("Cessna", "441"),
    "conquest": ("Cessna", "441"),
    "c25a": ("Cessna", "525A"),
    "citation cj2": ("Cessna", "525A"),
    "c25b": ("Cessna", "525B"),
    "citation cj3": ("Cessna", "525B"),
    "c56x": ("Cessna", "560XL"),
    "citation excel": ("Cessna", "560XL"),
    # -- Piper ----------------------------------------------------------------
    "j3": ("Piper", "J3C-65"),
    "cub": ("Piper", "J3C-65"),
    "pa11": ("Piper", "PA-11"),
    "cub special": ("Piper", "PA-11"),
    "pa12": ("Piper", "PA-12"),
    "super cruiser": ("Piper", "PA-12"),
    "pa18": ("Piper", "PA-18"),
    "super cub": ("Piper", "PA-18"),
    "pa20": ("Piper", "PA-20"),
    "pacer": ("Piper", "PA-20"),
    "pa22": ("Piper", "PA-22"),
    "tri-pacer": ("Piper", "PA-22"),
    "pa23": ("Piper", "PA-23"),
    "aztec": ("Piper", "PA-23"),
    "pa24": ("Piper", "PA-24"),
    "comanche": ("Piper", "PA-24"),
    "pa25": ("Piper", "PA-25"),
    "pawnee": ("Piper", "PA-25"),
    "p28a": ("Piper", "PA-28"),
    "cherokee": ("Piper", "PA-28"),
    "archer": ("Piper", "PA-28"),
    "warrior": ("Piper", "PA-28"),
    "p28b": ("Piper", "PA-28-236"),
    "dakota": ("Piper", "PA-28-236"),
    "p28r": ("Piper", "PA-28R"),
    "arrow": ("Piper", "PA-28R"),
    "pa30": ("Piper", "PA-30"),
    "twin comanche": ("Piper", "PA-30"),
    "pa31": ("Piper", "PA-31"),
    "navajo": ("Piper", "PA-31"),
    "p32r": ("Piper", "PA-32R"),
    "saratoga": ("Piper", "PA-32R"),
    "pa32": ("Piper", "PA-32"),
    "cherokee six": ("Piper", "PA-32"),
    "pa34": ("Piper", "PA-34"),
    "seneca": ("Piper", "PA-34"),
    "pa38": ("Piper", "PA-38-112"),
    "tomahawk": ("Piper", "PA-38-112"),
    "pa44": ("Piper", "PA-44"),
    "seminole": ("Piper", "PA-44"),
    "pa46": ("Piper", "PA-46-310P"),
    "malibu": ("Piper", "PA-46-310P"),
    "p46t": ("Piper", "PA-46-500TP"),
    "meridian": ("Piper", "PA-46-500TP"),
    "pa47": ("Piper", "PA-47"),
    "piperjet": ("Piper", "PA-47"),
    # -- Beechcraft -----------------------------------------------------------
    "be23": ("Beechcraft", "23"),
    "musketeer": ("Beechcraft", "23"),
    "be24": ("Beechcraft", "C24R"),
    "sierra": ("Beechcraft", "C24R"),
    "be33": ("Beechcraft", "35-33"),
    "debonair": ("Beechcraft", "35-33"),
    "be35": ("Beechcraft", "35"),
    "be36": ("Beechcraft", "A36"),
    "bonanza": ("Beechcraft", "A36"),
    "be55": ("Beechcraft", "95-55"),
    "be58": ("Beechcraft", "58"),
    "baron": ("Beechcraft", "58"),
    "be60": ("Beechcraft", "60"),
    "duke": ("Beechcraft", "60"),
    "be76": ("Beechcraft", "76"),
    "duchess": ("Beechcraft", "76"),
    "be77": ("Beechcraft", "77"),
    "skipper": ("Beechcraft", "77"),
    "be9l": ("Beechcraft", "C90"),
    "king air": ("Beechcraft", "C90"),
    "be20": ("Beechcraft", "B200"),
    "be18": ("Beechcraft", "D18S"),
    "twin beech": ("Beechcraft", "D18S"),
    # -- Cirrus, Diamond, Mooney ---------------------------------------------
    "sr20": ("Cirrus", "SR20"),
    "sr22": ("Cirrus", "SR22"),
    "s22t": ("Cirrus", "SR22T"),
    "sf50": ("Cirrus", "SF50"),
    "vision jet": ("Cirrus", "SF50"),
    "da20": ("Diamond", "DA20-C1"),
    "katana": ("Diamond", "DA20-C1"),
    "da40": ("Diamond", "DA 40"),
    "diamond star": ("Diamond", "DA 40"),
    "da42": ("Diamond", "DA 42"),
    "twin star": ("Diamond", "DA 42"),
    "da62": ("Diamond", "DA 62"),
    "m20p": ("Mooney", "M20J"),
    "m20t": ("Mooney", "M20K"),
    "ovation": ("Mooney", "M20R"),
    "acclaim": ("Mooney", "M20TN"),
    # -- Grumman American, Maule, Aviat, American Champion, Bellanca ---------
    "aa1": ("Grumman American", "AA-1"),
    "yankee": ("Grumman American", "AA-1"),
    "aa5": ("Grumman American", "AA-5"),
    "tiger": ("Grumman American", "AA-5B"),
    "mx7": ("Maule", "M-7"),
    "super rocket": ("Maule", "M-7"),
    "bl8": ("Aviat", "A-1"),
    "husky": ("Aviat", "A-1"),
    "pts2": ("Aviat", "Pitts S-2"),
    "pitts": ("Aviat", "Pitts S-2"),
    "ch7a": ("American Champion", "7ECA"),
    "citabria": ("American Champion", "7ECA"),
    "deca": ("American Champion", "8KCAB"),
    "decathlon": ("American Champion", "8KCAB"),
    "bl17": ("Bellanca", "17-30"),
    "viking": ("Bellanca", "17-30"),
    # -- Experimental and kit -------------------------------------------------
    "rv4": ("Van's", "RV-4"),
    "rv6": ("Van's", "RV-6"),
    "rv7": ("Van's", "RV-7"),
    "rv8": ("Van's", "RV-8"),
    "rv9": ("Van's", "RV-9"),
    "rv12": ("Van's", "RV-12"),
    "rv14": ("Van's", "RV-14"),
    "lnc4": ("Lancair", "IV-P"),
    "velo": ("Velocity", "Velocity"),
    "kitf": ("Foxair", "Kitfox Light Sport"),
    "kitfox": ("Foxair", "Kitfox Light Sport"),
    "snky": ("Rans", "S-7"),
    "courier": ("Rans", "S-7"),
    "carbon cub": ("CubCrafters", "CC11-160"),
    # -- Light sport ----------------------------------------------------------
    "ctls": ("Flight Design", "CTLS"),
    "icon": ("Icon", "A5"),
    "a5": ("Icon", "A5"),
    "slg2": ("Pipistrel", "Sinus"),
    "sinus": ("Pipistrel", "Sinus"),
    "viru": ("Pipistrel", "Virus SW"),
    "virus": ("Pipistrel", "Virus SW"),
    "tecn": ("Tecnam", "P2008"),
    "p2006": ("Tecnam", "P2006T"),
    "eurofox": ("Aeropro", "Eurofox"),
    # -- Amphibian and utility ------------------------------------------------
    "dhc2": ("de Havilland", "DHC-2"),
    "beaver": ("de Havilland", "DHC-2"),
    "dhc6": ("de Havilland", "DHC-6"),
    "twin otter": ("de Havilland", "DHC-6"),
    "lake": ("Lake", "LA-4"),
    "buccaneer": ("Lake", "LA-4"),
    "ac11": ("Aero Commander", "100"),
    "darter": ("Aero Commander", "100"),
    "ac50": ("Aero Commander", "500"),
    "shrike": ("Aero Commander", "500"),
    "pc12": ("Pilatus", "PC-12"),
    "tbm7": ("Daher", "TBM 700"),
    "tbm9": ("Daher", "TBM 700"),
    "epic": ("Epic", "E1000"),
    # -- Helicopters ----------------------------------------------------------
    "r22": ("Robinson", "R22"),
    "r44": ("Robinson", "R44"),
    "r66": ("Robinson", "R66"),
    "b06": ("Bell", "206B"),
    "jetranger": ("Bell", "206B"),
    "b407": ("Bell", "407"),
    "as50": ("Airbus", "AS 350 B2"),
    "astar": ("Airbus", "AS 350 B2"),
    "ecureuil": ("Airbus", "AS 350 B2"),
    "h125": ("Airbus", "AS350B3"),
    "ec30": ("Airbus", "EC 130"),
    "s76": ("Sikorsky", "S-76C"),
    "md5n": ("MD Helicopters", "369E"),
    "md 500": ("MD Helicopters", "369E"),
}


def resolve_alias(make: str, model_prefix: str) -> AircraftType | None:
    """The aircraft type an alias's ``(make, model_prefix)`` names, or ``None``.

    The type's display make equals ``make`` and its display model starts with
    ``model_prefix``, both compared case-insensitively.  Of several such types the one
    with the shortest model is chosen, then the first by model name.
    """
    return (
        AircraftType.objects.filter(make__iexact=make, model__istartswith=model_prefix)
        .order_by(Length("model"), "model", "pk")
        .first()
    )


@transaction.atomic
def write_aliases() -> int:
    """Write an ``AircraftTypeAlias`` row for each alias of :data:`ALIASES` that resolves.

    Each alias is pointed at :func:`resolve_alias`'s type, replacing whatever it
    pointed at before; an alias that resolves to nothing has its row removed, is
    logged, and is skipped.  Returns the number of alias rows written.
    """
    written = 0
    for alias, (make, model_prefix) in ALIASES.items():
        target = resolve_alias(make, model_prefix)
        if target is None:
            AircraftTypeAlias.objects.filter(alias=alias).delete()
            log.info("Alias %r names no aircraft type (%s %s); skipped.", alias, make, model_prefix)
            continue
        AircraftTypeAlias.objects.update_or_create(alias=alias, defaults={"type": target})
        written += 1
    return written
